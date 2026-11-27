# FSI 鞍点多重网格：配对、散度、分布式聚合与回收

本页对应 FSI-SADDLE-01，基线为已合并 PR #64 的
`036f865e3570905a58da465c91873678de485119`。
实现分支为 `codex/saddle-point-multigrid`；当前为源码待验证说明。
本轮执行遵循源码先同步远端、再构建与运行、最后按锁定 head 合并。
实际运行及失败证据会写入 `docs/research/data/fsi-saddle-01-2026-11-27/`。

## 1. 本轮路径及适用边界

目标仍是现有共形 Tet4、稳定化等阶流体、结构速度及 ALE 单体离散。
外层 Newton 方程、原算子真实残量和最终物理/约束接受规则保持。
新增配置均显式启用，不将算法入口等同于网格无关或多节点加速证明。

下表省略 `monolithic_mg_` 前缀；RCR bulk 的实际前缀是
`rcr_bulk_monolithic_mg_`。

| 用户方向 | 实际机制或入口 | 需要区分的边界 |
| --- | --- | --- |
| Saddle-point-aware AMG | `saddle_point true`；每层压力/非压力分列、受字段约束的 QR 和能量优化 | 不提供全局 inf-sup 下界 |
| Divergence-preserving prolongation | `divergence_preserving true` 保持 `B delta(Pv)=0`；额外 `divergence_commuting true` 扩充压力像空间并检查粗细散度交换关系 | 更强的闭包可能不再粗化压力；不能由缺陷小推断计算量小 |
| Multilevel pressure supremizer | `fsi_candidates true pressure_supremizers true`；每个 typed transfer 使用实际加权散度块、非压力能量对角代理及候选约束构造响应 | 不是完整 `F^-1 G`；每聚合体至多两个新增响应，已在现有空间内的响应不重复添加 |
| Coupled Schur multigrid | `smoother braess_sarazin` 在每个非粗层形成压力 Schur 近似 | 非压力块包含结构及 ALE，但实体之间的逆耦合仍为近似 |
| Distributed AMG aggregation | `distributed_aggregation true`；邻接 rank 间完整实体块迁移、分布式 QR、置换映回 | 每对邻接 rank 的迁移有预算；不是全局最优聚合或分布式网格前处理 |
| Adaptive multigrid hierarchy | `adaptive_hierarchy true`；粗化重试、算子复杂度上限及周期性真实残量作用探测 | 修改预条件工作量，不修改物理/Krylov 精度门槛 |
| Braess–Sarazin smoother | `smoother braess_sarazin`、`braess_alpha`、`schur_iterations` | 固定预算内压力迭代是平滑作用，不要求内层收敛到外层精度 |
| Multiplicative / colored Vanka | `smoother vanka_multiplicative` 或 `vanka_colored` | 每个阶段重新计算残量；彩色模式的通信成本须实测 |
| Adaptive AMG hierarchy reuse | `reuse_hierarchy true`、`hierarchy_max_age`、`hierarchy_drift` | 复用粗空间与 symbolic product，数值 Galerkin 和因子仍刷新 |
| Matrix-free MG fine level | `matrix_free_fine true`，配合外层 `-fsi_matrix_free` | 最细层残量使用当前精确作用；patch 和粗层仍使用 assembled P |
| Distributed coarse solver | `coarse_processes 0` 使用当前全部 ranks，正数保留原聚合配置 | 多 rank 使用有界 GMRES/ASM，单 rank 仍使用 PREONLY/LU |
| Deflated FGMRES | `-nonlinear_krylov_deflation N` | 使用真正逐次投影与提升；谱选择采用小 SVD，不是完整 harmonic-Ritz GCRO-DR |
| Communication-avoiding MG | `communication_avoiding true`，K-cycle 合并独立归约请求 | 不等于完全无通信或一般 s-step 多重网格；实际计数单独报告 |

## 2. 分层鞍点算子与结构顺应性

在每一层将活动未知量分成非压力 `u` 与流体压力 `p`：

\[
A_l=\begin{bmatrix}F_l&G_l\\D_l&C_l\end{bmatrix},\qquad
S_l=C_l-D_lF_l^{-1}G_l.
\]

