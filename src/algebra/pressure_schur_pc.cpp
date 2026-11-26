#include "eonsim/pressure_schur_pc.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <set>

namespace eonsim {
namespace {
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure Schur validation communication failed");
    if(any) throw std::runtime_error("Pressure Schur: "+message);
}
const char* kind_name(PressureSchurKind kind) {
    switch(kind) {
    case PressureSchurKind::lsc:return "lsc";
    case PressureSchurKind::bfbt:return "bfbt";
    case PressureSchurKind::pcd:return "pcd";
    }
    return "invalid";
}
void finite_matrix(MPI_Comm comm,Mat matrix,const char* description) {
    PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(matrix,&begin,&end));
    bool finite=true;
    for(PetscInt row=begin;row<end;++row) {
        PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
        EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns,&values));
        for(PetscInt j=0;j<count;++j) finite=finite&&std::isfinite(values[j]);
        EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns,&values));
    }
    common_check(comm,finite,std::string(description)+" has nonfinite entries");
}
void sum_matrix(Mat first,double a,Mat second,double b,PetscOwner<Mat,MatDestroy>& output) {
    if(!output.get()) {
        EONSIM_PETSC(MatDuplicate(first,MAT_COPY_VALUES,output.put()));
        EONSIM_PETSC(MatScale(output.get(),a));
        EONSIM_PETSC(MatAXPY(output.get(),b,second,DIFFERENT_NONZERO_PATTERN));
        EONSIM_PETSC(MatSetOption(output.get(),MAT_NEW_NONZERO_LOCATION_ERR,PETSC_TRUE));
    } else {
        EONSIM_PETSC(MatZeroEntries(output.get()));
        EONSIM_PETSC(MatAXPY(output.get(),a,first,SUBSET_NONZERO_PATTERN));
        EONSIM_PETSC(MatAXPY(output.get(),b,second,SUBSET_NONZERO_PATTERN));
    }
}
void option_default(const std::string& name,const char* value) {
    PetscBool found=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,name.c_str(),&found));
    if(!found) EONSIM_PETSC(PetscOptionsSetValue(nullptr,name.c_str(),value));
}
} // namespace

struct PressureSchurState {
    MPI_Comm comm;
    PressureSchurKind kind;
    PetscOwner<IS,ISDestroy> velocity,pressure;
    PetscOwner<Mat,MatDestroy> a,b,c,d,wb,awb,cb,cawb,p,middle;
    PetscOwner<Mat,MatDestroy> mass,laplace,transport,scaled_d,transport_d;
    PetscOwner<Vec,VecDestroy> weight,inverse_mass;
    PetscInt updates=0;
    double scale=1.;
    bool ready=false;

    PressureSchurState(MPI_Comm communicator,Mat root,
        const std::vector<PetscInt>& vr,const std::vector<PetscInt>& pr,
        PressureSchurKind selection):comm(communicator),kind(selection) {
        PetscInt begin=0,end=0,m=0,n=0;
        EONSIM_PETSC(MatGetOwnershipRange(root,&begin,&end));
        EONSIM_PETSC(MatGetSize(root,&m,&n));
        std::set<PetscInt> seen;
        bool valid=m==n&&(kind==PressureSchurKind::lsc||kind==PressureSchurKind::bfbt||kind==PressureSchurKind::pcd);
        for(auto row:vr) valid=valid&&row>=begin&&row<end&&seen.insert(row).second;
        for(auto row:pr) valid=valid&&row>=begin&&row<end&&seen.insert(row).second;
        common_check(comm,valid,"indices must be distinct locally owned root rows");
        EONSIM_PETSC(ISCreateGeneral(comm,vr.size(),vr.data(),PETSC_COPY_VALUES,velocity.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,pr.size(),pr.data(),PETSC_COPY_VALUES,pressure.put()));
        PetscInt velocities=0,pressures=0;
        EONSIM_PETSC(ISGetSize(velocity.get(),&velocities)); EONSIM_PETSC(ISGetSize(pressure.get(),&pressures));
        common_check(comm,velocities>0&&pressures>0,"requires nonempty global velocity and pressure blocks");
    }

