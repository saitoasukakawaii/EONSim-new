#include "eonsim/monolithic_fsi_mg.hpp"
#include "fsi_profile.hpp"
#include "eonsim/fsi_level_smoother.hpp"
#include "eonsim/native_float_sparse.hpp"
#include "eonsim/distributed_mg_layout.hpp"
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
    PetscInt spectral_refresh_period=0,coarse_patch_overlap=0,pressure_image_modes=0,coarse_rows_per_rank=0;
    double spectral_tolerance=.1,max_coarse_ratio=1.;
    bool single_precision=false,report=false,field_scaling=false,fsi_candidates=false,native_fp32=false,w_cycle=false,k_cycle=false;
    bool pressure_supremizers=false,saddle_point=false,divergence_preserving=false,divergence_commuting=false;
    bool distributed_aggregation=false,adaptive_hierarchy=false,reuse_hierarchy=false;
    bool matrix_free_fine=false,communication_avoiding=false;
    bool profile_levels=false;
    PetscInt hierarchy_max_age=8,adaptive_interval=16;
    double hierarchy_drift=.2,adaptive_threshold=.9,maximum_complexity=8.;
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
        {"polynomial_degree",&o.smoother.polynomial_degree},
        {"schur_iterations",&o.smoother.schur_iterations},{"hierarchy_max_age",&o.hierarchy_max_age},
        {"adaptive_interval",&o.adaptive_interval},{"pressure_image_modes",&o.pressure_image_modes},
        {"coarse_rows_per_rank",&o.coarse_rows_per_rank}})
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,(base+entry.first).c_str(),entry.second,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"spectral_tolerance").c_str(),&o.spectral_tolerance,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"eigenvalue_ratio").c_str(),&o.smoother.eigenvalue_ratio,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"patch_damping").c_str(),&o.smoother.patches.damping,nullptr));
    EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+"patch_strength").c_str(),&o.smoother.patches.strength_threshold,nullptr));
    PetscBool single=PETSC_FALSE,report=PETSC_FALSE,scaling=PETSC_FALSE,candidates=PETSC_FALSE,native=PETSC_FALSE,adaptive=PETSC_FALSE;
    PetscBool supremizers=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"single_precision").c_str(),&single,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"field_scaling").c_str(),&scaling,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"fsi_candidates").c_str(),&candidates,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"native_fp32").c_str(),&native,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"adaptive_patches").c_str(),&adaptive,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+"pressure_supremizers").c_str(),&supremizers,nullptr));
    o.single_precision=single||native; o.report=report; o.smoother.patches.single_precision=o.single_precision;
    o.field_scaling=scaling;o.fsi_candidates=candidates;o.native_fp32=native;
    o.pressure_supremizers=supremizers;
    for(const auto& entry:std::vector<std::pair<const char*,bool*>>{
        {"saddle_point",&o.saddle_point},{"divergence_preserving",&o.divergence_preserving},
        {"divergence_commuting",&o.divergence_commuting},
        {"distributed_aggregation",&o.distributed_aggregation},{"adaptive_hierarchy",&o.adaptive_hierarchy},
        {"reuse_hierarchy",&o.reuse_hierarchy},{"matrix_free_fine",&o.matrix_free_fine},
        {"braess_local_fields",&o.smoother.braess_local_fields},
        {"communication_avoiding",&o.communication_avoiding},{"profile_levels",&o.profile_levels}}) {
        PetscBool value=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,(base+entry.first).c_str(),&value,nullptr));
        *entry.second=value;
    }
    for(const auto& entry:std::vector<std::pair<const char*,double*>>{
        {"braess_alpha",&o.smoother.braess_alpha},{"hierarchy_drift",&o.hierarchy_drift},
        {"adaptive_threshold",&o.adaptive_threshold},{"maximum_complexity",&o.maximum_complexity}})
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,(base+entry.first).c_str(),entry.second,nullptr));
    PetscBool coarse_explicit=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+"coarse_processes").c_str(),&coarse_explicit));
    if(!coarse_explicit&&(o.saddle_point||o.distributed_aggregation)) o.coarse_processes=0;
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
        o.smoother.kind=="vanka"?1:o.smoother.kind=="chebyshev"?2:o.smoother.kind=="block_chebyshev"?3:o.smoother.kind=="braess_sarazin"?4:
        o.smoother.kind=="vanka_multiplicative"?5:o.smoother.kind=="vanka_colored"?6:0,
        o.spectral_refresh_period,o.report?1:0,o.coarse_patch_overlap,o.field_scaling?1:0,
        o.fsi_candidates?1:0,o.native_fp32?1:0,o.smoother.patches.adaptive?1:0,
        o.k_cycle?3:o.w_cycle?2:std::strcmp(cycle,"v")==0?1:0,o.pressure_supremizers?1:0,
        o.saddle_point?1:0,o.divergence_preserving?1:0,o.distributed_aggregation?1:0,
        o.adaptive_hierarchy?1:0,o.reuse_hierarchy?1:0,o.matrix_free_fine?1:0,
        o.communication_avoiding?1:0,o.hierarchy_max_age,o.adaptive_interval,o.smoother.schur_iterations,
        o.divergence_commuting?1:0,o.pressure_image_modes,o.coarse_rows_per_rank,
        o.smoother.braess_local_fields?1:0,o.profile_levels?1:0};
    constexpr int option_count=static_cast<int>(sizeof(values)/sizeof(values[0]));
    PetscInt minimum[option_count]{},maximum[option_count]{};
    MPI_Allreduce(values,minimum,option_count,MPIU_INT,MPI_MIN,comm);
    MPI_Allreduce(values,maximum,option_count,MPIU_INT,MPI_MAX,comm);
    bool valid=true; for(int i=0;i<option_count;++i) valid=valid&&minimum[i]==maximum[i];
    valid=valid&&o.aggregate_nodes>=2&&o.aggregate_nodes<=128&&o.aggregate_rows>=8&&o.aggregate_rows<=512&&
        o.max_levels>=1&&o.max_levels<=20&&o.coarse_limit>=1&&o.energy_steps>=0&&o.energy_steps<=3&&
        o.spectral_modes>=0&&o.spectral_modes<=8&&o.pre_smooth>=0&&o.post_smooth>=0&&
        o.pre_smooth+o.post_smooth>0&&o.pre_smooth<=8&&o.post_smooth<=8&&o.coarse_processes>=0&&values[13]!=0&&
        o.coarse_rows_per_rank>=0&&(!o.coarse_rows_per_rank||o.coarse_processes==0)&&
        o.spectral_refresh_period>=0&&o.spectral_refresh_period<=1000000&&
        o.coarse_patch_overlap>=0&&o.coarse_patch_overlap<=2&&values[21]!=0&&
        (!o.pressure_supremizers||(o.fsi_candidates&&o.spectral_modes>0))&&
        (!o.native_fp32||o.smoother.kind.find("vanka")==0)&&
        (!o.smoother.patches.adaptive||o.smoother.kind.find("vanka")==0)&&
        (!o.divergence_preserving||(o.saddle_point&&!o.single_precision))&&
        (!o.divergence_commuting||o.divergence_preserving)&&
        o.pressure_image_modes>=0&&o.pressure_image_modes<=8&&
        (!o.pressure_image_modes||(o.saddle_point&&!o.divergence_commuting&&
          !o.divergence_preserving&&o.energy_steps==0&&!o.reuse_hierarchy))&&
        (!o.reuse_hierarchy||(!o.native_fp32&&!o.smoother.patches.adaptive))&&
        (o.smoother.kind!="braess_sarazin"||o.saddle_point)&&
        o.hierarchy_max_age>=1&&o.hierarchy_max_age<=1000000&&
        o.adaptive_interval>=1&&o.adaptive_interval<=1000000&&
        o.smoother.schur_iterations>=1&&o.smoother.schur_iterations<=32;
    const double real[]={o.spectral_tolerance,o.smoother.eigenvalue_ratio,o.smoother.patches.damping,o.max_coarse_ratio,
        o.smoother.braess_alpha,o.hierarchy_drift,o.adaptive_threshold,o.maximum_complexity};
    double min_real[8]{},max_real[8]{};
    MPI_Allreduce(real,min_real,8,MPI_DOUBLE,MPI_MIN,comm);
    MPI_Allreduce(real,max_real,8,MPI_DOUBLE,MPI_MAX,comm);
    for(int i=0;i<8;++i) valid=valid&&std::isfinite(real[i])&&min_real[i]==max_real[i];
    valid=valid&&o.spectral_tolerance>=0&&o.spectral_tolerance<=1&&
        o.smoother.eigenvalue_ratio>0&&o.smoother.eigenvalue_ratio<1&&
        o.max_coarse_ratio>0&&o.max_coarse_ratio<=1&&o.smoother.braess_alpha>0&&
        o.hierarchy_drift>0&&o.hierarchy_drift<=1&&o.adaptive_threshold>0&&
        o.maximum_complexity>=1.;
    check(comm,valid,"inconsistent or out-of-range hierarchy options");
    return o;
}
struct LevelData {
    std::vector<Candidate> candidates;
    std::vector<std::vector<PetscInt>> blocks;
    std::vector<DofKey> semantics;
    std::vector<unsigned char> trace,active;
    std::vector<int> origin_rank;
};
bool is_pressure(const DofKey& key) {
    return key.quantity==DofQuantity::pressure&&key.kind!=DofEntity::boundary;
}
struct PressurePair {
    // Initially aggregate-basis indices; made global coarse indices below.
    std::vector<PetscInt> pressure_columns,velocity_columns;
    std::vector<std::vector<double>> pressure_combinations;
    std::vector<double> expected_coupling,row_norms;
    double coupling_scale=1.,minimum_singular=0.;
};
struct Transfer {
    PetscOwner<Mat,MatDestroy> matrix;
    LevelData coarse;
    std::vector<unsigned char> anchors;
    std::vector<unsigned char> fixed_columns;
    std::vector<PressurePair> pressure_pairs;
    MonolithicFsiMgLevelStats stats;
    bool energy_completed=false;
    std::vector<std::pair<PetscInt,PetscInt>> aggregate_columns;
    std::vector<std::vector<PetscInt>> aggregate_rows;
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

// Typed enrichment never introduces pressure values in a primal column.
// The full coupled Galerkin operator still includes both offdiagonal blocks.
PetscInt saddle_spectral_enrichment(Mat matrix,PetscInt begin,const std::vector<PetscInt>& rows,
    const LevelData& fine,PetscInt maximum,double threshold,std::vector<std::vector<double>>& basis) {
    std::vector<PetscInt> primal,positions;
    for(std::size_t i=0;i<rows.size();++i) if(!is_pressure(fine.semantics[rows[i]])) {
        primal.push_back(rows[i]);positions.push_back(static_cast<PetscInt>(i));
    }
    std::vector<std::vector<double>> restricted;
    for(const auto& q:basis) {
        std::vector<double> v;for(auto i:positions) v.push_back(q[i]);append_basis(std::move(v),restricted);
    }
    const auto previous=restricted.size();
    spectral_enrichment(matrix,begin,primal,maximum,threshold,restricted);
    for(std::size_t k=previous;k<restricted.size();++k) {
        std::vector<double> q(rows.size(),0.);
        for(std::size_t j=0;j<positions.size();++j) q[positions[j]]=restricted[k][j];
        basis.push_back(std::move(q));
    }
    return static_cast<PetscInt>(restricted.size()-previous);
}

double paired_minimum_singular(const std::vector<double>& matrix,std::size_t n) {
    if(n==1) return std::abs(matrix[0]);
    if(n!=2) return 0.;
    long double scale=0.;for(const auto value:matrix) scale=std::max(scale,std::abs(static_cast<long double>(value)));
    if(!(scale>0&&std::isfinite(scale))) return 0.;
    const long double a=matrix[0]/scale,b=matrix[1]/scale,c=matrix[2]/scale,d=matrix[3]/scale;
    const auto squared=a*a+b*b+c*c+d*d,determinant=a*d-b*c;
    const auto largest=std::sqrt(.5L*(squared+std::sqrt(std::max(0.L,squared*squared-4*determinant*determinant))));
    return largest>0?static_cast<double>(scale*std::abs(determinant)/largest):0.;
}

PressurePair pressure_enrichment(Mat matrix,PetscInt begin,const std::vector<PetscInt>& rows,
    const LevelData& fine,const std::vector<double>& test_weights,PetscInt maximum,
    std::vector<std::vector<double>>& basis,bool saddle_point=false) {
    PressurePair pair;
    if(maximum==0||basis.size()+1>=rows.size()) return pair;
    std::vector<PetscInt> pressure,velocity,pressure_position(rows.size(),-1);
    std::map<PetscInt,PetscInt> velocity_position;
    for(std::size_t i=0;i<rows.size();++i) {
        const auto& key=fine.semantics[rows[i]];
        if(saddle_point?is_pressure(key):(key.domain==DofDomain::fluid&&key.quantity==DofQuantity::pressure)) {
            pressure_position[i]=static_cast<PetscInt>(pressure.size());pressure.push_back(static_cast<PetscInt>(i));
        } else if((saddle_point&&!is_pressure(key))||(key.domain==DofDomain::fluid&&key.quantity==DofQuantity::velocity)) {
            velocity_position.emplace(begin+rows[i],static_cast<PetscInt>(velocity.size()));
            velocity.push_back(static_cast<PetscInt>(i));
        }
    }
    if(pressure.empty()||velocity.empty()) return pair;
    for(std::size_t column=0;column<basis.size();++column) {
        bool pure=true,nonzero=false;
        for(std::size_t i=0;i<rows.size();++i) if(basis[column][i]!=0.) {
            pure=pure&&pressure_position[i]>=0;nonzero=true;
        }
        if(pure&&nonzero) pair.pressure_columns.push_back(static_cast<PetscInt>(column));
    }
    if(pair.pressure_columns.empty()) return PressurePair{};
    const auto nv=velocity.size(),np=pressure.size(),m=pair.pressure_columns.size();
    std::vector<double> divergence(np*nv,0.);
    std::vector<long double> energy(nv,0.);
    double coupling_scale=0.;
    for(std::size_t i=0;i<rows.size();++i) {
        if(pressure_position[i]<0&&velocity_position.count(begin+rows[i])==0) continue;
        PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,begin+rows[i],&count,&columns,&values));
        bool finite=true;
        for(PetscInt j=0;j<count;++j) {
            const auto found=velocity_position.find(columns[j]);if(found==velocity_position.end()) continue;
            // The restriction is P^T W, hence the physical coarse form is
            // P^T (W A_s) P. Use that very form, not an unweighted surrogate B.
            const auto value=values[j]*test_weights[rows[i]];
            finite=finite&&std::isfinite(value);
            if(pressure_position[i]>=0) {
                divergence[static_cast<std::size_t>(pressure_position[i])*nv+found->second]=value;
                coupling_scale=std::max(coupling_scale,std::abs(value));
            } else energy[found->second]+=std::abs(static_cast<long double>(value));
        }
        EONSIM_PETSC(MatRestoreRow(matrix,begin+rows[i],&count,&columns,&values));
        if(!finite) throw std::runtime_error("Nonfinite weighted pressure/velocity coupling");
    }
    if(!(coupling_scale>0)) return PressurePair{};
    const auto smallest=*std::min_element(energy.begin(),energy.end());
    // H_jj=sum_i |(W A_s)_ij| over aggregate velocity rows is a positive
    // diagonal velocity-energy proxy. A missing/zero velocity block cannot
    // certify a pair and simply retains the existing spectral allocation.
    if(!(smallest>0&&std::isfinite(smallest))) return PressurePair{};
    std::vector<double> inverse_root(nv);
    for(std::size_t j=0;j<nv;++j) {
        inverse_root[j]=static_cast<double>(std::sqrt(smallest/energy[j]));
        if(!(inverse_root[j]>0&&std::isfinite(inverse_root[j]))) return PressurePair{};
    }
    for(auto& value:divergence) value/=coupling_scale;
    // D=constant*H^-1. QR of sqrt(D)*V gives the bounded constrained solve
    // s=sqrt(D)(I-Q Q^T)sqrt(D) B^T q, so V^T s=0 and q^T B s>=0.
    // V contains every existing basis column restricted to fluid velocity;
    // even coherent interface columns therefore retain their original span.
    std::vector<std::vector<double>> constraints,velocity_basis;
    for(const auto& column:basis) {
        std::vector<double> candidate(nv),unweighted(nv);
        for(std::size_t j=0;j<nv;++j) {
            unweighted[j]=column[velocity[j]];candidate[j]=inverse_root[j]*unweighted[j];
        }
        append_basis(std::move(candidate),constraints);
        append_basis(std::move(unweighted),velocity_basis);
    }
    if(constraints.size()>=nv||velocity_basis.size()>=nv) return PressurePair{};
    std::vector<std::vector<double>> gradients(m,std::vector<double>(nv)),responses(m,std::vector<double>(nv));
    for(std::size_t column=0;column<m;++column) {
        for(std::size_t j=0;j<nv;++j) {
            long double value=0.;
            for(std::size_t i=0;i<np;++i)
                value+=static_cast<long double>(basis[pair.pressure_columns[column]][pressure[i]])*divergence[i*nv+j];
            gradients[column][j]=static_cast<double>(value);
            responses[column][j]=inverse_root[j]*gradients[column][j];
        }
        for(int pass=0;pass<2;++pass) for(const auto& q:constraints) {
            const auto product=dot(q,responses[column]);
            for(std::size_t j=0;j<nv;++j) responses[column][j]-=static_cast<double>(product*q[j]);
        }
        for(std::size_t j=0;j<nv;++j) responses[column][j]*=inverse_root[j];
    }
    // Select at most two pressure combinations with the largest missing
    // velocity-response energy. This tiny eigensolve replaces spectral slots;
    // it never increases the aggregate basis budget or introduces an inner KSP.
    std::vector<double> coupling(m*m,0.),eigenvalues(m),work(std::max<std::size_t>(1,3*m-1));
    for(std::size_t i=0;i<m;++i) for(std::size_t j=i;j<m;++j)
        coupling[i+j*m]=coupling[j+i*m]=static_cast<double>(.5L*(dot(gradients[i],responses[j])+dot(gradients[j],responses[i])));
    PetscBLASInt dimension=0,lwork=0,info=0;
    EONSIM_PETSC(PetscBLASIntCast(static_cast<PetscInt>(m),&dimension));
    EONSIM_PETSC(PetscBLASIntCast(static_cast<PetscInt>(work.size()),&lwork));
    LAPACKsyev_("V","U",&dimension,coupling.data(),&dimension,eigenvalues.data(),work.data(),&lwork,&info);
    if(info!=0) throw std::runtime_error("Pressure response Gram eigensolve failed");
    for(const auto value:eigenvalues)
        if(!std::isfinite(value)) throw std::runtime_error("Nonfinite pressure response energy");
    const auto largest=std::max(0.,eigenvalues.back());
    const double cutoff=256*std::numeric_limits<double>::epsilon()*rows.size()*largest;
    for(std::size_t index=m;index-->0&&pair.velocity_columns.size()<static_cast<std::size_t>(std::min<PetscInt>(2,maximum))&&
        basis.size()+1<rows.size();) {
        if(!(eigenvalues[index]>cutoff)) break;
        std::vector<double> candidate(nv,0.),combination(m);
        for(std::size_t k=0;k<m;++k) {
            combination[k]=coupling[k+index*m];
            for(std::size_t j=0;j<nv;++j) candidate[j]+=combination[k]*responses[k][j];
        }
        const auto column=static_cast<PetscInt>(basis.size());
        // Reproject roundoff only inside the velocity subspace. Full mixed
        // QR would introduce tiny structure/ALE entries from coherent trace
        // candidates, invalidating a B-only pairing oracle in disparate units.
        if(append_basis(std::move(candidate),velocity_basis)) {
            std::vector<double> full(rows.size(),0.);
            for(std::size_t j=0;j<nv;++j) full[velocity[j]]=velocity_basis.back()[j];
            basis.push_back(std::move(full));
            pair.velocity_columns.push_back(column);pair.pressure_combinations.push_back(std::move(combination));
        }
    }
    pair.coupling_scale=coupling_scale;
    while(!pair.velocity_columns.empty()) {
        const auto count=pair.velocity_columns.size();
        pair.expected_coupling.assign(count*count,0.);pair.row_norms.assign(count,0.);
        std::vector<double> normalized(count*count);
        for(std::size_t i=0;i<count;++i) {
            std::vector<double> gradient(nv,0.);
            for(std::size_t k=0;k<m;++k) for(std::size_t j=0;j<nv;++j)
                gradient[j]+=pair.pressure_combinations[i][k]*gradients[k][j];
            pair.row_norms[i]=static_cast<double>(std::sqrt(dot(gradient,gradient)));
            for(std::size_t j=0;j<count;++j) {
                long double value=0.;for(std::size_t k=0;k<nv;++k)
                    value+=static_cast<long double>(gradient[k])*basis[pair.velocity_columns[j]][velocity[k]];
                pair.expected_coupling[i*count+j]=static_cast<double>(value);
                normalized[i*count+j]=pair.row_norms[i]>0?static_cast<double>(value)/pair.row_norms[i]:0.;
            }
        }
        pair.minimum_singular=paired_minimum_singular(normalized,count);
        if(std::isfinite(pair.minimum_singular)&&pair.minimum_singular>256*std::numeric_limits<double>::epsilon()*rows.size())
            return pair;
        // A numerically dependent selected pair is not an inf-sup certificate.
        // Release its slot back to the existing local spectral enrichment.
        basis.pop_back();pair.velocity_columns.pop_back();pair.pressure_combinations.pop_back();
    }
    return PressurePair{};
}

