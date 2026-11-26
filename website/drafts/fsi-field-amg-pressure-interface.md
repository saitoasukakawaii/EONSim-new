---
title: "算法说明：FSI 场感知 AMG、压力 Schur 与混合精度界面校正"
description: "从实际约束系统构造流固速度多层空间、稳定化压力近似和重叠界面校正，区分算法实现、正确性证据与性能结论。"
contentStatus: draft
algorithm: "FSI field-aware AMG / stabilized LSC-BFBt / physical PCD / interface patches"
sourceReferences:
  - "https://doi.org/10.1137/060655742"
  - "https://petsc.org/release/manualpages/PC/PCLSC/"
  - "https://www.firedrakeproject.org/_modules/firedrake/preconditioners/pcd.html"
  - "https://fenapack.readthedocs.io/en/latest/math.html"
  - "https://fenapack.readthedocs.io/en/latest/_modules/fenapack/preconditioners.html"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/mat/interface/matrix.c"
eonsimCommit: "19cd26f2af9b02859fac28ca8f662c29c20d47f1"
---

# 算法说明：FSI 场感知 AMG、压力 Schur 与混合精度界面校正

本文面向已了解 Newton、Krylov 和有限元块系统的读者。目标是说明：怎样把流固语义传入每一层粗空间，怎样保留稳定化压力块，怎样用真实界面混合未知量补充块预条件器，以及怎样限定 FP32 的适用范围。

**草稿证据状态：** 当前实现固定于已同步的 `19cd26f2af9b02859fac28ca8f662c29c20d47f1`，包含 PCD 辅助边界的尺度一致性修正，其 38 次受影响物理求解及独立原件审计均通过。此前代数验证固定于 `e565c98`，首轮 20 次物理求解固定于 `c5af27d`，新旧证据分别保留。小规模通过结果不构成一般网格无关收敛或性能加速证明。完整工程开关和证据路径见 [开发说明](../../docs/development/FSI_ADVANCED_PRECONDITIONERS.md)。

## 1. 问题定义

单体流固耦合同时求解流体速度、独立固体速度、压力和 ALE 网格运动。强耦合、不可压缩性和弹性低能量误差使简单场分裂容易留下难消除的误差。本轮新增的能力分工如下：

| 目标 | 所构造的预条件作用 | 本文不据此推断的结果 |
|---|---|---|
| FSI 专用 Block AMG | 联合速度多层法 + 压力 Schur + ALE 语义块树 | 一切网格/材料比下都近似网格无关 |
| PCD / LSC / BFBt | 保留完整压力稳定化的显式近似 | 所有算例压力迭代都减少 |
| 界面 Vanka / Patch | 块树响应后的混合重叠 patch 校正 | 已在每层 AMG 安装界面 smoother |
| Field-aware 粗空间 | 逐层传播流/固平移、旋转和刚体候选 | 已知完整动态系统的精确零空间 |
| 混合精度 | patch 稠密因子用 FP32，残量/改进与回退用 FP64 | 全局矩阵/向量改为 FP32 或程序内存减半 |

所有模块作用于原始系统的预条件器。物理残量、完整 Jacobian、时间离散、约束以及接受步条件仍按原模型计算。默认 `split` 速度、`diagonal` 压力、无界面校正、double patch 均保持不变。

## 2. 数学定义

### 2.1 压力稳定化必须保留

以联合速度和压力为例：

\[
J_{vp}=\begin{bmatrix}A&B\\C&D\end{bmatrix},\qquad S=D-CA^{-1}B.
\]

\(A,B,C,D\) 是约束处理后的实际块，\(D\) 包括完整稳定化；不假定 \(C=\pm B^T\)。本实现的 LSC/BFBt 选择

\[
W=I\quad\text{或}\quad W=\operatorname{diag}(|A_{ii}|)^{-1},
\qquad s=\|WA\|_\infty,
\]

