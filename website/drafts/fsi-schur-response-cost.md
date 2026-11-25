---
title: "算法说明：FSI Schur 预条件中的流体响应与嵌套成本"
description: "区分完整 Jacobian、近似流体逆和节点结构 Schur 矩阵，解释为何减少外层迭代不一定减少总求解时间。"
contentStatus: draft
algorithm: "Monolithic FSI block factorization with an approximate fluid response"
sourceReferences:
  - "https://petsc.org/release/manualpages/PC/PCFieldSplitSetSchurPre/"
  - "https://petsc.org/release/manualpages/KSP/KSPPREONLY/"
  - "https://petsc.org/release/manualpages/KSP/KSPFGMRES/"
eonsimCommit: "664a6238ab08a42639a6c180addc99ddbf38886b"
defaultSourceCommit: "c4fb266edec94afbf610cb1379dd1595ed96ae40"
---

# 算法说明：FSI Schur 预条件中的流体响应与嵌套成本

**草稿状态：完整比较 72/72、最终默认源码本地 Release 9/9、独立证据重放均已通过；文章未公开发布。**
比较使用生产代码 `664a6238ab08a42639a6c180addc99ddbf38886b`，驱动固定为
`66b0a62af6575d8a98d85b7c90d88d6e22666439`。旧、新响应均由显式选项固定，驱动当时没有改变生产默认值。
完成完整轨迹与交替计时后，已将 added_mass 流体响应和 twolevel 速度响应的默认 KSP 类型改为 PREONLY；
相对 664a623 的生产可执行变化只有这两行。默认源码已固定为
`c4fb266edec94afbf610cb1379dd1595ed96ae40` 并先推送、后验证。
[持久证据与复现](../../docs/research/data/fsi-block-efficiency-2026-11-25/README.md)
区分比较二进制、最终默认源码和实际执行；本文不据此声称一般问题的普遍加速。[S6] [S7] [E4]

面向维护单体 FSI 求解器的开发者。阅读后应能区分：完整物理算子、结构 Schur 的实际近似作用、
构建预条件器的显式矩阵，以及不同计时字段的范围。下文分别标注**理论、实现、验证、性能测量**。
本文按算法笔记模板保留在审核用草稿目录，不属于已发布内容。

## 1. 问题定义

单体 Newton 仍解完整线性系统 \(J\Delta x=-R\)。FSI 的独立未知量包括流体内部速度 \(u\)、
压力 \(p\)、结构速度 \(z\) 和内部网格位移 \(d_m\)；界面运动学消元、ALE 导数、时间积分和共同状态提交
沿用原契约。本项工作只改变预条件作用，不修改物理残量、Jacobian 或接受条件。[S1] [S2]

added_mass 在 dynamics 内将完整流体 \((u,p)\) 与结构 \(z\) 分开，外层仍对 dynamics/mesh
作乘法分裂。之前的流体与结构响应均使用有上限的迭代解。结构 Schur 的每次乘法可能再次启动流体求解，
因此外层迭代减少不直接意味着时间减少。此次先实现显式节点流体反馈矩阵，再用相同方程与门槛比较不同的内层工作预算。

## 2. 数学定义

**理论。** 固定当前 Newton Jacobian 的 dynamics 块为

\[
J_d=\begin{bmatrix}F&E\\G&K\end{bmatrix},\qquad
F=\begin{bmatrix}A&B\\C&D\end{bmatrix},\qquad
S_z=K-GF^{-1}E.
\]

\(F\) 包含完整速度/压力块；\(D\) 保留稳定化与适用的出口电路项。
\(E\) 与 \(G\) 分别是双向流固导数，不假定互为转置。
速度通常以 m/s、压力以 Pa、网格位移以 m 表示；各行残量也有不同物理尺度。
后述局部平衡只改善小块求逆的计算，不改变全系统未知量或物理验收的单位。[S1] [S2]

实现中 PETSc Schur 乘法调用指定的子 KSP。若用 \(\mathcal B_F\) 表示该子求解器的实际响应，
执行的是

\[
\widetilde{\mathcal S}(v)=Kv-G\mathcal B_F(Ev).
\]

只有当 \(\mathcal B_F\) 实现精确且固定的 \(F^{-1}\) 时，才等于精确 Schur。
有停止容差的流体 FGMRES 及一次 PREONLY 应用都是近似响应。[P1] [P2]