// Both modes include off-rank primal support. Strict QR may fill the pressure
// space. The compressed mode keeps physical candidates and adds leading left
// singular vectors of the remaining local divergence image.
PetscInt enrich_pressure_image(Mat divergence,PetscInt begin,const std::vector<PetscInt>& rows,
    const LevelData& fine,std::vector<std::vector<double>>& basis,PetscInt budget,bool& saturated) {
    std::vector<PetscInt> pressure;
    for(std::size_t i=0;i<rows.size();++i) if(is_pressure(fine.semantics[rows[i]])) pressure.push_back(static_cast<PetscInt>(i));
    if(pressure.empty()) return 0;
    std::vector<std::vector<double>> pressure_basis;
    for(const auto& q:basis) {
        std::vector<double> p;for(auto i:pressure) p.push_back(q[i]);append_basis(std::move(p),pressure_basis);
    }
    const auto initial=pressure_basis.size();
    const auto limit=pressure.size()/2;
    if(budget&&initial>=limit) {
        saturated=initial==pressure.size();
        return 0;
    }
    std::map<PetscInt,std::vector<double>> images;
    for(std::size_t i=0;i<pressure.size();++i) {
        PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(divergence,begin+rows[pressure[i]],&count,&columns,&values));
        for(PetscInt j=0;j<count;++j) if(values[j]!=0.) {
            auto& image=images[columns[j]];if(image.empty()) image.assign(pressure.size(),0.);image[i]=values[j];
        }
        EONSIM_PETSC(MatRestoreRow(divergence,begin+rows[pressure[i]],&count,&columns,&values));
    }
    if(budget) {
        const auto n=pressure.size();
        double scale=0.;
        for(const auto& item:images) for(double value:item.second) scale=std::max(scale,std::abs(value));
        if(scale>0.) {
            std::vector<double> gram(n*n,0.);
            for(auto& item:images) {
                auto& column=item.second;
                for(auto& value:column) value/=scale;
                for(const auto& mode:pressure_basis) {
                    const auto coefficient=dot(column,mode);
                    for(std::size_t i=0;i<n;++i) column[i]-=static_cast<double>(coefficient*mode[i]);
                }
                for(std::size_t j=0;j<n;++j) for(std::size_t i=0;i<=j;++i)
                    gram[i+j*n]+=column[i]*column[j];
            }
            PetscBLASInt dimension=0,lwork=0,info=0;
            EONSIM_PETSC(PetscBLASIntCast(static_cast<PetscInt>(n),&dimension));
            EONSIM_PETSC(PetscBLASIntCast(3*static_cast<PetscInt>(n)-1,&lwork));
            std::vector<double> eigenvalues(n),work(lwork);
            LAPACKsyev_("V","U",&dimension,gram.data(),&dimension,eigenvalues.data(),work.data(),&lwork,&info);
            if(info!=0||!std::isfinite(eigenvalues.back()))
                throw std::runtime_error("Compressed pressure image eigensolve failed");
            const auto target=std::min(limit,initial+static_cast<std::size_t>(budget));
            const auto tolerance=256*std::numeric_limits<double>::epsilon()*eigenvalues.back();
            for(std::size_t j=n;j>0&&pressure_basis.size()<target;--j) {
                if(eigenvalues[j-1]<=std::max(0.,tolerance)) break;
                append_basis(std::vector<double>(gram.begin()+(j-1)*n,gram.begin()+j*n),pressure_basis);
            }
        }
    } else {
        for(auto& item:images) {
            double magnitude=0.;for(auto x:item.second) magnitude=std::max(magnitude,std::abs(x));
            if(magnitude>0) {for(auto& x:item.second) x/=magnitude;append_basis(std::move(item.second),pressure_basis);}
            if(pressure_basis.size()==pressure.size()) break;
        }
    }
    for(std::size_t k=initial;k<pressure_basis.size();++k) {
        std::vector<double> full(rows.size(),0.);
        for(std::size_t i=0;i<pressure.size();++i) full[pressure[i]]=pressure_basis[k][i];
        basis.push_back(std::move(full));
    }
    saturated=pressure_basis.size()==pressure.size();
    return static_cast<PetscInt>(pressure_basis.size()-initial);
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
void minimize_divergence_preserving_energy(MPI_Comm comm,Mat matrix,const LevelData& fine,Transfer& transfer,
    PetscInt steps,Vec physical_test_weights);
