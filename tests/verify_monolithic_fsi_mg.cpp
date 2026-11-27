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
void vanka_coverage(MPI_Comm comm,const MonolithicFsiMgStats& stats,bool enriched) {
    check(comm,stats.levels>=3,"Bounded coarse Vanka regression needs an intermediate level");
    for(std::size_t level=0;level<stats.smoothers.size();++level) {
        const auto& patch=stats.smoothers[level].patches;
        const PetscInt local[]={patch.patch_rows,patch.covered_owned_rows,patch.patches,patch.interface_patches};
        PetscInt total[4]{};
        MPI_Allreduce(local,total,4,MPIU_INT,MPI_SUM,comm);
        const auto active=level==0?Problem::n-1:stats.transfers[level].rows;
        check(comm,total[1]==active&&total[2]>0&&total[3]>0&&patch.largest_patch<=12,
            "A Vanka level omitted active/interface rows or exceeded the fixed patch budget");
        if(level==0) {
            check(comm,patch.overlap==1,"Fine Vanka lost its default one-ring overlap");
        } else {
            // Four independent physical candidates are present in every block
            // of this problem, plus at most one independently selected mode.
            // Count actual patch rows, not the intended aggregation metadata.
            check(comm,patch.overlap==0&&total[0]==active&&total[0]>=4*total[2]&&
                patch.largest_patch<=(enriched?5:4),
                "Coarse Vanka did not retain complete bounded mixed aggregate bases");
        }
    }
}
void verify(MPI_Comm comm,const std::string& kind,bool single,bool empty_owner,bool enriched,
            PetscInt pre_smooth=1,PetscInt post_smooth=1) {
    const std::string prefix="mgverify_",base="-"+prefix+"monolithic_mg_";
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"aggregate_nodes").c_str(),"4"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_limit").c_str(),"8"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"max_levels").c_str(),"6"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"pre_smooth").c_str(),std::to_string(pre_smooth).c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"post_smooth").c_str(),std::to_string(post_smooth).c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"energy_steps").c_str(),enriched?"1":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),enriched?"1":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_tolerance").c_str(),"1"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_processes").c_str(),"1"));
    const bool rebuild=kind=="vanka"&&!single&&enriched;
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_refresh_period").c_str(),rebuild?"3":"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"single_precision").c_str(),single?"true":"false"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"smoother").c_str(),kind.c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"polynomial_degree").c_str(),"5"));
    // A fine three-node patch has at most 12 rows. Intermediate Galerkin
    // overlap can exceed this budget, while complete aggregate bases fit it.
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"patch_maximum_size").c_str(),"12"));
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,(base+"coarse_patch_overlap").c_str()));
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
        const auto previous=stats;
        action(problem,solver.get(),phase);
        query_monolithic_fsi_mg_stats(pc,stats);
        const auto level_cycles=(stats.applications-previous.applications)*(stats.levels-1);
        check(comm,stats.zero_start_skips-previous.zero_start_skips==level_cycles&&
            stats.level_matvecs-previous.level_matvecs==(pre_smooth+post_smooth)*level_cycles,
            "Zero-start V-cycle did not omit exactly one residual matvec per noncoarse level");
        check(comm,stats.refreshes==phase+1&&stats.applications>0&&stats.smoothers.size()+1==static_cast<std::size_t>(stats.levels),
            "Monolithic hierarchy did not refresh every Galerkin level");
        for(const auto& smoother:stats.smoothers) {
            check(comm,smoother.applications>0&&smoother.refreshes==phase+1,
                "A noncoarse level skipped smoothing or reused stale numeric factors");
            if(kind!="vanka") check(comm,smoother.polynomial_degree==5&&smoother.eigenvalue_upper>0,
                "Normal-equation Chebyshev did not configure its verified positive spectral interval");
        }
        if(kind=="vanka") vanka_coverage(comm,stats,enriched);
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
    const auto before_recovery=stats;
    problem.fill(0); updates.refresh(problem.matrix.get());
    query_monolithic_fsi_mg_stats(pc,stats);
    check(comm,stats.level_matvecs==before_recovery.level_matvecs&&
        stats.zero_start_skips==before_recovery.zero_start_skips,
        "Spectral rebuild reset the cumulative V-cycle action counters");
    action(problem,solver.get(),2);
    query_monolithic_fsi_mg_stats(pc,stats);
    check(comm,stats.hierarchy_rebuilds==(rebuild?2:1),"Scheduled spectral/energy hierarchy adaptation was not applied");
    if(kind=="vanka") vanka_coverage(comm,stats,enriched);
}
void oversized_coarse_overlap(MPI_Comm comm) {
    const std::string prefix="mgverify_",base="-"+prefix+"monolithic_mg_";
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"smoother").c_str(),"vanka"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"energy_steps").c_str(),"1"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),"1"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_patch_overlap").c_str(),"1"));
    Problem problem(comm,false);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    bool rejected=false;
    try {
        configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,
            problem.coordinates,problem.trace,&updates);
    } catch(const std::runtime_error& error) {
        rejected=std::string(error.what()).find("exceeds the maximum size")!=std::string::npos;
    }
    check(comm,rejected,"Explicit oversized coarse overlap was silently capped, truncated or ignored");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr,(base+"coarse_patch_overlap").c_str()));
}
void verify_enhancements(MPI_Comm comm,bool native,bool only_scaling,bool krylov=false) {
    const std::string prefix=krylov?"mgknew_":"mgnew_",base="-"+prefix+"monolithic_mg_";
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"aggregate_nodes").c_str(),"4"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"coarse_limit").c_str(),"8"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"max_levels").c_str(),only_scaling?"1":"6"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),"0"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"energy_steps").c_str(),only_scaling?"0":"1"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"field_scaling").c_str(),"true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"fsi_candidates").c_str(),only_scaling?"false":"true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"adaptive_patches").c_str(),only_scaling?"false":"true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"patch_strength").c_str(),"0.9"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"native_fp32").c_str(),native?"true":"false"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"cycle").c_str(),only_scaling?"v":krylov?"k":"w"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"patch_maximum_size").c_str(),"64"));
    Problem problem(comm,true);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),80));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,500));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    const auto rescale=[&]() {
        PetscOwner<Vec,VecDestroy> left,right;
        EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),right.put(),left.put()));
        PetscScalar *l=nullptr,*r=nullptr;
        EONSIM_PETSC(VecGetArray(left.get(),&l));EONSIM_PETSC(VecGetArray(right.get(),&r));
        const double ls[4]={1e3,1e-3,1e2,1.},rs[4]={1e-1,1e2,1e-2,1.};
        for(PetscInt row=problem.begin;row<problem.end;++row) {
            l[row-problem.begin]=row==0?1.:ls[row%4];
            r[row-problem.begin]=row==0?1.:rs[row%4];
        }
        EONSIM_PETSC(VecRestoreArray(right.get(),&r));EONSIM_PETSC(VecRestoreArray(left.get(),&l));
        EONSIM_PETSC(MatDiagonalScale(problem.matrix.get(),left.get(),right.get()));
    };
    if(only_scaling) rescale();
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,
        problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    for(int phase=0;phase<2;++phase) {
        if(phase) {problem.fill(phase);if(only_scaling) rescale();updates.refresh(problem.matrix.get());}
        MonolithicFsiMgStats previous;query_monolithic_fsi_mg_stats(pc,previous);
        action(problem,solver.get(),phase);
        MonolithicFsiMgStats stats;query_monolithic_fsi_mg_stats(pc,stats);
        check(comm,stats.field_scaling&&stats.native_fp32==native&&stats.hierarchy_rebuilds==phase+1,
              "Scaled/native hierarchy did not preserve mapping or rebuild on actual numerical change");
        if(only_scaling) continue;
        check(comm,stats.fsi_candidates&&stats.w_cycle==!krylov&&stats.k_cycle==krylov&&
              stats.levels>=3&&stats.coarse_revisits>0,
              "FSI coarse enrichment or the requested recursive cycle was not exercised");
        if(krylov) {
            const auto applications=stats.applications-previous.applications;
            const auto coarse_bound=applications*(PetscInt{1}<<(stats.levels-2));
            check(comm,stats.coarse_solves-previous.coarse_solves<=coarse_bound&&
                stats.coarse_solves>previous.coarse_solves&&stats.coarse_krylov_directions>previous.coarse_krylov_directions&&
                stats.coarse_krylov_reductions>previous.coarse_krylov_reductions&&
                stats.smoother_applications>previous.smoother_applications&&
                std::isfinite(stats.coarse_krylov_max_residual_ratio)&&stats.coarse_krylov_max_residual_ratio<=1.,
                "K-cycle exceeded its bounded coarse work, skipped QR, or returned an increasing coarse residual");
        }
        for(const auto& transfer:stats.transfers)
            check(comm,transfer.coarse_rows<=.8*transfer.rows&&transfer.reproduction_error<1e-9,
                  "Enriched hierarchy accepted weak coarsening or lost paired pressure/divergence modes");
        PetscInt expanded=0,core=0;
        for(const auto& smoother:stats.smoothers) {
            expanded+=smoother.patches.expanded_patches;core+=smoother.patches.core_patches;
            if(native) check(comm,smoother.patches.retained_fp64_matrix_bytes==0&&smoother.patches.fp64_patches==0,
                             "Native Vanka retained double matrix coefficients or fallback factors");
        }
        const PetscInt local[3]={expanded,core,stats.smoothers.front().patches.covered_owned_rows};
        PetscInt total[3]{};MPI_Allreduce(local,total,3,MPIU_INT,MPI_SUM,comm);
        check(comm,total[0]>0&&total[1]>0&&total[2]==Problem::n-1,
              "Adaptive Vanka failed to distinguish core/strong patches or lost active coverage");
        if(native) {
            unsigned long long local_bytes=stats.released_fp64_operator_bytes,total_bytes=0;
            MPI_Allreduce(&local_bytes,&total_bytes,1,MPI_UNSIGNED_LONG_LONG,MPI_SUM,comm);
            check(comm,total_bytes>0,"Native MG retained all noncoarse FP64 setup operators/transfers");
        }
    }
    MonolithicFsiMgStats before,after;
    query_monolithic_fsi_mg_stats(pc,before);updates.refresh(problem.matrix.get());query_monolithic_fsi_mg_stats(pc,after);
    check(comm,after.hierarchy_rebuilds==before.hierarchy_rebuilds,
          "An unchanged numerical generation rebuilt scaled/native hierarchy");
    action(problem,solver.get(),3);
    if(krylov) {
        PetscOwner<Vec,VecDestroy> zero,result;
        EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),zero.put(),result.put()));
        EONSIM_PETSC(VecSet(zero.get(),0.));EONSIM_PETSC(PCApply(pc,zero.get(),result.get()));
        PetscReal norm=0.;EONSIM_PETSC(VecNorm(result.get(),NORM_2,&norm));
        check(comm,norm==0.,"K-cycle divided by a zero Arnoldi direction or changed a zero correction");
        if(native) {
            // Preserve graph/constraints but force a mixed patch singularity
            // after the previous compact generation has been released. Failed
            // replacement must remain unusable and retain enough metadata to
            // reconstruct successfully on the next numeric refresh.
            if(problem.begin<=4&&4<problem.end) {
                const PetscInt row=4;PetscInt count=0;const PetscInt* indices=nullptr;
                EONSIM_PETSC(MatGetRow(problem.matrix.get(),row,&count,&indices,nullptr));
                std::vector<PetscInt> columns(indices,indices+count);
                EONSIM_PETSC(MatRestoreRow(problem.matrix.get(),row,&count,&indices,nullptr));
                for(const auto column:columns)
                    EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,column,0.,INSERT_VALUES));
            }
            EONSIM_PETSC(MatAssemblyBegin(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
            EONSIM_PETSC(MatAssemblyEnd(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
            bool rejected=false;
            try {updates.refresh(problem.matrix.get());} catch(const std::exception&) {rejected=true;}
            check(comm,rejected,"Singular native replacement unexpectedly retained a usable old generation");
            MonolithicFsiMgStats failed;query_monolithic_fsi_mg_stats(pc,failed);
            check(comm,failed.levels==0,"Native replacement failed before releasing the old compact generation");
            EONSIM_PETSC(PCApply(pc,zero.get(),result.get()));
            PCFailedReason failure=PC_NOERROR;EONSIM_PETSC(PCGetFailedReason(pc,&failure));
            check(comm,failure!=PC_NOERROR,"Failed native replacement did not poison the preconditioner");
            problem.fill(4);updates.refresh(problem.matrix.get());
            action(problem,solver.get(),4);
        }
    }
}

void verify_scaled_projection(MPI_Comm comm) {
    // The tentative spaces have the same physical span under a change of
    // field units. With one exact coarse solve and no energy/spectral change,
    // the complete two-level PC must therefore be invariant. Interface modes
    // mix fields with distinct row scales, so plain P^T restriction would
    // violate this property even though each individual solve is nonsingular.
    Problem problem(comm,true);
    PetscOwner<Vec,VecDestroy> rhs,plain,scaled;
    EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),plain.put(),rhs.put()));
    EONSIM_PETSC(VecDuplicate(plain.get(),scaled.put()));
    PetscScalar* entries=nullptr;EONSIM_PETSC(VecGetArray(rhs.get(),&entries));
    for(PetscInt row=problem.begin;row<problem.end;++row)
        entries[row-problem.begin]=std::sin(.19*(row+1))+.3*std::cos(.07*(row+1));
    EONSIM_PETSC(VecRestoreArray(rhs.get(),&entries));
    for(bool equilibrated:{false,true}) {
        const std::string prefix=equilibrated?"mgproject_scaled_":"mgproject_plain_";
        const auto base="-"+prefix+"monolithic_mg_";
        for(const auto& setting:std::vector<std::pair<std::string,std::string>>{
            {"aggregate_nodes","4"},{"coarse_limit","1"},{"max_levels","2"},
            {"energy_steps","0"},{"spectral_modes","0"},{"fsi_candidates","true"},
            {"max_coarse_ratio","1"},{"field_scaling",equilibrated?"true":"false"}})
            EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+setting.first).c_str(),setting.second.c_str()));
        PcSchurUpdates updates;
        PetscOwner<KSP,KSPDestroy> solver;
        EONSIM_PETSC(KSPCreate(comm,solver.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
        EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
        configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,
            problem.coordinates,problem.trace,&updates);
        PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
        MonolithicFsiMgStats stats;query_monolithic_fsi_mg_stats(pc,stats);
        check(comm,stats.levels==2,"Scaled projection invariant did not exercise a mixed coarse space");
        EONSIM_PETSC(PCApply(pc,rhs.get(),equilibrated?scaled.get():plain.get()));
    }
    PetscReal norm=0,difference=0;
    EONSIM_PETSC(VecNorm(plain.get(),NORM_2,&norm));
    EONSIM_PETSC(VecAXPY(scaled.get(),-1.,plain.get()));
    EONSIM_PETSC(VecNorm(scaled.get(),NORM_2,&difference));
    check(comm,norm>0&&difference<=1e-10*norm,
          "Two-sided equilibration changed the original physical mixed coarse projection");
}

