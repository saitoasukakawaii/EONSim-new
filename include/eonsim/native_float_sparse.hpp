#pragma once
/** @file Row-scaled FP32 CSR action with distributed sparse halo exchange. */
#include "eonsim/pc_plan.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace eonsim {
// Float coefficients are normalized per row; gathered vectors are normalized
// per local apply before conversion. This protects the float arithmetic from
// dimensional FSI scaling without changing the outer FP64 operator. Only the
// actual sparse column halo is communicated, including on empty owners.
struct NativeFloatSparse {
    MPI_Comm comm=PETSC_COMM_SELF;
    PetscInt begin=0,end=0,global_rows=0,global_columns=0;
    std::vector<PetscInt> offsets,columns,slots;
    std::vector<float> values,input_values,output_values;
    std::vector<double> scales;
    PetscOwner<Vec,VecDestroy> gathered;
    PetscOwner<VecScatter,VecScatterDestroy> scatter;
    bool prepared=false;
    // An optional binary column mask extracts an identity lifting action
    // directly from source rows. It never duplicates/scales a complete FP64
    // matrix merely to discard its inactive columns afterwards.
    void update(Mat matrix,bool drop_zeros=false,Vec column_filter=nullptr) {
        comm=PetscObjectComm(reinterpret_cast<PetscObject>(matrix));
        PetscInt new_begin=0,new_end=0,new_rows=0,new_columns=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&new_begin,&new_end));
        EONSIM_PETSC(MatGetSize(matrix,&new_rows,&new_columns));
        std::vector<PetscInt> mask_columns;
        std::vector<unsigned char> mask_values;
        bool valid=true;
        if(column_filter) {
            PetscInt size=0;EONSIM_PETSC(VecGetSize(column_filter,&size));
            int local_bad=size!=new_columns,any_bad=0;
            EONSIM_PETSC(MPI_Allreduce(&local_bad,&any_bad,1,MPI_INT,MPI_MAX,comm));
            if(any_bad) throw std::runtime_error("Float sparse column mask has the wrong global size");
            for(PetscInt row=new_begin;row<new_end;++row) {
                PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* entries=nullptr;
                EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
                if(count) mask_columns.insert(mask_columns.end(),indices,indices+count);
                EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
            }
            std::sort(mask_columns.begin(),mask_columns.end());
            mask_columns.erase(std::unique(mask_columns.begin(),mask_columns.end()),mask_columns.end());
            std::vector<PetscInt>(mask_columns).swap(mask_columns);
            PetscOwner<Vec,VecDestroy> selected;
            PetscOwner<IS,ISDestroy> selection;
            PetscOwner<VecScatter,VecScatterDestroy> gather;
            EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(mask_columns.size()),selected.put()));
            EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(mask_columns.size()),
                mask_columns.data(),PETSC_COPY_VALUES,selection.put()));
            EONSIM_PETSC(VecScatterCreate(column_filter,selection.get(),selected.get(),nullptr,gather.put()));
            EONSIM_PETSC(VecScatterBegin(gather.get(),column_filter,selected.get(),INSERT_VALUES,SCATTER_FORWARD));
            EONSIM_PETSC(VecScatterEnd(gather.get(),column_filter,selected.get(),INSERT_VALUES,SCATTER_FORWARD));
            mask_values.resize(mask_columns.size());
            const PetscScalar* values=nullptr;EONSIM_PETSC(VecGetArrayRead(selected.get(),&values));
            for(std::size_t i=0;i<mask_values.size();++i) {
                valid=valid&&(values[i]==0.||values[i]==1.);
                mask_values[i]=values[i]!=0.;
            }
            EONSIM_PETSC(VecRestoreArrayRead(selected.get(),&values));
        }
        const auto included=[&](PetscInt column) {
            return !column_filter||mask_values[static_cast<std::size_t>(
                std::lower_bound(mask_columns.begin(),mask_columns.end(),column)-mask_columns.begin())]!=0;
        };
        const auto row_count=static_cast<std::size_t>(new_end-new_begin);
        std::vector<PetscInt> new_offsets(row_count+1,0);
        std::vector<double> new_scales(row_count,1.);
        // Count first so the retained vectors have exact-sized allocations.
        // Amortized push_back capacity is sizeable for coefficient/index arrays
        // and is not visible in a values.size()*sizeof(float) counter.
        std::size_t entries_count=0;
        for(PetscInt row=new_begin;row<new_end;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            double scale=0;
            for(PetscInt j=0;j<count;++j) {
                valid=valid&&std::isfinite(entries[j]);
                if(!included(indices[j])) continue;
                scale=std::max(scale,std::abs(entries[j]));
                if(!drop_zeros||entries[j]!=0.) ++entries_count;
            }
            if(scale==0) scale=1.;
            new_scales[row-new_begin]=scale;
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
            valid=valid&&entries_count<=static_cast<std::size_t>(std::numeric_limits<PetscInt>::max());
            if(valid) new_offsets[row-new_begin+1]=static_cast<PetscInt>(entries_count);
        }
        int local_bad=!valid,any_bad=0;
        EONSIM_PETSC(MPI_Allreduce(&local_bad,&any_bad,1,MPI_INT,MPI_MAX,comm));
        if(any_bad) throw std::runtime_error("Float sparse source/mask is nonfinite or exceeds its local index range");
        std::vector<PetscInt> all_columns(entries_count);
        std::vector<float> new_values(entries_count);
        std::size_t position=0;
        for(PetscInt row=new_begin;row<new_end;++row) {
            PetscInt count=0;const PetscInt* indices=nullptr;const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            for(PetscInt j=0;j<count;++j) {
                if(!included(indices[j])||(drop_zeros&&entries[j]==0.)) continue;
                all_columns[position]=indices[j];
                new_values[position]=static_cast<float>(entries[j]/new_scales[row-new_begin]);
                valid=valid&&std::isfinite(new_values[position]);
                ++position;
            }
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        std::vector<PetscInt>().swap(mask_columns);
        std::vector<unsigned char>().swap(mask_values);
        std::vector<PetscInt> unique_columns=all_columns;
        std::sort(unique_columns.begin(),unique_columns.end());
        unique_columns.erase(std::unique(unique_columns.begin(),unique_columns.end()),unique_columns.end());
        // erase changes the size, not the capacity: without compacting this
        // unique halo map retained an entire nnz-sized index array per level.
        std::vector<PetscInt>(unique_columns).swap(unique_columns);
        std::vector<PetscInt> new_slots(all_columns.size());
        for(std::size_t i=0;i<all_columns.size();++i) new_slots[i]=static_cast<PetscInt>(
            std::lower_bound(unique_columns.begin(),unique_columns.end(),all_columns[i])-unique_columns.begin());
        std::vector<PetscInt>().swap(all_columns);
        if(prepared) valid=valid&&begin==new_begin&&end==new_end&&global_rows==new_rows&&
            global_columns==new_columns&&offsets==new_offsets&&columns==unique_columns&&slots==new_slots;
        local_bad=!valid;any_bad=0;
        EONSIM_PETSC(MPI_Allreduce(&local_bad,&any_bad,1,MPI_INT,MPI_MAX,comm));
        if(any_bad) throw std::runtime_error("Float sparse refresh changed the graph/ownership or received nonfinite entries");
        if(!prepared) {
            begin=new_begin; end=new_end; global_rows=new_rows; global_columns=new_columns;
            offsets=std::move(new_offsets); columns=std::move(unique_columns); slots=std::move(new_slots);
            PetscOwner<Vec,VecDestroy> input;
            EONSIM_PETSC(MatCreateVecs(matrix,input.put(),nullptr));
            EONSIM_PETSC(VecCreateSeq(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),gathered.put()));
            PetscOwner<IS,ISDestroy> source;
            EONSIM_PETSC(ISCreateGeneral(PETSC_COMM_SELF,static_cast<PetscInt>(columns.size()),
                columns.data(),PETSC_COPY_VALUES,source.put()));
            EONSIM_PETSC(VecScatterCreate(input.get(),source.get(),gathered.get(),nullptr,scatter.put()));
            input_values.resize(columns.size()); output_values.resize(columns.size()); prepared=true;
        }
        scales=std::move(new_scales); values=std::move(new_values);
    }
    PetscErrorCode multiply(Vec input,Vec output,bool transpose) {
        PetscFunctionBeginUser;
        if(!transpose) {
            PetscCall(VecScatterBegin(scatter.get(),input,gathered.get(),INSERT_VALUES,SCATTER_FORWARD));
            PetscCall(VecScatterEnd(scatter.get(),input,gathered.get(),INSERT_VALUES,SCATTER_FORWARD));
            const PetscScalar* x=nullptr; PetscScalar* y=nullptr;
            PetscCall(VecGetArrayRead(gathered.get(),&x));
            double scale=0; for(std::size_t i=0;i<columns.size();++i) scale=std::max(scale,std::abs(x[i]));
            if(scale==0) scale=1;
            for(std::size_t i=0;i<columns.size();++i) input_values[i]=static_cast<float>(x[i]/scale);
            PetscCall(VecRestoreArrayRead(gathered.get(),&x));
            PetscCall(VecGetArray(output,&y));
            for(PetscInt row=0;row<end-begin;++row) {
                float value=0;
                for(PetscInt j=offsets[row];j<offsets[row+1];++j) value+=values[j]*input_values[slots[j]];
                y[row]=static_cast<double>(value)*scale*scales[row];
            }
            PetscCall(VecRestoreArray(output,&y));
        } else {
            const PetscScalar* x=nullptr; PetscScalar* y=nullptr;
            PetscCall(VecGetArrayRead(input,&x));
            double scale=0;
            for(PetscInt row=0;row<end-begin;++row) scale=std::max(scale,std::abs(x[row]*scales[row]));
            if(scale==0) scale=1;
            std::fill(output_values.begin(),output_values.end(),0.f);
            for(PetscInt row=0;row<end-begin;++row) {
                const auto value=static_cast<float>((x[row]*scales[row])/scale);
                for(PetscInt j=offsets[row];j<offsets[row+1];++j) output_values[slots[j]]+=values[j]*value;
            }
            PetscCall(VecRestoreArrayRead(input,&x));
            PetscCall(VecGetArray(gathered.get(),&y));
            for(std::size_t i=0;i<columns.size();++i) y[i]=static_cast<double>(output_values[i])*scale;
            PetscCall(VecRestoreArray(gathered.get(),&y));
            PetscCall(VecSet(output,0));
            PetscCall(VecScatterBegin(scatter.get(),gathered.get(),output,ADD_VALUES,SCATTER_REVERSE));
            PetscCall(VecScatterEnd(scatter.get(),gathered.get(),output,ADD_VALUES,SCATTER_REVERSE));
        }
        PetscFunctionReturn(PETSC_SUCCESS);
    }
};

} // namespace eonsim