## 3. 算法步骤

**实现。** 可选的 `-pc_plan_structure_approx nodal` 仅适用于 added_mass：

1. 在配置阶段，用同一流体实体实际保留的速度与压力构造 1–4 维小块 \(F_i\)。
2. 对各小块作行、列最大值平衡和带选主元消元，恢复原单位的局部逆。
3. 构造稀疏 \(H_F=\operatorname{blockdiag}(F_i^{-1})\)，再计算
   \(P_z=K-GH_FE\)。全部交叉块取自已施加约束的根 Jacobian。
4. 将 \(P_z\) 交给 `PC_FIELDSPLIT_SCHUR_PRE_USER`。结构 KSP 的 A 仍是保留完整矩阵块的
   隐式 Schur 对象，P 是该显式近似；默认 `PCSetUseAmat(false)` 保证 PC 从 P 构建。
5. 新模式默认结构 PREONLY：只应用一次从 \(P_z\) 构建的 GAMG/Jacobi。用户可显式改回结构 FGMRES。
6. 每次成功、施加约束后的 Jacobian 装配后刷新数值，复用符号乘积与 USER Mat 句柄。
7. 局部块奇异、非有限或覆盖不完整时一致拒绝；外层求解与逐字段验收成功后才提交状态。[S1] [S2]

省略新选项仍取 `a11`，即结构 P 为 \(K\)。生产检查点 664a623 的流体默认为
FGMRES（rtol \(10^{-4}\)，max_it 20）；完整比较后采纳的默认类型改为 PREONLY。
该更改保留 rtol \(10^{-4}\) 和 max_it 20，供显式选择 FGMRES 时恢复原有预算。
a11 结构响应仍为 FGMRES（rtol \(10^{-2}\)，max_it 20）；nodal 结构模式仍为可选模式，默认结构 PREONLY。
twolevel 速度响应也从 FGMRES 改为 PREONLY，保留同样的 \(10^{-4}\)/20 备用预算。
这些默认值适用于每个实际 main/inner/upper 上下文，随后分别应用该上下文的用户选项。
这些默认值对应 c4fb266；该版本先推送后完成本地 Release 9/9 回归，见第 8 节。[S6] [S7]

## 4. 关键推导

**理论与实现。** 写 \(R_i=\operatorname{diag}(1/r_i)\)、\(C_i=\operatorname{diag}(1/c_i)\)，
其中 \(r_i\) 是原小块各行最大绝对值，\(c_i\) 是行平衡后各列最大绝对值。若
\(\widehat F_i=R_iF_iC_i\)，则

\[
F_i^{-1}=C_i\widehat F_i^{-1}R_i.
\]

这避免直接按混合单位矩阵的单一最大元素判断主元，使小压力系数不会仅因量纲差异被误判为奇异。
阈值检查仍拒绝数值奇异性，不增加压力钉点、对角移位或隐式回退。[S1]

\(H_F\) 在节点内同时使用速度、压力及其交叉项；压力独有节点与 RCR 边界压力也进入反馈。
它舍弃的是不同实体间的流体传播。因此 \(P_z\) 与只用速度逆的近似不同，但仍不是精确附加质量。
局部压力标量块可能为零，即使完整 \(F\) 通过其他耦合仍可逆；此时该可选模式明确失败。

已采纳的流体默认值改变的是 \(\mathcal B_F\)：fluid PREONLY 应用一次完整速度/压力分块 PC。
它保留压力反馈和两向耦合，减少流体层 Krylov 工作，但可能增加外层迭代。
twolevel 的 PREONLY 则应用一次完整 PCMG 周期。即使只应用一个 PC 周期，容差控制的迭代粗解
仍可能随右端项而变化，不能自动称为固定线性逆。
外层 FGMRES 允许可变/非线性预条件；这一性质并不把结构内层近似 Schur 乘法变为精确乘法。[P2] [P3]

## 5. 数据结构与并行映射

**实现。** 分组依据 `DofKey` 的 entity、domain、kind、mode、space，故意在流体节点内合并 velocity/pressure，
不依赖代数行相邻关系。RCR 的 boundary 身份与 vertex 身份不同，即使数字 ID 相同也不混组。
布局契约要求一个实体的有效分量由同一 rank 持有；缺少部分速度分量及本地空块均按实际 owned 集合处理。[S1]