void verify_weak_coarsening_stop(MPI_Comm comm) {
    Problem problem(comm,true);
    const std::string prefix="mgstop_",base="-"+prefix+"monolithic_mg_";
    for(const auto& setting:std::vector<std::pair<std::string,std::string>>{
        {"aggregate_nodes","2"},{"coarse_limit","1"},{"max_coarse_ratio","0.25"},
        {"energy_steps","0"},{"spectral_modes","0"}})
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+setting.first).c_str(),setting.second.c_str()));
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,100));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,
        problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    MonolithicFsiMgStats stats;query_monolithic_fsi_mg_stats(pc,stats);
    check(comm,stats.levels==1&&stats.transfers.empty()&&stats.weak_coarsening_stop_rows==Problem::n&&
        stats.weak_coarsening_proposed_rows>.25*Problem::n,
        "Weak coarsening did not collectively retain the parent as the exact coarse problem");
    action(problem,solver.get(),0);
}

void fill_pressure_pair_problem(Problem& problem,int phase) {
    // A discrete mixed block whose two pressure modes have B^T images
    // orthogonal to every existing constant/linear/quadratic velocity mode.
    // Third differences annihilate those polynomials independently of the
    // production candidate/QR implementation. Both responses vanish on the
    // constrained first velocity row. Each eight-node block is one aggregate.
    constexpr PetscInt width=8;
    const double first[width]={0.,1.,-3.,3.,-1.,0.,0.,0.};
    const double second[width]={0.,0.,0.,0.,1.,-3.,3.,-1.};
    double responses[2][width]{};
    for(PetscInt i=0;i<width;++i) {
        responses[0][i]=first[i]/std::sqrt(20.);
        responses[1][i]=(second[i]+first[i]/20.)/std::sqrt(399./20.);
    }
    for(int k=0;k<2;++k) for(int degree=0;degree<=2;++degree) {
        long double moment=0.;
        for(PetscInt i=0;i<width;++i) moment+=responses[k][i]*std::pow(static_cast<double>(i),degree);
        check(problem.comm,std::abs(moment)<1e-13,
              "Manufactured pressure response was not independent of the original polynomial velocity span");
    }
    EONSIM_PETSC(MatSetOption(problem.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
    EONSIM_PETSC(MatZeroEntries(problem.matrix.get()));
    for(PetscInt row=problem.begin;row<problem.end;++row) {
        const auto node=row/Problem::fields,field=row%Problem::fields,first_node=width*(node/width),i=node%width;
        if(row==0) {EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,row,1.,INSERT_VALUES));continue;}
        const double diagonal=field==0?2.+.1*phase:field==1?-.1:field==2?3.:4.;
        EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,row,diagonal,INSERT_VALUES));
        if(field==0||field==1) for(PetscInt j=0;j<width;++j) {
            const auto pressure_node=field==1?i:j,velocity_node=field==1?j:i;
            const auto strength=phase&&first_node==16?0.:1.+.2*phase;
            const auto coupling=strength*(responses[0][velocity_node]/std::sqrt(8.)+
                (pressure_node-3.5)*responses[1][velocity_node]/std::sqrt(42.));
            EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,
                Problem::fields*(first_node+j)+(field==1?0:1),coupling,INSERT_VALUES));
        }
        if(field==1) {
            // These extra channels detect accidental nonvelocity entries in
            // an enriched column: the oracle must match the actual full PtAP.
            EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,Problem::fields*node+2,3.7,INSERT_VALUES));
            EONSIM_PETSC(MatSetValue(problem.matrix.get(),row,Problem::fields*node+3,-2.3,INSERT_VALUES));
        }
    }
    // These two entries cross owners on four ranks and make the energy
    // gradient touch remote fixed columns. They do not enter either local
    // aggregate's B/self-pair oracle; deterministic eight-node growth remains
    // unchanged because the first seed already fills its complete block.
    const PetscInt pressure_row=7*Problem::fields+1,velocity_row=9*Problem::fields;
    if(problem.begin<=pressure_row&&pressure_row<problem.end)
        EONSIM_PETSC(MatSetValue(problem.matrix.get(),pressure_row,velocity_row,.17,INSERT_VALUES));
    if(problem.begin<=velocity_row&&velocity_row<problem.end)
        EONSIM_PETSC(MatSetValue(problem.matrix.get(),velocity_row,pressure_row,-.13,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatSetOption(problem.matrix.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_TRUE));
}

