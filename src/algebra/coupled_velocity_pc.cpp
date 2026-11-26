#include "eonsim/coupled_velocity_pc.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <tuple>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity validation communication failed");
    if(any) throw std::runtime_error("Coupled velocity: "+message);
}
void option_default(const std::string& name,const char* value) {
    PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&set));
    if(!set) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
void common_choice(MPI_Comm comm,int value,bool valid,const std::string& message) {
    int lo=0,hi=0;
    if(MPI_Allreduce(&value,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&value,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity option reduction failed");
    common_check(comm,valid&&lo==hi,message);
}
void response_options(MPI_Comm comm,const std::string& prefix) {
    char value[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+prefix+"ksp_type").c_str(),value,sizeof(value),&set));
    const std::string type=set?value:KSPPREONLY;
    const int choice=type==KSPPREONLY?1:type==KSPFGMRES?2:0;
    common_choice(comm,choice,choice!=0,"response requires identical preonly or fgmres on every rank at "+prefix);
    PetscBool distinct=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,("-"+prefix+"pc_mg_distinct_smoothup").c_str(),&distinct,nullptr));
    common_choice(comm,distinct,true,"distinct smoother selection differs between ranks at "+prefix);
}
void smoother_defaults(KSP solver) {
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPRICHARDSON));
    EONSIM_PETSC(KSPSetNormType(solver,KSP_NORM_NONE));
    EONSIM_PETSC(KSPSetTolerances(solver,PETSC_DEFAULT,PETSC_DEFAULT,PETSC_DEFAULT,1));
    EONSIM_PETSC(PCSetType(pc,PCASM));
    EONSIM_PETSC(PCASMSetOverlap(pc,1));
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    option_default(base+"sub_ksp_type","preonly");
    option_default(base+"sub_pc_type","ilu");
    option_default(base+"sub_pc_factor_levels","1");
    option_default(base+"sub_pc_factor_mat_ordering_type","rcm");
    EONSIM_PETSC(KSPSetFromOptions(solver));
}
// Subdomain modes deliberately remain separate across material domains and
// finite-element spaces; equal component numbers alone do not identify a mode.
using Mode=std::tuple<DofDomain,DofEntity,std::uint16_t,std::uint16_t,std::uint16_t>;
struct Group { std::vector<PetscInt> rows; };
struct SparseMode {
    std::vector<PetscInt> rows;
    std::vector<PetscScalar> values;
};
struct FineRows {
    Mat matrix=nullptr,preconditioner=nullptr;
    PetscInt begin=0,end=0,global=0;
    std::vector<char> active;
};
FineRows fine_rows(MPI_Comm comm,KSP solver,const std::vector<DofKey>& semantics,
                  const std::vector<std::array<double,3>>& coordinates,bool rigid,bool gamg) {
    common_choice(comm,rigid,true,"rigid-mode selection differs between ranks");
    FineRows fine;
    EONSIM_PETSC(KSPGetOperators(solver,&fine.matrix,&fine.preconditioner));
    PetscInt columns=0,pbegin=0,pend=0,prows=0,pcolumns=0,cbegin=0,cend=0,pcbegin=0,pcend=0;
    EONSIM_PETSC(MatGetOwnershipRange(fine.matrix,&fine.begin,&fine.end));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(fine.matrix,&cbegin,&cend));
    EONSIM_PETSC(MatGetSize(fine.matrix,&fine.global,&columns));
    EONSIM_PETSC(MatGetOwnershipRange(fine.preconditioner,&pbegin,&pend));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(fine.preconditioner,&pcbegin,&pcend));
    EONSIM_PETSC(MatGetSize(fine.preconditioner,&prows,&pcolumns));
    common_check(comm,fine.global==columns&&fine.end-fine.begin==static_cast<PetscInt>(semantics.size())&&
                 pbegin==fine.begin&&pend==fine.end&&prows==fine.global&&pcolumns==columns&&
                 cbegin==fine.begin&&cend==fine.end&&pcbegin==fine.begin&&pcend==fine.end,
                 "owned metadata or preconditioner does not match the coupled matrix");
    common_check(comm,(!rigid&&coordinates.empty())||coordinates.size()==semantics.size(),
                 "rigid modes require reference coordinates in owned row order");
    fine.active.resize(semantics.size());
    bool valid=true;
    for(PetscInt row=fine.begin;row<fine.end;++row) {
        const auto& key=semantics[row-fine.begin];
        valid=valid&&key.quantity==DofQuantity::velocity&&
            (key.domain==DofDomain::fluid||key.domain==DofDomain::solid)&&key.component<3;
        if(gamg||rigid) valid=valid&&((key.kind==DofEntity::vertex&&key.mode==0&&key.space==1)||
            (key.kind==DofEntity::body&&key.domain==DofDomain::solid&&key.component==0));
        if(rigid&&key.kind==DofEntity::vertex)
            for(double x:coordinates[row-fine.begin]) valid=valid&&std::isfinite(x);
        PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(fine.matrix,row,&count,&indices,&values));
        bool identity=true,diagonal=false;
        for(PetscInt j=0;j<count;++j) {
            valid=valid&&std::isfinite(values[j]);
            if(indices[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
            else identity=identity&&values[j]==0.;
        }
        EONSIM_PETSC(MatRestoreRow(fine.matrix,row,&count,&indices,&values));
        // MatZeroRows retains structural zero entries. Identity is numerical.
        fine.active[row-fine.begin]=!(identity&&diagonal);
    }
    if(gamg) {
        PetscInt block_size=0; EONSIM_PETSC(MatGetBlockSize(fine.preconditioner,&block_size));
        valid=valid&&block_size==1;
    }
    common_check(comm,valid,"nonfinite matrix/coordinates or unsupported velocity semantics (rigid/GAMG requires vertex P1 or a body scalar, GAMG requires scalar AIJ)");
    return fine;
}
long double reduced_sum(MPI_Comm comm,long double local,bool distributed) {
    if(!distributed) return local;
    long double global=0;
    if(MPI_Allreduce(&local,&global,1,MPI_LONG_DOUBLE,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Coupled velocity mode reduction failed");
    return global;
}
// Keep sparse owner-local storage even for global modes. Only scalar products,
// never complete fields, are reduced. Two passes resolve constrained/partial
// component and collinear geometries without adding an arbitrary regularizer.
bool append_mode(MPI_Comm comm,PetscInt begin,std::vector<PetscScalar> candidate,
                 std::vector<SparseMode>& modes,bool distributed) {
    long double initial_squared=0;
    for(auto value:candidate) initial_squared+=static_cast<long double>(value)*value;
    const auto initial=std::sqrt(reduced_sum(comm,initial_squared,distributed));
    if(initial==0) return true;
    for(int pass=0;pass<2;++pass) for(const auto& mode:modes) {
        long double local=0;
        for(std::size_t j=0;j<mode.rows.size();++j)
            local+=static_cast<long double>(mode.values[j])*candidate[mode.rows[j]-begin];
        const auto product=reduced_sum(comm,local,distributed);
        for(std::size_t j=0;j<mode.rows.size();++j)
            candidate[mode.rows[j]-begin]-=static_cast<double>(product*mode.values[j]);
    }
    long double squared=0;
    for(auto value:candidate) squared+=static_cast<long double>(value)*value;
    const auto norm=std::sqrt(reduced_sum(comm,squared,distributed));
    if(!std::isfinite(initial)||!std::isfinite(norm)) return false;
    // Coordinates are centered and scaled before rotations are formed. This
    // threshold is relative to that dimensionless basis, not physical units.
    const long double threshold=256*std::numeric_limits<double>::epsilon()*std::max(1.L,initial);
    if(norm<=threshold) return true;
    SparseMode result;
    for(std::size_t i=0;i<candidate.size();++i) if(candidate[i]!=0) {
        result.rows.push_back(begin+static_cast<PetscInt>(i));
        result.values.push_back(static_cast<double>(candidate[i]/norm));
    }
    modes.push_back(std::move(result));
    return true;
}
struct CoordinateFrame { std::array<long double,3> center{}; long double scale=0; };
CoordinateFrame coordinate_frame(PetscInt begin,const std::vector<PetscInt>& rows,
    const std::vector<std::array<double,3>>& coordinates) {
    CoordinateFrame frame;
    long double sums[4]{};
    for(auto row:rows) {
        for(int c=0;c<3;++c) sums[c]+=coordinates[row-begin][c];
        ++sums[3];
    }
    if(sums[3]>0) for(int c=0;c<3;++c) frame.center[c]=sums[c]/sums[3];
    for(auto row:rows) for(int c=0;c<3;++c)
        frame.scale=std::max(frame.scale,std::abs(static_cast<long double>(coordinates[row-begin][c])-frame.center[c]));
    return frame;
}
double rotation_component(const CoordinateFrame& frame,const std::array<double,3>& coordinate,
                          int component,int axis) {
    if(frame.scale==0||component==axis) return 0;
    const int positive=(axis+1)%3,negative=(axis+2)%3;
    const auto value=component==negative?
        static_cast<long double>(coordinate[positive])-frame.center[positive]:
        frame.center[negative]-static_cast<long double>(coordinate[negative]);
    return static_cast<double>(value/frame.scale);
}
std::vector<SparseMode> local_modes(MPI_Comm comm,const FineRows& fine,
    const std::vector<DofKey>& semantics,const std::vector<std::array<double,3>>& coordinates,bool rigid) {
    std::map<Mode,Group> groups;
    for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) {
        const auto& key=semantics[row-fine.begin];
        groups[{key.domain,key.kind,key.component,key.mode,key.space}].rows.push_back(row);
    }
    std::vector<SparseMode> modes;
    for(const auto& group:groups) {
        const auto& rows=group.second.rows;
        modes.push_back({rows,std::vector<PetscScalar>(rows.size(),1./std::sqrt(static_cast<double>(rows.size())))});
    }
    if(rigid) {
        using VectorGroup=std::tuple<DofEntity,std::uint16_t,std::uint16_t>;
        std::map<VectorGroup,std::vector<PetscInt>> solid;
        for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) {
            const auto& key=semantics[row-fine.begin];
            if(key.domain==DofDomain::solid&&key.kind==DofEntity::vertex&&key.mode==0&&key.space==1)
                solid[{key.kind,key.mode,key.space}].push_back(row);
        }
        bool valid=true;
        for(const auto& group:solid) {
            const auto frame=coordinate_frame(fine.begin,group.second,coordinates);
            for(int axis=0;axis<3;++axis) {
                std::vector<PetscScalar> candidate(fine.end-fine.begin,0);
                for(auto row:group.second) candidate[row-fine.begin]=rotation_component(
                    frame,coordinates[row-fine.begin],semantics[row-fine.begin].component,axis);
                valid=append_mode(comm,fine.begin,std::move(candidate),modes,false)&&valid;
            }
        }
        common_check(comm,valid,"nonfinite local rigid-motion orthogonalization");
    }
    return modes;
}
// Form a bounded, connected first coarse grid without imposing a packed xyz
// layout on the constraint-reduced operator. Local QR works only on an
// aggregate's rows: memory and arithmetic remain linear in owned fine rows.
std::vector<SparseMode> aggregate_modes(MPI_Comm comm,const FineRows& fine,
    const std::vector<DofKey>& semantics,const std::vector<std::array<double,3>>& coordinates,
    bool rigid,PetscInt maximum_nodes) {
    using Family=std::tuple<DofDomain,DofEntity,std::uint16_t,std::uint16_t>;
    struct Node { DofKey key; std::vector<PetscInt> rows,neighbors; };
    std::map<DofKey,PetscInt> node_ids;
    std::vector<Node> nodes;
    std::vector<PetscInt> row_node(semantics.size(),-1);
    for(PetscInt i=0;i<static_cast<PetscInt>(semantics.size());++i) if(fine.active[i]) {
        auto key=semantics[i]; key.component=0;
        auto found=node_ids.find(key);
        if(found==node_ids.end()) {
            const auto index=static_cast<PetscInt>(nodes.size());
            found=node_ids.emplace(key,index).first;
            nodes.push_back({key,{},{}});
        }
        row_node[i]=found->second;
        nodes[found->second].rows.push_back(fine.begin+i);
    }
    const auto family=[](const DofKey& key) { return Family{key.domain,key.kind,key.mode,key.space}; };
    for(PetscInt i=0;i<static_cast<PetscInt>(nodes.size());++i) {
        auto& node=nodes[i];
        for(auto row:node.rows) {
            PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(fine.matrix,row,&count,&columns,&values));
            for(PetscInt j=0;j<count;++j) if(columns[j]>=fine.begin&&columns[j]<fine.end) {
                const auto neighbor=row_node[columns[j]-fine.begin];
                if(neighbor>=0&&neighbor!=i&&family(nodes[neighbor].key)==family(node.key))
                    node.neighbors.push_back(neighbor);
            }
            EONSIM_PETSC(MatRestoreRow(fine.matrix,row,&count,&columns,&values));
        }
        std::sort(node.neighbors.begin(),node.neighbors.end());
        node.neighbors.erase(std::unique(node.neighbors.begin(),node.neighbors.end()),node.neighbors.end());
    }
    // Treat the structural adjacency as undirected even for nonsymmetric A.
    // Only the graph is symmetrized; the actual Galerkin operator remains A.
    for(PetscInt i=0;i<static_cast<PetscInt>(nodes.size());++i) {
        const auto neighbors=nodes[i].neighbors;
        for(auto j:neighbors) nodes[j].neighbors.push_back(i);
    }
    for(auto& node:nodes) {
        std::sort(node.neighbors.begin(),node.neighbors.end());
        node.neighbors.erase(std::unique(node.neighbors.begin(),node.neighbors.end()),node.neighbors.end());
    }
    std::vector<char> assigned(nodes.size(),0);
    std::vector<SparseMode> modes;
    bool valid=true;
    for(PetscInt seed=0;seed<static_cast<PetscInt>(nodes.size());++seed) if(!assigned[seed]) {
        std::vector<PetscInt> aggregate{seed}; assigned[seed]=1;
        for(std::size_t cursor=0;cursor<aggregate.size()&&aggregate.size()<static_cast<std::size_t>(maximum_nodes);++cursor)
            for(auto neighbor:nodes[aggregate[cursor]].neighbors) if(!assigned[neighbor]) {
                assigned[neighbor]=1; aggregate.push_back(neighbor);
                if(aggregate.size()==static_cast<std::size_t>(maximum_nodes)) break;
            }
        std::vector<PetscInt> rows;
        for(auto node:aggregate) rows.insert(rows.end(),nodes[node].rows.begin(),nodes[node].rows.end());
        std::sort(rows.begin(),rows.end());
        std::vector<std::vector<PetscScalar>> basis;
        const auto append=[&](std::vector<PetscScalar> candidate) {
            long double initial_squared=0;
            for(auto value:candidate) initial_squared+=static_cast<long double>(value)*value;
            const auto initial=std::sqrt(initial_squared);
            if(initial==0) return;
            for(int pass=0;pass<2;++pass) for(const auto& column:basis) {
                long double product=0;
                for(std::size_t i=0;i<rows.size();++i) product+=static_cast<long double>(column[i])*candidate[i];
                for(std::size_t i=0;i<rows.size();++i) candidate[i]-=static_cast<double>(product*column[i]);
            }
            long double squared=0;
            for(auto value:candidate) squared+=static_cast<long double>(value)*value;
            const auto norm=std::sqrt(squared);
            valid=valid&&std::isfinite(initial)&&std::isfinite(norm);
            if(norm<=256*std::numeric_limits<double>::epsilon()*std::max(1.L,initial)) return;
            for(auto& value:candidate) value=static_cast<double>(value/norm);
            basis.push_back(std::move(candidate));
        };
        for(int component=0;component<3;++component) {
            std::vector<PetscScalar> candidate(rows.size(),0);
            for(std::size_t i=0;i<rows.size();++i)
                candidate[i]=semantics[rows[i]-fine.begin].component==component?1.:0.;
            append(std::move(candidate));
        }
        if(rigid&&nodes[seed].key.domain==DofDomain::solid&&nodes[seed].key.kind==DofEntity::vertex) {
            const auto frame=coordinate_frame(fine.begin,rows,coordinates);
            for(int axis=0;axis<3;++axis) {
                std::vector<PetscScalar> candidate(rows.size(),0);
                for(std::size_t i=0;i<rows.size();++i) candidate[i]=rotation_component(frame,
                    coordinates[rows[i]-fine.begin],semantics[rows[i]-fine.begin].component,axis);
                append(std::move(candidate));
            }
        }
        for(auto& column:basis) {
            SparseMode mode;
            for(std::size_t i=0;i<rows.size();++i) if(column[i]!=0) {
                mode.rows.push_back(rows[i]); mode.values.push_back(column[i]);
            }
            modes.push_back(std::move(mode));
        }
    }
    common_check(comm,valid,"nonfinite aggregate coarse-space orthogonalization");
    return modes;
}
std::vector<SparseMode> scalar_mode(MPI_Comm comm,const FineRows& fine) {
    std::vector<SparseMode> modes;
    std::vector<PetscScalar> candidate(fine.end-fine.begin,0);
    for(PetscInt row=fine.begin;row<fine.end;++row) if(fine.active[row-fine.begin]) candidate[row-fine.begin]=1;
    const bool valid=append_mode(comm,fine.begin,std::move(candidate),modes,true);
    common_check(comm,valid,"nonfinite global scalar near mode");
    return modes;
}

