#include "eonsim/rcr_port_pc.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <memory>
#include <numeric>

namespace eonsim {
namespace {
constexpr const char* shell_name="EONSim RCR port Schur (Sherman-Morrison/Woodbury)";
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("RCR port validation communication failed");
    if(any) throw std::runtime_error("RCR port PC: "+message);
}

struct PortState {
    MPI_Comm comm;
    Mat source=nullptr; // Identity only; the containing KSP owns full.
    PC owner=nullptr; // Borrowed; the shell destroy callback clears it.
    PetscObjectState graph=0;
    PetscInt begin=0,end=0,global=0,port_begin=0,count=0,bulk_local=0;
    bool ready=false;
    PetscBool report=PETSC_FALSE;
    std::vector<PetscInt> bulk_offsets,port_offsets;
    PetscOwner<IS,ISDestroy> bulk_is,port_is;
    PetscOwner<Mat,MatDestroy> a,u,v,d,vt;
    PcSchurUpdates bulk_updates;
    PetscOwner<KSP,KSPDestroy> bulk;
    PetscOwner<Vec,VecDestroy> rhs,solution;
    std::vector<PetscOwner<Vec,VecDestroy>> columns,rows,responses;
    std::vector<Vec> response_handles;
    std::vector<const PetscScalar*> response_arrays;
    std::vector<PetscScalar> local_gram,global_gram,lu,row_scale,column_scale;
    std::vector<PetscScalar> local_rhs,port_rhs,negative_solution;
    std::vector<PetscInt> pivots;
    std::function<void(KSP,Mat,PcSchurUpdates*)> configure;
    RcrPortPcStats stats;

    PortState(MPI_Comm communicator,Mat full,const std::vector<PetscInt>& ports,
              const std::string& prefix,
              const std::function<void(KSP,Mat,PcSchurUpdates*)>& callback):
        comm(communicator),source(full),configure(callback) {
        PetscInt n=0,cbegin=0,cend=0;
        EONSIM_PETSC(MatGetSize(full,&global,&n));
        EONSIM_PETSC(MatGetOwnershipRange(full,&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRangeColumn(full,&cbegin,&cend));
        bool valid=global==n&&global>1&&begin==cbegin&&end==cend&&
            ports.size()<=static_cast<std::size_t>(std::numeric_limits<int>::max());
        auto sorted=ports;
        std::sort(sorted.begin(),sorted.end());
        valid=valid&&std::adjacent_find(sorted.begin(),sorted.end())==sorted.end();
        for(auto row:sorted) valid=valid&&row>=begin&&row<end;
        common_check(comm,valid,"port rows must be distinct owned rows of a square matrix with matching row/column ownership");
        int ranks=0,rank=0; MPI_Comm_size(comm,&ranks); MPI_Comm_rank(comm,&rank);
        const int owned=static_cast<int>(sorted.size());
        std::vector<int> sizes(ranks);
        if(MPI_Allgather(&owned,1,MPI_INT,sizes.data(),1,MPI_INT,comm)!=MPI_SUCCESS)
            throw std::runtime_error("RCR port count communication failed");
        long long total=0;
        for(int r=0;r<ranks;++r) {
            if(r==rank) port_begin=static_cast<PetscInt>(total);
            total+=sizes[r];
        }
        // Two k*k tables and one failure flag share the setup reduction.
        common_check(comm,total>0&&total<global&&
            total<=std::numeric_limits<PetscInt>::max()&&
            total<=static_cast<long long>(std::sqrt((std::numeric_limits<int>::max()-1)/2.)),
            "requires nonempty bulk and ports with a representable dense port table");
        count=static_cast<PetscInt>(total); stats.ports=count;
        std::vector<PetscInt> bulk_rows;
        bulk_rows.reserve(end-begin-sorted.size());
        std::size_t next=0;
        for(PetscInt row=begin;row<end;++row) {
            if(next<sorted.size()&&row==sorted[next]) { port_offsets.push_back(row-begin); ++next; }
            else { bulk_rows.push_back(row); bulk_offsets.push_back(row-begin); }
        }
        bulk_local=static_cast<PetscInt>(bulk_rows.size());
        EONSIM_PETSC(ISCreateGeneral(comm,bulk_local,bulk_rows.data(),PETSC_COPY_VALUES,bulk_is.put()));
        EONSIM_PETSC(ISCreateGeneral(comm,static_cast<PetscInt>(sorted.size()),sorted.data(),PETSC_COPY_VALUES,port_is.put()));
        EONSIM_PETSC(MatGetNonzeroState(full,&graph));
        EONSIM_PETSC(KSPCreate(comm,bulk.put()));
        EONSIM_PETSC(KSPSetOptionsPrefix(bulk.get(),prefix.c_str()));
        EONSIM_PETSC(KSPSetType(bulk.get(),KSPPREONLY));
        PetscBool plan_report=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-rcr_port_report",&report,nullptr));
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&plan_report,nullptr));
        if(plan_report) report=PETSC_TRUE;
        const auto square=static_cast<std::size_t>(count)*count;
        local_gram.resize(2*square+1); global_gram.resize(2*square+1);
        lu.resize(square); row_scale.resize(count); column_scale.resize(count); pivots.resize(count);
        local_rhs.resize(count+1); port_rhs.resize(count+1); negative_solution.resize(count);
        columns.resize(count); rows.resize(count); responses.resize(count);
        response_handles.resize(count); response_arrays.resize(count);
    }