void verify_pressure_supremizers(MPI_Comm comm,bool scaled,bool native) {
    const std::string prefix="mgpair_",base="-"+prefix+"monolithic_mg_";
    for(const auto& setting:std::vector<std::pair<std::string,std::string>>{
        {"aggregate_nodes","8"},{"aggregate_rows","64"},{"coarse_limit","1"},{"max_levels","2"},
        {"energy_steps","1"},{"spectral_modes","2"},{"max_coarse_ratio","1"},
        {"fsi_candidates","true"},{"pressure_supremizers","true"},{"patch_maximum_size","64"},
        {"field_scaling",scaled?"true":"false"},{"native_fp32",native?"true":"false"}})
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+setting.first).c_str(),setting.second.c_str()));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"fsi_candidates").c_str(),"false"));
    bool rejected=false;
    try {validate_monolithic_fsi_mg_options(comm,prefix);} catch(const std::runtime_error&) {rejected=true;}
    check(comm,rejected,"Pressure supremizers were accepted without their physical candidate space");
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"fsi_candidates").c_str(),"true"));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),"0"));
    rejected=false;
    try {validate_monolithic_fsi_mg_options(comm,prefix);} catch(const std::runtime_error&) {rejected=true;}
    check(comm,rejected,"Pressure supremizers silently increased an empty spectral budget");
    EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+"spectral_modes").c_str(),"2"));
    Problem problem(comm,true);
    std::fill(problem.trace.begin(),problem.trace.end(),0);
    fill_pressure_pair_problem(problem,0);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),80));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,300));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,
        problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    for(int phase=0;phase<2;++phase) {
        if(phase) {fill_pressure_pair_problem(problem,phase);updates.refresh(problem.matrix.get());}
        MonolithicFsiMgStats stats;query_monolithic_fsi_mg_stats(pc,stats);
        check(comm,stats.pressure_supremizers&&stats.levels==2&&stats.transfers.size()==1&&
            stats.hierarchy_rebuilds==phase+1,"Discrete pressure enrichment did not rebuild on numeric change");
        const auto& transfer=stats.transfers.front();
        // On four ranks the last owner loses all eligible pressure coupling
        // at refresh, while another rank remains entirely empty. Both still
        // participate in fixed-column halo exchange and the global pair audit.
        const PetscInt pairs=phase?2:3;
        check(comm,transfer.pressure_paired_aggregates==pairs&&transfer.pressure_supremizer_modes==2*pairs&&
            transfer.spectral_modes<=2*(3-pairs)&&transfer.pressure_pair_min_singular>.99&&
            transfer.pressure_pair_relative_change<1e-10&&transfer.reproduction_error<1e-10,
            "Selected discrete pressure pairs did not restore the two missing channels within the original spectral budget");
        check(comm,transfer.energy_after<=transfer.energy_before*(1.+1e-11),
            "Protecting mixed pressure pairs broke constrained transfer-energy descent");
        action(problem,solver.get(),phase);
    }
}