`u` 同时含流体速度、结构自由度、ALE 和适用的边界标量，不把结构从压力反馈中删去。
实体块逆保留同一实体内的响应，跨实体的结构顺应性传播仍由多重网格近似处理。
`C_l` 包含原来的压力稳定化，不能把它假定为零。约束行先精确恢复并消去其剩余作用。
上述分块只属于预条件器；物理时间步仍由同一个单体 Newton 系统接受。

Braess–Sarazin 使用 `H_l=alpha*blockdiag(F_l)`。每个 rank 拥有的实体非压力块经过两侧
平衡和 pivoted LU，不对压力钉点、不加对角 shift。实际作用为

\[
\widehat S_l=C_l-D_lH_l^{-1}G_l,\quad
\widehat S_l\delta p=r_p-D_lH_l^{-1}r_u,\quad
\delta u=H_l^{-1}(r_u-G_l\delta p).
\]

压力解使用固定迭代预算的 GMRES/Jacobi。达到该预算的有限校正可以作为平滑作用，
数值失败或非有限值不能视为有效校正。内层近似和可变 PC 要求外层 flexible GMRES。
代码分别记录预算、实际压力迭代数、作用次数及 primal/pressure 行数。

## 3. 两种散度保证

仅有 Galerkin 定义 `D_c=Pp^T D Pv` 不能证明粗细散度交换。
`divergence_preserving` 把插值能量变化限制在实际离散散度的零空间，检查

\[
D_l(P_{v,l}^{after}-P_{v,l}^{before})=0.
\]

约束包括远端压力方程，并保持原物理候选及选定压力响应。代码报告约束维数、零空间维数、
真正接受的非零更新数及更新范数；完全受约束、没有自由优化方向的聚合体可以明确地不更新。

`divergence_commuting` 进一步在每个聚合体的压力行上，对实际 `D_l` 的全部非压力列
（含远端列）做像空间 QR 补全。所得正交压力基包含 `D_l Pv_l` 的像，因而在选定离散
压力度量下成立

\[
D_lPv_l=Pp_lD_{l+1},\qquad D_{l+1}=Pp_l^TD_lPv_l.
\]

实现独立计算 `D_l Pv_l-Pp_l(Pp_l^T D_l Pv_l)`，不是将 Galerkin 定义自身相减。
对应诊断为 `divergence_commuting_defect`；强闭包模式使用 `1e-10` gate。
缩放模式使用与物理 Galerkin 限制一致的测试权重。
这里的散度块来自建立层级的 assembled P。使用 `fsi_reduced_pc` 时，它是该预条件近似
的压力—非压力耦合，不等同于完整精确 J 的全部压力—ALE 导数；外层精确 Jv 和接受规则独立保持。

这一充分闭包可能让局部压力空间达到满秩，等价于保留该聚合体的所有活动压力自由度。
因此同时记录 `compatible_pressure_modes`、`saturated_pressure_aggregates`、行数和算子复杂度。
精确交换、粗化效率、全局稳定性和端到端收益需要分别判断。

## 4. MPI 聚合和 Vanka 调度

`distributed_mg_layout.cpp` 只迁移 setup 所有权。奇数 rank 根据实际非零连接向一个偶数
邻居提议，每个接收者最多接受一个发送者。发送者迁移少量完整 vertex/entity 块，保留
至少一个本地行；body 和 boundary 实体保持原 owner。前提是输入实体块本来就有单一 owner。
每 rank 的匹配元数据为 O(ranks)，实体记录仅发给其新 owner，不收集全局矩阵或物理场。

令 `T` 为新所有权到原编号的置换，`A_new=T^T A T`。在新布局构建 `P_new` 后，
实际插值为 `P=T P_new`。迁移行数与真实跨原 rank 的聚合体数分别统计。
独立检查使用非对称矩阵、不同字段值及空 owner，比较置换逆和原矩阵作用。

