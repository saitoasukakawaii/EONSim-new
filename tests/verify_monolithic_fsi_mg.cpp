#include "eonsim/monolithic_fsi_mg.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <string>

using namespace eonsim;
namespace {
void check(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0; MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error(message);
}
struct Problem {
    static constexpr PetscInt nodes=24,fields=4,n=nodes*fields;
    MPI_Comm comm;
    PetscInt begin=0,end=0;
    PetscOwner<Mat,MatDestroy> matrix;
    std::vector<DofKey> semantics;
    std::vector<std::array<double,3>> coordinates;
    std::vector<unsigned char> trace;
    Problem(MPI_Comm communicator,bool empty_owner):comm(communicator) {
        int rank=0,size=0; MPI_Comm_rank(comm,&rank); MPI_Comm_size(comm,&size);
        const int owners=empty_owner&&size>1?size-1:size;
        begin=fields*(nodes*std::min(rank,owners)/owners);
        end=fields*(nodes*std::min(rank+1,owners)/owners);
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,end-begin,n,n,std::min<PetscInt>(16,end-begin),nullptr,
            std::min<PetscInt>(16,n-end+begin),nullptr,matrix.put()));
        EONSIM_PETSC(MatSetOption(matrix.get(),MAT_KEEP_NONZERO_PATTERN,PETSC_TRUE));
        for(PetscInt row=begin;row<end;++row) {
            const auto node=row/fields,field=row%fields;
            const auto domain=field==2?DofDomain::solid:field==3?DofDomain::mesh:DofDomain::fluid;
            const auto quantity=field==1?DofQuantity::pressure:field==3?DofQuantity::displacement:DofQuantity::velocity;
            semantics.push_back({node,domain,quantity,DofEntity::vertex,0,0,1});
            coordinates.push_back({static_cast<double>(node)/(nodes-1),0.,0.});
            trace.push_back(node==nodes/2||node==nodes/2-1);
        }
        fill(0);
    }
    void fill(int phase) {
        const double diagonal[4][4]={{8.,1.,-1.5,.2},{-1.,-.6,.15,0.},
            {-.7,.12,6.5,-.5},{0.,0.,-.3,3.5}};
        const double neighbor[4]={-1.3,.12,-.8,-.7};
        for(PetscInt row=begin;row<end;++row) {
            const auto node=row/fields,field=row%fields;
            for(PetscInt adjacent=std::max<PetscInt>(0,node-1);adjacent<=std::min<PetscInt>(nodes-1,node+1);++adjacent)
                for(PetscInt column_field=0;column_field<fields;++column_field) {
                    double value=adjacent==node?diagonal[field][column_field]:field==column_field?neighbor[field]:0.;
                    if(adjacent==node&&field==column_field) value*=1.+.09*phase;
                    if(field==0&&column_field==1&&adjacent!=node) value=.13*(adjacent-node);
                    if(field==1&&column_field==0&&adjacent!=node) value=-.13*(adjacent-node);
                    const auto column=fields*adjacent+column_field;
                    if(row==0) value=column==0?1.:0.;
                    EONSIM_PETSC(MatSetValue(matrix.get(),row,column,value,INSERT_VALUES));
                }
        }
        EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    }
};
void action(Problem& problem,KSP solver,int sample) {
    PetscOwner<Vec,VecDestroy> exact,rhs,actual,residual;
    EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),exact.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(exact.get(),actual.put())); EONSIM_PETSC(VecDuplicate(exact.get(),residual.put()));
    PetscScalar* values=nullptr; EONSIM_PETSC(VecGetArray(exact.get(),&values));
    for(PetscInt row=problem.begin;row<problem.end;++row)
        values[row-problem.begin]=std::sin((.11+.03*sample)*(row+1))+.2*std::cos(.17*(row/4+1));
    EONSIM_PETSC(VecRestoreArray(exact.get(),&values));
    EONSIM_PETSC(MatMult(problem.matrix.get(),exact.get(),rhs.get()));
    EONSIM_PETSC(VecSet(actual.get(),0)); EONSIM_PETSC(KSPSolve(solver,rhs.get(),actual.get()));
    KSPConvergedReason reason=KSP_CONVERGED_ITERATING; EONSIM_PETSC(KSPGetConvergedReason(solver,&reason));
    EONSIM_PETSC(MatMult(problem.matrix.get(),actual.get(),residual.get()));
    EONSIM_PETSC(VecAXPY(residual.get(),-1.,rhs.get()));
    PetscReal norm=0,bnorm=0,error=0,xnorm=0;
    EONSIM_PETSC(VecNorm(residual.get(),NORM_2,&norm)); EONSIM_PETSC(VecNorm(rhs.get(),NORM_2,&bnorm));
    EONSIM_PETSC(VecAXPY(actual.get(),-1.,exact.get()));
    EONSIM_PETSC(VecNorm(actual.get(),NORM_2,&error)); EONSIM_PETSC(VecNorm(exact.get(),NORM_2,&xnorm));
    check(problem.comm,reason>0&&norm<1e-10*bnorm&&error<1e-9*xnorm,
        "Monolithic MG failed the independent full indefinite matrix true-residual/manufactured-solution check");
}
void verify(MPI_Comm comm,const std::string& kind,bool single,bool empty_owner,bool enriched) {
    const std::string prefix="mgverify_",base="-"+prefix+"monolithic_mg_";
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"aggregate_nodes").c_str(),"4"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_limit").c_str(),"8"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"max_levels").c_str(),"6"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"energy_steps").c_str(),enriched?"1":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),enriched?"1":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_tolerance").c_str(),"1"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_processes").c_str(),"1"));
    const bool rebuild=kind=="vanka"&&!single&&enriched;
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_refresh_period").c_str(),rebuild?"3":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"single_precision").c_str(),single?"true":"false"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"smoother").c_str(),kind.c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"polynomial_degree").c_str(),"5"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"patch_maximum_size").c_str(),"256"));
    Problem problem(comm,empty_owner);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver; EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES)); EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),80));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,500));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,problem.coordinates,problem.trace,&updates);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    MonolithicFsiMgStats stats;
    check(comm,query_monolithic_fsi_mg_stats(pc,stats)&&stats.levels>=2&&stats.coarse_processes==1,
        "The full coupled problem did not create multiple levels and aggregate coarse MPI ranks");
    PetscInt eigenmodes=0;
    for(const auto& level:stats.transfers) {
        check(comm,level.rows>level.coarse_rows&&level.reproduction_error<1e-9&&
            std::isfinite(level.energy_after)&&level.energy_after<=level.energy_before*(1.+1e-11),
            "Transfer failed reduction, physical candidate preservation or constrained energy monotonicity");
        eigenmodes+=level.spectral_modes;
    }
    check(comm,!enriched||eigenmodes>0,"Adaptive spectral enrichment did not extract any independent low-energy modes");
    check(comm,stats.single_precision==single&&(!single||problem.begin==problem.end||stats.fp32_value_bytes>0),
        "Requested mixed V-cycle did not store local sparse coefficients in FP32");
    for(int phase=0;phase<2;++phase) {
        if(phase) {problem.fill(phase);updates.refresh(problem.matrix.get());}
        action(problem,solver.get(),phase);
        query_monolithic_fsi_mg_stats(pc,stats);
        check(comm,stats.refreshes==phase+1&&stats.applications>0&&stats.smoothers.size()+1==static_cast<std::size_t>(stats.levels),
            "Monolithic hierarchy did not refresh every Galerkin level");
        for(const auto& smoother:stats.smoothers) {
            check(comm,smoother.applications>0&&smoother.refreshes==phase+1,
                "A noncoarse level skipped smoothing or reused stale numeric factors");
            if(kind!="vanka") check(comm,smoother.polynomial_degree==5&&smoother.eigenvalue_upper>0,
                "Normal-equation Chebyshev did not configure its verified positive spectral interval");
        }
    }
    // The same numeric generation must hit the exact patch-factor cache. This
    // refresh is intentionally redundant: it tests invalidation independently
    // of whether the enclosing nonlinear driver chooses adaptive PC reuse.
    updates.refresh(problem.matrix.get());
    query_monolithic_fsi_mg_stats(pc,stats);
    if(kind=="vanka") for(const auto& smoother:stats.smoothers)
        check(comm,smoother.patches.patches==0||smoother.patches.cached_factorizations>0,
            "Unchanged multilevel Vanka factors were not reused");
    // A failed refresh cannot leave an old hierarchy marked ready. Matrix
    // recovery afterwards uses the same graph, then must pass the true residual.
    if(problem.begin==0&&problem.end>0) EONSIM_PETSC(MatSetValue(problem.matrix.get(),1,1,
        std::numeric_limits<double>::quiet_NaN(),INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
    bool rejected=false;
    try {updates.refresh(problem.matrix.get());} catch(const std::runtime_error&) {rejected=true;}
    check(comm,rejected,"Nonfinite hierarchy refresh was accepted");
    PetscOwner<Vec,VecDestroy> rhs,output;
    EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),output.put(),rhs.put()));
    EONSIM_PETSC(VecSet(rhs.get(),1.)); EONSIM_PETSC(PCApply(pc,rhs.get(),output.get()));
    PCFailedReason failure=PC_NOERROR; EONSIM_PETSC(PCGetFailedReason(pc,&failure));
    check(comm,failure==PC_SUBPC_ERROR,"Failed refresh left the previous hierarchy usable");
    EONSIM_PETSC(VecSet(rhs.get(),2.)); // Detect leaked read locks in failed apply.
    problem.fill(0); updates.refresh(problem.matrix.get()); action(problem,solver.get(),2);
    query_monolithic_fsi_mg_stats(pc,stats);
    check(comm,stats.hierarchy_rebuilds==(rebuild?2:1),"Scheduled spectral/energy hierarchy adaptation was not applied");
}
void run(MPI_Comm comm) {
    int size=0; MPI_Comm_size(comm,&size); check(comm,size==1||size==2||size==4,"Expected 1, 2 or 4 ranks");
    verify(comm,"vanka",false,false,true);
    verify(comm,"vanka",true,true,true);
    verify(comm,"chebyshev",false,false,true);
    verify(comm,"block_chebyshev",false,true,false);
    EONSIM_PETSC(PetscPrintf(comm,
        "Monolithic FSI MG: full indefinite manufactured solutions, multilevel Vanka, candidate preservation, energy descent, spectral enrichment, FP32 V-cycle, coarse MPI aggregation, numeric refresh/recovery and polynomial smoothers passed\n"));
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try {run(PETSC_COMM_WORLD);}
    catch(const std::exception& error) {std::cerr<<"Monolithic FSI MG verification failed: "<<error.what()<<'\n';result=1;}
    PetscFinalize(); return result;
}