    // Inner numerical failures are carried into the already-needed port
    // reduction. PREONLY failures must not be mistaken for successful H*r.
    bool solve_bulk(Vec input,Vec output) {
        const PetscErrorCode error=KSPSolve(bulk.get(),input,output);
        KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
        PC pc=nullptr; PCFailedReason failure=PC_NOERROR;
        const PetscErrorCode reason_error=KSPGetConvergedReason(bulk.get(),&reason);
        const PetscErrorCode pc_error=KSPGetPC(bulk.get(),&pc);
        const PetscErrorCode failure_error=pc?PCGetFailedReason(pc,&failure):PETSC_ERR_ARG_WRONGSTATE;
        return error==PETSC_SUCCESS&&reason_error==PETSC_SUCCESS&&pc_error==PETSC_SUCCESS&&
            failure_error==PETSC_SUCCESS&&reason>0&&failure==PC_NOERROR;
    }

    void factor() {
        const auto square=static_cast<std::size_t>(count)*count;
        const double tolerance=64*std::numeric_limits<double>::epsilon()*std::max<PetscInt>(1,count);
        for(PetscInt i=0;i<count;++i) {
            row_scale[i]=0;
            double accumulation_scale=0;
            for(PetscInt j=0;j<count;++j) {
                const auto index=static_cast<std::size_t>(i)*count+j;
                row_scale[i]=std::max(row_scale[i],std::abs(global_gram[index]));
                accumulation_scale=std::max(accumulation_scale,global_gram[square+index]);
            }
            if(!std::isfinite(row_scale[i])||!std::isfinite(accumulation_scale)||
               !(row_scale[i]>tolerance*accumulation_scale))
                throw LinearSolveFailure("RCR port Schur is singular, nonfinite or cancelled at working precision");
        }
        for(PetscInt j=0;j<count;++j) {
            column_scale[j]=0;
            for(PetscInt i=0;i<count;++i)
                column_scale[j]=std::max(column_scale[j],std::abs(global_gram[static_cast<std::size_t>(i)*count+j]/row_scale[i]));
            if(!std::isfinite(column_scale[j])||!(column_scale[j]>0))
                throw LinearSolveFailure("RCR port Schur has an empty or nonfinite column");
        }
        for(PetscInt i=0;i<count;++i) for(PetscInt j=0;j<count;++j)
            lu[static_cast<std::size_t>(i)*count+j]=(global_gram[static_cast<std::size_t>(i)*count+j]/row_scale[i])/column_scale[j];
        // One port uses a scalar denominator; the common scaled storage also
        // avoids overflow in q=g/S for widely differing port impedances.
        for(PetscInt k=0;k<count;++k) {
            PetscInt pivot=k;
            for(PetscInt i=k+1;i<count;++i)
                if(std::abs(lu[static_cast<std::size_t>(i)*count+k])>std::abs(lu[static_cast<std::size_t>(pivot)*count+k])) pivot=i;
            pivots[k]=pivot;
            const double value=lu[static_cast<std::size_t>(pivot)*count+k];
            if(!std::isfinite(value)||std::abs(value)<=tolerance)
                throw LinearSolveFailure("RCR port Schur has a singular or ill-conditioned dense pivot");
            if(pivot!=k) for(PetscInt j=0;j<count;++j)
                std::swap(lu[static_cast<std::size_t>(k)*count+j],lu[static_cast<std::size_t>(pivot)*count+j]);
            for(PetscInt i=k+1;i<count;++i) {
                auto& multiplier=lu[static_cast<std::size_t>(i)*count+k];
                multiplier/=lu[static_cast<std::size_t>(k)*count+k];
                for(PetscInt j=k+1;j<count;++j)
                    lu[static_cast<std::size_t>(i)*count+j]-=multiplier*lu[static_cast<std::size_t>(k)*count+j];
            }
        }
        if(!std::all_of(lu.begin(),lu.end(),[](double value){return std::isfinite(value);}))
            throw LinearSolveFailure("Nonfinite RCR port Schur factor");
    }

