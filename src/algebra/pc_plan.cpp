#include "eonsim/pc_plan.hpp"
#include "eonsim/coupled_velocity_pc.hpp"
#include "eonsim/rcr_port_pc.hpp"
#include "eonsim/pressure_schur_pc.hpp"
#include "eonsim/interface_patch_pc.hpp"
#include "eonsim/schur_solver.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <memory>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool good,const std::string& message) {
    int bad=!good,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("PC plan validation communication failed");
    if(any) throw std::runtime_error("PC plan: "+message);
}
using D=DofDomain; using Q=DofQuantity;
struct Spec {
    std::string name; int select; bool schur; std::vector<Spec> children;
    Spec(std::string n,int s,bool h=false,std::vector<Spec> c={}):
        name(std::move(n)),select(s),schur(h),children(std::move(c)) {}
};
bool selected(const DofKey& key,int choice) {
    switch(choice) {
    case 0:return true;
    case 1:return key.domain==D::fluid;
    case 2:return key.domain==D::solid;
    case 3:return key.domain==D::mesh;
    case 4:return key.quantity==Q::velocity;
    case 5:return key.quantity==Q::pressure;
    case 6:return key.quantity==Q::velocity||key.quantity==Q::pressure;
    }
    return false;
}
PcBlock build(MPI_Comm comm,const AlgebraLayout& layout,const Spec& spec,
              const std::vector<PetscInt>& roots,const std::vector<PetscInt>& parent_rows) {
    PcBlock node; node.name=spec.name; node.schur=spec.schur;
    node.root_rows=roots; node.parent_rows=parent_rows;
    PetscInt count=roots.size(); int rank=0; MPI_Comm_rank(comm,&rank);
    if(MPI_Exscan(&count,&node.begin,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS ||
       MPI_Allreduce(&count,&node.global,1,MPIU_INT,MPI_SUM,comm)!=MPI_SUCCESS)
        throw std::runtime_error("PC plan count communication failed");
    if(rank==0) node.begin=0;
    if(spec.name=="root") common_check(comm,node.begin==layout.begin&&node.global==layout.global,
        "root ownership is inconsistent with distributed counts");
    if(node.global==0) throw std::runtime_error("PC plan globally empty block: "+spec.name);
    if(spec.children.empty()) return node;
    std::vector<int> hits(roots.size(),0);
    for(const auto& child:spec.children) {
        std::vector<PetscInt> subroots,indices;
        for(std::size_t i=0;i<roots.size();++i) if(selected(layout.owned_semantics.at(roots[i]-layout.begin),child.select)) {
            ++hits[i]; subroots.push_back(roots[i]); indices.push_back(node.begin+i);
        }
        node.children.push_back(build(comm,layout,child,subroots,indices));
    }
    common_check(comm,std::all_of(hits.begin(),hits.end(),[](int n){return n==1;}),
                 "children must cover parent exactly once at "+spec.name);
    return node;
}
void option_default(const std::string& name,const char* value) {
    PetscBool found=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
// Options select topology collectively, before creating any nested PETSc objects.
int velocity_solver_requested(MPI_Comm comm) {
    char value[32]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_velocity_solver",value,sizeof(value),&set));
    const std::string name=set?value:"split";
    int local=name=="split"?1:name=="coupled"?2:name=="twolevel"?3:name=="gamg"?4:name=="aggregate"?5:name=="boomeramg"?6:name=="field_amg"?7:0,lo=0,hi=0;
    MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm);
    MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"velocity solver must be split, coupled, twolevel, gamg, aggregate, boomeramg or field_amg and identical on every rank");
    return local;
}
bool rigid_velocity_modes_requested(MPI_Comm comm,int velocity_solver) {
    char value[32]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_velocity_coarse_space",value,sizeof(value),&set));
    const std::string name=set?value:"constants";
    int local=name=="constants"?1:name=="rigid"?2:0,lo=0,hi=0;
    MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm);
    MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"velocity coarse space must be constants or rigid and identical on every rank");
    common_check(comm,!set||velocity_solver==3||velocity_solver==4||velocity_solver==5||velocity_solver==6||velocity_solver==7,
                 "velocity coarse space requires the twolevel, gamg, aggregate or boomeramg velocity solver");
    common_check(comm,local!=2||velocity_solver==3||velocity_solver==5||velocity_solver==7,
                 "rigid velocity coarse space requires twolevel or aggregate; scalar GAMG supports constants only");
    return local==2;
}
int pressure_schur_requested(MPI_Comm comm) {
    char value[32]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_schur_approx",value,sizeof(value),&set));
    const std::string name=set?value:"diagonal";
    int local=name=="diagonal"?1:name=="nodal"?2:name=="lsc"?3:name=="bfbt"?4:name=="pcd"?5:0,lo=0,hi=0;
    MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm);
    MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"Schur approximation must be diagonal, nodal, lsc, bfbt or pcd and identical on every rank");
    return local;
}
bool nodal_structure_requested(MPI_Comm comm,bool added_mass) {
    char value[32]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_structure_approx",value,sizeof(value),&set));
    const std::string name=set?value:"a11";
    int local=name=="a11"?1:name=="nodal"?2:0,lo=0,hi=0;
    MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm);
    MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"structure approximation must be a11 or nodal and identical on every rank");
    common_check(comm,!set||added_mass,"structure approximation option requires the added_mass recipe");
    return local==2;
}
// Canonical node ownership keeps all active components of a group on one rank.
// Domain/kind/space/mode distinguish different entities sharing a numeric ID.
void decorate(MPI_Comm comm,const AlgebraLayout& layout,PcBlock& node,int velocity_solver,int pressure_approx,bool nodal_structure,bool rigid_modes) {
    const bool nodal=pressure_approx==2;
    // The pressure approximation uses velocity groups. The structural
    // approximation below has its own mixed fluid groups and separate option.
    node.nodal_schur=node.schur&&nodal&&node.children.at(1).name=="pressure";
    if(node.schur&&pressure_approx>=3&&node.children.at(1).name=="pressure") node.pressure_schur=pressure_approx;
    if(node.name=="velocity") {
        node.coupled_velocity=velocity_solver!=1&&node.children.empty();
        node.twolevel_velocity=(velocity_solver==3||velocity_solver==5)&&node.children.empty();
        node.gamg_velocity=velocity_solver==4&&node.children.empty();
        node.boomeramg_velocity=velocity_solver==6&&node.children.empty();
        node.field_amg_velocity=velocity_solver==7&&node.children.empty();
        PetscInt aggregate_nodes=16; PetscBool aggregate_set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-pc_plan_velocity_aggregate_nodes",&aggregate_nodes,&aggregate_set));
        PetscInt minimum=0,maximum=0;
        MPI_Allreduce(&aggregate_nodes,&minimum,1,MPIU_INT,MPI_MIN,comm);
        MPI_Allreduce(&aggregate_nodes,&maximum,1,MPIU_INT,MPI_MAX,comm);
        common_check(comm,minimum==maximum&&aggregate_nodes>=2&&aggregate_nodes<=4096&&
                     (!aggregate_set||velocity_solver==5||velocity_solver==7),
                     "velocity aggregate nodes must be identical in [2,4096] and require aggregate solver");
        node.velocity_aggregate_nodes=(velocity_solver==5||velocity_solver==7)?aggregate_nodes:0;
        node.rigid_velocity_modes=rigid_modes&&(node.twolevel_velocity||node.gamg_velocity||node.field_amg_velocity);
        if(node.twolevel_velocity||node.gamg_velocity||node.boomeramg_velocity||node.field_amg_velocity) {
            if(node.rigid_velocity_modes)
                common_check(comm,layout.owned_reference_coordinates.size()==static_cast<std::size_t>(layout.owned),
                             "rigid velocity coarse space requires owned reference coordinates");
            bool valid=true;
            for(auto row:node.root_rows) {
                const auto offset=row-layout.begin;
                const auto& key=layout.owned_semantics.at(offset);
                node.velocity_semantics.push_back(key);
                if(node.gamg_velocity||node.boomeramg_velocity||node.field_amg_velocity)
                    valid=valid&&(key.kind==DofEntity::body||
                        (key.kind==DofEntity::vertex&&key.mode==0&&key.space==1));
                if(node.rigid_velocity_modes) {
                    const auto& point=layout.owned_reference_coordinates.at(offset);
                    valid=valid&&std::all_of(point.begin(),point.end(),[](double x){return std::isfinite(x);});
                    // Reference-position rotations are defined for the current
                    // nodal P1 velocity space, not arbitrary edge/modal DoFs.
                    valid=valid&&(key.kind==DofEntity::body||
                        (key.kind==DofEntity::vertex&&key.mode==0&&key.space==1));
                    node.velocity_reference_coordinates.push_back(point);
                }
            }
            common_check(comm,valid,"geometric velocity coarse spaces and GAMG require finite P1 vertex data or a scalar body");
        }
        if(nodal) {
            std::map<DofKey,std::vector<PetscInt>> groups;
            for(std::size_t i=0;i<node.root_rows.size();++i) {
                auto key=layout.owned_semantics.at(node.root_rows[i]-layout.begin);
                key.component=0;
                groups[key].push_back(node.begin+static_cast<PetscInt>(i));
            }
            bool valid=true;
            for(auto& group:groups) {
                valid=valid&&!group.second.empty()&&group.second.size()<=3;
                node.velocity_groups.push_back(std::move(group.second));
            }
            common_check(comm,valid,"nodal velocity blocks must contain one to three active components");
        }
    }
    if(nodal_structure&&node.name=="fluid") {
        std::map<DofKey,std::vector<PetscInt>> groups;
        for(std::size_t i=0;i<node.root_rows.size();++i) {
            auto key=layout.owned_semantics.at(node.root_rows[i]-layout.begin);
            // The mixed inverse deliberately joins u and p, while preserving
            // entity kind, space and mode (including distinct RCR pressures).
            key.quantity=Q::velocity; key.component=0;
            groups[key].push_back(node.begin+static_cast<PetscInt>(i));
        }
        bool valid=true;
        for(auto& group:groups) {
            valid=valid&&!group.second.empty()&&group.second.size()<=4;
            node.fluid_groups.push_back(std::move(group.second));
        }
        common_check(comm,valid,"nodal fluid blocks must contain one to four active velocity/pressure components");
    }
    for(auto& child:node.children) decorate(comm,layout,child,velocity_solver,pressure_approx,nodal_structure,rigid_modes);
}
using SmallBlock=std::array<PetscScalar,16>;
// Invert only a 1--4 component local block, using pivoted elimination.
// The inverse is needed for sparse matrix products, never for the physical solve.
bool invert_small(PetscInt n,SmallBlock& a,SmallBlock& h,bool equilibrate) {
    if(n<1||n>4) return false;
    double scale=0;
    for(PetscInt i=0;i<n*n;++i) {
        if(!std::isfinite(a[i])) return false;
        scale=std::max(scale,std::abs(a[i]));
    }
    if(!(scale>0)) return false;
    std::array<double,4> rows{},columns{};
    if(equilibrate) {
        // Mixed velocity/pressure entries have different units. Invert R*A*C
        // after two-sided max equilibration, then return C*(R*A*C)^-1*R.
        // This changes only the local inverse calculation, never J or its RHS.
        for(PetscInt i=0;i<n;++i) {
            for(PetscInt j=0;j<n;++j) rows[i]=std::max(rows[i],std::abs(a[i*n+j]));
            if(!(rows[i]>0)) return false;
            for(PetscInt j=0;j<n;++j) a[i*n+j]/=rows[i];
        }
        for(PetscInt j=0;j<n;++j) {
            for(PetscInt i=0;i<n;++i) columns[j]=std::max(columns[j],std::abs(a[i*n+j]));
            if(!(columns[j]>0)) return false;
            for(PetscInt i=0;i<n;++i) a[i*n+j]/=columns[j];
        }
        scale=1.;
    }
    h.fill(0);
    for(PetscInt i=0;i<n;++i) h[i*n+i]=1.;
    for(PetscInt k=0;k<n;++k) {
        PetscInt pivot=k;
        for(PetscInt i=k+1;i<n;++i) if(std::abs(a[i*n+k])>std::abs(a[pivot*n+k])) pivot=i;
        if(std::abs(a[pivot*n+k])<=32*std::numeric_limits<double>::epsilon()*scale) return false;
        for(PetscInt j=0;j<n;++j) {
            std::swap(a[k*n+j],a[pivot*n+j]);
            std::swap(h[k*n+j],h[pivot*n+j]);
        }
        const double diagonal=a[k*n+k];
        for(PetscInt j=0;j<n;++j) { a[k*n+j]/=diagonal; h[k*n+j]/=diagonal; }
        for(PetscInt i=0;i<n;++i) if(i!=k) {
            const double factor=a[i*n+k];
            for(PetscInt j=0;j<n;++j) { a[i*n+j]-=factor*a[k*n+j]; h[i*n+j]-=factor*h[k*n+j]; }
        }
    }
    if(equilibrate) for(PetscInt i=0;i<n;++i) for(PetscInt j=0;j<n;++j) {
        // Wider intermediates avoid overflow when the two scale factors cancel.
        h[i*n+j]=static_cast<PetscScalar>(static_cast<long double>(h[i*n+j])/columns[i]/rows[j]);
    }
    return std::all_of(h.begin(),h.begin()+n*n,[](double v){return std::isfinite(v);});
}
// The root graph and index sets are immutable for a NonlinearSystem. Retain
// the same USER preconditioning Mat for PETSc and reuse symbolic products.
struct NodalSchur {
    MPI_Comm comm;
    bool mixed_fluid;
    PetscOwner<IS,ISDestroy> first_block,second_block;
    PetscOwner<Mat,MatDestroy> a,b,c,d,h,hb,chb,p;
    std::vector<std::vector<PetscInt>> groups;
    std::vector<std::size_t> inverse_offsets;
    std::vector<PetscScalar> inverse_values;
    NodalSchur(MPI_Comm communicator,const PcBlock& node):comm(communicator),mixed_fluid(node.nodal_structure_schur),
        groups(mixed_fluid?node.children.at(0).fluid_groups:node.children.at(0).velocity_groups) {
        const auto& first=node.children.at(0).root_rows;
        const auto& second=node.children.at(1).root_rows;
        EONSIM_PETSC(ISCreateGeneral(comm,first.size(),first.data(),PETSC_COPY_VALUES,first_block.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,second.size(),second.data(),PETSC_COPY_VALUES,second_block.put()));
    }
    void prepare_inverse_pattern() {
        PetscInt begin,end,global,columns;
        EONSIM_PETSC(MatGetOwnershipRange(a.get(),&begin,&end));
        EONSIM_PETSC(MatGetSize(a.get(),&global,&columns));
        std::vector<char> covered(end-begin,0);
        std::vector<PetscInt> rows,cols;
        bool valid=global==columns;
        inverse_offsets.reserve(groups.size());
        for(const auto& group:groups) {
            const auto n=group.size();
            bool local=n>=1&&n<=static_cast<std::size_t>(mixed_fluid?4:3);
            for(auto row:group) local=local&&row>=begin&&row<end;
            inverse_offsets.push_back(rows.size());
            if(!local) { valid=false; continue; }
            for(auto row:group) {
                valid=valid&&!covered[row-begin]; covered[row-begin]=1;
                for(auto col:group) { rows.push_back(row); cols.push_back(col); }
            }
        }
        valid=valid&&std::all_of(covered.begin(),covered.end(),[](char value){return value!=0;});
        common_check(comm,valid,mixed_fluid?"incomplete nodal fluid block ownership":
                                          "incomplete nodal velocity block ownership");
        inverse_values.resize(rows.size());
        EONSIM_PETSC(MatCreate(comm,h.put()));
        EONSIM_PETSC(MatSetSizes(h.get(),end-begin,end-begin,global,global));
        EONSIM_PETSC(MatSetType(h.get(),MATAIJ));
        // Every inverse is a full local 1--4 component block, including zeros.
        // COO owns its permutation after preparation; retain values in this
        // original group/row/column order. Empty owners participate with zero
        // entries, and no off-owner contribution or reverse exchange is needed.
        EONSIM_PETSC(MatSetPreallocationCOO(h.get(),static_cast<PetscCount>(rows.size()),rows.data(),cols.data()));
        EONSIM_PETSC(MatSetOption(h.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
    }
    void update(Mat root) {
        const bool first=!a.get();
        const MatReuse reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(root,first_block.get(),first_block.get(),reuse,a.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,first_block.get(),second_block.get(),reuse,b.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,second_block.get(),first_block.get(),reuse,c.put()));
        EONSIM_PETSC(MatCreateSubMatrix(root,second_block.get(),second_block.get(),reuse,d.put()));
        // Group membership, ownership and graph are fixed for this PC plan.
        // Validate and prepare the inverse scatter once, but extract/invert the
        // current nodal values on every requested numerical refresh.
        if(first) prepare_inverse_pattern();
        bool valid=true;
        for(std::size_t i=0;i<groups.size();++i) {
            const auto& rows=groups[i];
            const PetscInt n=static_cast<PetscInt>(rows.size());
            SmallBlock values{},inverse{};
            EONSIM_PETSC(MatGetValues(a.get(),n,rows.data(),n,rows.data(),values.data()));
            if(!invert_small(n,values,inverse,mixed_fluid)) valid=false;
            std::copy_n(inverse.data(),n*n,inverse_values.data()+inverse_offsets[i]);
        }
        common_check(comm,valid,mixed_fluid?"singular, nonfinite or incomplete nodal fluid block":
                                          "singular, nonfinite or incomplete nodal velocity block");
        // INSERT_VALUES overwrites every prepared slot, so a newly zero
        // off-diagonal cannot retain an inverse from the preceding Jacobian.
        // Publish only after every rank has passed the current inverse checks.
        EONSIM_PETSC(MatSetValuesCOO(h.get(),inverse_values.data(),INSERT_VALUES));
        EONSIM_PETSC(MatMatMult(h.get(),b.get(),reuse,PETSC_DEFAULT,hb.put()));
        EONSIM_PETSC(MatMatMult(c.get(),hb.get(),reuse,PETSC_DEFAULT,chb.put()));
        if(first) {
            EONSIM_PETSC(MatDuplicate(chb.get(),MAT_COPY_VALUES,p.put()));
            EONSIM_PETSC(MatScale(p.get(),-1.));
            EONSIM_PETSC(MatAXPY(p.get(),1.,d.get(),DIFFERENT_NONZERO_PATTERN));
        } else {
            EONSIM_PETSC(MatZeroEntries(p.get()));
            EONSIM_PETSC(MatAXPY(p.get(),-1.,chb.get(),SUBSET_NONZERO_PATTERN));
            EONSIM_PETSC(MatAXPY(p.get(),1.,d.get(),SUBSET_NONZERO_PATTERN));
        }
        if(mixed_fluid) {
            bool finite=true;
            PetscInt begin,end;
            EONSIM_PETSC(MatGetOwnershipRange(p.get(),&begin,&end));
            for(PetscInt row=begin;row<end;++row) {
                PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(p.get(),row,&count,&columns,&values));
                for(PetscInt j=0;j<count;++j) finite=finite&&std::isfinite(values[j]);
                EONSIM_PETSC(MatRestoreRow(p.get(),row,&count,&columns,&values));
            }
            common_check(comm,finite,"nonfinite nodal structure Schur approximation");
        }
    }
};
// Keep the full fluid/solid momentum block, including off-diagonal interface terms.
// Flexible outer GMRES accommodates an inexact inner GMRES with bounded work.
void coupled_velocity_defaults(KSP ksp) {
    PC pc; EONSIM_PETSC(KSPGetPC(ksp,&pc));
    EONSIM_PETSC(KSPSetType(ksp,KSPGMRES));
    EONSIM_PETSC(KSPSetTolerances(ksp,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    EONSIM_PETSC(PCSetType(pc,PCASM));
    EONSIM_PETSC(PCASMSetOverlap(pc,1));
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    option_default(base+"sub_ksp_type","preonly");
    option_default(base+"sub_pc_type","ilu");
    option_default(base+"sub_pc_factor_levels","1");
    option_default(base+"sub_pc_factor_mat_ordering_type","rcm");
    EONSIM_PETSC(KSPSetFromOptions(ksp));
}
bool diagonal_preconditioner(MPI_Comm comm,Mat matrix) {
    PetscBool rows_available=PETSC_FALSE;
    EONSIM_PETSC(MatHasOperation(matrix,MATOP_GET_ROW,&rows_available));
    bool diagonal=rows_available;
    if(rows_available) {
        PetscInt begin=0,end=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
        for(PetscInt row=begin;row<end&&diagonal;++row) {
            PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
            bool present=false;
            for(PetscInt j=0;j<count;++j) {
                diagonal=diagonal&&std::isfinite(values[j]);
                if(columns[j]==row) { present=true; diagonal=diagonal&&values[j]!=0.; }
                else diagonal=diagonal&&values[j]==0.;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
            diagonal=diagonal&&present;
        }
    }
    int local=diagonal,all=0;
    if(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS)
        throw std::runtime_error("PC diagonal-block classification communication failed");
    return all!=0;
}
void defaults(MPI_Comm comm,KSP ksp,bool structure_response=false) {
    PC pc; EONSIM_PETSC(KSPGetPC(ksp,&pc));
    Mat preconditioner=nullptr; EONSIM_PETSC(KSPGetOperators(ksp,nullptr,&preconditioner));
    EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY));
    // No hierarchy is needed for a numerical diagonal, including constrained
    // identity blocks whose AIJ graph still stores zero off-diagonal entries.
    EONSIM_PETSC(PCSetType(pc,diagonal_preconditioner(comm,preconditioner)?PCJACOBI:PCGAMG));
    // GAMG sets useAmat=true and PETSc retains it across a later pc_type change.
    // Local factors must see assembled P, not the implicit Schur operator A.
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    if(structure_response) {
        // Apply the implicit Schur with the configured approximate full-fluid
        // response, preconditioned by the assembled structural diagonal block.
        // The outer flexible solve retains the complete root Jacobian and gate.
        EONSIM_PETSC(KSPSetType(ksp,KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(ksp,1e-2,PETSC_DEFAULT,PETSC_DEFAULT,20));
    }
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
    const std::string base="-"+std::string(prefix?prefix:"");
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"mg_coarse_ksp_type","gmres"},{"mg_coarse_pc_type","jacobi"},
        {"mg_coarse_ksp_rtol","1e-10"},{"mg_coarse_ksp_max_it","200"},
        {"mg_coarse_ksp_norm_type","unpreconditioned"}}) {
        PetscBool found=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,(base+option.first).c_str(),&found));
        if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+option.first).c_str(),option.second.c_str()));
    }
    EONSIM_PETSC(KSPSetFromOptions(ksp));
}
struct SubSolvers { KSP* values=nullptr; ~SubSolvers(){ PetscFree(values); } };
struct SchurCache {
    std::map<const PcBlock*,std::shared_ptr<NodalSchur>> nodal;
    std::map<const PcBlock*,std::shared_ptr<PressureSchurState>> pressure;
};
InterfacePatchOptions patch_options(const PcBlock& node) {
    InterfacePatchOptions options;
    options.single_precision=node.patch_single_precision;
    options.overlap=node.patch_overlap; options.maximum_size=node.patch_maximum_size;
    options.refinement_steps=node.patch_refinement_steps;
    options.refinement_tolerance=node.patch_refinement_tolerance;
    options.damping=node.patch_damping;
    return options;
}
void configure(MPI_Comm comm,KSP ksp,const PcBlock& node,Mat root_matrix,PcSchurUpdates* updates,
               SchurCache& schur_cache,bool root,bool schur_parent=false) {
    Mat a=nullptr; EONSIM_PETSC(KSPGetOperators(ksp,&a,nullptr));
    PetscInt m=0,n=0,begin=0,end=0;
    EONSIM_PETSC(MatGetSize(a,&m,&n)); EONSIM_PETSC(MatGetOwnershipRange(a,&begin,&end));
    common_check(comm,m==node.global&&n==m&&begin==node.begin&&end-begin==static_cast<PetscInt>(node.root_rows.size()),
                 "submatrix ownership does not match provenance at "+node.name);
    PetscBool report=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    if(report) {
        int rank=0; MPI_Comm_rank(comm,&rank);
        const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&prefix));
        EONSIM_PETSC(PetscSynchronizedPrintf(comm,"pc_block rank=%d name=%s prefix=%s global=%" PetscInt_FMT " begin=%" PetscInt_FMT " owned=%zu children=%zu structure_approx=%s\n",
            rank,node.name.c_str(),prefix?prefix:"-",node.global,node.begin,node.root_rows.size(),node.children.size(),
            node.added_mass_schur?(node.nodal_structure_schur?"nodal":"a11"):"none"));
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    PC pc; EONSIM_PETSC(KSPGetPC(ksp,&pc));
    if(node.rcr_ports) {
        // The child uses its own compact root numbering, not original J rows.
        // Its refreshers live in the shell and run before new port responses.
        configure_rcr_port_pc(comm,ksp,root_matrix,node.rcr_port_rows,
            [comm,bulk_plan=node.children.at(0)](KSP bulk,Mat matrix,PcSchurUpdates* bulk_updates) {
                SchurCache bulk_cache;
                configure(comm,bulk,bulk_plan,matrix,bulk_updates,bulk_cache,true);
            },updates);
        return;
    }
    if(node.interface_patch) {
        configure_interface_patch_pc(comm,ksp,root_matrix,node.patch_semantics,node.patch_interface,
            patch_options(node),[comm,bulk_plan=node.children.at(0)](KSP bulk,Mat matrix,PcSchurUpdates* bulk_updates) {
                SchurCache bulk_cache;
                configure(comm,bulk,bulk_plan,matrix,bulk_updates,bulk_cache,true);
            },updates);
        return;
    }
    if(node.children.empty()) {
        // Raw stabilized J_pp may have a constant nullspace even when the full
        // traction-coupled system is nonsingular. Do not invert that block with
        // an AMG coarse solve; the quantity recipe uses its diagonal action.
        if(node.field_amg_velocity) configure_coupled_velocity_field_amg(comm,ksp,node.velocity_semantics,
            node.velocity_reference_coordinates,node.rigid_velocity_modes,node.velocity_aggregate_nodes);
        else if(node.twolevel_velocity) configure_coupled_velocity_twolevel(comm,ksp,node.velocity_semantics,
            node.velocity_reference_coordinates,node.rigid_velocity_modes,node.velocity_aggregate_nodes);
        else if(node.gamg_velocity) configure_coupled_velocity_gamg(comm,ksp,node.velocity_semantics,
            node.velocity_reference_coordinates,node.rigid_velocity_modes);
        else if(node.boomeramg_velocity) configure_coupled_velocity_boomeramg(comm,ksp,node.velocity_semantics);
        else if(node.global==1 || (node.name=="pressure"&&!schur_parent)) {
            EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY)); EONSIM_PETSC(PCSetType(pc,PCJACOBI));
            EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
            if(node.structure_response) {
                EONSIM_PETSC(KSPSetType(ksp,KSPFGMRES));
                EONSIM_PETSC(KSPSetTolerances(ksp,1e-2,PETSC_DEFAULT,PETSC_DEFAULT,20));
            }
            EONSIM_PETSC(KSPSetFromOptions(ksp));
        } else if(node.coupled_velocity) coupled_velocity_defaults(ksp);
        else defaults(comm,ksp,node.structure_response);
        return;
    }
    if(!root) EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY));
    if(node.fluid_response) {
        // One complete velocity/pressure PC application approximates F^-1.
        // Its tolerance-dependent coarse solves still require outer FGMRES.
        // Retain the bounded budget for an explicit FGMRES override. Each
        // main/interior/upper KSP applies its own options after these defaults.
        EONSIM_PETSC(KSPSetType(ksp,KSPPREONLY));
        EONSIM_PETSC(KSPSetTolerances(ksp,1e-4,PETSC_DEFAULT,PETSC_DEFAULT,20));
    }
    EONSIM_PETSC(PCSetType(pc,PCFIELDSPLIT));
    EONSIM_PETSC(PCFieldSplitSetType(pc,node.schur?PC_COMPOSITE_SCHUR:PC_COMPOSITE_MULTIPLICATIVE));
    if(node.schur) {
        EONSIM_PETSC(PCFieldSplitSetSchurFactType(pc,PC_FIELDSPLIT_SCHUR_FACT_FULL));
        if(node.pressure_schur) {
            common_check(comm,updates!=nullptr,"pressure Schur requires live numeric refresh state");
            auto& state=schur_cache.pressure[&node];
            if(!state) {
                const auto kind=node.pressure_schur==3?PressureSchurKind::lsc:
                    node.pressure_schur==4?PressureSchurKind::bfbt:PressureSchurKind::pcd;
                state=make_pressure_schur_state(comm,root_matrix,node.children.at(0).root_rows,
                    node.children.at(1).root_rows,kind);
                updates->refreshers.push_back([state](Mat matrix){refresh_pressure_schur(state,matrix);});
            }
            EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,PC_FIELDSPLIT_SCHUR_PRE_USER,pressure_schur_matrix(state)));
        } else if(node.nodal_schur||node.nodal_structure_schur) {
            common_check(comm,updates!=nullptr,"nodal Schur requires live numeric refresh state");
            // Independent main/inner/upper KSPs use the same numerical block.
            // Share its USER matrix and refresh it once per Jacobian assembly.
            // Structure P is K-G*H_F*E. Its implicit A keeps the full fluid
            // blocks and applies the configured approximate fluid response;
            // the root Jacobian is unchanged.
            auto& state=schur_cache.nodal[&node];
            if(!state) {
                state=std::make_shared<NodalSchur>(comm,node);
                state->update(root_matrix);
                updates->refreshers.push_back([state](Mat matrix){state->update(matrix);});
            }
            EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,PC_FIELDSPLIT_SCHUR_PRE_USER,state->p.get()));
        } else EONSIM_PETSC(PCFieldSplitSetSchurPre(pc,
            node.added_mass_schur?PC_FIELDSPLIT_SCHUR_PRE_A11:PC_FIELDSPLIT_SCHUR_PRE_SELFP,nullptr));
    }
    for(const auto& child:node.children) {
        PetscOwner<IS,ISDestroy> is;
        EONSIM_PETSC(ISCreateGeneral(comm,child.parent_rows.size(),child.parent_rows.data(),PETSC_COPY_VALUES,is.put()));
        EONSIM_PETSC(PCFieldSplitSetIS(pc,child.name.c_str(),is.get()));
    }
    // Options are applied after registering IS, before setup. The topology is fixed.
    EONSIM_PETSC(KSPSetFromOptions(ksp));
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    common_check(comm,type&&std::string(type)==PCFIELDSPLIT,"internal node requires fieldsplit at "+node.name);
    PCCompositeType actual; EONSIM_PETSC(PCFieldSplitGetType(pc,&actual));
    common_check(comm,actual==(node.schur?PC_COMPOSITE_SCHUR:PC_COMPOSITE_MULTIPLICATIVE),
                 "options changed recipe split type at "+node.name);
    EONSIM_PETSC(PCSetUp(pc));
    if(node.schur) {
        configure_schur_subsolvers(comm,pc,
            [&](KSP sub){configure(comm,sub,node.children.at(0),root_matrix,updates,schur_cache,false,true);},
            [&](KSP sub){
                if(node.pressure_schur) configure_pressure_schur_pc(comm,sub,schur_cache.pressure.at(&node));
                else configure(comm,sub,node.children.at(1),root_matrix,updates,schur_cache,false,true);
            });
        return;
    }
    PetscInt count=0; SubSolvers sub;
    EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&count,&sub.values));
    common_check(comm,count==static_cast<PetscInt>(node.children.size()),"subsolver count changed at "+node.name);
    for(PetscInt i=0;i<count;++i) configure(comm,sub.values[i],node.children[i],root_matrix,updates,schur_cache,false,node.schur);
}
}
namespace {
PcBlock make_pc_plan_impl(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe,bool allow_ports,bool allow_interface=true) {
    int choice=recipe=="physics"?1:recipe=="quantity"?2:recipe=="hybrid"?3:recipe=="added_mass"?4:0;
    int lo=0,hi=0;
    MPI_Allreduce(&choice,&lo,1,MPI_INT,MPI_MIN,comm); MPI_Allreduce(&choice,&hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,lo==hi&&lo!=0,"recipe must be physics, quantity, hybrid or added_mass and identical on every rank");
    common_check(comm,layout.owned>=0&&layout.begin>=0&&layout.global>0&&
        static_cast<long long>(layout.begin)+layout.owned<=layout.global,"invalid root ownership range");
    bool owned_order=layout.local_to_global.size()>=static_cast<std::size_t>(layout.owned);
    if(owned_order) for(PetscInt i=0;i<layout.owned;++i) owned_order=owned_order&&layout.local_to_global[i]==layout.begin+i;
    common_check(comm,owned_order,"owned storage must precede ghosts in root order");
    common_check(comm,layout.owned_semantics.size()==static_cast<std::size_t>(layout.owned),"missing owned semantic identities");
    common_check(comm,layout.owned_interface.empty()||layout.owned_interface.size()==layout.owned_semantics.size(),
                 "interface metadata must follow owned semantic rows");
    std::set<DofKey> keys(layout.owned_semantics.begin(),layout.owned_semantics.end());
    common_check(comm,keys.size()==layout.owned_semantics.size(),"duplicate owned semantic identity");
    common_check(comm,std::all_of(layout.owned_semantics.begin(),layout.owned_semantics.end(),[](const DofKey& k) {
        const bool field=(k.domain==D::fluid&&
            ((k.quantity==Q::velocity&&k.component<3)||(k.quantity==Q::pressure&&k.component==0)))||
            (k.domain==D::solid&&k.quantity==Q::velocity&&k.component<3)||
            (k.domain==D::mesh&&k.quantity==Q::displacement&&k.component<3);
        return field&&static_cast<int>(k.kind)<=static_cast<int>(DofEntity::boundary)&&
            (k.kind!=DofEntity::body||(k.domain==D::solid&&k.component==0));
    }),"invalid semantic domain, quantity, entity kind or component");
    PetscBool port_option=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_rcr_ports",&port_option,nullptr));
    int port_local=port_option?1:0,port_min=0,port_max=0;
    MPI_Allreduce(&port_local,&port_min,1,MPI_INT,MPI_MIN,comm);
    MPI_Allreduce(&port_local,&port_max,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,port_min==port_max,"RCR port selection differs between ranks");
    if(allow_ports&&port_option) {
        PcBlock wrapper; wrapper.name="rcr_ports"; wrapper.rcr_ports=true;
        wrapper.begin=layout.begin; wrapper.global=layout.global;
        wrapper.root_rows.resize(layout.owned);
        std::iota(wrapper.root_rows.begin(),wrapper.root_rows.end(),layout.begin);
        wrapper.parent_rows=wrapper.root_rows;
        AlgebraLayout bulk;
        common_check(comm,layout.owned_reference_coordinates.empty()||
            layout.owned_reference_coordinates.size()==layout.owned_semantics.size(),
            "RCR bulk reference coordinates must follow owned rows");
        for(PetscInt i=0;i<layout.owned;++i) {
            const auto& key=layout.owned_semantics[i];
            if(key.domain==D::fluid&&key.quantity==Q::pressure&&key.kind==DofEntity::boundary)
                wrapper.rcr_port_rows.push_back(layout.begin+i);
            else {
                bulk.owned_semantics.push_back(key);
                if(!layout.owned_reference_coordinates.empty())
                    bulk.owned_reference_coordinates.push_back(layout.owned_reference_coordinates[i]);
                if(!layout.owned_interface.empty()) bulk.owned_interface.push_back(layout.owned_interface[i]);
            }
        }
        bulk.owned=static_cast<PetscInt>(bulk.owned_semantics.size());
        int rank=0; MPI_Comm_rank(comm,&rank);
        MPI_Exscan(&bulk.owned,&bulk.begin,1,MPIU_INT,MPI_SUM,comm);
        if(rank==0) bulk.begin=0;
        MPI_Allreduce(&bulk.owned,&bulk.global,1,MPIU_INT,MPI_SUM,comm);
        common_check(comm,bulk.global>0&&bulk.global<layout.global,
            "RCR port correction requires boundary-pressure ports and a nonempty bulk");
        bulk.local_to_global.resize(bulk.owned);
        std::iota(bulk.local_to_global.begin(),bulk.local_to_global.end(),bulk.begin);
        wrapper.children.push_back(make_pc_plan_impl(comm,bulk,recipe,false));
        return wrapper;
    }
    char smoother[32]{}; PetscBool smoother_set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_interface_smoother",smoother,sizeof(smoother),&smoother_set));
    const std::string smoother_name=smoother_set?smoother:"none";
    int patch=smoother_name=="none"?0:(smoother_name=="vanka"||smoother_name=="patch"?1:-1),patch_lo=0,patch_hi=0;
    MPI_Allreduce(&patch,&patch_lo,1,MPI_INT,MPI_MIN,comm); MPI_Allreduce(&patch,&patch_hi,1,MPI_INT,MPI_MAX,comm);
    common_check(comm,patch_lo==patch_hi&&patch>=0,"interface smoother must be none, vanka or patch and identical on every rank");
    bool patch_parameters=false;
    for(const char* option:{"-pc_plan_patch_precision","-pc_plan_patch_overlap","-pc_plan_patch_max_size",
        "-pc_plan_patch_refinement_steps","-pc_plan_patch_refinement_tolerance","-pc_plan_patch_damping"}) {
        PetscBool found=PETSC_FALSE; EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,option,&found));
        patch_parameters=patch_parameters||found;
    }
    common_check(comm,!patch_parameters||patch==1,"patch parameters require an interface smoother");
    if(allow_interface&&patch) {
        common_check(comm,layout.owned_interface.size()==layout.owned_semantics.size(),
                     "interface smoother requires true owned interface metadata");
        PcBlock wrapper; wrapper.name="interface_patch"; wrapper.interface_patch=true;
        wrapper.begin=layout.begin; wrapper.global=layout.global;
        wrapper.root_rows.resize(layout.owned); std::iota(wrapper.root_rows.begin(),wrapper.root_rows.end(),layout.begin);
        wrapper.parent_rows=wrapper.root_rows; wrapper.patch_semantics=layout.owned_semantics;
        wrapper.patch_interface=layout.owned_interface;
        char precision[32]{}; PetscBool precision_set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,"-pc_plan_patch_precision",precision,sizeof(precision),&precision_set));
        const std::string name=precision_set?precision:"double";
        common_check(comm,name=="double"||name=="single"||name=="fp32"||name=="fp64",
                     "patch precision must be double/fp64 or single/fp32");
        wrapper.patch_single_precision=name=="single"||name=="fp32";
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-pc_plan_patch_overlap",&wrapper.patch_overlap,nullptr));
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-pc_plan_patch_max_size",&wrapper.patch_maximum_size,nullptr));
        EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-pc_plan_patch_refinement_steps",&wrapper.patch_refinement_steps,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-pc_plan_patch_refinement_tolerance",&wrapper.patch_refinement_tolerance,nullptr));
        EONSIM_PETSC(PetscOptionsGetReal(nullptr,nullptr,"-pc_plan_patch_damping",&wrapper.patch_damping,nullptr));
        wrapper.children.push_back(make_pc_plan_impl(comm,layout,recipe,false,false));
        return wrapper;
    }
    int local[3]{},global[3]{};
    for(const auto& key:layout.owned_semantics) ++local[static_cast<int>(key.domain)];
    MPI_Allreduce(local,global,3,MPI_INT,MPI_SUM,comm);
    const bool coupled=global[1]||global[2];
    common_check(comm,global[0]>0&&(!coupled||(global[1]>0&&global[2]>0)),"recipes require independent fluid or complete FSI layout");
    const int velocity_solver=velocity_solver_requested(comm);
    const bool rigid_modes=rigid_velocity_modes_requested(comm,velocity_solver);
    const int pressure_approx=pressure_schur_requested(comm);
    const bool combined=velocity_solver!=1;
    const bool nodal_structure=nodal_structure_requested(comm,choice==4);
    common_check(comm,choice!=4||coupled,"added_mass requires a complete FSI layout");
    common_check(comm,pressure_approx==1||!coupled||choice!=2,"pressure approximation requires a recipe with a pressure Schur block");
    if(pressure_approx==5) common_check(comm,std::none_of(layout.owned_semantics.begin(),layout.owned_semantics.end(),[](const DofKey& key) {
        return key.quantity==Q::pressure&&key.kind==DofEntity::boundary;
    }),"PCD with boundary-pressure ports requires -pc_plan_rcr_ports true");
    common_check(comm,!combined||(coupled&&(choice==2||choice==3)),"coupled velocity requires a complete FSI quantity or hybrid recipe");
    Spec v{"velocity",4}, p{"pressure",5}, mesh{"mesh",3}, solid{"structure",2}, fluid{"fluid_interior",1};
    Spec root{"root",0};
    if(!coupled) { root.schur=true; root.children={v,p}; }
    else if(choice==1) root.children={{"fluid",1,true,{v,p}},{"solid",2},mesh};
    else if(choice==4) root.children={{"dynamics",6,true,{{"fluid",1,true,{v,p}},solid}},mesh};
    else {
        if(!combined) v.children={fluid,solid};
        if(choice==2) root.children={v,p,mesh};
        else root.children={{"dynamics",6,true,{v,p}},mesh};
    }
    std::vector<PetscInt> rows(layout.owned); std::iota(rows.begin(),rows.end(),layout.begin);
    auto plan=build(comm,layout,root,rows,rows);
    decorate(comm,layout,plan,velocity_solver,pressure_approx,nodal_structure,rigid_modes);
    if(choice==4) {
        auto& dynamics=plan.children.at(0);
        dynamics.added_mass_schur=true;
        dynamics.nodal_structure_schur=nodal_structure;
        dynamics.children.at(0).fluid_response=true;
        // The explicit nodal P defaults to one PC application, avoiding another
        // Krylov loop whose every Schur matvec would invoke a full fluid solve.
        // Explicit structural KSP options can still request that implicit action.
        dynamics.children.at(1).structure_response=!nodal_structure;
    }
    return plan;
}
}
PcBlock make_pc_plan(MPI_Comm comm,const AlgebraLayout& layout,const std::string& recipe) {
    return make_pc_plan_impl(comm,layout,recipe,true);
}
namespace {
bool requires_flexible_outer(const PcBlock& node) {
    return node.rcr_ports||node.interface_patch||node.pressure_schur||node.field_amg_velocity||node.added_mass_schur||node.twolevel_velocity||node.gamg_velocity||node.boomeramg_velocity||
        std::any_of(node.children.begin(),node.children.end(),requires_flexible_outer);
}
void validate_options(MPI_Comm comm,const PcBlock& node,const std::string& prefix,const std::vector<std::string>& tokens) {
    if(node.interface_patch) {
        validate_interface_patch_options(comm,prefix,patch_options(node));
        validate_options(comm,node.children.at(0),prefix+"interface_bulk_",tokens);
        return;
    }
    if(node.rcr_ports) {
        const std::string base="-"+prefix;
        char value[64]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"pc_type").c_str(),value,sizeof(value),&set));
        common_check(comm,!set||std::string(value)==PCSHELL,"RCR port correction requires a shell PC at "+prefix);
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"rcr_bulk_ksp_type").c_str(),value,sizeof(value),&set));
        common_check(comm,!set||std::string(value)==KSPPREONLY,"RCR bulk must use one PREONLY response at "+prefix);
        validate_options(comm,node.children.at(0),prefix+"rcr_bulk_",tokens);
        return;
    }
    if(node.children.empty()) {
        if(node.field_amg_velocity) validate_coupled_velocity_field_amg_options(comm,prefix);
        else if(node.twolevel_velocity) validate_coupled_velocity_twolevel_options(comm,prefix);
        else if(node.gamg_velocity) validate_coupled_velocity_gamg_options(comm,prefix);
        else if(node.boomeramg_velocity) validate_coupled_velocity_boomeramg_options(comm,prefix);
        return;
    }
    const auto base="-"+prefix;
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"pc_type","fieldsplit"},{"pc_fieldsplit_type",node.schur?"schur":"multiplicative"}}) {
        char value[128]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+option.first).c_str(),value,sizeof(value),&set));
        common_check(comm,!set||value==option.second,"options changed recipe at "+prefix+option.first);
    }
    bool valid=true;
    if(node.nodal_schur||node.nodal_structure_schur||node.pressure_schur) {
        char value[32]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"pc_fieldsplit_schur_precondition").c_str(),value,sizeof(value),&set));
        common_check(comm,!set||std::string(value)=="user","nodal Schur conflicts with a different Schur preconditioner at "+prefix);
        for(const auto& token:tokens)
            if(token==base+"fieldsplit_"+node.children[1].name+"_mat_schur_complement_ainv_type")
                valid=false;
        common_check(comm,valid,"nodal Schur conflicts with PETSc native A-inverse approximation at "+prefix);
    }
    if(node.added_mass_schur&&!node.nodal_structure_schur) {
        char value[32]{}; PetscBool set=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,(base+"pc_fieldsplit_schur_precondition").c_str(),value,sizeof(value),&set));
        common_check(comm,!set||std::string(value)=="a11","added_mass uses the structural A11 preconditioner at "+prefix);
    }
    for(const auto& child:node.children) validate_options(comm,child,prefix+"fieldsplit_"+child.name+"_",tokens);
    if(node.pressure_schur) validate_pressure_schur_options(comm,prefix+"fieldsplit_pressure_");
    if(node.schur) {
        const auto auxiliary=validate_schur_auxiliary_options(comm,prefix,node.children.at(1).name);
        const auto second=prefix+"fieldsplit_"+node.children.at(1).name;
        if(auxiliary.inner) validate_options(comm,node.children.at(0),second+"_inner_",tokens);
        if(auxiliary.upper) validate_options(comm,node.children.at(0),second+"_upper_",tokens);
    }
}
}
void validate_pc_plan_options(MPI_Comm comm,KSP solver,const PcBlock& plan) {
    char* text=nullptr; EONSIM_PETSC(PetscOptionsGetAll(nullptr,&text));
    std::istringstream stream(text?text:""); EONSIM_PETSC(PetscFree(text));
    std::vector<std::string> tokens; std::string token;
    while(stream>>token) tokens.push_back(token);
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    if(requires_flexible_outer(plan)) {
        char value[32]{}; PetscBool set=PETSC_FALSE;
        const std::string option="-"+std::string(prefix?prefix:"")+"ksp_type";
        EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,option.c_str(),value,sizeof(value),&set));
        KSPType actual=nullptr; EONSIM_PETSC(KSPGetType(solver,&actual));
        common_check(comm,(!set||std::string(value)==KSPFGMRES)&&(!actual||std::string(actual)==KSPFGMRES),
                     "RCR ports, added_mass, twolevel and AMG require outer FGMRES for variable inner actions");
    }
    validate_options(comm,plan,prefix?prefix:"",tokens);
}
void configure_pc_plan(MPI_Comm comm,KSP solver,Mat matrix,const PcBlock& plan,PcSchurUpdates* updates) {
    validate_pc_plan_options(comm,solver,plan);
    common_check(comm,!updates||updates->refreshers.empty(),"PC plan numeric state must be fresh");
    if(requires_flexible_outer(plan)) EONSIM_PETSC(KSPSetType(solver,KSPFGMRES));
    EONSIM_PETSC(KSPSetOperators(solver,matrix,matrix));
    SchurCache schur_cache;
    configure(comm,solver,plan,matrix,updates,schur_cache,true);
}
}