struct FineShell {
    Mat actual=nullptr;
    PetscInt calls=0;
};
PetscErrorCode fine_shell_mult(Mat shell,Vec x,Vec y) {
    PetscFunctionBeginUser;
    FineShell* context=nullptr;PetscCall(MatShellGetContext(shell,&context));
    ++context->calls;PetscCall(MatMult(context->actual,x,y));
    PetscFunctionReturn(PETSC_SUCCESS);
}
void verify_saddle_extensions(MPI_Comm comm,bool combined) {
    const std::string prefix=combined?"mgcompatible_":"mgsaddle_",base="-"+prefix+"monolithic_mg_";
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"aggregate_nodes","4"},{"aggregate_rows","128"},{"max_levels","6"},{"coarse_limit","8"},
        {"max_coarse_ratio","1"},{"patch_maximum_size","128"},{"spectral_modes","4"},
        {"spectral_tolerance","1"},{"fsi_candidates","true"},{"pressure_supremizers","true"},
        {"saddle_point","true"},{"smoother",combined?"vanka_colored":"braess_sarazin"},
        {"coarse_processes","0"},{"schur_iterations","3"},{"energy_steps","1"},
        {"divergence_preserving",combined?"true":"false"},{"divergence_commuting",combined?"true":"false"},
        {"distributed_aggregation",combined?"true":"false"},{"field_scaling",combined?"true":"false"},
        {"reuse_hierarchy",combined?"true":"false"},{"matrix_free_fine",combined?"true":"false"},
        {"communication_avoiding",combined?"true":"false"},{"cycle",combined?"k":"v"},
        {"hierarchy_drift","0.5"},{"hierarchy_max_age","2"}})
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+option.first).c_str(),option.second.c_str()));
    int ranks=0;MPI_Comm_size(comm,&ranks);
    Problem problem(comm,!combined);
    PcSchurUpdates updates;
    FineShell context{problem.matrix.get(),0};
    PetscOwner<Mat,MatDestroy> shell;
    if(combined) {
        EONSIM_PETSC(MatCreateShell(comm,problem.end-problem.begin,problem.end-problem.begin,
            Problem::n,Problem::n,&context,shell.put()));
        EONSIM_PETSC(MatShellSetOperation(shell.get(),MATOP_MULT,reinterpret_cast<void(*)(void)>(fine_shell_mult)));
    }
    PetscOwner<KSP,KSPDestroy> solver;EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));EONSIM_PETSC(KSPGMRESSetRestart(solver.get(),96));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,400));
    EONSIM_PETSC(KSPSetOperators(solver.get(),combined?shell.get():problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    if(combined) check(comm,set_monolithic_fsi_mg_fine_operator(pc,shell.get()),"Requested exact fine operator was not bound");
    MonolithicFsiMgStats initial;query_monolithic_fsi_mg_stats(pc,initial);
    check(comm,initial.saddle_point&&initial.levels>=2&&initial.coarse_processes==ranks,
          "Typed saddle hierarchy or distributed coarse solve was not created");
    PetscInt cross_rank=0,closure=0,pressure_modes=0,coarse_pair_modes=0;
    for(std::size_t l=0;l<initial.transfers.size();++l) {
        const auto& transfer=initial.transfers[l];
        check(comm,transfer.pressure_rows>0&&transfer.coarse_pressure_rows>0&&transfer.reproduction_error<1e-9,
              "Pressure type or physical span was lost on a coarse level");
        pressure_modes+=transfer.pressure_supremizer_modes;
        if(l>0) coarse_pair_modes+=transfer.pressure_supremizer_modes;
        cross_rank+=transfer.distributed_aggregates;closure+=transfer.compatible_pressure_modes;
        if(combined) check(comm,transfer.divergence_change<=1e-10&&transfer.divergence_commuting_defect<=1e-10&&
            std::isfinite(transfer.divergence_update_norm),"Compatible interpolation failed independent divergence/commuting audit");
    }
    check(comm,pressure_modes>0,"Saddle hierarchy failed to construct pressure supremizer responses");
    if(!combined) check(comm,initial.levels>=3&&coarse_pair_modes>0,
        "Multilevel supremizer fixture did not exercise an actual intermediate-level pressure response");
    if(combined&&ranks>1) check(comm,cross_rank>0,"Distributed option migrated rows without building a cut-spanning aggregate");
    if(combined) check(comm,closure>0,"Commuting transfer did not add any missing pressure-image modes");
    action(problem,solver.get(),0);
    MonolithicFsiMgStats solved;query_monolithic_fsi_mg_stats(pc,solved);
    if(combined) check(comm,solved.matrix_free_fine_actions>0&&context.calls>solved.matrix_free_fine_actions&&
        (solved.levels<3||solved.batched_reduction_groups>0),
        "Exact fine action or combined K-cycle reduction path did not actually execute");
    else {
        for(const auto& smooth:solved.smoothers) {
            const PetscInt local[]={smooth.pressure_rows,smooth.primal_rows};PetscInt global[2]{};
            MPI_Allreduce(local,global,2,MPIU_INT,MPI_SUM,comm);
            check(comm,global[0]>0&&global[1]>0&&smooth.schur_applications>0,
                  "Coupled pressure/structure Schur action was omitted on a multigrid level");
        }
    }
    problem.fill(1);updates.refresh(problem.matrix.get());
    action(problem,solver.get(),1);
    MonolithicFsiMgStats refreshed;query_monolithic_fsi_mg_stats(pc,refreshed);
    if(combined) check(comm,refreshed.hierarchy_rebuilds==initial.hierarchy_rebuilds&&
        refreshed.hierarchy_reuses==1&&refreshed.unchanged_divergence_reuses==1&&
        refreshed.symbolic_reuses>=refreshed.levels-1,
        "Compatible mild numeric update rebuilt the coarse space or skipped fresh symbolic-product reuse");
    if(combined) {
        // A change to B, rather than F/C, invalidates the reduced pressure-image
        // closure even at small row drift. It must rebuild, never keep a stale
        // compatibility certificate or merely relax its numerical audit.
        if(problem.begin<=5&&5<problem.end) EONSIM_PETSC(MatSetValue(problem.matrix.get(),5,4,-1.02,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(problem.matrix.get(),MAT_FINAL_ASSEMBLY));
        updates.refresh(problem.matrix.get());
        MonolithicFsiMgStats changed_B;query_monolithic_fsi_mg_stats(pc,changed_B);
        check(comm,changed_B.hierarchy_rebuilds==refreshed.hierarchy_rebuilds+1&&
            changed_B.divergence_rebuilds==1&&changed_B.hierarchy_reuses==refreshed.hierarchy_reuses,
            "Changed B reused a reduced compatible pressure space without rebuilding its closure");
        for(const auto& level:changed_B.transfers)
            check(comm,level.divergence_commuting_defect<=1e-10,"Rebuilt pressure closure lost the commuting relation");
        action(problem,solver.get(),2);
    }
    EONSIM_PETSC(PetscPrintf(comm,
        "saddle_extension combined=%d levels=%" PetscInt_FMT " supremizer_modes=%" PetscInt_FMT
        " intermediate_supremizer_modes=%" PetscInt_FMT " cut_aggregates=%" PetscInt_FMT
        " closure_modes=%" PetscInt_FMT " fine_actions=%" PetscInt_FMT " hierarchy_reuses=%" PetscInt_FMT "\n",
        combined?1:0,initial.levels,pressure_modes,coarse_pair_modes,cross_rank,closure,
        refreshed.matrix_free_fine_actions,refreshed.hierarchy_reuses));
}
void verify_adaptive_hierarchy(MPI_Comm comm) {
    const std::string prefix="mgadapt_",base="-"+prefix+"monolithic_mg_";
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"aggregate_nodes","4"},{"coarse_limit","8"},{"spectral_modes","1"},{"energy_steps","0"},
        {"adaptive_hierarchy","true"},{"reuse_hierarchy","true"},{"adaptive_interval","1"},
        {"adaptive_threshold","1e-30"},{"communication_avoiding","true"},{"maximum_complexity","8"}})
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+option.first).c_str(),option.second.c_str()));
    Problem problem(comm,true);PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    PetscOwner<Vec,VecDestroy> rhs,correction;
    EONSIM_PETSC(MatCreateVecs(problem.matrix.get(),correction.put(),rhs.put()));EONSIM_PETSC(VecSet(rhs.get(),1.));
    EONSIM_PETSC(PCApply(pc,rhs.get(),correction.get()));
    MonolithicFsiMgStats probed;query_monolithic_fsi_mg_stats(pc,probed);
    check(comm,probed.adaptive_probes==1&&probed.adaptive_residual_ratio>1e-30&&probed.batched_reduction_groups==1,
          "Adaptive hierarchy did not measure the original level residual");
    updates.refresh(problem.matrix.get());
    MonolithicFsiMgStats rebuilt;query_monolithic_fsi_mg_stats(pc,rebuilt);
    check(comm,rebuilt.hierarchy_rebuilds==probed.hierarchy_rebuilds+1&&rebuilt.adaptive_rebuilds==1&&
        rebuilt.operator_complexity<=8.,"Poor measured contraction did not trigger a bounded hierarchy adaptation");
}

