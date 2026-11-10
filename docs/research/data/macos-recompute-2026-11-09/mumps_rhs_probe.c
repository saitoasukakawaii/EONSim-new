/* Standalone dependency probe: no EONSim assembly or nonlinear solver. */
#include <petscksp.h>

int main(int argc, char **argv)
{
  Mat a;
  Vec exact, rhs, solution, residual;
  KSP ksp;
  PC pc;
  PetscInt begin, end;
  PetscReal error, norm;
  PetscMPIInt ranks;
  PetscCall(PetscInitialize(&argc, &argv, NULL, NULL));
  PetscCallMPI(MPI_Comm_size(PETSC_COMM_WORLD, &ranks));
  PetscCall(MatCreateAIJ(PETSC_COMM_WORLD, PETSC_DECIDE, PETSC_DECIDE, 3, 3,
                       3, NULL, 3, NULL, &a));
  PetscCall(MatGetOwnershipRange(a, &begin, &end));
  for (PetscInt i = begin; i < end; ++i) {
    PetscInt columns[2] = {i, (i + 1) % 3};
    PetscScalar values[2] = {2.3 + i, .1};
    PetscCall(MatSetValues(a, 1, &i, 2, columns, values, INSERT_VALUES));
  }
  PetscCall(MatAssemblyBegin(a, MAT_FINAL_ASSEMBLY));
  PetscCall(MatAssemblyEnd(a, MAT_FINAL_ASSEMBLY));
  PetscCall(MatCreateVecs(a, &exact, &rhs));
  PetscCall(VecDuplicate(exact, &solution));
  PetscCall(VecDuplicate(rhs, &residual));
  PetscCall(VecSet(exact, 1.0));
  PetscCall(MatMult(a, exact, rhs));
  PetscCall(KSPCreate(PETSC_COMM_WORLD, &ksp));
  PetscCall(KSPSetOperators(ksp, a, a));
  PetscCall(KSPSetType(ksp, KSPPREONLY));
  PetscCall(KSPGetPC(ksp, &pc));
  PetscCall(PCSetType(pc, PCLU));
  PetscCall(PCFactorSetMatSolverType(pc, MATSOLVERMUMPS));
  PetscCall(KSPSetFromOptions(ksp));
  PetscCall(KSPSolve(ksp, rhs, solution));
  PetscCall(MatMult(a, solution, residual));
  PetscCall(VecAXPY(residual, -1.0, rhs));
  PetscCall(VecNorm(residual, NORM_2, &norm));
  PetscCall(VecAXPY(solution, -1.0, exact));
  PetscCall(VecNorm(solution, NORM_INFINITY, &error));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD,
                       "ranks=%d solution_error=%.17g true_residual=%.17g\n",
                       ranks, (double)error, (double)norm));
  PetscCall(KSPDestroy(&ksp));
  PetscCall(VecDestroy(&exact));
  PetscCall(VecDestroy(&rhs));
  PetscCall(VecDestroy(&solution));
  PetscCall(VecDestroy(&residual));
  PetscCall(MatDestroy(&a));
  PetscCall(PetscFinalize());
  return error < 1e-12 && norm < 1e-12 ? 0 : 2;
}