// The candidate index denotes physical meaning, not an algebraic block size:
// fluid xyz, solid xyz, fluid rotations, solid rotations, scalar body motion.
// The same columns are propagated at every level. A scalar GAMG restarted on
// P^T A P would instead lose this information after the first transfer.
constexpr std::size_t field_candidate_count=13;
using FieldCandidate=std::array<PetscScalar,field_candidate_count>;
struct FieldLevel {
    std::vector<FieldCandidate> candidates;
    std::vector<std::vector<PetscInt>> blocks; // Local row offsets, no ghost copy.
};
struct FieldTransfer {
    PetscOwner<Mat,MatDestroy> interpolation;
    FieldLevel coarse;
    PetscInt global_size=0;
    double reproduction_error=0;
};
FieldLevel field_candidates(MPI_Comm comm,const FineRows& fine,
    const std::vector<DofKey>& semantics,const std::vector<std::array<double,3>>& coordinates,bool rigid) {
    FieldLevel data;
    data.candidates.resize(semantics.size());
    CoordinateFrame frame;
    if(rigid) {
        long double local[4]{},global[4]{};
        for(std::size_t row=0;row<semantics.size();++row)
            if(fine.active[row]&&semantics[row].kind==DofEntity::vertex) {
                for(int c=0;c<3;++c) local[c]+=coordinates[row][c];
                local[3]+=1;
            }
        if(MPI_Allreduce(local,global,4,MPI_LONG_DOUBLE,MPI_SUM,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Field AMG coordinate reduction failed");
        if(global[3]>0) for(int c=0;c<3;++c) frame.center[c]=global[c]/global[3];
        long double scale=0;
        for(std::size_t row=0;row<semantics.size();++row)
            if(fine.active[row]&&semantics[row].kind==DofEntity::vertex)
                for(int c=0;c<3;++c)
                    scale=std::max(scale,std::abs(static_cast<long double>(coordinates[row][c])-frame.center[c]));
        if(MPI_Allreduce(&scale,&frame.scale,1,MPI_LONG_DOUBLE,MPI_MAX,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Field AMG coordinate scale reduction failed");
    }
    std::map<DofKey,PetscInt> block_ids;
    for(PetscInt row=0;row<static_cast<PetscInt>(semantics.size());++row) if(fine.active[row]) {
        const auto& key=semantics[row];
        auto block_key=key; block_key.component=0;
        auto found=block_ids.find(block_key);
        if(found==block_ids.end()) {
            const auto index=static_cast<PetscInt>(data.blocks.size());
            found=block_ids.emplace(block_key,index).first;
            data.blocks.push_back({});
        }
        data.blocks[found->second].push_back(row);
        auto& candidate=data.candidates[row];
        if(key.kind==DofEntity::body) candidate[12]=1.;
        else {
            const bool solid=key.domain==DofDomain::solid;
            candidate[(solid?3:0)+key.component]=1.;
            if(rigid) for(int axis=0;axis<3;++axis)
                candidate[(solid?9:6)+axis]=rotation_component(frame,coordinates[row],key.component,axis);
        }
    }
    return data;
}

FieldTransfer field_transfer(MPI_Comm comm,Mat matrix,const FieldLevel& fine,PetscInt maximum_blocks) {
    PetscInt begin=0,end=0,global=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&global,nullptr));
    common_check(comm,end-begin==static_cast<PetscInt>(fine.candidates.size()),
                 "field AMG candidate ownership differs from its matrix");
    std::vector<PetscInt> row_block(fine.candidates.size(),-1);
    bool valid=true;
    for(PetscInt block=0;block<static_cast<PetscInt>(fine.blocks.size());++block)
        for(auto row:fine.blocks[block]) {
            if(row<0||row>=end-begin||row_block[row]!=-1) valid=false;
            else row_block[row]=block;
        }
    common_check(comm,valid,"field AMG blocks must be disjoint owned row sets");
    std::vector<std::vector<PetscInt>> neighbors(fine.blocks.size());
    for(PetscInt row=0;row<end-begin;++row) if(row_block[row]>=0) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,begin+row,&count,&columns,&values));
        for(PetscInt j=0;j<count;++j) if(columns[j]>=begin&&columns[j]<end) {
            const auto adjacent=row_block[columns[j]-begin];
            if(adjacent>=0&&adjacent!=row_block[row]) {
                neighbors[row_block[row]].push_back(adjacent);
                neighbors[adjacent].push_back(row_block[row]);
            }
        }
        EONSIM_PETSC(MatRestoreRow(matrix,begin+row,&count,&columns,&values));
    }
    for(auto& adjacent:neighbors) {
        std::sort(adjacent.begin(),adjacent.end());
        adjacent.erase(std::unique(adjacent.begin(),adjacent.end()),adjacent.end());
    }
    std::vector<char> assigned(fine.blocks.size(),0);
    std::vector<SparseMode> modes;
    FieldTransfer result;
    long double local_error=0,local_norm=0;
    for(PetscInt seed=0;seed<static_cast<PetscInt>(fine.blocks.size());++seed) if(!assigned[seed]) {
        std::vector<PetscInt> aggregate{seed}; assigned[seed]=1;
        for(std::size_t cursor=0;cursor<aggregate.size()&&aggregate.size()<static_cast<std::size_t>(maximum_blocks);++cursor)
            for(auto adjacent:neighbors[aggregate[cursor]]) if(!assigned[adjacent]) {
                assigned[adjacent]=1; aggregate.push_back(adjacent);
                if(aggregate.size()==static_cast<std::size_t>(maximum_blocks)) break;
            }
        std::vector<PetscInt> rows;
        for(auto block:aggregate) rows.insert(rows.end(),fine.blocks[block].begin(),fine.blocks[block].end());
        std::sort(rows.begin(),rows.end());
        std::vector<std::vector<PetscScalar>> basis;
        for(std::size_t component=0;component<field_candidate_count;++component) {
            std::vector<PetscScalar> candidate(rows.size());
            long double initial_squared=0;
            for(std::size_t i=0;i<rows.size();++i) {
                candidate[i]=fine.candidates[rows[i]][component];
                initial_squared+=static_cast<long double>(candidate[i])*candidate[i];
            }
            const auto initial=std::sqrt(initial_squared);
            if(initial==0) continue;
            for(int pass=0;pass<2;++pass) for(const auto& previous:basis) {
                long double product=0;
                for(std::size_t i=0;i<rows.size();++i) product+=static_cast<long double>(previous[i])*candidate[i];
                for(std::size_t i=0;i<rows.size();++i) candidate[i]-=static_cast<double>(product*previous[i]);
            }
            long double squared=0;
            for(auto value:candidate) squared+=static_cast<long double>(value)*value;
            const auto norm=std::sqrt(squared);
            valid=valid&&std::isfinite(initial)&&std::isfinite(norm);
            if(norm<=256*std::numeric_limits<double>::epsilon()*std::max(1.L,initial)) continue;
            for(auto& value:candidate) value=static_cast<double>(value/norm);
            basis.push_back(std::move(candidate));
        }
        std::vector<PetscInt> coarse_block;
        const auto first=result.coarse.candidates.size();
        for(const auto& column:basis) {
            SparseMode mode;
            FieldCandidate propagated{};
            for(std::size_t component=0;component<field_candidate_count;++component) {
                long double product=0;
                for(std::size_t i=0;i<rows.size();++i)
                    product+=static_cast<long double>(column[i])*fine.candidates[rows[i]][component];
                propagated[component]=static_cast<double>(product);
            }
            for(std::size_t i=0;i<rows.size();++i) if(column[i]!=0) {
                mode.rows.push_back(begin+rows[i]); mode.values.push_back(column[i]);
            }
            coarse_block.push_back(static_cast<PetscInt>(result.coarse.candidates.size()));
            result.coarse.candidates.push_back(propagated);
            modes.push_back(std::move(mode));
        }
        if(!coarse_block.empty()) result.coarse.blocks.push_back(std::move(coarse_block));
        for(std::size_t i=0;i<rows.size();++i)
            for(std::size_t component=0;component<field_candidate_count;++component) {
                long double reconstructed=0;
                for(std::size_t k=0;k<basis.size();++k)
                    reconstructed+=static_cast<long double>(basis[k][i])*result.coarse.candidates[first+k][component];
                const long double expected=fine.candidates[rows[i]][component];
                local_error+=(reconstructed-expected)*(reconstructed-expected);
                local_norm+=expected*expected;
            }
    }
    long double local[2]{local_error,local_norm},sums[2]{};
    if(MPI_Allreduce(local,sums,2,MPI_LONG_DOUBLE,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Field AMG reproduction audit reduction failed");
    result.reproduction_error=static_cast<double>(std::sqrt(sums[0]/std::max(1.L,sums[1])));
    common_check(comm,valid&&std::isfinite(result.reproduction_error)&&result.reproduction_error<=1e-10,
                 "field AMG failed to preserve the physical candidate span");
    const auto local_count=static_cast<PetscInt>(modes.size());
    PetscInt coarse_begin=0;
    int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&local_count,&coarse_begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local_count,&result.global_size,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Field AMG coarse size reduction failed");
    if(rank==0) coarse_begin=0;
    // No transfer is installed if QR could not reduce the global dimension.
    // The caller then solves this level with the bounded coarse KSP.
    if(result.global_size==0||result.global_size>=global) return result;
    std::vector<PetscInt> nonzeros(end-begin,0);
    for(const auto& mode:modes) for(auto row:mode.rows) ++nonzeros[row-begin];
    EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local_count,global,result.global_size,
        0,nonzeros.data(),0,nullptr,result.interpolation.put()));
    EONSIM_PETSC(MatSetOption(result.interpolation.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    for(PetscInt column=0;column<local_count;++column)
        for(std::size_t i=0;i<modes[column].rows.size();++i)
            EONSIM_PETSC(MatSetValue(result.interpolation.get(),modes[column].rows[i],coarse_begin+column,
                                    modes[column].values[i],INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(result.interpolation.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(result.interpolation.get(),MAT_FINAL_ASSEMBLY));
    return result;
}
}

void validate_coupled_velocity_twolevel_options(MPI_Comm comm,const std::string& prefix) {
    const auto base="-"+prefix;
    response_options(comm,prefix);
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","mg"},{"pc_mg_type","multiplicative"},
        {"pc_mg_galerkin","both"},{"pc_mg_adapt_interp_coarse_space","none"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
    PetscInt levels=2; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+"pc_mg_levels").c_str(),&levels,&set));
    common_check(comm,!set||levels==2,"pc_mg_levels must be 2 (the all-identity case collapses to one level)");
    PetscBool adapt=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_adapt_cr").c_str(),&adapt,nullptr));
    common_check(comm,!adapt,"adaptive coarse spaces require an independent implementation");
}

