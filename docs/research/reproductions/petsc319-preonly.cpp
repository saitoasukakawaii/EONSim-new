// Standalone PETSc reproduction: no EONSim, SNES or residual diagnostic.
#include <petscksp.h>
#include <cstdio>
static PetscErrorCode observe(KSP ksp,Vec,Vec,void*) {
  int rank; KSPConvergedReason reason;
  MPI_Comm_rank(PETSC_COMM_WORLD,&rank); KSPGetConvergedReason(ksp,&reason);
  std::printf("postsolve rank=%d ksp_reason=%d\n",rank,(int)reason); std::fflush(stdout);
  return 0;
}
int main(int argc,char** argv) {
  PetscInitialize(&argc,&argv,nullptr,nullptr);
  int rank; MPI_Comm_rank(PETSC_COMM_WORLD,&rank);
  Mat a; Vec b,x; KSP ksp; PC pc;
  MatCreateAIJ(PETSC_COMM_WORLD,1,1,2,2,1,nullptr,0,nullptr,&a);
  MatSetValue(a,rank,rank,rank?0.:1.,INSERT_VALUES);
  MatAssemblyBegin(a,MAT_FINAL_ASSEMBLY); MatAssemblyEnd(a,MAT_FINAL_ASSEMBLY);
  MatCreateVecs(a,&x,&b); VecSet(b,1.);
  KSPCreate(PETSC_COMM_WORLD,&ksp); KSPSetOperators(ksp,a,a);
  KSPSetType(ksp,KSPPREONLY); KSPGetPC(ksp,&pc); PCSetType(pc,PCBJACOBI);
  PetscOptionsSetValue(nullptr,"-sub_ksp_type","preonly");
  PetscOptionsSetValue(nullptr,"-sub_pc_type","lu");
  PetscOptionsSetValue(nullptr,"-sub_pc_factor_mat_solver_type","petsc");
  KSPSetFromOptions(ksp); KSPSetPostSolve(ksp,observe,nullptr);
  PetscPushErrorHandler(PetscReturnErrorHandler,nullptr);
  const auto error=KSPSolve(ksp,b,x);
  PetscPopErrorHandler();
  std::printf("returned rank=%d error=%d\n",rank,(int)error);
  KSPDestroy(&ksp); VecDestroy(&x); VecDestroy(&b); MatDestroy(&a);
  return PetscFinalize();
}