    bool solve_ports() {
        for(PetscInt i=0;i<count;++i) port_rhs[i]/=row_scale[i];
        // Later factorization pivots also swap earlier L multipliers. Apply
        // the complete recorded row permutation before forward substitution.
        for(PetscInt k=0;k<count;++k)
            if(pivots[k]!=k) std::swap(port_rhs[k],port_rhs[pivots[k]]);
        for(PetscInt k=0;k<count;++k) {
            for(PetscInt i=k+1;i<count;++i)
                port_rhs[i]-=lu[static_cast<std::size_t>(i)*count+k]*port_rhs[k];
        }
        for(PetscInt i=count;i-->0;) {
            for(PetscInt j=i+1;j<count;++j)
                port_rhs[i]-=lu[static_cast<std::size_t>(i)*count+j]*port_rhs[j];
            port_rhs[i]/=lu[static_cast<std::size_t>(i)*count+i];
        }
        bool finite=true;
        for(PetscInt i=0;i<count;++i) {
            port_rhs[i]/=column_scale[i];
            negative_solution[i]=-port_rhs[i];
            finite=finite&&std::isfinite(port_rhs[i]);
        }
        return finite;
    }

    void refresh(Mat full) {
        ready=false; // Failed preparation never leaves a usable old generation.
        PetscObjectState current_graph=0; EONSIM_PETSC(MatGetNonzeroState(full,&current_graph));
        common_check(comm,full==source&&current_graph==graph,
                     "matrix identity or graph changed; rebuild the port layout and PC");
        const bool first=!a.get();
        const MatReuse reuse=first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX;
        EONSIM_PETSC(MatCreateSubMatrix(full,bulk_is.get(),bulk_is.get(),reuse,a.put()));
        EONSIM_PETSC(MatCreateSubMatrix(full,bulk_is.get(),port_is.get(),reuse,u.put()));
        EONSIM_PETSC(MatCreateSubMatrix(full,port_is.get(),bulk_is.get(),reuse,v.put()));
        EONSIM_PETSC(MatCreateSubMatrix(full,port_is.get(),port_is.get(),reuse,d.put()));
        EONSIM_PETSC(MatTranspose(v.get(),reuse,vt.put()));
        EONSIM_PETSC(KSPSetOperators(bulk.get(),a.get(),a.get()));
        if(first) {
            EONSIM_PETSC(MatCreateVecs(a.get(),solution.put(),rhs.put()));
            for(PetscInt i=0;i<count;++i) {
                EONSIM_PETSC(VecDuplicate(rhs.get(),columns[i].put()));
                EONSIM_PETSC(VecDuplicate(rhs.get(),rows[i].put()));
                EONSIM_PETSC(VecDuplicate(solution.get(),responses[i].put()));
                response_handles[i]=responses[i].get();
            }
            configure(bulk.get(),a.get(),&bulk_updates);
            KSPType type=nullptr; PetscBool nonzero=PETSC_FALSE;
            EONSIM_PETSC(KSPGetType(bulk.get(),&type));
            EONSIM_PETSC(KSPGetInitialGuessNonzero(bulk.get(),&nonzero));
            common_check(comm,type&&std::strcmp(type,KSPPREONLY)==0&&!nonzero,
                         "bulk response requires PREONLY and a zero initial guess");
            EONSIM_PETSC(KSPSetErrorIfNotConverged(bulk.get(),PETSC_FALSE));
        } else bulk_updates.refresh(a.get());
        EONSIM_PETSC(KSPSetReusePreconditioner(bulk.get(),PETSC_FALSE));
        EONSIM_PETSC(KSPSetUp(bulk.get()));
        bool valid=true;
        for(PetscInt i=0;i<count;++i) {
            EONSIM_PETSC(MatGetColumnVector(u.get(),columns[i].get(),i));
            EONSIM_PETSC(MatGetColumnVector(vt.get(),rows[i].get(),i));
            const bool solved=solve_bulk(columns[i].get(),responses[i].get());
            ++stats.response_solves;
            valid=valid&&solved;
        }
        std::fill(local_gram.begin(),local_gram.end(),0.);
        const auto square=static_cast<std::size_t>(count)*count;
        PetscInt dbegin=0,dend=0; EONSIM_PETSC(MatGetOwnershipRange(d.get(),&dbegin,&dend));
        for(PetscInt row=dbegin;row<dend;++row) {
            PetscInt entries=0; const PetscInt* indices=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(d.get(),row,&entries,&indices,&values));
            for(PetscInt j=0;j<entries;++j) {
                const auto index=static_cast<std::size_t>(row)*count+indices[j];
                local_gram[index]=values[j]; local_gram[square+index]=std::abs(values[j]);
            }
            EONSIM_PETSC(MatRestoreRow(d.get(),row,&entries,&indices,&values));
        }
        for(PetscInt j=0;j<count;++j)
            EONSIM_PETSC(VecGetArrayRead(responses[j].get(),&response_arrays[j]));
        for(PetscInt i=0;i<count;++i) {
            const PetscScalar* row=nullptr; EONSIM_PETSC(VecGetArrayRead(rows[i].get(),&row));
            for(PetscInt j=0;j<count;++j) {
                long double dot=0,absolute=0;
                for(PetscInt p=0;valid&&p<bulk_local;++p) {
                    const long double product=static_cast<long double>(row[p])*response_arrays[j][p];
                    dot+=product; absolute+=std::abs(product);
                }
                const auto index=static_cast<std::size_t>(i)*count+j;
                local_gram[index]-=static_cast<double>(dot);
                local_gram[square+index]+=static_cast<double>(absolute);
            }
            EONSIM_PETSC(VecRestoreArrayRead(rows[i].get(),&row));
        }
        for(PetscInt j=0;j<count;++j)
            EONSIM_PETSC(VecRestoreArrayRead(responses[j].get(),&response_arrays[j]));
        valid=valid&&std::all_of(local_gram.begin(),local_gram.end()-1,[](double value){return std::isfinite(value);});
        local_gram.back()=valid?0.:1.;
        if(MPI_Allreduce(local_gram.data(),global_gram.data(),static_cast<int>(local_gram.size()),MPIU_SCALAR,MPI_SUM,comm)!=MPI_SUCCESS)
            throw std::runtime_error("RCR port Schur reduction failed");
        ++stats.setup_reductions;
        if(global_gram.back()!=0)
            throw LinearSolveFailure("RCR port bulk response failed or produced nonfinite coefficients");
        factor();
        if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
        ready=true; ++stats.rebuilds;
        if(report) EONSIM_PETSC(PetscPrintf(comm,
            "rcr_port_pc ports=%" PetscInt_FMT " rebuilds=%" PetscInt_FMT " responses=%" PetscInt_FMT
            " setup_reductions=%" PetscInt_FMT " applications=%" PetscInt_FMT " apply_reductions=%" PetscInt_FMT "\n",
            count,stats.rebuilds,stats.response_solves,stats.setup_reductions,stats.applications,stats.apply_reductions));
    }

    PetscErrorCode apply(PC pc,Vec input,Vec output) {
        PetscFunctionBeginUser;
        PetscCheck(ready,comm,PETSC_ERR_ARG_WRONGSTATE,"RCR port PC has no valid prepared generation");
        std::fill(local_rhs.begin(),local_rhs.end(),0.);
        const PetscScalar* in=nullptr; PetscScalar* b=nullptr;
        PetscCall(VecGetArrayRead(input,&in)); PetscCall(VecGetArray(rhs.get(),&b));
        for(PetscInt i=0;i<bulk_local;++i) b[i]=in[bulk_offsets[i]];
        for(std::size_t i=0;i<port_offsets.size();++i) local_rhs[port_begin+i]=in[port_offsets[i]];
        PetscCall(VecRestoreArray(rhs.get(),&b)); PetscCall(VecRestoreArrayRead(input,&in));
        bool valid=solve_bulk(rhs.get(),solution.get());
        const PetscScalar* z=nullptr; PetscCall(VecGetArrayRead(solution.get(),&z));
        for(PetscInt i=0;i<count;++i) {
            const PetscScalar* row=nullptr; PetscCall(VecGetArrayRead(rows[i].get(),&row));
            long double dot=0;
            for(PetscInt j=0;valid&&j<bulk_local;++j) dot+=static_cast<long double>(row[j])*z[j];
            local_rhs[i]-=static_cast<double>(dot);
            PetscCall(VecRestoreArrayRead(rows[i].get(),&row));
            valid=valid&&std::isfinite(local_rhs[i]);
        }
        PetscCall(VecRestoreArrayRead(solution.get(),&z));
        local_rhs.back()=valid?0.:1.;
        PetscCallMPI(MPI_Allreduce(local_rhs.data(),port_rhs.data(),static_cast<int>(local_rhs.size()),MPIU_SCALAR,MPI_SUM,comm));
        ++stats.applications; ++stats.apply_reductions;
        if(port_rhs.back()!=0||!solve_ports()) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
            PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        PetscCall(VecMAXPY(solution.get(),count,negative_solution.data(),response_handles.data()));
        PetscCall(VecGetArrayRead(solution.get(),&z));
        PetscScalar* out=nullptr; PetscCall(VecGetArray(output,&out));
        bool finite=true;
        for(PetscInt i=0;i<bulk_local;++i) {
            out[bulk_offsets[i]]=z[i]; finite=finite&&std::isfinite(z[i]);
        }
        for(std::size_t i=0;i<port_offsets.size();++i) out[port_offsets[i]]=port_rhs[port_begin+i];
        PetscCall(VecRestoreArray(output,&out)); PetscCall(VecRestoreArrayRead(solution.get(),&z));
        // PETSc propagates a rank-local PC failure through the outer Krylov
        // reductions; no second port-inner-product reduction is introduced.
        if(!finite) PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};

