#include "eonsim/pc_plan.hpp"
#include "eonsim/schur_solver.hpp"
#include <array>
#include <algorithm>
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/reduced_layout.hpp"
#include <cmath>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool ok,const char* msg) {
    int bad=!ok,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(msg);
}
double entry(PetscInt i,PetscInt j) {return (i==j?100.:0.)+.01*(i+1)+.02*(j+1);}
using Oracle=std::map<std::string,std::vector<PetscInt>>;
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
    for(const std::string recipe:{"physics","quantity","hybrid"}) {
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
            "-fieldsplit_velocity_fieldsplit_structure_":"-fieldsplit_dynamics_fieldsplit_velocity_fieldsplit_structure_";
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(leaf+"pc_type").c_str(),"bjacobi"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(leaf+"sub_pc_type").c_str(),"ilu"));
        failure=3;bool pc_failed=false;
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
        try {system.solve(config,initial,{}, {},assemble);}
        catch(const StepRejected&) {pc_failed=false;}
        catch(const std::runtime_error& e) {pc_failed=std::string(e.what()).find("Linear solver failure")!=std::string::npos&&
            std::string(e.what()).find("DIVERGED_PC_FAILED")!=std::string::npos;}
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
    for(const std::string recipe:{"physics","quantity","hybrid"}) {
        Oracle oracle;
        if(recipe=="physics") oracle={{"/fluid",{0,1,2,3,7}},{"/fluid/velocity",{0,1,2}},{"/fluid/pressure",p},{"/solid",solid},{"/mesh",mesh}};
        if(recipe=="quantity") oracle={{"/velocity",v},{"/velocity/fluid_interior",{0,1,2}},{"/velocity/structure",solid},{"/pressure",p},{"/mesh",mesh}};
        if(recipe=="hybrid") oracle={{"/dynamics",{0,1,2,3,7,8,9,10,11,12,13}},{"/dynamics/velocity",v},{"/dynamics/velocity/fluid_interior",{0,1,2}},{"/dynamics/velocity/structure",solid},{"/dynamics/pressure",p},{"/mesh",mesh}};
        const auto plan=make_pc_plan(comm,l,recipe);
        verify_tree(comm,matrix.get(),plan,"",oracle);
        PetscOwner<KSP,KSPDestroy> ksp; EONSIM_PETSC(KSPCreate(comm,ksp.put()));
        EONSIM_PETSC(KSPSetType(ksp.get(),KSPFGMRES));
        configure_pc_plan(comm,ksp.get(),matrix.get(),plan);
    }
    verify_nodal_schur(comm,l,matrix.get());
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
        {"-fieldsplit_dynamics_fieldsplit_pressure_inner_pc_type","jacobi"},
        {"-fieldsplit_dynamics_fieldsplit_pressure_upper_ksp_rtol","1e-5"},
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
