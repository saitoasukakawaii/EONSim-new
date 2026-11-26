#include "eonsim/pc_plan.hpp"
#include "eonsim/coupled_velocity_pc.hpp"
#include "eonsim/schur_solver.hpp"
#include <array>
#include <algorithm>
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/reduced_layout.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool ok,const char* msg) {
    int bad=!ok,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(msg);
}
double entry(PetscInt i,PetscInt j) {return (i==j?100.:0.)+.01*(i+1)+.02*(j+1);}
using Oracle=std::map<std::string,std::vector<PetscInt>>;
struct ScopedOptions {
    std::vector<std::string> names;
    void set(const std::string& name,const std::string& value) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value.c_str()));
        names.push_back(name);
    }
    ~ScopedOptions() { for(const auto& name:names) (void)PetscOptionsClearValue(nullptr,name.c_str()); }
};
KSP child_solver(MPI_Comm comm,KSP parent,PetscInt index,bool schur=false) {
    PC pc; EONSIM_PETSC(KSPGetPC(parent,&pc));
    PetscInt count=0; KSP* children=nullptr;
    if(schur) EONSIM_PETSC(PCFieldSplitSchurGetSubKSP(pc,&count,&children));
    else EONSIM_PETSC(PCFieldSplitGetSubKSP(pc,&count,&children));
    check(comm,index>=0&&index<count,"Missing expected block solver");
    KSP result=children[index]; EONSIM_PETSC(PetscFree(children));
    return result;
}
void solve_exact(MPI_Comm comm,KSP solver,Mat matrix,const char* label) {
    PetscOwner<Vec,VecDestroy> exact,rhs,solution,defect;
    EONSIM_PETSC(MatCreateVecs(matrix,exact.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(exact.get(),solution.put()));
    EONSIM_PETSC(VecDuplicate(rhs.get(),defect.put()));
    PetscInt begin,end; EONSIM_PETSC(VecGetOwnershipRange(exact.get(),&begin,&end));
    for(PetscInt i=begin;i<end;++i) EONSIM_PETSC(VecSetValue(exact.get(),i,.25*(i+1),INSERT_VALUES));
    EONSIM_PETSC(VecAssemblyBegin(exact.get())); EONSIM_PETSC(VecAssemblyEnd(exact.get()));
    EONSIM_PETSC(MatMult(matrix,exact.get(),rhs.get()));
    EONSIM_PETSC(VecSet(solution.get(),0.));
    EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(MatMult(matrix,solution.get(),defect.get()));
    EONSIM_PETSC(VecAXPY(defect.get(),-1.,rhs.get()));
    PetscReal residual,rhs_norm,error;
    EONSIM_PETSC(VecNorm(defect.get(),NORM_2,&residual));
    EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&rhs_norm));
    EONSIM_PETSC(VecAXPY(solution.get(),-1.,exact.get()));
    EONSIM_PETSC(VecNorm(solution.get(),NORM_INFINITY,&error));
    const bool good=reason>0&&residual<=1e-10*(1+rhs_norm)&&error<1e-9;
    if(!good) EONSIM_PETSC(PetscPrintf(comm,
        "pc_test_solve_failed case=%s reason=%d residual=%.17g rhs_norm=%.17g solution_error=%.17g\n",
        label,static_cast<int>(reason),static_cast<double>(residual),static_cast<double>(rhs_norm),
        static_cast<double>(error)));
    check(comm,good,
          "Block solve changed the exact solution or failed the true residual check");
}
void verify_preonly_action(MPI_Comm comm,KSP solver) {
    KSPType type=nullptr; PC pc; Mat matrix=nullptr;
    EONSIM_PETSC(KSPGetType(solver,&type)); EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPGetOperators(solver,&matrix,nullptr));
    check(comm,type&&std::string(type)==KSPPREONLY,"Default response did not retain PREONLY");
    PetscOwner<Vec,VecDestroy> rhs,solution,applied;
    EONSIM_PETSC(MatCreateVecs(matrix,solution.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(solution.get(),applied.put()));
    PetscInt begin,end; EONSIM_PETSC(VecGetOwnershipRange(rhs.get(),&begin,&end));
    for(PetscInt i=begin;i<end;++i) EONSIM_PETSC(VecSetValue(rhs.get(),i,.5+.25*i,INSERT_VALUES));
    EONSIM_PETSC(VecAssemblyBegin(rhs.get())); EONSIM_PETSC(VecAssemblyEnd(rhs.get()));
    EONSIM_PETSC(VecSet(solution.get(),0.)); EONSIM_PETSC(VecSet(applied.get(),0.));
    EONSIM_PETSC(KSPSolve(solver,rhs.get(),solution.get()));
    KSPConvergedReason reason; PetscInt iterations=0;
    EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(KSPGetIterationNumber(solver,&iterations));
    EONSIM_PETSC(PCApply(pc,rhs.get(),applied.get()));
    PetscReal magnitude=0,difference=0;
    EONSIM_PETSC(VecNorm(solution.get(),NORM_INFINITY,&magnitude));
    EONSIM_PETSC(VecAXPY(applied.get(),-1.,solution.get()));
    EONSIM_PETSC(VecNorm(applied.get(),NORM_INFINITY,&difference));
    PCFailedReason failure; EONSIM_PETSC(PCGetFailedReason(pc,&failure));
    // This is one PC application on this call, not accumulated inner work or
    // an assertion that the coarse iterative response is a fixed linear map.
    check(comm,reason>0&&iterations==1&&failure==PC_NOERROR&&std::isfinite(magnitude)&&
               magnitude>0&&std::isfinite(difference)&&difference<1e-11*(1+magnitude),
          "Default PREONLY response differed from one successful PC application");
}
void verify_tree(MPI_Comm comm,Mat parent,const PcBlock& node,const std::string& path,const Oracle& oracle) {
    for(const auto& child:node.children) {
        const auto name=path+"/"+child.name;
        const auto& expected=oracle.at(name);
        PetscOwner<IS,ISDestroy> is; PetscOwner<Mat,MatDestroy> sub;
        EONSIM_PETSC(ISCreateGeneral(comm,child.parent_rows.size(),child.parent_rows.data(),PETSC_COPY_VALUES,is.put()));
        EONSIM_PETSC(MatCreateSubMatrix(parent,is.get(),is.get(),MAT_INITIAL_MATRIX,sub.put()));
        PetscInt begin,end,n,m; EONSIM_PETSC(MatGetSize(sub.get(),&m,&n));
        EONSIM_PETSC(MatGetOwnershipRange(sub.get(),&begin,&end));
        bool good=m==static_cast<PetscInt>(expected.size())&&m==n&&begin==child.begin;
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count; const PetscInt* cols; const PetscScalar* values;
            EONSIM_PETSC(MatGetRow(sub.get(),row,&count,&cols,&values));
            good=good&&count==m;
            for(PetscInt i=0;i<count;++i) good=good&&values[i]==entry(expected.at(row),expected.at(cols[i]));
            EONSIM_PETSC(MatRestoreRow(sub.get(),row,&count,&cols,&values));
        }
        check(comm,good,"Nested matrix value/ownership oracle failed");
        verify_tree(comm,sub.get(),child,name,oracle);
    }
}
// Independent 1--3 component cofactor oracle. It intentionally uses the
// original root numbering and does not consult the production velocity groups.
double inverse_entry(const std::vector<PetscInt>& g,int i,int j) {
    const int n=static_cast<int>(g.size());
    const auto a=[&](int r,int c){return entry(g[r],g[c]);};
    if(n==1) return 1/a(0,0);
    if(n==2) return (i==j?a(1-i,1-j):-a(i,j))/(a(0,0)*a(1,1)-a(0,1)*a(1,0));
    const auto cofactor=[&](int r,int c) {
        std::array<int,2> rows{},cols{}; int nr=0,nc=0;
        for(int k=0;k<3;++k) {if(k!=r) rows[nr++]=k;if(k!=c) cols[nc++]=k;}
        return ((r+c)%2?-1.:1.)*(a(rows[0],cols[0])*a(rows[1],cols[1])-a(rows[0],cols[1])*a(rows[1],cols[0]));
    };
    const double det=a(0,0)*cofactor(0,0)+a(0,1)*cofactor(0,1)+a(0,2)*cofactor(0,2);
    return cofactor(j,i)/det;
}
double schur_entry(PetscInt i,PetscInt j,const std::vector<std::vector<PetscInt>>& groups) {
    double v=entry(i,j);
    for(const auto& g:groups) for(int k=0;k<static_cast<int>(g.size());++k)
        for(int l=0;l<static_cast<int>(g.size());++l)
            v-=entry(i,g[k])*inverse_entry(g,k,l)*entry(g[l],j);
    return v;
}
void verify_nodal_schur(MPI_Comm comm,const AlgebraLayout& original,Mat matrix) {
    auto layout=original;
    // Nonconsecutive active components, an independent mode, and a boundary
    // pressure (as used by RCR) exercise semantic groups and the complete D.
    for(PetscInt k=0;k<layout.owned;++k) {
        const auto row=layout.begin+k;
        auto& key=layout.owned_semantics[k];
        if(row==1||row==13) key.mode=1;
        if(row==7) key.kind=DofEntity::boundary;
    }
    const std::vector<PetscInt> pressure{3,7};
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_schur_approx","nodal"));
    for(const std::string recipe:{"physics","hybrid"}) {
        if(recipe=="hybrid")
            EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_velocity_solver","coupled"));
        auto plan=make_pc_plan(comm,layout,recipe);
        const auto& dynamics=plan.children.front();
        const auto& velocity=dynamics.children.front();
        check(comm,dynamics.nodal_schur&&(recipe!="hybrid"||
              (velocity.coupled_velocity&&velocity.children.empty())),"New PC topology was not selected");
        PcSchurUpdates updates;
        PetscOwner<KSP,KSPDestroy> outer;
        EONSIM_PETSC(KSPCreate(comm,outer.put()));
        EONSIM_PETSC(KSPSetType(outer.get(),KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(outer.get(),1e-12,1e-13,PETSC_DEFAULT,200));
        configure_pc_plan(comm,outer.get(),matrix,plan,&updates);
        PC root_pc,dynamics_pc;
        KSP *sub=nullptr,*inner=nullptr;
        PetscInt count=0,inner_count=0;
        EONSIM_PETSC(KSPGetPC(outer.get(),&root_pc));
        EONSIM_PETSC(PCFieldSplitGetSubKSP(root_pc,&count,&sub));
        check(comm,count==static_cast<PetscInt>(plan.children.size()),"Wrong root block count");
        EONSIM_PETSC(KSPGetPC(sub[0],&dynamics_pc));
        EONSIM_PETSC(PCFieldSplitGetSubKSP(dynamics_pc,&inner_count,&inner));
        check(comm,inner_count==2,"Missing pressure Schur block");
        Mat approx=nullptr;
        EONSIM_PETSC(KSPGetOperators(inner[1],nullptr,&approx));
        EONSIM_PETSC(PetscFree(inner));
        EONSIM_PETSC(PetscFree(sub));
        std::vector<std::vector<PetscInt>> groups{{0,2},{1}};
        if(recipe=="hybrid") groups.insert(groups.end(),{{8,9,10},{11,12},{13}});
        PetscOwner<Vec,VecDestroy> rhs,sol,exact,defect;
        EONSIM_PETSC(MatCreateVecs(matrix,sol.put(),rhs.put()));
        EONSIM_PETSC(VecDuplicate(sol.get(),exact.put()));
        EONSIM_PETSC(VecDuplicate(rhs.get(),defect.put()));
        EONSIM_PETSC(VecSet(exact.get(),1.));
        for(int phase=0;phase<2;++phase) {
            const double factor=phase?2.:1.;
            if(phase) {
                EONSIM_PETSC(MatScale(matrix,2.));
                updates.refresh(matrix);
            }
            PetscInt first,last; EONSIM_PETSC(MatGetOwnershipRange(approx,&first,&last));
            bool correct=true;
            for(PetscInt i=first;i<last;++i) for(PetscInt j=0;j<2;++j) {
                double v=0;
                EONSIM_PETSC(MatGetValues(approx,1,&i,1,&j,&v));
                const double expected=factor*schur_entry(pressure.at(i),pressure.at(j),groups);
                correct=correct&&std::abs(v-expected)<1e-11*(1+std::abs(expected));
            }
            check(comm,correct,"Nodal Schur cofactor oracle or numeric refresh failed");
            EONSIM_PETSC(MatMult(matrix,exact.get(),rhs.get()));
            EONSIM_PETSC(VecSet(sol.get(),0.));
            EONSIM_PETSC(KSPSolve(outer.get(),rhs.get(),sol.get()));
            KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(outer.get(),&reason));
            EONSIM_PETSC(MatMult(matrix,sol.get(),defect.get()));
            EONSIM_PETSC(VecAXPY(defect.get(),-1,rhs.get()));
            PetscReal norm,bnorm;
            EONSIM_PETSC(VecNorm(defect.get(),NORM_2,&norm)); EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&bnorm));
            check(comm,reason>0&&norm<=1e-11*bnorm,"Nodal/coupled solve failed independent residual check");
        }
        EONSIM_PETSC(MatScale(matrix,.5));
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_plan_velocity_solver"));
    }
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_plan_schur_approx"));
}
// This small dense reference eliminates the complete fluid saddle-point block.
// It is deliberately independent of PETSc's Schur objects and PC-tree indices.
std::vector<double> dense_solve(std::vector<std::vector<double>> a,std::vector<double> b) {
    const auto n=b.size();
    for(std::size_t k=0;k<n;++k) {
        std::size_t pivot=k;
        for(std::size_t i=k+1;i<n;++i) if(std::abs(a[i][k])>std::abs(a[pivot][k])) pivot=i;
        if(std::abs(a[pivot][k])<1e-14) throw std::runtime_error("Singular independent dense oracle");
        std::swap(a[k],a[pivot]); std::swap(b[k],b[pivot]);
        for(std::size_t i=k+1;i<n;++i) {
            const double factor=a[i][k]/a[k][k];
            for(std::size_t j=k+1;j<n;++j) a[i][j]-=factor*a[k][j];
            b[i]-=factor*b[k];
        }
    }
    for(std::size_t k=n;k-->0;) {
        for(std::size_t j=k+1;j<n;++j) b[k]-=a[k][j]*b[j];
        b[k]/=a[k][k];
    }
    return b;
}
double added_mass_entry(PetscInt i,PetscInt j,int phase) {
    const auto pressure=[](PetscInt row){return row==3?0:row==7?1:-1;};
    const auto pi=pressure(i),pj=pressure(j);
    if(i<3&&j<3) return i==j?4.+i+.4*phase:.12+.03*(i+j);
    if(i<3&&pj>=0) return .3+.11*i+.13*pj+.04*phase;
    if(pi>=0&&j<3) return .3+.11*j+.13*pi+.04*phase;
    if(pi>=0&&pj>=0) return pi==pj?-.2-.1*pi-.03*phase:-.02;
    if(i>=8&&j>=8) return (i==j?7.+.2*phase:0.)+.03*(i+j-14);
    if(i>=8&&pj>=0) return .15*(i-7)*(pj+1)+.02*phase;
    if(pi>=0&&j>=8) return .15*(j-7)*(pi+1)+.02*phase;
    if(i>=8&&j<3) return .025*(i-7)*(j+1);
    if(i<3&&j>=8) return .025*(j-7)*(i+1);
    const bool mi=i>=4&&i<=6,mj=j>=4&&j<=6;
    if(mi&&mj) return i==j?2.+.1*phase:.01;
    return .002*(1+(i+2*j)%5);
}
void verify_added_mass(MPI_Comm comm,const AlgebraLayout& original) {
    auto layout=original;
    for(PetscInt i=0;i<layout.owned;++i)
        if(layout.begin+i==7) layout.owned_semantics[i].kind=DofEntity::boundary;
    ScopedOptions options;
    options.set("-pc_plan_schur_approx","nodal");
    options.set("-added_oracle_fieldsplit_dynamics_fieldsplit_fluid_ksp_type","fgmres");
    options.set("-added_oracle_fieldsplit_dynamics_fieldsplit_fluid_ksp_rtol","1e-13");
    options.set("-added_oracle_fieldsplit_dynamics_fieldsplit_fluid_ksp_max_it","100");
    options.set("-added_oracle_fieldsplit_dynamics_fieldsplit_structure_ksp_rtol","1e-12");
    options.set("-added_oracle_fieldsplit_dynamics_fieldsplit_structure_ksp_max_it","100");
    for(const std::string role:{"inner","upper"}) {
        const auto base="-added_oracle_fieldsplit_dynamics_fieldsplit_structure_"+role+"_";
        options.set(base+"ksp_type","fgmres");
        options.set(base+"ksp_rtol",role=="inner"?"2e-13":"3e-13");
        options.set(base+"ksp_max_it",role=="inner"?"101":"102");
    }
    auto plan=make_pc_plan(comm,layout,"added_mass");
    PcSchurUpdates updates;
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,layout.owned,layout.owned,14,14,layout.owned,nullptr,
                             14-layout.owned,nullptr,matrix.put()));
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),"added_oracle_"));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
    const std::vector<PetscInt> fluid{0,1,2,3,7},velocity{0,1,2};
    for(int phase=0;phase<2;++phase) {
        for(PetscInt i=layout.begin;i<layout.begin+layout.owned;++i) for(PetscInt j=0;j<14;++j)
            EONSIM_PETSC(MatSetValue(matrix.get(),i,j,added_mass_entry(i,j,phase),INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
        if(!phase) configure_pc_plan(comm,solver.get(),matrix.get(),plan,&updates);
        else updates.refresh(matrix.get());
        solve_exact(comm,solver.get(),matrix.get(),phase?"added_mass_refreshed":"added_mass_initial");
        const auto dynamics=child_solver(comm,solver.get(),0);
        PC dynamics_pc; EONSIM_PETSC(KSPGetPC(dynamics,&dynamics_pc));
        Mat structural_schur=nullptr; KSP fluid_inner=nullptr;
        EONSIM_PETSC(PCFieldSplitSchurGetS(dynamics_pc,&structural_schur));
        EONSIM_PETSC(MatSchurComplementGetKSP(structural_schur,&fluid_inner));
        EONSIM_PETSC(PCFieldSplitSchurRestoreS(dynamics_pc,&structural_schur));
        const std::array<KSP,3> fluid_solvers{{child_solver(comm,dynamics,0,true),fluid_inner,
                                             child_solver(comm,dynamics,2,true)}};
        Mat shared_pressure=nullptr;
        bool shared=updates.refreshers.size()==1&&fluid_solvers[0]!=fluid_solvers[1]&&
                    fluid_solvers[0]!=fluid_solvers[2]&&fluid_solvers[1]!=fluid_solvers[2];
        for(int role=0;role<3;++role) {
            const auto fluid_solver=fluid_solvers[role];
            const char* prefix=nullptr; KSPType type=nullptr; PC pc; PCType pc_type=nullptr;
            PetscReal rtol=0; PetscInt max_it=0;
            EONSIM_PETSC(KSPGetOptionsPrefix(fluid_solver,&prefix));
            EONSIM_PETSC(KSPGetType(fluid_solver,&type));
            EONSIM_PETSC(KSPGetPC(fluid_solver,&pc)); EONSIM_PETSC(PCGetType(pc,&pc_type));
            EONSIM_PETSC(KSPGetTolerances(fluid_solver,&rtol,nullptr,nullptr,&max_it));
            const std::string expected="added_oracle_fieldsplit_dynamics_fieldsplit_"+
                std::string(role==0?"fluid_":role==1?"structure_inner_":"structure_upper_");
            shared=shared&&std::string(prefix?prefix:"")==expected&&std::string(type)==KSPFGMRES&&
                   std::string(pc_type)==PCFIELDSPLIT&&std::abs(rtol-(role+1)*1e-13)<1e-25&&max_it==100+role;
            const auto pressure_solver=child_solver(comm,fluid_solver,1,true);
            Mat p=nullptr; EONSIM_PETSC(KSPGetOperators(pressure_solver,nullptr,&p));
            if(!shared_pressure) shared_pressure=p;
            else shared=shared&&p==shared_pressure;
        }
        check(comm,shared,"Independent full-fluid solver overrides or shared nodal Schur refresh were lost");
        const auto structure=child_solver(comm,dynamics,1,true);
        Mat schur=nullptr,preconditioner=nullptr;
        EONSIM_PETSC(KSPGetOperators(structure,&schur,&preconditioner));
        PetscOwner<Vec,VecDestroy> basis,column;
        EONSIM_PETSC(MatCreateVecs(schur,basis.put(),column.put()));
        PetscInt begin,end; EONSIM_PETSC(VecGetOwnershipRange(column.get(),&begin,&end));
        bool correct=true,pressure_matters=false;
        for(PetscInt j=0;j<6;++j) {
            std::vector<std::vector<double>> f(5,std::vector<double>(5));
            std::vector<double> rhs(5);
            for(int k=0;k<5;++k) {
                rhs[k]=added_mass_entry(fluid[k],j+8,phase);
                for(int l=0;l<5;++l) f[k][l]=added_mass_entry(fluid[k],fluid[l],phase);
            }
            const auto response=dense_solve(f,rhs);
            f.resize(3); rhs.resize(3); for(auto& row:f) row.resize(3);
            const auto velocity_only=dense_solve(f,rhs);
            EONSIM_PETSC(VecSet(basis.get(),0.));
            if(j>=begin&&j<end) EONSIM_PETSC(VecSetValue(basis.get(),j,1.,INSERT_VALUES));
            EONSIM_PETSC(VecAssemblyBegin(basis.get())); EONSIM_PETSC(VecAssemblyEnd(basis.get()));
            EONSIM_PETSC(MatMult(schur,basis.get(),column.get()));
            const PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArrayRead(column.get(),&values));
            for(PetscInt i=begin;i<end;++i) {
                double expected=added_mass_entry(i+8,j+8,phase),incomplete=expected;
                for(int k=0;k<5;++k) expected-=added_mass_entry(i+8,fluid[k],phase)*response[k];
                for(int k=0;k<3;++k) incomplete-=added_mass_entry(i+8,velocity[k],phase)*velocity_only[k];
                correct=correct&&std::abs(values[i-begin]-expected)<1e-9;
                pressure_matters=pressure_matters||std::abs(expected-incomplete)>1e-3;
                double p=0; EONSIM_PETSC(MatGetValues(preconditioner,1,&i,1,&j,&p));
                correct=correct&&std::abs(p-added_mass_entry(i+8,j+8,phase))<1e-12;
            }
            EONSIM_PETSC(VecRestoreArrayRead(column.get(),&values));
        }
        int local=pressure_matters,any=0; MPI_Allreduce(&local,&any,1,MPI_INT,MPI_MAX,comm);
        check(comm,correct&&any,"Added-mass Schur omitted full-fluid pressure response or reused stale values");
    }
}
// A separate nonsymmetric fixture: neither B/C nor E/G are transposes.
// The optional constraints replace rows only, matching the physical assembly.
double structural_nodal_entry(PetscInt i,PetscInt j,int phase,bool partial) {
    if(partial&&(i==0||i==13)) return i==j?1.:0.;
    const bool fi=i<4||i==7,fj=j<4||j==7;
    double value=added_mass_entry(i,j,phase);
    if(fi&&fj&&i!=j) value+=.017*(i+1)-.011*(j+1);
    if(fi&&j>=8) value+=.009*(i+1)+.004*(j-7)*(j-7)+.003*phase*(i+j);
    if(i>=8&&fj) value+=-.006*(j+1)+.013*(i-7)+.002*phase*(2*i+j);
    if(i>=8&&j>=8&&i!=j) value+=.002*(i-8)-.003*(j-8);
    return value;
}
// Root indices below are hand-written, not taken from PcBlock.fluid_groups.
std::vector<double> structural_column(const std::vector<std::vector<PetscInt>>& groups,
                                      PetscInt column,int phase,bool partial) {
    std::vector<double> result(6);
    for(int i=0;i<6;++i) result[i]=structural_nodal_entry(i+8,column+8,phase,partial);
    for(const auto& group:groups) {
        std::vector<std::vector<double>> block(group.size(),std::vector<double>(group.size()));
        std::vector<double> rhs(group.size());
        for(std::size_t i=0;i<group.size();++i) {
            rhs[i]=structural_nodal_entry(group[i],column+8,phase,partial);
            for(std::size_t j=0;j<group.size();++j)
                block[i][j]=structural_nodal_entry(group[i],group[j],phase,partial);
        }
        const auto response=dense_solve(block,rhs);
        for(int i=0;i<6;++i) for(std::size_t k=0;k<group.size();++k)
            result[i]-=structural_nodal_entry(i+8,group[k],phase,partial)*response[k];
    }
    return result;
}
void verify_structural_nodal(MPI_Comm comm,const AlgebraLayout& original) {
    const std::vector<PetscInt> fluid{0,1,2,3,7};
    for(int profile=0;profile<3;++profile) {
        const bool partial=profile==1,scaled=profile==2;
        auto layout=original;
        for(PetscInt i=0;i<layout.owned;++i) {
            const auto row=layout.begin+i;
            if(partial&&row==1) layout.owned_semantics[i].mode=1;
            if(row==7) {
                // An RCR-like scalar may share the vertex's numeric entity ID.
                auto& key=layout.owned_semantics[i];
                key.entity=10; key.kind=DofEntity::boundary; key.space=0;
            }
        }
        const std::vector<std::vector<PetscInt>> groups=partial?
            std::vector<std::vector<PetscInt>>{{0,2,3},{1},{7}}:
            std::vector<std::vector<PetscInt>>{{0,1,2,3},{7}};
        auto no_boundary=groups; no_boundary.pop_back();
        const std::vector<std::vector<PetscInt>> velocity=partial?
            std::vector<std::vector<PetscInt>>{{0,2},{1}}:
            std::vector<std::vector<PetscInt>>{{0,1,2}};
        const std::string prefix=profile==0?"struct_full_":partial?"struct_partial_":"struct_scaled_";
        const std::string structural="-"+prefix+"fieldsplit_dynamics_fieldsplit_structure_";
        ScopedOptions options;
        options.set("-pc_plan_structure_approx","nodal");
        options.set("-pc_plan_schur_approx",scaled?"diagonal":"nodal");
        if(!scaled) {
            // Tighten only F^{-1} for an independent implicit-A oracle. The
            // full profile deliberately keeps the new structural default.
            for(const auto& base:std::vector<std::string>{
                "-"+prefix+"fieldsplit_dynamics_fieldsplit_fluid_",
                structural+"inner_",structural+"upper_"}) {
                options.set(base+"ksp_type","fgmres");
                options.set(base+"ksp_rtol","1e-13");
                options.set(base+"ksp_max_it","100");
            }
        }
        if(partial) {
            options.set(structural+"ksp_type","fgmres");
            options.set(structural+"ksp_rtol","1e-12");
            options.set(structural+"ksp_max_it","100");
        }
        if(partial||scaled) options.set(structural+"pc_type","jacobi");
        if(scaled) {
            const std::string base="-"+prefix+"fieldsplit_dynamics_fieldsplit_fluid_";
            options.set(base+"ksp_type","preonly");
            options.set(base+"fieldsplit_velocity_pc_type","jacobi");
            options.set(base+"fieldsplit_pressure_pc_type","jacobi");
        }
        // F'=R F C, E'=R E and G'=G C leave both structural complements
        // invariant. Evaluate the reference in original units, independently
        // of the production equilibration/inversion algorithm.
        const auto coefficient=[&](PetscInt i,PetscInt j,int phase) {
            const std::array<double,5> rows{{1e-8,1e4,1e-2,1e8,1e-4}};
            const std::array<double,5> columns{{1e6,1e-6,1e2,1e-4,1e4}};
            double value=structural_nodal_entry(i,j,phase,partial);
            if(scaled) {
                const auto row=std::find(fluid.begin(),fluid.end(),i),column=std::find(fluid.begin(),fluid.end(),j);
                if(row!=fluid.end()) value*=rows[row-fluid.begin()];
                if(column!=fluid.end()) value*=columns[column-fluid.begin()];
            }
            return value;
        };
        PetscOwner<Mat,MatDestroy> matrix;
        EONSIM_PETSC(MatCreateAIJ(comm,layout.owned,layout.owned,14,14,layout.owned,nullptr,
                                 14-layout.owned,nullptr,matrix.put()));
        const auto fill=[&](int phase) {
            for(PetscInt i=layout.begin;i<layout.begin+layout.owned;++i) for(PetscInt j=0;j<14;++j)
                EONSIM_PETSC(MatSetValue(matrix.get(),i,j,coefficient(i,j,phase),INSERT_VALUES));
            EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
        };
        PetscOwner<KSP,KSPDestroy> solver;
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
        EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
        const auto plan=make_pc_plan(comm,layout,"added_mass");
        PcSchurUpdates updates;
        Mat first_p=nullptr;
        for(int phase=0;phase<2;++phase) {
            fill(phase);
            if(!phase) configure_pc_plan(comm,solver.get(),matrix.get(),plan,&updates);
            else updates.refresh(matrix.get());
            if(!scaled) solve_exact(comm,solver.get(),matrix.get(),partial?"structural_nodal_partial":"structural_nodal_default");
            // Extreme mixed units test only the invariant preconditioner, not
            // whether unscaled Krylov can solve an arbitrarily conditioned J.
            const auto dynamics=child_solver(comm,solver.get(),0);
            const auto structure=child_solver(comm,dynamics,1,true);
            Mat a=nullptr,p=nullptr,root_a=nullptr;
            EONSIM_PETSC(KSPGetOperators(structure,&a,&p));
            EONSIM_PETSC(KSPGetOperators(solver.get(),&root_a,nullptr));
            if(!first_p) first_p=p;
            MatType type=nullptr; KSPType ksp_type=nullptr; PCType pc_type=nullptr;
            PC pc; PetscBool use_a=PETSC_TRUE;
            EONSIM_PETSC(MatGetType(a,&type)); EONSIM_PETSC(KSPGetType(structure,&ksp_type));
            EONSIM_PETSC(KSPGetPC(structure,&pc)); EONSIM_PETSC(PCGetType(pc,&pc_type));
            EONSIM_PETSC(PCGetUseAmat(pc,&use_a));
            check(comm,a!=p&&p==first_p&&root_a==matrix.get()&&std::string(type)==MATSCHURCOMPLEMENT&&
                       std::string(ksp_type)==(partial?KSPFGMRES:KSPPREONLY)&&!use_a&&
                       std::string(pc_type)==(profile==0?PCGAMG:PCJACOBI)&&
                       updates.refreshers.size()==static_cast<std::size_t>(scaled?1:2),
                  "Nodal structure replaced A, lost USER P reuse, or changed default/override solver semantics");
            PetscInt begin,end;
            EONSIM_PETSC(MatGetOwnershipRange(p,&begin,&end));
            std::vector<std::vector<double>> expected_p(6,std::vector<double>(6)),expected_a=expected_p;
            PetscOwner<Vec,VecDestroy> basis,action;
            EONSIM_PETSC(MatCreateVecs(a,basis.put(),action.put()));
            bool correct=true; int effects[3]{};
            for(PetscInt j=0;j<6;++j) {
                const auto expected=structural_column(groups,j,phase,partial);
                const auto full=structural_column({fluid},j,phase,partial);
                const auto without_pressure=structural_column(velocity,j,phase,partial);
                const auto without_boundary=structural_column(no_boundary,j,phase,partial);
                for(int i=0;i<6;++i) { expected_p[i][j]=expected[i]; expected_a[i][j]=full[i]; }
                if(!scaled) {
                    EONSIM_PETSC(VecSet(basis.get(),0.));
                    if(j>=begin&&j<end) EONSIM_PETSC(VecSetValue(basis.get(),j,1.,INSERT_VALUES));
                    EONSIM_PETSC(VecAssemblyBegin(basis.get())); EONSIM_PETSC(VecAssemblyEnd(basis.get()));
                    EONSIM_PETSC(MatMult(a,basis.get(),action.get()));
                }
                const PetscScalar* values=nullptr;
                if(!scaled) EONSIM_PETSC(VecGetArrayRead(action.get(),&values));
                for(PetscInt i=begin;i<end;++i) {
                    double actual=0; EONSIM_PETSC(MatGetValues(p,1,&i,1,&j,&actual));
                    correct=correct&&std::abs(actual-expected[i])<3e-11*(1+std::abs(expected[i]));
                    if(!scaled) correct=correct&&std::abs(values[i-begin]-full[i])<1e-9*(1+std::abs(full[i]));
                    effects[0]=effects[0]||std::abs(expected[i]-without_pressure[i])>1e-3;
                    effects[1]=effects[1]||std::abs(expected[i]-without_boundary[i])>1e-3;
                    effects[2]=effects[2]||std::abs(expected[i]-full[i])>1e-3;
                }
                if(!scaled) EONSIM_PETSC(VecRestoreArrayRead(action.get(),&values));
            }
            int global_effects[3]{}; MPI_Allreduce(effects,global_effects,3,MPI_INT,MPI_MAX,comm);
            check(comm,correct&&global_effects[0]&&global_effects[1]&&global_effects[2],
                  "Independent structural Schur oracle, boundary pressure feedback, or mixed scaling failed");
            // Exercise the real default PREONLY/GAMG action as well as a simple
            // independent Jacobi action and the explicit iterative override.
            for(PetscInt i=begin;i<end;++i) EONSIM_PETSC(VecSetValue(basis.get(),i,.5+.25*i,INSERT_VALUES));
            EONSIM_PETSC(VecAssemblyBegin(basis.get())); EONSIM_PETSC(VecAssemblyEnd(basis.get()));
            EONSIM_PETSC(VecSet(action.get(),0.)); EONSIM_PETSC(KSPSolve(structure,basis.get(),action.get()));
            KSPConvergedReason reason; EONSIM_PETSC(KSPGetConvergedReason(structure,&reason));
            correct=reason>0;
            if(profile==0) {
                PetscOwner<Vec,VecDestroy> applied;
                EONSIM_PETSC(VecDuplicate(action.get(),applied.put())); EONSIM_PETSC(PCApply(pc,basis.get(),applied.get()));
                EONSIM_PETSC(VecAXPY(applied.get(),-1.,action.get()));
                PetscReal difference=0; EONSIM_PETSC(VecNorm(applied.get(),NORM_INFINITY,&difference));
                PetscInt iterations=0; EONSIM_PETSC(KSPGetIterationNumber(structure,&iterations));
                correct=correct&&difference<1e-11&&iterations==1;
            } else {
                std::vector<double> rhs(6); for(int i=0;i<6;++i) rhs[i]=.5+.25*i;
                const auto exact=partial?dense_solve(expected_a,rhs):rhs;
                const PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArrayRead(action.get(),&values));
                for(PetscInt i=begin;i<end;++i) {
                    const auto expected=partial?exact[i]:rhs[i]/expected_p[i][i];
                    correct=correct&&std::abs(values[i-begin]-expected)<1e-9*(1+std::abs(expected));
                }
                EONSIM_PETSC(VecRestoreArrayRead(action.get(),&values));
            }
            for(PetscInt i=layout.begin;i<layout.begin+layout.owned;++i) for(PetscInt j=0;j<14;++j) {
                double value=0; EONSIM_PETSC(MatGetValues(matrix.get(),1,&i,1,&j,&value));
                correct=correct&&value==coefficient(i,j,phase);
            }
            check(comm,correct,"Structural PC action ignored USER P, changed physical J, or lost explicit KSP override");
        }
        if(scaled) for(int fault=0;fault<2;++fault) {
            const double invalid=fault?std::numeric_limits<double>::quiet_NaN():0.;
            // A pressure-only local block must fail even when global F could
            // remain invertible through its off-diagonal velocity coupling.
            if(layout.begin<=7&&7<layout.begin+layout.owned)
                EONSIM_PETSC(MatSetValue(matrix.get(),7,7,invalid,INSERT_VALUES));
            EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
            bool rejected=false;
            try {updates.refresh(matrix.get());}
            catch(const std::runtime_error& error) {
                rejected=std::string(error.what()).find("nodal fluid block")!=std::string::npos;
            }
            check(comm,rejected,"Singular/nonfinite local fluid response was silently accepted");
            fill(fault+2); updates.refresh(matrix.get());
            const auto structure=child_solver(comm,child_solver(comm,solver.get(),0),1,true);
            Mat recovered=nullptr; EONSIM_PETSC(KSPGetOperators(structure,nullptr,&recovered));
            PetscInt begin,end; EONSIM_PETSC(MatGetOwnershipRange(recovered,&begin,&end));
            bool correct=recovered==first_p;
            for(PetscInt j=0;j<6;++j) {
                const auto expected=structural_column(groups,j,fault+2,partial);
                for(PetscInt i=begin;i<end;++i) {
                    double actual=0; EONSIM_PETSC(MatGetValues(recovered,1,&i,1,&j,&actual));
                    correct=correct&&std::abs(actual-expected[i])<3e-11*(1+std::abs(expected[i]));
                }
            }
            check(comm,correct,"Failed structural refresh lost recovery values or the reusable USER matrix");
        }
    }
}
void verify_auxiliary_solvers(MPI_Comm comm,const AlgebraLayout& layout,Mat matrix) {
    for(int variant=0;variant<4;++variant) {
        const bool legacy=variant==1,twolevel=variant==2,gamg=variant==3,multilevel=twolevel||gamg;
        ScopedOptions options;
        const std::string root_prefix=legacy?"aux_legacy_":twolevel?"aux_twolevel_":gamg?"aux_gamg_":"aux_semantic_";
        const std::string prefix=root_prefix+(legacy?"fieldsplit_flow_":"fieldsplit_dynamics_");
        if(!legacy) options.set("-pc_plan_velocity_solver",twolevel?"twolevel":gamg?"gamg":"coupled");
        auto geometric_layout=layout;
        if(twolevel) {
            options.set("-pc_plan_velocity_coarse_space","rigid");
            geometric_layout.owned_reference_coordinates.clear();
            for(const auto& key:geometric_layout.owned_semantics)
                geometric_layout.owned_reference_coordinates.push_back(
                    {{key.entity==20?1.:0.,key.entity==30?1.:0.,0.}});
        }
        if(multilevel) {
            const auto base="-"+prefix+"fieldsplit_velocity_";
            options.set(base+"ksp_type","fgmres");
            options.set(base+"ksp_rtol","1e-12");
            options.set(base+"ksp_max_it","43");
        }
        for(const auto& role:{std::string("inner"),std::string("upper")}) {
            const std::string base="-"+prefix+"fieldsplit_pressure_"+role+"_";
            options.set(base+"ksp_type",multilevel?"fgmres":"gmres");
            options.set(base+"pc_type",twolevel?"mg":gamg?"gamg":"jacobi");
            options.set(base+"ksp_rtol",role=="inner"?"1e-11":"1e-9");
            options.set(base+"ksp_max_it",role=="inner"?"37":"41");
        }
        PetscOwner<KSP,KSPDestroy> solver;
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),root_prefix.c_str()));
        EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
        if(legacy) configure_schur_solver(comm,solver.get(),layout,matrix);
        else configure_pc_plan(comm,solver.get(),matrix,make_pc_plan(comm,geometric_layout,"hybrid"));
        const auto block=child_solver(comm,solver.get(),0);
        PC pc; EONSIM_PETSC(KSPGetPC(block,&pc));
        PetscInt count=0; KSP* sub=nullptr;
        EONSIM_PETSC(PCFieldSplitSchurGetSubKSP(pc,&count,&sub));
        check(comm,count==3,"FULL Schur did not create an independent upper solver");
        Mat schur=nullptr; KSP inner=nullptr;
        EONSIM_PETSC(PCFieldSplitSchurGetS(pc,&schur));
        EONSIM_PETSC(MatSchurComplementGetKSP(schur,&inner));
        EONSIM_PETSC(PCFieldSplitSchurRestoreS(pc,&schur));
        bool correct=inner!=sub[0]&&inner!=sub[2]&&sub[0]!=sub[2];
        if(multilevel) {
            const char* actual_prefix=nullptr; KSPType type=nullptr; PCType pc_type=nullptr;
            PC main_pc; PetscInt max_it=0,levels=0; PetscReal rtol=0;
            EONSIM_PETSC(KSPGetOptionsPrefix(sub[0],&actual_prefix)); EONSIM_PETSC(KSPGetType(sub[0],&type));
            EONSIM_PETSC(KSPGetPC(sub[0],&main_pc)); EONSIM_PETSC(PCGetType(main_pc,&pc_type));
            EONSIM_PETSC(KSPGetTolerances(sub[0],&rtol,nullptr,nullptr,&max_it));
            EONSIM_PETSC(PCMGGetLevels(main_pc,&levels));
            correct=correct&&std::string(actual_prefix?actual_prefix:"")==prefix+"fieldsplit_velocity_"&&
                    std::string(type)==KSPFGMRES&&std::string(pc_type)==(twolevel?PCMG:PCGAMG)&&
                    (twolevel?levels==2:levels>=1)&&
                    std::abs(rtol-1e-12)<1e-15&&max_it==43;
        }
        for(int i=0;i<2;++i) {
            const auto ksp=i?sub[2]:inner;
            const char* actual_prefix=nullptr; KSPType type=nullptr; PCType pc_type=nullptr;
            PC inverse_pc; PetscInt max_it=0; PetscReal rtol=0;
            EONSIM_PETSC(KSPGetOptionsPrefix(ksp,&actual_prefix)); EONSIM_PETSC(KSPGetType(ksp,&type));
            EONSIM_PETSC(KSPGetPC(ksp,&inverse_pc)); EONSIM_PETSC(PCGetType(inverse_pc,&pc_type));
            EONSIM_PETSC(KSPGetTolerances(ksp,&rtol,nullptr,nullptr,&max_it));
            correct=correct&&std::string(actual_prefix?actual_prefix:"")==prefix+"fieldsplit_pressure_"+(i?"upper_":"inner_")&&
                std::string(type)==(multilevel?KSPFGMRES:KSPGMRES)&&
                std::string(pc_type)==(twolevel?PCMG:gamg?PCGAMG:PCJACOBI)&&
                std::abs(rtol-(i?1e-9:1e-11))<1e-15&&max_it==(i?41:37);
            if(gamg) {
                Mat operator_matrix=nullptr; MatNullSpace space=nullptr;
                EONSIM_PETSC(KSPGetOperators(ksp,&operator_matrix,nullptr));
                EONSIM_PETSC(MatGetNearNullSpace(operator_matrix,&space));
                correct=correct&&space!=nullptr;
            }
            if(twolevel) {
                PetscInt levels=0; EONSIM_PETSC(PCMGGetLevels(inverse_pc,&levels));
                correct=correct&&levels==2;
            }
        }
        EONSIM_PETSC(PetscFree(sub));
        check(comm,correct,"Schur auxiliary solvers lost prefixes, independent identity, or user settings");
        solve_exact(comm,solver.get(),matrix,legacy?"legacy_auxiliary":twolevel?"twolevel_auxiliary":gamg?"gamg_auxiliary":"hybrid_auxiliary");
        // A bounded inner action is allowed to reach ITS. A genuine breakdown
        // must mark its enclosing fieldsplit, even if the iterate is finite.
        EONSIM_PETSC(PCFieldSplitSchurGetS(pc,&schur));
        PetscOwner<Vec,VecDestroy> input,action;
        EONSIM_PETSC(MatCreateVecs(schur,input.put(),action.put()));
        EONSIM_PETSC(VecSet(input.get(),1.));
        PCFailedReason failure; KSPConvergedReason reason;
        if(!multilevel) {
            // Jacobi makes this bounded action inexact. A two-level cycle may
            // solve the tiny oracle in one iteration, so retain the ITS probe
            // on these existing fixtures rather than require artificial work.
            EONSIM_PETSC(KSPSetTolerances(inner,1e-30,1e-30,PETSC_DEFAULT,1));
            EONSIM_PETSC(PCSetFailedReason(pc,PC_NOERROR));
            EONSIM_PETSC(MatMult(schur,input.get(),action.get()));
            EONSIM_PETSC(PCGetFailedReason(pc,&failure));
            EONSIM_PETSC(KSPGetConvergedReason(inner,&reason));
            check(comm,reason==KSP_DIVERGED_ITS&&failure==PC_NOERROR,
                  "Intentional bounded Schur inner solve was classified as a PC failure");
        }
        // Every solver here is explicitly iterative; PREONLY would not call
        // this convergence callback and is covered by the real PC fault test.
        EONSIM_PETSC(KSPSetConvergenceTest(inner,
            [](KSP,PetscInt,PetscReal,KSPConvergedReason* why,void*) -> PetscErrorCode {
                *why=KSP_DIVERGED_BREAKDOWN; return 0;
            },nullptr,nullptr));
        EONSIM_PETSC(PCSetFailedReason(pc,PC_NOERROR));
        EONSIM_PETSC(MatMult(schur,input.get(),action.get()));
        EONSIM_PETSC(PCGetFailedReason(pc,&failure));
        EONSIM_PETSC(PCFieldSplitSchurRestoreS(pc,&schur));
        check(comm,failure!=PC_NOERROR,"Schur MatMult hid a genuine inner solver breakdown");
    }
}
void verify_twolevel(MPI_Comm comm,const AlgebraLayout& layout) {
    int size=0; MPI_Comm_size(comm,&size);
    ScopedOptions options; options.set("-pc_plan_velocity_solver","twolevel");
    const std::vector<PetscInt> velocity{0,1,2,8,9,10,11,12,13};
    const std::vector<std::vector<PetscInt>> groups=size==4?
        std::vector<std::vector<PetscInt>>{{0},{1},{2},{8},{9},{10},{11},{12}}:
        std::vector<std::vector<PetscInt>>{{0},{1},{2},{8,11},{9,12},{10}};
    const auto coefficient=[](PetscInt i,PetscInt j,int phase) {
        if(i==13) return i==j?1.:0.; // A constrained velocity component.
        return entry(i,j)+phase*((i==j?i+1.:0.)+.003*(i+1)*(j+1));
    };
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,layout.owned,layout.owned,14,14,layout.owned,nullptr,
                             14-layout.owned,nullptr,matrix.put()));
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
    const auto plan=make_pc_plan(comm,layout,"hybrid");
    for(int phase=0;phase<2;++phase) {
        for(PetscInt i=layout.begin;i<layout.begin+layout.owned;++i) for(PetscInt j=0;j<14;++j)
            EONSIM_PETSC(MatSetValue(matrix.get(),i,j,coefficient(i,j,phase),INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
        if(!phase) configure_pc_plan(comm,solver.get(),matrix.get(),plan);
        solve_exact(comm,solver.get(),matrix.get(),phase?"twolevel_refreshed":"twolevel_initial");
        const auto dynamics=child_solver(comm,solver.get(),0);
        const auto momentum=child_solver(comm,dynamics,0,true);
        PC pc; EONSIM_PETSC(KSPGetPC(momentum,&pc));
        KSPType type=nullptr; PCType pc_type=nullptr; PetscReal rtol=0;
        PetscInt levels=0,max_it=0; EONSIM_PETSC(PCMGGetLevels(pc,&levels));
        EONSIM_PETSC(KSPGetType(momentum,&type)); EONSIM_PETSC(PCGetType(pc,&pc_type));
        EONSIM_PETSC(KSPGetTolerances(momentum,&rtol,nullptr,nullptr,&max_it));
        check(comm,levels==2&&std::string(type)==KSPPREONLY&&std::string(pc_type)==PCMG&&
                   std::abs(rtol-1e-4)<1e-15&&max_it==20,
              "Coupled two-level default lost PREONLY, its coarse correction, or its explicit-override budget");
        Mat interpolation=nullptr,coarse_matrix=nullptr; KSP coarse=nullptr;
        EONSIM_PETSC(PCMGGetInterpolation(pc,1,&interpolation));
        EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
        EONSIM_PETSC(KSPGetOperators(coarse,&coarse_matrix,nullptr));
        PetscInt rows=0,columns=0,begin=0,end=0;
        EONSIM_PETSC(MatGetSize(interpolation,&rows,&columns));
        bool correct=rows==9&&columns==static_cast<PetscInt>(groups.size());
        EONSIM_PETSC(MatGetOwnershipRange(interpolation,&begin,&end));
        for(PetscInt i=begin;i<end;++i) for(PetscInt j=0;j<columns;++j) {
            double actual=0; EONSIM_PETSC(MatGetValues(interpolation,1,&i,1,&j,&actual));
            const auto& g=groups[j];
            const double expected=std::find(g.begin(),g.end(),velocity.at(i))==g.end()?0.:1/std::sqrt(double(g.size()));
            correct=correct&&std::abs(actual-expected)<1e-12;
        }
        EONSIM_PETSC(MatGetOwnershipRange(coarse_matrix,&begin,&end));
        for(PetscInt i=begin;i<end;++i) for(PetscInt j=0;j<columns;++j) {
            double actual=0,expected=0;
            EONSIM_PETSC(MatGetValues(coarse_matrix,1,&i,1,&j,&actual));
            for(auto a:groups[i]) for(auto b:groups[j]) expected+=coefficient(a,b,phase);
            expected/=std::sqrt(double(groups[i].size()*groups[j].size()));
            correct=correct&&std::abs(actual-expected)<1e-10;
        }
        check(comm,correct,"Two-level interpolation, constraint handling or Galerkin numerical update failed");
        verify_preonly_action(comm,momentum);
    }
    // Recreate the solver for a completely constrained operator: no coarse
    // modes exist, but the same public option must remain well-defined.
    EONSIM_PETSC(MatZeroEntries(matrix.get()));
    for(PetscInt i=layout.begin;i<layout.begin+layout.owned;++i)
        EONSIM_PETSC(MatSetValue(matrix.get(),i,i,1.,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    PetscOwner<KSP,KSPDestroy> identity_solver;
    EONSIM_PETSC(KSPCreate(comm,identity_solver.put()));
    EONSIM_PETSC(KSPSetType(identity_solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(identity_solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
    configure_pc_plan(comm,identity_solver.get(),matrix.get(),plan);
    solve_exact(comm,identity_solver.get(),matrix.get(),"twolevel_identity");
    const auto identity_velocity=child_solver(comm,child_solver(comm,identity_solver.get(),0),0,true);
    PC identity_pc,coarse_pc; KSP coarse=nullptr; KSPType coarse_type=nullptr;
    PCType identity_type=nullptr,coarse_pc_type=nullptr; PetscInt levels=0;
    EONSIM_PETSC(KSPGetPC(identity_velocity,&identity_pc)); EONSIM_PETSC(PCGetType(identity_pc,&identity_type));
    EONSIM_PETSC(PCMGGetLevels(identity_pc,&levels)); EONSIM_PETSC(PCMGGetCoarseSolve(identity_pc,&coarse));
    EONSIM_PETSC(KSPGetType(coarse,&coarse_type)); EONSIM_PETSC(KSPGetPC(coarse,&coarse_pc));
    EONSIM_PETSC(PCGetType(coarse_pc,&coarse_pc_type));
    check(comm,std::string(identity_type)==PCMG&&levels==1&&std::string(coarse_type)==KSPPREONLY&&
               std::string(coarse_pc_type)==PCJACOBI,
          "All-identity two-level default did not retain its one-level Jacobi action");
    verify_preonly_action(comm,identity_velocity);
}
// Test the geometric span, not an implementation-dependent QR column order.
// The last row is a body scalar: its zero coordinate is not a vertex. One
// vertex lacks its z component; one other component is prescribed. Four-rank
// execution leaves two owners empty without collecting the distributed matrix.
void verify_coordinate_coarse_spaces(MPI_Comm comm) {
    int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
    constexpr PetscInt n=24,constrained=14;
    const PetscInt cuts2[]{0,12,n},cuts4[]{0,6,n,n,n};
    const PetscInt begin=size==1?0:size==2?cuts2[rank]:cuts4[rank];
    const PetscInt end=size==1?n:size==2?cuts2[rank+1]:cuts4[rank+1];
    const std::array<std::array<double,3>,8> points{{
        {{0,0,0}},{{1,0,0}},{{0,2,0}},{{0,0,3}},
        {{2,0,0}},{{3,0,0}},{{2,2,0}},{{2,0,3}}}};
    std::vector<DofKey> keys;
    std::vector<std::array<double,3>> coordinates;
    for(PetscInt i=begin;i<end;++i) {
        DofKey key; key.entity=i/3; key.component=i%3;
        key.domain=i<12?DofDomain::fluid:DofDomain::solid;
        if(i==n-1) {key.entity=100;key.kind=DofEntity::body;key.component=0;key.space=0;}
        keys.push_back(key);
        coordinates.push_back(i==n-1?std::array<double,3>{{0,0,0}}:points[i/3]);
    }
    const auto coefficient=[](PetscInt i,PetscInt j,int phase) {
        if(i==constrained) return i==j?1.:0.;
        return (i==j?80.+phase*(i+1):0.)+.003*(i+1)+.007*(j+1)+phase*.0001*(i+1)*(j+1);
    };
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,end-begin,nullptr,n-end+begin,nullptr,matrix.put()));
    const auto fill=[&](int phase,bool identity=false) {
        EONSIM_PETSC(MatZeroEntries(matrix.get()));
        for(PetscInt i=begin;i<end;++i) for(PetscInt j=0;j<n;++j)
            EONSIM_PETSC(MatSetValue(matrix.get(),i,j,identity?(i==j?1.:0.):coefficient(i,j,phase),INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    };
    for(int variant=0;variant<3;++variant) {
        const bool gamg=variant==1,aggregate=variant==2,rigid=!gamg;
        ScopedOptions options;
        if(gamg) {
            // Force this connected 24-row oracle through actual aggregation,
            // rather than accepting GAMG's tiny-matrix single-level fallback.
            options.set("-geometry_gamg_pc_gamg_coarse_eq_limit","2");
            options.set("-geometry_gamg_pc_gamg_threshold","0");
        }
        if(aggregate) {
            options.set("-geometry_aggregate_mg_coarse_pc_gamg_coarse_eq_limit","2");
            options.set("-geometry_aggregate_mg_coarse_pc_gamg_threshold","0");
        }
        fill(0);
        PetscOwner<KSP,KSPDestroy> solver;
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),gamg?"geometry_gamg_":aggregate?"geometry_aggregate_":"geometry_twolevel_"));
        EONSIM_PETSC(KSPSetOperators(solver.get(),matrix.get(),matrix.get()));
        if(gamg) configure_coupled_velocity_gamg(comm,solver.get(),keys);
        else configure_coupled_velocity_twolevel(comm,solver.get(),keys,coordinates,rigid,aggregate?2:0);
        EONSIM_PETSC(KSPSetUp(solver.get()));
        PC pc; PCType type=nullptr; PetscInt blocksize=0;
        EONSIM_PETSC(KSPGetPC(solver.get(),&pc)); EONSIM_PETSC(PCGetType(pc,&type));
        EONSIM_PETSC(MatGetBlockSize(matrix.get(),&blocksize));
        check(comm,std::string(type)==(gamg?PCGAMG:PCMG)&&blocksize==1,
              "Coupled geometric PC lost its full scalar matrix or selected backend");
        if(gamg) {
            PetscInt levels=0; EONSIM_PETSC(PCMGGetLevels(pc,&levels));
            check(comm,levels>=2,"Scalar GAMG oracle did not exercise a genuine multilevel cycle");
        }
        verify_preonly_action(comm,solver.get());
        std::vector<PetscOwner<Vec,VecDestroy>> basis;
        Mat interpolation=nullptr;
        if(gamg) {
            MatNullSpace space=nullptr; PetscBool constant=PETSC_FALSE; PetscInt count=0; const Vec* vectors=nullptr;
            EONSIM_PETSC(MatGetNearNullSpace(matrix.get(),&space));
            check(comm,space!=nullptr,"GAMG omitted the semantic near-nullspace");
            EONSIM_PETSC(MatNullSpaceGetVecs(space,&constant,&count,&vectors));
            check(comm,!constant&&count==1,"Scalar GAMG did not retain its single active-row constant");
            for(PetscInt j=0;j<count;++j) {
                basis.emplace_back(); EONSIM_PETSC(VecDuplicate(vectors[j],basis.back().put()));
                EONSIM_PETSC(VecCopy(vectors[j],basis.back().get()));
            }
        } else {
            EONSIM_PETSC(PCMGGetInterpolation(pc,1,&interpolation));
            PetscInt rows=0,columns=0;
            EONSIM_PETSC(MatGetSize(interpolation,&rows,&columns));
            check(comm,rows==n&&(aggregate?columns>(size==4?13:10):columns==(size==4?13:10)),
                  "Rigid two-level/aggregate coarse-space rank is incorrect");
            if(aggregate) {
                KSP coarse=nullptr; PC coarse_pc; PCType coarse_type=nullptr; PetscInt levels=0;
                EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse)); EONSIM_PETSC(KSPGetPC(coarse,&coarse_pc));
                EONSIM_PETSC(PCGetType(coarse_pc,&coarse_type)); EONSIM_PETSC(PCMGGetLevels(coarse_pc,&levels));
                check(comm,std::string(coarse_type)==PCGAMG&&levels>=2,
                      "Aggregate coarse operator did not use an actual GAMG hierarchy");
            }
            PetscOwner<Vec,VecDestroy> coarse,fine;
            EONSIM_PETSC(MatCreateVecs(interpolation,coarse.put(),fine.put()));
            PetscInt first=0,last=0; EONSIM_PETSC(VecGetOwnershipRange(coarse.get(),&first,&last));
            for(PetscInt j=0;j<columns;++j) {
                EONSIM_PETSC(VecSet(coarse.get(),0.));
                if(j>=first&&j<last) EONSIM_PETSC(VecSetValue(coarse.get(),j,1.,INSERT_VALUES));
                EONSIM_PETSC(VecAssemblyBegin(coarse.get())); EONSIM_PETSC(VecAssemblyEnd(coarse.get()));
                EONSIM_PETSC(MatMult(interpolation,coarse.get(),fine.get()));
                basis.emplace_back(); EONSIM_PETSC(VecDuplicate(fine.get(),basis.back().put()));
                EONSIM_PETSC(VecCopy(fine.get(),basis.back().get()));
            }
        }
        for(std::size_t i=0;i<basis.size();++i) {
            const PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArrayRead(basis[i].get(),&values));
            bool valid=true;
            std::set<std::tuple<DofDomain,DofEntity,std::int64_t>> support_nodes;
            for(PetscInt row=begin;row<end;++row)
                valid=valid&&std::isfinite(values[row-begin])&&(row!=constrained||values[row-begin]==0.);
            if(aggregate) for(PetscInt row=begin;row<end;++row) if(values[row-begin]!=0) {
                const auto& key=keys[row-begin]; support_nodes.insert({key.domain,key.kind,key.entity});
            }
            valid=valid&&(!aggregate||support_nodes.size()<=2);
            EONSIM_PETSC(VecRestoreArrayRead(basis[i].get(),&values));
            check(comm,valid,"Geometric coarse vector changed a constrained row or contains nonfinite data");
            for(std::size_t j=0;j<basis.size();++j) {
                PetscScalar dot=0; EONSIM_PETSC(VecDot(basis[i].get(),basis[j].get(),&dot));
                check(comm,std::abs(dot-(i==j?1.:0.))<2e-11,"Geometric coarse vectors are not orthonormal");
            }
        }
        PetscOwner<Vec,VecDestroy> target,projected;
        EONSIM_PETSC(MatCreateVecs(matrix.get(),target.put(),projected.put()));
        const auto span=[&](int owner,int domain,int mode,bool body) {
            PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(target.get(),&values));
            for(PetscInt row=begin;row<end;++row) {
                double value=0.; const auto& key=keys[row-begin];
                if(row!=constrained&&(owner<0||owner==rank)&&
                   (domain<0||domain==static_cast<int>(key.domain))) {
                    if(gamg) value=1.;
                    else if(body) value=key.kind==DofEntity::body?1.:0.;
                    else if(key.kind==DofEntity::vertex) {
                        // A large translation of the coordinate origin must
                        // not change the rigid span after translations exist.
                        const auto& x=coordinates[row-begin];
                        const double y[3]{x[0]+123.,x[1]-456.,x[2]+17.};
                        if(mode<3) value=key.component==mode?1.:0.;
                        else {
                            const double rotation[3][3]{{0.,-y[2],y[1]},
                                                       {y[2],0.,-y[0]},
                                                       {-y[1],y[0],0.}};
                            value=rotation[mode-3][key.component];
                        }
                    }
                }
                values[row-begin]=value;
            }
            EONSIM_PETSC(VecRestoreArray(target.get(),&values));
            EONSIM_PETSC(VecCopy(target.get(),projected.get()));
            for(const auto& vector:basis) {
                PetscScalar dot=0; EONSIM_PETSC(VecDot(vector.get(),target.get(),&dot));
                EONSIM_PETSC(VecAXPY(projected.get(),-dot,vector.get()));
            }
            PetscReal norm=0,error=0;
            EONSIM_PETSC(VecNorm(target.get(),NORM_2,&norm));
            EONSIM_PETSC(VecNorm(projected.get(),NORM_2,&error));
            check(comm,error<2e-11*(1+norm),"Coordinate translations/rotations are missing from the coarse span");
        };
        if(gamg) {
            span(-1,-1,0,false);
        } else for(int owner=0;owner<size;++owner) {
            for(int mode=0;mode<3;++mode) span(owner,static_cast<int>(DofDomain::fluid),mode,false);
            for(int mode=0;mode<6;++mode) span(owner,static_cast<int>(DofDomain::solid),mode,false);
            span(owner,static_cast<int>(DofDomain::solid),0,true);
        }
        EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-13,PETSC_DEFAULT,200));
        for(int phase=0;phase<2;++phase) {
            if(phase) fill(phase);
            solve_exact(comm,solver.get(),matrix.get(),gamg?"gamg_coordinate_refresh":aggregate?"aggregate_rigid_refresh":"twolevel_rigid_refresh");
            if(!gamg) {
                KSP coarse=nullptr; Mat product=nullptr; PetscInt first=0,last=0;
                EONSIM_PETSC(PCMGGetCoarseSolve(pc,&coarse));
                EONSIM_PETSC(KSPGetOperators(coarse,&product,nullptr));
                EONSIM_PETSC(MatGetOwnershipRange(product,&first,&last));
                for(PetscInt j=0;j<static_cast<PetscInt>(basis.size());++j) {
                    EONSIM_PETSC(MatMult(matrix.get(),basis[j].get(),projected.get()));
                    for(PetscInt i=0;i<static_cast<PetscInt>(basis.size());++i) {
                        PetscScalar expected=0; EONSIM_PETSC(VecDot(basis[i].get(),projected.get(),&expected));
                        bool valid=true;
                        if(i>=first&&i<last) {
                            PetscScalar actual=0; EONSIM_PETSC(MatGetValues(product,1,&i,1,&j,&actual));
                            valid=std::abs(actual-expected)<2e-10*(1+std::abs(expected));
                        }
                        check(comm,valid,"Rigid Galerkin matrix failed independent action/refresh oracle");
                    }
                }
            } else {
                PetscInt levels=0; Mat transfer=nullptr,product=nullptr; KSP coarse=nullptr;
                EONSIM_PETSC(PCMGGetLevels(pc,&levels));
                EONSIM_PETSC(PCMGGetInterpolation(pc,levels-1,&transfer));
                EONSIM_PETSC(PCMGGetSmoother(pc,levels-2,&coarse));
                EONSIM_PETSC(KSPGetOperators(coarse,&product,nullptr));
                PetscOwner<Vec,VecDestroy> unit,fine;
                EONSIM_PETSC(MatCreateVecs(transfer,unit.put(),fine.put()));
                PetscInt count=0,first=0,last=0;
                EONSIM_PETSC(VecGetSize(unit.get(),&count));
                EONSIM_PETSC(VecGetOwnershipRange(unit.get(),&first,&last));
                std::vector<PetscOwner<Vec,VecDestroy>> columns;
                for(PetscInt j=0;j<count;++j) {
                    EONSIM_PETSC(VecSet(unit.get(),0.));
                    if(j>=first&&j<last) EONSIM_PETSC(VecSetValue(unit.get(),j,1.,INSERT_VALUES));
                    EONSIM_PETSC(VecAssemblyBegin(unit.get())); EONSIM_PETSC(VecAssemblyEnd(unit.get()));
                    EONSIM_PETSC(MatMult(transfer,unit.get(),fine.get()));
                    columns.emplace_back(); EONSIM_PETSC(VecDuplicate(fine.get(),columns.back().put()));
                    EONSIM_PETSC(VecCopy(fine.get(),columns.back().get()));
                }
                EONSIM_PETSC(MatGetOwnershipRange(product,&first,&last));
                for(PetscInt j=0;j<count;++j) {
                    EONSIM_PETSC(MatMult(matrix.get(),columns[j].get(),projected.get()));
                    for(PetscInt i=0;i<count;++i) {
                        PetscScalar expected=0; EONSIM_PETSC(VecDot(columns[i].get(),projected.get(),&expected));
                        bool valid=true;
                        if(i>=first&&i<last) {
                            PetscScalar actual=0; EONSIM_PETSC(MatGetValues(product,1,&i,1,&j,&actual));
                            valid=std::abs(actual-expected)<2e-10*(1+std::abs(expected));
                        }
                        check(comm,valid,"GAMG fine Galerkin matrix failed independent action/refresh oracle");
                    }
                }
            }
        }
    }
    // Degenerate positions retain the two-level constants/body mode and drop
    // rotations. Native scalar GAMG deliberately rejects a rigid-vector set.
    fill(0);
    PetscOwner<KSP,KSPDestroy> degenerate;
    EONSIM_PETSC(KSPCreate(comm,degenerate.put()));
    EONSIM_PETSC(KSPSetOperators(degenerate.get(),matrix.get(),matrix.get()));
    const std::vector<std::array<double,3>> coincident(keys.size(),{{5.,5.,5.}});
    configure_coupled_velocity_twolevel(comm,degenerate.get(),keys,coincident,true);
    PC degenerate_pc; Mat degenerate_interpolation=nullptr; PetscInt rows=0,columns=0;
    EONSIM_PETSC(KSPGetPC(degenerate.get(),&degenerate_pc));
    EONSIM_PETSC(PCMGGetInterpolation(degenerate_pc,1,&degenerate_interpolation));
    EONSIM_PETSC(MatGetSize(degenerate_interpolation,&rows,&columns));
    check(comm,rows==n&&columns==(size==4?10:7),"Degenerate rigid modes were not removed");
    fill(0,true);
    PetscOwner<KSP,KSPDestroy> identity;
    EONSIM_PETSC(KSPCreate(comm,identity.put()));
    EONSIM_PETSC(KSPSetOperators(identity.get(),matrix.get(),matrix.get()));
    configure_coupled_velocity_gamg(comm,identity.get(),keys);
    PC pc; PCType type=nullptr; EONSIM_PETSC(KSPGetPC(identity.get(),&pc)); EONSIM_PETSC(PCGetType(pc,&type));
    check(comm,std::string(type)==PCJACOBI,"All-identity GAMG did not select exact Jacobi fallback");
    verify_preonly_action(comm,identity.get());
}