void verify_compressed_pressure_image(MPI_Comm comm) {
    const std::string prefix="mgimage_",base="-"+prefix+"monolithic_mg_";
    for(const auto& option:std::vector<std::pair<std::string,std::string>>{
        {"aggregate_nodes","6"},{"saddle_point","true"},{"pressure_image_modes","1"},
        {"energy_steps","0"},{"max_levels","2"},{"coarse_limit","8"},
        {"coarse_processes","0"},{"smoother","braess_sarazin"}})
        EONSIM_PETSC(PetscOptionsSetValue(nullptr,(base+option.first).c_str(),option.second.c_str()));
    Problem problem(comm,false);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> solver;
    EONSIM_PETSC(KSPCreate(comm,solver.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(solver.get(),prefix.c_str()));
    EONSIM_PETSC(KSPSetType(solver.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetTolerances(solver.get(),1e-12,1e-14,PETSC_DEFAULT,120));
    EONSIM_PETSC(KSPSetOperators(solver.get(),problem.matrix.get(),problem.matrix.get()));
    configure_monolithic_fsi_mg(comm,solver.get(),problem.matrix.get(),problem.semantics,problem.coordinates,problem.trace,&updates);
    PC pc=nullptr;
    EONSIM_PETSC(KSPGetPC(solver.get(),&pc));
    MonolithicFsiMgStats stats;
    check(comm,query_monolithic_fsi_mg_stats(pc,stats)&&stats.transfers.size()==1,
          "Compressed pressure image did not build a two-level hierarchy");
    const auto& level=stats.transfers.front();
    check(comm,level.compatible_pressure_modes>0&&level.coarse_pressure_rows<level.pressure_rows&&
          level.reproduction_error<1e-10&&std::isfinite(level.divergence_commuting_defect)&&
          level.divergence_commuting_defect>0.&&level.divergence_commuting_defect<1.,
          "Compressed pressure image lost its candidate span, enrichment or compression");
    action(problem,solver.get(),3);
    EONSIM_PETSC(PetscPrintf(comm,"compressed_pressure_rows=%" PetscInt_FMT " fine_pressure_rows=%" PetscInt_FMT
                            " projected_divergence_defect=%.9g\n",
                            level.coarse_pressure_rows,level.pressure_rows,level.divergence_commuting_defect));
}

void run(MPI_Comm comm) {
    int size=0; MPI_Comm_size(comm,&size); check(comm,size==1||size==2||size==4,"Expected 1, 2 or 4 ranks");
    PetscBool only=PETSC_FALSE,image_only=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-mgverify_saddle_only",&only,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-mgverify_pressure_image_only",&image_only,nullptr));
    verify_compressed_pressure_image(comm);
    if(image_only) return;
    verify_saddle_extensions(comm,false);
    verify_saddle_extensions(comm,true);
    verify_adaptive_hierarchy(comm);
    if(only) return;
    verify(comm,"vanka",false,false,true);
    verify(comm,"vanka",true,true,true);
    verify(comm,"chebyshev",false,false,true);
    verify(comm,"block_chebyshev",false,true,false);
    // Exercise both the no-presmoothing restriction path and multiple initial
    // sweeps with no postsmoothing, with the same independent solution oracle.
    verify(comm,"vanka",false,false,false,0,1);
    verify(comm,"vanka",true,true,false,2,0);
    oversized_coarse_overlap(comm);
    verify_enhancements(comm,false,true);
    verify_enhancements(comm,false,false);
    verify_enhancements(comm,true,false);
    verify_enhancements(comm,false,false,true);
    verify_enhancements(comm,true,false,true);
    verify_scaled_projection(comm);
    verify_weak_coarsening_stop(comm);
    verify_pressure_supremizers(comm,false,false);
    verify_pressure_supremizers(comm,true,false);
    verify_pressure_supremizers(comm,true,true);
    EONSIM_PETSC(PetscPrintf(comm,
        "Monolithic FSI MG: full indefinite manufactured solutions, bounded whole-aggregate coarse Vanka/explicit oversize rejection, candidate preservation, energy descent, spectral/discrete-pressure enrichment with weighted-pair preservation, FP32 V/K-cycles with bounded coarse work, coarse MPI aggregation, native replacement failure recovery and polynomial smoothers passed\n"));
}
} // namespace
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int result=0;
    try {run(PETSC_COMM_WORLD);}
    catch(const std::exception& error) {std::cerr<<"Monolithic FSI MG verification failed: "<<error.what()<<'\n';result=1;}
    PetscFinalize(); return result;
}