\[
L=-CWB+sD,\qquad H=-CWAWB+s^2D,\qquad
\mathcal B_p\approx L^{-1}HL^{-1}.
\]

这里 LSC 使用单位权重；BFBt 使用动量绝对对角的逆，零/非有限对角会报错。它们是当前具体的**稳定化交换子变体**，不代表所有速度质量加权 LSC 或 BFBt 算法。文献中给交换子两侧和中间项分别添加稳定化的思想可见 Elman 等第 4 节、式 (4.13)；本轮以全局行和尺度 \(s\) 构造稳定化，没有声称复制该文的逐单元尺度或全部谱分析。[1]

原生 PETSc `PCLSC` 的说明假设 \(A_{11}=0\)；对于此处的非零 \(D\)，仅调用它会遗漏一个关键组成部分。[2] 本实现使用 USER 矩阵和 shell，辅助求解默认是有限工作量的一次 GAMG 作用。因此公式中的逆表示理想目标，实际作用仍有内层误差。

### 2.2 PCD 需要物理算子与一致的辅助边界

物理 PCD 使用压力集中质量 \(M_p\)、Laplace \(K_p\) 和输运 \(F_p\)，作用顺序为 \(K_p^{-1}F_pM_p^{-1}\) 的一类 PCD。[3] 当前 P1 四面体在 ALE 坐标 \(x=X+d_m\) 上装配：

\[
(M_p^K)_{aa}=|K|/4,\quad (K^K)_{ab}=|K|\nabla N_a\cdot\nabla N_b,
\]

\[
(F^K)_{ab}=\frac{\rho}{\Delta t_{\rm eff}}\frac{|K|}{20}(1+\delta_{ab})
+\mu(K^K)_{ab}+\rho\int_KN_a(u-w)\cdot\nabla N_b\,dx.
\]

\(w=(d_m-d_m^{\rm previous})/\Delta t_m\)，时间系数和阶段状态来自同一次物理装配。关闭物理对流时也关闭辅助对流。四点积分对仿射 P1 单元的该二次输运被积式精确；集中质量本身不乘密度。

**19cd26f 的边界尺度修正：** 对已有压力牵引边界定义 \(Q\)：辅助边界行取 0，其余行取 1；令 \(E=I-Q\)。保持 \(M_p\) 的全部物理集中质量，设

\[
K_{bc}=QK+E,\qquad
\widetilde F_p=Q(\mu K+N)+\mu E
=\mu K_{bc}+QN,
\]

其中 \(N\) 为瞬态与 ALE 对流项。这里仅替换行，保留非边界行上的原列耦合；其它边界使用自然 Neumann 数据。本轮面向现有 FSI 的空间常黏度 \(\mu>0\)。没有牵引边界时拒绝配置，不随意 pin 压力。

以 \(K_p=K_{bc},F_p=\widetilde F_p\) 构造

\[
\widetilde S=D+M_pF_p^{-1}K_p,\qquad
T=K_p+F_pM_p^{-1}D,\qquad
\mathcal B_{p,\rm PCD}\approx T^{-1}F_pM_p^{-1}.
\]

\(T\) 是实际辅助求解矩阵；完整 \(D\) 保留。PCD 辅助边界不会改变物理压力条件或原始 Jacobian。FENaPack 的 BRM2 实现与数学说明提供了保留质量逆项、只对 Laplace 校正施加辅助条件的概念参考。[6] 这里没有实现所有入口 Robin 修正，也没有用离散速度质量消元重建一个完整 PCDR 辅助空间；完整 \(D\) 的 \(T\) 扩展为本文显式给出的变体。

`c5af27d/e565c98` 的历史实现同时把 \(M_p,K_p,F_p\) 的牵引边界行列置成单位。这保留了物理解正确性，却破坏 PCD 的稳态黏性尺度极限；首轮迭代数据属于该历史版本。新公式的验证不能借用这些旧收据。

### 2.3 每层都传递物理候选