double pressure_projection_defect(Mat image,const Transfer& transfer);
Transfer local_tentative_transfer(MPI_Comm comm,Mat matrix,const LevelData& fine,const Options& o,Vec physical_test_weights) {
    PetscInt begin=0,end=0,global=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix,&global,nullptr));
    const auto mode_scale=candidate_scales(comm,fine);
    std::vector<double> test_weights;
    if(o.pressure_supremizers) test_weights.assign(end-begin,1.);
    if(o.pressure_supremizers&&physical_test_weights) {
        const PetscScalar* weights=nullptr;EONSIM_PETSC(VecGetArrayRead(physical_test_weights,&weights));
        for(PetscInt i=0;i<end-begin;++i) test_weights[i]=weights[i];
        EONSIM_PETSC(VecRestoreArrayRead(physical_test_weights,&weights));
    }
    PetscOwner<Mat,MatDestroy> compatible_divergence;
    if(o.divergence_commuting||o.pressure_image_modes) {
        PetscOwner<Vec,VecDestroy> pressure_mask,primal_mask;
        EONSIM_PETSC(MatCreateVecs(matrix,primal_mask.put(),pressure_mask.put()));
        PetscScalar *p=nullptr,*u=nullptr;
        EONSIM_PETSC(VecGetArray(pressure_mask.get(),&p));EONSIM_PETSC(VecGetArray(primal_mask.get(),&u));
        for(PetscInt i=0;i<end-begin;++i) {
            p[i]=fine.active[i]&&is_pressure(fine.semantics[i])?1.:0.;
            u[i]=fine.active[i]&&!is_pressure(fine.semantics[i])?1.:0.;
        }
        EONSIM_PETSC(VecRestoreArray(primal_mask.get(),&u));EONSIM_PETSC(VecRestoreArray(pressure_mask.get(),&p));
        if(physical_test_weights) EONSIM_PETSC(VecPointwiseMult(pressure_mask.get(),physical_test_weights,pressure_mask.get()));
        EONSIM_PETSC(MatDuplicate(matrix,MAT_COPY_VALUES,compatible_divergence.put()));
        EONSIM_PETSC(MatDiagonalScale(compatible_divergence.get(),pressure_mask.get(),primal_mask.get()));
    }
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
    for(std::size_t block=0;block<neighbors.size();++block) {
        auto& adjacent=neighbors[block];
        std::sort(adjacent.begin(),adjacent.end());
        adjacent.erase(std::unique(adjacent.begin(),adjacent.end()),adjacent.end());
        if(!fine.origin_rank.empty()) std::stable_sort(adjacent.begin(),adjacent.end(),[&](PetscInt a,PetscInt b){
            const int origin=fine.origin_rank[fine.blocks[block].front()];
            const bool remote_a=fine.origin_rank[fine.blocks[a].front()]!=origin;
            const bool remote_b=fine.origin_rank[fine.blocks[b].front()]!=origin;
            return remote_a&&!remote_b;
        });
    }
    Transfer result; result.stats.rows=global; result.anchors.resize(end-begin,0);
    std::vector<unsigned char> assigned(fine.blocks.size(),0);
    std::vector<Column> columns;
    std::vector<std::pair<PetscInt,PetscInt>> coarse_blocks;
    long double local_error=0,local_norm=0;
    PetscInt spectral=0,supremizers=0,cross_rank=0,closure=0,saturated_pressure=0; bool valid=true; std::string local_error_message;
    std::vector<PetscInt> seed_order(fine.blocks.size());
    std::iota(seed_order.begin(),seed_order.end(),0);
    if(!fine.origin_rank.empty()) {
        std::vector<unsigned char> cut(fine.blocks.size(),0);
        for(std::size_t block=0;block<fine.blocks.size();++block) for(auto neighbor:neighbors[block])
            cut[block]=cut[block]||(fine.origin_rank[fine.blocks[block].front()]!=fine.origin_rank[fine.blocks[neighbor].front()]);
        std::stable_sort(seed_order.begin(),seed_order.end(),[&](PetscInt a,PetscInt b){return cut[a]>cut[b];});
    }
    try {
        for(auto seed:seed_order) if(!assigned[seed]) {
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
                if(o.saddle_point) {
                    for(int field=0;field<2;++field) {
                        auto separated=candidate;
                        for(std::size_t i=0;i<rows.size();++i)
                            if(is_pressure(fine.semantics[rows[i]])!=(field==1)) separated[i]=0.;
                        append_basis(std::move(separated),basis);
                    }
                } else append_basis(std::move(candidate),basis);
            }
            if(o.divergence_commuting||o.pressure_image_modes) {
                bool saturated=false;
                closure+=enrich_pressure_image(compatible_divergence.get(),begin,rows,fine,basis,o.pressure_image_modes,saturated);
                if(saturated) ++saturated_pressure;
            }
            auto pair=o.pressure_supremizers?
                pressure_enrichment(matrix,begin,rows,fine,test_weights,o.spectral_modes,basis,o.saddle_point):PressurePair{};
            const auto paired_modes=static_cast<PetscInt>(pair.velocity_columns.size());
            supremizers+=paired_modes;
            spectral+=o.saddle_point?
                saddle_spectral_enrichment(matrix,begin,rows,fine,o.spectral_modes-paired_modes,o.spectral_tolerance,basis):
                spectral_enrichment(matrix,begin,rows,o.spectral_modes-paired_modes,o.spectral_tolerance,basis);
            std::vector<unsigned char> fixed(basis.size(),0);
            if(paired_modes) {
                for(const auto column:pair.pressure_columns) fixed[column]=1;
                for(const auto column:pair.velocity_columns) fixed[column]=1;
            }
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
            for(std::size_t basis_index=0;basis_index<basis.size();++basis_index) {
                const auto& basis_column=basis[basis_index];
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
                bool pressure_column=false,primal_column=false;
                if(o.saddle_point) for(std::size_t i=0;i<rows.size();++i) if(basis_column[i]!=0.) {
                    pressure_column=pressure_column||is_pressure(fine.semantics[rows[i]]);
                    primal_column=primal_column||!is_pressure(fine.semantics[rows[i]]);
                }
                if(o.saddle_point&&pressure_column&&primal_column)
                    throw std::runtime_error("Saddle-point interpolation mixed primal and pressure entries");
                result.fixed_columns.push_back(fixed[basis_index]|(pressure_column?2:0));
                result.coarse.trace.push_back(trace); result.coarse.active.push_back(1);
            }
            if(paired_modes) {
                for(auto& column:pair.pressure_columns) column+=first;
                for(auto& column:pair.velocity_columns) column+=first;
                result.pressure_pairs.push_back(std::move(pair));
            }
            const auto last=static_cast<PetscInt>(columns.size());
            if(last>first) {
                coarse_blocks.emplace_back(first,last);
                result.aggregate_columns.emplace_back(first,last);
                result.aggregate_rows.push_back(rows);
                if(!fine.origin_rank.empty()) {
                    const auto origin=fine.origin_rank[rows.front()];
                    if(std::any_of(rows.begin(),rows.end(),[&](PetscInt row){return fine.origin_rank[row]!=origin;})) ++cross_rank;
                }
            }
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
    MPI_Allreduce(&cross_rank,&result.stats.distributed_aggregates,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&closure,&result.stats.compatible_pressure_modes,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&saturated_pressure,&result.stats.saturated_pressure_aggregates,1,MPIU_INT,MPI_SUM,comm);
    PetscInt pressure_count=0,coarse_pressure_count=0;
    for(std::size_t i=0;i<fine.semantics.size();++i) if(fine.active[i]&&is_pressure(fine.semantics[i])) ++pressure_count;
    for(const auto tag:result.fixed_columns) if(tag&2) ++coarse_pressure_count;
    MPI_Allreduce(&pressure_count,&result.stats.pressure_rows,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&coarse_pressure_count,&result.stats.coarse_pressure_rows,1,MPIU_INT,MPI_SUM,comm);
    if(o.pressure_supremizers) {
        MPI_Allreduce(&supremizers,&result.stats.pressure_supremizer_modes,1,MPIU_INT,MPI_SUM,comm);
        const auto paired_aggregates=static_cast<PetscInt>(result.pressure_pairs.size());
        MPI_Allreduce(&paired_aggregates,&result.stats.pressure_paired_aggregates,1,MPIU_INT,MPI_SUM,comm);
    }
    if(rank==0) coarse_begin=0;
    for(auto& pair:result.pressure_pairs) {
        for(auto& column:pair.pressure_columns) column+=coarse_begin;
        for(auto& column:pair.velocity_columns) column+=coarse_begin;
    }
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
            if(o.saddle_point&&(result.fixed_columns[i]&2)) {key.domain=DofDomain::fluid;key.quantity=DofQuantity::pressure;}
            key.component=static_cast<std::uint16_t>(i-block.first); key.space=0;
            result.coarse.semantics[i]=key; indices.push_back(i);
        }
        result.coarse.blocks.push_back(std::move(indices));
    }
    if(o.divergence_preserving) {
        minimize_divergence_preserving_energy(comm,matrix,fine,result,o.energy_steps,physical_test_weights);
        result.energy_completed=true;
        if(o.divergence_commuting) check(comm,std::isfinite(result.stats.divergence_commuting_defect)&&
            result.stats.divergence_commuting_defect<=1e-10,"compatible pressure closure failed the commuting relation");
    }
    if(o.pressure_image_modes) {
        PetscOwner<Mat,MatDestroy> image;
        EONSIM_PETSC(MatMatMult(compatible_divergence.get(),result.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,image.put()));
        result.stats.divergence_commuting_defect=pressure_projection_defect(image.get(),result);
        check(comm,std::isfinite(result.stats.divergence_commuting_defect)&&
              result.stats.divergence_commuting_defect<=1.+1e-10,
              "compressed pressure projection exceeds the divergence image norm");
    }
    return result;
}