多 rank 粗层使用 GMRES/ASM，局部 LU 在各 rank 均具备 sequential MUMPS 后端时默认选用
MUMPS 的数值主元；用户指定的局部后端或其他 PC 保持有效。实际 RCR 鞍点案例曾使原生
PETSc LU 在第 70 行遇到约 `1.30e-18` 的主元，粗层在第 0 次迭代返回 `PC_FAILED`。
仅切换局部主元后端即可通过该轨迹，无需改矩阵、对角 shift 或零主元门槛。没有 MUMPS
的安装仍沿用 PETSc 后端选择，不能从主锁通过推断其他后端也完成了这项验证。

乘性 Vanka 一次执行一个全局 patch；彩色 Vanka 用 patch/row incidence 矩阵的
`R^T R` 建立跨 rank 重叠冲突图，再做分布式 distance-one greedy coloring。
每色内部是无共享行的加性局部解，每色之间重新计算 smoother 层算子的残量，取消跨色的
加性 multiplicity 权重。FP64 路径使用 assembled 层矩阵；released native FP32 路径使用
保留的 FP32 稀疏层作用。MG 外部细层周期采用精确 shell 时，局部 smoother 仍使用 assembled P。
颜色数下降只说明比逐 patch 串行的阶段少；不能自动解释为比一次加性 Vanka 更快。

## 5. 层级自适应、复用与精确细层

粗化质量不足时按有界次数增加聚合节点预算；`maximum_complexity` 限制额外层的
nnz 总量。周期探测计算 `||r-A_probe M r||/||r||`，触发后续安全刷新阶段重建。
启用 `matrix_free_fine` 时 `A_probe` 是绑定的精确作用，否则是当前 assembled P；它与外层
原算子的最终真实残量接受规则分别记录。
这些规则保持层数/工作预算有界，没有在线修改线性收敛容差。

复用受图、维数、ownership、约束、age、数值漂移及收敛探测约束。数值变更仍使用
`MAT_REUSE_MATRIX` 更新 Galerkin 系数和 smoother 因子。强闭包允许所有层完整保留活动压力
空间，或在固定 scaling/typed transfer 下细层散度块的全部已存系数逐项完全不变；后者包含
远端耦合和显式零，并保持各粗层散度块不变。压力空间未满且散度改变时重建。
`unchanged_divergence_reuses` 与 `divergence_rebuilds` 区分两种路径；`drift_rebuilds`、
`age_rebuilds`、`adaptive_rebuilds` 记录实际拒绝复用的原因，这些原因可能同时成立。
`hierarchy_numeric_drift` 是对角值/绝对行和的启发式变化，不是算子误差上界。
诊断保留 transfer setup generation，不能把旧 setup audit 当成新算子的重新检查。

最细层使用当前精确 `MATSHELL` 计算残量，其余层及局部 smoother 仍由 assembled P 支持。
RCR 子空间通过零端口 lifting、完整精确 Jv、bulk restriction 构造精确子算子。
RCR 初始化低秩响应发生在精确作用状态绑定之前，仍使用同一已组装 P；外层循环随后绑定
精确作用。MG `multiply` 路径的 shell 作用计入 `matrix_free_fine_actions`，assembled bootstrap
计入 `fine_bootstrap_actions`。周期探测直接调用算子，另由 `adaptive_probes` 表示，不含在这两项中。

`divergence_preserving` / `divergence_commuting` 当前要求 FP64 transfer；精确散度门槛不对
native FP32 作无依据保证。`reuse_hierarchy` 暂不与 native FP32 或 adaptive patch 拓扑组合。
完整 P、reduced P、局部 patch、粗矩阵和精确 action cache 的内存分别存在；开启细层 shell
不表示所有预条件存储被取消。

## 6. 真正的 deflated FGMRES

每次线性求解前以当前算子重建 `A U=C`，通过成对 QR 保证 `C^T C=I`。
初始值为 `x0=U C^T b`，随后每次右预条件作用使用

\[
\mathcal B_j=(I-U C^TA)M_j^{-1}(I-C C^T)+U C^T.
\]

底层 `M_j` 可以随迭代变化。原 `A`、右端和真实残量判断保持。对与 `C` 正交的残量，
Krylov 图像经过 `(I-C C^T)` 投影；校正同步由 `I-U C^T A` 提升回原变量。
这与只投影一次初始猜测的旧 `-nonlinear_krylov_recycle` 不同。