    void pcd_auxiliary(Mat root,const char* key,PetscOwner<Mat,MatDestroy>& output) {
        Mat full=nullptr;
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(root),key,
            reinterpret_cast<PetscObject*>(&full)));
        common_check(comm,full!=nullptr,std::string("physical PCD requires assembled auxiliary ")+key);
        PetscInt rm=0,rn=0,rb=0,re=0,fm=0,fn=0,fb=0,fe=0;
        EONSIM_PETSC(MatGetSize(root,&rm,&rn)); EONSIM_PETSC(MatGetOwnershipRange(root,&rb,&re));
        EONSIM_PETSC(MatGetSize(full,&fm,&fn)); EONSIM_PETSC(MatGetOwnershipRange(full,&fb,&fe));
        common_check(comm,rm==fm&&rn==fn&&rb==fb&&re==fe,
            std::string("PCD auxiliary root numbering/ownership mismatch for ")+key);
        EONSIM_PETSC(MatCreateSubMatrix(full,pressure.get(),pressure.get(),
            output.get()?MAT_REUSE_MATRIX:MAT_INITIAL_MATRIX,output.put()));
        finite_matrix(comm,output.get(),key);
    }

    void update(Mat root) {
        // Refresh failure invalidates every action sharing this state; a
        // partially updated product must never be applied as the old PC.
        ready=false;
        const bool first=!d.get();
        const MatReuse reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(root,pressure.get(),pressure.get(),reuse,d.put()));
        finite_matrix(comm,d.get(),"pressure block");
        if(kind==PressureSchurKind::pcd) {
            pcd_auxiliary(root,pressure_pcd_mass_key,mass);
            pcd_auxiliary(root,pressure_pcd_laplace_key,laplace);
            pcd_auxiliary(root,pressure_pcd_transport_key,transport);
            if(first) {
                EONSIM_PETSC(MatCreateVecs(mass.get(),inverse_mass.put(),nullptr));
                EONSIM_PETSC(MatDuplicate(d.get(),MAT_DO_NOT_COPY_VALUES,scaled_d.put()));
            }
            EONSIM_PETSC(MatGetDiagonal(mass.get(),inverse_mass.get()));
            PetscScalar* values=nullptr; PetscInt size=0;
            EONSIM_PETSC(VecGetLocalSize(inverse_mass.get(),&size));
            EONSIM_PETSC(VecGetArray(inverse_mass.get(),&values));
            bool valid=true;
            for(PetscInt i=0;i<size;++i) {
                valid=valid&&std::isfinite(values[i])&&values[i]>0;
                if(values[i]>0) { values[i]=1./values[i]; valid=valid&&std::isfinite(values[i]); }
            }
            EONSIM_PETSC(VecRestoreArray(inverse_mass.get(),&values));
            PetscInt begin=0,end=0;
            EONSIM_PETSC(MatGetOwnershipRange(mass.get(),&begin,&end));
            for(PetscInt row=begin;row<end;++row) {
                PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* entries=nullptr;
                EONSIM_PETSC(MatGetRow(mass.get(),row,&count,&columns,&entries));
                for(PetscInt j=0;j<count;++j) if(columns[j]!=row&&entries[j]!=0.) valid=false;
                EONSIM_PETSC(MatRestoreRow(mass.get(),row,&count,&columns,&entries));
            }
            common_check(comm,valid,"PCD mass must be finite positive and lumped, with a representable reciprocal");
            EONSIM_PETSC(MatCopy(d.get(),scaled_d.get(),SAME_NONZERO_PATTERN));
            EONSIM_PETSC(MatDiagonalScale(scaled_d.get(),inverse_mass.get(),nullptr));
            EONSIM_PETSC(MatMatMult(transport.get(),scaled_d.get(),reuse,PETSC_DEFAULT,transport_d.put()));
            sum_matrix(laplace.get(),1.,transport_d.get(),1.,p);
        } else {
            EONSIM_PETSC(MatCreateSubMatrix(root,velocity.get(),velocity.get(),reuse,a.put()));
            EONSIM_PETSC(MatCreateSubMatrix(root,velocity.get(),pressure.get(),reuse,b.put()));
            EONSIM_PETSC(MatCreateSubMatrix(root,pressure.get(),velocity.get(),reuse,c.put()));
            if(first) {
                EONSIM_PETSC(MatCreateVecs(a.get(),weight.put(),nullptr));
                EONSIM_PETSC(MatDuplicate(b.get(),MAT_DO_NOT_COPY_VALUES,wb.put()));
            }
            bool valid=true;
            if(kind==PressureSchurKind::bfbt) {
                EONSIM_PETSC(MatGetDiagonal(a.get(),weight.get()));
                PetscScalar* values=nullptr; PetscInt size=0;
                EONSIM_PETSC(VecGetLocalSize(weight.get(),&size));
                EONSIM_PETSC(VecGetArray(weight.get(),&values));
                for(PetscInt i=0;i<size;++i) {
                    valid=valid&&std::isfinite(values[i])&&values[i]!=0.;
                    if(values[i]!=0.) { values[i]=1./std::abs(values[i]); valid=valid&&std::isfinite(values[i]); }
                }
                EONSIM_PETSC(VecRestoreArray(weight.get(),&values));
                common_check(comm,valid,"BFBt requires finite nonzero momentum diagonals with representable reciprocals");
            } else EONSIM_PETSC(VecSet(weight.get(),1.));
            // s supplies the units needed for both stabilization terms. The
            // infinity norm is an inexpensive upper bound, not an eigenvalue
            // estimate or a claim of optimal stabilization for all FSI regimes.
            const PetscScalar* weights=nullptr;
            EONSIM_PETSC(VecGetArrayRead(weight.get(),&weights));
            PetscInt begin=0,end=0; EONSIM_PETSC(MatGetOwnershipRange(a.get(),&begin,&end));
            double local=0.;
            for(PetscInt row=begin;row<end;++row) {
                PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(a.get(),row,&count,&columns,&values));
                long double sum=0.;
                for(PetscInt j=0;j<count;++j) {
                    valid=valid&&std::isfinite(values[j]);
                    sum+=std::abs(static_cast<long double>(weights[row-begin])*values[j]);
                }
                local=std::max(local,static_cast<double>(sum));
                valid=valid&&std::isfinite(static_cast<double>(sum));
                EONSIM_PETSC(MatRestoreRow(a.get(),row,&count,&columns,&values));
            }
            EONSIM_PETSC(VecRestoreArrayRead(weight.get(),&weights));
            common_check(comm,valid,"nonfinite scaled momentum matrix");
            if(MPI_Allreduce(&local,&scale,1,MPI_DOUBLE,MPI_MAX,comm)!=MPI_SUCCESS)
                throw std::runtime_error("pressure commutator scale reduction failed");
            common_check(comm,scale>0&&std::isfinite(scale*scale),"invalid or unrepresentable commutator scale");
            EONSIM_PETSC(MatCopy(b.get(),wb.get(),SAME_NONZERO_PATTERN));
            EONSIM_PETSC(MatDiagonalScale(wb.get(),weight.get(),nullptr));
            EONSIM_PETSC(MatMatMult(c.get(),wb.get(),reuse,PETSC_DEFAULT,cb.put()));
            EONSIM_PETSC(MatMatMult(a.get(),wb.get(),reuse,PETSC_DEFAULT,awb.put()));
            EONSIM_PETSC(MatDiagonalScale(awb.get(),weight.get(),nullptr));
            EONSIM_PETSC(MatMatMult(c.get(),awb.get(),reuse,PETSC_DEFAULT,cawb.put()));
            sum_matrix(cb.get(),-1.,d.get(),scale,p);
            sum_matrix(cawb.get(),-1.,d.get(),scale*scale,middle);
            finite_matrix(comm,middle.get(),"stabilized commutator middle matrix");
        }
        finite_matrix(comm,p.get(),"pressure auxiliary solve matrix");
        ++updates;
        ready=true;
        PetscBool report=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
        if(report) {
            PetscInt rows=0; EONSIM_PETSC(MatGetSize(p.get(),&rows,nullptr));
            EONSIM_PETSC(PetscPrintf(comm,"pressure_schur kind=%s rows=%" PetscInt_FMT
                " numerical_updates=%" PetscInt_FMT " scale=%.17g\n",kind_name(kind),rows,updates,scale));
        }
    }
};