速度多层法使用 13 个候选槽位：流体平移 3、固体平移 3、流体参考旋转 3、固体参考旋转 3、标量刚体速度 1。旋转取 \(\omega\times(X-X_c)\)，只在 `rigid` 选项下启用；`constants` 下旋转槽位为零。恒等约束行也置零，实际列秩由所在 aggregate 决定。

细层块按节点完整语义分组，保留缺分量约束后实际存在的行；聚合可沿本地图穿过流/固耦合边。每个 aggregate 对候选做两遍局部 modified Gram–Schmidt，丢弃零/依赖列，拼出 \(P_\ell\)，随后

\[
A_{\ell+1}=P_\ell^TA_\ell P_\ell,
\qquad N_{\ell+1}=P_\ell^TN_\ell.
\]

下一层把前一 aggregate 的全部粗系数视作一个块，再重复聚合和局部 QR。每层都审计 \(\|N_\ell-P_\ell N_{\ell+1}\|_F/\max(1,\|N_\ell\|_F)\le10^{-10}\)。完整流固交叉项进入每层 Galerkin 矩阵，没有在第一层之后丢弃候选的物理含义。

### 2.4 界面后校正和全局重叠权重

令 \(\mathcal H\) 表示既有块预条件树，\(R_i\) 限制到真实界面顶点扩展出的混合 patch，\(J_i=R_iJR_i^T\)。每个全局行的 patch 覆盖次数为 \(m_j\)，并定义 \(W_i=\operatorname{diag}(1/m_j)\)。一次响应为

\[
x_0=\mathcal Hr,\quad e=r-J_{\rm current}x_0,\quad
x=x_0+\omega\sum_iR_i^TW_iJ_i^{-1}R_ie.
\]

patch 包含可达的压力、流/固速度和 ALE 分量。精确恒等行与 boundary 端口标量排除；后者由外层 RCR 处理。这里的 `vanka`、`patch` 是相同算法的别名，准确位置是块预条件器的后校正。AMG 内部各层仍使用 ASM/ILU 平滑。

## 3. 算法步骤

1. 根据 owned 独立行建立语义树，验证参考坐标、真实界面标记与各 rank 的配置一致性。
2. 成功装配当前 Jacobian 并完成约束、halo 和矩阵归并；FSI 从同一阶段重建状态，随后更新物理 PCD 辅助算子。
3. 按现有刷新策略更新压力产品、patch 因子及 bulk/Galerkin 数值。插值与 patch 图在一次固定布局的求解会话内复用。
4. 外层 FGMRES 调用新块 PC；如果有界面 wrapper，先执行 bulk 再求当前残量的界面后校正；有 RCR 时它位于两者之外。
5. 检查原始系统真实残量及非线性接受门槛，成功后才由原有物理流程提交历史。局部非有限、奇异或实质子 PC 失败必须传回外层。

默认联合速度 `PREONLY` 使用一次多层循环：上下行各一次 Richardson + ASM(overlap=1)/ILU(1)，粗层 GMRES/ASM，局部 LU。默认 coarse limit 64、最多 10 层，无法继续降低维度时提前停止。全恒等矩阵退化为单层 Jacobi。

FP32 仅用于界面稠密 LU。先做行列最大值平衡，再部分选主元；右端归一化后求解，解用 double 保存。以原 FP64 patch 矩阵计算残量，long double 累积后逐行检查

\[
|b_a-(J_ix)_a|\le\tau\left(|b_a|+\sum_b|(J_i)_{ab}x_b|\right).
\]

默认 \(\tau=10^{-10}\)，最多三次迭代改进。FP32 不满足主元/残量要求时明确回退 FP64；FP64 也失败则报告求解失败，不正则化、不放宽门槛。apply 回退会持续到该代下次刷新，因此需要查看最终统计而不只是 setup 输出。

## 4. 关键推导

三个简单恒等式帮助区分算法目标和经过验证的特殊情况。

