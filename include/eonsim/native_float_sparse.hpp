#pragma once
/** @file Row-scaled FP32 CSR action with distributed sparse halo exchange. */
#include "eonsim/pc_plan.hpp"
#include <algorithm>
#include <cmath>
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
    void update(Mat matrix,bool drop_zeros=false) {
        comm=PetscObjectComm(reinterpret_cast<PetscObject>(matrix));
        PetscInt new_begin=0,new_end=0,new_rows=0,new_columns=0;
        EONSIM_PETSC(MatGetOwnershipRange(matrix,&new_begin,&new_end));
        EONSIM_PETSC(MatGetSize(matrix,&new_rows,&new_columns));
        std::vector<PetscInt> new_offsets(1,0),all_columns;
        std::vector<float> new_values; std::vector<double> new_scales;
        bool valid=true;
        for(PetscInt row=new_begin;row<new_end;++row) {
            PetscInt count=0; const PetscInt* indices=nullptr; const PetscScalar* entries=nullptr;
            EONSIM_PETSC(MatGetRow(matrix,row,&count,&indices,&entries));
            double scale=0;
            for(PetscInt j=0;j<count;++j) { scale=std::max(scale,std::abs(entries[j])); valid=valid&&std::isfinite(entries[j]); }
            if(scale==0) scale=1.;
            new_scales.push_back(scale);
            for(PetscInt j=0;j<count;++j) {
                if(drop_zeros&&entries[j]==0.) continue;
                all_columns.push_back(indices[j]); new_values.push_back(static_cast<float>(entries[j]/scale));
                valid=valid&&std::isfinite(new_values.back());
            }
            new_offsets.push_back(static_cast<PetscInt>(all_columns.size()));
            EONSIM_PETSC(MatRestoreRow(matrix,row,&count,&indices,&entries));
        }
        std::vector<PetscInt> unique_columns=all_columns;
        std::sort(unique_columns.begin(),unique_columns.end());
        unique_columns.erase(std::unique(unique_columns.begin(),unique_columns.end()),unique_columns.end());
        std::vector<PetscInt> new_slots; new_slots.reserve(all_columns.size());
        for(auto column:all_columns) new_slots.push_back(static_cast<PetscInt>(
            std::lower_bound(unique_columns.begin(),unique_columns.end(),column)-unique_columns.begin()));
        if(prepared) valid=valid&&begin==new_begin&&end==new_end&&global_rows==new_rows&&
            global_columns==new_columns&&offsets==new_offsets&&columns==unique_columns&&slots==new_slots;
        int local_bad=!valid,any_bad=0;
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