收集至多 `2*N` 个真实预条件搜索方向，与至多 `N` 个旧方向及成功修正组成有界空间。
方向 QR、图像 QR 和小矩阵 SVD 选择最小的非零奇异响应，避免显式形成 normal equations
使条件数平方。每次作用可能增加一次精确 `A` 乘；是否节省总时间须实测。
未实现 harmonic Ritz GCRO-DR 的完整重启维护，不能使用该名称替代本实现。

## 7. 可复现入口与验收口径

在锁定环境中构建受影响目标，源码必须先同步。以下是使用示例，当前不表示已经执行：

```bash
python tests/verify_fsi_multigrid.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_SOURCE" \
  --work results/fsi_saddle --sections default moving \
  --modes mono_saddle mono_commuting mono_multilevel mono_braess \
          mono_colored mono_distributed mono_reuse mono_mf_fine \
          mono_coarse_distributed mono_deflated mono_communication mono_saddle_all

python tests/verify_fsi_multigrid.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_SOURCE" \
  --work results/fsi_saddle_grid --sections scaling \
  --modes mono mono_saddle mono_braess
```

每种模式与独立 direct 轨迹、全部保存场、时间历史和原算子残量比较。
严格模式沿用 `1e-12 + 1e-10*rhs_norm` 真实残量 gate，保存场沿用 `2e-9`。
新 `mono_saddle_all` 不含 inexact forcing，避免用较宽的中间线性精度伪装迭代改善。
只有被日志计数证明确实执行的机制才能被该算例支持；每次 setup 与累计 action 不重复相加。
单独 `mono_reuse` 必须实际执行粗空间和符号复用；组合自适应模式允许由真实 guard 拒绝复用，
但结果明确记录为重建，不把这种轨迹当作复用已执行的证据。`mono_saddle_all` 使用 colored
Vanka；Braess–Sarazin 是另一个平滑器，由 `mono_braess` 独立验证。
`schur_budget` 是配置预算，`schur_iterations` 是实际累计迭代。Schur/Vanka 计数属于当前存活
smoother，重建后重新开始；hierarchy 的动作计数跨重建保留，不能跨快照直接求和。
`coarse_krylov_reductions` 统计 VecDot/VecNorm 请求，`batched_reduction_groups` 统计 K-cycle
起始独立范数对及自适应探测范数对的 Begin/End 调度；二者不是 MPI 包数或网络延迟测量。
网格窗口仍预声明迭代比上限 `1.3`，没有达标则保留开放状态。

## 8. 来源与证据类别

数学块消元和投影恒等式在上述方程及代码中直接给出。相关原始资料为：

- Braess、Sarazin, *An efficient smoother for the Stokes problem*, Applied Numerical Mathematics 23 (1997), 3–19,
  [DOI](https://doi.org/10.1016/S0168-9274(96)00059-1)，[作者版本](https://homepage.rub.de/dietrich.braess/smooth.pdf)。
  本项目使用包含结构/ALE 的实体块近似，不能把 Stokes 论文的收敛结论直接移植为 FSI 证明。
- Hicken、Zingg, *A Simplified and Flexible Variant of GCROT for Solving Nonsymmetric Linear Systems*,
  SIAM J. Sci. Comput. 32 (2010), 1672–1694,
  [DOI](https://doi.org/10.1137/090754674)。本文仅将其作为 flexible recycling 背景，实际谱选择和更新规则以上文为准。
- PETSc [MatPtAP](https://petsc.org/release/manualpages/Mat/MatPtAP/)、
  [MatCreateSubMatrix](https://petsc.org/release/manualpages/Mat/MatCreateSubMatrix/)、
  [MATCOLORINGGREEDY](https://petsc.org/release/manualpages/MatGraphOperations/MATCOLORINGGREEDY/)、
  [PCShellSetApply](https://petsc.org/release/manualpages/PC/PCShellSetApply/)。实际执行依赖锁为 PETSc 3.23.7。

理论恒等式、源码实现、已运行正确性检查和性能测量分开记录。未测百万自由度/多节点时，
分布式接口或小 rank 成功都不支持对应规模结论。
