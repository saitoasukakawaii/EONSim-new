#pragma once
/** @file @brief 通用 assembled SNES 驱动；不依赖物理与网格。 */
#include "eonsim/linear_system.hpp"
#include <petscsnes.h>
#include <functional>
namespace eonsim {
struct NonlinearResult {
    std::vector<double> values, raw_residual;
    PetscInt iterations=0, linear_iterations=0;
    double residual_norm=0;
};
/** 回调只插入本 rank 单元的原始贡献，不做最终装配或提交历史。
 * 输入是 owned+ghost；Mat 为 nullptr 时仅计算残量。所有方法 collective。
 * constraints 只包含 owned 行；约束替换残量行，保留其它行对约束列的导数。
 */
NonlinearResult solve_nonlinear(MPI_Comm comm, const AlgebraLayout& layout,
    const SolverConfig& config, const std::vector<double>& initial,
    const std::vector<PetscInt>& constraints, const std::vector<double>& prescribed,
    const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble);
}