`PcBlock.root_rows` 保留根编号来源，`fluid_groups` 使用完整流体子矩阵编号。
子块提取与稀疏乘积由 PETSc 完成，不收集全局场。
`PcSchurUpdates` 持有数值状态；同一语义子树的 main/inner/upper 共用同一个近似矩阵并只刷新一次。
固定拓扑、分区、约束支撑及非零图是复用的前提。[S1] [P4]

局部逆的维度有界，不等于全局稀疏填充有界。一个出口电路自由度可能连接多个端口节点，
\(GH_FE\) 可因此形成端口范围的填充；大端口的存储与成本需要另行测量。

## 6. EONSim 实现

| 固定版本与位置 | 职责 |
|---|---|
| [664a623 `pc_plan.cpp`][S1]：`decorate`、`invert_small`、`NodalSchur::update`、`configure` | 语义分组、平衡求逆、USER P、默认值与选项优先级 |
| [664a623 `nonlinear_system.cpp`][S2]：`jacobian`、`linear_end`、`NonlinearSystem::solve` | 成功装配后刷新、真实残量诊断、物理接受与状态边界 |
| [664a623 `schur_solver.cpp`][S3]：`configure_schur_subsolvers` | 区分并去重 main/inner/upper、配置各自 options、传递内层失败 |
| [664a623 `verify_pc_plan.cpp`][S4]：`verify_structural_nodal` | 独立非对称矩阵与尺度不变性 oracle |
| [66b0a62 比较驱动][S5] | 固定旧/新响应预算，逐条检查求解器观测，分阶段执行性能比较 |
| c4fb266 默认版本：[pc_plan.cpp][S6] 与 [coupled_velocity_pc.cpp][S7] | 各一处 FGMRES → PREONLY；保留原容差、预算、PC 配置及完整根 Jacobian |

PETSc 3.23.7 的 PREONLY 在一次 PCApply 后汇总 PC 失败并标记结果；EONSim 还通过公开
`KSPCheckSolve` 回调检查 Schur 内部求解。正常 `CONVERGED_ITS` 表示一次应用完成，不能解释为流体残量收敛；
真正的 PC 故障或 breakdown 会传到外层。有界内层达到 max_it 可保留最后迭代作为预条件作用，
但外层失败仍拒绝。[S3] [P2] [P5]

**已采纳的默认类型与迭代参考须明确区分。** 默认版本保留备用 rtol/max_it；恢复旧流体作用需设置
`-fieldsplit_dynamics_fieldsplit_fluid_ksp_type fgmres`。twolevel 恢复迭代参考时，hybrid 使用
`-fieldsplit_dynamics_fieldsplit_velocity_ksp_type fgmres`，quantity 使用
`-fieldsplit_velocity_ksp_type fgmres`。
只改 `...fluid_ksp_rtol` 不会让 PREONLY 开始迭代。若显式创建独立 `...structure_inner_` 或
`...structure_upper_`，应分别设置所需类型；upper 仍只适用于 FULL 分解。[S1] [S3] [P2]
新默认值的精确 Schur oracle 显式恢复 FGMRES，并分别检查独立 main/inner/upper 的类型、前缀和不同预算；
默认作用另用非零右端项比较一次 KSPSolve 与一次 PCApply，已在 1/2/4 rank 的最终默认版本上通过。[S8]

## 7. 复杂度和性能影响

**性能假设。** 结构 Krylov 每次 Schur 乘法调用流体响应，流体 Krylov 又重复应用其 PC。
因此总成本受外层次数、结构响应次数、流体响应次数及每次 PC 成本共同决定；不能只看外层次数。
粗略乘法模型可以解释瓶颈方向，但当前 `solver_node.last_iterations` 仅为最后一次调用的快照，
不是累计内层次数，不能直接据此重构完整工作量。[S2] [S5]

### 7.1 已完成的短程筛选

以下是 664a623 的**单次四步样本**，不是最终计时中位数。锁定 PETSc 3.23.7 Release、Open MPI 5.0.8，
OpenMP/OpenBLAS/MKL 线程数均为 1；MPI 按 core 映射与绑定。粗网格为 1027 DoF/1 rank，
细网格为 3024 DoF/2 rank。早期筛选收据未记录 CPU 型号，故仅作同批候选筛选，不作跨机器性能结论。[E1] [E2]

