#pragma once
/** @file
 * @brief 通用 assembled SNES 驱动；不依赖物理与网格。 */
#include "eonsim/linear_system.hpp"
#include <petscsnes.h>
#include <functional>
#include <memory>
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
    bool solver_reused=false; ///< 本次是否复用了前一次成功调用的 SNES/KSP/PC。
    PetscInt solver_generation=0; ///< 此 NonlinearSystem 的求解器构建序号，从 1 开始。
    double residual_norm=0;
    std::vector<FieldResidual> field_residuals; ///< 所有 rank 相同；原始反力不参与字段收敛范数。
};
/** 固定代数布局的非线性存储，复用 ghost Vec、AIJ 图和本地试算缓冲。
 * 构造复制本地 layout；分区、有效编号、字段或稀疏图改变时须重新构造。
 * 构造、solve 和析构须在同一 communicator 上按相同顺序调用，且在 PetscFinalize 前析构。
 * 不保存历史或 solve 回调；不可复制、不可重入。同配置的默认 Newton 求解器及工作缓冲跨 solve 复用，
 * 但每次仍更新 Jacobian/数值 PC；配置、PETSc options、约束行改变或失败后重建求解器。
 */
class NonlinearSystem {
public:
    /** Consume an optional assembled AIJ pattern, without duplicating its graph.
     * Supply it on all ranks or none. Its communicator, row/column ownership and
     * global sizes must match layout; all later entries (including constraint
     * diagonals) must already exist. Numeric values are cleared before assembly.
     * Without a pattern, use layout.diagonal/off_diagonal preallocation as before.
     */
    NonlinearSystem(MPI_Comm communicator,const AlgebraLayout& layout,
                    PetscOwner<Mat,MatDestroy> pattern={});
    ~NonlinearSystem();
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
    /** Opt in to a fixed residual COO plan before the first solve (collective, once).
     * Rows are global contribution indices, may repeat or belong to another rank,
     * and may be negative (ignored). An empty local contribution list is valid.
     * The callback then fills residual_coo_values() instead of inserting into Vec.
     * Success publishes the complete buffer collectively; failed partial buffers
     * are discarded. Constraint replacement and unprojected reactions are unchanged.
     * The driver prepares every actual callback Vec, including SNES line-search
     * work vectors, when its residual is published. Jacobian-only scratch is
     * not published and needs no COO plan. VecDuplicate is not assumed to copy
     * a COO communication plan.
     */
    void set_residual_coo(const std::vector<PetscInt>& rows);
    /// Borrowed fixed-size buffer in the original residual contribution order.
    PetscScalar* residual_coo_values() noexcept { return residual_coo_enabled_?residual_coo_values_.data():nullptr; }
    /** 回调只插入本 rank 单元的原始贡献，不做最终装配或提交历史。
 * 输入是 owned+ghost；Mat 为 nullptr 时仅计算残量。所有方法 collective。
 * constraints 只包含 owned 行；约束替换残量行，保留其它行对约束列的导数。
 * layout.fields 在各 rank 上同名同序，须无重叠地覆盖 owned 有效行。
 * 每字段要求 rms <= atol + rtol*initial_rms，约束误差另按 constraint_tolerance 验收。
 * 初始范数取本次调用施加 prescribed 后的状态；无字段配置时尺度为 1，容差继承 config。
 * 所有正 SNES reason 都需通过最终重新装配的字段验收，否则抛 StepRejected，不返回 trial。
 * 最终一次全新原始残量先保存 owned+ghost 反力，再替换约束行做验收；两者来自同一评价。
 * assemble 抛 StepRejected 时先完成部分装配以排空远程插入，再用 SNES domain-error 协议拒绝试探点。
 * 默认 Newton 回溯线搜索可尝试较小步；最终未收敛才交给时间驱动缩步。线性/PC 故障抛普通异常。
 * 已共同传播的callback错误或StepRejected后可用相同布局重新solve；每次覆盖trial、重算初始范数和矩阵数值。
 * fatal callback引起PETSc提前返回时更换trial Vec以隔离遗留只读锁；COO矩阵/图不重建。
 * config、约束值及回调只借用到本次调用结束；约束行可变化，但必须包含在既有图中。
 * -nonlinear_reuse false 可显式使用每次新建的求解器；非默认 SNES/lagged-PC 选项保留每次新建语义。
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
    bool coo_enabled_=false,residual_coo_enabled_=false,solve_started_=false,solving_=false;
    std::vector<PetscScalar> coo_values_;
    std::vector<PetscInt> residual_coo_rows_;
    std::vector<PetscScalar> residual_coo_values_;
    std::vector<PetscObjectId> residual_coo_vectors_; ///< IDs only; never retains borrowed Vec handles.
    PetscInt solver_generation_=0;
    struct Workspace;
    std::unique_ptr<Workspace> workspace_; ///< Destroy solver/PC before the referenced matrix and vectors.
};
}