namespace {
constexpr const char* shell_name="EONSim stabilized pressure commutator/PCD";
struct PressureAction {
    PressureSchurHandle state;
    PetscOwner<KSP,KSPDestroy> auxiliary;
    PetscOwner<Vec,VecDestroy> first,second;

    PetscErrorCode solve(PC pc,Vec rhs,Vec solution,PetscBool* success) {
        PetscFunctionBeginUser;
        // Finite work caps are approximate inverses. Breakdown, failed local
        // factors and nonfinite outputs must reach the containing outer solve.
        // Convert numerical subsolve failure to PC failure rather than throwing
        // across a PETSc callback while the caller holds read-locked vectors.
        const PetscErrorCode error=KSPSolve(auxiliary.get(),rhs,solution);
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
        PC subpc=nullptr; PCFailedReason failed=PC_NOERROR;
        const auto reason_error=KSPGetConvergedReason(auxiliary.get(),&reason);
        const auto pc_error=KSPGetPC(auxiliary.get(),&subpc);
        const auto failure_error=subpc?PCGetFailedReason(subpc,&failed):PETSC_ERR_ARG_WRONGSTATE;
        bool valid=error==PETSC_SUCCESS&&reason_error==PETSC_SUCCESS&&pc_error==PETSC_SUCCESS&&
            failure_error==PETSC_SUCCESS&&failed==PC_NOERROR&&(reason>0||reason==KSP_DIVERGED_ITS);
        const PetscScalar* values=nullptr; PetscInt size=0;
        PetscCall(VecGetLocalSize(solution,&size)); PetscCall(VecGetArrayRead(solution,&values));
        for(PetscInt i=0;i<size;++i) valid=valid&&std::isfinite(values[i]);
        PetscCall(VecRestoreArrayRead(solution,&values));
        int local=valid,all=0;
        PetscCallMPI(MPI_Allreduce(&local,&all,1,MPI_INT,MPI_MIN,state->comm));
        *success=all?PETSC_TRUE:PETSC_FALSE;
        if(!all) PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
    PetscErrorCode apply(PC pc,Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!state->ready) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
            PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        PetscCall(PCSetFailedReason(pc,PC_NOERROR));
        PetscBool success=PETSC_FALSE;
        if(state->kind==PressureSchurKind::pcd) {
            PetscCall(VecPointwiseMult(first.get(),state->inverse_mass.get(),input));
            PetscCall(MatMult(state->transport.get(),first.get(),second.get()));
            PetscCall(solve(pc,second.get(),output,&success));
        } else {
            PetscCall(solve(pc,input,first.get(),&success));
            if(!success) {
                PetscCall(VecSet(output,PETSC_INFINITY));
                PetscFunctionReturn(PETSC_SUCCESS);
            }
            PetscCall(MatMult(state->middle.get(),first.get(),second.get()));
            PetscCall(solve(pc,second.get(),output,&success));
        }
        if(!success) PetscCall(VecSet(output,PETSC_INFINITY));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};
PetscErrorCode apply_pressure(PC pc,Vec input,Vec output) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    PetscCall(action->apply(pc,input,output));
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode destroy_pressure(PC pc) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    delete action;
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode view_pressure(PC pc,PetscViewer viewer) {
    PetscFunctionBeginUser;
    PressureAction* action=nullptr; PetscCall(PCShellGetContext(pc,&action));
    PetscBool ascii=PETSC_FALSE;
    PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        PetscCall(PetscViewerASCIIPrintf(viewer,"Pressure %s, numerical updates=%" PetscInt_FMT
            ", stabilization scale=%.17g\n",kind_name(action->state->kind),action->state->updates,action->state->scale));
        PetscCall(PetscViewerASCIIPushTab(viewer));
        PetscCall(KSPView(action->auxiliary.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    PetscFunctionReturn(PETSC_SUCCESS);
}
} // namespace

PressureSchurHandle make_pressure_schur_state(MPI_Comm comm,Mat root,
    const std::vector<PetscInt>& velocity_root_rows,
    const std::vector<PetscInt>& pressure_root_rows,PressureSchurKind kind) {
    auto result=std::make_shared<PressureSchurState>(comm,root,velocity_root_rows,pressure_root_rows,kind);
    result->update(root); return result;
}
Mat pressure_schur_matrix(const PressureSchurHandle& state) { return state->p.get(); }
void refresh_pressure_schur(const PressureSchurHandle& state,Mat root) { state->update(root); }

void propagate_pressure_auxiliaries(Mat root,Mat child,IS child_rows) {
    const auto comm=PetscObjectComm(reinterpret_cast<PetscObject>(root));
    const std::array<const char*,3> keys{{pressure_pcd_mass_key,pressure_pcd_laplace_key,pressure_pcd_transport_key}};
    std::array<Mat,3> sources{};
    int count=0;
    for(std::size_t i=0;i<keys.size();++i) {
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(root),keys[i],
            reinterpret_cast<PetscObject*>(&sources[i])));
        count+=sources[i]!=nullptr;
    }
    int lo=0,hi=0;
    if(MPI_Allreduce(&count,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&count,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure auxiliary propagation communication failed");
    common_check(comm,lo==hi&&(count==0||count==3),"PCD auxiliary composition must be a complete triple on every rank");
    if(count==0) return;
    for(std::size_t i=0;i<keys.size();++i) {
        Mat previous=nullptr;
        EONSIM_PETSC(PetscObjectQuery(reinterpret_cast<PetscObject>(child),keys[i],
            reinterpret_cast<PetscObject*>(&previous)));
        PetscOwner<Mat,MatDestroy> extracted;
        if(previous) {
            EONSIM_PETSC(PetscObjectReference(reinterpret_cast<PetscObject>(previous)));
            *extracted.put()=previous;
        }
        EONSIM_PETSC(MatCreateSubMatrix(sources[i],child_rows,child_rows,
            previous?MAT_REUSE_MATRIX:MAT_INITIAL_MATRIX,extracted.put()));
        EONSIM_PETSC(PetscObjectCompose(reinterpret_cast<PetscObject>(child),keys[i],
            reinterpret_cast<PetscObject>(extracted.get())));
    }
}

void validate_pressure_schur_options(MPI_Comm comm,const std::string& pressure_prefix) {
    char requested[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+pressure_prefix+"pc_type").c_str(),requested,sizeof(requested),&set));
    common_check(comm,!set||std::strcmp(requested,PCSHELL)==0,
        "pressure commutator/PCD requires its shell PC at "+pressure_prefix);
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+pressure_prefix+"ksp_type").c_str(),requested,sizeof(requested),&set));
    const int local=!set||std::strcmp(requested,KSPPREONLY)==0?1:std::strcmp(requested,KSPFGMRES)==0?2:0;
    int lo=0,hi=0;
    if(MPI_Allreduce(&local,&lo,1,MPI_INT,MPI_MIN,comm)!=MPI_SUCCESS||
       MPI_Allreduce(&local,&hi,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("pressure solver option communication failed");
    common_check(comm,lo==hi&&lo!=0,
        "pressure commutator/PCD KSP must be preonly or fgmres and identical on every rank at "+pressure_prefix);
}

void configure_pressure_schur_pc(MPI_Comm comm,KSP pressure,const PressureSchurHandle& state) {
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(pressure,&prefix));
    const std::string own=prefix?prefix:"",aux=own+"pressure_aux_";
    validate_pressure_schur_options(comm,own);
    auto action=std::make_unique<PressureAction>(); action->state=state;
    EONSIM_PETSC(KSPCreate(comm,action->auxiliary.put()));
    EONSIM_PETSC(KSPSetOptionsPrefix(action->auxiliary.get(),aux.c_str()));
    EONSIM_PETSC(KSPSetOperators(action->auxiliary.get(),state->p.get(),state->p.get()));
    EONSIM_PETSC(KSPSetType(action->auxiliary.get(),KSPPREONLY));
    EONSIM_PETSC(KSPSetTolerances(action->auxiliary.get(),1e-3,PETSC_DEFAULT,PETSC_DEFAULT,30));
    PC auxiliary_pc=nullptr; EONSIM_PETSC(KSPGetPC(action->auxiliary.get(),&auxiliary_pc));
    EONSIM_PETSC(PCSetType(auxiliary_pc,PCGAMG));
    EONSIM_PETSC(PCSetUseAmat(auxiliary_pc,PETSC_FALSE));
    option_default("-"+aux+"mg_coarse_ksp_type","gmres");
    option_default("-"+aux+"mg_coarse_pc_type","jacobi");
    option_default("-"+aux+"mg_coarse_ksp_rtol","1e-10");
    option_default("-"+aux+"mg_coarse_ksp_max_it","200");
    option_default("-"+aux+"mg_coarse_ksp_norm_type","unpreconditioned");
    EONSIM_PETSC(KSPSetFromOptions(action->auxiliary.get()));
    EONSIM_PETSC(MatCreateVecs(state->p.get(),action->first.put(),nullptr));
    EONSIM_PETSC(VecDuplicate(action->first.get(),action->second.put()));
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(pressure,&pc));
    EONSIM_PETSC(KSPSetType(pressure,KSPPREONLY));
    EONSIM_PETSC(PCSetType(pc,PCSHELL));
    EONSIM_PETSC(PCSetUseAmat(pc,PETSC_FALSE));
    EONSIM_PETSC(PCShellSetContext(pc,action.get()));
    EONSIM_PETSC(PCShellSetDestroy(pc,destroy_pressure));
    action.release();
    EONSIM_PETSC(PCShellSetName(pc,shell_name));
    EONSIM_PETSC(PCShellSetApply(pc,apply_pressure));
    EONSIM_PETSC(PCShellSetView(pc,view_pressure));
    EONSIM_PETSC(KSPSetFromOptions(pressure));
    PCType actual=nullptr; EONSIM_PETSC(PCGetType(pc,&actual));
    common_check(comm,actual&&std::strcmp(actual,PCSHELL)==0,"options changed pressure shell PC at "+own);
}
KSP pressure_schur_auxiliary_solver(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    PressureAction* action=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&action));
    return action?action->auxiliary.get():nullptr;
}
} // namespace eonsim
