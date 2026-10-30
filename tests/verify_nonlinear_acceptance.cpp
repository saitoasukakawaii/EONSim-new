/** 非线性耦合小系统：极端方程尺度、空本地字段、约束反力及提前停止。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace eonsim;
namespace {
void require(bool condition,const char* message) { if(!condition) throw std::runtime_error(message); }
void verify(MPI_Comm comm)
{
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    require(ranks<=2,"Verification uses 1/2 ranks");
    AlgebraLayout l;
    l.global=3; l.owned=ranks==1?3:(rank==0?2:1); l.begin=rank==0?0:2;
    for(PetscInt i=0;i<l.owned;++i) l.local_to_global.push_back(l.begin+i);
    for(PetscInt id=0;id<l.global;++id) if(id<l.begin||id>=l.begin+l.owned) l.local_to_global.push_back(id);
    l.diagonal.assign(l.owned,l.owned); l.off_diagonal.assign(l.owned,l.global-l.owned);
    const char* names[]={"velocity","mesh","structure"};
    PetscInt index[3];
    for(std::size_t i=0;i<l.local_to_global.size();++i) index[l.local_to_global[i]]=i;
    for(PetscInt id=0;id<l.global;++id) {
        auto& field=l.fields[names[id]];
        if(id>=l.begin&&id<l.begin+l.owned) field.push_back(id);
    }
    NonlinearSystem system(comm,l);
    std::vector<PetscInt> bc;
    std::vector<double> prescribed;
    if(2>=l.begin&&2<l.begin+l.owned) { bc.push_back(2); prescribed.push_back(3); }
    SolverConfig config;
    for(const auto* name:names) {
        FieldTolerance t; t.relative_tolerance=0; t.absolute_tolerance=1e-11;
        config.fields.emplace(name,t);
    }
    std::vector<double> initial(3,0); initial[index[0]]=1;
    // 故意放宽 PETSc 总范数停止条件；字段验收必须让 Newton 继续到实际方程达标。
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_atol","1e30"));
    PetscObjectId matrix_id=0;
    const double* trial_buffer=nullptr;
    for(double alpha:{1e-8,1e8}) {
        config.fields.at("mesh").residual_scale=alpha;
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            if(trial_buffer) require(trial_buffer==x.data(),"Local trial storage was reallocated");
            trial_buffer=x.data();
            if(j) {
                PetscObjectId id; EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(j),&id));
                if(matrix_id) require(matrix_id==id,"Matrix storage was recreated between solves");
                matrix_id=id;
            }
            const double u=x[index[0]],m=x[index[1]];
            // 真解 u=m=sqrt(2)；受约束行的非零原始残量是反力，不能纳入物理方程范数。
            const double residual[]={u*u-2+.25*(u-m),alpha*(m-u),100+u};
            const double tangent[3][3]={{2*u+.25,-.25,0},{-alpha,alpha,0},{1,0,0}};
            const PetscInt columns[]={0,1,2};
            for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
                EONSIM_PETSC(VecSetValue(r,row,residual[row],ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,1,&row,3,columns,tangent[row],ADD_VALUES));
            }
        };
        const auto solved=system.solve(config,initial,bc,prescribed,assemble);
        require(std::abs(solved.values[index[0]]-std::sqrt(2.))<1e-11,"Velocity equation was masked");
        require(std::abs(solved.values[index[1]]-std::sqrt(2.))<1e-11,"Mesh equation was masked");
        require(solved.values[index[2]]==3,"Nonzero prescribed value changed");
        require(std::abs(solved.raw_residual[index[2]]-100-std::sqrt(2.))<1e-11,"Raw reaction was lost");
        require(solved.iterations>1,"Loose total norm bypassed field convergence");
        for(const auto& f:solved.field_residuals) {
            require(std::isfinite(f.rms)&&f.rms<=f.limit,"Field residual did not pass");
            if(f.name=="structure") {
                require(f.equation_rows==0&&f.constraint_rows==1,"Constrained rows counted as equations");
                require(f.rms==0&&f.constraint_max==0,"Reaction polluted convergence check");
            } else {
                require(f.equation_rows==1&&f.constraint_rows==0,"Owned field rows counted twice");
                require(std::abs(f.initial_rms-(f.name=="mesh"?1:.75))<1e-12,"Incorrect initial scaled norm");
            }
        }
        // PETSc skip 可以以正 reason 返回未迭代的状态；最终重新装配验收必须拒绝。
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_convergence_test","skip"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_max_it","0"));
        bool rejected=false;
        try { system.solve(config,initial,bc,prescribed,assemble); }
        catch(const StepRejected& e) { rejected=std::string(e.what()).find("Field acceptance failed")!=std::string::npos; }
        require(rejected,"Positive SNES reason bypassed final field acceptance");
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_convergence_test"));
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_max_it"));
    }
    // 1e-200 的平方会下溢，但它仍高于 1e-210；另两块已满足条件，不能由总范数放行。
    config.fields.at("mesh").residual_scale=1;
    // 旧约束行不能污染下一次求解；重新装配还须清掉前一个非对角算子的贡献。
    const auto diagonal=[&](const std::vector<double>& x,Vec r,Mat j) {
        for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
            EONSIM_PETSC(VecSetValue(r,row,2*(x[index[row]]-(row+1)),ADD_VALUES));
            if(j) EONSIM_PETSC(MatSetValue(j,row,row,2,ADD_VALUES));
        }
    };
    const std::vector<double> changed_value(prescribed.size(),7);
    const auto constrained=system.solve(config,initial,bc,changed_value,diagonal);
    require(constrained.values[index[2]]==7,"Updated constraint value was lost");
    const auto released=system.solve(config,initial,{}, {},diagonal);
    for(int row=0;row<3;++row) require(std::abs(released.values[index[row]]-(row+1))<1e-11,"Old constraints or matrix values survived reassembly");
    config.fields.at("mesh").absolute_tolerance=1e-210;
    const auto tiny_residual=[&](const std::vector<double>&,Vec r,Mat) {
        const PetscScalar* previous;
        EONSIM_PETSC(VecGetArrayRead(r,&previous));
        bool zero=true;
        for(PetscInt i=0;i<l.owned;++i) zero=zero&&previous[i]==0;
        EONSIM_PETSC(VecRestoreArrayRead(r,&previous));
        require(zero,"Cached zero norm skipped residual clearing");
        if(1>=l.begin&&1<l.begin+l.owned) EONSIM_PETSC(VecSetValue(r,1,1e-200,ADD_VALUES));
    };
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_convergence_test","skip"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_max_it","0"));
    bool rejected=false;
    try { system.solve(config,initial,bc,prescribed,tiny_residual); }
    catch(const StepRejected& e) { rejected=std::string(e.what()).find("Field acceptance failed: mesh")!=std::string::npos; }
    require(rejected,"Squared residual underflow bypassed acceptance");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_convergence_test"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_max_it"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_atol"));
    if(rank==0) std::cout<<"nonlinear field acceptance passed on "<<ranks<<" ranks\n";
}
}
int main(int argc,char** argv)
{
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    try { verify(PETSC_COMM_WORLD); }
    catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1); }
    return PetscFinalize();
}
