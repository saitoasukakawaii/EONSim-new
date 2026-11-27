#include "eonsim/interface_patch_pc.hpp"
#include "eonsim/native_float_sparse.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <tuple>

namespace eonsim {
namespace {
constexpr const char* shell_name="EONSim mixed FSI interface patches";
void common_check(MPI_Comm comm,bool valid,const std::string& message) {
    int bad=!valid,any=0;
    if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
        throw std::runtime_error("Interface patch validation communication failed");
    if(any) throw std::runtime_error("Interface patch PC: "+message);
}
struct IndexSets {
    std::vector<IS> values;
    void clear() {
        for(auto& value:values) if(value) (void)ISDestroy(&value);
        std::vector<IS>().swap(values);
    }
    ~IndexSets() { clear(); }
    void append(const std::vector<PetscInt>& rows) {
        IS value=nullptr;
        EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(rows.size()),
                                   rows.data(),PETSC_COPY_VALUES,&value));
        values.push_back(value);
    }
};

// Small dense patch factors do not change PETSc's real-double ABI. Equilibrate
// both rows and columns before deciding whether FP32 is safe. Never regularize
// a singular mixed patch: the caller needs to change its patch/solver choice.
struct Patch {
    Mat matrix=nullptr; // Borrowed from PatchState's sequential submatrix array.
    PetscInt n=0;
    bool factor_ready=false;
    std::vector<PetscInt> union_offsets,pivots;
    std::vector<double> rows,columns,double_lu,solution,defect,correction;
    std::vector<float> single_lu,single_work,single_matrix;
    // A nonempty offset array identifies compact native coefficients. These
    // are local patch indices, never global PETSc row/column identifiers.
    std::vector<std::uint32_t> single_offsets;
    std::vector<std::uint16_t> single_columns;
    std::vector<double> double_work;

