#pragma once

#include "eonsim/config.hpp"
#include <petscksp.h>
#include <string>
#include <type_traits>
#include <vector>

namespace eonsim {

static_assert(std::is_same<PetscScalar, double>::value,
              "EONSim currently requires a real, double-precision PETSc build");

void check_petsc(PetscErrorCode error, const char* operation);
#define EONSIM_PETSC(operation) ::eonsim::check_petsc((operation), #operation)

template<class T, PetscErrorCode (*Destroy)(T*)>
class PetscOwner {
public:
    PetscOwner() = default;
    ~PetscOwner() { if (value_) (void)Destroy(&value_); }
    PetscOwner(const PetscOwner&) = delete;
    PetscOwner& operator=(const PetscOwner&) = delete;
    T get() const { return value_; }
    T* put() { return &value_; }
private:
    T value_ = nullptr;
};

struct LinearResult {
    std::vector<double> values;
    PetscInt iterations = 0;
    double true_residual = 0.0;
    double rhs_norm = 0.0;
    double relative_tolerance = 0.0;
    double absolute_tolerance = 0.0;
    double nonzeros = 0.0;
    std::string reason;
    std::string ksp_type;
    std::string pc_type;
};

// Sequential assembled algebra for P0. No mesh or physical-kernel dependency.
class LinearSystem {
public:
    LinearSystem(MPI_Comm communicator, const std::vector<PetscInt>& row_nonzeros);
    void add(PetscInt count, const PetscInt* dofs, const double* stiffness, const double* load);
    void constrain(const std::vector<PetscInt>& dofs, const std::vector<double>& values);
    LinearResult solve(const SolverConfig& config, bool full_diagnostics);
private:
    MPI_Comm communicator_;
    PetscOwner<Mat, MatDestroy> matrix_;
    PetscOwner<Vec, VecDestroy> rhs_, solution_, work_;
    PetscOwner<KSP, KSPDestroy> solver_;
};

} // namespace eonsim
