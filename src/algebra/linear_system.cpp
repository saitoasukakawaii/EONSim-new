#include "eonsim/linear_system.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace eonsim {

void check_petsc(PetscErrorCode error, const char* operation)
{
    if (!error) return;
    const char* message = nullptr;
    (void)PetscErrorMessage(error, &message, nullptr);
    throw std::runtime_error(std::string(operation) + ": " + (message ? message : "PETSc failure"));
}

LinearSystem::LinearSystem(MPI_Comm communicator, const std::vector<PetscInt>& row_nonzeros)
    : communicator_(communicator)
{
    int size = 0;
    if (MPI_Comm_size(communicator, &size) != MPI_SUCCESS) throw std::runtime_error("MPI_Comm_size failed");
    if (size != 1) throw std::runtime_error("P0 algebra requires one rank; distributed assembly is not implemented");
    if (row_nonzeros.empty() || row_nonzeros.size() > static_cast<std::size_t>(std::numeric_limits<PetscInt>::max()))
        throw std::runtime_error("DoF count exceeds the current PETSc index range");
    const auto n = static_cast<PetscInt>(row_nonzeros.size());
    EONSIM_PETSC(MatCreateSeqAIJ(communicator_, n, n, 0, row_nonzeros.data(), matrix_.put()));
    EONSIM_PETSC(MatSetOption(matrix_.get(), MAT_NEW_NONZERO_ALLOCATION_ERR, PETSC_TRUE));
    EONSIM_PETSC(VecCreateSeq(communicator_, n, rhs_.put()));
    EONSIM_PETSC(VecDuplicate(rhs_.get(), solution_.put()));
    EONSIM_PETSC(VecDuplicate(rhs_.get(), work_.put()));
    EONSIM_PETSC(VecSet(rhs_.get(), 0.0));
    EONSIM_PETSC(VecSet(solution_.get(), 0.0));
}

void LinearSystem::add(PetscInt count, const PetscInt* dofs, const double* stiffness, const double* load)
{
    EONSIM_PETSC(MatSetValues(matrix_.get(), count, dofs, count, dofs, stiffness, ADD_VALUES));
    EONSIM_PETSC(VecSetValues(rhs_.get(), count, dofs, load, ADD_VALUES));
}

void LinearSystem::constrain(const std::vector<PetscInt>& dofs, const std::vector<double>& values)
{
    if (dofs.size() != values.size() || dofs.empty()) throw std::runtime_error("Invalid Dirichlet data");
    EONSIM_PETSC(MatAssemblyBegin(matrix_.get(), MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatAssemblyEnd(matrix_.get(), MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(VecAssemblyBegin(rhs_.get()));
    EONSIM_PETSC(VecAssemblyEnd(rhs_.get()));
    EONSIM_PETSC(VecSet(work_.get(), 0.0));
    const auto n = static_cast<PetscInt>(dofs.size());
    EONSIM_PETSC(VecSetValues(work_.get(), n, dofs.data(), values.data(), INSERT_VALUES));
    EONSIM_PETSC(VecAssemblyBegin(work_.get()));
    EONSIM_PETSC(VecAssemblyEnd(work_.get()));
    // Symmetric row/column elimination: b_free -= A_free,boundary * g.
    EONSIM_PETSC(MatZeroRowsColumns(matrix_.get(), n, dofs.data(), 1.0, work_.get(), rhs_.get()));
}

LinearResult LinearSystem::solve(const SolverConfig& config, bool full_diagnostics)
{
    if (full_diagnostics) {
        PetscBool symmetric = PETSC_FALSE;
        EONSIM_PETSC(MatIsSymmetric(matrix_.get(), 1e-12, &symmetric));
        if (!symmetric) throw std::runtime_error("Constrained Poisson operator is not symmetric");
    }
    EONSIM_PETSC(KSPCreate(communicator_, solver_.put()));
    EONSIM_PETSC(KSPSetOperators(solver_.get(), matrix_.get(), matrix_.get()));
    EONSIM_PETSC(KSPSetType(solver_.get(), KSPCG));
    EONSIM_PETSC(KSPSetNormType(solver_.get(), KSP_NORM_UNPRECONDITIONED));
    PC preconditioner = nullptr;
    EONSIM_PETSC(KSPGetPC(solver_.get(), &preconditioner));
    EONSIM_PETSC(PCSetType(preconditioner, PCJACOBI));
    EONSIM_PETSC(KSPSetTolerances(solver_.get(), config.relative_tolerance, config.absolute_tolerance,
                                PETSC_DEFAULT, config.maximum_iterations));
    EONSIM_PETSC(KSPSetFromOptions(solver_.get()));
    EONSIM_PETSC(KSPSolve(solver_.get(), rhs_.get(), solution_.get()));
    KSPConvergedReason reason;
    EONSIM_PETSC(KSPGetConvergedReason(solver_.get(), &reason));
    if (reason <= 0) throw std::runtime_error(std::string("Linear solve did not converge: ") + KSPConvergedReasons[reason]);
    LinearResult result;
    result.reason = KSPConvergedReasons[reason];
    EONSIM_PETSC(KSPGetIterationNumber(solver_.get(), &result.iterations));
    EONSIM_PETSC(KSPGetTolerances(solver_.get(), &result.relative_tolerance, &result.absolute_tolerance, nullptr, nullptr));
    EONSIM_PETSC(MatMult(matrix_.get(), solution_.get(), work_.get()));
    EONSIM_PETSC(VecAXPY(work_.get(), -1.0, rhs_.get()));
    EONSIM_PETSC(VecNorm(work_.get(), NORM_2, &result.true_residual));
    EONSIM_PETSC(VecNorm(rhs_.get(), NORM_2, &result.rhs_norm));
    const double tolerance = std::max(result.absolute_tolerance, result.relative_tolerance * result.rhs_norm);
    if (!std::isfinite(result.true_residual) || !std::isfinite(result.rhs_norm) || result.true_residual > tolerance)
        throw std::runtime_error("True residual does not satisfy the configured linear solve tolerance");
    const char *ksp = nullptr, *pc = nullptr;
    EONSIM_PETSC(KSPGetType(solver_.get(), &ksp));
    EONSIM_PETSC(PCGetType(preconditioner, &pc));
    result.ksp_type = ksp;
    result.pc_type = pc;
    MatInfo info{};
    EONSIM_PETSC(MatGetInfo(matrix_.get(), MAT_LOCAL, &info));
    result.nonzeros = info.nz_used;
    PetscInt n = 0;
    EONSIM_PETSC(VecGetSize(solution_.get(), &n));
    result.values.resize(static_cast<std::size_t>(n));
    const PetscScalar* data = nullptr;
    EONSIM_PETSC(VecGetArrayRead(solution_.get(), &data));
    std::copy(data, data+n, result.values.begin());
    EONSIM_PETSC(VecRestoreArrayRead(solution_.get(), &data));
    for (double value : result.values)
        if (!std::isfinite(value)) throw std::runtime_error("Non-finite solution");
    return result;
}
} // namespace eonsim
