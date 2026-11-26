#include "eonsim/monolithic_fsi_mg.hpp"
#include "eonsim/fsi_level_smoother.hpp"
#include <petscblaslapack.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <tuple>

namespace eonsim {
namespace {
constexpr const char* shell_name="EONSim all-field monolithic FSI multigrid";
constexpr std::size_t candidate_count=22;
using Candidate=std::array<double,candidate_count>;
void check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Monolithic FSI MG validation communication failed");
    if(any) throw std::runtime_error("Monolithic FSI MG: "+message);
}
void option_default(const std::string& name,const char* value) {
    PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&set));
    if(!set) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
struct Options {
    PetscInt aggregate_nodes=12,aggregate_rows=192,max_levels=8,coarse_limit=96;
    PetscInt energy_steps=1,spectral_modes=2,pre_smooth=1,post_smooth=1,coarse_processes=1;
    PetscInt spectral_refresh_period=0;
    double spectral_tolerance=.1;
    bool single_precision=false,report=false;
    FsiLevelSmootherOptions smoother;
};
Options options(MPI_Comm comm,const std::string& prefix) {
    Options o; const auto base="-"+prefix+"monolithic_mg_";
    for(const auto& entry:std::vector<std::pair<const char*,PetscInt*>>{
        {"aggregate_nodes",&o.aggregate_nodes},{"aggregate_rows",&o.aggregate_rows},
        {"max_levels",&o.max_levels},{"coarse_limit",&o.coarse_limit},
        {"energy_steps",&o.energy_steps},{"spectral_modes",&o.spectral_modes},
        {"pre_smooth",&o.pre_smooth},{"post_smooth",&o.post_smooth},
        {"coarse_processes",&o.coarse_processes},{"patch_overlap",&o.smoother.patches.overlap},
        {"spectral_refresh_period",&o.spectral_refresh_period},
        {"patch_maximum_size",&o.smoother.patches.maximum_size},
        {"polynomial_degree",&o.smoother.polynomial_degree}})
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+entry.first).c_str(),entry.second,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"spectral_tolerance").c_str(),&o.spectral_tolerance,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"eigenvalue_ratio").c_str(),&o.smoother.eigenvalue_ratio,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"patch_damping").c_str(),&o.smoother.patches.damping,nullptr));
    PetscBool single=PETSC_FALSE,report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"single_precision").c_str(),&single,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    o.single_precision=single; o.report=report; o.smoother.patches.single_precision=single;
    char type[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"smoother").c_str(),type,sizeof(type),&set));
    if(set) o.smoother.kind=type;
    const PetscInt values[]={o.aggregate_nodes,o.aggregate_rows,o.max_levels,o.coarse_limit,o.energy_steps,
        o.spectral_modes,o.pre_smooth,o.post_smooth,o.coarse_processes,o.single_precision?1:0,
        o.smoother.patches.overlap,o.smoother.patches.maximum_size,o.smoother.polynomial_degree,
        o.smoother.kind=="vanka"?1:o.smoother.kind=="chebyshev"?2:o.smoother.kind=="block_chebyshev"?3:0,
        o.spectral_refresh_period,o.report?1:0};
    PetscInt minimum[16]{},maximum[16]{};
    MPI_Allreduce(values,minimum,16,MPIU_INT,MPI_MIN,comm);
    MPI_Allreduce(values,maximum,16,MPIU_INT,MPI_MAX,comm);
    bool valid=true; for(int i=0;i<16;++i) valid=valid&&minimum[i]==maximum[i];
    valid=valid&&o.aggregate_nodes>=2&&o.aggregate_nodes<=128&&o.aggregate_rows>=8&&o.aggregate_rows<=512&&
        o.max_levels>=1&&o.max_levels<=20&&o.coarse_limit>=1&&o.energy_steps>=0&&o.energy_steps<=3&&
        o.spectral_modes>=0&&o.spectral_modes<=8&&o.pre_smooth>=0&&o.post_smooth>=0&&
        o.pre_smooth+o.post_smooth>0&&o.pre_smooth<=8&&o.post_smooth<=8&&o.coarse_processes>=1&&values[13]!=0&&
        o.spectral_refresh_period>=0&&o.spectral_refresh_period<=1000000;
    const double real[]={o.spectral_tolerance,o.smoother.eigenvalue_ratio,o.smoother.patches.damping};
    double min_real[3]{},max_real[3]{};
    MPI_Allreduce(real,min_real,3,MPI_DOUBLE,MPI_MIN,comm);
    MPI_Allreduce(real,max_real,3,MPI_DOUBLE,MPI_MAX,comm);
    for(int i=0;i<3;++i) valid=valid&&std::isfinite(real[i])&&min_real[i]==max_real[i];
    valid=valid&&o.spectral_tolerance>=0&&o.spectral_tolerance<=1&&
        o.smoother.eigenvalue_ratio>0&&o.smoother.eigenvalue_ratio<1;
    check(comm,valid,"inconsistent or out-of-range hierarchy options");
    return o;
}
struct LevelData {
    std::vector<Candidate> candidates;
    std::vector<std::vector<PetscInt>> blocks;
    std::vector<DofKey> semantics;
    std::vector<unsigned char> trace,active;
};
struct Transfer {
    PetscOwner<Mat,MatDestroy> matrix;
    LevelData coarse;
    std::vector<unsigned char> anchors;
    MonolithicFsiMgLevelStats stats;
};
long double dot(const std::vector<double>& x,const std::vector<double>& y) {
    long double result=0;
    for(std::size_t i=0;i<x.size();++i) result+=static_cast<long double>(x[i])*y[i];
    return result;
}
bool append_basis(std::vector<double> candidate,std::vector<std::vector<double>>& basis) {
    const auto initial=std::sqrt(dot(candidate,candidate));
    if(initial==0) return false;
    for(int pass=0;pass<2;++pass) for(const auto& q:basis) {
        const auto product=dot(q,candidate);
        for(std::size_t i=0;i<candidate.size();++i) candidate[i]-=static_cast<double>(product*q[i]);
    }
    const auto length=std::sqrt(dot(candidate,candidate));
    if(!std::isfinite(length)||!std::isfinite(initial)) throw std::runtime_error("Nonfinite monolithic near-mode QR");
    if(length<=256*std::numeric_limits<double>::epsilon()*std::max(1.L,initial)) return false;
    for(auto& value:candidate) value=static_cast<double>(value/length);
    basis.push_back(std::move(candidate)); return true;
}
LevelData fine_data(MPI_Comm comm,Mat matrix,const std::vector<DofKey>& semantics,
    const std::vector<std::array<double,3>>& coordinates,const std::vector<unsigned char>& trace) {
    PetscInt begin=0,end=0,n=0,m=0,cbegin=0,cend=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(matrix,&cbegin,&cend));
    EONSIM_PETSC(MatGetSize(matrix,&n,&m));
    check(comm,n==m&&begin==cbegin&&end==cend&&end-begin==static_cast<PetscInt>(semantics.size())&&
        trace.size()==semantics.size()&&(coordinates.empty()||coordinates.size()==semantics.size()),
        "matrix ownership/shape and full field metadata do not agree");
    LevelData result; result.semantics=semantics; result.trace=trace;
    result.candidates.resize(semantics.size()); result.active.resize(semantics.size());
    double local_sum[4]{},global_sum[4]{};
    bool valid=true;
    if(!coordinates.empty()) for(std::size_t row=0;row<semantics.size();++row)
        if(semantics[row].kind==DofEntity::vertex) {
            for(int c=0;c<3;++c) { valid=valid&&std::isfinite(coordinates[row][c]); local_sum[c]+=coordinates[row][c]; }
            local_sum[3]+=1;
        }
    MPI_Allreduce(local_sum,global_sum,4,MPI_DOUBLE,MPI_SUM,comm);
    std::array<double,3> center{};
    if(global_sum[3]>0) for(int c=0;c<3;++c) center[c]=global_sum[c]/global_sum[3];
    double local_scale=0,scale=1;
    if(!coordinates.empty()) for(std::size_t row=0;row<semantics.size();++row)
        if(semantics[row].kind==DofEntity::vertex)
            for(int c=0;c<3;++c) local_scale=std::max(local_scale,std::abs(coordinates[row][c]-center[c]));
    MPI_Allreduce(&local_scale,&scale,1,MPI_DOUBLE,MPI_MAX,comm);
    if(scale==0) scale=1;
    using Node=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
    std::map<Node,PetscInt> blocks;
    for(PetscInt local=0;local<end-begin;++local) {
        const auto row=begin+local; const auto& key=semantics[local];
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
        bool identity=true,diagonal=false;
        for(PetscInt j=0;j<count;++j) {
            valid=valid&&std::isfinite(values[j]);
            if(columns[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
            else identity=identity&&values[j]==0.;
        }
        EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
        result.active[local]=!(identity&&diagonal);
        if(!result.active[local]) continue;
        valid=valid&&(key.component<3||key.quantity==DofQuantity::scalar_value);
        auto& modes=result.candidates[local];
        int vector_offset=-1,rotation_offset=-1;
        if(key.kind==DofEntity::body) modes[10]=1;
        else if(key.kind==DofEntity::boundary) modes[11]=1;
        else if(key.quantity==DofQuantity::pressure) modes[9]=1;
        else if(key.quantity==DofQuantity::velocity&&key.domain==DofDomain::fluid) { vector_offset=0; rotation_offset=13; }
        else if(key.quantity==DofQuantity::velocity&&key.domain==DofDomain::solid) { vector_offset=3; rotation_offset=16; }
        else if(key.domain==DofDomain::mesh&&key.quantity==DofQuantity::displacement) { vector_offset=6; rotation_offset=19; }
        else if(key.quantity==DofQuantity::scalar_value) modes[12]=1;
        else valid=false;
        if(vector_offset>=0&&key.component<3) {
            modes[vector_offset+key.component]=1;
            if(!coordinates.empty()&&key.kind==DofEntity::vertex&&key.mode==0&&key.space==1) {
                std::array<double,3> x{};
                for(int c=0;c<3;++c) x[c]=(coordinates[local][c]-center[c])/scale;
                const double rotations[3][3]={{0,-x[2],x[1]},{x[2],0,-x[0]},{-x[1],x[0],0}};
                for(int axis=0;axis<3;++axis) modes[rotation_offset+axis]=rotations[axis][key.component];
            }
        }
        const Node node{key.entity,key.kind,key.mode,key.space};
        auto found=blocks.find(node);
        if(found==blocks.end()) {
            const auto id=static_cast<PetscInt>(result.blocks.size());
            found=blocks.emplace(node,id).first; result.blocks.push_back({});
        }
        result.blocks[found->second].push_back(local);
    }
    check(comm,valid,"nonfinite matrix/coordinates or unsupported field semantics");
    return result;
}

// Aggregate-local spectral enrichment uses the complete mixed principal block
// (including pressure and off-diagonal physical couplings), row-scaled before
// forming its positive normal energy. It is a local low-energy proxy, not a
// global eigenvalue computation or a claimed inf-sup certificate.
PetscInt spectral_enrichment(Mat matrix,PetscInt begin,const std::vector<PetscInt>& rows,
    PetscInt maximum,double threshold,std::vector<std::vector<double>>& basis) {
    const auto n=static_cast<PetscInt>(rows.size());
    if(maximum==0||n<2||basis.size()>=rows.size()) return 0;
    std::map<PetscInt,PetscInt> positions;
    for(PetscInt i=0;i<n;++i) positions.emplace(begin+rows[i],i);
    std::vector<double> block(static_cast<std::size_t>(n)*n,0.);
    for(PetscInt i=0;i<n;++i) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,begin+rows[i],&count,&columns,&values));
        double scale=0; for(PetscInt j=0;j<count;++j) scale=std::max(scale,std::abs(values[j]));
        if(scale>0) for(PetscInt j=0;j<count;++j) {
            auto found=positions.find(columns[j]);
            if(found!=positions.end()) block[i*n+found->second]=values[j]/scale;
        }
        EONSIM_PETSC(MatRestoreRow(matrix,begin+rows[i],&count,&columns,&values));
    }
    std::vector<double> normal(static_cast<std::size_t>(n)*n,0.);
    for(PetscInt i=0;i<n;++i) for(PetscInt j=i;j<n;++j) {
        long double product=0;
        for(PetscInt k=0;k<n;++k) product+=static_cast<long double>(block[k*n+i])*block[k*n+j];
        normal[i+j*n]=normal[j+i*n]=static_cast<double>(product);
    }
    PetscBLASInt size=0,info=0,lwork=0;
    EONSIM_PETSC(PetscBLASIntCast(n,&size));
    EONSIM_PETSC(PetscBLASIntCast(std::max<PetscInt>(1,3*n-1),&lwork));
    std::vector<double> values(n),work(lwork);
    LAPACKsyev_("V","U",&size,normal.data(),&size,values.data(),work.data(),&lwork,&info);
    if(info!=0) throw std::runtime_error("Monolithic spectral local eigensolve failed");
    PetscInt added=0;
    const auto cutoff=threshold*std::max(0.,values.back());
    for(PetscInt j=0;j<n&&added<maximum&&basis.size()+1<rows.size();++j) {
        if(!std::isfinite(values[j])) throw std::runtime_error("Nonfinite monolithic local eigenvalue");
        if(values[j]>cutoff) break;
        std::vector<double> candidate(n);
        for(PetscInt i=0;i<n;++i) candidate[i]=normal[i+j*n];
        if(append_basis(std::move(candidate),basis)) ++added;
    }
    return added;
}

