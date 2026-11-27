# FSI 可扩展 Matrix-free 路径：运行与证据指南

本文记录 FSI-SCALE-01 的当前生产源码
`50b41ae19067bd8853a482ab853805e23c096ec5`，初始实现为
`e0edc6b83fa2a3b61ac64f758e7be9ab96f40539`。它扩展了
[整体 FSI 多重网格指南](FSI_MONOLITHIC_MULTIGRID.md)中的精确方向作用、混合粗空间及逐层平滑。
旧指南所述“仍存储完整 P”适用于旧路径和本轮未启用 `-fsi_reduced_pc` 的配置。
各次真实残量、RSS、粗空间与投影修复的执行来源，以及最终验收源码，由下述证据索引分别锁定。

**十二项开发方向均有对应代码或运行入口；近似网格无关收敛、百万自由度和多节点强弱扩展仍须以实际算例验收。**
各次执行的源码、构建、命令、成功/失败原件及最终结果统一见
[FSI-SCALE-01 证据索引](../research/data/fsi-scale-01-2026-11-26/README.md)。
本页命令是操作示例，不表示这些命令已经执行，也不把某组可运行选项解释为最优配置。
`50b41ae` 的 MG MPI 1/2/4 检查、严格网格对照 9/9 和 default/moving 物理对照 15/15 均通过；
pressure-supremizer 的网格窗口迭代比仍为 2.1630，高于预设的 1.3，近网格无关目标保持开放。
下文 `30e2941` 的 K-cycle/RSS 和更早结果继续按原源码记录，没有改挂到新增机制。

## 1. 适用模型与十二条入口

适用模型仍是当前共形、低阶 Tet4 单体 FSI：流体速度/压力、结构速度及由时间关系恢复的位移、
参考域 ALE 网格扩展、支持的壁支撑和 RCR 端口。独立测试/试探映射、界面消元、时间历史提交、
压力面及约束处理沿用原离散契约。没有增加高阶、非匹配界面或分布式重网格能力。

下表的 MG 名称省略 RCR wrapper 前缀，完整前缀规则见下一节。

| 优先级 / 目标 | 当前入口与机制 | 当前边界 |
| --- | --- | --- |
| P0 / FSI Multigrid Convergence Optimization | `-pc_recipe monolithic_mg`；物理缩放、增强候选，以及可选 `-monolithic_mg_cycle w` 或 `k`；K-cycle 最多用两个递归预条件方向最小化加权粗残量 | V-cycle 仍为默认；W/K 增加粗工作。实现这些机制不等于网格无关收敛已经成立 |
| P0 / Reduced Assembled Preconditioner | `-fsi_matrix_free -fsi_reduced_pc true`；减少流体方程对 ALE 列的预条件耦合，AIJ/COO 都建立更小符号图 | 外层使用完整精确 Jv；P 仍是 assembled 稀疏矩阵，不是零存储预条件器 |
| P0 / Physics-aware Block Scaling | `-monolithic_mg_field_scaling true`；语义左右缩放，第一层使用带权限制保持原物理 Galerkin 投影 | 缩放只进入 MG 预条件作用；外层残量及验收门槛保持原定义 |
| P0 / FSI-aware Coarse Space | `-monolithic_mg_fsi_candidates true`；压力坐标、界面协同及四个压力—散度配对速度候选；可另开 `-monolithic_mg_pressure_supremizers true` | 36 个容器槽位不代表独立模式数；离散响应仅在细层、原 spectral 预算内最多两个方向；小例通过，网格目标仍开放，不构成 inf-sup 证明 |
| P1 / Adaptive Vanka Patch Selection | `-monolithic_mg_adaptive_patches true`、`-monolithic_mg_patch_strength` | 所有活动实体核心仍平滑，只在界面或强外耦合区域扩展重叠；只支持 Vanka |
| P1 / Partial Assembly | `-fsi_partial_assembly true`；每次当前 Newton 线性化准备流体/ALE、固体中间系数 | 依赖精确 matrix-free；为现有低阶单元实现，不是任意阶积分库 |
| P1 / Native FP32 Multigrid | `-monolithic_mg_native_fp32 true`；保留 float 系数，patch 按字节选择 CSR/稠密表示，刷新前释放旧 native 层 | 外层 P、粗解、PETSc 向量及 MPI 数据仍为 FP64；只支持 Vanka；下文给出一次同源 RSS 对照，不能外推至所有规模 |
| P1 / SIMD Matrix-free Kernels | `-fsi_matrix_free_simd true`；四 lane 的流体/ALE及固体缓存方向核，支持尾批次 | 同时要求 partial assembly；压力面等边界小核仍单独作用，回写保持原顺序 |
| P1 / Matrix-free MPI Overlap | `-fsi_matrix_free_overlap true`；方向 halo 发起后先计算纯 owned 单元，再计算 halo 单元及端口 | 实际隐藏的通信时间依赖 MPI progress 和 owned 工作量；仅有分组计数不能证明加速 |
| P2 / Adaptive Inexact Newton | `-nonlinear_inexact_newton true`；有界 EW-II 风格 forcing | 中间线性修正使用当次 forcing 门槛；最终独立物理字段/约束验收保持原规则 |
| P2 / Krylov Subspace Recycling | `-nonlinear_krylov_recycle N`；保存有限个成功修正方向，以当前算子投影生成初值 | 跨兼容求解会话复用的是 solution/correction span；没有实现 GCRO-DR 或保存完整 Arnoldi 基 |
| P2 / Large-scale FSI Benchmark | `scripts/benchmark_fsi_block_scaling.py --campaign strong/weak` | 驱动记录真实节点和自由度并设验收下限；驱动存在不等于百万自由度或多节点试验已完成 |

## 2. 默认值、依赖与前缀

新增性能优化开关默认关闭；`cycle` 默认 `v`，recycling 容量默认 0。用于阻止假收敛的
`-nonlinear_true_residual` 对 `monolithic_mg` 默认开启，其他 recipe 默认关闭。
`-fsi_matrix_free_overlap`
未显式设置时跟随既有的 `-fsi_overlap`，所以开启装配 overlap 的 matrix-free 配置也会选用方向重叠。
`native_fp32` 自动启用层内单精度算术，不必再重复传 `single_precision=true`。