using Handle=std::shared_ptr<PortState>;
PetscErrorCode apply_port(PC pc,Vec input,Vec output) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    PetscCall((*handle)->apply(pc,input,output));
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode destroy_port(PC pc) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    if(handle) (*handle)->owner=nullptr;
    delete handle;
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode view_port(PC pc,PetscViewer viewer) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    PetscBool ascii=PETSC_FALSE;
    PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        const auto& s=(*handle)->stats;
        PetscCall(PetscViewerASCIIPrintf(viewer,
            "RCR ports=%" PetscInt_FMT ", successful generations=%" PetscInt_FMT ", response solves=%" PetscInt_FMT
            ", setup reductions=%" PetscInt_FMT ", applications=%" PetscInt_FMT ", apply reductions=%" PetscInt_FMT "\n",
            s.ports,s.rebuilds,s.response_solves,s.setup_reductions,s.applications,s.apply_reductions));
        PetscCall(PetscViewerASCIIPushTab(viewer));
        PetscCall(KSPView((*handle)->bulk.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    PetscFunctionReturn(PETSC_SUCCESS);
}
Handle* get_handle(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    Handle* handle=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&handle));
    return handle;
}
} // namespace

void configure_rcr_port_pc(MPI_Comm comm,KSP solver,Mat full,
    const std::vector<PetscInt>& local_port_rows,
    const std::function<void(KSP,Mat,PcSchurUpdates*)>& configure_bulk,
    PcSchurUpdates* updates) {
    common_check(comm,updates&&static_cast<bool>(configure_bulk),"requires a live update registry and bulk configuration callback");
    const char* prefix=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix));
    auto state=std::make_shared<PortState>(comm,full,local_port_rows,
        std::string(prefix?prefix:"")+"rcr_bulk_",configure_bulk);
    state->refresh(full);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetOperators(solver,full,full));
    EONSIM_PETSC(PCSetType(pc,PCSHELL));
    auto handle=std::make_unique<Handle>(state);
    EONSIM_PETSC(PCShellSetContext(pc,handle.get()));
    EONSIM_PETSC(PCShellSetDestroy(pc,destroy_port));
    handle.release();
    state->owner=pc;
    EONSIM_PETSC(PCShellSetName(pc,shell_name));
    EONSIM_PETSC(PCShellSetApply(pc,apply_port));
    EONSIM_PETSC(PCShellSetView(pc,view_port));
    updates->refreshers.push_back([state](Mat matrix){state->refresh(matrix);});
}

bool query_rcr_port_pc_stats(PC pc,RcrPortPcStats& stats) {
    auto* handle=get_handle(pc);
    if(!handle) return false;
    stats=(*handle)->stats; return true;
}
KSP rcr_port_bulk_solver(PC pc) {
    auto* handle=get_handle(pc);
    return handle?(*handle)->bulk.get():nullptr;
}
} // namespace eonsim