    template<class T> bool factor_values(std::vector<T>& lu,const std::vector<double>& values) {
        lu.assign(values.begin(),values.end());
        const double tolerance=8.*std::numeric_limits<T>::epsilon()*std::max<PetscInt>(1,n);
        for(PetscInt k=0;k<n;++k) {
            PetscInt pivot=k;
            for(PetscInt i=k+1;i<n;++i)
                if(std::abs(lu[static_cast<std::size_t>(i)*n+k])>
                   std::abs(lu[static_cast<std::size_t>(pivot)*n+k])) pivot=i;
            const auto value=lu[static_cast<std::size_t>(pivot)*n+k];
            if(!std::isfinite(value)||std::abs(value)<=tolerance) return false;
            pivots[k]=pivot;
            if(pivot!=k) for(PetscInt j=0;j<n;++j)
                std::swap(lu[static_cast<std::size_t>(k)*n+j],lu[static_cast<std::size_t>(pivot)*n+j]);
            for(PetscInt i=k+1;i<n;++i) {
                auto& multiplier=lu[static_cast<std::size_t>(i)*n+k];
                multiplier/=lu[static_cast<std::size_t>(k)*n+k];
                for(PetscInt j=k+1;j<n;++j)
                    lu[static_cast<std::size_t>(i)*n+j]-=multiplier*lu[static_cast<std::size_t>(k)*n+j];
            }
        }
        return std::all_of(lu.begin(),lu.end(),[](T value){return std::isfinite(value);});
    }
    std::vector<double> scaled_matrix() {
        if(!matrix) {
            if(single_offsets.empty()) return std::vector<double>(single_matrix.begin(),single_matrix.end());
            std::vector<double> values(static_cast<std::size_t>(n)*n,0.);
            for(PetscInt row=0;row<n;++row)
                for(auto index=single_offsets[row];index<single_offsets[row+1];++index)
                    values[static_cast<std::size_t>(row)*n+single_columns[index]]=single_matrix[index];
            return values;
        }
        std::vector<double> values(static_cast<std::size_t>(n)*n,0.);
        for(PetscInt row=0;row<n;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j)
                values[static_cast<std::size_t>(row)*n+indices[j]]=(entries[j]/rows[row])/columns[indices[j]];
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        return values;
    }
    void retain_native_coefficients() {
        // Count exactly the FP32 coefficients that the former dense action
        // retained. Quantized zeros need no slot. Read sparse rows directly:
        // no n*n FP64 staging matrix coexists with the native coefficients.
        std::size_t nonzeros=0;
        for(PetscInt row=0;row<n;++row) {
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j) {
                const auto value=static_cast<float>((entries[j]/rows[row])/columns[indices[j]]);
                if(value!=0.f) ++nonzeros;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        const auto width=static_cast<std::size_t>(n);
        const auto dense_values=width*width;
        // Bounds are checked before narrowing; a wider patch simply keeps its
        // dense representation. Options currently cap n at 2048, but storage
        // correctness does not depend on that separate validation contract.
        const bool bounded=n>=0&&width<=std::numeric_limits<std::uint16_t>::max()&&
            nonzeros<=std::numeric_limits<std::uint32_t>::max();
        const auto sparse_bytes=nonzeros*(sizeof(float)+sizeof(std::uint16_t))+
            (width+1)*sizeof(std::uint32_t);
        const bool sparse=bounded&&sparse_bytes<dense_values*sizeof(float);
        single_matrix.assign(sparse?nonzeros:dense_values,0.f);
        if(sparse) {single_offsets.resize(width+1);single_columns.resize(nonzeros);}
        else {
            std::vector<std::uint32_t>().swap(single_offsets);
            std::vector<std::uint16_t>().swap(single_columns);
        }
        std::size_t position=0;
        for(PetscInt row=0;row<n;++row) {
            if(sparse) single_offsets[row]=static_cast<std::uint32_t>(position);
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j) {
                const auto value=static_cast<float>((entries[j]/rows[row])/columns[indices[j]]);
                if(sparse) {
                    if(value==0.f) continue;
                    single_matrix[position]=value;
                    single_columns[position]=static_cast<std::uint16_t>(indices[j]);
                    ++position;
                } else single_matrix[static_cast<std::size_t>(row)*width+indices[j]]=value;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        if(sparse) single_offsets[width]=static_cast<std::uint32_t>(position);
        // Native failures never fall back to a double local solve.
        std::vector<double>().swap(double_work);
    }
    bool prepare_factor() {
        factor_ready=false;
        EONSIM_PETSC(MatGetSize(matrix,&n,nullptr));
        rows.assign(n,0.); columns.assign(n,0.); pivots.resize(n);
        solution.resize(n); defect.resize(n); correction.resize(n); double_work.resize(n); single_work.resize(n);
        bool finite=true;
        for(PetscInt row=0;row<n;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j) {
                finite=finite&&std::isfinite(entries[j]);
                rows[row]=std::max(rows[row],std::abs(entries[j]));
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
            finite=finite&&rows[row]>0;
        }
        if(!finite) return false;
        for(PetscInt row=0;row<n;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j)
                columns[indices[j]]=std::max(columns[indices[j]],std::abs(entries[j]/rows[row]));
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        return std::all_of(columns.begin(),columns.end(),[](double x){return x>0&&std::isfinite(x);});
    }
    // Keep the previous sparse values only during a refresh, before PETSc
    // overwrites its reusable submatrix. Exact comparison permits factor reuse
    // without a collision-prone hash or a persistent second dense matrix.
    std::vector<double> numeric_snapshot() const {
        std::vector<double> values;
        for(PetscInt row=0;row<n;++row) {
            PetscInt count=0; const PetscInt* columns_ptr=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&columns_ptr,&entries));
            if(count) values.insert(values.end(),entries,entries+count);
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&columns_ptr,&entries));
        }
        return values;
    }
    void copy_factor(const Patch& other) {
        n=other.n; rows=other.rows; columns=other.columns; pivots=other.pivots;
        double_lu=other.double_lu; single_lu=other.single_lu;
        single_matrix=other.single_matrix;
        single_offsets=other.single_offsets;single_columns=other.single_columns;
        factor_ready=other.factor_ready;
        solution.resize(n); defect.resize(n); correction.resize(n); double_work.resize(n); single_work.resize(n);
    }
    template<class T> bool solve_values(const std::vector<T>& lu,std::vector<T>& work,
                                       const double* rhs,std::vector<double>& result) {
        long double scale=0;
        for(PetscInt i=0;i<n;++i) {
            if(!std::isfinite(rhs[i])) return false;
            scale=std::max(scale,std::abs(static_cast<long double>(rhs[i])/rows[i]));
        }
        if(scale==0) { std::fill(result.begin(),result.end(),0.); return true; }
        if(!std::isfinite(scale)) return false;
        for(PetscInt i=0;i<n;++i) work[i]=static_cast<T>((static_cast<long double>(rhs[i])/rows[i])/scale);
        // Later pivot swaps also move the stored L columns. Apply the complete
        // row permutation before forward substitution.
        for(PetscInt k=0;k<n;++k) if(pivots[k]!=k) std::swap(work[k],work[pivots[k]]);
        for(PetscInt i=0;i<n;++i)
            for(PetscInt j=0;j<i;++j) work[i]-=lu[static_cast<std::size_t>(i)*n+j]*work[j];
        for(PetscInt i=n;i-->0;) {
            for(PetscInt j=i+1;j<n;++j) work[i]-=lu[static_cast<std::size_t>(i)*n+j]*work[j];
            work[i]/=lu[static_cast<std::size_t>(i)*n+i];
        }
        bool valid=true;
        for(PetscInt i=0;i<n;++i) {
            result[i]=static_cast<double>((static_cast<long double>(work[i])*scale)/columns[i]);
            valid=valid&&std::isfinite(result[i]);
        }
        return valid;
    }
    bool residual(const double* rhs,double tolerance) {
        bool accepted=true;
        for(PetscInt row=0;row<n;++row) {
            if(!matrix) {
                // Native storage retains the equilibrated FP32 coefficients.
                // Refinement solves this approximate local action accurately;
                // the outer physical operator and acceptance remain FP64.
                long double value=static_cast<long double>(rhs[row])/rows[row];
                long double denominator=std::abs(value);
                if(single_offsets.empty()) {
                    for(PetscInt column=0;column<n;++column) {
                        const long double product=static_cast<long double>(single_matrix[static_cast<std::size_t>(row)*n+column])*
                            columns[column]*solution[column];
                        value-=product; denominator+=std::abs(product);
                    }
                } else {
                    for(auto index=single_offsets[row];index<single_offsets[row+1];++index) {
                        const auto column=single_columns[index];
                        const long double product=static_cast<long double>(single_matrix[index])*
                            columns[column]*solution[column];
                        value-=product; denominator+=std::abs(product);
                    }
                }
                defect[row]=static_cast<double>(value*rows[row]);
                accepted=accepted&&std::isfinite(defect[row])&&std::isfinite(denominator)&&
                    std::abs(value)<=static_cast<long double>(tolerance)*denominator;
                continue;
            }
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            long double value=rhs[row],denominator=std::abs(static_cast<long double>(rhs[row]));
            for(PetscInt j=0;j<count;++j) {
                const long double product=static_cast<long double>(entries[j])*solution[indices[j]];
                value-=product; denominator+=std::abs(product);
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
            defect[row]=static_cast<double>(value);
            accepted=accepted&&std::isfinite(defect[row])&&std::isfinite(denominator)&&
                std::abs(value)<=static_cast<long double>(tolerance)*denominator;
        }
        return accepted;
    }
    bool solve(const double* rhs,const InterfacePatchOptions& options,
               InterfacePatchPcStats& stats) {
        if(single_lu.empty()) {
            return solve_values(double_lu,double_work,rhs,solution)&&residual(rhs,options.refinement_tolerance);
        }
        bool valid=solve_values(single_lu,single_work,rhs,solution);
        for(PetscInt step=0;valid&&step<=options.refinement_steps;++step) {
            if(residual(rhs,options.refinement_tolerance)) return true;
            if(step==options.refinement_steps) break;
            valid=solve_values(single_lu,single_work,defect.data(),correction);
            ++stats.refinements;
            for(PetscInt i=0;i<n;++i) solution[i]+=correction[i];
        }
        // A native level never allocates a hidden FP64 fallback factor. Failure
        // is propagated through the PC protocol after all scatters complete.
        if(options.native_storage) return false;
        const auto values=scaled_matrix();
        if(!factor_values(double_lu,values)) {factor_ready=false;return false;}
        stats.factor_bytes+=double_lu.size()*sizeof(double)-single_lu.size()*sizeof(float);
        std::vector<float>().swap(single_lu);
        ++stats.apply_fallbacks; --stats.fp32_patches; ++stats.fp64_patches;
        return solve_values(double_lu,double_work,rhs,solution)&&residual(rhs,options.refinement_tolerance);
    }
};