| 参数 | 默认值 / 范围 | 关系 |
| --- | --- | --- |
| `-fsi_matrix_free`、`-fsi_reduced_pc`、`-fsi_partial_assembly`、`-fsi_matrix_free_simd` | 均默认 false | 后三项要求精确 matrix-free；SIMD 还要求 partial assembly |
| `-nonlinear_matrix_free_pc_interval` | 1，范围 1–1000 | 控制 assembled P 的刷新；每个新 solve 首次刷新，每个 Newton 状态的精确 Jv 仍重新准备 |
| `-nonlinear_true_residual` | `monolithic_mg` 默认 true，其他 recipe 默认 false | 对候选 Krylov 收敛检查当前原算子残量；适用于 assembled 和 matrix-free 的 unpreconditioned FGMRES/PIPEFGMRES |
| `-monolithic_mg_field_scaling`、`-monolithic_mg_fsi_candidates`、`-monolithic_mg_adaptive_patches`、`-monolithic_mg_native_fp32` | 均默认 false | 属于实际 MG KSP 的前缀命名空间 |
| `-monolithic_mg_pressure_supremizers` | false | 要求 `fsi_candidates=true` 且 `spectral_modes>0`；仅细层使用离散压力/速度块生成局部响应 |
| `-monolithic_mg_spectral_modes` | 2，范围 0–8 | 每个聚合体的额外模态名额；supremizer 从中替换最多两个，启用 supremizer 时不能为 0 |
| `-monolithic_mg_cycle` | `v`、`w` 或 `k`，默认 `v` | W-cycle 再访问一次粗层；K-cycle 在最多两个递归预条件 Arnoldi 方向中最小化加权粗残量，要求 flexible outer Krylov |
| `-monolithic_mg_max_coarse_ratio` | 范围 (0,1]；启用 `fsi_candidates` 时默认 0.8，否则默认 1 | 若 proposed coarse rows / parent rows 超过该值，停止继续粗化，以 parent 为最粗层求解 |
| `-monolithic_mg_patch_strength` | 0.25，范围 [0,1] | 行的实体外绝对系数和 / 整行绝对系数和达到阈值时扩展该实体 patch |
| `-monolithic_mg_patch_overlap` / `-monolithic_mg_coarse_patch_overlap` | 1 / 0 | adaptive 只决定是否使用所配置的重叠；粗层默认不额外沿稠密图扩展 |
| `-nonlinear_krylov_recycle` | 0，范围 0–32 | 同时存储有限个分布式修正向量；0 关闭 |
| `-nonlinear_forcing_initial` / `-nonlinear_forcing_max` | 0.1 / 0.5 | `0 < initial <= max < 1`，原 KSP rtol 不大于 initial |
| `-nonlinear_forcing_gamma` / `-nonlinear_forcing_alpha` | 0.9 / 1.5 | `0 < gamma <= 1`，`1 < alpha <= 2` |

精确 matrix-free 使用右预条件 `fgmres` 或 `pipefgmres`，拒绝 `-fsi_fd_tangent`、替换精确算子的
SNES FD/MF 选项及冲突的 Jacobian/PC 手工 lag/reuse 或 EW 控制；另一套
`-nonlinear_adaptive_pc` 不能与精确 matrix-free 组合。Inexact/recycling 也要求普通
fresh Newton 和 flexible GMRES；recycling 拒绝另一套非零初值、Knoll 或 Fischer guess 策略。
PETSc KSP 的 diagonal scaling 与这里的 inexact/recycling 不兼容；MG 内部 `field_scaling` 是另一条明确实现的路径，可组合使用。
真实残量 guard 要求原 convergence test 依据残量判断；`-ksp_convergence_test skip` 和
`-ksp_converged_maxits` 可以不看残量就返回成功，与该 guard 不兼容。

含 RCR 端口的整体 MG 使用 `-pc_plan_rcr_ports true`，bulk 层级在端口 Schur 内部：

| 控制对象 | 无 RCR wrapper | 有 RCR wrapper |
| --- | --- | --- |
| MG 选项 | `-monolithic_mg_*` | `-rcr_bulk_monolithic_mg_*` |
| 最粗层 KSP | `-monolithic_mg_coarse_*` | `-rcr_bulk_monolithic_mg_coarse_*` |
| FSI 方向作用、P、forcing、recycling | `-fsi_*`、`-nonlinear_*` | 名称保持相同 |
| 最外层 Krylov | `-ksp_*` | 名称保持相同 |

整体 MG 不消费旧块预条件树的 `-pc_plan_velocity_solver`、`-pc_plan_schur_approx` 或
`-pc_plan_patch_*`；这些选项不可混入整体 MG 命令。

## 3. 可逐项比较的运行示例

以下命令使用已配置的 Release/PETSc 3.23.7 环境及相同案例、分区和物理验收设置。
输出目录、构建来源和 MPI launcher 应按实际环境设置。

```bash
FSI_BIN=./build/release/eonsim
FSI_MPI=/path/to/locked/environment/bin/mpiexec
FSI_CASE=cases/fsi/domains/case.yaml
FSI_PART=results/fsi_scale_part2

"$FSI_BIN" -case "$FSI_CASE" -prepare "$FSI_PART" -parts 2

FSI_RUN=("$FSI_MPI" -n 2 "$FSI_BIN" -case "$FSI_CASE" -partition "$FSI_PART"
  -pc_recipe monolithic_mg -ksp_type fgmres -ksp_pc_side right
  -ksp_norm_type unpreconditioned -ksp_rtol 1e-12 -ksp_atol 1e-15
  -ksp_max_it 1500 -ksp_gmres_restart 100
  -monolithic_mg_coarse_limit 48
  -linear_report -solver_report -pc_plan_report -fsi_assembly_report)

# 精确方向作用和完整 assembled P，作为同路径对照。
"${FSI_RUN[@]}" -fsi_matrix_free -output results/fsi_full_p.vtu

# 更小的 P 符号图；先独立比较此项。
"${FSI_RUN[@]}" -fsi_matrix_free -fsi_reduced_pc true \
  -output results/fsi_reduced_p.vtu

# 加入冻结中间量、批量方向核及方向 halo 重叠。
"${FSI_RUN[@]}" -fsi_matrix_free -fsi_reduced_pc true \
  -fsi_partial_assembly true -fsi_matrix_free_simd true \
  -fsi_matrix_free_overlap true -nonlinear_matrix_free_pc_interval 2 \
  -output results/fsi_cached_actions.vtu

# 在同一精确作用上选择缩放、粗空间、选择性 patch 和 native FP32。
"${FSI_RUN[@]}" -fsi_matrix_free -fsi_reduced_pc true \
  -fsi_partial_assembly true -fsi_matrix_free_simd true \
  -fsi_matrix_free_overlap true \
  -monolithic_mg_field_scaling true -monolithic_mg_fsi_candidates true \
  -monolithic_mg_adaptive_patches true -monolithic_mg_patch_strength 0.25 \
  -monolithic_mg_native_fp32 true -output results/fsi_compact_mg.vtu
```

`coarse_limit=48` 是小例参数，源码默认值为 96。要比较 W/K-cycle，可在同一命令分别增加
`-monolithic_mg_cycle w` 或 `-monolithic_mg_cycle k`。要比较中间线性精度及跨步初值，可分别增加
`-nonlinear_inexact_newton true` 和 `-nonlinear_krylov_recycle 4`；这些选择应保留独立对照，
不能从全部开关组合的单次运行判断每项贡献；单项缩放与缩放/候选/精度组合的收敛行为也可能不同。
从 `30e2941` 起，物理测试预设 `mono_kcycle` 和 `mono_all` 显式使用 K-cycle；
`mono_optimized` 显式使用 V-cycle，提供相同缩放、候选、patch 和精度组合的循环对照。
`mono_kcycle` 保持严格线性容差，`mono_all` 另含 inexact Newton。此前 `116836b` 的
`mono_all` 使用 V-cycle；比较历史结果时必须同时锁定二进制和 driver，不能只按模式名称合并。
从 `50b41ae` 起，`mono_supremizer` 是 `mono_optimized` 的严格 V-cycle 配置加上
`-monolithic_mg_pressure_supremizers true`，便于隔离新增离散配对的作用；当前 `mono_all`
也加入该开关。RCR bulk 使用 `-rcr_bulk_monolithic_mg_pressure_supremizers true`，同样要求
带 `rcr_bulk_` 前缀的 `fsi_candidates=true` 与正的 `spectral_modes`。