struct Column { std::vector<PetscInt> rows; std::vector<double> values; };
Transfer tentative_transfer(MPI_Comm comm,Mat matrix,const LevelData& fine,const Options& o) {
    PetscInt begin=0,end=0,global=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&global,nullptr));
    std::vector<PetscInt> row_block(end-begin,-1);
    for(PetscInt block=0;block<static_cast<PetscInt>(fine.blocks.size());++block)
        for(auto row:fine.blocks[block]) row_block[row]=block;
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
    Transfer result; result.stats.rows=global; result.anchors.resize(end-begin,0);
    std::vector<unsigned char> assigned(fine.blocks.size(),0);
    std::vector<Column> columns;
    std::vector<std::pair<PetscInt,PetscInt>> coarse_blocks;
    long double local_error=0,local_norm=0;
    PetscInt spectral=0; bool valid=true; std::string local_error_message;
    try {
        for(PetscInt seed=0;seed<static_cast<PetscInt>(fine.blocks.size());++seed) if(!assigned[seed]) {
            std::vector<PetscInt> aggregate{seed}; assigned[seed]=1;
            std::size_t row_count=fine.blocks[seed].size();
            const bool protected_scalar=fine.semantics[fine.blocks[seed].front()].kind!=DofEntity::vertex;
            for(std::size_t cursor=0;!protected_scalar&&cursor<aggregate.size()&&
                aggregate.size()<static_cast<std::size_t>(o.aggregate_nodes);++cursor)
                for(auto adjacent:neighbors[aggregate[cursor]]) if(!assigned[adjacent]&&
                    fine.semantics[fine.blocks[adjacent].front()].kind==DofEntity::vertex&&
                    row_count+fine.blocks[adjacent].size()<=static_cast<std::size_t>(o.aggregate_rows)) {
                    assigned[adjacent]=1; aggregate.push_back(adjacent); row_count+=fine.blocks[adjacent].size();
                    if(aggregate.size()==static_cast<std::size_t>(o.aggregate_nodes)) break;
                }
            if(row_count>static_cast<std::size_t>(o.aggregate_rows))
                throw std::runtime_error("one semantic block exceeds monolithic_mg_aggregate_rows");
            std::vector<PetscInt> rows;
            for(auto block:aggregate) rows.insert(rows.end(),fine.blocks[block].begin(),fine.blocks[block].end());
            std::sort(rows.begin(),rows.end());
            std::vector<std::vector<double>> basis;
            for(std::size_t component=0;component<candidate_count;++component) {
                std::vector<double> candidate(rows.size());
                for(std::size_t i=0;i<rows.size();++i) candidate[i]=fine.candidates[rows[i]][component];
                append_basis(std::move(candidate),basis);
            }
            spectral+=spectral_enrichment(matrix,begin,rows,o.spectral_modes,o.spectral_tolerance,basis);
            // Fixed, rank-revealing anchor rows protect every coarse column,
            // including spectral columns orthogonal to physical candidates.
            // Without these anchors, unconstrained energy descent could shrink
            // such an enrichment column to zero and make P^T J P singular.
            std::vector<std::vector<double>> anchor_basis;
            std::vector<unsigned char> anchored(rows.size(),0);
            for(std::size_t k=0;k<basis.size();++k) {
                std::size_t pivot=rows.size(); long double largest=-1;
                std::vector<double> pivot_candidate;
                for(std::size_t i=0;i<rows.size();++i) if(!anchored[i]) {
                    std::vector<double> candidate(basis.size());
                    for(std::size_t j=0;j<basis.size();++j) candidate[j]=basis[j][i];
                    for(int pass=0;pass<2;++pass) for(const auto& q:anchor_basis) {
                        const auto product=dot(q,candidate);
                        for(std::size_t j=0;j<candidate.size();++j) candidate[j]-=static_cast<double>(product*q[j]);
                    }
                    const auto squared=dot(candidate,candidate);
                    if(squared>largest) { largest=squared; pivot=i; pivot_candidate=std::move(candidate); }
                }
                if(pivot==rows.size()||!append_basis(std::move(pivot_candidate),anchor_basis))
                    throw std::runtime_error("Unable to anchor an independent monolithic coarse column");
                anchored[pivot]=1; result.anchors[rows[pivot]]=1;
            }
            const auto first=static_cast<PetscInt>(columns.size());
            bool trace=false; for(auto row:rows) trace=trace||fine.trace[row];
            for(const auto& basis_column:basis) {
                Candidate propagated{}; Column column;
                for(std::size_t component=0;component<candidate_count;++component) {
                    long double value=0;
                    for(std::size_t i=0;i<rows.size();++i)
                        value+=static_cast<long double>(basis_column[i])*fine.candidates[rows[i]][component];
                    propagated[component]=static_cast<double>(value);
                }
                for(std::size_t i=0;i<rows.size();++i) if(basis_column[i]!=0.) {
                    column.rows.push_back(rows[i]); column.values.push_back(basis_column[i]);
                }
                columns.push_back(std::move(column)); result.coarse.candidates.push_back(propagated);
                result.coarse.trace.push_back(trace); result.coarse.active.push_back(1);
            }
            const auto last=static_cast<PetscInt>(columns.size());
            if(last>first) coarse_blocks.emplace_back(first,last);
            for(std::size_t i=0;i<rows.size();++i) for(std::size_t component=0;component<candidate_count;++component) {
                long double reconstructed=0;
                for(std::size_t k=0;k<basis.size();++k)
                    reconstructed+=static_cast<long double>(basis[k][i])*result.coarse.candidates[first+k][component];
                const long double expected=fine.candidates[rows[i]][component];
                local_error+=(reconstructed-expected)*(reconstructed-expected); local_norm+=expected*expected;
            }
        }
    } catch(const std::exception& e) { valid=false; local_error_message=e.what(); }
    check(comm,valid,"aggregate basis construction failed"+(local_error_message.empty()?std::string{}:": "+local_error_message));
    const auto local=static_cast<PetscInt>(columns.size());
    PetscInt coarse_begin=0;
    int rank=0; MPI_Comm_rank(comm,&rank);
    MPI_Exscan(&local,&coarse_begin,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&local,&result.stats.coarse_rows,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&spectral,&result.stats.spectral_modes,1,MPIU_INT,MPI_SUM,comm);
    if(rank==0) coarse_begin=0;
    long double audit[2]{local_error,local_norm},sum[2]{};
    MPI_Allreduce(audit,sum,2,MPI_LONG_DOUBLE,MPI_SUM,comm);
    result.stats.reproduction_error=static_cast<double>(std::sqrt(sum[0]/std::max(1.L,sum[1])));
    check(comm,std::isfinite(result.stats.reproduction_error)&&result.stats.reproduction_error<=1e-10,
        "tentative transfer lost physical candidate modes");
    if(result.stats.coarse_rows==0||result.stats.coarse_rows>=global) return result;
    std::vector<PetscInt> nonzeros(end-begin,0);
    for(const auto& column:columns) for(auto row:column.rows) ++nonzeros[row];
    EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local,global,result.stats.coarse_rows,
        0,nonzeros.data(),0,nullptr,result.matrix.put()));
    EONSIM_PETSC(MatSetOption(result.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
    for(PetscInt column=0;column<local;++column)
        for(std::size_t i=0;i<columns[column].rows.size();++i)
            EONSIM_PETSC(MatSetValue(result.matrix.get(),begin+columns[column].rows[i],coarse_begin+column,
                columns[column].values[i],INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(result.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(result.matrix.get(),MAT_FINAL_ASSEMBLY));
    result.coarse.semantics.resize(local);
    for(const auto& block:coarse_blocks) {
        std::vector<PetscInt> indices;
        for(PetscInt i=block.first;i<block.second;++i) {
            DofKey key; key.entity=coarse_begin+block.first; key.domain=DofDomain::scalar;
            key.quantity=DofQuantity::scalar_value; key.kind=DofEntity::vertex;
            key.component=static_cast<std::uint16_t>(i-block.first); key.space=0;
            result.coarse.semantics[i]=key; indices.push_back(i);
        }
        result.coarse.blocks.push_back(std::move(indices));
    }
    return result;
}

// Gather only candidate rows touched by this rank's transfer stencil. This is
// setup-only halo data, not a replicated global coarse field or matrix.
std::vector<Candidate> gather_candidates(Mat transfer,const LevelData& coarse,
    const std::vector<PetscInt>& columns) {
    PetscOwner<Vec,VecDestroy> global,local;
    EONSIM_PETSC(MatCreateVecs(transfer,global.put(),nullptr));
    EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),local.put()));
    PetscOwner<IS,ISDestroy> source;
    EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),columns.data(),PETSC_COPY_VALUES,source.put()));
    PetscOwner<VecScatter,VecScatterDestroy> scatter;
    EONSIM_PETSC(VecScatterCreate(global.get(),source.get(),local.get(),nullptr,scatter.put()));
    std::vector<Candidate> values(columns.size());
    for(std::size_t component=0;component<candidate_count;++component) {
        PetscScalar* owned=nullptr;
        EONSIM_PETSC(VecGetArray(global.get(),&owned));
        for(std::size_t i=0;i<coarse.candidates.size();++i) owned[i]=coarse.candidates[i][component];
        EONSIM_PETSC(VecRestoreArray(global.get(),&owned));
        EONSIM_PETSC(VecScatterBegin(scatter.get(),global.get(),local.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),global.get(),local.get(),INSERT_VALUES,SCATTER_FORWARD));
        const PetscScalar* gathered=nullptr; EONSIM_PETSC(VecGetArrayRead(local.get(),&gathered));
        for(std::size_t i=0;i<columns.size();++i) values[i][component]=gathered[i];
        EONSIM_PETSC(VecRestoreArrayRead(local.get(),&gathered));
    }
    return values;
}
double frobenius_product(MPI_Comm comm,Mat a,Mat b) {
    PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(a,&begin,&end));
    long double local=0,global=0;
    for(PetscInt row=begin;row<end;++row) {
        PetscInt na=0,nb=0; const PetscInt *ca=nullptr,*cb=nullptr; const PetscScalar *va=nullptr,*vb=nullptr;
        EONSIM_PETSC(MatGetRow(a,row,&na,&ca,&va)); EONSIM_PETSC(MatGetRow(b,row,&nb,&cb,&vb));
        PetscInt i=0,j=0;
        while(i<na&&j<nb) {
            if(ca[i]==cb[j]) { local+=static_cast<long double>(va[i])*vb[j]; ++i; ++j; }
            else if(ca[i]<cb[j]) ++i; else ++j;
        }
        EONSIM_PETSC(MatRestoreRow(b,row,&nb,&cb,&vb)); EONSIM_PETSC(MatRestoreRow(a,row,&na,&ca,&va));
    }
    MPI_Allreduce(&local,&global,1,MPI_LONG_DOUBLE,MPI_SUM,comm); return static_cast<double>(global);
}
PetscOwner<Mat,MatDestroy> row_scaled_operator(MPI_Comm comm,Mat matrix) {
    PetscOwner<Mat,MatDestroy> scaled;
    EONSIM_PETSC(MatDuplicate(matrix,MAT_COPY_VALUES,scaled.put()));
    PetscOwner<Vec,VecDestroy> inverse;
    EONSIM_PETSC(MatCreateVecs(matrix,nullptr,inverse.put()));
    PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    PetscScalar* entries=nullptr; EONSIM_PETSC(VecGetArray(inverse.get(),&entries));
    bool valid=true;
    for(PetscInt row=begin;row<end;++row) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
        double largest=0; for(PetscInt j=0;j<count;++j) largest=std::max(largest,std::abs(values[j]));
        entries[row-begin]=largest>0?1./largest:1.;
        valid=valid&&std::isfinite(entries[row-begin]);
        EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
    }
    EONSIM_PETSC(VecRestoreArray(inverse.get(),&entries));
    check(comm,valid,"row scaling is outside representable precision");
    EONSIM_PETSC(MatDiagonalScale(scaled.get(),inverse.get(),nullptr)); return scaled;
}