**交换子的精确极限。** 若 \(WA=sI\)，有 \(W=sA^{-1}\)，所以 \(L=sS\)、\(H=s^2S\)。精确辅助求解时 \(L^{-1}HL^{-1}=S^{-1}\)。\(D=0\) 时则还原相应带符号的经典交换子形式。一般强对流/流固耦合不满足这个极限，不能外推成通用谱界。

**PCD 的稳定化顺序。** 因为

\[
M_pF_p^{-1}T=M_pF_p^{-1}K_p+D,
\]

目标逆恰是 \(T^{-1}F_pM_p^{-1}\)。在新边界公式的稳态无对流极限 \(N=0\) 下，\(F_p=\mu K_p\)，因此

\[
\mathcal B_{p,\rm PCD}=(M_p/\mu+D)^{-1},
\qquad D=0\Longrightarrow\mathcal B_{p,\rm PCD}=\mu M_p^{-1}
\]

成立的前提是辅助求解精确。这个极限可以用独立稠密 oracle 直接检查，也解释了不能把质量边界任意改成单位的原因。六个独立作用 oracle 已通过，新测试链接旧 e565 库则首先在此极限检查 exit 1；收据见第 8 节。此恒等式描述 PCD 近似模型自身，并不意味着任意真实有限元 Stokes Schur 都精确等于 \(M_p/\mu\)。

**粗空间列再现。** aggregate 局部正交基给出 \(P_\ell^TP_\ell=I\)，且候选投影误差受审核。因此相应候选组合能被粗空间表示。这是模态保留证据；物理网格独立性还要求合适的平滑、近似性质和粗层解。

## 5. 数据结构与并行映射

独立行来自 `DofKey` 与约束映射，不依赖连续 xyz 编号。`owned_interface` 来自真实流固界面节点；alias 行不会重复计数。RCR 压缩 bulk 编号时同步复制语义、坐标、界面标记，并通过相同 IS 传播三元 PCD 辅助算子。

field AMG 在每个 owner 内聚合，候选按每层 `13 × owned_rows` 存储；跨 owner 与跨域耦合保留在分布式 Galerkin 矩阵中。没有把矩阵或完整场 gather 到一个 rank，但大量小 owner 仍可能限制粗化效率。

界面 patch 可以包含 off-rank 行，由 `MatCreateSubMatrices` 提取局部顺序矩阵；残量读取和校正散射通过 `VecScatter`。覆盖次数由全体 patch 反向累加，再传回各 patch，因此权重反映全局重叠，而非仅计算本 rank 的重复次数。

一个已实际发生的失败说明集体契约的必要性：首轮 4 rank 中有空 patch owner，`MatIncreaseOverlap` 的 `n==0` 在 PETSc 3.23.7 中提前返回，非空 rank 仍在集体 overlap 通信。后续 scatter 暴露 `MPI_ERR_BUFFER`，随后超时；保留的诊断复现还出现 `MPI_ERR_TRUNCATE`。[4]

修复仅在 setup 临时把每个 rank 的 IS 数补到全局最大值，调用 overlap 后立即移除空补位。它们不会成为数值 patch。4 rank 的 `2/1/0/0` patch 回归和修复后的 1/2/4 rank 均通过。`MatCreateSubMatrices` 可接受 rank 不同的局部数量，不能把某一 API 的 collective 规则套到所有 API。调试环境未提供 GDB/LLDB；本次记录的是原二进制诊断、固定版本源码契约与修复后回归，没有声称执行过调试器。

## 6. EONSim 实现

