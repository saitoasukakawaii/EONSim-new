#include "eonsim/monolithic_fsi_mg.hpp"
#include "eonsim/fsi_level_smoother.hpp"
#include "eonsim/native_float_sparse.hpp"
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
constexpr std::size_t candidate_count=36;
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
    PetscInt spectral_refresh_period=0,coarse_patch_overlap=0;
    double spectral_tolerance=.1,max_coarse_ratio=1.;
    bool single_precision=false,report=false,field_scaling=false,fsi_candidates=false,native_fp32=false,w_cycle=false,k_cycle=false;
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
        {"coarse_patch_overlap",&o.coarse_patch_overlap},
        {"patch_maximum_size",&o.smoother.patches.maximum_size},
        {"polynomial_degree",&o.smoother.polynomial_degree}})
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+entry.first).c_str(),entry.second,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"spectral_tolerance").c_str(),&o.spectral_tolerance,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"eigenvalue_ratio").c_str(),&o.smoother.eigenvalue_ratio,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"patch_damping").c_str(),&o.smoother.patches.damping,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"patch_strength").c_str(),&o.smoother.patches.strength_threshold,nullptr));
    PetscBool single=PETSC_FALSE,report=PETSC_FALSE,scaling=PETSC_FALSE,candidates=PETSC_FALSE,native=PETSC_FALSE,adaptive=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"single_precision").c_str(),&single,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"field_scaling").c_str(),&scaling,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"fsi_candidates").c_str(),&candidates,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"native_fp32").c_str(),&native,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"adaptive_patches").c_str(),&adaptive,nullptr));
    o.single_precision=single||native; o.report=report; o.smoother.patches.single_precision=o.single_precision;
    o.field_scaling=scaling;o.fsi_candidates=candidates;o.native_fp32=native;
    // An enriched local basis has a finite rank floor. Stop before another
    // level costs almost as much as its parent without reducing the problem.
    if(o.fsi_candidates) o.max_coarse_ratio=.8;
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"max_coarse_ratio").c_str(),&o.max_coarse_ratio,nullptr));
    o.smoother.patches.adaptive=adaptive;o.smoother.patches.native_storage=native;
    char type[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"smoother").c_str(),type,sizeof(type),&set));
    if(set) o.smoother.kind=type;
    char cycle[16]="v";
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"cycle").c_str(),cycle,sizeof(cycle),nullptr));
    o.w_cycle=std::strcmp(cycle,"w")==0;
    o.k_cycle=std::strcmp(cycle,"k")==0;
    const PetscInt values[]={o.aggregate_nodes,o.aggregate_rows,o.max_levels,o.coarse_limit,o.energy_steps,
        o.spectral_modes,o.pre_smooth,o.post_smooth,o.coarse_processes,o.single_precision?1:0,
        o.smoother.patches.overlap,o.smoother.patches.maximum_size,o.smoother.polynomial_degree,
        o.smoother.kind=="vanka"?1:o.smoother.kind=="chebyshev"?2:o.smoother.kind=="block_chebyshev"?3:0,
        o.spectral_refresh_period,o.report?1:0,o.coarse_patch_overlap,o.field_scaling?1:0,
        o.fsi_candidates?1:0,o.native_fp32?1:0,o.smoother.patches.adaptive?1:0,
        o.k_cycle?3:o.w_cycle?2:std::strcmp(cycle,"v")==0?1:0};
    constexpr int option_count=static_cast<int>(sizeof(values)/sizeof(values[0]));
    PetscInt minimum[option_count]{},maximum[option_count]{};
    MPI_Allreduce(values,minimum,option_count,MPIU_INT,MPI_MIN,comm);
    MPI_Allreduce(values,maximum,option_count,MPIU_INT,MPI_MAX,comm);
    bool valid=true; for(int i=0;i<option_count;++i) valid=valid&&minimum[i]==maximum[i];
    valid=valid&&o.aggregate_nodes>=2&&o.aggregate_nodes<=128&&o.aggregate_rows>=8&&o.aggregate_rows<=512&&
        o.max_levels>=1&&o.max_levels<=20&&o.coarse_limit>=1&&o.energy_steps>=0&&o.energy_steps<=3&&
        o.spectral_modes>=0&&o.spectral_modes<=8&&o.pre_smooth>=0&&o.post_smooth>=0&&
        o.pre_smooth+o.post_smooth>0&&o.pre_smooth<=8&&o.post_smooth<=8&&o.coarse_processes>=1&&values[13]!=0&&
        o.spectral_refresh_period>=0&&o.spectral_refresh_period<=1000000&&
        o.coarse_patch_overlap>=0&&o.coarse_patch_overlap<=2&&values[21]!=0&&
        (!o.native_fp32||o.smoother.kind=="vanka")&&(!o.smoother.patches.adaptive||o.smoother.kind=="vanka");
    const double real[]={o.spectral_tolerance,o.smoother.eigenvalue_ratio,o.smoother.patches.damping,o.max_coarse_ratio};
    double min_real[4]{},max_real[4]{};
    MPI_Allreduce(real,min_real,4,MPI_DOUBLE,MPI_MIN,comm);
    MPI_Allreduce(real,max_real,4,MPI_DOUBLE,MPI_MAX,comm);
    for(int i=0;i<4;++i) valid=valid&&std::isfinite(real[i])&&min_real[i]==max_real[i];
    valid=valid&&o.spectral_tolerance>=0&&o.spectral_tolerance<=1&&
        o.smoother.eigenvalue_ratio>0&&o.smoother.eigenvalue_ratio<1&&
        o.max_coarse_ratio>0&&o.max_coarse_ratio<=1;
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
    const std::vector<std::array<double,3>>& coordinates,const std::vector<unsigned char>& trace,bool enrich) {
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
        if(enrich) {
            std::array<double,3> x{};
            if(!coordinates.empty()) for(int c=0;c<3;++c) x[c]=(coordinates[local][c]-center[c])/scale;
            if(key.quantity==DofQuantity::pressure) {
                for(int c=0;c<3;++c) modes[22+c]=x[c];
                if(trace[local]) modes[31]=1.;
            }
            if(key.quantity==DofQuantity::velocity&&key.domain==DofDomain::fluid&&key.component<3&&
               key.kind==DofEntity::vertex&&key.mode==0&&key.space==1) {
                // In normalized reference coordinates, div(x/3)=1 and
                // div(e_i*x_i^2/2)=x_i. Pair constant/affine pressure with
                // smooth velocity divergence modes; translations/rotations
                // alone have zero divergence. Dirichlet rows stay excluded.
                modes[32]=x[key.component]/3.;
                modes[33+key.component]=.5*x[key.component]*x[key.component];
            }
            if(trace[local]&&vector_offset>=0&&key.component<3) {
                modes[25+key.component]=1.;
                const double rotations[3][3]={{0,-x[2],x[1]},{x[2],0,-x[0]},{-x[1],x[0],0}};
                for(int axis=0;axis<3;++axis) modes[28+axis]=rotations[axis][key.component];
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
Candidate candidate_scales(MPI_Comm comm,const LevelData& data) {
    Candidate local{},global{};
    for(const auto& row:data.candidates) for(std::size_t c=0;c<candidate_count;++c)
        local[c]=std::max(local[c],std::abs(row[c]));
    EONSIM_PETSC(MPI_Allreduce(local.data(),global.data(),static_cast<int>(candidate_count),MPI_DOUBLE,MPI_MAX,comm));
    for(auto& value:global) if(value==0) value=1.;
    return global;
}
Transfer tentative_transfer(MPI_Comm comm,Mat matrix,const LevelData& fine,const Options& o) {
    PetscInt begin=0,end=0,global=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&global,nullptr));
    const auto mode_scale=candidate_scales(comm,fine);
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
                for(std::size_t i=0;i<rows.size();++i) candidate[i]=fine.candidates[rows[i]][component]/mode_scale[component];
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
    const auto mode_scale=candidate_scales(comm,transfer.coarse);
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
                for(const auto& entry:row) column.push_back(halo[positions.at(entry.first)][component]/mode_scale[component]);
                try { append_basis(std::move(column),constraints); } catch(...) { valid=false; }
            }
            std::vector<double> direction; direction.reserve(row.size());
            for(const auto& entry:row) direction.push_back(entry.second);
            const auto unprojected_norm=std::sqrt(dot(direction,direction));
            // Orthogonal projection makes each row satisfy dP*N_coarse=0.
            for(int pass=0;pass<2;++pass) for(const auto& q:constraints) {
                const auto product=dot(q,direction);
                for(std::size_t j=0;j<direction.size();++j) direction[j]-=static_cast<double>(product*q[j]);
            }
            // Enriched candidate constraints may span the entire row stencil.
            // Its mathematical projected gradient is then zero; otherwise an
            // exact line search can amplify roundoff/its tiny curvature into
            // a finite violation of P*Nc=Nf. Remove only projection noise
            // relative to the input gradient, never a physical candidate or
            // a residual/acceptance tolerance.
            if(std::sqrt(dot(direction,direction))<=1024*std::numeric_limits<double>::epsilon()*unprojected_norm)
                std::fill(direction.begin(),direction.end(),0.);
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


struct Level {
    PetscOwner<Mat,MatDestroy> matrix,prolongation;
    LevelData data;
    std::shared_ptr<FsiLevelSmoother> smoother;
    PetscOwner<Vec,VecDestroy> rhs,solution,residual,correction,second_rhs,second_solution;
    PetscOwner<Vec,VecDestroy> restriction_weights,restriction_input;
    PetscOwner<Vec,VecDestroy> krylov_scale,first_action,second_action,metric_residual;
    NativeFloatSparse float_matrix,float_transfer;
};
struct Hierarchy {
    MPI_Comm comm;
    Options configuration;
    std::string prefix;
    std::vector<std::array<double,3>> reference_coordinates;
    std::vector<Level> levels;
    PetscOwner<Mat,MatDestroy> source_reference;
    PetscOwner<Vec,VecDestroy> left_scale,right_scale,scaled_input,scaled_output;
    PetscOwner<KSP,KSPDestroy> coarse;
    MonolithicFsiMgStats stats;
    PC owner=nullptr;
    PetscObjectState graph=0,numeric_state=0;
    bool ready=false;
    Hierarchy(MPI_Comm communicator,Mat matrix,const std::vector<DofKey>& semantics,
        const std::vector<std::array<double,3>>& coordinates,
        const std::vector<unsigned char>& trace,const Options& selected,const std::string& options_prefix,
        bool emit_report=true,bool keep_coordinates=true):
        comm(communicator),configuration(selected),prefix(options_prefix),
        reference_coordinates(keep_coordinates?coordinates:std::vector<std::array<double,3>>{}) {
        Level fine;
        EONSIM_PETSC(MatGetNonzeroState(matrix,&graph));
        EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(matrix)));*source_reference.put()=matrix;
        fine.data=fine_data(comm,matrix,semantics,coordinates,trace,configuration.fsi_candidates);
        if(configuration.field_scaling) {
            EONSIM_PETSC(MatDuplicate(matrix,MAT_COPY_VALUES,fine.matrix.put()));
            equilibrate(fine.matrix.get(),fine.data);
        } else {
            EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(matrix)));*fine.matrix.put()=matrix;
        }
        levels.push_back(std::move(fine));
        for(PetscInt depth=1;depth<configuration.max_levels;++depth) {
            PetscInt global=0; EONSIM_PETSC(MatGetSize(levels.back().matrix.get(),&global,nullptr));
            if(global<=configuration.coarse_limit) break;
            auto transfer=tentative_transfer(comm,levels.back().matrix.get(),levels.back().data,configuration);
            if(!transfer.matrix.get()) break;
            if(static_cast<double>(transfer.stats.coarse_rows)>
               configuration.max_coarse_ratio*static_cast<double>(global)) {
                stats.weak_coarsening_stop_rows=global;
                stats.weak_coarsening_proposed_rows=transfer.stats.coarse_rows;
                break;
            }
            minimize_transfer_energy(comm,levels.back().matrix.get(),levels.back().data,transfer,configuration.energy_steps);
            Level next;
            if(depth==1&&configuration.field_scaling) {
                // P interpolates scaled unknowns y, x=R*y. Retain the original
                // physical Galerkin test space R*P: Q^T=P^T*R*L^-1 and
                // Q^T*(L*A*R)*P=(R*P)^T*A*(R*P). Using plain P^T here would
                // change the test space whenever independent field row/column
                // scales differ, and can destroy mixed coarse stability.
                auto& parent=levels.back();
                EONSIM_PETSC(VecDuplicate(left_scale.get(),parent.restriction_weights.put()));
                EONSIM_PETSC(VecDuplicate(left_scale.get(),parent.restriction_input.put()));
                EONSIM_PETSC(VecPointwiseDivide(parent.restriction_weights.get(),right_scale.get(),left_scale.get()));
                const PetscScalar* weights=nullptr;bool valid=true;
                EONSIM_PETSC(VecGetArrayRead(parent.restriction_weights.get(),&weights));
                for(std::size_t row=0;row<parent.data.active.size();++row)
                    valid=valid&&weights[row]>0&&std::isfinite(weights[row]);
                EONSIM_PETSC(VecRestoreArrayRead(parent.restriction_weights.get(),&weights));
                check(comm,valid,"physical restriction weights are outside representable precision");
                PetscOwner<Mat,MatDestroy> form;
                EONSIM_PETSC(MatDuplicate(parent.matrix.get(),MAT_COPY_VALUES,form.put()));
                EONSIM_PETSC(MatDiagonalScale(form.get(),parent.restriction_weights.get(),nullptr));
                EONSIM_PETSC(MatPtAP(form.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,next.matrix.put()));
                // Scaled hierarchies rebuild on actual numeric changes. No
                // product reuse needs to retain this temporary FP64 operator.
                EONSIM_PETSC(MatProductClear(next.matrix.get()));
            } else {
                EONSIM_PETSC(MatPtAP(levels.back().matrix.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,next.matrix.put()));
            }
            levels.back().prolongation=std::move(transfer.matrix);
            next.data=std::move(transfer.coarse); stats.transfers.push_back(transfer.stats);
            levels.push_back(std::move(next));
        }
        stats.levels=static_cast<PetscInt>(levels.size()); stats.single_precision=configuration.single_precision;
        stats.native_fp32=configuration.native_fp32;stats.field_scaling=configuration.field_scaling;
        stats.fsi_candidates=configuration.fsi_candidates;stats.w_cycle=configuration.w_cycle;stats.k_cycle=configuration.k_cycle;
        for(std::size_t level=0;level<levels.size();++level) {
            auto& data=levels[level];
            EONSIM_PETSC(MatCreateVecs(data.matrix.get(),data.solution.put(),data.rhs.put()));
            EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.residual.put()));
            EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.correction.put()));
            if((configuration.w_cycle||configuration.k_cycle)&&level>0&&level+1<levels.size()) {
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.second_rhs.put()));
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.second_solution.put()));
            }
            if(configuration.k_cycle&&level>0&&level+1<levels.size()) {
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.krylov_scale.put()));
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.first_action.put()));
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.second_action.put()));
                EONSIM_PETSC(VecDuplicate(data.rhs.get(),data.metric_residual.put()));
                update_krylov_scale(data);
            }
            if(level+1<levels.size()) {
                auto smoother_options=configuration.smoother;
                // A coarse semantic entity is already a complete mixed
                // aggregate basis, including its spectral columns. Growing it
                // through a filled Galerkin graph can turn a bounded patch into
                // most of the level. Keep whole aggregate blocks by default;
                // inter-aggregate couplings remain in every full level matvec.
                if(level>0) smoother_options.patches.overlap=configuration.coarse_patch_overlap;
                data.smoother=make_fsi_level_smoother(comm,data.matrix.get(),data.data.semantics,data.data.trace,smoother_options);
                if(configuration.single_precision) {
                    data.float_matrix.update(data.matrix.get()); data.float_transfer.update(data.prolongation.get());
                    stats.fp32_value_bytes+=(data.float_matrix.values.size()+data.float_transfer.values.size())*sizeof(float);
                }
            }
        }
        configure_coarse();
        update_storage_stats();
        if(configuration.native_fp32) release_native_setup();
        EONSIM_PETSC(MatGetState(matrix,&numeric_state));
        ready=true; stats.refreshes=1; stats.hierarchy_rebuilds=1;
        if(emit_report) report();
    }
    void update_krylov_scale(Level& level) {
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(level.matrix.get(),&begin,&end));
        PetscScalar* scale=nullptr;bool valid=true;
        EONSIM_PETSC(VecGetArray(level.krylov_scale.get(),&scale));
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(level.matrix.get(),row,&count,&columns,&values));
            double maximum=0.;
            for(PetscInt j=0;j<count;++j) {
                valid=valid&&std::isfinite(values[j]);maximum=std::max(maximum,std::abs(values[j]));
            }
            EONSIM_PETSC(MatRestoreRow(level.matrix.get(),row,&count,&columns,&values));
            scale[row-begin]=maximum>0?1./maximum:0.;
            valid=valid&&scale[row-begin]>0&&std::isfinite(scale[row-begin]);
        }
        EONSIM_PETSC(VecRestoreArray(level.krylov_scale.get(),&scale));
        check(comm,valid,"K-cycle cannot equilibrate a zero/nonfinite coarse row");
    }
    static int field(const DofKey& key) {
        if(key.kind==DofEntity::body) return 4;
        if(key.kind==DofEntity::boundary) return 5;
        if(key.quantity==DofQuantity::pressure) return 1;
        if(key.domain==DofDomain::solid) return 2;
        if(key.domain==DofDomain::mesh) return 3;
        return key.domain==DofDomain::fluid?0:6;
    }
    void equilibrate(Mat matrix,LevelData& data) {
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        EONSIM_PETSC(MatCreateVecs(matrix,right_scale.put(),left_scale.put()));
        EONSIM_PETSC(VecDuplicate(left_scale.get(),scaled_input.put()));
        EONSIM_PETSC(VecDuplicate(right_scale.get(),scaled_output.put()));
        double local[7]{},maximum[7]{};
        for(PetscInt row=begin;row<end;++row) if(data.active[row-begin]) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
            auto& largest=local[field(data.semantics[row-begin])];
            for(PetscInt j=0;j<count;++j) largest=std::max(largest,std::abs(values[j]));
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
        }
        EONSIM_PETSC(MPI_Allreduce(local,maximum,7,MPI_DOUBLE,MPI_MAX,comm));
        PetscScalar* scale=nullptr;bool valid=true;
        EONSIM_PETSC(VecGetArray(left_scale.get(),&scale));
        for(PetscInt i=0;i<end-begin;++i) {
            const auto magnitude=maximum[field(data.semantics[i])];
            scale[i]=data.active[i]&&magnitude>0?1./magnitude:1.;
            valid=valid&&scale[i]>0&&std::isfinite(scale[i]);
        }
        EONSIM_PETSC(VecRestoreArray(left_scale.get(),&scale));
        check(comm,valid,"field row scaling is outside representable precision");
        EONSIM_PETSC(MatDiagonalScale(matrix,left_scale.get(),nullptr));
        PetscOwner<Mat,MatDestroy> transpose;
        EONSIM_PETSC(MatTranspose(matrix,MAT_INITIAL_MATRIX,transpose.put()));
        std::fill(std::begin(local),std::end(local),0.);
        for(PetscInt row=begin;row<end;++row) if(data.active[row-begin]) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(transpose.get(),row,&count,&columns,&values));
            auto& largest=local[field(data.semantics[row-begin])];
            for(PetscInt j=0;j<count;++j) largest=std::max(largest,std::abs(values[j]));
            EONSIM_PETSC(MatRestoreRow(transpose.get(),row,&count,&columns,&values));
        }
        EONSIM_PETSC(MPI_Allreduce(local,maximum,7,MPI_DOUBLE,MPI_MAX,comm));
        EONSIM_PETSC(VecGetArray(right_scale.get(),&scale));
        for(PetscInt i=0;i<end-begin;++i) {
            const auto magnitude=maximum[field(data.semantics[i])];
            scale[i]=data.active[i]&&magnitude>0?1./magnitude:1.;
            valid=valid&&scale[i]>0&&std::isfinite(scale[i]);
            // x=R*y: coarse candidates must be R^-1 times physical modes.
            for(auto& candidate:data.candidates[i]) candidate/=scale[i];
        }
        EONSIM_PETSC(VecRestoreArray(right_scale.get(),&scale));
        check(comm,valid,"field column scaling is outside representable precision");
        EONSIM_PETSC(MatDiagonalScale(matrix,nullptr,right_scale.get()));
    }
    static std::size_t coefficient_bytes(Mat matrix) {
        if(!matrix) return 0;
        MatInfo info{};EONSIM_PETSC(MatGetInfo(matrix,MAT_LOCAL,&info));
        return static_cast<std::size_t>(info.nz_allocated)*sizeof(PetscScalar);
    }
    void update_storage_stats() {
        stats.retained_fp64_operator_bytes=0;
        for(std::size_t i=0;i<levels.size();++i) {
            // The original fine P belongs to the outer nonlinear solver and
            // is not duplicated by this hierarchy. Count only owned extras.
            if(i>0||configuration.field_scaling)
                stats.retained_fp64_operator_bytes+=coefficient_bytes(levels[i].matrix.get());
            stats.retained_fp64_operator_bytes+=coefficient_bytes(levels[i].prolongation.get());
        }
    }
    void release_native_setup() {
        const auto before=stats.retained_fp64_operator_bytes;
        // PETSc Galerkin product metadata retains references to its operands.
        // Native refresh rebuilds setup, so symbolic product contexts can go.
        for(std::size_t i=1;i<levels.size();++i) EONSIM_PETSC(MatProductClear(levels[i].matrix.get()));
        for(std::size_t i=0;i+1<levels.size();++i) {
            release_native_fsi_smoother_setup(levels[i].smoother);
            const auto patch=query_fsi_level_smoother_stats(levels[i].smoother);
            stats.fp32_value_bytes+=patch.patches.fp32_matrix_bytes;
            levels[i].matrix=PetscOwner<Mat,MatDestroy>{};
            levels[i].prolongation=PetscOwner<Mat,MatDestroy>{};
        }
        for(std::size_t i=0;i<levels.size();++i) {
            std::vector<Candidate>().swap(levels[i].data.candidates);
            std::vector<std::vector<PetscInt>>().swap(levels[i].data.blocks);
            if(i>0) {
                std::vector<DofKey>().swap(levels[i].data.semantics);
                std::vector<unsigned char>().swap(levels[i].data.trace);
            }
        }
        update_storage_stats();
        stats.released_fp64_operator_bytes=before-stats.retained_fp64_operator_bytes;
    }
    void release_native_before_rebuild() {
        // The old numeric generation is already invalid. Retain only the fine
        // metadata needed to validate/retry refresh, and release old compact
        // matrices, patch factors, transfers and work vectors before allocating
        // replacement FP64 setup plus new FP32 storage. A construction failure
        // leaves ready=false and this metadata-only level; a later refresh can
        // safely rebuild it instead of dereferencing an empty level list.
        LevelData metadata=std::move(levels.front().data);
        coarse=PetscOwner<KSP,KSPDestroy>{};
        levels.clear();levels.emplace_back();levels.front().data=std::move(metadata);
        left_scale=PetscOwner<Vec,VecDestroy>{};right_scale=PetscOwner<Vec,VecDestroy>{};
        scaled_input=PetscOwner<Vec,VecDestroy>{};scaled_output=PetscOwner<Vec,VecDestroy>{};
        stats.levels=0;stats.transfers.clear();
        stats.fp32_value_bytes=stats.retained_fp64_operator_bytes=stats.released_fp64_operator_bytes=0;
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
            " single_precision=%d refreshes=%" PetscInt_FMT " hierarchy_rebuilds=%" PetscInt_FMT
            " smoother=%s field_scaling=%d fsi_candidates=%d native_fp32=%d cycle=%s"
            " max_coarse_ratio=%.17g weak_coarsening_stop_rows=%" PetscInt_FMT
            " weak_coarsening_proposed_rows=%" PetscInt_FMT "\n",
            prefix.empty()?"-":prefix.c_str(),stats.levels,stats.coarse_processes,
            stats.single_precision?1:0,stats.refreshes,stats.hierarchy_rebuilds,configuration.smoother.kind.c_str(),
            stats.field_scaling?1:0,stats.fsi_candidates?1:0,stats.native_fp32?1:0,stats.k_cycle?"k":stats.w_cycle?"w":"v",
            configuration.max_coarse_ratio,stats.weak_coarsening_stop_rows,stats.weak_coarsening_proposed_rows));
        for(std::size_t i=0;i<stats.transfers.size();++i) {
            const auto& level=stats.transfers[i];
            EONSIM_PETSC(PetscPrintf(comm,
                "pc_monolithic_mg_level level=%zu rows=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
                " spectral_modes=%" PetscInt_FMT " reproduction_error=%.17g energy_before=%.17g energy_after=%.17g\n",
                i,level.rows,level.coarse_rows,level.spectral_modes,level.reproduction_error,level.energy_before,level.energy_after));
        }
        int rank=0; MPI_Comm_rank(comm,&rank);
        EONSIM_PETSC(PetscSynchronizedPrintf(comm,
            "pc_monolithic_mg_storage rank=%d fp32_value_bytes=%zu retained_fp64_operator_bytes=%zu released_fp64_operator_bytes=%zu\n",
            rank,stats.fp32_value_bytes,stats.retained_fp64_operator_bytes,stats.released_fp64_operator_bytes));
        for(std::size_t i=0;i+1<levels.size();++i) {
            const auto smoother=query_fsi_level_smoother_stats(levels[i].smoother);
            EONSIM_PETSC(PetscSynchronizedPrintf(comm,
                "pc_monolithic_mg_smoother rank=%d level=%zu patches=%" PetscInt_FMT
                " patch_overlap=%" PetscInt_FMT " largest_patch=%" PetscInt_FMT
                " patch_rows=%" PetscInt_FMT " covered_owned_rows=%" PetscInt_FMT
                " interface_patches=%" PetscInt_FMT " factor_batches=%" PetscInt_FMT
                " numeric_factorizations=%" PetscInt_FMT " cached_factorizations=%" PetscInt_FMT
                " fp32_patches=%" PetscInt_FMT " polynomial_degree=%" PetscInt_FMT " eigenvalue_upper=%.17g"
                " expanded_patches=%" PetscInt_FMT " core_patches=%" PetscInt_FMT
                " retained_fp64_patch_bytes=%zu fp32_patch_bytes=%zu factor_bytes=%zu"
                " native_sparse_patches=%" PetscInt_FMT " native_dense_patches=%" PetscInt_FMT
                " native_index_bytes=%zu\n",
                rank,i,smoother.patches.patches,smoother.patches.overlap,smoother.patches.largest_patch,
                smoother.patches.patch_rows,smoother.patches.covered_owned_rows,smoother.patches.interface_patches,
                smoother.patches.factor_batches,smoother.patches.numeric_factorizations,
                smoother.patches.cached_factorizations,smoother.patches.fp32_patches,
                smoother.polynomial_degree,smoother.eigenvalue_upper,smoother.patches.expanded_patches,
                smoother.patches.core_patches,smoother.patches.retained_fp64_matrix_bytes,smoother.patches.fp32_matrix_bytes,
                smoother.patches.factor_bytes,smoother.patches.native_sparse_patches,smoother.patches.native_dense_patches,
                smoother.patches.native_index_bytes));
        }
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    void refresh(Mat matrix) {
        ready=false;
        PetscInt begin=0,end=0,old_begin=0,old_end=0,n=0,old_n=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRange(source_reference.get(),&old_begin,&old_end));
        EONSIM_PETSC(MatGetSize(matrix,&n,nullptr)); EONSIM_PETSC(MatGetSize(source_reference.get(),&old_n,nullptr));
        PetscObjectState current_graph=0; EONSIM_PETSC(MatGetNonzeroState(matrix,&current_graph));
        check(comm,matrix==source_reference.get()&&begin==old_begin&&end==old_end&&n==old_n&&current_graph==graph,
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
        PetscObjectState current_numeric_state=0;
        EONSIM_PETSC(MatGetState(matrix,&current_numeric_state));
        int local_changed=current_numeric_state!=numeric_state,changed=0;
        EONSIM_PETSC(MPI_Allreduce(&local_changed,&changed,1,MPI_INT,MPI_MAX,comm));
        if((changed&&(configuration.native_fp32||configuration.field_scaling||configuration.smoother.patches.adaptive))||
           (configuration.spectral_refresh_period>0&&stats.refreshes%configuration.spectral_refresh_period==0)) {
            if(configuration.native_fp32) release_native_before_rebuild();
            Hierarchy rebuilt(comm,matrix,levels.front().data.semantics,reference_coordinates,
                levels.front().data.trace,configuration,prefix,false,false);
            rebuilt.stats.applications=stats.applications;
            rebuilt.stats.level_matvecs=stats.level_matvecs;
            rebuilt.stats.zero_start_skips=stats.zero_start_skips;
            rebuilt.stats.coarse_revisits=stats.coarse_revisits;
            rebuilt.stats.coarse_solves=stats.coarse_solves;
            rebuilt.stats.coarse_iterations=stats.coarse_iterations;
            rebuilt.stats.smoother_applications=stats.smoother_applications;
            rebuilt.stats.coarse_krylov_directions=stats.coarse_krylov_directions;
            rebuilt.stats.coarse_krylov_rank_drops=stats.coarse_krylov_rank_drops;
            rebuilt.stats.coarse_krylov_rejections=stats.coarse_krylov_rejections;
            rebuilt.stats.coarse_krylov_reductions=stats.coarse_krylov_reductions;
            rebuilt.stats.coarse_krylov_max_residual_ratio=stats.coarse_krylov_max_residual_ratio;
            rebuilt.stats.refreshes=stats.refreshes+1;
            rebuilt.stats.hierarchy_rebuilds=stats.hierarchy_rebuilds+1;
            coarse=std::move(rebuilt.coarse); levels=std::move(rebuilt.levels); stats=std::move(rebuilt.stats);
            left_scale=std::move(rebuilt.left_scale);right_scale=std::move(rebuilt.right_scale);
            scaled_input=std::move(rebuilt.scaled_input);scaled_output=std::move(rebuilt.scaled_output);
            numeric_state=current_numeric_state;
            if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
            ready=true; report(); return;
        }
        if(configuration.native_fp32) {
            // An unchanged numeric generation has no FP64 setup to refresh.
            // Its compact coefficients/factors are already the exact cache.
            if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
            ready=true;++stats.refreshes;return;
        }
        for(std::size_t i=0;i+1<levels.size();++i) {
            // Re-evaluating an unchanged distributed PtAP can reorder sums at
            // deeper levels. Avoid both that roundoff churn and needless exact
            // factor-cache misses by retaining a truly unchanged generation.
            if(changed) {
                Mat next=levels[i+1].matrix.get();
                EONSIM_PETSC(MatPtAP(levels[i].matrix.get(),levels[i].prolongation.get(),MAT_REUSE_MATRIX,PETSC_DEFAULT,&next));
                if(configuration.k_cycle&&i>0) update_krylov_scale(levels[i]);
            }
            refresh_fsi_level_smoother(levels[i].smoother,levels[i].matrix.get());
            if(changed&&configuration.single_precision) levels[i].float_matrix.update(levels[i].matrix.get());
        }
        if(changed) {
            EONSIM_PETSC(KSPSetOperators(coarse.get(),levels.back().matrix.get(),levels.back().matrix.get()));
            EONSIM_PETSC(KSPSetReusePreconditioner(coarse.get(),PETSC_FALSE));
            EONSIM_PETSC(KSPSetUp(coarse.get()));
        }
        // Numerical freshness is controlled only by the caller's refresh
        // registry. A later J change must not silently rebuild coarse factors.
        EONSIM_PETSC(KSPSetReusePreconditioner(coarse.get(),PETSC_TRUE));
        if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
        numeric_state=current_numeric_state; ready=true; ++stats.refreshes;
    }
    PetscErrorCode multiply(std::size_t level,Vec x,Vec y) {
        PetscFunctionBeginUser;
        if(configuration.single_precision&&level+1<levels.size()) PetscCall(levels[level].float_matrix.multiply(x,y,false));
        else PetscCall(MatMult(levels[level].matrix.get(),x,y));
        ++stats.level_matvecs;
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode residual(std::size_t index,Vec rhs,Vec solution,bool zero_start) {
        PetscFunctionBeginUser;
        auto& level=levels[index];
        // cycle() establishes an exact zero initial correction on every rank.
        // Use that known state, not a norm or rank-local zero test, to omit one
        // sparse action and its halo exchange per noncoarse level. This also
        // covers restriction when the user explicitly disables presmoothing.
        if(zero_start) {
            PetscCall(VecCopy(rhs,level.residual.get()));
            ++stats.zero_start_skips;
        } else {
            PetscCall(multiply(index,solution,level.residual.get()));
            PetscCall(VecAYPX(level.residual.get(),-1.,rhs));
        }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode smooth(std::size_t index,Vec rhs,Vec solution,bool& valid,bool zero_start=false) {
        PetscFunctionBeginUser;
        auto& level=levels[index];
        PetscCall(residual(index,rhs,solution,zero_start));
        ++stats.smoother_applications;
        const auto error=apply_fsi_level_smoother(level.smoother,level.residual.get(),level.correction.get());
        if(error==PETSC_ERR_NOT_CONVERGED) {
            valid=false; PetscCall(VecSet(level.correction.get(),0.));
        } else PetscCall(error);
        PetscCall(VecAXPY(solution,1.,level.correction.get()));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode krylov_norm(Vec vector,PetscReal* norm) {
        PetscFunctionBeginUser;
        ++stats.coarse_krylov_reductions;
        PetscCall(VecNorm(vector,NORM_2,norm));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode krylov_dot(Vec first,Vec second,PetscScalar* product) {
        PetscFunctionBeginUser;
        ++stats.coarse_krylov_reductions;
        PetscCall(VecDot(first,second,product));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode minimize_coarse_residual(std::size_t index,bool& valid) {
        PetscFunctionBeginUser;
        auto& level=levels[index];
        // The first recursive cycle has produced z1=M*b. Minimize the full
        // coupled residual in at most two preconditioned directions. Row
        // equilibration defines the norm only; the coarse equations and all
        // transfer candidates remain unchanged.
        PetscCall(VecPointwiseMult(level.metric_residual.get(),level.krylov_scale.get(),level.rhs.get()));
        PetscReal rhs_norm=0.;PetscCall(krylov_norm(level.metric_residual.get(),&rhs_norm));
        if(!std::isfinite(rhs_norm)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        if(rhs_norm==0.) {PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);}
        PetscCall(multiply(index,level.solution.get(),level.first_action.get()));
        PetscCall(VecPointwiseMult(level.first_action.get(),level.krylov_scale.get(),level.first_action.get()));
        PetscReal first_norm=0.;PetscCall(krylov_norm(level.first_action.get(),&first_norm));
        if(!std::isfinite(first_norm)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        if(first_norm==0.||!std::isfinite(1./first_norm)) {
            ++stats.coarse_krylov_rank_drops;
            stats.coarse_krylov_max_residual_ratio=std::max(stats.coarse_krylov_max_residual_ratio,1.);
            PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        PetscCall(VecScale(level.first_action.get(),1./first_norm));
        PetscCall(VecScale(level.solution.get(),1./first_norm));
        PetscScalar alpha=0.;PetscCall(krylov_dot(level.first_action.get(),level.metric_residual.get(),&alpha));
        if(!std::isfinite(alpha)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        ++stats.coarse_krylov_directions;
        PetscCall(VecAXPY(level.metric_residual.get(),-alpha,level.first_action.get()));
        PetscReal first_residual=0.;PetscCall(krylov_norm(level.metric_residual.get(),&first_residual));
        if(!std::isfinite(first_residual)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        const double rank_tolerance=64.*(configuration.single_precision?
            std::numeric_limits<float>::epsilon():std::numeric_limits<double>::epsilon());
        const bool need_second=first_residual>rank_tolerance*rhs_norm;
        bool second_available=false;
        if(need_second&&std::isfinite(1./rhs_norm)) {
            // Use the next Arnoldi vector, rather than preconditioning the
            // first minimized residual again. The latter stagnates when the
            // first action is orthogonal to b, as can occur in saddle systems.
            PetscCall(VecPointwiseMult(level.second_rhs.get(),level.krylov_scale.get(),level.rhs.get()));
            PetscCall(VecScale(level.second_rhs.get(),1./rhs_norm));
            PetscCall(VecWAXPY(level.second_action.get(),-alpha/rhs_norm,
                              level.second_rhs.get(),level.first_action.get()));
            PetscScalar projection=0.;
            PetscCall(krylov_dot(level.second_rhs.get(),level.second_action.get(),&projection));
            PetscCall(VecAXPY(level.second_action.get(),-projection,level.second_rhs.get()));
            PetscReal next_norm=0.;PetscCall(krylov_norm(level.second_action.get(),&next_norm));
            if(!std::isfinite(next_norm)) {
                valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
            }
            if(next_norm>rank_tolerance&&std::isfinite(1./next_norm)) {
                PetscCall(VecPointwiseDivide(level.second_rhs.get(),level.second_action.get(),level.krylov_scale.get()));
                PetscCall(VecScale(level.second_rhs.get(),1./next_norm));
                second_available=true;
            }
        }
        if(second_available) {
            PetscCall(cycle(index,level.second_rhs.get(),level.second_solution.get(),valid));
            ++stats.coarse_revisits;
            PetscCall(multiply(index,level.second_solution.get(),level.second_action.get()));
            PetscCall(VecPointwiseMult(level.second_action.get(),level.krylov_scale.get(),level.second_action.get()));
            PetscReal unprojected_norm=0.;PetscCall(krylov_norm(level.second_action.get(),&unprojected_norm));
            if(!std::isfinite(unprojected_norm)) {
                valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
            }
            // Twice modified Gram-Schmidt on action vectors, with exactly the
            // same changes to their correction vectors, avoids normal equations
            // and protects against cancellation in almost dependent directions.
            for(int pass=0;pass<2;++pass) {
                PetscScalar beta=0.;PetscCall(krylov_dot(level.first_action.get(),level.second_action.get(),&beta));
                PetscCall(VecAXPY(level.second_action.get(),-beta,level.first_action.get()));
                PetscCall(VecAXPY(level.second_solution.get(),-beta,level.solution.get()));
            }
            PetscReal second_norm=0.;PetscCall(krylov_norm(level.second_action.get(),&second_norm));
            if(!std::isfinite(second_norm)) {
                valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
            }
            if(second_norm>rank_tolerance*unprojected_norm&&std::isfinite(1./second_norm)) {
                PetscCall(VecScale(level.second_action.get(),1./second_norm));
                PetscCall(VecScale(level.second_solution.get(),1./second_norm));
                PetscScalar gamma=0.;PetscCall(krylov_dot(level.second_action.get(),level.metric_residual.get(),&gamma));
                if(!std::isfinite(gamma)) {
                    valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
                }
                PetscCall(VecScale(level.solution.get(),alpha));
                PetscCall(VecAXPY(level.solution.get(),gamma,level.second_solution.get()));
                ++stats.coarse_krylov_directions;
            } else {
                ++stats.coarse_krylov_rank_drops;
                PetscCall(VecScale(level.solution.get(),alpha));
            }
        } else {
            if(need_second) ++stats.coarse_krylov_rank_drops;
            PetscCall(VecScale(level.solution.get(),alpha));
        }
        // Recompute the residual of the actual returned correction. Native
        // FP32 sparse arithmetic need not exactly reproduce a QR combination.
        // Zero is in the trial subspace, so reject a finite increasing update
        // rather than allowing it to amplify the coarse error. Nonfinite
        // actions still propagate through the existing PC failure protocol.
        PetscCall(multiply(index,level.solution.get(),level.first_action.get()));
        PetscCall(VecPointwiseMult(level.first_action.get(),level.krylov_scale.get(),level.first_action.get()));
        PetscCall(VecPointwiseMult(level.metric_residual.get(),level.krylov_scale.get(),level.rhs.get()));
        PetscCall(VecAXPY(level.metric_residual.get(),-1.,level.first_action.get()));
        PetscReal final_norm=0.;PetscCall(krylov_norm(level.metric_residual.get(),&final_norm));
        if(!std::isfinite(final_norm)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        if(final_norm>rhs_norm) {
            ++stats.coarse_krylov_rejections;final_norm=rhs_norm;
            PetscCall(VecSet(level.solution.get(),0.));
        }
        stats.coarse_krylov_max_residual_ratio=std::max(stats.coarse_krylov_max_residual_ratio,final_norm/rhs_norm);
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode cycle(std::size_t index,Vec rhs,Vec solution,bool& valid) {
        PetscFunctionBeginUser;
        auto& level=levels[index]; PetscCall(VecSet(solution,0.));
        if(index+1==levels.size()) {
            ++stats.coarse_solves;
            const auto error=KSPSolve(coarse.get(),rhs,solution);
            if(error) PetscFunctionReturn(error);
            PetscInt iterations=0;PetscCall(KSPGetIterationNumber(coarse.get(),&iterations));
            stats.coarse_iterations+=iterations;
            KSPConvergedReason reason=KSP_CONVERGED_ITERATING; PC pc=nullptr; PCFailedReason failure=PC_NOERROR;
            PetscCall(KSPGetConvergedReason(coarse.get(),&reason)); PetscCall(KSPGetPC(coarse.get(),&pc));
            PetscCall(PCGetFailedReason(pc,&failure));
            if(reason<=0||failure!=PC_NOERROR) { valid=false; PetscCall(VecSet(solution,0.)); }
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        for(PetscInt step=0;step<configuration.pre_smooth;++step)
            PetscCall(smooth(index,rhs,solution,valid,step==0));
        PetscCall(residual(index,rhs,solution,configuration.pre_smooth==0));
        auto& coarse_level=levels[index+1];
        Vec restriction_input=level.residual.get();
        if(level.restriction_weights.get()) {
            PetscCall(VecPointwiseMult(level.restriction_input.get(),level.restriction_weights.get(),restriction_input));
            restriction_input=level.restriction_input.get();
        }
        if(configuration.single_precision)
            PetscCall(level.float_transfer.multiply(restriction_input,coarse_level.rhs.get(),true));
        else PetscCall(MatMultTranspose(level.prolongation.get(),restriction_input,coarse_level.rhs.get()));
        PetscCall(cycle(index+1,coarse_level.rhs.get(),coarse_level.solution.get(),valid));
        if(configuration.k_cycle&&index+2<levels.size()) {
            PetscCall(minimize_coarse_residual(index+1,valid));
        } else if(configuration.w_cycle&&index+2<levels.size()) {
            PetscCall(multiply(index+1,coarse_level.solution.get(),coarse_level.second_rhs.get()));
            PetscCall(VecAYPX(coarse_level.second_rhs.get(),-1.,coarse_level.rhs.get()));
            PetscCall(cycle(index+1,coarse_level.second_rhs.get(),coarse_level.second_solution.get(),valid));
            PetscCall(VecAXPY(coarse_level.solution.get(),1.,coarse_level.second_solution.get()));
            ++stats.coarse_revisits;
        }
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
        bool valid=true;
        if(configuration.field_scaling) {
            PetscCall(VecPointwiseMult(scaled_input.get(),left_scale.get(),input));
            PetscCall(cycle(0,scaled_input.get(),scaled_output.get(),valid));
            PetscCall(VecPointwiseMult(output,right_scale.get(),scaled_output.get()));
        } else PetscCall(cycle(0,input,output,valid));
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
            ", hierarchy rebuilds=%" PetscInt_FMT ", applications=%" PetscInt_FMT
            ", level matvecs=%" PetscInt_FMT ", zero-start skips=%" PetscInt_FMT "\n",stats.levels,stats.coarse_processes,
            stats.single_precision?1:0,stats.fp32_value_bytes,stats.refreshes,stats.hierarchy_rebuilds,stats.applications,
            stats.level_matvecs,stats.zero_start_skips));
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
