/** 回溯处理非法试探点；单 rank 的部分远程装配不得污染下一候选点；PC 故障不可缩步掩盖。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
namespace {
void require(bool condition,const char* message) { if(!condition) throw std::runtime_error(message); }
void verify() {
    const auto comm=PETSC_COMM_WORLD;
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    require(ranks<=2,"Verification uses 1/2 ranks");
    AlgebraLayout l; l.global=2; l.owned=ranks==1?2:1; l.begin=rank;
    for(PetscInt row=0;row<l.owned;++row) l.local_to_global.push_back(l.begin+row);
    if(ranks==2) l.local_to_global.push_back(1-rank);
    l.diagonal.assign(l.owned,l.owned); l.off_diagonal.assign(l.owned,l.global-l.owned);
    for(int row=0;row<2;++row) {
        auto& ids=l.fields[row==0?"structure":"mesh"];
        if(row>=l.begin&&row<l.begin+l.owned) ids.push_back(row);
    }
    NonlinearSystem system(comm,l);
    const int uindex=rank==0?0:1,vindex=1-uindex;
    const std::vector<double> initial(2,2);
    SolverConfig config; config.maximum_iterations=30;
    int failure_mode=0,invalid_trials=0;
    const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
        // 最后一个 rank 先向 row 0 写入（2 rank 时为远程 stash），之后才可能发现试探点非法。
        if(rank==ranks-1) {
            EONSIM_PETSC(VecSetValue(r,0,7,ADD_VALUES));
            if(failure_mode==1&&j) throw StepRejected("Jacobian outside constitutive domain");
            if(failure_mode==2) throw std::runtime_error("Invalid constitutive input");
            if(x[uindex]<=0) { ++invalid_trials; throw StepRejected("Logarithm requires positive stretch"); }
        }
        if(rank==0) {
            // 非 owner 也看到非法 ghost，但此测试只由最后一个 rank 报 domain error。
            const double u=x[uindex],v=x[vindex];
            if(u>0) {
                EONSIM_PETSC(VecSetValue(r,0,std::log(u/.1)+.2*(u-v)-7,ADD_VALUES));
                if(j) {
                    const PetscInt row=0,cols[]={0,1}; const double tangent[]={1/u+.2,-.2};
                    EONSIM_PETSC(MatSetValues(j,1,&row,2,cols,tangent,ADD_VALUES));
                }
            }
        }
        if(rank==ranks-1) {
            EONSIM_PETSC(VecSetValue(r,1,x[vindex]-x[uindex],ADD_VALUES));
            if(j) {
                const PetscInt row=1,cols[]={0,1}; const double tangent[]={-1,1};
                EONSIM_PETSC(MatSetValues(j,1,&row,2,cols,tangent,ADD_VALUES));
            }
        }
    };
    const auto solved=system.solve(config,initial,{}, {},assemble);
    require(solved.domain_rejections>0,"Expected rejected full Newton trial");
    require(std::abs(solved.values[uindex]-.1)<1e-10&&std::abs(solved.values[vindex]-.1)<1e-10,
            "Rejected trial left remote contributions in the next evaluation");
    int total=0; MPI_Allreduce(&invalid_trials,&total,1,MPI_INT,MPI_SUM,comm);
    require(total>0,"Positive-domain restriction was not exercised");
    require(initial==std::vector<double>(2,2),"Trial mutated accepted input");
    failure_mode=1;
    bool rejected=false;
    try { system.solve(config,initial,{}, {},assemble); }
    catch(const StepRejected& e) { rejected=std::string(e.what()).find("Jacobian outside")!=std::string::npos; }
    require(rejected,"Jacobian domain error was ignored");
    failure_mode=0;
    const auto recovered=system.solve(config,initial,{}, {},assemble);
    require(std::abs(recovered.values[uindex]-.1)<1e-10&&std::abs(recovered.values[vindex]-.1)<1e-10,
            "Persistent storage retained values from a rejected solve");
    failure_mode=2; bool fatal=false;
    try { system.solve(config,initial,{}, {},assemble); }
    catch(const StepRejected&) { throw std::runtime_error("Invalid input was classified as retryable"); }
    catch(const std::runtime_error& e) { fatal=std::string(e.what()).find("Invalid constitutive input")!=std::string::npos; }
    require(fatal,"Fatal callback error was not propagated");
    failure_mode=0;
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-snes_max_it","0"));
    rejected=false;
    try { system.solve(config,initial,{}, {},assemble); } catch(const StepRejected&) { rejected=true; }
    require(rejected,"Nonlinear iteration limit should reject the time step");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-snes_max_it"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_report","true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-ksp_type","gmres"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_type","none"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-ksp_max_it","0"));
    fatal=false;
    try { system.solve(config,initial,{}, {},assemble); }
    catch(const StepRejected&) { throw std::runtime_error("Linear iteration exhaustion was classified as retryable"); }
    catch(const std::runtime_error& e) {
        const std::string message=e.what();
        fatal=message.find("ksp_reason_name=DIVERGED_ITS")!=std::string::npos&&
              message.find("pc_reason_name=FACTOR_NOERROR")!=std::string::npos;
    }
    require(fatal,"Linear exhaustion was not distinguished from PC failure");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-ksp_type"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_type"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-ksp_max_it"));
    const auto singular=[&](const std::vector<double>&,Vec r,Mat j) {
        for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
            EONSIM_PETSC(VecSetValue(r,row,1,ADD_VALUES));
            if(j) EONSIM_PETSC(MatSetValue(j,row,row,row==1?0:1,ADD_VALUES));
        }
    };
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_type","bjacobi"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-sub_ksp_type","preonly"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-sub_pc_type","lu"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-sub_pc_factor_mat_solver_type","petsc"));
    EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
    fatal=false;
    try { system.solve(config,initial,{}, {},singular); }
    catch(const StepRejected&) { throw std::runtime_error("PC failure was classified as retryable"); }
    catch(const std::runtime_error& e) {
        const std::string message=e.what();
        fatal=message.find("Linear solver failure:")!=std::string::npos;
        require(message.find("path=root/local0")!=std::string::npos,"Missing local PC diagnostic");
        require(message.find("rank="+std::to_string(rank))!=std::string::npos,"Missing diagnostic rank");
        if(rank==ranks-1) {
            require(message.find("FACTOR_NUMERIC_ZEROPIVOT")!=std::string::npos,"Missing zero-pivot cause in child PC");
        }
    }
    EONSIM_PETSC(PetscPopErrorHandler());
    require(fatal,"PC failure did not provide linear solver diagnostics");
    // 初态已满足方程时 PC 尚未 setup；报告必须保留成功结果，不能为诊断额外 setup。
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-solver_report","true"));
    const auto zero=[](const std::vector<double>&,Vec,Mat) {};
    const auto unchanged=system.solve(config,initial,{}, {},zero);
    require(unchanged.iterations==0&&unchanged.values==initial,"Diagnostics changed an initially converged solve");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-solver_report"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-linear_report"));
    if(rank==0) std::cout<<"trial backtracking, partial assembly and failure classification passed on "<<ranks<<" ranks\n";
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    try { verify(); } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1); }
    return PetscFinalize();
}
