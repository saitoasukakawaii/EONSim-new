#include "eonsim/distributed_mg_layout.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>

namespace {
eonsim::DofKey semantic(PetscInt row) {
    eonsim::DofKey key;key.entity=row/4;key.component=0;
    switch(row%4) {
    case 0:key.domain=eonsim::DofDomain::fluid;key.quantity=eonsim::DofQuantity::velocity;break;
    case 1:key.domain=eonsim::DofDomain::solid;key.quantity=eonsim::DofQuantity::velocity;break;
    case 2:key.domain=eonsim::DofDomain::mesh;key.quantity=eonsim::DofQuantity::displacement;break;
    default:key.domain=eonsim::DofDomain::fluid;key.quantity=eonsim::DofQuantity::pressure;break;
    }
    return key;
}
void require(MPI_Comm comm,bool valid,const char* message) {
    int bad=!valid,any=0;EONSIM_PETSC(MPI_Allreduce(&bad,&any,1,MPI_INT,MPI_MAX,comm));
    if(any) throw std::runtime_error(message);
}
void verify(MPI_Comm comm,bool empty_last) {
    using namespace eonsim;
    int rank=0,size=1;MPI_Comm_rank(comm,&rank);MPI_Comm_size(comm,&size);
    const PetscInt local=empty_last&&size>1&&rank==size-1?0:32;
    PetscOwner<Mat,MatDestroy> matrix;
    EONSIM_PETSC(MatCreateAIJ(comm,local,local,PETSC_DECIDE,PETSC_DECIDE,4,nullptr,2,nullptr,matrix.put()));
    PetscInt begin=0,end=0,n=0;EONSIM_PETSC(MatGetOwnershipRange(matrix.get(),&begin,&end));
    EONSIM_PETSC(MatGetSize(matrix.get(),&n,nullptr));
    std::vector<DofKey> semantics;std::vector<std::array<double,36>> candidates;
    std::vector<unsigned char> trace,active;
    for(PetscInt row=begin;row<end;++row) {
        EONSIM_PETSC(MatSetValue(matrix.get(),row,row,row==0?1.:4.+.01*row,INSERT_VALUES));
        if(row!=0) {
            if(row>=4) EONSIM_PETSC(MatSetValue(matrix.get(),row,row-4,-1.,INSERT_VALUES));
            if(row+4<n) EONSIM_PETSC(MatSetValue(matrix.get(),row,row+4,-.7,INSERT_VALUES));
            EONSIM_PETSC(MatSetValue(matrix.get(),row,row/4*4+(row+1)%4,.2,INSERT_VALUES));
        }
        semantics.push_back(semantic(row));
        std::array<double,36> mode{};
        for(std::size_t j=0;j<mode.size();++j) mode[j]=(row+1)*.01+(j+1)*.125;
        candidates.push_back(mode);trace.push_back(row%5==0);active.push_back(row!=0);
    }
    EONSIM_PETSC(MatAssemblyBegin(matrix.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(matrix.get(),MAT_FINAL_ASSEMBLY));
    auto moved=redistribute_mg_layout(comm,matrix.get(),semantics,candidates,trace,active);
    const int nonempty_ranks=empty_last&&size>1?size-1:size;
    require(comm,nonempty_ranks<2?moved.moved_rows==0:moved.moved_rows>0,"Expected actual cross-rank migration");
    bool metadata=true;
    for(std::size_t i=0;i<moved.original_rows.size();++i) {
        const auto row=moved.original_rows[i];
        metadata=metadata&&moved.semantics[i]==semantic(row)&&moved.origin_rank[i]==row/32&&
            moved.trace[i]==(row%5==0)&&moved.active[i]==(row!=0);
        for(std::size_t j=0;j<36;++j)
            metadata=metadata&&moved.candidates[i][j]==(row+1)*.01+(j+1)*.125;
    }
    require(comm,metadata,"Migration changed field semantics, candidates, trace, constraints or provenance");
    // A nonsymmetric graph and distinct field values make an accidentally
    // transposed/per-rank-only permutation fail this original-operator oracle.
    PetscOwner<Vec,VecDestroy> original,original_action,returned,new_vector,new_action,expected;
    EONSIM_PETSC(MatCreateVecs(matrix.get(),original.put(),original_action.put()));
    EONSIM_PETSC(VecDuplicate(original.get(),returned.put()));
    EONSIM_PETSC(MatCreateVecs(moved.matrix.get(),new_vector.put(),new_action.put()));
    EONSIM_PETSC(VecDuplicate(new_vector.get(),expected.put()));
    PetscScalar* values=nullptr;EONSIM_PETSC(VecGetArray(original.get(),&values));
    for(PetscInt i=0;i<local;++i) values[i]=std::sin(.21*(begin+i+1))+.01*(begin+i);
    EONSIM_PETSC(VecRestoreArray(original.get(),&values));
    EONSIM_PETSC(MatMultTranspose(moved.permutation.get(),original.get(),new_vector.get()));
    EONSIM_PETSC(MatMult(moved.permutation.get(),new_vector.get(),returned.get()));
    EONSIM_PETSC(VecAXPY(returned.get(),-1.,original.get()));
    PetscReal inverse_error=0;EONSIM_PETSC(VecNorm(returned.get(),NORM_INFINITY,&inverse_error));
    EONSIM_PETSC(MatMult(matrix.get(),original.get(),original_action.get()));
    EONSIM_PETSC(MatMultTranspose(moved.permutation.get(),original_action.get(),expected.get()));
    EONSIM_PETSC(MatMult(moved.matrix.get(),new_vector.get(),new_action.get()));
    EONSIM_PETSC(VecAXPY(new_action.get(),-1.,expected.get()));
    PetscReal action_error=0,action_norm=0;
    EONSIM_PETSC(VecNorm(new_action.get(),NORM_INFINITY,&action_error));
    EONSIM_PETSC(VecNorm(expected.get(),NORM_INFINITY,&action_norm));
    require(comm,inverse_error==0.&&action_error<=5e-14*std::max(1.,action_norm),
        "Distributed permutation changed the original matrix action");
    // All four semantic slots of a vertex must still have one common owner.
    std::map<std::int64_t,int> node_counts;
    for(const auto& key:moved.semantics) ++node_counts[key.entity];
    bool complete=true;for(const auto& node:node_counts) complete=complete&&node.second==4;
    require(comm,complete,"Migration split a semantic node block");
    if(rank==0) std::cout<<"distributed_mg_layout empty_last="<<empty_last<<" moved_rows="<<moved.moved_rows
        <<" inverse_error="<<inverse_error<<" action_error="<<action_error<<'\n';
}
}
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    int status=0;
    try { verify(PETSC_COMM_WORLD,false);verify(PETSC_COMM_WORLD,true); }
    catch(const std::exception& e) { std::cerr<<e.what()<<'\n';status=1; }
    int all=0;MPI_Allreduce(&status,&all,1,MPI_INT,MPI_MAX,PETSC_COMM_WORLD);
    PetscFinalize();return all;
}
