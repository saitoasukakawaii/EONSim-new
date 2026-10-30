#pragma once
/** @file
 * @brief 通用 assembled SNES 驱动；不依赖物理与网格。 */
#include "eonsim/linear_system.hpp"
#include <petscsnes.h>
#include <functional>
namespace eonsim {
struct FieldResidual {
    std::string name;
    PetscInt equation_rows=0,constraint_rows=0; ///< 全局 owned 行数；不计 ghost。
    double initial_rms=0,rms=0,limit=0,constraint_max=0;
    FieldTolerance tolerance;
};
struct NonlinearResult {
    std::vector<double> values, raw_residual;
    PetscInt iterations=0, linear_iterations=0;
    PetscInt domain_rejections=0; ///< 回调中被拒绝的试探残量/Jacobian 评价次数；不表示已提交时间步。
    double residual_norm=0;
    std::vector<FieldResidual> field_residuals; ///< 所有 rank 相同；原始反力不参与字段收敛范数。
};
/** 固定代数布局的非线性存储，复用 ghost Vec、AIJ 图和本地试算缓冲。
 * 构造复制本地 layout；分区、有效编号、字段或稀疏图改变时须重新构造。
 * 构造、solve 和析构须在同一 communicator 上按相同顺序调用，且在 PetscFinalize 前析构。
 * 不保存历史或 solve 回调；不可复制、不可重入。SNES/KSP/PC 仍按每次 solve 创建。
 */
class NonlinearSystem {
public:
    NonlinearSystem(MPI_Comm communicator,const AlgebraLayout& layout);
    /** Opt in to a fixed COO Jacobian before the first solve (collective, once).
     * rows/columns are global indices in contribution order, including duplicates and remote rows.
     * Each rank may supply no entries. Invalid indices/sizes fail collectively before changing the matrix.
     * Owned diagonal slots are added internally so constraint-only rows remain representable.
     * The pattern, layout and partition are immutable for this system's lifetime.
     */
    void set_jacobian_coo(const std::vector<PetscInt>& rows,const std::vector<PetscInt>& columns);
    /** Borrowed, fixed-size buffer in the original COO contribution order (nullptr when disabled).
     * During a callback with non-null Mat, fill these values instead of calling MatSetValues.
     * The driver zeros the buffer each evaluation and performs the collective COO update only
     * after all local callbacks succeed. Do not insert matrix values or call collective COO APIs
     * inside the callback. Residual Vec insertion and final constraint/reaction semantics are unchanged.
     * The pointer stays valid until destruction; callers must not write past their pattern size.
     */
    PetscScalar* jacobian_coo_values() noexcept { return coo_enabled_?coo_values_.data():nullptr; }
    /** 回调只插入本 rank 单元的原始贡献，不做最终装配或提交历史。
 * 输入是 owned+ghost；Mat 为 nullptr 时仅计算残量。所有方法 collective。
 * constraints 只包含 owned 行；约束替换残量行，保留其它行对约束列的导数。
 * layout.fields 在各 rank 上同名同序，须无重叠地覆盖 owned 有效行。
 * 每字段要求 rms <= atol + rtol*initial_rms，约束误差另按 constraint_tolerance 验收。
 * 初始范数取本次调用施加 prescribed 后的状态；无字段配置时尺度为 1，容差继承 config。
 * 所有正 SNES reason 都需通过最终重新装配的字段验收，否则抛 StepRejected，不返回 trial。
 * assemble 抛 StepRejected 时先完成部分装配以排空远程插入，再用 SNES domain-error 协议拒绝试探点。
 * 默认 Newton 回溯线搜索可尝试较小步；最终未收敛才交给时间驱动缩步。线性/PC 故障抛普通异常。
 * StepRejected 后可用相同布局重新 solve；每次覆盖 trial、重算初始范数和矩阵数值。
 * config、约束值及回调只借用到本次调用结束；约束行可变化，但必须包含在既有图中。
 */
    NonlinearResult solve(const SolverConfig& config, const std::vector<double>& initial,
        const std::vector<PetscInt>& constraints, const std::vector<double>& prescribed,
        const std::function<void(const std::vector<double>&,Vec,Mat)>& assemble);
private:
    MPI_Comm communicator_;
    const AlgebraLayout layout_;
    PetscOwner<Vec,VecDestroy> solution_,residual_,scratch_;
    PetscOwner<Mat,MatDestroy> matrix_;
    std::vector<double> local_trial_;
    bool coo_enabled_=false,solve_started_=false;
    std::vector<PetscScalar> coo_values_;
};
}
