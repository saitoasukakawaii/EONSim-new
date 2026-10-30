#include <petscsys.h>
#include <iostream>
#include <limits>
#include <cstring>
int main(int argc,char** argv) {
    if(PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    int rank=0,size=0,sum=0,length=0;
    MPI_Comm_rank(PETSC_COMM_WORLD,&rank);
    MPI_Comm_size(PETSC_COMM_WORLD,&size);
    MPI_Allreduce(&rank,&sum,1,MPI_INT,MPI_SUM,PETSC_COMM_WORLD);
    char mpi[MPI_MAX_LIBRARY_VERSION_STRING],petsc[256];
    MPI_Get_library_version(mpi,&length);
    PetscGetVersion(petsc,sizeof(petsc));
    bool valid=sizeof(PetscInt)==4 && sizeof(PetscReal)==8 &&
        sizeof(PetscScalar)==8 && std::numeric_limits<PetscReal>::digits==53 &&
        sum==size*(size-1)/2 && std::strstr(mpi,"Open MPI");
#if defined(PETSC_USE_COMPLEX)
    valid=false;
#endif
    if(rank==0) std::cout<<"runtime scalar=real precision=double int_bits="<<8*sizeof(PetscInt)
        <<" ranks="<<size<<" valid="<<valid<<"\n"<<petsc<<"\n"<<mpi<<"\n";
    const auto error=PetscFinalize();
    return valid&&!error?0:1;
}