// Equal-size patches are factored in short AoSoA batches. Every lane chooses
// its own row pivots; only independent trailing updates share SIMD loops.
// There is no threading or PETSc access inside the arithmetic batch.
template<class T>
std::vector<unsigned char> factor_batch_values(const std::vector<Patch*>& patches,
                                               const std::vector<std::vector<double>>& values) {
    const auto lanes=patches.size();
    const PetscInt n=patches.front()->n;
    std::vector<T> packed(static_cast<std::size_t>(n)*n*lanes);
    std::vector<unsigned char> good(lanes,1);
    for(std::size_t slot=0;slot<static_cast<std::size_t>(n)*n;++slot)
        for(std::size_t lane=0;lane<lanes;++lane) packed[slot*lanes+lane]=static_cast<T>(values[lane][slot]);
    const double tolerance=8.*std::numeric_limits<T>::epsilon()*std::max<PetscInt>(1,n);
    for(PetscInt k=0;k<n;++k) {
        for(std::size_t lane=0;lane<lanes;++lane) if(good[lane]) {
            PetscInt pivot=k;
            for(PetscInt i=k+1;i<n;++i)
                if(std::abs(packed[(static_cast<std::size_t>(i)*n+k)*lanes+lane])>
                   std::abs(packed[(static_cast<std::size_t>(pivot)*n+k)*lanes+lane])) pivot=i;
            const auto value=packed[(static_cast<std::size_t>(pivot)*n+k)*lanes+lane];
            if(!std::isfinite(value)||std::abs(value)<=tolerance) {good[lane]=0;continue;}
            patches[lane]->pivots[k]=pivot;
            if(pivot!=k) for(PetscInt j=0;j<n;++j)
                std::swap(packed[(static_cast<std::size_t>(k)*n+j)*lanes+lane],
                          packed[(static_cast<std::size_t>(pivot)*n+j)*lanes+lane]);
        }
        for(PetscInt i=k+1;i<n;++i) {
            for(std::size_t lane=0;lane<lanes;++lane) if(good[lane])
                packed[(static_cast<std::size_t>(i)*n+k)*lanes+lane]/=
                    packed[(static_cast<std::size_t>(k)*n+k)*lanes+lane];
            for(PetscInt j=k+1;j<n;++j) {
#if defined(_OPENMP)
#pragma omp simd
#endif
                for(std::size_t lane=0;lane<lanes;++lane) if(good[lane])
                    packed[(static_cast<std::size_t>(i)*n+j)*lanes+lane]-=
                        packed[(static_cast<std::size_t>(i)*n+k)*lanes+lane]*
                        packed[(static_cast<std::size_t>(k)*n+j)*lanes+lane];
            }
        }
    }
    for(std::size_t lane=0;lane<lanes;++lane) {
        auto& lu=[&]() -> std::vector<T>& {
            if constexpr(std::is_same<T,float>::value) return patches[lane]->single_lu;
            else return patches[lane]->double_lu;
        }();
        lu.resize(static_cast<std::size_t>(n)*n);
        for(std::size_t slot=0;slot<lu.size();++slot) {
            lu[slot]=packed[slot*lanes+lane];
            good[lane]=good[lane]&&std::isfinite(lu[slot]);
        }
    }
    return good;
}
bool factor_patch_batch(const std::vector<Patch*>& patches,bool single,InterfacePatchPcStats& stats) {
    bool valid=true;
    std::vector<std::vector<double>> values;
    for(auto* patch:patches) {
        valid=patch->prepare_factor()&&valid;
        if(valid) values.push_back(patch->scaled_matrix());
    }
    if(!valid) return false;
    auto good=single?factor_batch_values<float>(patches,values):factor_batch_values<double>(patches,values);
    ++stats.factor_batches; stats.numeric_factorizations+=static_cast<PetscInt>(patches.size());
    for(std::size_t lane=0;lane<patches.size();++lane) {
        auto& patch=*patches[lane];
        if(single&&good[lane]) std::vector<double>().swap(patch.double_lu);
        else if(single) {
            ++stats.setup_fallbacks;
            std::vector<float>().swap(patch.single_lu);
            good[lane]=patch.factor_values(patch.double_lu,values[lane]);
        } else std::vector<float>().swap(patch.single_lu);
        patch.factor_ready=good[lane];
        valid=valid&&good[lane];
    }
    return valid;
}

struct PatchState {
    MPI_Comm comm;
    Mat source=nullptr; // The parent KSP owns J; it remains the exact current operator.
    PC owner=nullptr;
    PetscObjectState graph=0;
    PetscInt begin=0,end=0,global=0;
    bool ready=false,submatrices_ready=false,bulk_configured=false,level_mode=false;
    PetscBool report=PETSC_FALSE;
    InterfacePatchOptions options;
    std::vector<unsigned char> active_owned;
    std::vector<DofKey> semantics;
    IndexSets indices;
    Mat* submatrices=nullptr;
    std::vector<Patch> patches;
    std::vector<PetscInt> patch_colors;
    std::vector<double> inverse_multiplicity,patch_rhs;
    PcSchurUpdates bulk_updates; // Must outlive the KSP retaining USER matrices.
    PetscOwner<KSP,KSPDestroy> bulk;
    PetscOwner<Vec,VecDestroy> residual_vector,union_rhs,union_correction;
    PetscOwner<VecScatter,VecScatterDestroy> scatter;
    std::function<void(KSP,Mat,PcSchurUpdates*)> configure;
    InterfacePatchPcStats stats;
    NativeFloatSparse native_residual;
    bool released=false;