| 结构 P / 响应选择 | 粗网格外层次数 | 粗网格线性时间 / s | 细网格外层次数 | 细网格线性时间 / s |
|---|---:|---:|---:|---:|
| a11，流体/结构均 FGMRES20 | 179 | 6.329710 | 354 | 49.117077 |
| a11，流体 FGMRES20、结构 PREONLY | 2999 | 5.709943 | 9743 | 68.456574 |
| nodal，流体 FGMRES20、结构 PREONLY | 3394 | 6.160497 | 9801 | 65.788333 |

对应的旧 a11 与 nodal 结构 PREONLY 墙钟为：粗网格 6.735156 / 6.532788 s，细网格
49.785546 / 66.618494 s。节点反馈公式通过了正确性检查，但此次筛选没有显示有用且可靠的总成本收益。[E1]

随后只在粗网格做了两项有界探测：nodal P 加回结构 FGMRES20 的线性时间为 6.716347 s、外层 179 次；
保留 a11 与结构 FGMRES20，仅把流体改为 PREONLY，线性时间为 0.907051 s、外层 332 次，墙钟 1.269389 s。
两项均完成四步和八次真实残量检查。这支持“应优先减少嵌套流体响应成本”的候选解释，
不构成完整轨迹加速结论。相同粗网格初始筛选中 direct 和 coupled_nodal 的线性时间分别为
0.062472 / 0.161198 s，也不能把改进旧 added_mass 解读为超过这些基线。[E1] [E3]

节点近似遗漏跨实体流体传播，可能解释结构 PREONLY 所需的更多外层迭代；这是根据算子结构作出的解释，
不是已有谱分析结论。后续完整比较因此保留结构迭代，重点比较 fluid 和 twolevel 响应中的额外 Krylov 层。

### 7.2 完整轨迹与重复计时结果

**测量。** 66b0a62 驱动完成 12 次 quick 和 60 次 full-stage 运行，全部通过。
full-stage 包括两网格、六模式各一条 32 步完整轨迹、一次四步预热和三次交替四步计时；
所以完整轨迹为 12 条，重复计时样本为 36 次，并非 60 条完整轨迹。[E4]

记录环境为 Intel Xeon Platinum 8573C、Linux 6.18.57 x86_64、PETSc 3.23.7 Release、Open MPI 5.0.8。
工作区 CPU affinity / 预算为 9，记录内存预算 10,451,423,232 bytes；性能运行仅用 1 或 2 rank。
OpenMP、OpenBLAS、MKL 各 1 线程，MPI `--map-by core --bind-to core`，通信设置
`OMPI_MCA_pml=ob1`、`OMPI_MCA_btl=self,sm,tcp`。测量期间没有另外启动本地数值任务，
但不声称共享宿主机独占。每个样本都是新进程；预热主要控制运行环境，不复用上一个样本的内存中 PC。[E4]

下表为三次交替四步样本的中位数，单位 s。粗网格是 1027 DoF、1 rank、natural 排序；
细网格是 3024 DoF、2 rank、RCM 排序。每一对旧/新模式使用相同输入、分区、排序和数值门槛；
两个网格同时改变了规模与 rank，不能把横跨两列的差异解释为强扩展效率。[E4]

| 模式 | 粗网格 linear | 粗网格 wall | 细网格 linear | 细网格 wall |
|---|---:|---:|---:|---:|
| direct | 0.060408 | 0.365677 | 0.257188 | 0.716814 |
| coupled_nodal | 0.167959 | 0.567337 | 1.014540 | 1.569494 |
| 旧 added_mass：流体 FGMRES20 | 6.482707 | 6.885585 | 44.477524 | 45.057488 |
| 新 added_mass：流体 PREONLY | 0.974291 | 1.368866 | 6.506006 | 7.148527 |
| 旧 twolevel：速度 FGMRES20 | 0.614463 | 1.017857 | 3.931200 | 4.585011 |
| 新 twolevel：速度 PREONLY | 0.119125 | 0.515940 | 0.609956 | 1.237586 |