## 4. P、精确 Jv 与缓存的数学关系

设当前 Newton 状态为 \(x_k\)，原始残量为 \(\mathcal R(x_k)\)，精确线性算子为
\(J_k=\mathcal R'(x_k)\)。`-fsi_matrix_free` 作用于 \(J_kv\)，assembled 矩阵只提供预条件近似 \(P_k\)。
`reduced_pc` 在物理分量层面删除 P 的流体方程/ALE 列依赖，再分别应用测试和试探约束映射。
因此 AIJ 预分配和 COO 索引列表都变小，而不是先分配完整 Jacobian 图再将部分值置零。

流体 u/p、各 ALE 扩展分量、结构弹性及共享界面速度贡献保留。流体方程和入口压力面对应的
ALE 导数不进入 reduced P，移动 RCR 端口的额外几何与压力耦合仍单独装配。完整方向作用继续
包含流体几何、网格速度、稳定化、压力面、结构、支撑、端口和消元链系数。
[耦合图](../../include/eonsim/fsi_coupling_pattern.hpp)、[布局](../../src/fem/reduced_layout.cpp)、
[装配与方向映射](../../src/physics/fsi.cpp)

Partial assembly 在每次冻结当前 Newton 状态时准备流体/ALE 的 132 个系数及入口压力面几何，
固体准备 27 个系数。内容包括体积、形函数梯度、当前速度/压力中间量、稳定化导数系数、
参考 ALE 刚度及有限变形固体所需的 \(F_s^{-T}\) 和体积响应，其中 \(F_s\) 为固体变形梯度。
缓存不保存完整 nodal tangent。

P 被复用时，当前 Jv 的缓存仍更新；线搜索试探残量不覆盖冻结线性化。缓存准备保留几何、
材料及有限值检查，失败通过共同错误路径处理。局部缓存核与原 assembled 切线分别实现，
验证直接比较二者，避免使用新缓存公式自我验证。
[流体/ALE 核](../../src/physics/fsi_element.cpp)、[固体核](../../src/physics/solid_element.cpp)

SIMD 将至多四个单元的系数与方向转成独立 lane，在流体/ALE、固体体积核中批量运算。
尾 lane 使用零方向，局部压力面及支撑按各自精确小核补充；PETSc 插入发生在批量算术完成后，
保持原单元顺序。是否生成机器 SIMD 必须检查实际编译对象，不能只看 pragma 或批量 API。

## 5. MG 缩放、粗空间和选择性平滑

本节将 assembled 预条件矩阵记为 \(A\)，层间插值记为 \(Z\)，避免将预条件矩阵与插值混用同一符号。
物理缩放按流体、压力、结构、ALE、刚体、端口及其他语义组的全局系数极值生成左右对角矩阵，
在 MG 内形成

\[
A_s=L A R,\qquad B(r)=R\,M_s^{-1}(Lr).
\]

物理候选同步变为 \(R^{-1}N\)。约束 identity 行保持精确修正，外层求解和最终物理残量使用原尺度。
源数值改变后，缩放及其层级共同重建；这会增加 setup 成本，需与迭代变化一起报告。

`116836b` 在第一层采用 \(Z^T W\) 限制，其中 \(W=R L^{-1}\)，逐项为 \(R_{ii}/L_{ii}\)，从而

\[
A_c=Z^T W A_s Z=(RZ)^T A(RZ).
\]

第一层粗残量同时使用 \(Z^T W r_s\)，使原物理坐标中的测试和试探空间都为 \(RZ\)。后续粗层
继续普通 Galerkin。W 在 FP64 或 native FP32 限制之前作用，仅保留其对角向量；setup 的加权
临时 FP64 矩阵及 product 引用释放，不增加长期完整 fine 矩阵副本。此前 \(Z^T LARZ\) 也是一种
可定义的缩放坐标粗近似；本次改变的是粗测试空间的数值选择，以保持原物理 Galerkin 投影，
两版精细方程及物理接受均保持原定义。

已有候选包含各向量场平移/旋转和压力常数等模式。`fsi_candidates` 增加归一化参考坐标的压力
线性模式、真实界面上的协同平移/旋转和界面压力模式，并加入四个流体速度候选。在归一化参考坐标
\(\hat x\) 中，向量场 \(\hat x/3\) 的散度为 1，\(e_i\hat x_i^2/2\) 的散度为 \(\hat x_i\)，
分别为常数及三个线性压力模式提供非零散度配对。实现使用节点采样，约束行排除；上述连续场
关系不意味着 Tet4 离散散度精确匹配，也不构成 inf-sup 证明。候选容器共 36 个槽位，实际
独立列数取决于本地语义、约束和去相关结果。局部秩揭示去掉相关列，约束插值保持
\(Z N_c=N_f\)。额外谱模态仍来自聚合体局部正规能量，不是全局困难误差的完整谱分解。

### 离散 pressure-supremizer：原预算内的局部响应

`50b41ae` 的 `pressure_supremizers` 默认关闭。它只在保留原物理语义的细层工作：从每个
聚合体已有的纯压力候选列出发，读取该聚合体的实际离散压力行/流体速度列耦合。若开启
field scaling，定义 \(B_\omega=(W A_s)_{p,u}\)；未缩放时 \(W=I\)。这与随后形成
\(Z^T W A_s Z\) 的测试权重相同，没有用连续散度关系替代实际离散块。

局部速度能量使用正对角代理

\[
H_{jj}=\sum_{i\in\text{聚合体流体速度行}} |(W A_s)_{ij}|,
\qquad D=(\min_j H_{jj})H^{-1}.
\]

若必要的对角量为零，当前聚合体不生成该配对。设 \(V\) 为已有全部粗基列限制到本地流体
速度后的列空间，\(Q\) 是 \(D^{1/2}V\) 的 QR 正交基。压力方向 \(q\) 的代理响应为

\[
s(q)=D^{1/2}(I-QQ^T)D^{1/2}B_\omega^T q.
\]

实现对 \(B_\omega\) 作共同尺度归一化以保持可表示性；这不改变响应 span。响应避开已有速度
空间，由小型对称 Gram 问题选择缺失响应能量较大的压力组合，再在纯速度子空间内去相关。
它不是完整 \(A_{uu}^{-1}B^T\) 求解，也没有新增内部 KSP。最多接受
`min(2, spectral_modes)` 个独立方向，并从原 spectral 名额中扣除实际使用数；未形成有效配对
的名额继续用于原谱增强。聚合体上限、平滑次数和粗解调用预算不因此增加，但局部 QR 和
特征求解会增加 setup 工作。

Energy descent 冻结组成所选压力组合的原压力基列及响应列；冻结标记随 transfer halo
传递，远端列和空 owner 也参与一致通信。这样选中配对的
\(q_i^T B_\omega s_j\) 在 energy 更新前后保持同一 FP64 coarse 子块。代码随后从实际形成的
`MatPtAP` 粗矩阵读回该子块，检查相对变化不超过 `1e-10`，并报告选中行归一化块的最小
奇异值。后续 mixed scalar 层不再构造新响应；源系数发生数值变化时重新建立这一 enrichment。

`pressure_supremizer_modes`、`pressure_paired_aggregates`、`pressure_pair_min_singular`
和 `pressure_pair_relative_change` 只描述被选中的局部配对。它们不能保证其他压力方向、后续
粗层或全局 inf-sup 稳定性；尤其 `1e-10` 是 **FP64 setup** 审计门槛，不能解释为 native FP32
transfer 量化后的精确配对保证。Native 作用仍必须通过独立的原算子真实残量和物理门槛。
该机制已有同源 MPI 检查及两组物理对照，实际配对与窗口结果见第 10 节；它们支持本次有限
输入上的正确性和局部配对保护，尚未实现预设的近网格无关目标。
[实现与审计](../../src/algebra/monolithic_fsi_mg.cpp)、[范围契约](../../include/eonsim/monolithic_fsi_mg.hpp)

增强候选有局部秩下限，细分更多层可能只减少很少行。`max_coarse_ratio` 以 proposed/parent
全局行数比限制这类弱粗化：超过上限时放弃该 proposed 层，以现有 parent 作为最粗层。
`weak_coarsening_stop_rows` 和 `weak_coarsening_proposed_rows` 报告停止处的两种规模；未触发时为 0。
这是层级工作量控制，不改变物理/Krylov 容差，也不保证更少层一定更快；最粗问题可能因此更大。

Adaptive Vanka 始终保留每个活动实体核心；若实体在真实界面上，或者某行的实体外绝对耦合
占比达到 `patch_strength`，才增加所配置的 overlap。数值变化时重新选择，不以一次固定选择
冒充动态适应。粗层默认 overlap 0，以完整混合聚合体为核心；没有删除弱区域方程。

### 有界 K-cycle 与实际工作计数

`cycle=k` 在非最粗层的第一次递归修正后，以当前完整粗层作用 \(A_c\) 和 RHS \(b_c\) 定义

\[
\min_{\alpha_1,\alpha_2}
\left\|D_c\left(b_c-A_c(\alpha_1z_1+\alpha_2z_2)\right)\right\|_2,
\qquad (D_c)_{ii}=\frac{1}{\max_j|(A_c)_{ij}|}.
\]

\(z_1\) 来自第一次递归作用；需要第二个方向时，由 Arnoldi 方向生成下一次递归输入。
实现对作用向量做两遍 modified Gram–Schmidt，并同步变换修正向量，避免构造正规方程。
方向是否相关按该层使用的算术精度判断；不相关方向最多两个，不在内部无界迭代至某个容差。
实际返回修正还会重新计算上述加权残量；若有限残量增大，则返回子空间内的零修正并计为拒绝；
非有限作用沿既有 PC 失败路径传播。粗方程、候选和外层真实残量门槛保持原定义。

含 \(L\) 层时，每个非平凡 MG 作用至多调用最粗求解 \(2^{L-2}\) 次；\(L\le2\) 时为一次。
这是粗求解调用次数上界，不是整个算法的网格无关复杂度证明。额外粗 matvec、工作向量及
dot/norm 请求必须计入成本。`monolithic_mg_stats` 的计数随 hierarchy 生命周期累积，数值重建
时保留；按 rank/path/solver generation 取末值，不能将每个接受步的累计快照直接相加。
RCR response 的内部应用也包含在这些计数中。`coarse_krylov_reductions` 表示 VecDot/VecNorm
请求数，不能等同于实际 MPI 包数或延迟事件，范数可能命中缓存。

初始源码在增强候选约束张满某行插值支撑时出现实际失败：数学上应为零的投影下降方向只剩
舍入噪声，精确线搜索又用极小曲率放大该噪声，破坏候选重构。`707a6a6` 在投影方向不超过
`1024 * epsilon * 未投影梯度范数` 时归零这一数值噪声。它没有删除候选、增大重构容差或放宽
物理门槛。失败及修复后的相关验证分别保存在证据索引中。
[MG 实现](../../src/algebra/monolithic_fsi_mg.cpp)、[patch 选择](../../src/algebra/interface_patch_pc.cpp)

## 6. Native FP32 的存储边界

`single_precision` 使用行缩放 float CSR、float 层矩阵/传递算术及局部 float 因子，保留 FP64 setup。
`native_fp32` 在此基础上释放非粗层 FP64 层矩阵、传递矩阵、patch 子矩阵，以及 Galerkin product
对旧操作数的引用。局部残量细化使用保留的均衡 FP32 系数；不能表达的 FP32 因子明确失败，
不隐藏地重新建立 FP64 因子。数值刷新重建临时 setup，再回到紧凑存储。

`30e2941` 针对实际 RSS 回归调整了存储与生命周期。Native 数值变化时先保留 fine metadata，
释放旧 coarse solver、旧层的系数/因子及工作向量，再建立新 setup，避免两代 hierarchy 同时
存活。失败保留不可应用的 metadata-only 状态，后续合法 refresh 可重新构造；外层 P 的所有权
不受影响。重建过程仍需要 FP64 setup，不能仅凭旧代提前释放推断峰值已经下降。

Patch 系数按实际字节选择稠密 float 或 CSR。CSR 使用经过范围检查的 uint16 局部列号和
uint32 行偏移；只有系数与索引合计比稠密 float 更小时才选择 CSR，LU 仍是稠密 float。
转换直接读取稀疏行，删除了逐 patch 的临时稠密 double 矩阵。Native release 后还释放 setup IS、
不再使用的语义副本和 double 工作数组。Identity lifting 直接提取约束列，避免复制整份 FP64
矩阵；是否可以使用零 lifting 由全局判定决定，空 owner 仍参与需要的通信。

Float 稀疏数组按实际 nnz 预分配；去重后的 halo 列表压缩容量，避免 `erase` 后仍常驻 nnz
大小的索引缓冲。系数字节采用独立口径：`fp32_value_bytes` 包含 native patch/lifting 系数，
不包含 LU 因子；`factor_bytes` 单独计 LU；`native_index_bytes` 只计局部 patch CSR 索引。
这些量都不能替代进程 RSS。

必须分别观察以下存储：

| 对象 | Native 路径实际状态 |
| --- | --- |
| 非最粗层稀疏系数、传递系数、局部矩阵/因子 | FP32 系数；相关 FP64 setup 副本释放 |
| 最外层 assembled P | 仍为 FP64；可用 reduced P 单独减少其图 |
| 最粗层算子与求解 | 仍为 FP64 |
| PETSc 向量、外层 Krylov、MPI 交换数据 | 仍为 FP64；没有实现全链路 FP32 通信 |
| 索引、语义、halo 元数据及运行时开销 | 另外占内存，不包含在单纯系数字节指标中 |
| setup 峰值与进程峰值 RSS | 同源 n8 对照的最大 rank 归一化峰值下降约 4.06%；未独立剖析 setup 瞬时分配峰值 |

`pc_monolithic_mg_storage` 的 byte 字段是各 rank 的系数计数，最外层 P 不算作 MG 自己的额外
FP64 副本。合并各 rank 后也不能直接等同于 RSS。
[float 稀疏存储](../../include/eonsim/native_float_sparse.hpp)、[层级释放](../../src/algebra/monolithic_fsi_mg.cpp)

## 7. MPI、inexact Newton 与 recycling 的接受规则

方向作用先发起 ghost 更新，用可用的 owned 方向计算不依赖远端 aliases 的单元；通信完成后更新
halo 方向并计算其余单元。端口标量和当前面几何可能涉及远端值，放在完成通信后的阶段且只计算一次。
所有 owned/halo 路径共享冻结的完整状态，错误路径仍排空通信并拒绝该 solve。

### 候选 Krylov 收敛的真实残量保护

缩放或不精确预条件可能使 Krylov 递推残量低估实际 \(\|b-Jx\|_2\)。
`-nonlinear_true_residual true` 在原 convergence test 首次提出正停止原因时，使用公共
`KSPBuildResidual` 构造当前修正的残量，再把真实范数交给同一个原测试。它不替换容差，
不重新调用 `KSPSolve`，也不重置最大迭代预算。尚未满足原条件时继续当前 Krylov 过程，
普通 restart 按 PETSc 原流程重建残量；如果真实拒绝同时遇到 happy breakdown，PETSc 仍可能
返回 `KSP_DIVERGED_BREAKDOWN`，不能把这种情况改称成功或保证一定重启。

候选原因先保存在局部变量，构造残量时回调公开的停止原因必须仍为 `ITERATING`，最后才发布
真实检查的原因。初版 `8410818` guard 曾提前向传入的 reason 写入正值：PETSc 3.23.7 的
`KSPBuildSolution` 公共入口因此把求解视为已结束，复制旧 restart 基解，跳过当前 Krylov
解重构。结果是大量错误拒绝和 PIPEFGMRES 的 happy-breakdown 失败。修复这一顺序不需要
访问 PETSc 私有字段；初版失败与修复后复验须分别保留，不能因某个物理对照通过而遗漏其算法缺陷。
[PETSc 3.23.7 公共解/残量构造入口](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/itfunc.c)

### 中间线性精度与最终物理接受

Inexact Newton 根据连续 Newton RHS 范数比生成有界 forcing，原 KSP rtol 是下界。
每次成功线性修正都用当前精确算子检查

\[
\|J_k s_k-b_k\|_2\le a_{\rm KSP}+\eta_k\|b_k\|_2,
\]

并允许规定的浮点舍入余量。最终接受前重新计算原物理残量，检查各字段和约束，之后才共同提交历史。
因此中间线性残量不能再机械套用未启用 forcing 的固定紧门槛；最终字段/历史与直接参考的比较门槛保持不变。

Recycling 保存成功 Krylov 修正的有限独立方向。每次新线性系统使用当前 \(J_k\) 重新计算其像，
正交化后形成最小残量投影初值；相关或有害投影丢弃，失败/不兼容会话清空缓存。
它不复用旧 Jacobian、旧 RHS 或物理状态，也不保存整个 Arnoldi 过程。
额外 Jv、正交化、归约和分布式向量存储都应计入成本。
[非线性策略及真残量检查](../../src/algebra/nonlinear_system.cpp)

## 8. 应读取的报告

| 报告 | 用途与口径 |
| --- | --- |
| `fsi_preconditioner` | `reduced`、`stores_full_jacobian` 记录选择；再与同案例完整 P 的 `solver_report nnz` 对比确认真实图减少 |
| `fsi_action_report` | `prepared_cells`、`cached_actions`、`simd_batches` 为实际工作计数；`cache_bytes` 为当前单元缓存字节；`owned_cells` / `halo_cells` 为分组规模 |
| `solver_report` | 实际 DoF、P nnz、矩阵作用/准备/复用次数、`matrix_free_overlapped_actions`、`true_residual_checks` / `true_residual_rejections`、forcing/recycle 计数、时间及 RSS |
| `pc_monolithic_mg` / `pc_monolithic_mg_level` | 真实层数、缩放/候选/循环开关、`max_coarse_ratio`、弱粗化规模、重构/能量；`pressure_supremizers` 记录选项，另读四个 `pressure_*` 配对统计确认实际生成和 FP64 setup 审计 |
| `pc_monolithic_mg_smoother` | 每 rank/层的核心及扩展 patch 数、覆盖、最大 patch、FP32/FP64 系数、`factor_bytes`、`native_sparse_patches` / `native_dense_patches` 和 `native_index_bytes` |
| `pc_monolithic_mg_storage` | 已保留 FP32、仍保留 FP64、已释放 FP64 系数字节；不是整个进程内存 |
| `monolithic_mg_stats` | 生命周期累计的应用、层 matvec、零起步跳过、粗求解/迭代、平滑应用、K-cycle 方向/降秩/拒绝/归约请求和最大粗残量比；按 generation 分组取末值 |
| `linear_residual` | 当前原算子的显式残量；forcing 时同时读取 `requested_rtol`、`requested_atol` 和 `forcing` |
| `field_residual` | 最终独立字段及约束验收；检查所有接受步的完整记录 |
| `solver_rank_report` | 真实 rank/主机、owned/ghost 及局部计时；`rss_bytes`、归一后的 `peak_rss_bytes` 和原始 `system_peak_rss_bytes` 分别记录；节点数来自实际主机记录 |

`matrix_free_overlap_seconds_rank0` 记录可重叠阶段的工作，不是“节省了多少通信时间”。
只有同环境、同输入、固定容差的配对计时才能评价收益。
`true_residual_seconds_rank0` 包含构造当前解、额外 Jv/矩阵作用及范数计算；在 matrix-free 配置中，
这些 Jv 也计入 `matrix_free_actions` 和 `matrix_free_seconds_rank0`，两段时间存在包含关系，不能相加为互斥阶段总耗时。

每次报告的 RSS 口径为

\[
\mathrm{peak}_{\rm normalized}
=\max(\mathrm{RSS}_{\rm observed\ current},\mathrm{peak}_{\rm raw\ OS}).
\]

Linux 上原始系统值来自 `getrusage`，PETSc 的当前 RSS 来自另一采样途径，两者可能暂时不满足
同一样本的 peak/current 大小关系。归一后的 peak 保证不低于本次观测的 current；原始系统值
保留在 `system_peak_rss_bytes`，没有将归一值冒充纯 `ru_maxrss`。汇总的 peak max/sum 使用
归一值。初始 cluster smoke 因这两种 API 的比较不一致被拒绝，其失败记录保留；修复统计口径
不等于新增了多节点或大规模运行证据。

## 9. 定向验证和大规模驱动

局部方向核测试为 `fsi_element_jacobian`、`solid_element_jacobian`，包括缓存/原切线、混合参数、
四加三尾批次及非法状态。代数接口检查涵盖 `monolithic_fsi_mg_mpi*`、`matrix_free_mpi*`、
相关 patch/层平滑器及非线性接受测试。测试选择应按受影响路径确定，不因为文档更新重跑数值测试。

物理驱动支持独立模式和组合模式，检查直接参考轨迹、保存场、历史、真残量及实际执行计数：

```bash
FSI_BUILD_SOURCE=50b41ae19067bd8853a482ab853805e23c096ec5

python tests/verify_fsi_multigrid.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" \
  --build-source "$FSI_BUILD_SOURCE" --work results/fsi_scale_physical \
  --sections default moving \
  --modes mono_reduced mono_reduced_coo mono_partial mono_simd mono_overlap \
          mono_scaled mono_candidates mono_adaptive mono_native_fp32 \
          mono_optimized mono_kcycle mono_supremizer mono_inexact mono_recycle mono_all
```

`--build-source` 必须是实际二进制的完整 40 位源码提交，不能用后续文档提交代替。
驱动另存当时驱动提交、二进制和输入/分区/输出的 hash，并保留失败原件。

Strong/weak 路径用于有实际集群分配时运行；下面的网格参数需按资源设置，资格由运行得到的
约束后 DoF 和主机记录决定。`--minimum-nodes` 对每个参考和候选运行都生效，要求两节点时不能
从单 rank 配置开始，也不能只增加同节点 rank 数。

```bash
# FSI_LARGE_N、FSI_HOSTFILE 应由本次资源分配设置。
python scripts/benchmark_fsi_block_scaling.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_BUILD_SOURCE" \
  --work results/fsi_strong --campaign strong \
  --subdivisions "$FSI_LARGE_N" --ranks 2 4 8 \
  --reference-mode mono --modes mono_mf mono_all \
  --minimum-dofs 1000000 --minimum-nodes 2 --steps 5 --timing-repeats 3 \
  --mpi-arg=--hostfile --mpi-arg="$FSI_HOSTFILE"

# 每个 subdivision 与对应 rank 数一一配对，实际 DoF/rank 再检查。
python scripts/benchmark_fsi_block_scaling.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_BUILD_SOURCE" \
  --work results/fsi_weak --campaign weak \
  --subdivisions "$FSI_WEAK_N2" "$FSI_WEAK_N4" "$FSI_WEAK_N8" --ranks 2 4 8 \
  --reference-mode mono --modes mono_all --weak-load-tolerance 0.1 \
  --minimum-dofs 1000000 --minimum-nodes 2 --steps 5 --timing-repeats 3 \
  --mpi-arg=--hostfile --mpi-arg="$FSI_HOSTFILE"
```

集群路径继承调用环境和 launcher 参数，不强制 TCP；调用者需安排 scheduler、进程放置及共享文件系统。
现有网格生成和 METIS preparation 仍是串行全网格工作，不能报告为分布式前处理。
大规模路径用 SQLite 暂存最终场和拓扑，避免 Python 审计器持有完整全局字段字典；它检查全部接受历史/
线性残量和最终保存场，不保存所有中间体场。默认大规模参考为同方程迭代 `mono`，可以选择 direct，
参考方案本身也必须成功。

`--timing-repeats 0` 只执行正确性 smoke；至少 3 才进入计时样本。Strong 对同一网格比较不同 rank，
weak 按显式网格/rank 配对，并用实际 DoF/rank 漂移标记 `weak_load_comparable`。
未通过规模、放置、物理或负载可比性检查的结果不能改写为有效扩展效率。

## 10. 已有证据与仍待完成的结论

当前生产源码 `50b41ae` 的 MG MPI 1/2/4 检查通过，原件为 `unit-50b41ae-summary.json`。
同源严格网格 9/9、default/moving 物理 15/15 通过，新增离散压力响应的局部配对统计也得到
实际检查，但网格窗口目标仍未达到，详细结果列在本节末尾。下列历史记录保持各自源码来源，
尤其 `30e2941` 的 K-cycle/RSS 结果没有启用新增响应，不能将旧通过数算到新路径。

初始小例的 reduced P 观察到约 22%–23% 的 nnz 减少：307 DoF 双域案例与 350 DoF 移动 RCR 案例
分别约为 23.42% 和 22.00%，AIJ/COO 对照均保留同一物理解。这个范围说明当前图确实不同，
不预测其他网格的固定节省比例，也不代表总 RSS 同比例下降。

初始 Release 对象的 `fsi_element_action_batch` 和 `solid_element_action_batch` 分别包含 468 和
182 条 packed double 算术指令；反汇编证据带 source/tree 和对象 SHA256。它确认实际 SSE2 代码生成，
不构成吞吐或端到端加速测量。后续编译器、选项和目标架构应重新检查对应对象。

正确的 Krylov guard 在 `6378f4cca035bcf8a29150ef21588528c70aa824` 通过
`matrix_free_mpi1/2/4`，同源 moving-RCR 的 direct、`mono_scaled` 和 `mono_mf_pipe` 三次物理
对照也通过。`mono_scaled` 实际进行了 176 次候选检查、167 次拒绝、441 次外层迭代，仍满足原
真实残量和物理场门槛；这证明拒绝分支得到实际执行，不表示该配置的迭代成本已经理想。
原件见 `residual-guard-6378-summary.json` 及证据索引。

`116836b9d4143a280759a2e69e6c1b31156fb616` 的 `monolithic_fsi_mg_mpi1/2/4` 已通过，
包括固定物理候选 span、关闭能量/谱变化时的两层缩放投影不变量和弱粗化停止检查。
该版本的固定 2-rank、n=4/6/8 网格 campaign 已完成 **15/15** 物理通过，分别运行 direct、
`mono`、`mono_scaled`、`mono_optimized` 和当时仍为 V-cycle 的 `mono_all`。
另一次 default/moving campaign 的 15/15 通过覆盖 307/350 DoF、变步长及 NH/RCR；独立审计
核验了 45 个接受步、119 次线性校正和 200 个体场分片。两批结果按各自 receipt 分开记录。
原件对应 `grid-scaling-116-summary.json` 和 `physical-116836b-independent-audit.json`。

`30e2941` 的 patch、MG、层 smoother MPI 1/2/4-rank 共九项检查通过，包含 compact native
表示、远端约束/空 owner、源 Mat 释放后作用，以及 native 重建失败后的恢复。
原件为 `unit-30e2941-summary.json`。同源 K-cycle 网格 12/12 物理通过，但有限窗口收敛目标
仍未达到；native-only RSS 两次对照均通过原门槛，具体工作量和存储观察见下文。

本轮保留两类初始失败：增强粗候选的投影舍入问题，以及 requested action accounting 未输出导致的
物理驱动证据检查失败。后者即使离线场/历史对照通过，也不能将原 campaign 改写为通过。
随后还记录了缩放路径的递推/真实残量差距、初版真实残量 guard 的公开 API 状态顺序错误，
以及 cluster smoke 的 RSS 口径检查失败。这些故障按各自源版本保留。
修正后的执行结果、受影响项复验和未受影响证据复用由
[本轮证据索引](../research/data/fsi-scale-01-2026-11-26/README.md)统一列出，本页不预填正在运行的总数或耗时。

### `707a6a6` 网格加密中间结果

以下为 2-rank、相同物理案例和固定线性容差下，每个 Newton 线性修正的平均外迭代数。
`mono_optimized` 在该版本组合字段缩放、FSI 候选、adaptive Vanka 与 native FP32；它不是未来
改进后的固定性能承诺。原件索引对应 `grid-scaling-707-summary.json`。

| 网格 subdivision | 实际约束后 DoF | 基线 `mono` | 增强组合 `mono_optimized` |
| ---: | ---: | ---: | ---: |
| 4 | 703 | 17.17 | 19.83 |
| 6 | 2299 | 25.17 | 38.33 |
| 8 | 5367 | 34.33 | 81.33 |

基线随加密约增长两倍，增强组合约增长 4.1 倍，并在全部三档增加迭代。这组结果未展示近似
网格无关收敛，组合机制也未改善该窗口的迭代成本。MG 改进仍在继续，后续结果应与此中间
结果分开记录。`mono_all` 含 inexact Newton，会改变每次中间线性求解的目标精度，不能用其
较低平均迭代数证明 MG 本身获得相同倍数的改善。

### `116836b` 后续网格与 native RSS 结果

保持原严格线性门槛，物理 Galerkin 限制修复后的网格窗口得到：

| 实际约束后 DoF | 基线 `mono` | V-cycle `mono_optimized` |
| ---: | ---: | ---: |
| 703 | 17.17 | 16.17 |
| 2299 | 25.17 | 26.67 |
| 5367 | 34.33 | 37.83 |

数值是每次 Newton 校正的平均外迭代数。增强组合的最大/最小比仍约为 2.34，未展示近似
网格无关收敛。当前 driver 在运行前声明 n=4/6/8、相同严格门槛下该比值不超过 1.3 的有限
窗口目标；达标也只支持此窗口。含 inexact 的模式标记为不适用于这个严格线性收敛目标。

同一 `116836b`、n8/2-rank/三步的 native-only 定向观察保留为内存回归证据：对 FP64 的
物理场差 `7.534806112374781e-13`，FGMRES 206→205 次；首次报告的系数合计
29,978,976→28,234,816 bytes，LU 40,025,728→20,012,864 bytes，但报告的 normalized peak
rank 最大值为 210,153,472→283,660,288 bytes，约增加 35%。原 FP64 与 native 是各一次观测，
没有计时结论；旧日志没有 rank ID 对应的 RSS 明细。原件为 `native-only-n8-116836b/independent-audit.json`。
这一失败推动了 `30e2941` 的生命周期、CSR 和容量修复；旧负结果继续保留。

### `30e2941`：K-cycle 通过物理检查，网格窗口目标仍未达到

固定同一二进制、n=4/6/8、2 ranks、三个时间步，direct、基线 `mono`、增强 V-cycle
`mono_optimized` 和同组合 K-cycle `mono_kcycle` 共 **12/12** 通过。各迭代模式均使用相同
严格线性门槛，不含 inexact forcing。下表列总外层迭代数除以六次 Newton 校正：

| 实际约束后 DoF | 基线 V | 增强 V | 增强 K |
| ---: | ---: | ---: | ---: |
| 703 | 103/6 = 17.17 | 97/6 = 16.17 | 98/6 = 16.33 |
| 2,299 | 151/6 = 25.17 | 160/6 = 26.67 | 148/6 = 24.67 |
| 5,367 | 206/6 = 34.33 | 227/6 = 37.83 | 202/6 = 33.67 |
| 平均迭代最大/最小 | 2.0000 | 2.3402 | 2.0612 |

三种模式都未达到运行前声明的 **≤1.3** 窗口目标。K 在后两档减少了增强 V 的外层迭代，
仍随加密明显增长，不能据此宣称近似网格无关或全局 inf-sup 稳定性。独立审计核验 36 个接受步、
72 次校正、192 个体场分片、639 个 artifact hash 和 15 个命令日志；最大场差
`9.398315459208106e-13`、历史差 `5.684341886080802e-14`、严格真实残量/原门槛最大
`0.008201356570989377`。原件为 `grid-kcycle-30-summary.json` 和
`grid-kcycle-30e2941-independent-audit.json`。

外层迭代需要与每次 PC 作用的工作一起看。以下 V/K 都指同一增强组合，分别有 4/4/5 层：

| subdivision | coarse solves，V→K | level matvec，V→K | smoother applications，V→K | K 的 VecNorm/VecDot 请求 |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 1→4 | 6→23 | 6→14 | 36 |
| 6 | 1→4 | 6→23 | 6→14 | 36 |
| 8 | 1→8 | 8→51 | 8→30 | 84 |

计数来自各 `(rank, path, solver_generation)` 的最后一个累计快照除以应用数，没有跨时间步
重复相加；归约请求不等于测得的 MPI collective 数。这次共享节点的 V 求解时间为
2.778/12.993/54.032 秒，K 为 2.840/13.157/57.771 秒：减少迭代没有转化成这次求解加速。
这些是一次正确性窗口中的时间观察，不是重复性能研究。

### `30e2941`：native-only 同源 RSS 配对

同一固定二进制在 n8、5,367 DoF、两个 rank、一个 host、三个时间步上各运行一次 FP64 与
native-only。双方共同增加 `-solver_rank_report`，除输出路径及
`-monolithic_mg_native_fp32 true` 外参数完全一致；均为 V-cycle，没有叠加 scaling、增强候选、
adaptive patch 或 K-cycle。FP64/native 分别接受三步、完成六次校正与 206/205 次外迭代，
各有六次真实残量检查、零次拒绝。真实残量/原门槛最大分别为 `0.006938085232256278` 和
`0.0069361029682299446`；两者全保存轨迹与最终场最大差 `7.534806112374781e-13`，
历史差 `2.3314683517128287e-15`，原场比较门槛仍为 `2e-9`。

| 内存观察（bytes） | FP64 | native-only | 变化 |
| --- | ---: | ---: | ---: |
| 最大 rank 的归一化峰值 RSS | 210,673,664 | 202,129,408 | −4.0557% |
| 各 rank 归一化峰值之和 | 316,915,712 | 303,300,608 | −4.2961% |
| 最大 rank 的原始 OS 峰值 | 210,206,720 | 202,129,408 | −3.8426% |
| 各 rank 原始 OS 峰值之和 | 316,448,768 | 302,882,816 | −4.2869% |

各 rank 的原始记录保留，不能把无序采样当成 rank 对应关系：

| 模式 / rank | 最后 current RSS | 最大观测 current RSS | 归一化峰值 | 原始 OS 峰值 |
| --- | ---: | ---: | ---: | ---: |
| FP64 / 0 | 210,673,664 | 210,673,664 | 210,673,664 | 210,206,720 |
| FP64 / 1 | 100,478,976 | 100,478,976 | 106,242,048 | 106,242,048 |
| native / 0 | 176,627,712 | 194,863,104 | 202,129,408 | 202,129,408 |
| native / 1 | 101,171,200 | 101,171,200 | 101,171,200 | 100,753,408 |

保留系数、LU 和索引也分别记录，而非只给释放的 FP64 字节。FP64 只报告一次初始存储，
native 的六次数值重建分别报告；由于原来的零系数在后续线性化中可能变成非零，native 首末
存储不能混为常数。

| 报告存储，跨 rank 合计（bytes） | FP64 初始/唯一报告 | native 首次 | native 末次 |
| --- | ---: | ---: | ---: |
| 保留系数合计，含 FP32 与剩余 FP64 | 29,978,976 | 13,430,456 | 15,867,872 |
| 局部 LU 因子 | 40,025,728 | 20,012,864 | 20,012,864 |
| native patch CSR 索引 | 0 | 2,764,526 | 3,967,996 |
| 上述三项合计 | 70,004,704 | 36,207,846 | 39,848,732 |

Native 的 sparse/dense patch 数从首次 1,193/230 变为末次 1,175/248，总数均为 1,423。
这些合计不包含其他稀疏索引、PETSc 向量、MPI 缓冲、外层 P 和分配器/运行时开销；也没有
逐项分离瞬时 setup 峰值。各 rank 峰值之和不是同一时刻测得的总分配峰值。这一次 pair
支持该固定输入上的 RSS 改善，不能推断总内存或带宽减半，也不提供计时结论。

独立标准库审计重新读取全部 64 份 VTU（含边界）、比较 432 组数值数组并严格核对整数
拓扑/编号；核验 112 个 hash 条目，对应 110 个不同运行/输入文件，另核验 54 个既有 direct
参考文件。真实残量来自运行时原算子诊断，离线只复核标量及门槛，没有从 VTU 重建 J、b、dx。
原命令/source/binary/input/output hash、rank 明细和审计分别保存在
`native-paired-30e2941/invocation.json`、`rank-memory-summary.csv`、`independent-audit.json`
与 `summary.json`，由[证据索引](../research/data/fsi-scale-01-2026-11-26/README.md)归档。

### `50b41ae`：离散压力响应的严格网格对照

二进制与 driver 均来自 `50b41ae19067bd8853a482ab853805e23c096ec5`，固定二进制 SHA256 为
`dea9ab78339d4d07a8a83bac11fb22f733898d45ef681d51b99f71adfa3522e7`。
同一 n=4/6/8、2-rank、三步窗口分别执行 direct、增强 V `mono_optimized` 和加离散压力响应
的严格 V `mono_supremizer`，共 **9/9** 通过原物理与线性门槛。每个运行仍有六次 Newton 校正：

| 实际约束后 DoF | 增强 V，总迭代 / 校正 | 增强 V + 离散响应，总迭代 / 校正 | 每次 setup 的响应模态 / 配对聚合体 |
| ---: | ---: | ---: | ---: |
| 703 | 97/6 = 16.1667 | 92/6 = 15.3333 | 20 / 10 |
| 2,299 | 160/6 = 26.6667 | 138/6 = 23.0000 | 56 / 28 |
| 5,367 | 227/6 = 37.8333 | 199/6 = 33.1667 | 118 / 59 |

新增响应减少了该窗口每档的迭代，平均迭代最大/最小比从 `2.3402061855670104` 变为
`2.163043478260869`，两者仍超过运行前声明的 **≤1.3**。因此有限窗口目标保持 **OPEN**，
不能将物理通过或各档迭代下降解释为近网格无关收敛。

三档的六次 setup 都记录了上表的实际响应数。所选行归一化局部配对块的最小奇异值，跨这些
setup 的最小值为 `0.1498419920143982`；FP64 setup 配对相对变化最大
`3.6505504122740457e-16`。它们确认实际生成及冻结后的局部配对，不给出全局 inf-sup 界，
也不把 FP64 audit 误差解释为 native FP32 action 的保持精度。

独立审计读取 144 个体场分片，核验 480 个 artifact hash、12 个命令日志、27 个接受步和
54 条线性记录。最大场差 `3.577971252610723e-13`、历史差 `8.049116928532385e-16`，
owner/ghost 差为 0；原严格真实残量/门槛最大 `0.00872921617003258`，36 次 guard 检查
零拒绝。原件为 `grid-supremizer-50b41ae-summary.json` 和
`grid-supremizer-50b41ae-independent-audit.json`。正确性运行中的耗时不作为重复性能研究。

### `50b41ae`：双域及移动 RCR 的最终物理对照

同一固定二进制在 domains-r1、domains-r2 和 moving-rcr 上运行 direct、增强 V、增强 K、
增强 V + 离散响应及 `mono_all`，共 **15/15** 通过。每个案例接受三个时间步，包含既有
NH 固体、移动边界、变步长和 RCR 行为的相应输入。下表同时列总外层迭代与 Newton 校正，
避免把 `mono_all` 的 inexact forcing 与严格线性模式混成同一收敛比较：

| 案例 | DoF / ranks | 增强 V | 增强 K | 增强 V + 离散响应 | `mono_all` |
| --- | ---: | ---: | ---: | ---: | ---: |
| domains-r1 | 307 / 1 | 72/6 | 70/6 | 71/6 | 38/11 |
| domains-r2 | 307 / 2 | 68/6 | 69/6 | 67/6 | 36/10 |
| moving-rcr | 350 / 2 | 134/9 | 189/9 | 133/9 | 112/12 |

Moving RCR 的 K-cycle 比 V-cycle 增加外层迭代；离散响应只从 134 降到 133。
`mono_all` 同时启用较小 P、缓存/批量/overlap、forcing、recycling 等机制，其中间线性目标和
校正次数不同，112 次迭代不能单独证明 MG 的同精度改善。没有据此声称 K、局部响应或组合
配置在所有案例上更快。

独立审计核验 45 个接受步、117 条线性记录、200 个体场分片、643 个 artifact hash 和
18 个命令日志。最大场差 `2.909998353395338e-10`、历史差 `4.168998479769925e-12`，
仍满足原 `2e-9` 比较门槛；owner/ghost 差为 0。严格模式的原算子残量/门槛最大
`0.007862816997846028`，inexact 模式按当次 forcing 检查的最大比值
`0.9962145448716808`。最终物理接受比值最大 `0.5379066790177952`、约束比值为 0，
RCR 恒等式缺陷最大 `4.0766001685454967e-17`；96 次 guard 检查零拒绝。

启用离散响应的物理模式每次 setup 生成 8 个响应、覆盖 4 个聚合体；最小局部奇异值
`0.14278562400145994`，最大 FP64 setup 配对变化 `5.11600760109919e-16`。
审计同时核对所请求机制的实际 counters、coarse 工作及 native 保留存储，没有仅凭开关被接受
判定路径执行。保存的 VTU 不足以重建每次 J、b、dx，离线真实残量检查仍使用运行时原算子
诊断的标量。原件为 `physical-supremizer-50b41ae-summary.json` 与
`physical-supremizer-50b41ae-independent-audit.json`。

上述两批都是单 host 小规模验证；本轮实际最大规模仍为既有 smoke 的 10,387 DoF。
**百万自由度和真实多节点强弱扩展没有运行，近网格无关目标也仍未达到。**

仍需独立证明：网格加密下迭代近似不增长、强耦合范围的稳定性、总内存/峰值和端到端时间收益、
百万约束后自由度及真实多节点强弱扩展。有限的小 rank 对照、系数精度变化和 SIMD 指令出现分别只支持其自身结论。
