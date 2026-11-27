#include "eonsim/deflated_fgmres.hpp"
#include <petscblaslapack.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <memory>

namespace eonsim {
namespace {
constexpr const char* shell_name="EONSim spectral right-deflated FGMRES";
using Vector=PetscOwner<Vec,VecDestroy>;
struct Pair { Vector direction,image; };
Vector copy(Vec x) {
    Vector result; EONSIM_PETSC(VecDuplicate(x,result.put()));
    EONSIM_PETSC(VecCopy(x,result.get())); return result;
}
double norm(Vec x) {
    PetscReal value=0; EONSIM_PETSC(VecNorm(x,NORM_2,&value));
    if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deflated FGMRES vector");
    return value;
}
struct State {
    PetscOwner<KSP,KSPDestroy> bulk;
    Mat current=nullptr; // Borrowed from outer and bulk KSP; valid during a solve.
    Vector projected_rhs,action;
    std::vector<Vector> retained;
    std::vector<Pair> active,samples;
    DeflatedFgmresStats stats;
    bool collecting=false,prepared=false;

    std::vector<PetscScalar> dots(Vec x,const std::vector<Pair>& space,bool image) {
        std::vector<Vec> handles; handles.reserve(space.size());
        for(const auto& item:space) handles.push_back(image?item.image.get():item.direction.get());
        std::vector<PetscScalar> values(handles.size());
        if(!handles.empty()) {
            EONSIM_PETSC(VecMDot(x,static_cast<PetscInt>(handles.size()),handles.data(),values.data()));
            ++stats.projection_reductions;
        }
        return values;
    }
    void paired_axpy(Pair& value,const std::vector<Pair>& space,const std::vector<PetscScalar>& coefficients) {
        for(std::size_t i=0;i<space.size();++i) {
            EONSIM_PETSC(VecAXPY(value.direction.get(),-coefficients[i],space[i].direction.get()));
            EONSIM_PETSC(VecAXPY(value.image.get(),-coefficients[i],space[i].image.get()));
        }
    }
    bool append(Pair value,std::vector<Pair>& space,bool image_metric) {
        const double original=norm(image_metric?value.image.get():value.direction.get());
        if(original==0) { ++stats.rank_drops; return false; }
        for(int pass=0;pass<2;++pass) {
            const auto coefficients=dots(image_metric?value.image.get():value.direction.get(),space,image_metric);
            paired_axpy(value,space,coefficients);
        }
        const double length=norm(image_metric?value.image.get():value.direction.get());
        if(length<=256*std::numeric_limits<double>::epsilon()*original) { ++stats.rank_drops; return false; }
        EONSIM_PETSC(VecScale(value.direction.get(),1./length));
        EONSIM_PETSC(VecScale(value.image.get(),1./length));
        space.push_back(std::move(value)); return true;
    }
    void multiply(Vec input,Vec output) {
        EONSIM_PETSC(MatMult(current,input,output)); ++stats.operator_actions;
    }
    void refresh(KSP outer,Vec rhs,Vec x) {
        PC wrapper=nullptr,base=nullptr;
        Mat p=nullptr;
        EONSIM_PETSC(KSPGetPC(outer,&wrapper)); EONSIM_PETSC(KSPGetPC(bulk.get(),&base));
        EONSIM_PETSC(KSPGetOperators(outer,&current,&p));
        // Preserve deliberate numerical PC reuse; refreshing C uses exact A
        // even if the underlying preconditioner generation remains old.
        PetscBool reuse=PETSC_FALSE; EONSIM_PETSC(PCGetReusePreconditioner(wrapper,&reuse));
        EONSIM_PETSC(KSPSetOperators(bulk.get(),current,p));
        EONSIM_PETSC(KSPSetReusePreconditioner(bulk.get(),reuse));
        EONSIM_PETSC(PCSetFailedReason(wrapper,PC_NOERROR));
        if(!action.get()) {
            EONSIM_PETSC(VecDuplicate(rhs,action.put()));
            EONSIM_PETSC(VecDuplicate(rhs,projected_rhs.put()));
        }
        collecting=false; prepared=false; active.clear(); samples.clear();
        for(const auto& stored:retained) {
            Pair value; value.direction=copy(stored.get()); value.image=copy(stored.get());
            multiply(value.direction.get(),value.image.get());
            append(std::move(value),active,true);
        }
        EONSIM_PETSC(VecSet(x,0.)); EONSIM_PETSC(KSPSetInitialGuessNonzero(outer,PETSC_FALSE));
        const auto coefficients=dots(rhs,active,true);
        for(std::size_t i=0;i<active.size();++i)
            EONSIM_PETSC(VecAXPY(x,coefficients[i],active[i].direction.get()));
        if(!active.empty()) {
            const double rhs_norm=norm(rhs);
            multiply(x,action.get()); EONSIM_PETSC(VecAXPY(action.get(),-1.,rhs));
            const double error=norm(action.get());
            // Very ill-scaled AU normalization can lose the minimum-residual
            // property. Drop that space collectively instead of poisoning A.
            if(error>rhs_norm*(1+256*std::numeric_limits<double>::epsilon())) {
                stats.rank_drops+=static_cast<PetscInt>(active.size()); active.clear();
                EONSIM_PETSC(VecSet(x,0.));
            } else {
                EONSIM_PETSC(KSPSetInitialGuessNonzero(outer,PETSC_TRUE)); ++stats.projections;
            }
        }
        ++stats.refreshes; prepared=true; collecting=true;
    }
    PetscErrorCode apply(PC wrapper,Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!prepared||!current) PetscFunctionReturn(PETSC_ERR_ARG_WRONGSTATE);
        PC base=nullptr; PetscCall(KSPGetPC(bulk.get(),&base));
        const auto coarse=dots(input,active,true);
        PetscCall(VecCopy(input,projected_rhs.get()));
        for(std::size_t i=0;i<active.size();++i)
            PetscCall(VecAXPY(projected_rhs.get(),-coarse[i],active[i].image.get()));
        const auto error=PCApply(base,projected_rhs.get(),output);
        PCFailedReason failure=PC_NOERROR;
        const auto failure_error=PCGetFailedReason(base,&failure);
        // PCGetFailedReason is rank-local until a Krylov reduction has checked
        // it. We introduce further MatMult/QR collectives inside the wrapper,
        // so propagate failure BEFORE any rank takes that collective path.
        const int bad=error||failure_error||failure!=PC_NOERROR;
        int any=0;
        PetscCallMPI(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,PetscObjectComm(reinterpret_cast<PetscObject>(wrapper))));
        ++stats.failure_reductions;
        if(any) {
            PetscCall(PCSetFailedReason(wrapper,PC_SUBPC_ERROR));
            PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        ++stats.applications;
        const bool collect=collecting&&samples.size()<static_cast<std::size_t>(2*stats.capacity);
        if(!active.empty()||collect) {
            multiply(output,action.get());
            if(collect) {
                Pair value; value.direction=copy(output); value.image=copy(action.get());
                if(append(std::move(value),samples,false)) ++stats.candidates;
            }
        }
        if(!active.empty()) {
            // Lift the projected Krylov direction in the original variables;
            // paired subtraction keeps its exact image perpendicular to C.
            for(int pass=0;pass<2;++pass) {
                const auto coefficients=dots(action.get(),active,true);
                for(std::size_t i=0;i<active.size();++i) {
                    PetscCall(VecAXPY(output,-coefficients[i],active[i].direction.get()));
                    PetscCall(VecAXPY(action.get(),-coefficients[i],active[i].image.get()));
                }
            }
            for(std::size_t i=0;i<active.size();++i)
                PetscCall(VecAXPY(output,coarse[i],active[i].direction.get()));
            ++stats.projected_applications;
        }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    void complete(Vec solution) {
        collecting=false;
        // Build an orthonormal direction basis with consistently transformed
        // operator images. Existing C and captured images are from current A.
        std::vector<Pair> pool;
        for(const auto& value:active) {
            Pair candidate; candidate.direction=copy(value.direction.get()); candidate.image=copy(value.image.get());
            append(std::move(candidate),pool,false);
        }
        for(auto& value:samples) append(std::move(value),pool,false);
        samples.clear();
        Pair last; last.direction=copy(solution); last.image=copy(solution);
        multiply(solution,last.image.get()); append(std::move(last),pool,false);
        const auto count=pool.size();
        if(!count) { retained.clear(); stats.vectors=0; return; }

        // A distributed thin image QR followed by dense SVD of R avoids the
        // condition-number squaring of forming (AQ)^T(AQ). V selects small
        // nonzero singular responses in the actual bounded search space.
        std::vector<Vector> image_basis;
        std::vector<double> triangular(count*count,0.);
        for(std::size_t column=0;column<count;++column) {
            auto work=copy(pool[column].image.get());
            const double original=norm(work.get());
            for(int pass=0;pass<2;++pass) {
                std::vector<Vec> handles; for(const auto& q:image_basis) handles.push_back(q.get());
                std::vector<PetscScalar> coefficients(handles.size());
                if(!handles.empty()) {
                    EONSIM_PETSC(VecMDot(work.get(),static_cast<PetscInt>(handles.size()),handles.data(),coefficients.data()));
                    ++stats.projection_reductions;
                }
                for(std::size_t row=0;row<handles.size();++row) {
                    triangular[row+count*column]+=coefficients[row];
                    EONSIM_PETSC(VecAXPY(work.get(),-coefficients[row],handles[row]));
                }
            }
            const double length=norm(work.get());
            if(length>256*std::numeric_limits<double>::epsilon()*original&&length>0) {
                triangular[image_basis.size()+count*column]=length;
                EONSIM_PETSC(VecScale(work.get(),1./length)); image_basis.push_back(std::move(work));
            }
        }
        PetscBLASInt n=0,one=1,lwork=0,info=0;
        EONSIM_PETSC(PetscBLASIntCast(static_cast<PetscInt>(count),&n));
        std::vector<double> singular(count),right(count*count),work(8*count),unused(1);
        EONSIM_PETSC(PetscBLASIntCast(static_cast<PetscInt>(work.size()),&lwork));
        LAPACKgesvd_("N","A",&n,&n,triangular.data(),&n,singular.data(),unused.data(),&one,
                     right.data(),&n,work.data(),&lwork,&info);
        if(info) throw std::runtime_error("Deflated FGMRES recycle SVD failed");
        for(const auto value:singular)
            if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deflated FGMRES singular response");
        const double cutoff=256*std::numeric_limits<double>::epsilon()*count*singular.front();
        std::vector<Vector> selected;
        stats.smallest_retained_response=stats.largest_retained_response=0.;
        for(std::size_t index=count;index-->0&&selected.size()<static_cast<std::size_t>(stats.capacity);) {
            if(singular[index]<=cutoff) { ++stats.rank_drops; continue; }
            Vector direction=copy(solution); EONSIM_PETSC(VecSet(direction.get(),0.));
            for(std::size_t row=0;row<count;++row)
                EONSIM_PETSC(VecAXPY(direction.get(),right[index+count*row],pool[row].direction.get()));
            if(selected.empty()) stats.smallest_retained_response=singular[index];
            stats.largest_retained_response=singular[index];
            selected.push_back(std::move(direction));
        }
        retained=std::move(selected); stats.vectors=static_cast<PetscInt>(retained.size());
        ++stats.spectral_updates; prepared=false;
    }
};
using Handle=std::shared_ptr<State>;
Handle* handle(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    Handle* result=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&result)); return result;
}
PetscErrorCode apply(PC pc,Vec input,Vec output) {
    Handle* value=nullptr; PetscCall(PCShellGetContext(pc,&value));
    try { return (*value)->apply(pc,input,output); }
    catch(const std::exception& error) {
        PetscCall(PetscInfo(pc,"Deflated FGMRES apply failed: %s\n",error.what()));
        PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); return PETSC_ERR_LIB;
    }
}
PetscErrorCode destroy(PC pc) {
    Handle* value=nullptr; PetscCall(PCShellGetContext(pc,&value)); delete value; return PETSC_SUCCESS;
}
PetscErrorCode view(PC pc,PetscViewer viewer) {
    Handle* value=nullptr; PetscCall(PCShellGetContext(pc,&value));
    PetscBool ascii=PETSC_FALSE; PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        const auto& s=(*value)->stats;
        PetscCall(PetscViewerASCIIPrintf(viewer,"Spectral deflated FGMRES: capacity=%" PetscInt_FMT
            " retained=%" PetscInt_FMT " projected applications=%" PetscInt_FMT " spectral updates=%" PetscInt_FMT "\n",
            s.capacity,s.vectors,s.projected_applications,s.spectral_updates));
        PetscCall(PetscViewerASCIIPushTab(viewer)); PetscCall(KSPView((*value)->bulk.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    return PETSC_SUCCESS;
}
} // namespace
void configure_deflated_fgmres(KSP solver,PetscInt capacity) {
    const auto comm=PetscObjectComm(reinterpret_cast<PetscObject>(solver));
    PC original=nullptr; EONSIM_PETSC(KSPGetPC(solver,&original));
    KSPType method=nullptr; PCSide side; PetscBool scaling=PETSC_FALSE;
    EONSIM_PETSC(KSPGetType(solver,&method)); EONSIM_PETSC(KSPGetPCSide(solver,&side));
    EONSIM_PETSC(KSPGetDiagonalScale(solver,&scaling));
    PetscInt low=0,high=0; MPI_Allreduce(&capacity,&low,1,MPIU_INT,MPI_MIN,comm);
    MPI_Allreduce(&capacity,&high,1,MPIU_INT,MPI_MAX,comm);
    int invalid=low!=high||capacity<1||capacity>32||!method||std::strcmp(method,KSPFGMRES)!=0||side!=PC_RIGHT||scaling;
    int any=0; MPI_Allreduce(&invalid,&any,1,MPI_INT,MPI_MAX,comm);
    if(any) throw std::runtime_error("Deflation requires right-preconditioned FGMRES, no diagonal scaling, and identical capacity in [1,32]");
    if(auto* existing=handle(original)) {
        if((*existing)->stats.capacity!=capacity) throw std::runtime_error("Deflated FGMRES capacity changed without rebuilding its session");
        return;
    }
    auto state=std::make_shared<State>(); state->stats.capacity=capacity;
    EONSIM_PETSC(KSPCreate(comm,state->bulk.put())); EONSIM_PETSC(KSPSetType(state->bulk.get(),KSPPREONLY));
    EONSIM_PETSC(KSPSetPC(state->bulk.get(),original));
    Mat a=nullptr,p=nullptr; EONSIM_PETSC(KSPGetOperators(solver,&a,&p));
    EONSIM_PETSC(KSPSetOperators(state->bulk.get(),a,p));
    PetscOwner<PC,PCDestroy> wrapper; EONSIM_PETSC(PCCreate(comm,wrapper.put()));
    EONSIM_PETSC(PCSetType(wrapper.get(),PCSHELL)); EONSIM_PETSC(PCSetOperators(wrapper.get(),a,p));
    auto owner=std::make_unique<Handle>(state);
    EONSIM_PETSC(PCShellSetContext(wrapper.get(),owner.get())); EONSIM_PETSC(PCShellSetDestroy(wrapper.get(),destroy));
    owner.release();
    EONSIM_PETSC(PCShellSetName(wrapper.get(),shell_name)); EONSIM_PETSC(PCShellSetApply(wrapper.get(),apply));
    EONSIM_PETSC(PCShellSetView(wrapper.get(),view)); EONSIM_PETSC(KSPSetPC(solver,wrapper.get()));
}
void prepare_deflated_fgmres(KSP solver,Vec rhs,Vec x) {
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc)); auto* value=handle(pc);
    if(!value) throw std::runtime_error("Deflated FGMRES was not configured before its linear solve");
    (*value)->refresh(solver,rhs,x);
}
void complete_deflated_fgmres(KSP solver,Vec solution) {
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc)); auto* value=handle(pc);
    if(!value) throw std::runtime_error("Deflated FGMRES disappeared during its linear solve");
    (*value)->complete(solution);
}
void reset_deflated_fgmres_stats(PC pc) {
    if(auto* value=handle(pc)) {
        const auto capacity=(*value)->stats.capacity;
        (*value)->stats={}; (*value)->stats.capacity=capacity;
        (*value)->stats.vectors=static_cast<PetscInt>((*value)->retained.size());
    }
}
bool query_deflated_fgmres_stats(PC pc,DeflatedFgmresStats& stats) {
    auto* value=handle(pc); if(!value) return false; stats=(*value)->stats; return true;
}
KSP deflated_fgmres_bulk_solver(PC pc) { auto* value=handle(pc); return value?(*value)->bulk.get():nullptr; }
} // namespace eonsim