细网格内，added_mass 的线性时间由 44.477524 降至 6.506006 s，约为原来的 1/6.84；
twolevel 由 3.931200 降至 0.609956 s，约为原来的 1/6.45。
对应外层次数反而从 354 增至 661、从 563 增至 682；粗网格分别从 179 增至 332、从 288 增至 380。
这支持减少嵌套响应工作的解释，但尚不能由最后一次内层迭代快照量化每层的累计节省。
新的 added_mass 在这两个小规模问题中仍比 direct 和 coupled_nodal 慢；本轮采纳的是对自身旧默认值的有界改进，
并不确立它为所有算例的最快 recipe。[E4]

节点结构 P 的负面筛选结论仍保留：它实现了预期矩阵，尚未提供有用的时间收益。
完整比较没有把它的单次短程计时混入上述三样本中位数，采纳的默认结构 P 仍为 a11。[E1] [E3] [E4]

### 7.3 计时范围

| 字段 | 实际范围及解释边界 |
|---|---|
| `wall_seconds` | 子进程启动、运行和日志读取的墙钟；准备分区命令另外记录 |
| `setup_seconds` | 一次 `NonlinearSystem::solve` 的初始化；不是全部 PC setup |
| `schur_setup_seconds` | 初始显式树配置，包括对应 IS/子矩阵/初始 USER P 与配置阶段 PCSetUp；不是以后所有层级重建 |
| `linear_seconds` | 顶层 KSP pre/post 区间，包含实际 PC setup 和嵌套求解；不包括回调之后的真实残量诊断 |
| `solve_seconds` | 初始装配、树配置和 SNESSolve 的总体区间，包含上述重叠部分 |
| 后续 USER P 刷新 | 在 Jacobian 回调中、`Context::evaluate` 结束后执行；包含在 solve 中，目前没有独立计时字段 |

每次非线性 solve 会创建新的 SNES/KSP 树。一次 Newton 内数值重用不等于跨时间步或跨进程重用全部 PC。
完整比较驱动的预热与每个计时样本也是独立子进程，预热不会保留前一次的内存中层级。
各计时输出取 rank 最大值，重叠区间及不同 rank 的最大值不能直接相加解释为总耗时。[S2] [S5]

## 8. 验证策略