void run(MPI_Comm comm) {
    int rank,size; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
    check(comm,size==1||size==2||size==4,"Expected 1/2/4 ranks");
    // G0A's nonsymmetric 5x5 oracle: W != K, nonzero lifting and shared alias.
    const double dense[5][5]={{2,1,-1,3,4},{5,6,2,0,1},{-2,4,7,1,-3},{9,8,6,5,2},{1,0,3,2,4}};
    const std::vector<ReducedSlot> mapping{{0,0,0,1,0},{1,1,1,1,0},{1,1,1,1,0},{1,1,-1,2,3},{-1,-1,-1,0,5}};
    const std::vector<double> q{1,2}; double residual[2]{},jac[2][2]{};
    for(int i=0;i<5;++i) {
        double ri=-(i+1);
        for(int j=0;j<5;++j) ri+=dense[i][j]*mapping[j].expand(q);
        if(mapping[i].test_row<0) continue;
        const auto row=mapping[i].test_row; residual[row]+=ri;
        for(int j=0;j<5;++j) if(mapping[j].column>=0)
            jac[row][mapping[j].column]+=dense[i][j]*mapping[j].trial_weight;
    }
    check(comm,residual[0]==42&&residual[1]==33&&jac[0][0]==2&&jac[0][1]==6&&jac[1][0]==3&&jac[1][1]==21,
          "Affine constraint/lifting oracle failed");
    const int cuts4[]={0,7,11,14,14},cuts2[]={0,7,14};
    AlgebraLayout l; l.global=14;l.begin=size==1?0:(size==2?cuts2[rank]:cuts4[rank]);
    l.owned=(size==1?14:(size==2?cuts2[rank+1]:cuts4[rank+1]))-l.begin;
    for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
        l.local_to_global.push_back(row);
        DofKey key;
        key.entity=row<7?10:row<11?20:30;
        key.domain=row>=8?DofDomain::solid:row>=4&&row<=6?DofDomain::mesh:DofDomain::fluid;
        key.quantity=row==3||row==7?DofQuantity::pressure:key.domain==DofDomain::mesh?DofQuantity::displacement:DofQuantity::velocity;
        key.component=row<3?row:row>=4&&row<=6?row-4:row>=8&&row<=10?row-8:row>=11?row-11:0;
        l.owned_semantics.push_back(key);
    }
    for(const char* name:{"velocity","pressure","mesh","structure"}) l.fields[name];
    for(PetscInt i=0;i<l.owned;++i) {
        const auto& key=l.owned_semantics[i];
        l.fields[key.domain==DofDomain::solid?"structure":key.domain==DofDomain::mesh?"mesh":key.quantity==DofQuantity::pressure?"pressure":"velocity"].push_back(l.begin+i);
    }
    l.diagonal.assign(l.owned,l.owned); l.off_diagonal.assign(l.owned,14-l.owned);
    // Matrix and physical acceptance are identical across recipes. Diagonal
    // exact solution x_i=i+1 is independent of the PC-plan implementation.
    NonlinearSystem system(comm,l);
    std::vector<double> initial(l.owned,0);
    int failure=0;
    const auto assemble=[&](const std::vector<double>& x,Vec residual,Mat jacobian) {
        if(rank==size-1&&(failure==1||failure==2)) {
            EONSIM_PETSC(VecSetValue(residual,0,777,ADD_VALUES));
            if(failure==1) throw StepRejected("synthetic rejected trial");
            throw std::runtime_error("synthetic invalid callback");
        }
        for(PetscInt i=0;i<l.owned;++i) {
            const auto row=l.begin+i;
            EONSIM_PETSC(VecSetValue(residual,row,2*(x[i]-(row+1)),ADD_VALUES));
            if(jacobian) EONSIM_PETSC(MatSetValue(jacobian,row,row,(failure==3&&row==13)?0:2,ADD_VALUES));
        }
    };
    for(const std::string recipe:{"physics","quantity","hybrid","added_mass"}) {
        SolverConfig config;config.pc_recipe=recipe;
        auto solved=system.solve(config,initial,{}, {},assemble);
        bool good=true;
        for(PetscInt i=0;i<l.owned;++i) good=good&&std::abs(solved.values[i]-(l.begin+i+1))<1e-10;
        for(const auto& f:solved.field_residuals) good=good&&f.rms<=f.limit;
        check(comm,good,"Recipe changed exact solution or physical acceptance");
        for(int mode:{1,2}) {
            failure=mode;bool caught=false;
            try {system.solve(config,initial,{}, {},assemble);}
            catch(const StepRejected&) {caught=mode==1;}
            catch(const std::runtime_error&) {caught=mode==2;}
            check(comm,caught,"Callback failure category changed");
            failure=0;
            const auto restored=system.solve(config,initial,{}, {},assemble);
            bool same=initial==std::vector<double>(l.owned,0);
            for(PetscInt i=0;i<l.owned;++i) same=same&&std::abs(restored.values[i]-(l.begin+i+1))<1e-10;
            check(comm,same,"Failed callback polluted accepted state or next solve");
        }
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-ksp_max_it","0"));
        bool linear_failed=false;
        try {system.solve(config,initial,{}, {},assemble);}
        catch(const StepRejected&) {linear_failed=false;}
        catch(const std::runtime_error& e) {linear_failed=std::string(e.what()).find("Linear solver failure")!=std::string::npos;}
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-ksp_max_it"));
        check(comm,linear_failed,"Recipe hid linear nonconvergence");
        const std::string leaf=recipe=="physics"?"-fieldsplit_solid_":recipe=="quantity"?
            "-fieldsplit_velocity_fieldsplit_structure_":recipe=="added_mass"?
            "-fieldsplit_dynamics_fieldsplit_structure_":"-fieldsplit_dynamics_fieldsplit_velocity_fieldsplit_structure_";
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(leaf+"pc_type").c_str(),"bjacobi"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(leaf+"sub_pc_type").c_str(),"ilu"));
        failure=3;bool pc_failed=false,pc_exception=false;
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        try {system.solve(config,initial,{}, {},assemble);}
        catch(const StepRejected& e) {
            pc_exception=true; pc_failed=false;
            std::cerr<<"pc_test_failure_category rank="<<rank<<" recipe="<<recipe<<" step_rejected="<<e.what()<<'\n';
        }
        catch(const std::runtime_error& e) {
            pc_exception=true;
            pc_failed=std::string(e.what()).find("Linear solver failure")!=std::string::npos&&
                std::string(e.what()).find("DIVERGED_PC_FAILED")!=std::string::npos;
            if(!pc_failed) std::cerr<<"pc_test_failure_category rank="<<rank<<" recipe="<<recipe<<" error="<<e.what()<<'\n';
        }
        if(!pc_exception) std::cerr<<"pc_test_failure_category rank="<<rank<<" recipe="<<recipe<<" unexpectedly_accepted=1\n";
        EONSIM_PETSC(PetscPopErrorHandler());
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,(leaf+"pc_type").c_str()));
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,(leaf+"sub_pc_type").c_str()));
        check(comm,pc_failed,"Recipe did not diagnose local PC failure");
        failure=0;
        auto recovered=system.solve(config,initial,{}, {},assemble);
        bool same=initial==std::vector<double>(l.owned,0);
        for(PetscInt i=0;i<l.owned;++i) same=same&&std::abs(recovered.values[i]-(l.begin+i+1))<1e-10;
        check(comm,same,"PC failure polluted accepted state or recovery");
        const auto zero=[](const std::vector<double>&,Vec,Mat) {};
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_fieldsplit_type","additive"));
        bool invalid_zero=false;
        try {system.solve(config,initial,{}, {},zero);} catch(const std::runtime_error&) {invalid_zero=true;}
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_fieldsplit_type"));
        check(comm,invalid_zero,"Zero initial residual bypassed invalid recipe options");
        const auto unchanged=system.solve(config,initial,{}, {},zero);
        check(comm,unchanged.iterations==0&&unchanged.values==initial,"Initially converged solve changed state");
    }
    // Optional permutation diagnostics must also fail collectively and leave
    // the same nonlinear object usable, including the empty-owned fourth rank.
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-verify_operator_permutation","true"));
    failure=3;
    bool diagnostic_failed=false;
    EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
    try { system.solve(SolverConfig{},initial,{}, {},assemble); }
    catch(const std::runtime_error& error) {
        diagnostic_failed=std::string(error.what()).find("permutation reference solve failed")!=std::string::npos;
    }
    EONSIM_PETSC(PetscPopErrorHandler());
    failure=0;
    const auto diagnostic_recovered=system.solve(SolverConfig{},initial,{}, {},assemble);
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-verify_operator_permutation"));
    bool diagnostic_exact=initial==std::vector<double>(l.owned,0);
    for(PetscInt i=0;i<l.owned;++i)
        diagnostic_exact=diagnostic_exact&&std::abs(diagnostic_recovered.values[i]-(l.begin+i+1))<1e-10;
    check(comm,diagnostic_failed&&diagnostic_exact,"Permutation diagnostic failure/recovery contract failed");
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,l.owned,l.owned,14,14,l.owned,nullptr,14-l.owned,nullptr,matrix.put()));
    for(PetscInt row=l.begin;row<l.begin+l.owned;++row) for(PetscInt col=0;col<14;++col)
        EONSIM_PETSC(MatSetValue(matrix.get(),row,col,entry(row,col),INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY)); EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    // Coordinate permutation q=P*y, with reverse global ordering. This tests
    // PETSc algebra only; it does not introduce a production storage option.
    std::vector<PetscInt> reverse;
    for(PetscInt i=l.begin;i<l.begin+l.owned;++i) reverse.push_back(13-i);
    PetscOwner<IS,ISDestroy> permutation; PetscOwner<Mat,MatDestroy> permuted;
    EONSIM_PETSC(ISCreateGeneral(comm,reverse.size(),reverse.data(),PETSC_COPY_VALUES,permutation.put()));
    EONSIM_PETSC(MatPermute(matrix.get(),permutation.get(),permutation.get(),permuted.put()));
    for(bool changed:{false,true}) {
        Mat a=changed?permuted.get():matrix.get();
        PetscOwner<Vec,VecDestroy> rhs,x,defect;
        EONSIM_PETSC(MatCreateVecs(a,x.put(),rhs.put())); EONSIM_PETSC(VecDuplicate(rhs.get(),defect.put()));
        for(PetscInt i=l.begin;i<l.begin+l.owned;++i) {
            const auto old=changed?13-i:i;
            // Sum_j A_ij*(j+1): sum(j+1)=105, sum((j+1)^2)=1015.
            EONSIM_PETSC(VecSetValue(rhs.get(),i,101.05*(old+1)+20.3,INSERT_VALUES));
        }
        EONSIM_PETSC(VecAssemblyBegin(rhs.get())); EONSIM_PETSC(VecAssemblyEnd(rhs.get()));
        PetscOwner<KSP,KSPDestroy> solver; EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOperators(solver.get(),a,a)); EONSIM_PETSC(KSPSetType(solver.get(),KSPGMRES));
        PC pc; EONSIM_PETSC(KSPGetPC(solver.get(),&pc)); EONSIM_PETSC(PCSetType(pc,PCJACOBI));
        EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-13,1e-13,PETSC_DEFAULT,100));
        EONSIM_PETSC(KSPSolve(solver.get(),rhs.get(),x.get()));
        const PetscScalar* values; EONSIM_PETSC(VecGetArrayRead(x.get(),&values));
        bool exact=true;
        for(PetscInt i=0;i<l.owned;++i) exact=exact&&std::abs(values[i]-(changed?14-(l.begin+i):l.begin+i+1))<1e-10;
        EONSIM_PETSC(VecRestoreArrayRead(x.get(),&values));
        EONSIM_PETSC(MatMult(a,x.get(),defect.get())); EONSIM_PETSC(VecAXPY(defect.get(),-1,rhs.get()));
        PetscReal norm; EONSIM_PETSC(VecNorm(defect.get(),NORM_INFINITY,&norm));
        check(comm,exact&&norm<1e-9,"Permutation changed exact solution or residual");
        for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
            PetscInt count; const PetscInt* cols; const PetscScalar* vals;
            EONSIM_PETSC(MatGetRow(a,row,&count,&cols,&vals));
            for(PetscInt j=0;j<count;++j) exact=exact&&vals[j]==entry(changed?13-row:row,changed?13-cols[j]:cols[j]);
            EONSIM_PETSC(MatRestoreRow(a,row,&count,&cols,&vals));
        }
        check(comm,exact,"Permutation Jacobian value oracle failed");
    }
    // Handwritten independent root-provenance oracle, not generated from the plan.
    const std::vector<PetscInt> v{0,1,2,8,9,10,11,12,13},p{3,7},mesh{4,5,6},solid{8,9,10,11,12,13};
    for(const std::string recipe:{"physics","quantity","hybrid","added_mass"}) {
        Oracle oracle;
        if(recipe=="physics") oracle={{"/fluid",{0,1,2,3,7}},{"/fluid/velocity",{0,1,2}},{"/fluid/pressure",p},{"/solid",solid},{"/mesh",mesh}};
        if(recipe=="quantity") oracle={{"/velocity",v},{"/velocity/fluid_interior",{0,1,2}},{"/velocity/structure",solid},{"/pressure",p},{"/mesh",mesh}};
        if(recipe=="hybrid") oracle={{"/dynamics",{0,1,2,3,7,8,9,10,11,12,13}},{"/dynamics/velocity",v},{"/dynamics/velocity/fluid_interior",{0,1,2}},{"/dynamics/velocity/structure",solid},{"/dynamics/pressure",p},{"/mesh",mesh}};
        if(recipe=="added_mass") oracle={{"/dynamics",{0,1,2,3,7,8,9,10,11,12,13}},{"/dynamics/fluid",{0,1,2,3,7}},{"/dynamics/fluid/velocity",{0,1,2}},{"/dynamics/fluid/pressure",p},{"/dynamics/structure",solid},{"/mesh",mesh}};
        const auto plan=make_pc_plan(comm,l,recipe);
        verify_tree(comm,matrix.get(),plan,"",oracle);
        PetscOwner<KSP,KSPDestroy> ksp; EONSIM_PETSC(KSPCreate(comm,ksp.put()));
        EONSIM_PETSC(KSPSetType(ksp.get(),KSPFGMRES));
        configure_pc_plan(comm,ksp.get(),matrix.get(),plan);
        if(recipe=="added_mass") {
            const auto dynamics=child_solver(comm,ksp.get(),0);
            const auto fluid=child_solver(comm,dynamics,0,true),structure=child_solver(comm,dynamics,1,true);
            PC fluid_pc; PCType pc_type=nullptr; KSPType structure_type=nullptr;
            Mat schur=nullptr; KSP interior=nullptr;
            PetscReal fluid_rtol=0,structure_rtol=0; PetscInt fluid_max=0,structure_max=0;
            EONSIM_PETSC(KSPGetPC(fluid,&fluid_pc)); EONSIM_PETSC(PCGetType(fluid_pc,&pc_type));
            EONSIM_PETSC(KSPGetOperators(structure,&schur,nullptr));
            EONSIM_PETSC(MatSchurComplementGetKSP(schur,&interior));
            EONSIM_PETSC(KSPGetType(structure,&structure_type));
            EONSIM_PETSC(KSPGetTolerances(fluid,&fluid_rtol,nullptr,nullptr,&fluid_max));
            EONSIM_PETSC(KSPGetTolerances(structure,&structure_rtol,nullptr,nullptr,&structure_max));
            check(comm,interior==fluid&&std::string(pc_type)==PCFIELDSPLIT&&
                       std::string(structure_type)==KSPFGMRES&&fluid_max==20&&structure_max==20&&
                       std::abs(fluid_rtol-1e-4)<1e-15&&std::abs(structure_rtol-1e-2)<1e-15,
                  "Added-mass defaults lost shared fluid action or the retained iterative-override budgets");
            verify_preonly_action(comm,fluid);
        }
    }
    verify_nodal_schur(comm,l,matrix.get());
    verify_added_mass(comm,l);
    verify_structural_nodal(comm,l);
    verify_twolevel(comm,l);
    verify_coordinate_coarse_spaces(comm);
    verify_auxiliary_solvers(comm,l,matrix.get());
    // Exercise the production SNES callback with changing Jacobian values.
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_schur_approx","nodal"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_velocity_solver","coupled"));
    SolverConfig improved; improved.pc_recipe="hybrid";
    const auto nonlinear=[&](const std::vector<double>& x,Vec residual,Mat jacobian) {
        for(PetscInt i=0;i<l.owned;++i) {
            const auto row=l.begin+i; const double target=row+1;
            EONSIM_PETSC(VecSetValue(residual,row,2*(x[i]-target)+.01*(x[i]*x[i]-target*target),ADD_VALUES));
            if(jacobian) EONSIM_PETSC(MatSetValue(jacobian,row,row,2+.02*x[i],ADD_VALUES));
        }
    };
    const auto improved_result=system.solve(improved,initial,{}, {},nonlinear);
    bool improved_exact=true;
    for(PetscInt i=0;i<l.owned;++i)
        improved_exact=improved_exact&&std::abs(improved_result.values[i]-(l.begin+i+1))<1e-8;
    check(comm,improved_exact&&improved_result.iterations>1,"Nodal refresh during nonlinear solve failed");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_plan_velocity_solver"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_plan_schur_approx"));
    // Configuration errors must be detected even at an already converged state.
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-pc_plan_schur_approx","invalid"},{"-pc_plan_velocity_solver","invalid"}}) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,option.first.c_str(),option.second.c_str()));
        bool rejected=false;
        try {system.solve(improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,option.first.c_str()));
        check(comm,rejected,"Invalid new PC option was ignored");
    }
    for(const auto& configuration:std::vector<std::pair<std::string,std::string>>{
        {"","a11"},{"","nodal"},{"hybrid","nodal"},{"added_mass","invalid"}}) {
        ScopedOptions options; options.set("-pc_plan_structure_approx",configuration.second);
        SolverConfig config; config.pc_recipe=configuration.first;
        bool rejected=false;
        try {system.solve(config,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Structural approximation option escaped validation at zero residual");
    }
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-fieldsplit_dynamics_pc_fieldsplit_schur_precondition","a11"},
        {"-fieldsplit_dynamics_fieldsplit_structure_mat_schur_complement_ainv_type","diag"}}) {
        ScopedOptions options; options.set("-pc_plan_structure_approx","nodal");
        options.set(option.first,option.second);
        SolverConfig config; config.pc_recipe="added_mass";
        bool rejected=false;
        try {system.solve(config,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Conflicting structural USER approximation was accepted at zero residual");
    }
    if(size>1) {
        ScopedOptions options;
        if(rank==0) options.set("-pc_plan_structure_approx","nodal");
        SolverConfig config; config.pc_recipe="added_mass";
        bool rejected=false;
        try {system.solve(config,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Rank-inconsistent structural approximation was accepted at zero residual");
    }
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-fieldsplit_dynamics_fieldsplit_velocity_pc_type","asm"},
        {"-fieldsplit_dynamics_fieldsplit_velocity_pc_mg_levels","3"},
        {"-fieldsplit_dynamics_fieldsplit_velocity_ksp_type","gmres"},
        {"-ksp_type","gmres"}}) {
        ScopedOptions options;
        options.set("-pc_plan_velocity_solver","twolevel");
        options.set(option.first,option.second);
        bool rejected=false;
        try {system.solve(improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid two-level topology or nonflexible outer solver was ignored at zero residual");
    }
    for(const auto& configuration:std::vector<std::array<std::string,3>>{
        {{"","","constants"}},{{"hybrid","split","constants"}},
        {{"hybrid","coupled","rigid"}},{{"hybrid","gamg","invalid"}},
        {{"hybrid","gamg","rigid"}},{{"hybrid","twolevel","rigid"}}}) {
        ScopedOptions options;
        if(!configuration[1].empty()) options.set("-pc_plan_velocity_solver",configuration[1]);
        options.set("-pc_plan_velocity_coarse_space",configuration[2]);
        SolverConfig config; config.pc_recipe=configuration[0];
        bool rejected=false;
        try {system.solve(config,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid coarse-space option or missing coordinates escaped zero-residual validation");
    }
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-fieldsplit_dynamics_fieldsplit_velocity_pc_type","asm"},
        {"-fieldsplit_dynamics_fieldsplit_velocity_ksp_type","gmres"},
        {"-ksp_type","gmres"}}) {
        ScopedOptions options; options.set("-pc_plan_velocity_solver","gamg");
        options.set(option.first,option.second);
        bool rejected=false;
        try {system.solve(improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid coupled GAMG configuration escaped zero-residual validation");
    }
    for(int fault=0;fault<4;++fault) {
        ScopedOptions options; options.set("-pc_plan_velocity_solver","twolevel");
        options.set("-pc_plan_velocity_coarse_space","rigid");
        auto invalid=l;
        invalid.owned_reference_coordinates.assign(invalid.owned,{{0.,0.,0.}});
        if(rank==0&&invalid.owned) {
            if(fault==0) invalid.owned_reference_coordinates.pop_back();
            if(fault==1) invalid.owned_reference_coordinates[0][1]=std::numeric_limits<double>::quiet_NaN();
            if(fault==2) invalid.owned_semantics[0].mode=1;
            if(fault==3) invalid.owned_semantics[0].kind=DofEntity::edge;
        }
        bool rejected=false;
        try {make_pc_plan(comm,invalid,"hybrid");}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid rank-local coordinate metadata was not collectively rejected");
    }
    if(size>1) {
        ScopedOptions options; options.set("-pc_plan_velocity_solver","twolevel");
        options.set("-pc_plan_velocity_coarse_space",rank==0?"rigid":"constants");
        auto geometry=l;
        geometry.owned_reference_coordinates.assign(geometry.owned,{{0.,0.,0.}});
        bool rejected=false;
        try {make_pc_plan(comm,geometry,"hybrid");}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Rank-inconsistent coarse-space options were accepted");
    }
    {
        ScopedOptions options; options.set("-pc_plan_velocity_solver","gamg");
        options.set("-pc_plan_velocity_coarse_space","rigid");
        auto geometry=l;
        geometry.owned_reference_coordinates.assign(geometry.owned,{{0.,0.,0.}});
        bool rejected=false;
        try {make_pc_plan(comm,geometry,"hybrid");}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Native scalar GAMG accepted an unsupported multivector rigid near-nullspace");
    }
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-fieldsplit_dynamics_pc_fieldsplit_schur_precondition","selfp"},
        {"-pc_plan_velocity_solver","coupled"},{"-ksp_type","gmres"}}) {
        ScopedOptions options; options.set(option.first,option.second);
        SolverConfig added_mass; added_mass.pc_recipe="added_mass";
        bool rejected=false;
        try {system.solve(added_mass,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
        catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid added-mass topology or nonflexible outer solver was ignored at zero residual");
    }
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_schur_approx","nodal"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-fieldsplit_dynamics_pc_fieldsplit_schur_precondition","selfp"));
    bool conflict=false;
    try {system.solve(improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
    catch(const std::runtime_error&) {conflict=true;}
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-fieldsplit_dynamics_pc_fieldsplit_schur_precondition"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_plan_schur_approx"));
    check(comm,conflict,"Conflicting Schur preconditioner was ignored");
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-schur_pc","true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-fieldsplit_flow_pc_fieldsplit_type","additive"));
    bool old_conflict=false;
    try {system.solve(SolverConfig{},initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
    catch(const std::runtime_error&) {old_conflict=true;}
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-fieldsplit_flow_pc_fieldsplit_type"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-schur_pc"));
    check(comm,old_conflict,"Legacy Schur topology conflict was ignored at zero residual");
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"-pc_fieldsplit_type","additive"}}) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,option.first.c_str(),option.second.c_str()));
        bool rejected=false;
        try {
            auto plan=make_pc_plan(comm,l,"hybrid");
            PetscOwner<KSP,KSPDestroy> ksp; EONSIM_PETSC(KSPCreate(comm,ksp.put()));
            configure_pc_plan(comm,ksp.get(),matrix.get(),plan);
        } catch(const std::runtime_error&) {rejected=true;}
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,option.first.c_str()));
        check(comm,rejected,"Unsupported recipe override was not rejected");
    }
    for(bool legacy:{false,true}) {
        const std::string prefix=legacy?"-fieldsplit_flow_":"-fieldsplit_dynamics_";
        for(const std::string factor:{"lower","upper","diag"}) {
            ScopedOptions options;
            if(legacy) options.set("-schur_pc","true");
            options.set(prefix+"pc_fieldsplit_schur_fact_type",factor);
            options.set(prefix+"fieldsplit_pressure_upper_ksp_type","gmres");
            bool rejected=false;
            try {system.solve(legacy?SolverConfig{}:improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
            catch(const std::runtime_error&) {rejected=true;}
            check(comm,rejected,"Unused Schur upper options were accepted for a non-FULL factorization");
        }
        if(size>1) {
            ScopedOptions options;
            if(legacy) options.set("-schur_pc","true");
            if(rank==0) options.set(prefix+"fieldsplit_pressure_inner_ksp_type","gmres");
            bool rejected=false;
            try {system.solve(legacy?SolverConfig{}:improved,initial,{}, {},[](const std::vector<double>&,Vec,Mat){});}
            catch(const std::runtime_error&) {rejected=true;}
            check(comm,rejected,"Rank-specific Schur inner activation was not rejected collectively");
        }
    }
    for(auto quantity:{DofQuantity::pressure,DofQuantity::displacement}) {
        auto missing=l;
        for(auto& key:missing.owned_semantics) if(key.quantity==quantity) {
            key.entity+=100; key.domain=DofDomain::solid; key.quantity=DofQuantity::velocity;
        }
        bool rejected=false;
        try {make_pc_plan(comm,missing,"hybrid");} catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Globally empty block was not rejected");
    }
    bool caught=false;
    try { make_pc_plan(comm,l,rank==0?"invalid":"hybrid"); } catch(const std::runtime_error&) {caught=true;}
    check(comm,caught,"Rank-specific invalid recipe was not collectively rejected");
    for(int error:{0,1,2}) {
        auto invalid=l;
        if(rank==0) {
            if(error==0) invalid.local_to_global[1]=invalid.local_to_global[0];
            if(error==1) invalid.global+=1;
            if(error==2) invalid.owned_semantics.pop_back();
        }
        bool rejected=false;
        try {make_pc_plan(comm,invalid,"hybrid");} catch(const std::runtime_error&) {rejected=true;}
        check(comm,rejected,"Invalid ownership/missing identity was not collectively rejected");
    }
    auto invalid=l;
    if(rank==0) invalid.owned_semantics[1]=invalid.owned_semantics[0];
    caught=false;try { make_pc_plan(comm,invalid,"hybrid"); } catch(const std::runtime_error&) {caught=true;}
    check(comm,caught,"Duplicate identity was not collectively rejected");
    if(rank==0) std::cout<<"PC plan matrix provenance and collective negative cases passed\n";
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try {run(PETSC_COMM_WORLD);} catch(const std::exception& e) {std::cerr<<e.what()<<'\n';result=1;}
    PetscFinalize();return result;
}