void configure_coupled_velocity_twolevel(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,bool rigid_modes,PetscInt aggregate_nodes) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_twolevel_options(comm,prefix);
    common_choice(comm,aggregate_nodes,aggregate_nodes==0||(aggregate_nodes>=2&&aggregate_nodes<=4096),
                  "aggregate node count must be identical and either zero or in [2,4096]");
    const auto fine=fine_rows(comm,solver,owned_semantics,owned_coordinates,rigid_modes,false);
    const auto modes=aggregate_nodes?aggregate_modes(comm,fine,owned_semantics,owned_coordinates,rigid_modes,aggregate_nodes):
        local_modes(comm,fine,owned_semantics,owned_coordinates,rigid_modes);
    const auto begin=fine.begin,end=fine.end,global=fine.global;
    std::vector<PetscInt> nonzeros(end-begin,0);
    for(const auto& mode:modes) for(auto row:mode.rows) ++nonzeros[row-begin];
    PetscInt local_count=static_cast<PetscInt>(modes.size()),coarse_begin=0,global_count=0;
    int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&local_count,&coarse_begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local_count,&global_count,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Two-level velocity mode count communication failed");
    if(rank==0) coarse_begin=0;

    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    // Apply PCMG once by default. The tolerance-dependent coarse GMRES still
    // makes this action variable, so the outer FSI solve remains FGMRES.
    // Keep the bounded budget for an explicit FGMRES option applied below.
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCMG));
    EONSIM_PETSC(PCMGSetLevels(pc,2,nullptr));
    EONSIM_PETSC(PCMGSetType(pc,PC_MG_MULTIPLICATIVE));
    EONSIM_PETSC(PCMGSetGalerkin(pc,PC_MG_GALERKIN_BOTH));
    EONSIM_PETSC(KSPSetFromOptions(solver));

    if(global_count==0) {
        // All rows are exactly the identity. There is no unconstrained coarse
        // space, and a single Jacobi action is an exact solve, not a failed MG.
        EONSIM_PETSC(PCMGSetLevels(pc,1,nullptr));
        EONSIM_PETSC(PCMGSetGalerkin(pc,PC_MG_GALERKIN_NONE));
        KSP identity_solver=nullptr; EONSIM_PETSC(PCMGGetSmoother(pc,0,&identity_solver));
        PC identity_pc; EONSIM_PETSC(KSPGetPC(identity_solver,&identity_pc));
        EONSIM_PETSC(KSPSetType(identity_solver,KSPPREONLY));
        EONSIM_PETSC(PCSetType(identity_pc,PCJACOBI));
    } else {
        PetscOwner<Mat,MatDestroy> interpolation;
        // Every coarse column is owned by the same rank as its contributing
        // rows. Empty ranks and ranks containing only constraints have no columns.
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local_count,global,global_count,
            0,nonzeros.data(),0,nullptr,interpolation.put()));
        EONSIM_PETSC(MatSetOption(interpolation.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
        PetscInt column=coarse_begin;
        for(const auto& mode:modes) {
            for(std::size_t i=0;i<mode.rows.size();++i)
                EONSIM_PETSC(MatSetValue(interpolation.get(),mode.rows[i],column,mode.values[i],INSERT_VALUES));
            ++column;
        }
        EONSIM_PETSC(MatAssemblyBegin(interpolation.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(interpolation.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(PCMGSetInterpolation(pc,1,interpolation.get()));
        // PETSc owns a reference to P and computes/reuses P^T A P at setup;
        // no root-matrix copy or user numeric-refresh callback is necessary.
        // The Down getter itself creates a distinct Up smoother in PETSc;
        // use the shared getter unless the user requested distinct smoothers.
        KSP down=nullptr; EONSIM_PETSC(PCMGGetSmoother(pc,1,&down));
        smoother_defaults(down);
        PetscBool distinct=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_distinct_smoothup").c_str(),&distinct,nullptr));
        if(distinct) {
            KSP up=nullptr; EONSIM_PETSC(PCMGGetSmootherUp(pc,1,&up));
            if(up!=down) smoother_defaults(up);
        }
        KSP coarse=nullptr; EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
        PC coarse_pc; EONSIM_PETSC(KSPGetPC(coarse,&coarse_pc));
        EONSIM_PETSC(KSPSetType(coarse,KSPGMRES));
        EONSIM_PETSC(KSPSetTolerances(coarse,1e-10,PETSC_DEFAULT,PETSC_DEFAULT,200));
        EONSIM_PETSC(KSPSetNormType(coarse,KSP_NORM_UNPRECONDITIONED));
        EONSIM_PETSC(PCSetType(coarse_pc,PCJACOBI));
        if(aggregate_nodes) {
            // The first transfer preserves the requested mechanical modes;
            // native GAMG coarsens its distributed scalar Galerkin matrix.
            // Use ASM instead of Chebyshev: the coupled operator can be
            // nonsymmetric, and its near modes do not assert positive definiteness.
            EONSIM_PETSC(KSPSetType(coarse,KSPPREONLY));
            EONSIM_PETSC(KSPSetNormType(coarse,KSP_NORM_NONE));
            EONSIM_PETSC(PCSetType(coarse_pc,PCGAMG));
            EONSIM_PETSC(PCGAMGSetReuseInterpolation(coarse_pc,PETSC_TRUE));
            const char* coarse_prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(coarse,&coarse_prefix));
            const std::string coarse_base="-"+std::string(coarse_prefix?coarse_prefix:"");
            for(const auto& option:std::vector<std::pair<std::string,std::string>>{
                {"pc_mg_cycle_type","v"},{"mg_levels_ksp_type","richardson"},
                {"mg_levels_ksp_norm_type","none"},{"mg_levels_ksp_max_it","1"},
                {"mg_levels_pc_type","asm"},{"mg_levels_pc_asm_overlap","1"},
                {"mg_levels_sub_ksp_type","preonly"},{"mg_levels_sub_pc_type","ilu"},
                {"mg_coarse_ksp_type","gmres"},{"mg_coarse_pc_type","jacobi"},
                {"mg_coarse_ksp_rtol","1e-10"},{"mg_coarse_ksp_max_it","200"},
                {"mg_coarse_ksp_norm_type","unpreconditioned"}})
                option_default(coarse_base+option.first,option.second.c_str());
        }
        EONSIM_PETSC(KSPSetFromOptions(coarse));
    }
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) EONSIM_PETSC(PetscPrintf(comm,
        "pc_twolevel prefix=%s global_modes=%" PetscInt_FMT " levels=%d identity=%d rigid_modes=%d aggregate_nodes=%" PetscInt_FMT " coarse_amg=%d\n",
        prefix.empty()?"-":prefix.c_str(),global_count,global_count?2:1,global_count?0:1,static_cast<int>(rigid_modes),
        aggregate_nodes,aggregate_nodes&&global_count?1:0));
}

void validate_coupled_velocity_field_amg_options(MPI_Comm comm,const std::string& prefix) {
    response_options(comm,prefix);
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","mg"},{"pc_mg_type","multiplicative"},
        {"pc_mg_galerkin","both"},{"pc_mg_adapt_interp_coarse_space","none"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
    PetscBool fixed=PETSC_FALSE,adapt=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+"pc_mg_levels").c_str(),&fixed));
    common_check(comm,!fixed,"field AMG determines its own level count at "+prefix);
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_adapt_cr").c_str(),&adapt,nullptr));
    common_check(comm,!adapt,"field AMG uses its fixed physical candidate hierarchy at "+prefix);
    for(const auto& option:std::vector<std::tuple<std::string,PetscInt,PetscInt>>{
        {"field_amg_coarse_limit",64,1000000},{"field_amg_max_levels",10,16}}) {
        PetscInt value=std::get<1>(option),minimum=0,maximum=0;
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+std::get<0>(option)).c_str(),&value,nullptr));
        if(MPI_Allreduce(&value,&minimum,1,MPIU_INT,MPI_MIN,comm)!=MPI_SUCCESS||
           MPI_Allreduce(&value,&maximum,1,MPIU_INT,MPI_MAX,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Field AMG option reduction failed");
        common_check(comm,value>=1&&value<=std::get<2>(option)&&minimum==maximum,
                     "invalid or rank-inconsistent "+prefix+std::get<0>(option));
    }
}

