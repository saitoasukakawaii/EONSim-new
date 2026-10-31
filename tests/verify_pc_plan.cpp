#include "eonsim/pc_plan.hpp"
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
