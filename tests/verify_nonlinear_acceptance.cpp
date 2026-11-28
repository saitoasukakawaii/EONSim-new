/** 非线性耦合小系统：极端方程尺度、空本地字段、约束反力及提前停止。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <sstream>
#include <array>

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
    const char* names[]={"velocity","mesh","structure"};
    PetscInt index[3];
    for(std::size_t i=0;i<l.local_to_global.size();++i) index[l.local_to_global[i]]=i;
    for(PetscInt id=0;id<l.global;++id) {
        auto& field=l.fields[names[id]];
        if(id>=l.begin&&id<l.begin+l.owned) field.push_back(id);
    }
    // The only pattern producer may be remote from a row owner. Adopt its
    // completed graph with no fallback row counts; destroying the preallocator
    // and moving the owner must leave exactly the same usable AIJ object.
    PetscOwner<Mat,MatDestroy> pattern;
    {
        PetscOwner<Mat,MatDestroy> graph;
        EONSIM_PETSC(MatCreate(comm,graph.put()));
        EONSIM_PETSC(MatSetSizes(graph.get(),l.owned,l.owned,l.global,l.global));
        EONSIM_PETSC(MatSetType(graph.get(),MATPREALLOCATOR));
        EONSIM_PETSC(MatSetUp(graph.get()));
        const PetscInt ids[]={0,1,2};
        if(rank==ranks-1) EONSIM_PETSC(MatSetValues(graph.get(),3,ids,3,ids,nullptr,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(graph.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(graph.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatCreate(comm,pattern.put()));
        EONSIM_PETSC(MatSetSizes(pattern.get(),l.owned,l.owned,l.global,l.global));
        EONSIM_PETSC(MatSetType(pattern.get(),MATAIJ));
        EONSIM_PETSC(MatPreallocatorPreallocate(graph.get(),PETSC_TRUE,pattern.get()));
    }
    PetscObjectId matrix_id=0;
    EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(pattern.get()),&matrix_id));
    NonlinearSystem system(comm,l,std::move(pattern));
    require(pattern.get()==nullptr,"Moved Jacobian pattern retained a second owner");
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
    const double* trial_buffer=nullptr;
    for(double alpha:{1e-8,1e8}) {
        // 第二组启用额外 MatMult/字段诊断，验收基线与反力必须仍保持正确。
        if(alpha==1e8) EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_report","true"));
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
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-linear_report"));
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
    if(std::numeric_limits<long double>::digits>std::numeric_limits<double>::digits) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_lu_refinement_steps","2"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_lu_refinement_rtol","1e-20"));
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_lu_refinement_atol","1e-23"));
        const auto exact=system.solve(config,initial,bc,changed_value,diagonal);
        require(exact.values[index[2]]==7,"LU refinement changed a lifted constraint");
        // Non-dyadic factor multipliers, exactly representable coupled solution.
        const auto integers=[&](const std::vector<double>& x,Vec r,Mat j) {
            const double coefficients[3][3]={{7,2,1},{2,9,-3},{-1,4,7}};
            const PetscInt columns[]={0,1,2};
            for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
                double value=0;
                for(int k=0;k<3;++k) value+=coefficients[row][k]*(x[index[k]]-(k+1));
                EONSIM_PETSC(VecSetValue(r,row,value,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,1,&row,3,columns,coefficients[row],ADD_VALUES));
            }
        };
        const auto represented=system.solve(config,std::vector<double>(3,0),{}, {},integers);
        for(int k=0;k<3;++k) require(represented.values[index[k]]==k+1,"Wrong returned FP64 solution");
        // FP64 computes 3*(1/3)==1, but the stored vector fails this original-unit
        // tolerance. A positive PREONLY reason must never admit its Newton step.
        const auto thirds=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
                EONSIM_PETSC(VecSetValue(r,row,3*x[index[row]]-1,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,row,row,3.,ADD_VALUES));
            }
        };
        bool failed=false;
        try { system.solve(config,std::vector<double>(3,0),{}, {},thirds); }
        catch(const std::runtime_error& error) {
            failed=std::string(error.what()).find("LU refinement failed the original equation")!=std::string::npos;
        }
        require(failed,"Rounded direct correction bypassed the explicit original-equation gate");
        for(const char* option:{"-linear_lu_refinement_steps","-linear_lu_refinement_rtol","-linear_lu_refinement_atol"})
            EONSIM_PETSC(PetscOptionsClearValue(nullptr,option));
    }
    // preonly/Jacobi 报告范数为零，但首个近似线性解的实际缺陷是 (-1.5,-1.5,0)。
    // 直接检查非零诊断，避免仅用精确 LU 的近零结果掩盖错误算子或字段映射。
    const auto coupled=[&](const std::vector<double>& x,Vec r,Mat j) {
        const double residual[]={2*x[index[0]]+x[index[1]]-3,x[index[0]]+2*x[index[1]]-3,x[index[2]]-3};
        const double tangent[3][3]={{2,1,0},{1,2,0},{0,0,1}};
        const PetscInt columns[]={0,1,2};
        for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
            EONSIM_PETSC(VecSetValue(r,row,residual[row],ADD_VALUES));
            if(j) EONSIM_PETSC(MatSetValues(j,1,&row,3,columns,tangent[row],ADD_VALUES));
        }
    };
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_type","jacobi"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-linear_report","true"));
    config.maximum_iterations=100;
    std::ostringstream diagnostic_output;
    auto* saved=std::cout.rdbuf(diagnostic_output.rdbuf());
    NonlinearResult approximate;
    try { approximate=system.solve(config,std::vector<double>(3,0),bc,prescribed,coupled); }
    catch(...) { std::cout.rdbuf(saved); throw; }
    std::cout.rdbuf(saved);
    require(std::abs(approximate.values[index[0]]-1)<1e-11&&std::abs(approximate.values[index[1]]-1)<1e-11,
            "Diagnostic changed inexact Newton convergence");
    if(rank==0) {
        const auto output=diagnostic_output.str();
        require(output.find("linear_field_residual solve=1 name=velocity rms=1.5 ")!=std::string::npos,
                "True linear velocity residual differs from known Jacobi defect");
        require(output.find("linear_field_residual solve=1 name=mesh rms=1.5 ")!=std::string::npos,
                "True linear mesh residual differs from known Jacobi defect");
        require(output.find("linear_field_residual solve=1 name=structure rms=0 constraint_max=0 ")!=std::string::npos,
                "Linear constraints were mixed into physical equations");
    }
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_type"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-linear_report"));
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
void verify_lifetime(MPI_Comm comm,bool coo,bool matrix_coo)
{
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    AlgebraLayout layout;
    layout.global=3; layout.owned=ranks==1?3:(rank==0?2:1); layout.begin=rank==0?0:2;
    for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
        layout.local_to_global.push_back(row); layout.fields["state"].push_back(row);
    }
    for(PetscInt row=0;row<3;++row)
        if(row<layout.begin||row>=layout.begin+layout.owned) layout.local_to_global.push_back(row);
    layout.diagonal.assign(layout.owned,1); layout.off_diagonal.assign(layout.owned,0);
    std::array<PetscInt,3> index{};
    for(std::size_t i=0;i<layout.local_to_global.size();++i) index[layout.local_to_global[i]]=i;
    NonlinearSystem system(comm,layout);
    const bool producer=rank==ranks-1;
    if(coo) {
        // One remote-only producer, repeated rows, an ignored negative row,
        // and a rank with no contributions exercise the complete COO contract.
        const std::vector<PetscInt> rows=producer?std::vector<PetscInt>{0,0,1,1,2,2,-1}:std::vector<PetscInt>{};
        system.set_residual_coo(rows);
    }
    if(matrix_coo) {
        const std::vector<PetscInt> diagonal=producer?std::vector<PetscInt>{0,1,2}:std::vector<PetscInt>{};
        system.set_jacobian_coo(diagonal,diagonal);
    }
    auto* residual_buffer=system.residual_coo_values();
    auto* matrix_buffer=system.jacobian_coo_values();
    PetscObjectId matrix_id=0;
    const auto publish=[&](Vec r,Mat j,const std::array<double,3>& residual,const std::array<double,3>& tangent) {
        if(j) {
            PetscObjectId id=0; EONSIM_PETSC(PetscObjectGetId(reinterpret_cast<PetscObject>(j),&id));
            require(!matrix_id||matrix_id==id,"Solver reset rebuilt the fixed matrix"); matrix_id=id;
        }
        require(residual_buffer==system.residual_coo_values(),"Residual COO buffer changed address");
        require(matrix_buffer==system.jacobian_coo_values(),"Jacobian COO buffer changed address");
        if(!producer) return;
        for(PetscInt row=0;row<3;++row) {
            if(coo) {
                require(residual_buffer[2*row]==0&&residual_buffer[2*row+1]==0,"Residual COO buffer was not cleared");
                residual_buffer[2*row]=.25*residual[row]; residual_buffer[2*row+1]=.75*residual[row];
            } else {
                EONSIM_PETSC(VecSetValue(r,row,residual[row],ADD_VALUES));
            }
            if(j) {
                if(matrix_coo) matrix_buffer[row]=tangent[row];
                else EONSIM_PETSC(MatSetValue(j,row,row,tangent[row],ADD_VALUES));
            }
        }
        if(coo) residual_buffer[6]=1e99;
    };
    const auto linear=[&](double coefficient,double target,bool fail=false) {
        // Returned temporary callables must not remain borrowed by a cached SNES.
        return [&,coefficient,target,fail](const std::vector<double>& x,Vec r,Mat j) {
            std::array<double,3> residual{},tangent{};
            for(int row=0;row<3;++row) {
                residual[row]=coefficient*(x[index[row]]-target-row); tangent[row]=coefficient;
            }
            publish(r,j,residual,tangent);
            if(fail&&j&&rank==0) throw std::runtime_error("intentional lifetime callback failure");
        };
    };
    SolverConfig config;
    config.maximum_iterations=100;
    FieldTolerance tolerance; tolerance.absolute_tolerance=1e-10; tolerance.relative_tolerance=0;
    config.fields.emplace("state",tolerance);
    const std::vector<double> initial(3,0.);
    std::vector<PetscInt> constrained_rows;
    if(2>=layout.begin&&2<layout.begin+layout.owned) constrained_rows.push_back(2);
    const auto check_linear=[&](double coefficient,double target,bool constrained,double prescribed) {
        const auto& rows=constrained?constrained_rows:std::vector<PetscInt>{};
        const std::vector<double> values(rows.size(),prescribed);
        auto result=system.solve(config,initial,rows,values,linear(coefficient,target));
        for(int row=0;row<3;++row) {
            const double expected=constrained&&row==2?prescribed:target+row;
            require(std::abs(result.values[index[row]]-expected)<1e-9,"Retained solver used stale numerical factors or constraints");
            const double reaction=constrained&&row==2?coefficient*(prescribed-target-row):0.;
            require(std::abs(result.raw_residual[index[row]]-reaction)<1e-8,"Retained solver changed raw reactions");
        }
        require(result.iterations==1&&result.linear_iterations==1,"Linear equation did not use a fresh exact numeric factor");
        return result;
    };
    auto previous=check_linear(2,1,true,11);
    require(!previous.solver_reused&&previous.solver_generation==1,"First solve did not construct its solver");
    auto next=check_linear(5,2,true,13);
    require(next.solver_reused&&next.solver_generation==previous.solver_generation,"Changed values unnecessarily discarded the solver");
    previous=next; next=check_linear(7,3,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Changed constraint support did not reset the solver");
    require(next.field_residuals.at(0).constraint_rows==0,"Cached field groups retained released constraints");
    previous=next; next=check_linear(17,4,false,0);
    require(next.solver_reused&&next.solver_generation==previous.solver_generation,"Stable unconstrained solve did not reuse its solver");
    previous=next; ++config.maximum_iterations; next=check_linear(3,5,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Changed SolverConfig did not reset the solver");
    previous=next; config.fields.at("state").residual_scale=3; next=check_linear(11,6,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Changed field tolerances did not reset the solver");
    require(next.field_residuals.at(0).tolerance.residual_scale==3,"Cached field tolerance was stale");
    previous=next; EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_type","jacobi")); next=check_linear(13,7,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Changed PETSc options did not reset the solver");
    previous=next; EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-pc_type")); next=check_linear(19,8,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Cleared PETSc options did not restore fresh defaults");
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_reuse","false"));
    previous=check_linear(2,9,false,0); next=check_linear(5,10,false,0);
    require(!previous.solver_reused&&!next.solver_reused&&next.solver_generation==previous.solver_generation+1,
            "Explicit fresh-solver reference reused a solver");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_reuse"));
    if(ranks==2) {
        // Only the retention policy differs. Collective SNES destruction must
        // not leave the other rank holding or using a different generation.
        if(rank==0) EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_reuse","false"));
        previous=check_linear(3,9,false,0); next=check_linear(7,10,false,0);
        require(!previous.solver_reused&&!next.solver_reused&&next.solver_generation==previous.solver_generation+1,
                "Rank-local fresh policy broke collective solver lifetime");
        if(rank==0) EONSIM_PETSC(PetscOptionsClearValue(nullptr,"-nonlinear_reuse"));
    }
    previous=check_linear(7,11,false,0);
    EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
    bool failed=false;
    try { system.solve(config,initial,{}, {},linear(11,12,true)); }
    catch(const std::runtime_error& e) { failed=std::string(e.what()).find("intentional lifetime callback failure")!=std::string::npos; }
    EONSIM_PETSC(PetscPopErrorHandler());
    require(failed,"Fatal callback was not propagated collectively");
    next=check_linear(13,13,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Failed solver state survived the next solve");
    previous=next;
    bool rejected=false;
    const auto reject=[&](const std::vector<double>& x,Vec r,Mat j) {
        linear(3,14)(x,r,j);
        if(rank==0) throw StepRejected("intentional initial rejection");
    };
    try { system.solve(config,initial,{}, {},reject); }
    catch(const StepRejected&) { rejected=true; }
    require(rejected,"Initial domain rejection was not propagated");
    next=check_linear(17,15,false,0);
    require(!next.solver_reused&&next.solver_generation==previous.solver_generation+1,"Rejected attempt did not invalidate its solver");
    // The first full Newton step exceeds the domain. Backtracking must evaluate
    // and prepare its own residual work Vec without publishing rejected COO data.
    const auto cubic=[&](const std::vector<double>& x,Vec r,Mat j) {
        std::array<double,3> residual{},tangent{};
        for(int row=0;row<3;++row) {
            const auto value=x[index[row]],target=double(row+2);
            residual[row]=value*value*value-target*target*target; tangent[row]=3*value*value;
        }
        publish(r,j,residual,tangent);
        if(!j&&rank==0&&(x[index[0]]>10||x[index[1]]>10)) throw StepRejected("cubic trial outside domain");
    };
    const std::vector<double> cubic_initial(3,.25),prescribed(constrained_rows.size(),7);
    previous=system.solve(config,cubic_initial,constrained_rows,prescribed,cubic);
    require(previous.domain_rejections>0,"Cubic check did not exercise line-search domain recovery");
    require(std::abs(previous.values[index[0]]-2)<1e-9&&std::abs(previous.values[index[1]]-3)<1e-9&&previous.values[index[2]]==7,
            "Line-search residual assembly changed the nonlinear solution");
    require(std::abs(previous.raw_residual[index[2]]-279)<1e-9,"COO raw reaction lost constrained-row contributions");
    next=system.solve(config,cubic_initial,constrained_rows,prescribed,cubic);
    require(next.solver_reused&&next.solver_generation==previous.solver_generation&&
            next.iterations==previous.iterations&&next.linear_iterations==previous.linear_iterations,
            "Retained Newton/line-search state changed the repeated solve trajectory");
    // A stationary exact solution needs the initial function and one new final
    // physical evaluation. Reactions must retain the constrained row and its
    // remote ghost, while acceptance sees the replaced zero constraint defect.
    std::vector<double> exact(3);
    for(int row=0;row<3;++row) exact[index[row]]=row==2?11:row+1;
    const std::vector<double> exact_prescribed(constrained_rows.size(),11);
    int evaluations=0;
    const auto exact_callback=[&](const std::vector<double>& x,Vec r,Mat j) {
        ++evaluations;
        linear(2,1)(x,r,j);
    };
    const auto stationary=system.solve(config,exact,constrained_rows,exact_prescribed,exact_callback);
    require(stationary.iterations==0&&evaluations==2,"Final acceptance duplicated or skipped a fresh physical evaluation");
    require(stationary.values==exact,"Final solution lost owned or ghost values");
    require(stationary.raw_residual[index[0]]==0&&stationary.raw_residual[index[1]]==0&&
            stationary.raw_residual[index[2]]==16,"Raw and constrained residuals were mixed during finalization");
    require(stationary.residual_norm==0&&stationary.field_residuals.front().constraint_max==0,
            "Raw reaction polluted final acceptance");
    // Fault injection changes a free equation only in the final evaluation.
    // Reusing SNES's already accepted function would incorrectly return success.
    evaluations=0;
    const auto changed_final=[&](const std::vector<double>& x,Vec r,Mat j) {
        ++evaluations;
        std::array<double,3> residual{2*(x[index[0]]-1),2*(x[index[1]]-2),2*(x[index[2]]-3)};
        if(evaluations==2) residual[0]=1;
        publish(r,j,residual,{2,2,2});
    };
    rejected=false;
    try { system.solve(config,exact,constrained_rows,exact_prescribed,changed_final); }
    catch(const StepRejected& e) { rejected=std::string(e.what()).find("Field acceptance failed")!=std::string::npos; }
    require(rejected&&evaluations==2,"Fresh final physical acceptance was bypassed");
    evaluations=0;
    const auto recovered=system.solve(config,exact,constrained_rows,exact_prescribed,exact_callback);
    require(!recovered.solver_reused&&evaluations==2&&recovered.raw_residual[index[2]]==16,
            "Final rejection left a stale solver or raw reaction");
    bool late_pattern=false;
    try { system.set_residual_coo({}); }
    catch(const std::runtime_error&) { late_pattern=true; }
    require(late_pattern,"Residual COO configuration changed after solving");
    if(rank==0) std::cout<<"nonlinear lifetime passed coo="<<coo<<" matrix_coo="<<matrix_coo<<" ranks="<<ranks<<'\n';
}
void verify_initial_jacobian(MPI_Comm comm,bool semantic)
{
    int rank,ranks; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&ranks);
    AlgebraLayout layout;
    layout.global=4; layout.owned=ranks==1?4:2; layout.begin=rank*layout.owned;
    layout.diagonal.assign(layout.owned,layout.owned);
    layout.off_diagonal.assign(layout.owned,layout.global-layout.owned);
    layout.fields["velocity"]={}; layout.fields["pressure"]={};
    for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
        layout.local_to_global.push_back(row);
        const bool velocity=row%2==0;
        layout.fields[velocity?"velocity":"pressure"].push_back(row);
        layout.owned_semantics.push_back({row/2,DofDomain::fluid,
            velocity?DofQuantity::velocity:DofQuantity::pressure,DofEntity::vertex,0,0,1});
    }
    for(PetscInt row=0;row<4;++row)
        if(row<layout.begin||row>=layout.begin+layout.owned) layout.local_to_global.push_back(row);
    std::array<PetscInt,4> index{};
    for(std::size_t i=0;i<layout.local_to_global.size();++i) index[layout.local_to_global[i]]=i;
    NonlinearSystem reference(comm,layout),optimized(comm,layout);
    SolverConfig config;
    config.maximum_iterations=40;
    config.pc_recipe=semantic?"physics":"";
    FieldTolerance tolerance; tolerance.absolute_tolerance=1e-10; tolerance.relative_tolerance=0;
    config.fields.emplace("velocity",tolerance); config.fields.emplace("pressure",tolerance);
    if(semantic) EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-pc_plan_schur_approx","nodal"));
    else EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-schur_pc","true"));
    // The independent outer solve sees the full coupled matrix. Small Jacobi
    // subsolves avoid turning this lifecycle check into an AMG performance test.
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-fieldsplit_velocity_pc_type","jacobi"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-fieldsplit_pressure_pc_type","jacobi"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-ksp_rtol","1e-12"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-ksp_atol","1e-14"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-solver_rank_report","true"));
    const std::array<double,4> target{2.,.5,3.,-.25};
    const auto callback=[&](double coefficient,double cubic,bool constrained,bool fail,PetscInt& calls) {
        return [&,coefficient,cubic,constrained,fail](const std::vector<double>& x,Vec r,Mat j) {
            if(j) ++calls;
            const double a[4][4]={{3*coefficient,.25,.1,0},{.5,-2*coefficient,0,.05},
                                  {.1,0,4*coefficient,.25},{0,.05,.5,-3*coefficient}};
            const PetscInt columns[]={0,1,2,3};
            for(PetscInt row=layout.begin;row<layout.begin+layout.owned;++row) {
                double residual=0; std::array<double,4> tangent{};
                for(int column=0;column<4;++column) {
                    residual+=a[row][column]*(x[index[column]]-target[column]);
                    tangent[column]=a[row][column];
                }
                if(row%2==0) {
                    const double value=x[index[row]],exact=target[row];
                    residual+=cubic*(value*value*value-exact*exact*exact);
                    tangent[row]+=3*cubic*value*value;
                }
                if(constrained&&row==2) residual+=7;
                EONSIM_PETSC(VecSetValue(r,row,residual,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,1,&row,4,columns,tangent.data(),ADD_VALUES));
            }
            if(fail&&j&&rank==ranks-1) throw std::runtime_error("initial Jacobian failure control");
            if(cubic&&!j&&rank==0&&(x[index[0]]>4||x[index[2]]>4))
                throw StepRejected("initial Jacobian line-search domain control");
        };
    };
    const auto run=[&](NonlinearSystem& system,bool reuse,double coefficient,double cubic,
                       bool constrained,bool fail=false,bool exact=false,bool local_disable=false) {
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,"-nonlinear_initial_jacobian_reuse",
            reuse&&!(local_disable&&rank==0)?"true":"false"));
        std::vector<PetscInt> rows;
        if(constrained&&2>=layout.begin&&2<layout.begin+layout.owned) rows.push_back(2);
        const std::vector<double> prescribed(rows.size(),target[2]);
        std::vector<double> initial(layout.local_to_global.size(),.25);
        if(exact) for(int row=0;row<4;++row) initial[index[row]]=target[row];
        PetscInt calls=0;
        auto result=system.solve(config,initial,rows,prescribed,callback(coefficient,cubic,constrained,fail,calls));
        require(calls==result.jacobian_assemblies,"Reported Jacobian work differs from physical callback count");
        require(result.jacobian_assemblies==result.initial_jacobian_assemblies+
            result.jacobian_callbacks-result.initial_jacobian_reuses,"Jacobian accounting lost a startup or callback evaluation");
        require(result.jacobian_callbacks==result.iterations,"Newton Jacobian callback count differs from accepted corrections");
        for(int row=0;row<4;++row) {
            require(std::abs(result.values[index[row]]-target[row])<1e-9,"Initial Jacobian reuse changed a coupled physical solution");
            const double expected=constrained&&row==2?7.:0.;
            require(std::abs(result.raw_residual[index[row]]-expected)<1e-8,"Initial Jacobian reuse changed owned/ghost reactions");
        }
        if(!exact) {
            require(result.jacobian_callbacks>0,"Jacobian check did not perform a Newton correction");
            require(result.user_schur_updates==(semantic?result.jacobian_assemblies:0),
                    "Nodal USER Schur was stale or refreshed more than once per numerical Jacobian");
            if(reuse&&!local_disable) {
                require(result.jacobian_assemblies==result.iterations,"Optimized Schur path retained redundant startup assembly");
                require(result.initial_jacobian_reuses==result.initial_jacobian_assemblies,
                        "Startup tangent was not used exactly once by the first Newton callback");
                require(result.initial_jacobian_deferred==(result.initial_jacobian_assemblies==0),
                        "Retained Schur path did not defer its first numeric update");
            } else {
                require(result.initial_jacobian_assemblies==1&&result.initial_jacobian_reuses==0&&
                        !result.initial_jacobian_deferred&&result.jacobian_assemblies==result.iterations+1,
                        "Disabled initial reuse did not retain the independent reference path");
            }
        }
        return result;
    };
    const auto pair=[&](double coefficient,double cubic,bool constrained) {
        const auto baseline=run(reference,false,coefficient,cubic,constrained);
        const auto candidate=run(optimized,true,coefficient,cubic,constrained);
        require(baseline.iterations==candidate.iterations&&baseline.linear_iterations==candidate.linear_iterations&&
                baseline.domain_rejections==candidate.domain_rejections,"Initial Jacobian optimization changed the solver trajectory");
        require(baseline.jacobian_assemblies==candidate.jacobian_assemblies+1,
                "Paired Schur solve did not remove exactly one redundant Jacobian");
        for(std::size_t i=0;i<baseline.values.size();++i)
            require(std::abs(baseline.values[i]-candidate.values[i])<1e-12,"Paired Schur solutions differ");
        return candidate;
    };
    auto first=pair(2,0,true);
    require(!first.solver_reused&&first.initial_jacobian_reuses==1,"Fresh Schur solver did not consume its startup tangent");
    auto changed=pair(5,0,true);
    require(changed.solver_reused&&changed.initial_jacobian_deferred,"Changed coefficients did not update a retained Schur solver");
    auto nonlinear=pair(.2,1,false);
    require(!nonlinear.solver_reused&&nonlinear.domain_rejections>0,
            "Constraint change or line-search rejection was not exercised");
    auto repeated=pair(.2,1,false);
    require(repeated.solver_reused&&repeated.initial_jacobian_deferred&&repeated.iterations==nonlinear.iterations,
            "Retained nonlinear solve cached a previous step tangent or line-search state");
    EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler,nullptr));
    for(bool reuse:{false,true}) {
        bool failed=false;
        try { run(reuse?optimized:reference,reuse,7,0,false,true); }
        catch(const std::runtime_error& e) { failed=std::string(e.what()).find("initial Jacobian failure control")!=std::string::npos; }
        require(failed,"Rank-local Jacobian failure did not invalidate the startup state collectively");
    }
    EONSIM_PETSC(PetscPopErrorHandler());
    auto recovered=pair(7,0,false);
    require(!recovered.solver_reused&&recovered.initial_jacobian_reuses==1,
            "Failed Jacobian left a cached matrix or numeric Schur in the next solve");
    const auto stationary=run(optimized,true,7,0,false,false,true);
    require(stationary.iterations==0&&stationary.jacobian_assemblies==0&&stationary.user_schur_updates==0,
            "Converged retained state assembled or refreshed an unused Jacobian/Schur");
    if(ranks==2) run(optimized,true,11,0,false,false,false,true);
    for(const auto* option:{"-pc_plan_schur_approx","-schur_pc","-fieldsplit_velocity_pc_type",
            "-fieldsplit_pressure_pc_type","-ksp_rtol","-ksp_atol","-solver_rank_report","-nonlinear_initial_jacobian_reuse"})
        EONSIM_PETSC(PetscOptionsClearValue(nullptr,option));
    if(rank==0) std::cout<<"initial Jacobian reuse passed semantic="<<semantic<<" ranks="<<ranks<<'\n';
}
}
int main(int argc,char** argv)
{
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    try {
        verify(PETSC_COMM_WORLD);
        for(bool residual_coo:{false,true}) for(bool matrix_coo:{false,true})
            verify_lifetime(PETSC_COMM_WORLD,residual_coo,matrix_coo);
        verify_initial_jacobian(PETSC_COMM_WORLD,false);
        verify_initial_jacobian(PETSC_COMM_WORLD,true);
    }
    catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; MPI_Abort(PETSC_COMM_WORLD,1); }
    return PetscFinalize();
}