**已完成验证，生产源码 664a623。** [E2] 的 Release 收据记录 `pc_plan_mpi1/2/4` 三项通过；
独立 oracle 包含非对称 \(B/C\)、\(E/G\)，4 维混合块、压力标量、不同 mode、缺失分量与恒等约束行，
以及 \(F'=RFC,E'=RE,G'=GC\) 下结构近似不变、USER P 句柄复用、显式 KSP 覆盖和失败后恢复。
物理选测 `fsi_tube_rcr`、`pc_added_mass_nodal_retry`、`fsi_block_efficiency` 三项通过；后者是两网格共 12 次四步筛选，
不是完整 32 步验收。原命令分别为：

```text
ctest --test-dir build/cloud-3.23.7-release -j 1 -V -R '^(pc_plan_mpi1|pc_plan_mpi2|pc_plan_mpi4)$'
ctest --test-dir build/cloud-3.23.7-release -j 1 -V -R '^(fsi_block_efficiency|fsi_tube_rcr|pc_added_mass_nodal_retry)$'
```

收据中另保存 `-T Test`、JUnit 路径、依赖配置和实际完整命令；以上省略的仅是报告输出选项。[E2]

**完整性能比较已通过，驱动 66b0a62。** 固定归档输入包含 80 Pa 升压、\(E=0.4\) MPa、
\(\nu=0.45\)、流体/结构密度 1060/1100 kg/m³、黏度 0.004 Pa·s，
generalized-alpha \(\rho_\infty=0.5\)，\(\Delta t=1/32\) s，总计 32 步。
驱动检查归档 SHA256 与算例参数；边界约束和材料沿用输入，不随 solver 模式调整。[S5]

候选为 direct、coupled_nodal、旧 added_mass、fluid PREONLY added_mass、旧 twolevel FGMRES20 与 twolevel 一周期。
每个模式先有相容的成功 quick 收据，再执行完整轨迹、一次预热、三次交替四步计时。
迭代候选的外层使用 right FGMRES、MGS、restart 100、rtol \(5\times10^{-11}\)、atol \(5\times10^{-24}\)、max_it 3000；
直接参考使用 PREONLY/MUMPS LU。
每次修正的真实残量要求为 \(\|J\Delta x-b\|_2\le\max(10^{-23},10^{-10}\|b\|_2)\)，
保留原比较余量 1.00001 与五字段相对峰值差上限 \(2\times10^{-6}\)。不以更快为数值通过条件。[S5]

必须同时核对所有求解器观测中的实际 KSP/PC 类型、真实残量、字段解、完整时间点与进程退出。
`-linear_report` 本身只输出重算残量；上述额外线性门槛由验证驱动执行。
生产代码另在状态提交前强制检查完整物理残量及各字段接受条件。[S2] [S5]

收据记录 quick 12/12、full-stage 60/60 通过，总计 72 次运行、624 个接受时间步和 1248 次线性修正。
其中 12 条完整轨迹合计 384 步、768 次修正，最大真实残量/目标比为 0.5547250921，
五字段相对峰值差最大为 \(3.1382040814\times10^{-11}\)。这两个最大值同时覆盖 full-stage 的全部样本；
quick 的最大比值为 0.4994970443，最大字段差为 \(7.0052837240\times10^{-12}\)。
未放宽物理输入、时间步、真实残量门槛或字段阈值。[E4]

**最终默认源码与独立重放已通过。** 上述比较显式固定了旧、新类型和预算，
所比较的作用与两个 PREONLY 默认值一致。另对已推送的 c4fb266 重新编译，
`pc_plan_mpi1/2/4`、`fsi_tube_rcr`、`pc_added_mass_retry`、`pc_added_mass_nodal_retry`、
`pc_twolevel_retry`、`pc_recipe_restart`、`pc_recipe_hybrid` 本地 9/9 通过，工作树 clean。
新增两 rank 刚体、弹性双域和 Neo-Hookean 变体保留直接解、物理记录和真实残量门槛，
并逐 rank、逐报告检查实际 PREONLY 默认值。[E5]

同一推送提交中的标准库重放脚本没有调用求解器或导入原验证驱动；独立核验 2,635 份文件、
72 份运行日志、1,248 次修正、2,028 次要求的求解器观测和 468 份体 VTU。
156 个保存状态提供 780 项五场对照，其中 130 项是直接参考自身对照，650 项来自其余模式。
所有检查通过；重放仅核对原墙钟的有限性并重算中位数，不重造过去的实际耗时。[E6]

验证器首版漏过了被后续正确快照掩盖的早期 KSP 类型错误。保留原 21/22 结果，
66b0a62 改为逐次检查目标观测，并要求各 rank 总数等于接受步数后，扩展的 25/25 正负对照符合预期。
独立重放进一步按接受步区间要求每 rank 恰有一份目标观测，并检查真实 KSP/PC 原因合法，
允许预定迭代预算的 ITS，拒绝 breakdown 或负 PREONLY 原因。
这些检查器修改没有放宽数值条件。[E4] [E6]

## 9. 适用范围与失效模式

当前证据覆盖共形、低阶、assembled、单机小 rank FSI。尚不支持多节点性能、网格无关收敛、
高 Reynolds 数稳健性或任意密度比的结论。节点逆模式还要求每个活动局部流体块可逆，并依赖固定图与规范一致性。
显式节点反馈的正确实现、良好谱性质和端到端加速是三件分别需要证据的事。

后续阅读练习：保持同一 \(J\)，先改变流体响应预算，再改变结构 P；逐项记录真实残量与总成本，
解释何时外层次数增多而时间下降。若要把一个周期称为固定线性算子，还应检查各层粗解是否也采用固定线性作用。

## 10. 参考文献与证据

[S1]: https://github.com/saitoasukakawaii/EONSim-new/blob/664a6238ab08a42639a6c180addc99ddbf38886b/src/algebra/pc_plan.cpp
[S2]: https://github.com/saitoasukakawaii/EONSim-new/blob/664a6238ab08a42639a6c180addc99ddbf38886b/src/algebra/nonlinear_system.cpp
[S3]: https://github.com/saitoasukakawaii/EONSim-new/blob/664a6238ab08a42639a6c180addc99ddbf38886b/src/algebra/schur_solver.cpp
[S4]: https://github.com/saitoasukakawaii/EONSim-new/blob/664a6238ab08a42639a6c180addc99ddbf38886b/tests/verify_pc_plan.cpp
[S5]: https://github.com/saitoasukakawaii/EONSim-new/blob/66b0a62af6575d8a98d85b7c90d88d6e22666439/tests/verify_fsi_block_efficiency.py
[S6]: https://github.com/saitoasukakawaii/EONSim-new/blob/c4fb266edec94afbf610cb1379dd1595ed96ae40/src/algebra/pc_plan.cpp
[S7]: https://github.com/saitoasukakawaii/EONSim-new/blob/c4fb266edec94afbf610cb1379dd1595ed96ae40/src/algebra/coupled_velocity_pc.cpp
[S8]: https://github.com/saitoasukakawaii/EONSim-new/blob/c4fb266edec94afbf610cb1379dd1595ed96ae40/tests/verify_pc_plan.cpp
[P1]: https://petsc.org/release/manualpages/PC/PCFieldSplitSetSchurPre/
[P2]: https://petsc.org/release/manualpages/KSP/KSPPREONLY/
[P3]: https://petsc.org/release/manualpages/KSP/KSPFGMRES/
[P4]: https://petsc.org/release/manualpages/Mat/MatMatMult/
[P5]: https://petsc.org/release/manualpages/KSP/KSPCheckSolve/

- **[P1]** PETSc `PCFieldSplitSetSchurPre`，Notes 的 USER/A11/SELFP/FULL 区别；实际 Schur 作用参见
  [3.23.7 `MatMult_SchurComplement`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/utils/schurm/schurm.c)。
- **[P2]** PREONLY 的一次应用、容差及初值语义；失败传播核对
  [3.23.7 `KSPSolve_PREONLY`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/impls/preonly/preonly.c)。
- **[P3]** FGMRES Notes：可变/非线性预条件与右预条件的适用范围。
- **[P4]** MatMatMult Notes：MAT_REUSE_MATRIX 要求与原非零图相容。
- **[P5]** KSPCheckSolve：内层失败传播与允许有界 ITS 的语义；核对
  [3.23.7 `iterativ.c`](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/iterativ.c)。

以下 E1–E4 原始路径均保留在[性能归档](../../docs/research/data/fsi-block-efficiency-2026-11-25/evidence.tar.xz)中；
[验证索引](../../docs/research/data/fsi-block-efficiency-2026-11-25/README.md)给出 SHA256、目录映射和重放命令：

- **[E1]** `build/diagnostics/fsi-efficient-664a623/results-quick.json`：两网格 12 次筛选、原始命令、输入与日志校验和。
- **[E2]** `build/diagnostics/fsi-efficient-664a623/algebra-evidence/summary.json` 与
  `physical-evidence/summary.json`：源码、Release/PETSc、实际测试命令、退出状态与日志；相邻目录保存 JUnit/ctest 日志。
- **[E3]** `build/diagnostics/fsi-efficient-664a623/iterative-probes/summary.json`：nodal_iterative 与 fluid_onecycle 的两次粗网格探测。
- **[E4]** `build/diagnostics/fsi-efficient-66b0a62/environment.json` 与
  `campaign/results-quick.json`、`campaign/results-full.json`：66b0a62 驱动下 72 次成功运行、
  完整命令、输入/日志校验和、每次残量与字段对照、环境、三样本计时与中位数；相邻 campaign 目录保存原日志和场文件。
  两个收据均记录生产可执行文件 SHA256
  `654f809bc2e273d0c74d77ea2813859a7ca0ee2044e0f2729f4b20e8a113aed9`，
  输入归档 SHA256 为 `662518aa06f1d9f3072c92910fcfd08c3788f0be8bf0875ec035ff6e0984fae6`。

- **[E5]** [c4fb266 本地默认路径收据](../../docs/research/data/fsi-block-efficiency-2026-11-25/default-summary.json)，
  [最终输出归档](../../docs/research/data/fsi-block-efficiency-2026-11-25/default-validation.tar.xz)。
- **[E6]** [独立重放源码](../../docs/research/data/fsi-block-efficiency-2026-11-25/replay.py)、
  [执行结果](../../docs/research/data/fsi-block-efficiency-2026-11-25/replay-result.json)。

源码、历史失败、当前通过证据和来源复用分别记录；合并状态以
[PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50)为准。