当前固定源码为 [`19cd26f2af9b02859fac28ca8f662c29c20d47f1`](https://github.com/saitoasukakawaii/EONSim-new/tree/19cd26f2af9b02859fac28ca8f662c29c20d47f1)。当前及历史验证在第 8 节按源版本单列，最终独立审计已通过，原件和哈希已归档。

| 模块 | 代码路径与函数 |
|---|---|
| 语义树和 wrapper | `src/algebra/pc_plan.cpp`，`make_pc_plan_impl`、`configure` |
| 逐层物理候选 | `src/algebra/coupled_velocity_pc.cpp`，`field_candidates`、`field_transfer`、`configure_coupled_velocity_field_amg` |
| 稳定化压力 | `src/algebra/pressure_schur_pc.cpp`，共享 `PressureSchurState`、`configure_pressure_schur_pc` |
| 物理 PCD | `src/physics/fsi_pressure_operators.cpp`、`src/physics/fsi.cpp`；`src/algebra/nonlinear_system.cpp` 的 `after_jacobian` 钩子 |
| 界面/精度 | `src/algebra/interface_patch_pc.cpp`，`PatchState`、`Patch::factor`、`Patch::solve` |
| RCR 辅助传播 | `src/algebra/rcr_port_pc.cpp` 与 `propagate_pressure_auxiliaries` |

组合入口示例为 `-pc_recipe hybrid -pc_plan_velocity_solver field_amg -pc_plan_velocity_coarse_space rigid -pc_plan_schur_approx bfbt -pc_plan_interface_smoother vanka -pc_plan_patch_precision single`。`pcd` 还需要物理辅助算子及现有牵引边界；有 RCR 端口必须加 `-pc_plan_rcr_ports true`。这些是配置示例，不是额外实验记录。

| 参数 | 默认/范围 |
|---|---|
| `-pc_plan_velocity_aggregate_nodes` | 16，2–4096 |
| `-pc_plan_schur_approx` | `diagonal`；可选 `nodal/lsc/bfbt/pcd` |
| `-pc_plan_interface_smoother` | `none`；`vanka/patch` 为别名 |
| `-pc_plan_patch_precision` | `double/fp64`；可选 `single/fp32` |
| `-pc_plan_patch_overlap` | 1，0–2 |
| `-pc_plan_patch_max_size` | 256，1–2048；超限报错 |
| `-pc_plan_patch_refinement_steps` | 3，0–8 |
| `-pc_plan_patch_refinement_tolerance` | `1e-10`，`1e-14`–`1e-4` |
| `-pc_plan_patch_damping` | 1，范围 `(0,2]` |

精确 PETSc 前缀反映真实嵌套。没有用户根前缀时，普通 hybrid 的联合速度前缀为 `fieldsplit_dynamics_fieldsplit_velocity_`，压力辅助为 `fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_`。开启界面 wrapper 时在二者前加 `interface_bulk_`；同时开启 RCR 时前缀完整为：

```text
rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_velocity_
rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_pressure_pressure_aux_
```

所以一个完整 coarse target 选项为 `-rcr_bulk_interface_bulk_fieldsplit_dynamics_fieldsplit_velocity_field_amg_coarse_limit 64`。仅 RCR 时只有 `rcr_bulk_`，已有根前缀放在最前。`pc_plan_report` 会打印最终 `pc_block ... prefix=...`，独立 Schur inner/upper 使用各自前缀。

根外层要求 FGMRES；interface/RCR 的 bulk 固定为一次 PREONLY 响应。压力 shell 和速度响应可用 PREONLY 或显式 FGMRES。压力内部辅助默认 PREONLY/GAMG：只设置 rtol 不会使 PREONLY 开始迭代。`field_amg_max_levels` 默认 10，必须附在实际速度前缀下；不能另外用 `pc_mg_levels` 覆盖自建层数。

## 7. 复杂度和性能影响

patch setup 的稠密 LU 成本为 \(O(\sum_i n_i^3)\)，每次局部求解为 \(O(\sum_i n_i^2)\)，迭代改进再增加残量与三角求解。FP32 因子数组通常每项 4 字节，FP64 每项 8 字节；这里没有计算稀疏原 patch、全局矩阵、AMG、压力乘积、向量和通信空间。因此“局部因子数组一半”与“全程序内存一半”是不同的证据命题。

在首轮同一双域问题中，全部 patch 为 single 时因子数组总计 108136 字节，double 为 216272 字节；配对外迭代数相同。这是实际存储与迭代记录，不是速度或内存带宽结论。额外一次冻结 `e565c98` 的 `1e-6` 改进门槛诊断保持原外层/物理门槛并通过，但改进次数仍为 5001（原 `1e-10` 为 6406），不能说明放宽局部门槛就消除了改进成本；默认未改变。该次 2 rank 三步诊断外迭代仍为 400，真残量/原门槛最大比 `0.009043401917193978`，所有步及 final 场差 `3.591377195633072e-12`。收据为 `build/fsi-advanced/fix-e565c98/precision-1e-6-diagnosis/results.json`。

当前 `19cd26f` 原驱动已记录三档物理加密的 PCD+single patch 结果：

| 自由度 | 1 rank 累计外迭代 | 2 rank 累计外迭代 |
|---|---:|---:|
| 703 | 142 | 144 |
| 2299 | 160 | 166 |
| 5367 | 225 | 225 |

每例均为 3 个接受步、6 次线性修正。这是有限网格窗口的迭代记录，没有建立网格独立性。完整跨方案/强耦合比较已归档，硬件、软件版本、物性、分区与门槛见来源记录。没有执行独占资源上的重复计时；代码中出现 float 或单次 wall time 较小都不能建立稳定收益。

## 8. 验证策略与已执行结果

算法应分层验证：独立矩阵 oracle 检查公式和符号，制造解检查原始残量，MPI 对照检查空 owner/跨 rank 数据，真实 FSI 与同配置直接解比较全部场和历史，再单独研究性能。

本稿已有的执行证据如下：

| 检查 | 已执行结果 |
|---|---|
| `verify_field_amg` | `c5af27d`，MPI 1/2/4 通过；385/1297 个制造代数自由度、3/4 层，逐层候选再现、系数改变后的 Galerkin 更新、约束/缺分量/body/空 owner/全恒等 |
| `verify_pressure_schur` | `e565c98`，MPI 1/2/4 通过；独立 dense oracle、零/完整稳定化、精确极限、刷新、empty owner、辅助传播与失败/恢复 |
| `verify_interface_patch` | `e565c98`，MPI 1/2/4 通过；独立重叠加权 oracle、非对称/非局部混合块、FP32 与强制回退、`2/1/0/0` patch 数及真实残量 |
| `verify_fsi_pressure_operators` | `e565c98`，四组 ALE/时间/对流的单四面体 oracle 通过，最大误差 `2.22045e-16`；使用 `PETSC_COMM_SELF`，不当作多进程分布式装配证明 |
| 首轮真实 FSI | `c5af27d`，20 次求解、54 个接受步、117 次显式真实残量检查全部通过；含 1/2 rank、307/350 自由度、移动 RCR、变步广义 alpha 和两次 restart |
| 修正后的 PCD 物理回放 | `19cd26f`，38/38 次求解由原驱动验收通过，包括受影响默认例、restart、加密和密度/时间步对照；独立原件审计通过 |

代数执行命令格式为 `bash build/locked.sh mpiexec -n N build/cloud-3.23.7-release/verify_interface_patch` 等，分别取 `N=1,2,4`；历史 `e565c98` 物理单元 oracle 使用 `PETSC_COMM_SELF`，以 2/4 进程启动仅重复串行 fixture；`19cd26f` 新增的 WORLD fixture 及 1/2 进程测试见下文。原始命令/exit/log 保留在 `build/fsi-advanced/initial/field/`、`build/fsi-advanced/fix-e565c98/pressure/` 和 `build/fsi-advanced/fix-e565c98/interface/`。

首轮物理原件为 `build/fsi-advanced/initial/physical/1795682143415893521/results.json`，独立原件审计为 `build/fsi-advanced/initial/independent-physical-audit.json`。20 次包括 16 条完整轨迹、2 次 checkpoint 生成、2 段 restart 尾部。最大场差 `1.257624560047077e-11 < 2e-9`，最大历史差 `8.104628079763643e-15`，原始线性残量相对 `1e-12 + 1e-10 * rhs_norm` 门槛的最大比值 `0.009257947264879914`。

同一 2 rank 三步双域例的累计外迭代为：nodal 72、LSC 100、BFBt 87、历史 PCD 442、历史 PCD+patch double/single 均 400。这个事实表明正确性通过不等于压力近似收益。它属于旧 PCD 边界版本，不代表新修正版本的表现。首轮空 owner 失败日志也保留，后来的成功没有覆盖原始失败。

修正后原收据为 `build/fsi-advanced/pcd-fix-19cd26f/physical/1795683464167404865/results.json`，生产二进制 SHA256 为 `45ce710b6f7d1358c4b0524c9dc41d8cd2218beee2e416295d4c311d57132d77`。38 次为 34 个完整轨迹、2 次 checkpoint 首段和 2 次续算，共 108 个接受步、225 次已记录线性修正；原收据最大场差 `3.1915137199689525e-11 < 2e-9`，历史差 `5.684341886080802e-14`，真残量/原门槛最大比 `0.009273085855602773`。同一 2 rank 默认双域例 PCD 从 442 降到 150，PCD+patch double/single 从 400 降到 161；当前 patch 仍略多于无 patch，不能宣称每一算例都改善。

最终 `fsi_pressure_operators` 与 `fsi_pressure_operators_mpi2` 两项通过：六个独立 Stokes 作用最大误差 `2.06789e-15`，四代积分 `3.97763e-16`，还包含真实 WORLD 空流体 owner、区域/跨 rank 黏度拒绝与恢复。同一新测试链接旧库的负控明确 exit 1，首个错误是 Stokes mass-limit action oracle，正式二进制保持不变。

最终 38 次独立审计重新匹配全部场/历史/ghost/拓扑及 1544 个旧 pin，owner/ghost 差为 0。残量审计从原程序显式 J 诊断的 norm/rhs 标量重算门槛，不是离线重新做 J 乘积。跨源码 26 对 HDF5 分区原始容器 SHA 不同，但完整类型、数据与属性语义一致；这两个事实分别保留。

2 rank 三网格中，最终 PCD+patch 为 `144/166/225`，nodal 为 `82/99/131`，BFBt+patch 为 `94/109/140`。BFBt 的六组密度/时间步对照加 patch 少 `2.44%–11.96%` 外迭代，但额外工作仍使小算例线性时间增加。当前没有独占资源上的重复计时，不声称稳定加速；网格无关与更大规模仍未验证。

[完整证据与 CI 收据](../../docs/research/data/fsi-advanced-2026-11-26/README.md)包含原命令、来源、三批审计、两个单次诊断、首次失败和负控；[跨源 PCD 比较](../../docs/research/data/fsi-advanced-2026-11-26/pcd-comparison.json)保留逐步、逐 mode、分区与输入核对。

## 9. 适用范围与失效模式

当前支持固定会话内的 P1 顶点/标量刚体速度语义；新边界 PCD 面向常黏度 FSI 与明确牵引边界。拓扑、约束、ownership 或参考几何元数据变化时必须重建；已有自适应 PC 策略可以保留旧因子，但界面残量仍使用当前 Jacobian。

配置会明确拒绝：没有真实界面标记、无全局有效界面顶点、过大/空/奇异 patch；非有限算子；BFBt 零动量对角；不完整或错误编号的 PCD 三元组；非正/非集中质量；没有 PCD 更新回调；端口未隔离；跨 rank 不一致选项或固定 PC 拓扑冲突。初始零 Newton 状态仍检查契约，却不去分解未使用的预条件器。

运行时应记录 `pc_field_amg_level` 的再现误差与层维度、`pressure_schur` 更新计数、`interface_patch_stats` 的 FP32/FP64/refinements/fallbacks/factor_bytes，最终还必须检查原始 Jacobian 真残量和接受步条件。`coarse_limit` 不保证一定达到；强对流、材料/密度比、各向异性及更多 MPI rank 可能暴露目前候选/平滑器/粗解不足。

### 进一步推导与阅读

可先推导 \(WA=sI\) 时的完整稳定化精确极限，再在包含非对称 \(B,C,D\) 的小矩阵上检查。对 PCD，分别比较“把三个矩阵都变成单位边界”和“保留质量、按 \(\mu\) 匹配 Laplace/输运行”的 \(D=0\) 稳态作用。对多层法，尝试缺分量或共线节点，解释为什么局部候选秩应降低。这些是阅读练习，不是新增已执行实验。

## 10. 参考文献

1. H. Elman, V. E. Howle, J. Shadid, D. Silvester, R. Tuminaro, *Least Squares Preconditioners for Stabilized Discretizations of the Navier–Stokes Equations*, SIAM J. Sci. Comput. 30(1), 290–311；第 4 节，p. 301 式 (4.13)。[DOI: 10.1137/060655742](https://doi.org/10.1137/060655742)，[作者稿](https://www.math.ttu.edu/~vhowle/publications/065574.pdf)。本文实现的全局尺度稳定化是另行明确给出的变体。
2. PETSc [`PCLSC`](https://petsc.org/release/manualpages/PC/PCLSC/)，Notes 的 Schur 定义与忽略 \(A_{11}\) 的限制；[`MatPtAP`](https://petsc.org/release/manualpages/Mat/MatPtAP/) 与 [`PCMG`](https://petsc.org/release/manualpages/PC/PCMG/) 说明 Galerkin 和多层接口。文档可能更新，实际运行使用 PETSc 3.23.7。
3. Firedrake [`firedrake.preconditioners.pcd`](https://www.firedrakeproject.org/_modules/firedrake/preconditioners/pcd.html)，`PCDPC` 类说明及 `apply`，用于定位 \(K^{-1}F_pM^{-1}\) 作用顺序；其边界与正则化选择并未被直接照搬。
4. PETSc v3.23.7 [`src/mat/interface/matrix.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/mat/interface/matrix.c)，`MatIncreaseOverlap` 的 `n` collective 检查与零数提前返回；API 对照 [`MatIncreaseOverlap`](https://petsc.org/release/manualpages/Mat/MatIncreaseOverlap/) 和 [`MatCreateSubMatrices`](https://petsc.org/release/manualpages/Mat/MatCreateSubMatrices/)。
5. EONSim 当前源码 [`19cd26f`](https://github.com/saitoasukakawaii/EONSim-new/tree/19cd26f2af9b02859fac28ca8f662c29c20d47f1)，此前代数源码 [`e565c98`](https://github.com/saitoasukakawaii/EONSim-new/tree/e565c9872551dad9dc7a01d4d7b613e8a96d3545)，首轮物理源码 [`c5af27d`](https://github.com/saitoasukakawaii/EONSim-new/tree/c5af27de8fdc7a42df855543ad6366ce7db70571)；接口路径、命令、失败记录及证据限制见 [开发说明](../../docs/development/FSI_ADVANCED_PRECONDITIONERS.md)。
6. FENaPack [Mathematical background](https://fenapack.readthedocs.io/en/latest/math.html)，BRM2/outlet 条件及 time-dependent 扩展；[`PCDPC_BRM2.apply`](https://fenapack.readthedocs.io/en/latest/_modules/fenapack/preconditioners.html) 的质量逆、对流乘法、边界投影和 Laplace 校正顺序，同页 BRM1 说明强调 leading Stokes term 的保留。用于算法概念核对，不复制其代码或声称实现了其全部边界/反应增强形式。