// Gather only candidate rows touched by this rank's transfer stencil. This is
// setup-only halo data, not a replicated global coarse field or matrix.
std::vector<Candidate> gather_candidates(Mat transfer,const LevelData& coarse,
    const std::vector<PetscInt>& columns,const std::vector<unsigned char>& fixed_columns,
    std::vector<unsigned char>* fixed_halo) {
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
    if(fixed_halo) {
        PetscScalar* owned=nullptr;EONSIM_PETSC(VecGetArray(global.get(),&owned));
        for(std::size_t i=0;i<fixed_columns.size();++i) owned[i]=fixed_columns[i];
        EONSIM_PETSC(VecRestoreArray(global.get(),&owned));
        EONSIM_PETSC(VecScatterBegin(scatter.get(),global.get(),local.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),global.get(),local.get(),INSERT_VALUES,SCATTER_FORWARD));
        const PetscScalar* gathered=nullptr;EONSIM_PETSC(VecGetArrayRead(local.get(),&gathered));
        fixed_halo->resize(columns.size());
        for(std::size_t i=0;i<columns.size();++i) (*fixed_halo)[i]=static_cast<unsigned char>(gathered[i]);
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

void minimize_transfer_energy(MPI_Comm comm,Mat matrix,const LevelData& fine,Transfer& transfer,PetscInt steps,bool saddle_point=false) {
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
        std::vector<unsigned char> fixed_halo;
        const bool paired=transfer.stats.pressure_supremizer_modes>0||saddle_point;
        const auto halo=gather_candidates(transfer.matrix.get(),transfer.coarse,columns,transfer.fixed_columns,
                                         paired?&fixed_halo:nullptr);
        std::map<PetscInt,std::size_t> positions;
        for(std::size_t i=0;i<columns.size();++i) positions.emplace(columns[i],i);
        bool valid=true;
        for(PetscInt local=0;local<end-begin;++local) {
            auto& row=rows[local];
            // Fixed whole columns preserve the selected actual discrete
            // pressure/velocity pairing. Include remote columns in the halo:
            // energy stencils cross ownership even though aggregates do not.
            if(paired) {
                for(auto entry=row.begin();entry!=row.end();) {
                    if((fixed_halo[positions.at(entry->first)]&1)||
                       (saddle_point&&bool(fixed_halo[positions.at(entry->first)]&2)!=is_pressure(fine.semantics[local])))
                        entry=row.erase(entry);
                    else ++entry;
                }
            }
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

// Constrain the *change* of every primal transfer column to ker(B). B contains
// all active pressure equations and all active nonpressure columns, including
// structural/ALE couplings. Transposing B exposes every pressure equation
// incident to an aggregate, including equations owned by another MPI rank.
// Pressure interpolation is fixed. Thus B P_v and the coarse pressure/primal
// pairing survive energy minimization. A commuting diagram additionally needs
// the separate compatible pressure-image closure and its caller's audit gate.
void minimize_divergence_preserving_energy(MPI_Comm comm,Mat matrix,const LevelData& fine,Transfer& transfer,
    PetscInt steps,Vec physical_test_weights) {
    PetscInt begin=0,end=0,n=0,nc=0,cbegin=0,cend=0;
    EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    EONSIM_PETSC(MatGetSize(transfer.matrix.get(),&n,&nc));
    EONSIM_PETSC(MatGetOwnershipRangeColumn(transfer.matrix.get(),&cbegin,&cend));
    PetscOwner<Vec,VecDestroy> pressure,primal;
    EONSIM_PETSC(MatCreateVecs(matrix,primal.put(),pressure.put()));
    PetscScalar *pv=nullptr,*uv=nullptr;
    EONSIM_PETSC(VecGetArray(pressure.get(),&pv));EONSIM_PETSC(VecGetArray(primal.get(),&uv));
    for(PetscInt i=0;i<end-begin;++i) {
        pv[i]=fine.active[i]&&is_pressure(fine.semantics[i])?1.:0.;
        uv[i]=fine.active[i]&&!is_pressure(fine.semantics[i])?1.:0.;
    }
    EONSIM_PETSC(VecRestoreArray(primal.get(),&uv));EONSIM_PETSC(VecRestoreArray(pressure.get(),&pv));
    if(physical_test_weights) EONSIM_PETSC(VecPointwiseMult(pressure.get(),physical_test_weights,pressure.get()));
    PetscOwner<Mat,MatDestroy> divergence,transpose,initial,before;
    EONSIM_PETSC(MatDuplicate(matrix,MAT_COPY_VALUES,divergence.put()));
    EONSIM_PETSC(MatDiagonalScale(divergence.get(),pressure.get(),primal.get()));
    EONSIM_PETSC(MatTranspose(divergence.get(),MAT_INITIAL_MATRIX,transpose.put()));
    EONSIM_PETSC(MatDuplicate(transfer.matrix.get(),MAT_COPY_VALUES,initial.put()));
    EONSIM_PETSC(MatMatMult(divergence.get(),initial.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,before.put()));
    auto scaled=row_scaled_operator(comm,matrix);
    PetscOwner<Mat,MatDestroy> action;
    EONSIM_PETSC(MatMatMult(scaled.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,action.put()));
    PetscReal norm=0.;EONSIM_PETSC(MatNorm(action.get(),NORM_FROBENIUS,&norm));
    transfer.stats.energy_before=transfer.stats.energy_after=norm*norm;
    struct ConstraintBlock {
        std::vector<PetscInt> rows,columns;
        std::vector<std::vector<double>> left,right;
    };
    std::vector<ConstraintBlock> blocks;
    PetscInt constraints=0,nullity=0;
    const auto scales=candidate_scales(comm,transfer.coarse);
    bool valid=true;std::string error;
    try {
        for(std::size_t a=0;a<transfer.aggregate_rows.size();++a) {
            ConstraintBlock block;
            for(auto row:transfer.aggregate_rows[a])
                if(!is_pressure(fine.semantics[row])&&!transfer.anchors[row]) block.rows.push_back(row);
            for(PetscInt column=transfer.aggregate_columns[a].first;column<transfer.aggregate_columns[a].second;++column)
                if((transfer.fixed_columns[column]&3)==0) block.columns.push_back(column);
            if(block.rows.empty()||block.columns.empty()) continue;
            std::map<PetscInt,std::vector<double>> incidence;
            for(std::size_t i=0;i<block.rows.size();++i) {
                PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(transpose.get(),begin+block.rows[i],&count,&columns,&values));
                for(PetscInt j=0;j<count;++j) if(values[j]!=0.) {
                    auto& constraint=incidence[columns[j]];
                    if(constraint.empty()) constraint.assign(block.rows.size(),0.);
                    constraint[i]=values[j];
                }
                EONSIM_PETSC(MatRestoreRow(transpose.get(),begin+block.rows[i],&count,&columns,&values));
            }
            for(auto& entry:incidence) {
                double magnitude=0.;for(auto x:entry.second) magnitude=std::max(magnitude,std::abs(x));
                if(magnitude>0) {for(auto& x:entry.second) x/=magnitude;append_basis(std::move(entry.second),block.left);}
            }
            for(std::size_t k=0;k<candidate_count;++k) {
                std::vector<double> constraint;
                for(auto column:block.columns) constraint.push_back(transfer.coarse.candidates[column][k]/scales[k]);
                append_basis(std::move(constraint),block.right);
            }
            constraints+=static_cast<PetscInt>(block.left.size());
            nullity+=static_cast<PetscInt>(block.rows.size()-block.left.size());
            blocks.push_back(std::move(block));
        }
    } catch(const std::exception& e) {valid=false;error=e.what();}
    check(comm,valid,"divergence constraint QR failed: "+error);
    MPI_Allreduce(&constraints,&transfer.stats.divergence_constraints,1,MPIU_INT,MPI_SUM,comm);
    MPI_Allreduce(&nullity,&transfer.stats.divergence_nullity,1,MPIU_INT,MPI_SUM,comm);
    for(PetscInt iteration=0;iteration<steps;++iteration) {
        PetscOwner<Mat,MatDestroy> gradient,direction,direction_action;
        EONSIM_PETSC(MatTransposeMatMult(scaled.get(),action.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,gradient.put()));
        std::vector<PetscInt> nnz(end-begin,0);
        for(const auto& block:blocks) for(auto row:block.rows) nnz[row]=static_cast<PetscInt>(block.columns.size());
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,cend-cbegin,n,nc,0,nnz.data(),0,nullptr,direction.put()));
        for(const auto& block:blocks) {
            const auto nr=block.rows.size(),nk=block.columns.size();
            if(block.left.size()>=nr||block.right.size()>=nk) continue;
            std::vector<double> dense(nr*nk,0.);
            for(std::size_t i=0;i<nr;++i) {
                PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(gradient.get(),begin+block.rows[i],&count,&columns,&values));
                for(std::size_t j=0;j<nk&&count>0;++j) {
                    const auto found=std::lower_bound(columns,columns+count,cbegin+block.columns[j]);
                    if(found!=columns+count&&*found==cbegin+block.columns[j]) dense[i*nk+j]=-values[found-columns];
                }
                EONSIM_PETSC(MatRestoreRow(gradient.get(),begin+block.rows[i],&count,&columns,&values));
            }
            const long double original_norm=std::sqrt(dot(dense,dense));
            // Orthogonal left and right projections commute. Two QR passes
            // retain accuracy for disparate physical field scales.
            for(int pass=0;pass<2;++pass) {
                for(const auto& q:block.left) for(std::size_t j=0;j<nk;++j) {
                    long double d=0.;for(std::size_t i=0;i<nr;++i) d+=q[i]*static_cast<long double>(dense[i*nk+j]);
                    for(std::size_t i=0;i<nr;++i) dense[i*nk+j]-=static_cast<double>(d*q[i]);
                }
                for(const auto& q:block.right) for(std::size_t i=0;i<nr;++i) {
                    long double d=0.;for(std::size_t j=0;j<nk;++j) d+=q[j]*static_cast<long double>(dense[i*nk+j]);
                    for(std::size_t j=0;j<nk;++j) dense[i*nk+j]-=static_cast<double>(d*q[j]);
                }
            }
            if(std::sqrt(dot(dense,dense))<=1024.*std::numeric_limits<double>::epsilon()*original_norm)
                std::fill(dense.begin(),dense.end(),0.);
            for(std::size_t i=0;i<nr;++i) for(std::size_t j=0;j<nk;++j)
                EONSIM_PETSC(MatSetValue(direction.get(),begin+block.rows[i],cbegin+block.columns[j],dense[i*nk+j],INSERT_VALUES));
        }
        EONSIM_PETSC(MatAssemblyBegin(direction.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(direction.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatMatMult(scaled.get(),direction.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,direction_action.put()));
        const double derivative=frobenius_product(comm,action.get(),direction_action.get());
        EONSIM_PETSC(MatNorm(direction_action.get(),NORM_FROBENIUS,&norm));
        const double curvature=norm*norm;
        check(comm,std::isfinite(derivative)&&std::isfinite(curvature),"nonfinite divergence-constrained energy");
        if(derivative>=0||curvature<=std::numeric_limits<double>::min()) break;
        const double alpha=-derivative/curvature;
        check(comm,std::isfinite(alpha)&&alpha>0,"invalid divergence-constrained energy step");
        EONSIM_PETSC(MatSetOption(transfer.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
        EONSIM_PETSC(MatAXPY(transfer.matrix.get(),alpha,direction.get(),DIFFERENT_NONZERO_PATTERN));
        EONSIM_PETSC(MatSetOption(transfer.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
        action=PetscOwner<Mat,MatDestroy>{};
        EONSIM_PETSC(MatMatMult(scaled.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,action.put()));
        EONSIM_PETSC(MatNorm(action.get(),NORM_FROBENIUS,&norm));
        transfer.stats.energy_after=norm*norm;++transfer.stats.divergence_updates;
        check(comm,transfer.stats.energy_after<=transfer.stats.energy_before*(1.+1e-10),
              "divergence-constrained interpolation increased energy");
    }
    PetscOwner<Mat,MatDestroy> after,change,delta;
    EONSIM_PETSC(MatMatMult(divergence.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,after.put()));
    EONSIM_PETSC(MatDuplicate(after.get(),MAT_COPY_VALUES,change.put()));
    EONSIM_PETSC(MatAXPY(change.get(),-1.,before.get(),DIFFERENT_NONZERO_PATTERN));
    PetscReal defect=0.,bnorm=0.,pnorm=0.;
    EONSIM_PETSC(MatNorm(change.get(),NORM_FROBENIUS,&defect));
    EONSIM_PETSC(MatNorm(divergence.get(),NORM_FROBENIUS,&bnorm));
    EONSIM_PETSC(MatNorm(initial.get(),NORM_FROBENIUS,&pnorm));
    transfer.stats.divergence_change=defect/std::max(1e-300,bnorm*pnorm);
    check(comm,std::isfinite(transfer.stats.divergence_change)&&transfer.stats.divergence_change<=1e-10,
          "interpolation energy change violated discrete divergence preservation");
    EONSIM_PETSC(MatDuplicate(transfer.matrix.get(),MAT_COPY_VALUES,delta.put()));
    EONSIM_PETSC(MatAXPY(delta.get(),-1.,initial.get(),DIFFERENT_NONZERO_PATTERN));
    EONSIM_PETSC(MatNorm(delta.get(),NORM_FROBENIUS,&norm));transfer.stats.divergence_update_norm=norm;
    transfer.stats.divergence_commuting_defect=pressure_projection_defect(after.get(),transfer);
    const double before_energy=transfer.stats.energy_before,after_energy=transfer.stats.energy_after;
    minimize_transfer_energy(comm,matrix,fine,transfer,0,true); // independent candidate-span audit
    transfer.stats.energy_before=before_energy;transfer.stats.energy_after=after_energy;
}

double pressure_projection_defect(Mat image,const Transfer& transfer) {
    // Pressure columns are a disjoint orthonormal basis. Measure the part of
    // B Pv outside their span independently of the coarse Galerkin identity.
    PetscInt cbegin=0,cend=0;
    EONSIM_PETSC(MatGetOwnershipRangeColumn(transfer.matrix.get(),&cbegin,&cend));
    PetscOwner<Mat,MatDestroy> pp,restricted,projected;
    PetscOwner<Vec,VecDestroy> coarse_mask;
    EONSIM_PETSC(MatCreateVecs(transfer.matrix.get(),coarse_mask.put(),nullptr));
    PetscScalar* mask=nullptr;EONSIM_PETSC(VecGetArray(coarse_mask.get(),&mask));
    for(PetscInt i=0;i<cend-cbegin;++i) mask[i]=(transfer.fixed_columns[i]&2)?1.:0.;
    EONSIM_PETSC(VecRestoreArray(coarse_mask.get(),&mask));
    EONSIM_PETSC(MatDuplicate(transfer.matrix.get(),MAT_COPY_VALUES,pp.put()));
    EONSIM_PETSC(MatDiagonalScale(pp.get(),nullptr,coarse_mask.get()));
    EONSIM_PETSC(MatTransposeMatMult(pp.get(),image,MAT_INITIAL_MATRIX,PETSC_DEFAULT,restricted.put()));
    EONSIM_PETSC(MatMatMult(pp.get(),restricted.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,projected.put()));
    EONSIM_PETSC(MatAXPY(projected.get(),-1.,image,DIFFERENT_NONZERO_PATTERN));
    PetscReal image_norm=0.,norm=0.;
    EONSIM_PETSC(MatNorm(image,NORM_FROBENIUS,&image_norm));
    EONSIM_PETSC(MatNorm(projected.get(),NORM_FROBENIUS,&norm));
    return image_norm==0.&&norm==0.?0.:norm/image_norm;
}

Transfer tentative_transfer(MPI_Comm comm,Mat matrix,const LevelData& fine,const Options& o,Vec physical_test_weights) {
    if(!o.distributed_aggregation) return local_tentative_transfer(comm,matrix,fine,o,physical_test_weights);
    auto moved=redistribute_mg_layout(comm,matrix,fine.semantics,fine.candidates,fine.trace,fine.active);
    LevelData local;
    local.semantics=std::move(moved.semantics);local.candidates=std::move(moved.candidates);
    local.trace=std::move(moved.trace);local.active=std::move(moved.active);local.origin_rank=std::move(moved.origin_rank);
    using Node=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
    std::map<Node,PetscInt> blocks;
    for(PetscInt row=0;row<static_cast<PetscInt>(local.semantics.size());++row) if(local.active[row]) {
        const auto& key=local.semantics[row];const Node node{key.entity,key.kind,key.mode,key.space};
        auto inserted=blocks.emplace(node,static_cast<PetscInt>(local.blocks.size()));
        if(inserted.second) local.blocks.push_back({});
        local.blocks[inserted.first->second].push_back(row);
    }
    PetscOwner<Vec,VecDestroy> weights;
    if(physical_test_weights) {
        EONSIM_PETSC(MatCreateVecs(moved.permutation.get(),weights.put(),nullptr));
        EONSIM_PETSC(MatMultTranspose(moved.permutation.get(),physical_test_weights,weights.get()));
    }
    auto result=local_tentative_transfer(comm,moved.matrix.get(),local,o,weights.get());
    result.stats.migrated_rows=moved.moved_rows;
    if(!result.matrix.get()) return result;
    if(!result.energy_completed) {
        minimize_transfer_energy(comm,moved.matrix.get(),local,result,o.energy_steps,o.saddle_point);
        result.energy_completed=true;
    }
    PetscOwner<Mat,MatDestroy> physical;
    EONSIM_PETSC(MatMatMult(moved.permutation.get(),result.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,physical.put()));
    // MatProduct retains operands; numeric refresh uses the resulting physical
    // transfer, so release this setup-only migration and tentative factor.
    EONSIM_PETSC(MatProductClear(physical.get()));
    result.matrix=std::move(physical);
    std::vector<unsigned char>().swap(result.anchors);
    std::vector<std::vector<PetscInt>>().swap(result.aggregate_rows);
    std::vector<std::pair<PetscInt,PetscInt>>().swap(result.aggregate_columns);
    return result;
}

void audit_pressure_pairs(MPI_Comm comm,Mat coarse,Transfer& transfer) {
    if(transfer.stats.pressure_supremizer_modes==0) return;
    double local_change=0.,local_minimum=std::numeric_limits<double>::infinity();
    bool valid=true;
    try {
        for(const auto& pair:transfer.pressure_pairs) {
            const auto count=pair.velocity_columns.size(),pressures=pair.pressure_columns.size();
            std::vector<PetscScalar> entries(pressures*count);
            EONSIM_PETSC(MatGetValues(coarse,static_cast<PetscInt>(pressures),pair.pressure_columns.data(),
                static_cast<PetscInt>(count),pair.velocity_columns.data(),entries.data()));
            std::vector<double> normalized(count*count);
            long double difference=0.,reference=0.;
            for(std::size_t i=0;i<count;++i) for(std::size_t j=0;j<count;++j) {
                long double value=0.;
                for(std::size_t k=0;k<pressures;++k)
                    value+=static_cast<long double>(pair.pressure_combinations[i][k])*entries[k*count+j]/pair.coupling_scale;
                const auto expected=pair.expected_coupling[i*count+j];
                difference+=(value-expected)*(value-expected);reference+=static_cast<long double>(expected)*expected;
                normalized[i*count+j]=static_cast<double>(value/pair.row_norms[i]);
                valid=valid&&std::isfinite(value)&&std::isfinite(normalized[i*count+j]);
            }
            valid=valid&&reference>0;
            const auto change=reference>0?static_cast<double>(std::sqrt(difference/reference)):std::numeric_limits<double>::infinity();
            const auto minimum=paired_minimum_singular(normalized,count);
            valid=valid&&std::isfinite(change)&&change<=1e-10&&std::isfinite(minimum)&&minimum>0;
            local_change=std::max(local_change,change);local_minimum=std::min(local_minimum,minimum);
        }
    } catch(const std::exception&) {valid=false;}
    check(comm,valid,"energy transfer changed a selected discrete pressure/velocity coarse pair");
    EONSIM_PETSC(MPI_Allreduce(&local_change,&transfer.stats.pressure_pair_relative_change,1,MPI_DOUBLE,MPI_MAX,comm));
    EONSIM_PETSC(MPI_Allreduce(&local_minimum,&transfer.stats.pressure_pair_min_singular,1,MPI_DOUBLE,MPI_MIN,comm));
}


struct Level {
    PetscLogEvent smooth_event=-1,restrict_event=-1,prolong_event=-1,coarse_event=-1,schur_event=-1;
    PetscOwner<Mat,MatDestroy> matrix,prolongation,restriction_form;
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
    PetscOwner<Mat,MatDestroy> source_reference,exact_fine;
    PetscOwner<Vec,VecDestroy> exact_input,adaptive_action;
    std::vector<std::array<double,2>> hierarchy_reference;
    // Exact B-only generation signature. The entry mask covers the fixed
    // pressure-row graph including numerical zeros; reference values include
    // every active primal column, local or remote. This is not a hash.
    std::vector<unsigned char> divergence_entries;
    std::vector<double> divergence_reference;
    PetscInt hierarchy_age=0;
    bool adaptation_pending=false,exact_is_shell=false;
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
        MatInfo fine_info{};EONSIM_PETSC(MatGetInfo(matrix,MAT_GLOBAL_SUM,&fine_info));
        const double fine_nnz=std::max(1.,static_cast<double>(fine_info.nz_used));
        double hierarchy_nnz=fine_nnz;
        double level_nnz=fine_info.nz_used;
        for(PetscInt depth=1;depth<configuration.max_levels;++depth) {
            PetscInt global=0; EONSIM_PETSC(MatGetSize(levels.back().matrix.get(),&global,nullptr));
            if(global<=configuration.coarse_limit) break;
            if(depth==1&&configuration.field_scaling&&(configuration.pressure_supremizers||
               configuration.divergence_preserving||configuration.pressure_image_modes))
                prepare_restriction_weights(levels.back());
            auto transfer=tentative_transfer(comm,levels.back().matrix.get(),levels.back().data,configuration,
                                             levels.back().restriction_weights.get());
            for(int retry=0;configuration.adaptive_hierarchy&&retry<2&&transfer.matrix.get()&&
                static_cast<double>(transfer.stats.coarse_rows)>configuration.max_coarse_ratio*global&&
                configuration.aggregate_nodes<128;++retry) {
                configuration.aggregate_nodes=std::min<PetscInt>(128,2*configuration.aggregate_nodes);
                transfer=tentative_transfer(comm,levels.back().matrix.get(),levels.back().data,configuration,
                    levels.back().restriction_weights.get());
            }
            if(!transfer.matrix.get()) break;
            if(static_cast<double>(transfer.stats.coarse_rows)>
               configuration.max_coarse_ratio*static_cast<double>(global)) {
                stats.weak_coarsening_stop_rows=global;
                stats.weak_coarsening_proposed_rows=transfer.stats.coarse_rows;
                break;
            }
            if(!transfer.energy_completed)
                minimize_transfer_energy(comm,levels.back().matrix.get(),levels.back().data,transfer,configuration.energy_steps,configuration.saddle_point);
            Level next;
            if(depth==1&&configuration.field_scaling) {
                // P interpolates scaled unknowns y, x=R*y. Retain the original
                // physical Galerkin test space R*P: Q^T=P^T*R*L^-1 and
                // Q^T*(L*A*R)*P=(R*P)^T*A*(R*P). Using plain P^T here would
                // change the test space whenever independent field row/column
                // scales differ, and can destroy mixed coarse stability.
                auto& parent=levels.back();
                prepare_restriction_weights(parent);
                EONSIM_PETSC(VecDuplicate(left_scale.get(),parent.restriction_input.put()));
                EONSIM_PETSC(MatDuplicate(parent.matrix.get(),MAT_COPY_VALUES,parent.restriction_form.put()));
                EONSIM_PETSC(MatDiagonalScale(parent.restriction_form.get(),parent.restriction_weights.get(),nullptr));
                EONSIM_PETSC(MatPtAP(parent.restriction_form.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,next.matrix.put()));
                if(!configuration.reuse_hierarchy) {
                    EONSIM_PETSC(MatProductClear(next.matrix.get()));
                    parent.restriction_form=PetscOwner<Mat,MatDestroy>{};
                }
            } else {
                EONSIM_PETSC(MatPtAP(levels.back().matrix.get(),transfer.matrix.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,next.matrix.put()));
            }
            MatInfo next_info{},transfer_info{};
            EONSIM_PETSC(MatGetInfo(next.matrix.get(),MAT_LOCAL,&next_info));
            EONSIM_PETSC(MatGetInfo(transfer.matrix.get(),MAT_LOCAL,&transfer_info));
            const double local_nnz[]={next_info.nz_used,transfer_info.nz_used};
            double global_nnz[2]{};
            EONSIM_PETSC(MPI_Allreduce(local_nnz,global_nnz,2,MPI_DOUBLE,MPI_SUM,comm));
            const double proposed=hierarchy_nnz+global_nnz[0];
            if(configuration.adaptive_hierarchy&&proposed>configuration.maximum_complexity*fine_nnz) {
                stats.complexity_stop_rows=global;break;
            }
            hierarchy_nnz=proposed;stats.operator_complexity=hierarchy_nnz/fine_nnz;
            stats.interpolation_complexity+=global_nnz[1]/fine_nnz;
            transfer.stats.operator_nnz=level_nnz;
            transfer.stats.coarse_operator_nnz=level_nnz=global_nnz[0];
            transfer.stats.interpolation_nnz=global_nnz[1];
            audit_pressure_pairs(comm,next.matrix.get(),transfer);
            levels.back().prolongation=std::move(transfer.matrix);
            next.data=std::move(transfer.coarse); stats.transfers.push_back(transfer.stats);
            levels.push_back(std::move(next));
        }
        stats.levels=static_cast<PetscInt>(levels.size()); stats.single_precision=configuration.single_precision;
        stats.native_fp32=configuration.native_fp32;stats.field_scaling=configuration.field_scaling;
        stats.fsi_candidates=configuration.fsi_candidates;stats.w_cycle=configuration.w_cycle;stats.k_cycle=configuration.k_cycle;
        stats.pressure_supremizers=configuration.pressure_supremizers;
        stats.saddle_point=configuration.saddle_point;stats.divergence_preserving=configuration.divergence_preserving;stats.divergence_commuting=configuration.divergence_commuting;
        stats.distributed_aggregation=configuration.distributed_aggregation;
        stats.adaptive_hierarchy=configuration.adaptive_hierarchy;stats.reuse_hierarchy=configuration.reuse_hierarchy;
        stats.matrix_free_fine=configuration.matrix_free_fine;
        for(std::size_t level=0;level<levels.size();++level) {
            auto& data=levels[level];
            if(configuration.profile_levels) {
                const std::string name="FSI_L"+std::to_string(level)+"_";
                auto register_event=[&](const char* suffix,PetscLogEvent& event) {
                    EONSIM_PETSC(PetscLogEventRegister((name+suffix).c_str(),PC_CLASSID,&event));
                };
                if(level+1==levels.size()) register_event("Coarse",data.coarse_event);
                else {
                    register_event("Smooth",data.smooth_event);
                    register_event("Schur",data.schur_event);
                    register_event("Restrict",data.restrict_event);
                    register_event("Prolong",data.prolong_event);
                }
            }
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
                smoother_options.schur_event=data.schur_event;
                // A coarse semantic entity is already a complete mixed
                // aggregate basis, including its spectral columns. Growing it
                // through a filled Galerkin graph can turn a bounded patch into
                // most of the level. Keep whole aggregate blocks by default;
                // inter-aggregate couplings remain in every full level matvec.
                if(level>0) smoother_options.patches.overlap=configuration.coarse_patch_overlap;
                data.smoother=make_fsi_level_smoother(comm,data.matrix.get(),data.data.semantics,data.data.trace,smoother_options);
                if(configuration.single_precision) {
                    if(level>0||!configuration.matrix_free_fine) data.float_matrix.update(data.matrix.get());
                    data.float_transfer.update(data.prolongation.get());
                    stats.fp32_value_bytes+=(data.float_matrix.values.size()+data.float_transfer.values.size())*sizeof(float);
                }
            }
        }
        if(configuration.matrix_free_fine) EONSIM_PETSC(VecDuplicate(levels.front().rhs.get(),exact_input.put()));
        if(configuration.adaptive_hierarchy) EONSIM_PETSC(VecDuplicate(levels.front().rhs.get(),adaptive_action.put()));
        if(configuration.reuse_hierarchy) {
            hierarchy_reference=numeric_signature(matrix);
            if(configuration.divergence_commuting) prepare_divergence_reference(matrix);
        }
        configure_coarse();
        update_storage_stats();
        if(configuration.native_fp32) release_native_setup();
        EONSIM_PETSC(MatGetState(matrix,&numeric_state));
        ready=true; stats.refreshes=1; stats.hierarchy_rebuilds=1;
        if(emit_report) report();
    }
    std::vector<std::array<double,2>> numeric_signature(Mat matrix) const {
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        std::vector<std::array<double,2>> signature(end-begin);
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
            long double norm=0.;
            for(PetscInt j=0;j<count;++j) {norm+=std::abs(static_cast<long double>(values[j]));if(columns[j]==row) signature[row-begin][0]=values[j];}
            signature[row-begin][1]=static_cast<double>(norm);
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
        }
        return signature;
    }
    void prepare_divergence_reference(Mat matrix) {
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        const auto& data=levels.front().data;
        std::vector<PetscInt> columns;
        for(PetscInt row=begin;row<end;++row) if(data.active[row-begin]&&is_pressure(data.semantics[row-begin])) {
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&values));
            if(count) columns.insert(columns.end(),indices,indices+count);
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&values));
        }
        std::sort(columns.begin(),columns.end());columns.erase(std::unique(columns.begin(),columns.end()),columns.end());
        PetscOwner<Vec,VecDestroy> mask,halo;
        EONSIM_PETSC(MatCreateVecs(matrix,mask.put(),nullptr));
        PetscScalar* entries=nullptr;EONSIM_PETSC(VecGetArray(mask.get(),&entries));
        for(PetscInt i=0;i<end-begin;++i) entries[i]=data.active[i]&&!is_pressure(data.semantics[i])?1.:0.;
        EONSIM_PETSC(VecRestoreArray(mask.get(),&entries));
        EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),halo.put()));
        PetscOwner<IS,ISDestroy> selected;
        EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),columns.data(),PETSC_COPY_VALUES,selected.put()));
        PetscOwner<VecScatter,VecScatterDestroy> scatter;
        EONSIM_PETSC(VecScatterCreate(mask.get(),selected.get(),halo.get(),nullptr,scatter.put()));
        EONSIM_PETSC(VecScatterBegin(scatter.get(),mask.get(),halo.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),mask.get(),halo.get(),INSERT_VALUES,SCATTER_FORWARD));
        const PetscScalar* flags=nullptr;EONSIM_PETSC(VecGetArrayRead(halo.get(),&flags));
        divergence_entries.clear();divergence_reference.clear();
        for(PetscInt row=begin;row<end;++row) if(data.active[row-begin]&&is_pressure(data.semantics[row-begin])) {
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&values));
            for(PetscInt j=0;j<count;++j) {
                const auto slot=std::lower_bound(columns.begin(),columns.end(),indices[j])-columns.begin();
                const bool primal=flags[slot]!=0.;divergence_entries.push_back(primal);
                if(primal) divergence_reference.push_back(values[j]);
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&values));
        }
        EONSIM_PETSC(VecRestoreArrayRead(halo.get(),&flags));
    }
    bool unchanged_divergence(Mat matrix) const {
        PetscInt begin=0,end=0;EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        const auto& data=levels.front().data;
        std::size_t entry=0,value=0;bool same=true;
        for(PetscInt row=begin;row<end;++row) if(data.active[row-begin]&&is_pressure(data.semantics[row-begin])) {
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&values));
            for(PetscInt j=0;j<count;++j,++entry) {
                if(entry>=divergence_entries.size()) {same=false;continue;}
                if(divergence_entries[entry]) {
                    same=same&&value<divergence_reference.size()&&values[j]==divergence_reference[value];++value;
                }
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&values));
        }
        same=same&&entry==divergence_entries.size()&&value==divergence_reference.size();
        int changed=!same,any=0;EONSIM_PETSC(MPI_Allreduce(&changed,&any,1,MPI_INT,MPI_MAX,comm));return any==0;
    }
    double signature_drift(Mat matrix) const {
        const auto current=numeric_signature(matrix);double local=0.,global=0.;
        for(std::size_t i=0;i<current.size();++i) for(int k=0;k<2;++k) {
            const auto denominator=std::max({std::abs(current[i][k]),std::abs(hierarchy_reference[i][k]),
                current[i][1]*64.*std::numeric_limits<double>::epsilon(),std::numeric_limits<double>::min()});
            local=std::max(local,std::abs(current[i][k]-hierarchy_reference[i][k])/denominator);
        }
        EONSIM_PETSC(MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_MAX,comm));return global;
    }
    void bind_exact(Mat matrix) {
        PetscInt m=0,n=0,lm=0,ln=0,expected_m=0,expected_n=0,expected_lm=0,expected_ln=0;
        EONSIM_PETSC(MatGetSize(matrix,&m,&n));EONSIM_PETSC(MatGetLocalSize(matrix,&lm,&ln));
        EONSIM_PETSC(MatGetSize(source_reference.get(),&expected_m,&expected_n));
        EONSIM_PETSC(MatGetLocalSize(source_reference.get(),&expected_lm,&expected_ln));
        check(comm,m==expected_m&&n==expected_n&&lm==expected_lm&&ln==expected_ln,
              "exact fine operator has incompatible ownership or dimensions");
        PetscBool shell=PETSC_FALSE;
        EONSIM_PETSC(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(matrix),MATSHELL,&shell));
        exact_is_shell=shell;
        if(matrix!=exact_fine.get()) {
            EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(matrix)));
            PetscOwner<Mat,MatDestroy> replacement;*replacement.put()=matrix;exact_fine=std::move(replacement);
        }
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
    void prepare_restriction_weights(Level& parent) {
        if(parent.restriction_weights.get()) return;
        EONSIM_PETSC(VecDuplicate(left_scale.get(),parent.restriction_weights.put()));
        EONSIM_PETSC(VecPointwiseDivide(parent.restriction_weights.get(),right_scale.get(),left_scale.get()));
        const PetscScalar* weights=nullptr;bool valid=true;
        EONSIM_PETSC(VecGetArrayRead(parent.restriction_weights.get(),&weights));
        for(std::size_t row=0;row<parent.data.active.size();++row)
            valid=valid&&weights[row]>0&&std::isfinite(weights[row]);
        EONSIM_PETSC(VecRestoreArrayRead(parent.restriction_weights.get(),&weights));
        check(comm,valid,"physical restriction weights are outside representable precision");
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
        PetscInt rows=0;
        EONSIM_PETSC(MatGetSize(levels.back().matrix.get(),&rows,nullptr));
        const auto requested=configuration.coarse_processes==0?static_cast<PetscInt>(size):
            std::min<PetscInt>(size,configuration.coarse_processes);
        PetscInt target=requested;
        if(configuration.coarse_rows_per_rank) {
            // Avoid a single rank on a nontrivial distributed coarse problem.
            // Use the smallest admissible communicator meeting the load target.
            const auto budget=configuration.coarse_rows_per_rank;
            const auto minimum=rows==1?1:std::min<PetscInt>(size,std::max<PetscInt>(2,1+(rows-1)/budget));
            target=minimum;
            while(size%target!=0) ++target;
        } else {
            while(target>1&&size%target!=0) --target;
        }
        stats.coarse_processes=target;
        EONSIM_PETSC(KSPCreate(comm,coarse.put()));
        const auto coarse_prefix=prefix+"monolithic_mg_coarse_";
        const auto prefer_pivoted_local_lu=[&](const std::string& sub_prefix) {
            const auto solver_option="-"+sub_prefix+"pc_factor_mat_solver_type";
            PetscBool explicit_solver=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,solver_option.c_str(),&explicit_solver));
            char local_pc[32]="lu";
            EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+sub_prefix+"pc_type").c_str(),local_pc,sizeof(local_pc),nullptr));
            // ASM's matrices are sequential even when the coarse operator is
            // distributed. PETSc's native sparse LU has no numerical row
            // pivoting and can reject a nonsingular saddle block. Select the
            // available pivoted backend, never a shift or a smaller pivot gate.
            PetscOwner<Mat,MatDestroy> probe;
            EONSIM_PETSC(MatCreateSeqAIJ(PETSC_COMM_SELF,1,1,1,nullptr,probe.put()));
            PetscBool available=PETSC_FALSE;
            EONSIM_PETSC(MatGetFactorAvailable(probe.get(),MATSOLVERMUMPS,MAT_FACTOR_LU,&available));
            int local=available?1:0,all=0;
            EONSIM_PETSC(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm));
            // Keep this collective unconditional: PETSc options can differ
            // by rank even when the hierarchy itself is collective.
            if(all&&!explicit_solver&&std::strcmp(local_pc,"lu")==0)
                option_default(solver_option,"mumps");
        };
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
            if(target>1) prefer_pivoted_local_lu(coarse_prefix+"telescope_sub_");
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
            prefer_pivoted_local_lu(coarse_prefix+"sub_");
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
        PetscInt coarse_rows=0;
        EONSIM_PETSC(MatGetSize(levels.back().matrix.get(),&coarse_rows,nullptr));
        EONSIM_PETSC(PetscPrintf(comm,
            "pc_monolithic_mg prefix=%s levels=%" PetscInt_FMT " coarse_processes=%" PetscInt_FMT
            " single_precision=%d refreshes=%" PetscInt_FMT " hierarchy_rebuilds=%" PetscInt_FMT
            " smoother=%s field_scaling=%d fsi_candidates=%d native_fp32=%d cycle=%s"
            " max_coarse_ratio=%.17g weak_coarsening_stop_rows=%" PetscInt_FMT
            " weak_coarsening_proposed_rows=%" PetscInt_FMT " pressure_supremizers=%d"
            " saddle_point=%d divergence_preserving=%d divergence_commuting=%d distributed_aggregation=%d adaptive_hierarchy=%d"
            " reuse_hierarchy=%d matrix_free_fine=%d communication_avoiding=%d"
            " operator_complexity=%.17g interpolation_complexity=%.17g complexity_stop_rows=%" PetscInt_FMT
            " transfer_setup_generation=%" PetscInt_FMT
            " pressure_image_modes=%" PetscInt_FMT " coarse_rows_per_rank=%" PetscInt_FMT
            " coarsest_rows=%" PetscInt_FMT "\n",
            prefix.empty()?"-":prefix.c_str(),stats.levels,stats.coarse_processes,
            stats.single_precision?1:0,stats.refreshes,stats.hierarchy_rebuilds,configuration.smoother.kind.c_str(),
            stats.field_scaling?1:0,stats.fsi_candidates?1:0,stats.native_fp32?1:0,stats.k_cycle?"k":stats.w_cycle?"w":"v",
            configuration.max_coarse_ratio,stats.weak_coarsening_stop_rows,stats.weak_coarsening_proposed_rows,
            stats.pressure_supremizers?1:0,stats.saddle_point?1:0,stats.divergence_preserving?1:0,stats.divergence_commuting?1:0,
            stats.distributed_aggregation?1:0,stats.adaptive_hierarchy?1:0,stats.reuse_hierarchy?1:0,
            stats.matrix_free_fine?1:0,configuration.communication_avoiding?1:0,stats.operator_complexity,
            stats.interpolation_complexity,
            stats.complexity_stop_rows,stats.hierarchy_rebuilds,configuration.pressure_image_modes,
            configuration.coarse_rows_per_rank,coarse_rows));
        for(std::size_t i=0;i<stats.transfers.size();++i) {
            const auto& level=stats.transfers[i];
            EONSIM_PETSC(PetscPrintf(comm,
                "pc_monolithic_mg_level level=%zu rows=%" PetscInt_FMT " coarse_rows=%" PetscInt_FMT
                " spectral_modes=%" PetscInt_FMT " reproduction_error=%.17g energy_before=%.17g energy_after=%.17g"
                " pressure_supremizer_modes=%" PetscInt_FMT " pressure_paired_aggregates=%" PetscInt_FMT
                " pressure_pair_min_singular=%.17g pressure_pair_relative_change=%.17g"
                " pressure_rows=%" PetscInt_FMT " coarse_pressure_rows=%" PetscInt_FMT
                " distributed_aggregates=%" PetscInt_FMT " migrated_rows=%" PetscInt_FMT
                " divergence_constraints=%" PetscInt_FMT " divergence_nullity=%" PetscInt_FMT
                " divergence_updates=%" PetscInt_FMT " divergence_change=%.17g divergence_update_norm=%.17g"
                " divergence_commuting_defect=%.17g compatible_pressure_modes=%" PetscInt_FMT
                " saturated_pressure_aggregates=%" PetscInt_FMT
                " operator_nnz=%.0f coarse_operator_nnz=%.0f interpolation_nnz=%.0f\n",
                i,level.rows,level.coarse_rows,level.spectral_modes,level.reproduction_error,level.energy_before,level.energy_after,
                level.pressure_supremizer_modes,level.pressure_paired_aggregates,
                level.pressure_pair_min_singular,level.pressure_pair_relative_change,
                level.pressure_rows,level.coarse_pressure_rows,level.distributed_aggregates,level.migrated_rows,
                level.divergence_constraints,level.divergence_nullity,level.divergence_updates,
                level.divergence_change,level.divergence_update_norm,level.divergence_commuting_defect,
                level.compatible_pressure_modes,level.saturated_pressure_aggregates,
                level.operator_nnz,level.coarse_operator_nnz,level.interpolation_nnz));
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
                " native_index_bytes=%zu primal_rows=%" PetscInt_FMT " pressure_rows=%" PetscInt_FMT
                " schur_iterations=%" PetscInt_FMT " schur_budget=%" PetscInt_FMT " schur_applications=%" PetscInt_FMT
                " colors=%" PetscInt_FMT " color_stages=%" PetscInt_FMT " residual_products=%" PetscInt_FMT "\n",
                rank,i,smoother.patches.patches,smoother.patches.overlap,smoother.patches.largest_patch,
                smoother.patches.patch_rows,smoother.patches.covered_owned_rows,smoother.patches.interface_patches,
                smoother.patches.factor_batches,smoother.patches.numeric_factorizations,
                smoother.patches.cached_factorizations,smoother.patches.fp32_patches,
                smoother.polynomial_degree,smoother.eigenvalue_upper,smoother.patches.expanded_patches,
                smoother.patches.core_patches,smoother.patches.retained_fp64_matrix_bytes,smoother.patches.fp32_matrix_bytes,
                smoother.patches.factor_bytes,smoother.patches.native_sparse_patches,smoother.patches.native_dense_patches,
                smoother.patches.native_index_bytes,smoother.primal_rows,smoother.pressure_rows,
                smoother.schur_iterations,smoother.schur_budget,smoother.schur_applications,smoother.patches.colors,
                smoother.patches.color_stages,smoother.patches.residual_products));
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
        bool reusable=false,unchanged_coupling_reuse=false,divergence_rebuild=false;
        bool drift_rebuild=false,age_rebuild=false;
        if(configuration.reuse_hierarchy&&changed) {
            stats.hierarchy_numeric_drift=signature_drift(matrix);
            drift_rebuild=stats.hierarchy_numeric_drift>configuration.hierarchy_drift;
            age_rebuild=hierarchy_age>=configuration.hierarchy_max_age;
            reusable=!age_rebuild&&!drift_rebuild&&!adaptation_pending;
            if(configuration.divergence_commuting) {
                bool full_pressure_span=true;
                for(const auto& level:stats.transfers)
                    full_pressure_span=full_pressure_span&&level.pressure_rows==level.coarse_pressure_rows;
                if(!full_pressure_span) {
                    // With fixed L/R and typed block-diagonal transfers,
                    // unchanged fine B implies every Galerkin B is unchanged.
                    // Exact comparison includes all remote primal couplings;
                    // diagonal F/C changes alone do not invalidate closure.
                    const bool same_B=unchanged_divergence(matrix);
                    unchanged_coupling_reuse=reusable&&same_B;
                    divergence_rebuild=!same_B;
                    reusable=reusable&&same_B;
                }
            }
        }
        const bool periodic=configuration.spectral_refresh_period>0&&stats.refreshes%configuration.spectral_refresh_period==0;
        const bool must_rebuild=adaptation_pending||periodic||
            (changed&&((configuration.reuse_hierarchy&&!reusable)||
             (!reusable&&(configuration.native_fp32||configuration.field_scaling||configuration.smoother.patches.adaptive||
                          configuration.pressure_supremizers||configuration.divergence_preserving))));
        if(must_rebuild) {
            const bool adapted=adaptation_pending;
            if(adapted) {
                configuration.energy_steps=std::min<PetscInt>(3,configuration.energy_steps+1);
                configuration.spectral_modes=std::min<PetscInt>(8,configuration.spectral_modes+1);
            }
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
            rebuilt.stats.matrix_free_fine_actions=stats.matrix_free_fine_actions;
            rebuilt.stats.fine_bootstrap_actions=stats.fine_bootstrap_actions;
            rebuilt.stats.hierarchy_reuses=stats.hierarchy_reuses;
            rebuilt.stats.divergence_rebuilds=stats.divergence_rebuilds+(divergence_rebuild?1:0);
            rebuilt.stats.drift_rebuilds=stats.drift_rebuilds+(drift_rebuild?1:0);
            rebuilt.stats.age_rebuilds=stats.age_rebuilds+(age_rebuild?1:0);
            rebuilt.stats.unchanged_divergence_reuses=stats.unchanged_divergence_reuses;
            rebuilt.stats.symbolic_reuses=stats.symbolic_reuses;
            rebuilt.stats.adaptive_rebuilds=stats.adaptive_rebuilds+(adapted?1:0);
            rebuilt.stats.adaptive_probes=stats.adaptive_probes;
            rebuilt.stats.batched_reduction_groups=stats.batched_reduction_groups;
            rebuilt.stats.adaptive_residual_ratio=stats.adaptive_residual_ratio;
            rebuilt.stats.hierarchy_numeric_drift=stats.hierarchy_numeric_drift;
            rebuilt.stats.refreshes=stats.refreshes+1;
            rebuilt.stats.hierarchy_rebuilds=stats.hierarchy_rebuilds+1;
            coarse=std::move(rebuilt.coarse); levels=std::move(rebuilt.levels); stats=std::move(rebuilt.stats);
            left_scale=std::move(rebuilt.left_scale);right_scale=std::move(rebuilt.right_scale);
            scaled_input=std::move(rebuilt.scaled_input);scaled_output=std::move(rebuilt.scaled_output);
            hierarchy_reference=std::move(rebuilt.hierarchy_reference);
            divergence_entries=std::move(rebuilt.divergence_entries);divergence_reference=std::move(rebuilt.divergence_reference);
            configuration=rebuilt.configuration;hierarchy_age=0;adaptation_pending=false;
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
        if(changed&&configuration.field_scaling) {
            EONSIM_PETSC(MatCopy(matrix,levels.front().matrix.get(),SAME_NONZERO_PATTERN));
            EONSIM_PETSC(MatDiagonalScale(levels.front().matrix.get(),left_scale.get(),right_scale.get()));
            if(levels.front().restriction_form.get()) {
                EONSIM_PETSC(MatCopy(levels.front().matrix.get(),levels.front().restriction_form.get(),SAME_NONZERO_PATTERN));
                EONSIM_PETSC(MatDiagonalScale(levels.front().restriction_form.get(),levels.front().restriction_weights.get(),nullptr));
            }
        }
        for(std::size_t i=0;i+1<levels.size();++i) {
            // Re-evaluating an unchanged distributed PtAP can reorder sums at
            // deeper levels. Avoid both that roundoff churn and needless exact
            // factor-cache misses by retaining a truly unchanged generation.
            if(changed) {
                Mat next=levels[i+1].matrix.get();
                Mat form=levels[i].restriction_form.get()?levels[i].restriction_form.get():levels[i].matrix.get();
                EONSIM_PETSC(MatPtAP(form,levels[i].prolongation.get(),MAT_REUSE_MATRIX,PETSC_DEFAULT,&next));
                ++stats.symbolic_reuses;
                if(configuration.k_cycle&&i>0) update_krylov_scale(levels[i]);
            }
            refresh_fsi_level_smoother(levels[i].smoother,levels[i].matrix.get());
            if(changed&&configuration.single_precision&&(i>0||!configuration.matrix_free_fine))
                levels[i].float_matrix.update(levels[i].matrix.get());
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
        if(reusable) {++stats.hierarchy_reuses;++hierarchy_age;
            if(unchanged_coupling_reuse) ++stats.unchanged_divergence_reuses;
        }
        numeric_state=current_numeric_state; ready=true; ++stats.refreshes;
    }
    PetscErrorCode multiply(std::size_t level,Vec x,Vec y) {
        PetscFunctionBeginUser;
        if(level==0&&configuration.matrix_free_fine) {
            if(!exact_fine.get()) PetscFunctionReturn(PETSC_ERR_ARG_WRONGSTATE);
            if(configuration.field_scaling) {
                PetscCall(VecPointwiseMult(exact_input.get(),right_scale.get(),x));
                PetscCall(MatMult(exact_fine.get(),exact_input.get(),y));
                PetscCall(VecPointwiseMult(y,left_scale.get(),y));
            } else PetscCall(MatMult(exact_fine.get(),x,y));
            if(exact_is_shell) ++stats.matrix_free_fine_actions;
            else ++stats.fine_bootstrap_actions;
        } else if(configuration.single_precision&&level+1<levels.size()) PetscCall(levels[level].float_matrix.multiply(x,y,false));
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
        const auto error=profile_fsi_operation(level.smooth_event,[&]{
            return apply_fsi_level_smoother(level.smoother,level.residual.get(),level.correction.get());
        });
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
        PetscReal rhs_norm=0.,first_norm=0.;
        if(configuration.communication_avoiding) {
            PetscCall(multiply(index,level.solution.get(),level.first_action.get()));
            PetscCall(VecPointwiseMult(level.first_action.get(),level.krylov_scale.get(),level.first_action.get()));
            // Both local norm contributions are ready before Begin. End both
            // requests before any failure branch; PETSc combines their MPI
            // reduction without a cancellation-prone Gram/norm identity.
            PetscCall(VecNormBegin(level.metric_residual.get(),NORM_2,&rhs_norm));
            PetscCall(VecNormBegin(level.first_action.get(),NORM_2,&first_norm));
            PetscCall(VecNormEnd(level.metric_residual.get(),NORM_2,&rhs_norm));
            PetscCall(VecNormEnd(level.first_action.get(),NORM_2,&first_norm));
            stats.coarse_krylov_reductions+=2;++stats.batched_reduction_groups;
        } else {
            PetscCall(krylov_norm(level.metric_residual.get(),&rhs_norm));
            if(std::isfinite(rhs_norm)&&rhs_norm>0) {
                PetscCall(multiply(index,level.solution.get(),level.first_action.get()));
                PetscCall(VecPointwiseMult(level.first_action.get(),level.krylov_scale.get(),level.first_action.get()));
                PetscCall(krylov_norm(level.first_action.get(),&first_norm));
            }
        }
        if(!std::isfinite(rhs_norm)) {
            valid=false;PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);
        }
        if(rhs_norm==0.) {PetscCall(VecSet(level.solution.get(),0.));PetscFunctionReturn(PETSC_SUCCESS);}
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
            const auto error=profile_fsi_operation(level.coarse_event,[&]{return KSPSolve(coarse.get(),rhs,solution);});
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
        PetscCall(profile_fsi_operation(level.restrict_event,[&]{
            if(configuration.single_precision) return level.float_transfer.multiply(restriction_input,coarse_level.rhs.get(),true);
            return MatMultTranspose(level.prolongation.get(),restriction_input,coarse_level.rhs.get());
        }));
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
        PetscCall(profile_fsi_operation(level.prolong_event,[&]{
            if(configuration.single_precision) return level.float_transfer.multiply(coarse_level.solution.get(),level.correction.get(),false);
            return MatMult(level.prolongation.get(),coarse_level.solution.get(),level.correction.get());
        }));
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
        if(!ready||(configuration.matrix_free_fine&&!exact_fine.get())) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        bool valid=true;
        if(configuration.field_scaling) {
            PetscCall(VecPointwiseMult(scaled_input.get(),left_scale.get(),input));
            PetscCall(cycle(0,scaled_input.get(),scaled_output.get(),valid));
            PetscCall(VecPointwiseMult(output,right_scale.get(),scaled_output.get()));
        } else PetscCall(cycle(0,input,output,valid));
        if(configuration.adaptive_hierarchy&&(stats.applications+1)%configuration.adaptive_interval==0) {
            if(configuration.matrix_free_fine) PetscCall(MatMult(exact_fine.get(),output,adaptive_action.get()));
            else PetscCall(MatMult(source_reference.get(),output,adaptive_action.get()));
            PetscCall(VecAYPX(adaptive_action.get(),-1.,input));
            PetscReal rn=0.,bn=0.;
            if(configuration.communication_avoiding) {
                PetscCall(VecNormBegin(adaptive_action.get(),NORM_2,&rn));
                PetscCall(VecNormBegin(input,NORM_2,&bn));
                PetscCall(VecNormEnd(adaptive_action.get(),NORM_2,&rn));
                PetscCall(VecNormEnd(input,NORM_2,&bn));
                ++stats.batched_reduction_groups;
            } else {PetscCall(VecNorm(adaptive_action.get(),NORM_2,&rn));PetscCall(VecNorm(input,NORM_2,&bn));}
            const double ratio=bn>0?rn/bn:0.;
            stats.adaptive_residual_ratio=ratio;++stats.adaptive_probes;
            if(!std::isfinite(ratio)) valid=false;
            else if(ratio>configuration.adaptive_threshold) adaptation_pending=true;
        }
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
bool set_monolithic_fsi_mg_fine_operator(PC pc,Mat exact_operator) {
    auto* state=hierarchy_handle(pc);
    if(!state||!(*state)->configuration.matrix_free_fine) return false;
    (*state)->bind_exact(exact_operator);return true;
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