    ~PatchState() {
        if(submatrices) (void)MatDestroySubMatrices(static_cast<PetscInt>(indices.values.size()),&submatrices);
    }
    std::vector<unsigned char> active_rows(Mat full) const {
        std::vector<unsigned char> result(end-begin,0);
        bool valid=true;
        for(PetscInt row=begin;row<end;++row) {
            PetscInt count=0; const PetscInt* columns=nullptr; const PetscScalar* values=nullptr;
            EONSIM_PETSC(MatGetRow(full,row,&count,&columns,&values));
            bool identity=true,diagonal=false;
            for(PetscInt j=0;j<count;++j) {
                valid=valid&&std::isfinite(values[j]);
                if(columns[j]==row) { diagonal=true; identity=identity&&values[j]==1.; }
                else identity=identity&&values[j]==0.;
            }
            EONSIM_PETSC(MatRestoreRow(full,row,&count,&columns,&values));
            result[row-begin]=(level_mode||semantics[row-begin].kind!=DofEntity::boundary)&&!(identity&&diagonal);
        }
        common_check(comm,valid,"nonfinite source Jacobian");
        return result;
    }
    void prepare_schedule(const std::vector<PetscInt>& union_rows,PetscInt total) {
        const auto local=static_cast<PetscInt>(patches.size());
        patch_colors.assign(patches.size(),0);
        if(options.sweep=="additive"||total==0) return;
        PetscInt offset=0;
        int rank=0;EONSIM_PETSC(MPI_Comm_rank(comm,&rank));
        EONSIM_PETSC(MPI_Exscan(&local,&offset,1,MPIU_INT,MPI_SUM,comm));
        if(rank==0) offset=0;
        if(options.sweep=="multiplicative") {
            std::iota(patch_colors.begin(),patch_colors.end(),offset);
            stats.colors=total;
            return;
        }
        // R maps patch amplitudes to their participating rows. R^T R is the
        // exact shared-row conflict graph, including off-rank patch overlap.
        // Its row ownership is the patch seed ownership, not a gathered graph.
        PetscOwner<Mat,MatDestroy> incidence,conflicts;
        EONSIM_PETSC(MatCreateAIJ(comm,end-begin,local,global,total,0,nullptr,0,nullptr,incidence.put()));
        EONSIM_PETSC(MatSetOption(incidence.get(),MAT_NEW_NONZERO_ALLOCATION_ERR,PETSC_FALSE));
        for(PetscInt p=0;p<local;++p) for(auto row_offset:patches[p].union_offsets)
            EONSIM_PETSC(MatSetValue(incidence.get(),union_rows[row_offset],offset+p,1.,INSERT_VALUES));
        EONSIM_PETSC(MatAssemblyBegin(incidence.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatAssemblyEnd(incidence.get(),MAT_FINAL_ASSEMBLY));
        EONSIM_PETSC(MatTransposeMatMult(incidence.get(),incidence.get(),MAT_INITIAL_MATRIX,PETSC_DEFAULT,conflicts.put()));
        PetscOwner<MatColoring,MatColoringDestroy> coloring;
        PetscOwner<ISColoring,ISColoringDestroy> schedule;
        EONSIM_PETSC(MatColoringCreate(conflicts.get(),coloring.put()));
        EONSIM_PETSC(MatColoringSetType(coloring.get(),MATCOLORINGGREEDY));
        EONSIM_PETSC(MatColoringSetDistance(coloring.get(),1));
        EONSIM_PETSC(MatColoringApply(coloring.get(),schedule.put()));
        PetscInt count=0,colors=0;
        const ISColoringValue* values=nullptr;
        EONSIM_PETSC(ISColoringGetColors(schedule.get(),&count,&colors,&values));
        common_check(comm,count==local,"distributed coloring changed patch ownership");
        for(PetscInt p=0;p<local;++p) patch_colors[p]=static_cast<PetscInt>(values[p]);
        EONSIM_PETSC(MPI_Allreduce(&colors,&stats.colors,1,MPIU_INT,MPI_MAX,comm));
        common_check(comm,stats.colors>0&&std::all_of(patch_colors.begin(),patch_colors.end(),
            [&](PetscInt color){return color>=0&&color<stats.colors;}),"invalid distributed patch color");
    }
    PatchState(MPI_Comm communicator,Mat full,const std::vector<DofKey>& keys,
               const std::vector<unsigned char>& trace,const InterfacePatchOptions& selected,
               const std::string& prefix,
               const std::function<void(KSP,Mat,PcSchurUpdates*)>& callback,bool pure_level=false):
        comm(communicator),source(full),level_mode(pure_level),options(selected),semantics(keys),configure(callback) {
        PetscInt n=0,cbegin=0,cend=0;
        EONSIM_PETSC(MatGetSize(full,&global,&n));
        EONSIM_PETSC(MatGetOwnershipRange(full,&begin,&end));
        EONSIM_PETSC(MatGetOwnershipRangeColumn(full,&cbegin,&cend));
        common_check(comm,global==n&&global>0&&begin==cbegin&&end==cend&&
            static_cast<PetscInt>(keys.size())==end-begin&&trace.size()==keys.size()&&
            std::all_of(trace.begin(),trace.end(),[](unsigned char value){return value<=1;}),
            "metadata must follow matching owned row/column ordering");
        common_check(comm,(!options.adaptive&&!options.native_storage)||level_mode,
                     "adaptive/native storage options require a pure Vanka level");
        common_check(comm,level_mode||options.sweep=="additive",
                     "multiplicative/colored sweeps require a pure Vanka level");
        EONSIM_PETSC(MatGetNonzeroState(full,&graph));
        stats.overlap=options.overlap;
        active_owned=active_rows(full);
        using Center=std::tuple<std::int64_t,DofEntity,std::uint16_t,std::uint16_t>;
        std::map<Center,std::vector<PetscInt>> centers;
        std::map<Center,bool> interface_centers;
        for(PetscInt i=0;i<end-begin;++i) if(active_owned[i]&&
            (level_mode||(trace[i]&&keys[i].kind==DofEntity::vertex))) {
            const auto& k=keys[i];
            centers[{k.entity,k.kind,k.mode,k.space}].push_back(begin+i);
            interface_centers[{k.entity,k.kind,k.mode,k.space}]=
                interface_centers[{k.entity,k.kind,k.mode,k.space}]||trace[i];
        }
        std::vector<unsigned char> expand;
        for(const auto& center:centers) {
            indices.append(center.second);
            if(interface_centers[center.first]) ++stats.interface_patches;
            bool selected=!options.adaptive||interface_centers[center.first];
            if(options.adaptive&&!selected) for(auto row:center.second) {
                PetscInt count=0;const PetscInt* columns=nullptr;const PetscScalar* values=nullptr;
                EONSIM_PETSC(MatGetRow(full,row,&count,&columns,&values));
                long double external=0,total=0;
                for(PetscInt j=0;j<count;++j) {
                    const auto value=std::abs(static_cast<long double>(values[j]));
                    total+=value;
                    if(!std::binary_search(center.second.begin(),center.second.end(),columns[j])) external+=value;
                }
                EONSIM_PETSC(MatRestoreRow(full,row,&count,&columns,&values));
                selected=selected||(total>0&&external>=options.strength_threshold*total);
            }
            expand.push_back(selected&&options.overlap>0);
            if(expand.back()) ++stats.expanded_patches; else ++stats.core_patches;
        }
        PetscInt local=static_cast<PetscInt>(indices.values.size()),total=0;
        MPI_Allreduce(&local,&total,1,MPIU_INT,MPI_SUM,comm);
        common_check(comm,level_mode||total>0,"no active interface vertices were supplied");
        if(options.overlap&&total>0) {
            // MatIncreaseOverlap's domain count is logically collective; in
            // PETSc 3.23.7 n==0 returns before MPIAIJ overlap communication.
            // Pad only the setup call with empty sets, so ranks without trace
            // vertices still participate and uneven patch counts are valid.
            // Empty padding never becomes a numerical patch or an unknown.
            IndexSets selected;
            std::vector<PetscInt> selected_positions;
            PetscInt position=0;
            for(const auto& center:centers) {
                if(expand[position]) {selected.append(center.second);selected_positions.push_back(position);}
                ++position;
            }
            const PetscInt selected_local=static_cast<PetscInt>(selected_positions.size());
            PetscInt maximum=0;
            EONSIM_PETSC(MPI_Allreduce(&selected_local,&maximum,1,MPIU_INT,MPI_MAX,comm));
            if(maximum>0) {
                while(static_cast<PetscInt>(selected.values.size())<maximum) selected.append({});
                EONSIM_PETSC(MatIncreaseOverlap(full,maximum,selected.values.data(),options.overlap));
                for(PetscInt i=0;i<selected_local;++i) {
                    EONSIM_PETSC(ISDestroy(&indices.values[selected_positions[i]]));
                    indices.values[selected_positions[i]]=selected.values[i];selected.values[i]=nullptr;
                }
            }
        }
        std::vector<PetscInt> union_rows;
        for(auto is:indices.values) {
            PetscInt size=0; const PetscInt* rows=nullptr;
            EONSIM_PETSC(ISGetLocalSize(is,&size)); EONSIM_PETSC(ISGetIndices(is,&rows));
            union_rows.insert(union_rows.end(),rows,rows+size);
            EONSIM_PETSC(ISRestoreIndices(is,&rows));
        }
        std::sort(union_rows.begin(),union_rows.end());
        union_rows.erase(std::unique(union_rows.begin(),union_rows.end()),union_rows.end());
        EONSIM_PETSC(MatCreateVecs(full,residual_vector.put(),nullptr));
        EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(union_rows.size()),union_rhs.put()));
        EONSIM_PETSC(VecDuplicate(union_rhs.get(),union_correction.put()));
        PetscOwner<IS,ISDestroy> union_is;
        EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(union_rows.size()),
                                   union_rows.data(),PETSC_COPY_VALUES,union_is.put()));
        EONSIM_PETSC(VecScatterCreate(residual_vector.get(),union_is.get(),union_rhs.get(),nullptr,scatter.put()));
        PetscScalar* owned=nullptr;
        EONSIM_PETSC(VecGetArray(residual_vector.get(),&owned));
        for(PetscInt i=0;i<end-begin;++i) owned[i]=active_owned[i];
        EONSIM_PETSC(VecRestoreArray(residual_vector.get(),&owned));
        EONSIM_PETSC(VecScatterBegin(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
        const PetscScalar* allowed=nullptr;
        EONSIM_PETSC(VecGetArrayRead(union_rhs.get(),&allowed));
        bool bounded=true;
        for(auto& is:indices.values) {
            PetscInt size=0; const PetscInt* rows=nullptr;
            EONSIM_PETSC(ISGetLocalSize(is,&size)); EONSIM_PETSC(ISGetIndices(is,&rows));
            std::vector<PetscInt> selected_rows;
            Patch patch;
            for(PetscInt j=0;j<size;++j) {
                const auto offset=std::lower_bound(union_rows.begin(),union_rows.end(),rows[j])-union_rows.begin();
                if(allowed[offset]!=0.) selected_rows.push_back(rows[j]);
            }
            EONSIM_PETSC(ISRestoreIndices(is,&rows));
            std::sort(selected_rows.begin(),selected_rows.end());
            for(auto row:selected_rows) patch.union_offsets.push_back(static_cast<PetscInt>(
                std::lower_bound(union_rows.begin(),union_rows.end(),row)-union_rows.begin()));
            bounded=bounded&&!selected_rows.empty()&&static_cast<PetscInt>(selected_rows.size())<=options.maximum_size;
            stats.largest_patch=std::max(stats.largest_patch,static_cast<PetscInt>(selected_rows.size()));
            stats.patch_rows+=static_cast<PetscInt>(selected_rows.size());
            EONSIM_PETSC(ISDestroy(&is));
            EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(selected_rows.size()),
                                       selected_rows.data(),PETSC_COPY_VALUES,&is));
            patches.push_back(std::move(patch));
        }
        EONSIM_PETSC(VecRestoreArrayRead(union_rhs.get(),&allowed));
        common_check(comm,bounded,"an interface patch is empty or exceeds the maximum size; no rows were truncated");
        stats.patches=local;
        prepare_schedule(union_rows,total);
        patch_rhs.resize(stats.largest_patch);
        EONSIM_PETSC(VecSet(union_correction.get(),0.));
        PetscScalar* counts=nullptr;
        EONSIM_PETSC(VecGetArray(union_correction.get(),&counts));
        for(const auto& patch:patches) for(auto offset:patch.union_offsets) counts[offset]+=1.;
        EONSIM_PETSC(VecRestoreArray(union_correction.get(),&counts));
        EONSIM_PETSC(VecSet(residual_vector.get(),0.));
        EONSIM_PETSC(VecScatterBegin(scatter.get(),union_correction.get(),residual_vector.get(),ADD_VALUES,SCATTER_REVERSE));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),union_correction.get(),residual_vector.get(),ADD_VALUES,SCATTER_REVERSE));
        const PetscScalar* owned_counts=nullptr;
        EONSIM_PETSC(VecGetArrayRead(residual_vector.get(),&owned_counts));
        bool complete=true;
        for(PetscInt i=0;i<end-begin;++i) if(active_owned[i]) {
            if(owned_counts[i]>0.) ++stats.covered_owned_rows;
            else complete=false;
        }
        EONSIM_PETSC(VecRestoreArrayRead(residual_vector.get(),&owned_counts));
        common_check(comm,!level_mode||complete,"level patches must cover every active owned row");
        EONSIM_PETSC(VecScatterBegin(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecScatterEnd(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
        EONSIM_PETSC(VecGetArrayRead(union_rhs.get(),&allowed));
        inverse_multiplicity.resize(union_rows.size());
        for(std::size_t i=0;i<union_rows.size();++i) inverse_multiplicity[i]=allowed[i]>0?1./allowed[i]:0.;
        EONSIM_PETSC(VecRestoreArrayRead(union_rhs.get(),&allowed));
        if(!level_mode) {
            EONSIM_PETSC(KSPCreate(comm,bulk.put()));
            EONSIM_PETSC(KSPSetOptionsPrefix(bulk.get(),prefix.c_str()));
            EONSIM_PETSC(KSPSetType(bulk.get(),KSPPREONLY));
        }
        EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-pc_plan_report",&report,nullptr));
    }
    void refresh(Mat full) {
        ready=false;
        common_check(comm,!released,"released native Vanka setup requires rebuilding the level");
        PetscObjectState current_graph=0; EONSIM_PETSC(MatGetNonzeroState(full,&current_graph));
        common_check(comm,full==source&&current_graph==graph,"source matrix identity/graph changed; rebuild the PC");
        common_check(comm,active_rows(full)==active_owned,"identity constraints changed; rebuild the interface patches");
        const bool first=!submatrices_ready;
        std::vector<std::vector<double>> previous_values(patches.size());
        if(!first) for(std::size_t i=0;i<patches.size();++i)
            previous_values[i]=patches[i].numeric_snapshot();
        EONSIM_PETSC(MatCreateSubMatrices(full,static_cast<PetscInt>(indices.values.size()),indices.values.data(),
            indices.values.data(),first?MAT_INITIAL_MATRIX:MAT_REUSE_MATRIX,&submatrices));
        submatrices_ready=true;
        bool valid=true;
        stats.fp32_patches=stats.fp64_patches=0; stats.factor_bytes=0;
        stats.retained_fp64_matrix_bytes=0;
        std::map<PetscInt,std::vector<Patch*>> pending;
        std::map<std::vector<PetscInt>,std::size_t> representatives;
        std::vector<std::pair<std::size_t,std::size_t>> duplicates;
        for(std::size_t i=0;i<patches.size();++i) {
            auto& patch=patches[i]; patch.matrix=submatrices[i];
            MatInfo storage{};EONSIM_PETSC(MatGetInfo(patch.matrix,MAT_LOCAL,&storage));
            stats.retained_fp64_matrix_bytes+=static_cast<std::size_t>(storage.nz_allocated)*sizeof(PetscScalar);
            EONSIM_PETSC(MatGetSize(patch.matrix,&patch.n,nullptr));
            const auto representative=representatives.emplace(patch.union_offsets,i);
            if(!first&&patch.factor_ready&&previous_values[i]==patch.numeric_snapshot()) ++stats.cached_factorizations;
            else if(!representative.second) {
                duplicates.emplace_back(i,representative.first->second);
                ++stats.cached_factorizations;
            } else pending[patch.n].push_back(&patch);
        }
        for(const auto& size_group:pending) {
            // Bound transient AoSoA storage even when a user deliberately
            // requests a much larger patch than the usual small blocks.
            const auto entries=static_cast<std::size_t>(size_group.first)*size_group.first;
            const auto width=std::max<std::size_t>(1,std::min<std::size_t>(8,262144/entries));
            for(std::size_t start=0;start<size_group.second.size();start+=width) {
                const auto end_index=std::min(start+width,size_group.second.size());
                const std::vector<Patch*> batch(size_group.second.begin()+start,size_group.second.begin()+end_index);
                valid=factor_patch_batch(batch,options.single_precision,stats)&&valid;
            }
        }
        for(const auto& duplicate:duplicates) patches[duplicate.first].copy_factor(patches[duplicate.second]);
        for(const auto& patch:patches) {
            if(patch.single_lu.empty()) ++stats.fp64_patches; else ++stats.fp32_patches;
            stats.factor_bytes+=patch.single_lu.size()*sizeof(float)+patch.double_lu.size()*sizeof(double);
        }
        if(options.native_storage) {
            // Setup fallback remains available for legacy mixed precision;
            // native storage explicitly requires representable FP32 factors.
            valid=valid&&stats.fp64_patches==0;
        }
        int bad=!valid,any=0;
        if(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm)!=MPI_SUCCESS)
            throw std::runtime_error("Interface patch factor failure reduction failed");
        if(any) throw LinearSolveFailure("Interface patch has a singular/nonfinite pivot (including after FP64 fallback)");
        if(!level_mode) {
          EONSIM_PETSC(KSPSetOperators(bulk.get(),full,full));
          if(!bulk_configured) {
            configure(bulk.get(),full,&bulk_updates);
            KSPType type=nullptr; PetscBool nonzero=PETSC_FALSE;
            EONSIM_PETSC(KSPGetType(bulk.get(),&type));
            EONSIM_PETSC(KSPGetInitialGuessNonzero(bulk.get(),&nonzero));
            common_check(comm,type&&std::strcmp(type,KSPPREONLY)==0&&!nonzero,
                         "bulk action requires PREONLY and a zero initial guess");
            EONSIM_PETSC(KSPSetErrorIfNotConverged(bulk.get(),PETSC_FALSE));
            bulk_configured=true;
          } else bulk_updates.refresh(full);
          EONSIM_PETSC(KSPSetReusePreconditioner(bulk.get(),PETSC_FALSE));
          EONSIM_PETSC(KSPSetUp(bulk.get()));
          // Numerical changes to J between refreshes must not trigger hidden
          // nested setup and defeat the caller's adaptive reuse decision.
          EONSIM_PETSC(KSPSetReusePreconditioner(bulk.get(),PETSC_TRUE));
        }
        if(owner) EONSIM_PETSC(PCSetFailedReason(owner,PC_NOERROR));
        ready=true; ++stats.rebuilds;
        if(report) {
            int rank=0; MPI_Comm_rank(comm,&rank);
            EONSIM_PETSC(PetscSynchronizedPrintf(comm,
                "interface_patch_pc rank=%d patches=%" PetscInt_FMT " largest=%" PetscInt_FMT
                " fp32=%" PetscInt_FMT " fp64=%" PetscInt_FMT " factor_bytes=%zu rebuilds=%" PetscInt_FMT
                " setup_fallbacks=%" PetscInt_FMT " apply_fallbacks=%" PetscInt_FMT " refinements=%" PetscInt_FMT
                " batches=%" PetscInt_FMT " factorizations=%" PetscInt_FMT " cached=%" PetscInt_FMT
                " interface=%" PetscInt_FMT " level=%d colors=%" PetscInt_FMT " sweep=%s\n",
                rank,stats.patches,stats.largest_patch,stats.fp32_patches,stats.fp64_patches,stats.factor_bytes,
                stats.rebuilds,stats.setup_fallbacks,stats.apply_fallbacks,stats.refinements,
                stats.factor_batches,stats.numeric_factorizations,stats.cached_factorizations,stats.interface_patches,level_mode?1:0,
                stats.colors,options.sweep.c_str()));
            EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
        }
    }
    void release_setup() {
        common_check(comm,level_mode&&options.native_storage&&options.single_precision&&ready&&!released,
                     "native setup release requires a ready FP32 Vanka level");
        int local_identity=std::any_of(active_owned.begin(),active_owned.end(),[](unsigned char x){return !x;});
        int any_identity=0;
        EONSIM_PETSC(MPI_Allreduce(&local_identity,&any_identity,1,MPI_INT,MPI_MAX,comm));
        if(options.sweep!="additive") native_residual.update(source,true);
        else if(any_identity) {
            PetscOwner<Vec,VecDestroy> mask;
            EONSIM_PETSC(MatCreateVecs(source,mask.put(),nullptr));
            PetscScalar* values=nullptr;EONSIM_PETSC(VecGetArray(mask.get(),&values));
            for(PetscInt i=0;i<end-begin;++i) values[i]=active_owned[i]?0.:1.;
            EONSIM_PETSC(VecRestoreArray(mask.get(),&values));
            native_residual.update(source,true,mask.get());
        }
        stats.fp32_matrix_bytes=native_residual.values.size()*sizeof(float);
        stats.native_sparse_patches=stats.native_dense_patches=0;
        stats.native_index_bytes=(native_residual.offsets.capacity()+native_residual.columns.capacity()+
            native_residual.slots.capacity())*sizeof(PetscInt);
        for(auto& patch:patches) {
            patch.retain_native_coefficients();
            stats.fp32_matrix_bytes+=patch.single_matrix.size()*sizeof(float);
            if(patch.single_offsets.empty()) ++stats.native_dense_patches;
            else ++stats.native_sparse_patches;
            stats.native_index_bytes+=patch.single_offsets.capacity()*sizeof(std::uint32_t)+
                patch.single_columns.capacity()*sizeof(std::uint16_t);
            patch.matrix=nullptr;
        }
        if(submatrices) EONSIM_PETSC(MatDestroySubMatrices(static_cast<PetscInt>(indices.values.size()),&submatrices));
        // Native numeric changes rebuild the level, so these setup-only copies
        // of the row sets and semantic metadata have no subsequent consumer.
        indices.clear();std::vector<DofKey>().swap(semantics);
        stats.retained_fp64_matrix_bytes=0;
        submatrices_ready=false;source=nullptr;released=true;
    }
    PetscErrorCode apply(PC pc,Vec input,Vec output) {
        PetscFunctionBeginUser;
        if(!ready) {
            PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR));
            PetscCall(VecSet(output,PETSC_INFINITY));
            PetscFunctionReturn(PETSC_SUCCESS);
        }
        bool valid=true;
        if(level_mode) {
            const PetscScalar* rhs=nullptr; PetscScalar* x=nullptr;
            PetscCall(VecGetArrayRead(input,&rhs)); PetscCall(VecGetArray(output,&x));
            for(PetscInt i=0;i<end-begin;++i) x[i]=active_owned[i]?0.:rhs[i];
            PetscCall(VecRestoreArray(output,&x)); PetscCall(VecRestoreArrayRead(input,&rhs));
        } else {
            const auto solve_error=KSPSolve(bulk.get(),input,output);
            KSPConvergedReason reason=KSP_CONVERGED_ITERATING;
            PC bulk_pc=nullptr; PCFailedReason failure=PC_NOERROR;
            PetscCall(KSPGetConvergedReason(bulk.get(),&reason)); PetscCall(KSPGetPC(bulk.get(),&bulk_pc));
            PetscCall(PCGetFailedReason(bulk_pc,&failure));
            valid=solve_error==PETSC_SUCCESS&&reason>0&&failure==PC_NOERROR;
        }
        for(PetscInt color=0;color<stats.colors;++color) {
            if(released) {
                if(native_residual.prepared) {
                    PetscCall(native_residual.multiply(output,residual_vector.get(),false));
                    ++stats.residual_products;
                } else PetscCall(VecSet(residual_vector.get(),0.));
            } else {PetscCall(MatMult(source,output,residual_vector.get()));++stats.residual_products;}
            PetscCall(VecAYPX(residual_vector.get(),-1.,input));
            PetscCall(VecScatterBegin(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
            PetscCall(VecScatterEnd(scatter.get(),residual_vector.get(),union_rhs.get(),INSERT_VALUES,SCATTER_FORWARD));
            const PetscScalar* rhs=nullptr; PetscScalar* correction=nullptr;
            PetscCall(VecGetArrayRead(union_rhs.get(),&rhs));
            PetscCall(VecGetArray(union_correction.get(),&correction));
            if(!inverse_multiplicity.empty()) std::fill(correction,correction+inverse_multiplicity.size(),0.);
            // Every rank completes every color/scatter even after a local
            // factor failure. No rank-local branch changes the MPI schedule.
            for(std::size_t p=0;p<patches.size();++p) if(patch_colors[p]==color) {
                auto& patch=patches[p];
                for(PetscInt i=0;i<patch.n;++i) patch_rhs[i]=rhs[patch.union_offsets[i]];
                bool solved=false;
                try { solved=patch.solve(patch_rhs.data(),options,stats); } catch(...) { solved=false; }
                valid=valid&&solved;
                if(solved) for(PetscInt i=0;i<patch.n;++i) {
                    const auto offset=patch.union_offsets[i];
                    const auto weight=options.sweep=="additive"?inverse_multiplicity[offset]:1.;
                    correction[offset]+=options.damping*weight*patch.solution[i];
                }
            }
            PetscCall(VecRestoreArray(union_correction.get(),&correction));
            PetscCall(VecRestoreArrayRead(union_rhs.get(),&rhs));
            PetscCall(VecScatterBegin(scatter.get(),union_correction.get(),output,ADD_VALUES,SCATTER_REVERSE));
            PetscCall(VecScatterEnd(scatter.get(),union_correction.get(),output,ADD_VALUES,SCATTER_REVERSE));
            ++stats.color_stages;
        }
        const PetscScalar* result=nullptr;
        PetscCall(VecGetArrayRead(output,&result));
        for(PetscInt i=0;i<end-begin;++i) valid=valid&&std::isfinite(result[i]);
        PetscCall(VecRestoreArrayRead(output,&result));
        ++stats.applications;
        if(!valid) { PetscCall(PCSetFailedReason(pc,PC_SUBPC_ERROR)); PetscCall(VecSet(output,PETSC_INFINITY)); }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};
using Handle=std::shared_ptr<PatchState>;
PetscErrorCode apply_patch(PC pc,Vec input,Vec output) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    PetscCall((*handle)->apply(pc,input,output));
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode destroy_patch(PC pc) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    if(handle) (*handle)->owner=nullptr;
    delete handle;
    PetscFunctionReturn(PETSC_SUCCESS);
}
PetscErrorCode view_patch(PC pc,PetscViewer viewer) {
    PetscFunctionBeginUser;
    Handle* handle=nullptr; PetscCall(PCShellGetContext(pc,&handle));
    PetscBool ascii=PETSC_FALSE;
    PetscCall(PetscObjectTypeCompare(reinterpret_cast<PetscObject>(viewer),PETSCVIEWERASCII,&ascii));
    if(ascii) {
        const auto& s=(*handle)->stats;
        PetscCall(PetscViewerASCIIPrintf(viewer,
            "Interface mixed patches: local=%" PetscInt_FMT ", largest=%" PetscInt_FMT
            ", FP32/FP64=%" PetscInt_FMT "/%" PetscInt_FMT ", LU bytes=%zu, generations=%" PetscInt_FMT
            ", applications=%" PetscInt_FMT ", refinements=%" PetscInt_FMT ", setup/apply fallback=%" PetscInt_FMT "/%" PetscInt_FMT
            ", colors=%" PetscInt_FMT ", color stages=%" PetscInt_FMT ", residual products=%" PetscInt_FMT "\n",
            s.patches,s.largest_patch,s.fp32_patches,s.fp64_patches,s.factor_bytes,s.rebuilds,
            s.applications,s.refinements,s.setup_fallbacks,s.apply_fallbacks,s.colors,s.color_stages,s.residual_products));
        PetscCall(PetscViewerASCIIPushTab(viewer));
        if((*handle)->bulk.get()) PetscCall(KSPView((*handle)->bulk.get(),viewer));
        PetscCall(PetscViewerASCIIPopTab(viewer));
    }
    PetscFunctionReturn(PETSC_SUCCESS);
}
Handle* get_handle(PC pc) {
    PCType type=nullptr; EONSIM_PETSC(PCGetType(pc,&type));
    if(!type||std::strcmp(type,PCSHELL)!=0) return nullptr;
    const char* name=nullptr; EONSIM_PETSC(PCShellGetName(pc,&name));
    if(!name||std::strcmp(name,shell_name)!=0) return nullptr;
    Handle* handle=nullptr; EONSIM_PETSC(PCShellGetContext(pc,&handle)); return handle;
}
} // namespace