void minimize_transfer_energy(MPI_Comm comm,Mat matrix,const LevelData& fine,Transfer& transfer,PetscInt steps) {
    auto scaled=row_scaled_operator(comm,matrix);
    PetscOwner<Mat,MatDestroy> action;
    EONSIM_PETSC(MatMatMult(scaled.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,action.put()));
    PetscReal norm=0; EONSIM_PETSC(MatNorm(action.get(),NORM_FROBENIUS,&norm));
    transfer.stats.energy_before=norm*norm; transfer.stats.energy_after=norm*norm;
    PetscInt begin=0,end=0,global=0,coarse_global=0,coarse_local=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(transfer.matrix.get(),&global,&coarse_global));
    EONSIM_PETSC(MatGetLocalSize(transfer.matrix.get(),nullptr,&coarse_local));
    for(PetscInt iteration=0;iteration<steps;++iteration) {
        PetscOwner<Mat,MatDestroy> gradient;
        EONSIM_PETSC(MatTransposeMatMult(scaled.get(),action.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,gradient.put()));
        std::vector<std::map<PetscInt,double>> rows(end-begin);
        std::set<PetscInt> union_columns;
        for(PetscInt row=begin;row<end;++row) if(fine.active[row-begin]&&!transfer.anchors[row-begin]) {
            PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(gradient.get(),row,&count,&columns,&values));
            for(PetscInt j=0;j<count;++j) rows[row-begin][columns[j]]=-values[j];
            EONSIM_PETSC(MatRestoreRow(gradient.get(),row,&count,&columns,&values));
            EONSIM_PETSC(MatGetRow(transfer.matrix.get(),row,&count,&columns,&values));
            for(PetscInt j=0;j<count;++j) rows[row-begin].emplace(columns[j],0.);
            EONSIM_PETSC(MatRestoreRow(transfer.matrix.get(),row,&count,&columns,&values));
            for(const auto& entry:rows[row-begin]) union_columns.insert(entry.first);
        }
        const std::vector<PetscInt> columns(union_columns.begin(),union_columns.end());
        const auto halo=gather_candidates(transfer.matrix.get(),transfer.coarse,columns);
        std::map<PetscInt,std::size_t> positions;
        for(std::size_t i=0;i<columns.size();++i) positions.emplace(columns[i],i);
        bool valid=true;
        for(auto& row:rows) {
            std::vector<std::vector<double>> constraints;
            for(std::size_t component=0;component<candidate_count;++component) {
                std::vector<double> column; column.reserve(row.size());
                for(const auto& entry:row) column.push_back(halo[positions.at(entry.first)][component]);
                try { append_basis(std::move(column),constraints); } catch(...) { valid=false; }
            }
            std::vector<double> direction; direction.reserve(row.size());
            for(const auto& entry:row) direction.push_back(entry.second);
            // Orthogonal projection makes each row satisfy dP*N_coarse=0.
            for(int pass=0;pass<2;++pass) for(const auto& q:constraints) {
                const auto product=dot(q,direction);
                for(std::size_t j=0;j<direction.size();++j) direction[j]-=static_cast<double>(product*q[j]);
            }
            std::size_t j=0; for(auto& entry:row) { entry.second=direction[j++]; valid=valid&&std::isfinite(entry.second); }
        }
        check(comm,valid,"nonfinite constrained energy descent");
        PetscOwner<Mat,MatDestroy> direction;
        PetscInt coarse_begin=0,coarse_end=0;
        EONSIM_PETSC(MatGetOwnershipRangeColumn(transfer.matrix.get(),&coarse_begin,&coarse_end));
        std::vector<PetscInt> diagonal(rows.size(),0),offdiagonal(rows.size(),0);
        for(std::size_t row=0;row<rows.size();++row) for(const auto& entry:rows[row])
            ++(entry.first>=coarse_begin&&entry.first<coarse_end?diagonal[row]:offdiagonal[row]);
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,coarse_local,global,coarse_global,
            0,diagonal.data(),0,offdiagonal.data(),direction.put()));
        for(PetscInt row=0;row<end-begin;++row) for(const auto& entry:rows[row])
            EONSIM_PETSC(MatSetValue(direction.get(),begin+row,entry.first,entry.second,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(direction.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(direction.get(),MAT_FINAL_ASSEMBLY));
        PetscOwner<Mat,MatDestroy> direction_action;
        EONSIM_PETSC(MatMatMult(scaled.get(),direction.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,direction_action.put()));
        const auto derivative=frobenius_product(comm,action.get(),direction_action.get());
        EONSIM_PETSC(MatNorm(direction_action.get(),NORM_FROBENIUS,&norm));
        const auto curvature=norm*norm;
        check(comm,std::isfinite(derivative)&&std::isfinite(curvature),"nonfinite prolongation energy");
        if(derivative>=0||curvature<=std::numeric_limits<double>::min()) break;
        const double alpha=-derivative/curvature;
        check(comm,std::isfinite(alpha)&&alpha>0,"invalid constrained energy step");
        EONSIM_PETSC(MatSetOption(transfer.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
        EONSIM_PETSC(MatAXPY(transfer.matrix.get(),alpha,direction.get(),DIFFERENT_NONZERO_PATTERN));
        EONSIM_PETSC(MatSetOption(transfer.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
        action=PetscOwner<Mat,MatDestroy>{};
        EONSIM_PETSC(MatMatMult(scaled.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,action.put()));
        EONSIM_PETSC(MatNorm(action.get(),NORM_FROBENIUS,&norm));
        transfer.stats.energy_after=norm*norm;
        check(comm,transfer.stats.energy_after<=transfer.stats.energy_before*(1.+1e-11),
            "energy-minimizing prolongation increased its positive normal energy");
    }
    PetscOwner<Vec,VecDestroy> coarse,fine_value,expected;
    EONSIM_PETSC(MatCreateVecs(transfer.matrix.get(),coarse.put(),fine_value.put()));
    EONSIM_PETSC(VecDuplicate(fine_value.get(),expected.put()));
    long double error=0,reference=0;
    for(std::size_t component=0;component<candidate_count;++component) {
        PetscScalar* data=nullptr; EONSIM_PETSC(VecGetArray(coarse.get(),&data));
        for(std::size_t i=0;i<transfer.coarse.candidates.size();++i) data[i]=transfer.coarse.candidates[i][component];
        EONSIM_PETSC(VecRestoreArray(coarse.get(),&data));
        EONSIM_PETSC(MatMult(transfer.matrix.get(),coarse.get(),fine_value.get()));
        const PetscScalar* actual=nullptr; EONSIM_PETSC(VecGetArrayRead(fine_value.get(),&actual));
        for(std::size_t i=0;i<fine.candidates.size();++i) {
            const long double target=fine.candidates[i][component],difference=actual[i]-target;
            error+=difference*difference; reference+=target*target;
        }
        EONSIM_PETSC(VecRestoreArrayRead(fine_value.get(),&actual));
    }
    long double local[2]{error,reference},sum[2]{};
    MPI_Allreduce(local,sum,2,MPI_LONG_DOUBLE,MPI_SUM,comm);
    transfer.stats.reproduction_error=static_cast<double>(std::sqrt(sum[0]/std::max(1.L,sum[1])));
    check(comm,std::isfinite(transfer.stats.reproduction_error)&&transfer.stats.reproduction_error<=1e-9,
        "energy smoothing lost the physical candidate span");
    // A coarse unknown is a trace unknown when ANY nonzero transfer entry
    // touches the true fine trace. Absolute values prevent cancellation.
    EONSIM_PETSC(VecSet(coarse.get(),0));
    for(PetscInt row=begin;row<end;++row) if(fine.trace[row-begin]) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(transfer.matrix.get(),row,&count,&columns,&values));
        for(PetscInt j=0;j<count;++j) if(values[j]!=0.)
            EONSIM_PETSC(VecSetValue(coarse.get(),columns[j],std::abs(values[j]),ADD_VALUES));
        EONSIM_PETSC(MatRestoreRow(transfer.matrix.get(),row,&count,&columns,&values));
    }
    EONSIM_PETSC(VecAssemblyBegin(coarse.get())); EONSIM_PETSC(VecAssemblyEnd(coarse.get()));
    const PetscScalar* traces=nullptr; EONSIM_PETSC(VecGetArrayRead(coarse.get(),&traces));
    for(std::size_t i=0;i<transfer.coarse.trace.size();++i) transfer.coarse.trace[i]=traces[i]>0.;
    EONSIM_PETSC(VecRestoreArrayRead(coarse.get(),&traces));
}

// Float coefficients are normalized per row; gathered vectors are normalized
// per local apply before conversion. This protects the float arithmetic from
// dimensional FSI scaling without changing the outer FP64 operator. Only the
// actual sparse column halo is communicated, including on empty owners.
struct FloatSparse {
    MPI_Comm comm=PETSC_COMM_SELF;
    PetscInt begin=0,end=0,global_rows=0,global_columns=0;
    std::vector<PetscInt> offsets,columns,slots;
    std::vector<float> values,input_values,output_values;
    std::vector<double> scales;
    PetscOwner<Vec,VecDestroy> gathered;
    PetscOwner<VecScatter,VecScatterDestroy> scatter;
    bool prepared=false;
    void update(Mat matrix) {
        comm=PetscObjectComm(reinterpret_cast<PetscObject>(matrix));
        PetscInt new_begin=0,new_end=0,new_rows=0,new_columns=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&new_begin,&new_end));
        EONSIM_PETSC(MatGetSize(matrix,&new_rows,&new_columns));
        std::vector<PetscInt> new_offsets(1,0),all_columns;
        std::vector<float> new_values; std::vector<double> new_scales;
        bool valid=true;
        for(PetscInt row=new_begin;row<new_end;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            double scale=0;
            for(PetscInt j=0;j<count;++j) { scale=std::max(scale,std::abs(entries[j])); valid=valid&&std::isfinite(entries[j]); }
            if(scale==0) scale=1.;
            new_scales.push_back(scale);
            for(PetscInt j=0;j<count;++j) {
                all_columns.push_back(indices[j]); new_values.push_back(static_cast<float>(entries[j]/scale));
                valid=valid&&std::isfinite(new_values.back());
            }
            new_offsets.push_back(static_cast<PetscInt>(all_columns.size()));
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        std::vector<PetscInt> unique_columns=all_columns;
        std::sort(unique_columns.begin(),unique_columns.end());
        unique_columns.erase(std::unique(unique_columns.begin(),unique_columns.end()),unique_columns.end());
        std::vector<PetscInt> new_slots; new_slots.reserve(all_columns.size());
        for(auto column:all_columns) new_slots.push_back(static_cast<PetscInt>(
            std::lower_bound(unique_columns.begin(),unique_columns.end(),column)-unique_columns.begin()));
        if(prepared) valid=valid&&begin==new_begin&&end==new_end&&global_rows==new_rows&&
            global_columns==new_columns&&offsets==new_offsets&&columns==unique_columns&&slots==new_slots;
        check(comm,valid,"float sparse refresh changed the graph/ownership or received nonfinite entries");
        if(!prepared) {
            begin=new_begin; end=new_end; global_rows=new_rows; global_columns=new_columns;
            offsets=std::move(new_offsets); columns=std::move(unique_columns); slots=std::move(new_slots);
            PetscOwner<Vec,VecDestroy> input;
            EONSIM_PETSC(MatCreateVecs(matrix,input.put(),nullptr));
            EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),gathered.put()));
            PetscOwner<IS,ISDestroy> source;
            EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),
                columns.data(),PETSC_COPY_VALUES,source.put()));
            EONSIM_PETSC(VecScatterCreate(input.get(),source.get(),gathered.get(),nullptr,scatter.put()));
            input_values.resize(columns.size()); output_values.resize(columns.size()); prepared=true;
        }
        scales=std::move(new_scales); values=std::move(new_values);
    }
    PetscErrorCode multiply(Vec input,Vec output,bool transpose) {
        PetscFunctionBeginUser;
        if(!transpose) {
            PetscCall(VecScatterBegin(scatter.get(),input,gathered.get(),INSERT_VALUES,SCATTER_FORWARD));
            PetscCall(VecScatterEnd(scatter.get(),input,gathered.get(),INSERT_VALUES,SCATTER_FORWARD));
            const PetscScalar* x=nullptr; PetscScalar* y=nullptr;
            PetscCall(VecGetArrayRead(gathered.get(),&x));
            double scale=0; for(std::size_t i=0;i<columns.size();++i) scale=std::max(scale,std::abs(x[i]));
            if(scale==0) scale=1;
            for(std::size_t i=0;i<columns.size();++i) input_values[i]=static_cast<float>(x[i]/scale);
            PetscCall(VecRestoreArrayRead(gathered.get(),&x));
            PetscCall(VecGetArray(output,&y));
            for(PetscInt row=0;row<end-begin;++row) {
                float value=0;
                for(PetscInt j=offsets[row];j<offsets[row+1];++j) value+=values[j]*input_values[slots[j]];
                y[row]=static_cast<double>(value)*scale*scales[row];
            }
            PetscCall(VecRestoreArray(output,&y));
        } else {
            const PetscScalar* x=nullptr; PetscScalar* y=nullptr;
            PetscCall(VecGetArrayRead(input,&x));
            double scale=0;
            for(PetscInt row=0;row<end-begin;++row) scale=std::max(scale,std::abs(x[row]*scales[row]));
            if(scale==0) scale=1;
            std::fill(output_values.begin(),output_values.end(),0.f);
            for(PetscInt row=0;row<end-begin;++row) {
                const auto value=static_cast<float>((x[row]*scales[row])/scale);
                for(PetscInt j=offsets[row];j<offsets[row+1];++j) output_values[slots[j]]+=values[j]*value;
            }
            PetscCall(VecRestoreArrayRead(input,&x));
            PetscCall(VecGetArray(gathered.get(),&y));
            for(std::size_t i=0;i<columns.size();++i) y[i]=static_cast<double>(output_values[i])*scale;
            PetscCall(VecRestoreArray(gathered.get(),&y));
            PetscCall(VecSet(output,0));
            PetscCall(VecScatterBegin(scatter.get(),gathered.get(),output,ADD_VALUES,SCATTER_REVERSE));
            PetscCall(VecScatterEnd(scatter.get(),gathered.get(),output,ADD_VALUES,SCATTER_REVERSE));
        }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};