void configure_coupled_velocity_field_amg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,bool rigid_modes,PetscInt aggregate_nodes) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_field_amg_options(comm,prefix);
    common_choice(comm,aggregate_nodes,aggregate_nodes>=2&&aggregate_nodes<=4096,
                  "field AMG aggregate nodes must be identical in [2,4096]");
    const auto fine=fine_rows(comm,solver,owned_semantics,owned_coordinates,rigid_modes,true);
    auto data=field_candidates(comm,fine,owned_semantics,owned_coordinates,rigid_modes);
    PetscInt coarse_limit=64,maximum_levels=10,active=0,local_active=0;
    EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+"field_amg_coarse_limit").c_str(),&coarse_limit,nullptr));
    EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+"field_amg_max_levels").c_str(),&maximum_levels,nullptr));
    for(auto value:fine.active) local_active+=value!=0;
    if(MPI_Allreduce(&local_active,&active,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Field AMG active-row reduction failed");
    std::vector<PetscOwner<Mat,MatDestroy>> transfers;
    PetscOwner<Mat,MatDestroy> temporary_operator;
    std::vector<PetscInt> dimensions{fine.global};
    std::vector<double> reproduction_errors;
    Mat current=fine.matrix;
    while(active&&dimensions.back()>coarse_limit&&static_cast<PetscInt>(dimensions.size())<maximum_levels) {
        auto transfer=field_transfer(comm,current,data,aggregate_nodes);
        if(!transfer.interpolation.get()) break;
        PetscOwner<Mat,MatDestroy> coarse;
        // This initial Galerkin matrix supplies the next graph. PCMG owns all
        // installed transfers and rebuilds numerical operators after J changes;
        // these temporary matrices do not persist as stale runtime operators.
        EONSIM_PETSC(MatPtAP(current,transfer.interpolation.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,coarse.put()));
        temporary_operator=std::move(coarse);
        current=temporary_operator.get();
        dimensions.push_back(transfer.global_size);
        reproduction_errors.push_back(transfer.reproduction_error);
        data=std::move(transfer.coarse);
        transfers.push_back(std::move(transfer.interpolation));
    }
    const auto levels=static_cast<PetscInt>(dimensions.size());
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCMG));
    EONSIM_PETSC(PCMGSetLevels(pc,levels,nullptr));
    EONSIM_PETSC(PCMGSetType(pc,PC_MG_MULTIPLICATIVE));
    EONSIM_PETSC(PCMGSetGalerkin(pc,levels>1?PC_MG_GALERKIN_BOTH:PC_MG_GALERKIN_NONE));
    EONSIM_PETSC(KSPSetFromOptions(solver));
    PetscBool distinct=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_distinct_smoothup").c_str(),&distinct,nullptr));
    for(PetscInt level=1;level<levels;++level) {
        EONSIM_PETSC(PCMGSetInterpolation(pc,level,transfers[levels-1-level].get()));
        KSP down=nullptr; EONSIM_PETSC(PCMGGetSmoother(pc,level,&down));
        smoother_defaults(down);
        if(distinct) {
            KSP up=nullptr; EONSIM_PETSC(PCMGGetSmootherUp(pc,level,&up));
            if(up!=down) smoother_defaults(up);
        }
    }
    KSP coarse=nullptr; PC coarse_pc;
    EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
    EONSIM_PETSC(KSPGetPC(coarse,&coarse_pc));
    if(active==0) {
        EONSIM_PETSC(KSPSetType(coarse,KSPPREONLY));
        EONSIM_PETSC(PCSetType(coarse_pc,PCJACOBI));
    } else {
        EONSIM_PETSC(KSPSetType(coarse,KSPGMRES));
        EONSIM_PETSC(KSPSetTolerances(coarse,1e-10,PETSC_DEFAULT,PETSC_DEFAULT,200));
        EONSIM_PETSC(KSPSetNormType(coarse,KSP_NORM_UNPRECONDITIONED));
        EONSIM_PETSC(PCSetType(coarse_pc,PCASM));
        EONSIM_PETSC(PCASMSetOverlap(coarse_pc,1));
        const char* coarse_prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(coarse,&coarse_prefix));
        const auto coarse_base="-"+std::string(coarse_prefix?coarse_prefix:"");
        option_default(coarse_base+"sub_ksp_type","preonly");
        option_default(coarse_base+"sub_pc_type","lu");
        EONSIM_PETSC(KSPSetFromOptions(coarse));
    }
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) {
        EONSIM_PETSC(PetscPrintf(comm,
            "pc_field_amg prefix=%s global_rows=%" PetscInt_FMT " levels=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
            " identity=%d rigid_modes=%d aggregate_nodes=%" PetscInt_FMT " candidate_columns=%d\n",
            prefix.empty()?"-":prefix.c_str(),fine.global,levels,dimensions.back(),active==0?1:0,
            static_cast<int>(rigid_modes),aggregate_nodes,static_cast<int>(field_candidate_count)));
        for(PetscInt index=0;index<levels-1;++index)
            EONSIM_PETSC(PetscPrintf(comm,
                "pc_field_amg_level prefix=%s fine_level=%" PetscInt_FMT " fine_rows=%" PetscInt_FMT
                " coarse_rows=%" PetscInt_FMT " reproduction_error=%.17g\n",
                prefix.empty()?"-":prefix.c_str(),levels-1-index,dimensions[index],dimensions[index+1],
                reproduction_errors[index]));
    }
}