void validate_interface_patch_options(MPI_Comm comm,const std::string& prefix,const InterfacePatchOptions& options,
                                      bool inspect_solver_options) {
    const PetscInt values[]={options.single_precision?1:0,options.overlap,options.maximum_size,options.refinement_steps,
        options.adaptive?1:0,options.native_storage?1:0,
        options.sweep=="additive"?1:options.sweep=="multiplicative"?2:options.sweep=="colored"?3:0};
    PetscInt minimum[7]{},maximum[7]{};
    MPI_Allreduce(values,minimum,7,MPIU_INT,MPI_MIN,comm);
    MPI_Allreduce(values,maximum,7,MPIU_INT,MPI_MAX,comm);
    bool valid=true;
    for(int i=0;i<7;++i) valid=valid&&minimum[i]==maximum[i];
    valid=valid&&options.overlap>=0&&options.overlap<=2&&options.maximum_size>=1&&options.maximum_size<=2048&&
        options.refinement_steps>=0&&options.refinement_steps<=8&&(!options.native_storage||options.single_precision)&&values[6]!=0;
    const double real[]={options.refinement_tolerance,options.damping,options.strength_threshold};
    double min_real[3]{},max_real[3]{};
    MPI_Allreduce(real,min_real,3,MPI_DOUBLE,MPI_MIN,comm);
    MPI_Allreduce(real,max_real,3,MPI_DOUBLE,MPI_MAX,comm);
    for(int i=0;i<3;++i) valid=valid&&std::isfinite(real[i])&&min_real[i]==max_real[i];
    valid=valid&&options.refinement_tolerance>=1e-14&&options.refinement_tolerance<=1e-4&&
        options.damping>0&&options.damping<=2&&options.strength_threshold>=0&&options.strength_threshold<=1;
    common_check(comm,valid,"options must be identical across ranks with overlap 0..2, size 1..2048, refinement 0..8, tolerance 1e-14..1e-4, damping (0,2]");
    if(!inspect_solver_options) return;
    char value[64]{}; PetscBool set=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+prefix+"pc_type").c_str(),value,sizeof(value),&set));
    common_check(comm,!set||std::strcmp(value,PCSHELL)==0,"interface correction requires a shell PC at "+prefix);
    EONSIM_PETSC(PetscOptionsGetString(nullptr,nullptr,("-"+prefix+"interface_bulk_ksp_type").c_str(),value,sizeof(value),&set));
    common_check(comm,!set||std::strcmp(value,KSPPREONLY)==0,"interface bulk action requires PREONLY at "+prefix);
}
void configure_interface_patch_pc(MPI_Comm comm,KSP solver,Mat full,
    const std::vector<DofKey>& owned_semantics,const std::vector<unsigned char>& owned_interface,
    const InterfacePatchOptions& options,
    const std::function<void(KSP,Mat,PcSchurUpdates*)>& configure_bulk,PcSchurUpdates* updates) {
    common_check(comm,updates&&static_cast<bool>(configure_bulk),"requires a live update registry and bulk callback");
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"";
    validate_interface_patch_options(comm,prefix,options);
    auto state=std::make_shared<PatchState>(comm,full,owned_semantics,owned_interface,options,prefix+"interface_bulk_",configure_bulk);
    state->refresh(full);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetOperators(solver,full,full)); EONSIM_PETSC(PCSetType(pc,PCSHELL));
    auto handle=std::make_unique<Handle>(state);
    EONSIM_PETSC(PCShellSetContext(pc,handle.get())); EONSIM_PETSC(PCShellSetDestroy(pc,destroy_patch));
    handle.release(); state->owner=pc;
    EONSIM_PETSC(PCShellSetName(pc,shell_name)); EONSIM_PETSC(PCShellSetApply(pc,apply_patch));
    EONSIM_PETSC(PCShellSetView(pc,view_patch));
    updates->refreshers.push_back([state](Mat matrix){state->refresh(matrix);});
}
bool query_interface_patch_pc_stats(PC pc,InterfacePatchPcStats& stats) {
    auto* handle=get_handle(pc); if(!handle) return false;
    stats=(*handle)->stats; return true;
}
KSP interface_patch_bulk_solver(PC pc) {
    auto* handle=get_handle(pc); return handle?(*handle)->bulk.get():nullptr;
}
void configure_vanka_level_pc(MPI_Comm comm,KSP solver,Mat full,
    const std::vector<DofKey>& owned_semantics,const std::vector<unsigned char>& owned_interface,
    const InterfacePatchOptions& options,PcSchurUpdates* updates) {
    common_check(comm,updates!=nullptr,"level Vanka requires a live numeric update registry");
    const char* prefix_ptr=nullptr; EONSIM_PETSC(KSPGetOptionsPrefix(solver,&prefix_ptr));
    const std::string prefix=prefix_ptr?prefix_ptr:"";
    // The enclosing hierarchy validated its own PETSc prefix. A level action
    // has typed controls and must not consume unrelated root -pc_type options.
    validate_interface_patch_options(comm,prefix,options,false);
    auto state=std::make_shared<PatchState>(comm,full,owned_semantics,owned_interface,options,prefix,
        std::function<void(KSP,Mat,PcSchurUpdates*)>{},true);
    state->refresh(full);
    PC pc=nullptr; EONSIM_PETSC(KSPGetPC(solver,&pc));
    EONSIM_PETSC(KSPSetOperators(solver,full,full)); EONSIM_PETSC(KSPSetType(solver,KSPPREONLY));
    EONSIM_PETSC(PCSetType(pc,PCSHELL));
    auto handle=std::make_unique<Handle>(state);
    EONSIM_PETSC(PCShellSetContext(pc,handle.get())); EONSIM_PETSC(PCShellSetDestroy(pc,destroy_patch));
    handle.release(); state->owner=pc;
    EONSIM_PETSC(PCShellSetName(pc,shell_name)); EONSIM_PETSC(PCShellSetApply(pc,apply_patch));
    EONSIM_PETSC(PCShellSetView(pc,view_patch));
    updates->refreshers.push_back([state](Mat matrix){state->refresh(matrix);});
}
void release_native_vanka_setup(KSP solver) {
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver,&pc));
    auto* handle=get_handle(pc);
    if(!handle) throw std::runtime_error("Native setup release requires the Vanka shell PC");
    auto& state=**handle;
    state.release_setup();
    // The level KSP is only an owner for PCApply. Replace its setup operator
    // references by a dimension-only shell so it cannot retain FP64 values.
    PetscOwner<Mat,MatDestroy> placeholder;
    EONSIM_PETSC(MatCreateShell(state.comm,state.end-state.begin,state.end-state.begin,
        state.global,state.global,nullptr,placeholder.put()));
    EONSIM_PETSC(KSPSetOperators(solver,placeholder.get(),placeholder.get()));
}
bool query_vanka_patch_schedule(KSP solver,std::vector<std::vector<PetscInt>>& rows,
                               std::vector<PetscInt>& colors) {
    PC pc=nullptr;EONSIM_PETSC(KSPGetPC(solver,&pc));
    auto* handle=get_handle(pc);
    if(!handle||!(*handle)->level_mode||(*handle)->released) return false;
    rows.clear();colors=(*handle)->patch_colors;
    for(auto is:(*handle)->indices.values) {
        PetscInt count=0;const PetscInt* indices=nullptr;
        EONSIM_PETSC(ISGetLocalSize(is,&count));EONSIM_PETSC(ISGetIndices(is,&indices));
        rows.emplace_back(indices,indices+count);
        EONSIM_PETSC(ISRestoreIndices(is,&indices));
    }
    return true;
}
} // namespace eonsim