struct Level {
    PetscOwner<Mat,MatDestroy> matrix,prolongation;
    LevelData data;
    std::shared_ptr<FsiLevelSmoother> smoother;
    PetscOwner<Vec,VecDestroy> rhs,solution,residual,correction;
    FloatSparse float_matrix,float_transfer;
};
struct Hierarchy {
    MPI_Comm comm;
    Options configuration;
    std::string prefix;
    std::vector<std::array<double,3>> reference_coordinates;
    std::vector<Level> levels;
    PetscOwner<KSP,KSPDestroy> coarse;
    MonolithicFsiMgStats stats;
    PC owner=nullptr;
    PetscObjectState graph=0;
    bool ready=false;
    Hierarchy(MPI_Comm communicator,Mat matrix,const std::vector<DofKey>& semantics,
        const std::vector<std::array<double,3>>& coordinates,
        const std::vector<unsigned char>& trace,const Options& selected,const std::string& options_prefix,bool emit_report=true):
        comm(communicator),configuration(selected),prefix(options_prefix),reference_coordinates(coordinates) {
        Level fine;
        EONSIM_PETSC(MatGetNonzeroState(matrix,&graph));
        EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(matrix))); *fine.matrix.put()=matrix;
        fine.data=fine_data(comm,matrix,semantics,coordinates,trace);
        levels.push_back(std::move(fine));
        for(PetscInt depth=1;depth<configuration.max_levels;++depth) {
            PetscInt global=0; EONSIM_PETSC(MatGetSize(levels.back().matrix.get(),&global,nullptr));
            if(global<=configuration.coarse_limit) break;
            auto transfer=tentative_transfer(comm,levels.back().matrix.get(),levels.back().data,configuration);
            if(!transfer.matrix.get()) break;
            minimize_transfer_energy(comm,levels.back().matrix.get(),levels.back().data,transfer,configuration.energy_steps);
            Level next;
            EONSIM_PETSC(MatPtAP(levels.back().matrix.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,next.matrix.put()));
            levels.back().prolongation=std::move(transfer.matrix);
            next.data=std::move(transfer.coarse); stats.transfers.push_back(transfer.stats);
            levels.push_back(std::move(next));
        }
        stats.levels=static_cast<PetscInt>(levels.size()); stats.single_precision=configuration.single_precision;
        for(std::size_t level=0;level<levels.size();++level) {
            auto& data=levels[level];
            EONSIM_PETSC(MatCreateVecs(data.matrix.get(),data.solution.put(),data.rhs.put()));
            EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.residual.put()));
            EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.correction.put()));
            if(level+1<levels.size()) {
                data.smoother=make_fsi_level_smoother(comm,data.matrix.get(),data.data.semantics,data.data.trace,configuration.smoother);
                if(configuration.single_precision) {
                    data.float_matrix.update(data.matrix.get()); data.float_transfer.update(data.prolongation.get());
                    stats.fp32_value_bytes+=(data.float_matrix.values.size()+data.float_transfer.values.size())*sizeof(float);
                }
            }
        }
        configure_coarse(); ready=true; stats.refreshes=1; stats.hierarchy_rebuilds=1;
        if(emit_report) report();
    }
    void configure_coarse() {
        int size=1; MPI_Comm_size(comm,&size);
        const auto requested=std::min<PetscInt>(size,configuration.coarse_processes);
        // Choose the largest divisor no greater than the requested rank budget.
        PetscInt target=requested;
        while(target>1&&size%target!=0) --target;
        stats.coarse_processes=target;
        EONSIM_PETSC(KSPCreate(comm,coarse.put()));
        const auto coarse_prefix=prefix+"monolithic_mg_coarse_";
        EONSIM_PETSC(KSPSetOptionsPrefix(coarse.get(),coarse_prefix.c_str()));
        EONSIM_PETSC(KSPSetOperators(coarse.get(),levels.back().matrix.get(),levels.back().matrix.get()));
        PC pc=nullptr; EONSIM_PETSC(KSPGetPC(coarse.get(),&pc));
        if(target<size) {
            EONSIM_PETSC(KSPSetType(coarse.get(),KSPPREONLY));
            EONSIM_PETSC(PCSetType(pc,PCTELESCOPE));
            EONSIM_PETSC(PCTelescopeSetReductionFactor(pc,size/target));
            EONSIM_PETSC(PCTelescopeSetIgnoreDM(pc,PETSC_TRUE));
            option_default("-"+coarse_prefix+"telescope_ksp_type",target==1?"preonly":"gmres");
            option_default("-"+coarse_prefix+"telescope_pc_type",target==1?"lu":"asm");
            option_default("-"+coarse_prefix+"telescope_sub_ksp_type","preonly");
            option_default("-"+coarse_prefix+"telescope_sub_pc_type","lu");
            option_default("-"+coarse_prefix+"telescope_ksp_rtol","1e-12");
            option_default("-"+coarse_prefix+"telescope_ksp_max_it","200");
        } else if(size==1) {
            EONSIM_PETSC(KSPSetType(coarse.get(),KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCLU));
        } else {
            EONSIM_PETSC(KSPSetType(coarse.get(),KSPGMRES));
            EONSIM_PETSC(KSPSetTolerances(coarse.get(),1e-12,PETSC_DEFAULT,PETSC_DEFAULT,200));
            EONSIM_PETSC(KSPSetNormType(coarse.get(),KSP_NORM_UNPRECONDITIONED));
            EONSIM_PETSC(PCSetType(pc,PCASM)); EONSIM_PETSC(PCASMSetOverlap(pc,1));
            option_default("-"+coarse_prefix+"sub_ksp_type","preonly");
            option_default("-"+coarse_prefix+"sub_pc_type","lu");
        }
        EONSIM_PETSC(KSPSetFromOptions(coarse.get()));
        if(target<size) {
            PCType selected=nullptr; EONSIM_PETSC(PCGetType(pc,&selected));
            check(comm,selected&&std::strcmp(selected,PCTELESCOPE)==0,
                "coarse_processes requires PCTELESCOPE; coarse pc_type overrode the requested aggregation");
            PetscInt reduction=0; EONSIM_PETSC(PCTelescopeGetReductionFactor(pc,&reduction));
            check(comm,reduction==size/target,"coarse telescope reduction conflicts with coarse_processes");
        }
        EONSIM_PETSC(KSPSetErrorIfNotConverged(coarse.get(),PETSC_FALSE));
        EONSIM_PETSC(KSPSetUp(coarse.get()));
        EONSIM_PETSC(KSPSetReusePreconditioner(coarse.get(),PETSC_TRUE));
    }
    void report() {
        if(!configuration.report) return;
        EONSIM_PETSC(PetscPrintf(comm,
            "pc_monolithic_mg prefix=%s levels=%" PetscInt_FMT " coarse_processes=%" PetscInt_FMT
            " single_precision=%d refreshes=%" PetscInt_FMT " hierarchy_rebuilds=%" PetscInt_FMT " smoother=%s\n",
            prefix.empty()?"-":prefix.c_str(),stats.levels,stats.coarse_processes,
            stats.single_precision?1:0,stats.refreshes,stats.hierarchy_rebuilds,configuration.smoother.kind.c_str()));
        for(std::size_t i=0;i<stats.transfers.size();++i) {
            const auto& level=stats.transfers[i];
            EONSIM_PETSC(PetscPrintf(comm,
                "pc_monolithic_mg_level level=%zu rows=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
                " spectral_modes=%" PetscInt_FMT " reproduction_error=%.17g energy_before=%.17g energy_after=%.17g\n",
                i,level.rows,level.coarse_rows,level.spectral_modes,level.reproduction_error,level.energy_before,level.energy_after));
        }
        int rank=0; MPI_Comm_rank(comm,&rank);
        for(std::size_t i=0;i+1<levels.size();++i) {
            const auto smoother=query_fsi_level_smoother_stats(levels[i].smoother);
            EONSIM_PETSC(PetscSynchronizedPrintf(comm,
                "pc_monolithic_mg_smoother rank=%d level=%zu patches=%" PetscInt_FMT
                " interface_patches=%" PetscInt_FMT " factor_batches=%" PetscInt_FMT
                " numeric_factorizations=%" PetscInt_FMT " cached_factorizations=%" PetscInt_FMT
                " fp32_patches=%" PetscInt_FMT " polynomial_degree=%" PetscInt_FMT " eigenvalue_upper=%.17g\n",
                rank,i,smoother.patches.patches,smoother.patches.interface_patches,
                smoother.patches.factor_batches,smoother.patches.numeric_factorizations,
                smoother.patches.cached_factorizations,smoother.patches.fp32_patches,
                smoother.polynomial_degree,smoother.eigenvalue_upper));
        }
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    void refresh(Mat matrix) {
        ready=false;
        PetscInt begin=0,end=0,old_begin=0,old_end=0,n=0,old_n=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRange(levels.front().matrix.get(),&old_begin,&old_end));
        EONSIM_PETSC(MatGetSize(matrix,&n,nullptr)); EONSIM_PETSC(MatGetSize(levels.front().matrix.get(),&old_n,nullptr));
        PetscObjectState current_graph=0; EONSIM_PETSC(MatGetNonzeroState(matrix,&current_graph));
        check(comm,matrix==levels.front().matrix.get()&&begin==old_begin&&end==old_end&&n==old_n&&current_graph==graph,
            "refresh changed hierarchy matrix identity, graph, ownership or dimension");
        bool same_constraints=true;
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
            bool identity=true,diagonal=false;
            for(PetscInt j=0;j<count;++j) {
                same_constraints=same_constraints&&std::isfinite(values[j]);
                if(columns[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
                else identity=identity&&values[j]==0.;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
            same_constraints=same_constraints&&(levels.front().data.active[row-begin]!=(identity&&diagonal));
        }
        check(comm,same_constraints,"refresh changed fine constraints or supplied nonfinite coefficients");
        if(configuration.spectral_refresh_period>0&&stats.refreshes%configuration.spectral_refresh_period==0) {
            Hierarchy rebuilt(comm,matrix,levels.front().data.semantics,reference_coordinates,
                levels.front().data.trace,configuration,prefix,false);
            rebuilt.stats.applications=stats.applications;
            rebuilt.stats.refreshes=stats.refreshes+1;
            rebuilt.stats.hierarchy_rebuilds=stats.hierarchy_rebuilds+1;
            coarse=std::move(rebuilt.coarse); levels=std::move(rebuilt.levels); stats=std::move(rebuilt.stats);
            if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
            ready=true; report(); return;
        }
        for(std::size_t i=0;i+1<levels.size();++i) {
            Mat next=levels[i+1].matrix.get();
            EONSIM_PETSC(MatPtAP(levels[i].matrix.get(),levels[i].prolongation.get(),MAT_REUSE_MATRIX,PETSC_DEFAULT,&next));
            refresh_fsi_level_smoother(levels[i].smoother,levels[i].matrix.get());
            if(configuration.single_precision) levels[i].float_matrix.update(levels[i].matrix.get());
        }
        EONSIM_PETSC(KSPSetOperators(coarse.get(),levels.back().matrix.get(),levels.back().matrix.get()));
        EONSIM_PETSC(KSPSetReusePreconditioner(coarse.get(),PETSC_FALSE));
        EONSIM_PETSC(KSPSetUp(coarse.get()));
        // Numerical freshness is controlled only by the caller's refresh
        // registry. A later J change must not silently rebuild coarse factors.
        EONSIM_PETSC(KSPSetReusePreconditioner(coarse.get(),PETSC_TRUE));
        if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
        ready=true; ++stats.refreshes;
    }
    PetscErrorCode multiply(std::size_t level,Vec x,Vec y) {
        PetscFunctionBeginUser;
        if(configuration.single_precision) PetscCall(levels[level].float_matrix.multiply(x,y,false));
        else PetscCall(MatMult(levels[level].matrix.get(),x,y));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode smooth(std::size_t index,Vec rhs,Vec solution,bool& valid) {
        PetscFunctionBeginUser;
        auto& level=levels[index];
        PetscCall(multiply(index,solution,level.residual.get()));
        PetscCall(VecAYPX(level.residual.get(),-1.,rhs));
        const auto error=apply_fsi_level_smoother(level.smoother,level.residual.get(),level.correction.get());
        if(error==PETSC_ERR_NOT_CONVERGED) {
            valid=false; PetscCall(VecSet(level.correction.get(),0.));
        } else PetscCall(error);
        PetscCall(VecAXPY(solution,1.,level.correction.get()));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode cycle(std::size_t index,Vec rhs,Vec solution,bool& valid) {
        PetscFunctionBeginUser;
        auto& level=levels[index]; PetscCall(VecSet(solution,0.));
        if(index+1==levels.size()) {
            const auto error=KSPSolve(coarse.get(),rhs,solution);
            if(error) PetscFunctionReturn(error);
            KSPConvergedReason reason=KSP_CONVERGED_ITERATING; PC pc=nullptr; PCFailedReason failure=PC_NOERROR;
            PetscCall(KSPGetConvergedReason(coarse.get(),&reason)); PetscCall(KSPGetPC(coarse.get(),&pc));
            PetscCall(PCGetFailedReason(pc,&failure));
            if(reason<=0||failure!=PC_NOERROR) { valid=false; PetscCall(VecSet(solution,0.)); }
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        for(PetscInt step=0;step<configuration.pre_smooth;++step) PetscCall(smooth(index,rhs,solution,valid));
        PetscCall(multiply(index,solution,level.residual.get()));
        PetscCall(VecAYPX(level.residual.get(),-1.,rhs));
        auto& coarse_level=levels[index+1];
        if(configuration.single_precision)
            PetscCall(level.float_transfer.multiply(level.residual.get(),coarse_level.rhs.get(),true));
        else PetscCall(MatMultTranspose(level.prolongation.get(),level.residual.get(),coarse_level.rhs.get()));
        PetscCall(cycle(index+1,coarse_level.rhs.get(),coarse_level.solution.get(),valid));
        if(configuration.single_precision)
            PetscCall(level.float_transfer.multiply(coarse_level.solution.get(),level.correction.get(),false));
        else PetscCall(MatMult(level.prolongation.get(),coarse_level.solution.get(),level.correction.get()));
        PetscCall(VecAXPY(solution,1.,level.correction.get()));
        for(PetscInt step=0;step<configuration.post_smooth;++step) PetscCall(smooth(index,rhs,solution,valid));
        // No coarse correction is allowed on exact constraint rows. Correct
        // them directly even when a normal-equation smoother was selected.
        const PetscScalar* b=nullptr; PetscScalar* x=nullptr;
        PetscCall(VecGetArrayRead(rhs,&b)); PetscCall(VecGetArray(solution,&x));
        for(std::size_t row=0;row<level.data.active.size();++row)
            if(!level.data.active[row]) x[row]=b[row];
        PetscCall(VecRestoreArray(solution,&x)); PetscCall(VecRestoreArrayRead(rhs,&b));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode apply(PC pc,Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!ready) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        bool valid=true; PetscCall(cycle(0,input,output,valid));
        const PetscScalar* result=nullptr; PetscInt local=0;
        PetscCall(VecGetLocalSize(output,&local)); PetscCall(VecGetArrayRead(output,&result));
        for(PetscInt i=0;i<local;++i) valid=valid&&std::isfinite(result[i]);
        PetscCall(VecRestoreArrayRead(output,&result)); ++stats.applications;
        if(!valid) { PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); PetscCall(VecSet(output,PETSC_INFINITY)); }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};
using Handle=std::shared_ptr<Hierarchy>;
PetscErrorCode apply_hierarchy(PC pc,Vec input,Vec output) {
    PetscFunctionBeginUser;
    Handle* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    PetscCall((*state)->apply(pc,input,output)); PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode destroy_hierarchy(PC pc) {
    PetscFunctionBeginUser;
    Handle* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    if(state) (*state)->owner=nullptr;
    delete state; PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode view_hierarchy(PC pc,PetscViewer viewer) {
    PetscFunctionBeginUser;
    Handle* state=nullptr; PetscCall(PCShellGetContext(pc,&state));
    PetscBool ascii=PETSC_FALSE;
    PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        const auto& stats=(*state)->stats;
        PetscCall(PetscViewerASCIIPrintf(viewer,
            "All-field monolithic FSI V-cycle: levels=%" PetscInt_FMT ", coarse MPI ranks=%" PetscInt_FMT
            ", FP32 sparse arithmetic=%d, local FP32 coefficient bytes=%zu, refreshes=%" PetscInt_FMT
            ", hierarchy rebuilds=%" PetscInt_FMT ", applications=%" PetscInt_FMT "\n",stats.levels,stats.coarse_processes,
            stats.single_precision?1:0,stats.fp32_value_bytes,stats.refreshes,stats.hierarchy_rebuilds,stats.applications));
        PetscCall(PetscViewerASCIIPushTab(viewer)); PetscCall(KSPView((*state)->coarse.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    PetscFunctionReturn(PETSC_SUCCESS);
}
Handle* hierarchy_handle(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    Handle* result=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&result)); return result;
}
} // namespace

void validate_monolithic_fsi_mg_options(MPI_Comm comm,const std::string& prefix) {
    const auto selected=options(comm,prefix);
    validate_interface_patch_options(comm,prefix,selected.smoother.patches);
    char type[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+prefix+"pc_type").c_str(),type,sizeof(type),&set));
    check(comm,!set||std::strcmp(type,PCSHELL)==0,"monolithic hierarchy requires its shell preconditioner");
}
void configure_monolithic_fsi_mg(MPI_Comm comm,KSP solver,Mat assembled,
    const std::vector<DofKey>& owned_semantics,
    const std::vector<std::array<double,3>>& owned_coordinates,
    const std::vector<unsigned char>& owned_interface,PcSchurUpdates* updates) {
    check(comm,updates!=nullptr,"numeric Galerkin refresh requires a persistent update registry");
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"";
    validate_monolithic_fsi_mg_options(comm,prefix);
    auto state=std::make_shared<Hierarchy>(comm,assembled,owned_semantics,owned_coordinates,owned_interface,options(comm,prefix),prefix);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(PCSetType(pc,PCSHELL)); EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    auto handle=std::make_unique<Handle>(state);
    EONSIM_PETSC(PCShellSetContext(pc,handle.get())); EONSIM_PETSC(PCShellSetDestroy(pc,destroy_hierarchy));
    handle.release(); state->owner=pc;
    EONSIM_PETSC(PCShellSetName(pc,shell_name)); EONSIM_PETSC(PCShellSetApply(pc,apply_hierarchy));
    EONSIM_PETSC(PCShellSetView(pc,view_hierarchy));
    updates->refreshers.push_back([state](Mat matrix){state->refresh(matrix);});
}
bool query_monolithic_fsi_mg_stats(PC pc,MonolithicFsiMgStats& stats) {
    auto* state=hierarchy_handle(pc); if(!state) return false;
    stats=(*state)->stats; stats.smoothers.clear();
    for(std::size_t i=0;i+1<(*state)->levels.size();++i)
        stats.smoothers.push_back(query_fsi_level_smoother_stats((*state)->levels[i].smoother));
    return true;
}
KSP monolithic_fsi_mg_coarse_solver(PC pc) {
    auto* state=hierarchy_handle(pc); return state?(*state)->coarse.get():nullptr;
}
} // namespace eonsim