void validate_coupled_velocity_gamg_options(MPI_Comm comm,const std::string& prefix) {
    response_options(comm,prefix);
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","gamg"},{"pc_gamg_type","agg"},{"pc_mg_type","multiplicative"},
        {"pc_mg_cycle_type","v"},{"pc_mg_galerkin","external"},
        {"pc_mg_adapt_interp_coarse_space","none"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
    PetscBool fixed_levels=PETSC_FALSE,adapt=PETSC_FALSE,reuse=PETSC_TRUE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+"pc_mg_levels").c_str(),&fixed_levels));
    common_check(comm,!fixed_levels,"GAMG determines its levels; use pc_gamg_ options at "+prefix);
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_mg_adapt_cr").c_str(),&adapt,nullptr));
    common_check(comm,!adapt,"adaptive coarse spaces require an independent implementation");
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_gamg_reuse_interpolation").c_str(),&reuse,nullptr));
    common_choice(comm,reuse,true,"GAMG interpolation reuse differs between ranks at "+prefix);
}

void configure_coupled_velocity_gamg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,bool rigid_modes) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_gamg_options(comm,prefix);
    common_check(comm,!rigid_modes,"scalar GAMG cannot use rigid near modes; choose twolevel with rigid modes");
    const auto fine=fine_rows(comm,solver,owned_semantics,owned_coordinates,false,true);
    const auto modes=scalar_mode(comm,fine);
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCGAMG));
    EONSIM_PETSC(PCGAMGSetType(pc,PCGAMGAGG));
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    EONSIM_PETSC(PCMGSetType(pc,PC_MG_MULTIPLICATIVE));
    // GAMG creates levels during setup; PCMGSetCycleType requires them to
    // exist. Its deferred MG-options pass applies this default afterwards.
    option_default(base+"pc_mg_cycle_type","v");
    EONSIM_PETSC(PCGAMGSetReuseInterpolation(pc,PETSC_TRUE));
    // PETSc creates the levels during setup. Prefix defaults reach every new
    // smoother, including rebuilt levels when interpolation reuse is disabled.
    // ASM handles the nonsymmetric coupled matrix without assuming it is SPD.
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"mg_levels_ksp_type","richardson"},{"mg_levels_ksp_norm_type","none"},
        {"mg_levels_ksp_max_it","1"},{"mg_levels_pc_type","asm"},
        {"mg_levels_pc_asm_overlap","1"},{"mg_levels_sub_ksp_type","preonly"},
        {"mg_levels_sub_pc_type","ilu"},{"mg_levels_sub_pc_factor_levels","1"},
        {"mg_levels_sub_pc_factor_mat_ordering_type","rcm"},
        {"mg_coarse_ksp_type","gmres"},{"mg_coarse_pc_type","jacobi"},
        {"mg_coarse_ksp_rtol","1e-10"},{"mg_coarse_ksp_max_it","200"},
        {"mg_coarse_ksp_norm_type","unpreconditioned"}})
        option_default(base+option.first,option.second.c_str());

    if(!modes.empty()) {
        PetscOwner<Vec,VecDestroy> vector;
        EONSIM_PETSC(MatCreateVecs(fine.preconditioner,vector.put(),nullptr));
        EONSIM_PETSC(VecSet(vector.get(),0));
        PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(vector.get(),&values));
        for(std::size_t j=0;j<modes.front().rows.size();++j)
            values[modes.front().rows[j]-fine.begin]=modes.front().values[j];
        EONSIM_PETSC(VecRestoreArray(vector.get(),&values));
        PetscOwner<MatNullSpace,MatNullSpaceDestroy> near_space;
        const Vec near_vector=vector.get();
        EONSIM_PETSC(MatNullSpaceCreate(comm,PETSC_FALSE,1,&near_vector,near_space.put()));
        EONSIM_PETSC(MatSetNearNullSpace(fine.preconditioner,near_space.get()));
        if(fine.matrix!=fine.preconditioner)
            EONSIM_PETSC(MatSetNearNullSpace(fine.matrix,near_space.get()));
        // PETSc retains the vectors through MatNullSpace references. This is a
        // single scalar constant over all active components and the body, not
        // a vector-elasticity nullspace. With blocksize 1, AGG's fixed-column QR
        // can create redundant columns if separate vector modes vanish within
        // a scalar aggregate; global orthogonality would not prevent that.
    } else {
        // A matrix may previously have carried this optional near space before
        // a constraint-triggered solver rebuild. Do not retain obsolete modes.
        EONSIM_PETSC(MatSetNearNullSpace(fine.preconditioner,nullptr));
        if(fine.matrix!=fine.preconditioner) EONSIM_PETSC(MatSetNearNullSpace(fine.matrix,nullptr));
    }
    EONSIM_PETSC(KSPSetFromOptions(solver));
    PetscInt levels=1,coarse_rows=fine.global;
    if(modes.empty()) {
        // Every row is the identity. Avoid AMG setup with an empty near space.
        EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
        EONSIM_PETSC(PCSetType(pc,PCJACOBI));
        EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    } else {
        // This setup establishes the actual hierarchy once; repeated setup on
        // unchanged matrices is a PETSc no-op. Subsequent numeric changes use
        // GAMG's native MatPtAP refresh, never stale coarse numerical matrices.
        EONSIM_PETSC(PCSetUp(pc));
        EONSIM_PETSC(PCMGGetLevels(pc,&levels));
        KSP coarse=nullptr; Mat coarse_matrix=nullptr;
        EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
        EONSIM_PETSC(KSPGetOperators(coarse,&coarse_matrix,nullptr));
        EONSIM_PETSC(MatGetSize(coarse_matrix,&coarse_rows,nullptr));
    }
    PetscBool report=PETSC_FALSE,reuse=PETSC_TRUE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pc_gamg_reuse_interpolation").c_str(),&reuse,nullptr));
    if(report) EONSIM_PETSC(PetscPrintf(comm,
        "pc_coupled_gamg prefix=%s near_modes=%zu levels=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
        " identity=%d reuse_interpolation=%d basis=scalar_constant\n",prefix.empty()?"-":prefix.c_str(),
        modes.size(),levels,coarse_rows,modes.empty()?1:0,static_cast<int>(reuse)));
}
void validate_coupled_velocity_boomeramg_options(MPI_Comm comm,const std::string& prefix) {
    response_options(comm,prefix);
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","hypre"},{"pc_hypre_type","boomeramg"}}) {
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"incompatible "+prefix+option.first);
    }
