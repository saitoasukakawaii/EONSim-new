#pragma once
/** @file
 * @brief 分布式 PETSc 代数对象、装配和线性求解。 */

#include "eonsim/config.hpp"
#include <petscksp.h>
#include <string>
#include <map>
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

/** @brief 本 rank 的代数布局；local_to_global 先 owned 后 ghost。
 * @ingroup mhpc_parallel
 * diagonal/off_diagonal 包含远程单元写入本地行所需的完整稀疏图计数。
 * fields 中的 IS 只列本 rank owned 全局编号，不复制全部场。
 */
struct AlgebraLayout {
    PetscInt owned = 0, global = 0, begin = 0;
    std::vector<PetscInt> local_to_global, diagonal, off_diagonal;
    std::map<std::string, std::vector<PetscInt>> fields;
};

/** @brief assembled AIJ 线性系统；不依赖网格或物理核。
 * @ingroup mhpc_numerics
 * 构造、constrain 和 solve 是 communicator 上的 collective；add 为本地插入。
 * 单元贡献仅插入一次，PETSc 完成远程 row owner 累加；返回值包含同步后的 ghost。
 */
class LinearSystem {
public:
    LinearSystem(MPI_Comm communicator, const AlgebraLayout& layout);
    void add(PetscInt count, const PetscInt* dofs, const double* stiffness, const double* load);
    void constrain(const std::vector<PetscInt>& dofs, const std::vector<double>& values);
    LinearResult solve(const SolverConfig& config, bool full_diagnostics);
private:
    MPI_Comm communicator_;
    AlgebraLayout layout_;
    PetscOwner<Mat, MatDestroy> matrix_;
    PetscOwner<Vec, VecDestroy> rhs_, solution_, work_;
};

} // namespace eonsim