#if !defined(PETSC_HAVE_HYPRE)
    common_check(comm,false,"BoomerAMG requires a PETSc build with hypre");
#endif
}

void configure_coupled_velocity_boomeramg(MPI_Comm comm,KSP solver,
    const std::vector<DofKey>& owned_semantics) {
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"",base="-"+prefix;
    validate_coupled_velocity_boomeramg_options(comm,prefix);
    const auto fine=fine_rows(comm,solver,owned_semantics,{},false,true);
    int active=std::any_of(fine.active.begin(),fine.active.end(),[](char x){return x!=0;}),any=0;
    MPI_Allreduce(&active,&any,1,MPI_INT,MPI_MAX,comm);
    PC pc; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(solver,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
#if defined(PETSC_HAVE_HYPRE)
    EONSIM_PETSC(PCSetType(pc,PCHYPRE));
    EONSIM_PETSC(PCHYPRESetType(pc,"boomeramg"));
#endif
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    // One fixed V-cycle is a linear response with the built hierarchy. Users
    // can select a different inner budget; the containing solve is flexible.
    option_default(base+"pc_hypre_boomeramg_max_iter","1");
    option_default(base+"pc_hypre_boomeramg_tol","0");
    EONSIM_PETSC(KSPSetFromOptions(solver));
    if(!any) {
        EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
        EONSIM_PETSC(PCSetType(pc,PCJACOBI));
        EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    }
    EONSIM_PETSC(PCSetUp(pc));
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) EONSIM_PETSC(PetscPrintf(comm,
        "pc_coupled_boomeramg prefix=%s identity=%d basis=scalar\n",
        prefix.empty()?"-":prefix.c_str(),any?0:1));
}
} // namespace eonsim
