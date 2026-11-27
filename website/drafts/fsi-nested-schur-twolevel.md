---
title: "单体 FSI：完整流体 Schur 响应与两层速度粗校正"
description: "区分完整流体消元、压力近似和联合速度粗空间，说明嵌套 PETSc 配置与验收边界。"
contentStatus: draft
algorithm: "Nested Schur complement and two-level coupled velocity correction"
sourceReferences:
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mg.c"
eonsimCommit: "b52281d7585ead08e545f29f8d83eca9177e7eac"
---

# 单体 FSI：完整流体 Schur 响应与两层速度粗校正

**未发布算法草稿；独立代数和最终本地物理选测已通过，等待用户审阅。** 目标读者是已有鞍点问题、Krylov 和
分布式稀疏矩阵基础的开发者。学习目标是判断“保留了流固耦合”的具体含义，
区分 Schur 内层求解器的角色，并用独立证据验收粗校正算法。

| 证据类别 | 本文状态 |
|---|---|
| 理论 | 块消元和 Galerkin 投影由矩阵恒等式得到 |
| 实现 | 求解器检查点 `b8ac03a`；当前 `b52281d` 仅继续加固测试和证据，均先推送后运行 |
| 验证 | `b8ac03a` 代数 1/2/4 rank 共 3/3；首轮物理 5/7；`ff81e5b` 验证器对照 23/23；`b52281d` 最终物理/恢复选测 8/8 |
| 性能 | 已有小规模耗时及拒绝的调参数据；没有普遍加速或多节点扩展结论 |

固定源码 `b52281d` 的四项必需 CI 检查全部通过，包含 53 项数值选测、58 项
Python 检查及网站构建/草稿隔离；见
[源码 CI 收据](../../docs/research/data/fsi-block-2026-11-25/ci-source-b522.json)。
这是该源码提交的结果，不预先代表后续文档提交的检查状态。

环境、完整命令、失败历史及最终数据见
[验证索引](../../docs/research/data/fsi-block-2026-11-25/README.md)和
[原始证据归档](../../docs/research/data/fsi-block-2026-11-25/evidence.tar.xz)。
下文 `build/...` 为原始来源路径，其归档映射见该索引；本地通过不代替 PR CI、
用户审核或发布许可。


## 1. 问题定义

对象是共形 ALE 单体 FSI 的一次 Newton 修正。流体内部速度 \(u\)、压力 \(p\)、
结构速度 \(s\) 和网格内部位移 \(m\) 已经约束消元，界面速度只有一个独立代表。
求解完整方程 \(J\delta x=-R\)。预条件器不能改变物理残量、Jacobian、
时间层和接受步状态。

## 2. 数学定义

对 dynamics 的完整流体/结构划分，

\[
J_d=\begin{bmatrix}F&E\\G&K\end{bmatrix},\qquad
F=\begin{bmatrix}A_{ff}&B_f\\C_f&D_f\end{bmatrix},\qquad
S_s=K-GF^{-1}E.
\]

\(F\) 包括速度和压力，\(D_f\) 保留稳定化及属于该块的端口项。
公式要求 \(F\) 可逆。只消去流体速度得到
\(K-G_vA_{ff}^{-1}E_v\)，它遗漏压力反馈，不能称为相同消元。
各块保留原方程量纲；这里没有自动无量纲化。

另一种划分把流体和结构速度合成 \(v=(u,s)\)，再对压力做 Schur：
\(S_p=D-CA_v^{-1}B\)。节点近似
\(\widetilde S_p=D-CHB\) 只反演语义节点保留的 1–3 个速度分量。
它是压力预条件近似，不是完整结构附加质量算子。

## 3. 算法步骤

1. 从 owned 语义建立互斥且覆盖的索引树，保留原矩阵编号。
2. 创建 IS 和嵌套 FieldSplit。对 main、inner、upper 中每个独立 A00 KSP
   配置同一语义子树，再读取各自 options；别名只配置一次。
3. 外层 FGMRES 作用于完整 \(J\)。added_mass 使用完整流体近似响应；
   twolevel 作用于联合速度块，两者是不同分组路径。
4. 装配成功且施加约束后更新 nodal USER 矩阵；PCMG setup 更新 Galerkin 粗矩阵。
   固定图时复用符号结构。
5. 原始真实残量和非线性字段条件决定有效性；接受后才提交时间状态。
   有界内层迭代与真实 PC 故障分别处理。

## 4. 粗校正推导

令 \(P\) 的列为各 rank 内语义分组的归一化分片常数，键为
`(domain, kind, component, mode, space)`。无需 xyz 连续或全部存在；
精确恒等行的插值为零。对平滑后的近似 \(z\)，要求校正后的残量在粗空间正交：

\[
P^\mathsf T[r-A_v(z+Pe_c)]=0
\Longrightarrow
(P^\mathsf TA_vP)e_c=P^\mathsf T(r-A_vz).
\]

因此 \(A_c=P^\mathsf TA_vP\)，校正为 \(Pe_c\)。
完整 \(A_v\) 中的流固非对角项和跨 rank 连接进入 \(A_c\)。
粗校正前后用 ASM/ILU 平滑处理粗空间不能表达的误差。
全恒等算子没有有效粗列，实现明确使用一层 Jacobi，避免零维粗问题。

粗空间没有旋转模态或谱富集。“有两层”不等于网格无关迭代。
不能凭算法形式报告生产可扩展性。

## 5. 数据结构与并行映射

`PcBlock` 保存根索引、父矩阵索引和速度语义，不持有借用 PETSc 句柄。
插值每个有效细行一个非零元，粗列由同 rank 的细行组成。
空 rank 仍参与矩阵操作和规约；不收集全局场或原矩阵。

PCMG 持有插值引用，并复用 Galerkin 符号结果。`PcSchurUpdates` 持有 nodal
数值状态；同一语义子树的 main/inner/upper 共享近似矩阵，避免重复产品和刷新。
分区、图、语义或约束结构变化时须重建求解器。

## 6. EONSim 实现

基线为 `f50a4a4338689c9a065bee30ae4a7f3f52c5002e`；求解器实现检查点为
[`b8ac03ab162715fca24009f18903da8116ef4ecc`](https://github.com/saitoasukakawaii/EONSim-new/commit/b8ac03ab162715fca24009f18903da8116ef4ecc)。
当前验收提交为
[`b52281d7585ead08e545f29f8d83eca9177e7eac`](https://github.com/saitoasukakawaii/EONSim-new/commit/b52281d7585ead08e545f29f8d83eca9177e7eac)，
其相对上述检查点的改动仅涉及验证脚本、精度选项及执行预算。
入口、选测命令和原始收据路径见
[配置说明](../../docs/development/FSI_BLOCK_PRECONDITIONER.md)。

| 文件/函数 | 职责 |
|---|---|
| `src/algebra/pc_plan.cpp` / `make_pc_plan` | added_mass 与两层速度树、根/父索引 |
| `src/algebra/pc_plan.cpp` / `configure_pc_plan` | 递归配置、nodal 状态共享 |
| `src/algebra/schur_solver.cpp` / `configure_schur_subsolvers` | 主解、内部解、FULL 回代解 |
| `src/algebra/coupled_velocity_pc.cpp` / `configure_coupled_velocity_twolevel` | 插值、Galerkin、平滑、恒等退化 |
| `src/algebra/nonlinear_system.cpp` | 原始 Jacobian、刷新和物理接受 |

`PCFieldSplitGetSubKSP` 在 Schur 模式不能代表全部三个角色；
实现使用公开 Schur getter，并按对象身份去重。
另一个 API 细节是 `PCMGGetSmootherDown` 会创建独立上平滑器。
检查共享平滑器应使用 `PCMGGetSmoother`，避免查询改变算法。

## 7. 复杂度和性能影响

插值存储随 owned 细行数线性增长。当前两域 P1 三分量场的粗维数最多约为
MPI rank 数的六倍；其它实体种类、空间或模式会扩大粗空间。
Galerkin 成本由稀疏乘积与通信决定，粗解在更多 rank 下也可能成为瓶颈。
两层增加 setup 和每次校正工作，只有外层迭代节省足够时才会更快。

added_mass 的每次结构 Schur 作用需要流体响应，更完整的反馈也可能增加内层成本。
最终 `b52281d` 小规模结果说明，迭代减少与耗时下降必须分别判断。
每种模式完成完整 32 步精度验收和一次预热后，做三次交错的四步计时；下表的
迭代、线性时间和墙钟分别取三样本中位数，每个样本含八次 Newton 修正。

| 模式 | 1027 DoF / 1 rank：迭代 / 线性 s / 墙钟 s | 3024 DoF / 2 rank：迭代 / 线性 s / 墙钟 s |
|---|---:|---:|
| `direct` | 8 / 0.059785 / 0.415753 | 8 / 0.303184 / 0.767447 |
| `physics_lower` | 386 / 0.384190 / 0.766624 | 766 / 3.015633 / 3.627327 |
| `coupled_diagonal` | 334 / 0.177158 / 0.565688 | 646 / 1.032484 / 1.619708 |
| `coupled_nodal` | 331 / 0.159509 / 0.565938 | 645 / 0.928008 / 1.521485 |
| `twolevel_nodal` | 288 / 0.588150 / 0.967359 | 563 / 3.795757 / 4.378000 |
| `added_mass` | 179 / 6.839241 / 7.239584 | 354 / 45.805123 / 46.404431 |

来源为 `build/cloud-3.23.7-release/fsi_tube/arterial-block/results.json`。
环境为单机 Linux、PETSc 3.23.7 Release，MPI 按核映射/绑核，OMP/OpenBLAS/MKL
各 1 线程；线性时间累计每个接受步 rank 最大的 KSP 区间，包含内部求解和 PC
setup。墙钟包含相同诊断与输出。两列同时改变网格和 rank 数，不能用作强扩展
曲线，也没有逐子层时间归因。twolevel 和 added_mass 的外层迭代均更少，但
这组输入上更慢。完整 added_mass 粗/细网格墙钟分别为 `59.382126` /
`408.075013` s；其有效性证据是严格精度通过，不能写成性能领先。

细网格 added_mass 的原 130 s 运行预算不足以执行完整 32 步。针对其成本，
在同一已推送二进制上做了四种有限尝试：结构 FGMRES 上限 4 或 2、结构和流体
速度同时改 ASM/ILU(1)、三个 GAMG 小粗块改 PREONLY/LU/MUMPS。首步外层
迭代/线性秒数依次为 `489/17.849`、`1152/23.324`、`491/49.661`、`92/29.349`，
基准为 `92/13.653`；四种四步诊断均在 80 s 超时。完整命令与结果见
`build/diagnostics/arterial-budget-b8ac03a/results.json`、
`build/diagnostics/arterial-asm-b8ac03a/results.json` 和
`build/diagnostics/arterial-coarse-lu-b8ac03a/results.json`。
这些证据拒绝了相应“更省工作必然更快”的假设，未支持更换默认配置。
当前仍保留流体/结构 FGMRES 20/20 与 GAMG。粗 LU 的算子仍是显式 P 的
Galerkin 投影，完整结构 Schur 不变；数学上可用不等于在该环境更快。

## 8. 验证方法、结果与证据范围

独立代数证据来自 `b8ac03a` 的 `pc_plan_mpi1/2/4`，三项均通过。测试手写完整
流体的稠密结构 Schur oracle，故意保留压力反馈，使其不能退化成速度单独消元；
另外独立检查插值及 \(P^\mathsf TA_vP\)、缺失分量、约束、空 owned rank、两次
数值更新、全恒等块、Schur main/inner/upper 及错误配置与故障传播。
原始收据为 `build/validation-history/algebra-b8ac03a/summary.json`。

首轮物理选测是 **5/7，而非全部通过**：`fsi_tube_rcr`、`pc_twolevel_retry`、
`pc_recipe_restart`、`pc_recipe_hybrid`、`schur_verification` 通过；`fsi_tube`
因细网格 added_mass 在 130 s 时只完成 10/32 步而失败，`pc_added_mass_retry`
在两次 Newton 预算下因后续精度不足而耗尽缩步。历史收据为
`build/validation-history/physical-b8ac03a/evidence/summary.json`。
这些失败记录不被新的运行覆盖，也不按其已完成子集改记为成功。

验证器本身也要检查：`ff81e5b` 的 23 项对照包含 12 项正常数据接受和 11 项
损坏数据拒绝。检查涵盖丢失/截短数组、后续 NaN、缺报告、无穷 RHS 和负范数。
这些对照从提交的比较函数或断言执行，不启动求解器或 MPI，不算额外的物理通过；
收据为 `build/diagnostics/validation-guards/summary.json`。

`b52281d` 的最终验收保持六种动脉模式、每种完整 32 步、五类节点场与
同网格直接解对照。每次 Newton 修正独立要求真实残量满足
`max(1e-23, 1e-10*rhs_norm)`，比较余量 `1.00001`；全场相对峰值差上限
`2e-6`。完整 added_mass 的执行预算改为 600 s，整项 `fsi_tube` 为 1200 s，
其余动脉运行保持 130 s。时间预算变化不减少步数、不放宽精度，也不取消三次
计时样本。retry 仅将外层精度收紧为 `rtol=1e-11, atol=1e-15`，保留两次
Newton 上限、回滚语义和物理接受条件。

最终本地八项选测在 2026-11-25 11:58 UTC 全部通过：`fsi_tube`、`fsi_tube_rcr`、
`pc_recipe_retry`、`pc_added_mass_retry`、`pc_twolevel_retry`、`pc_recipe_hybrid`、
`schur_verification` 和 `time_retry_verification`。代数 3/3 与
`pc_recipe_restart` 的通过属于此前历史证据，没有改记为本次新运行。
当前收据为 `build/cloud-3.23.7-release/evidence/summary.json`。

动脉 60 次运行全部通过，其中 12 条完整轨迹包含 384 个接受步、768 次线性
修正；768/768 均达到独立真实残量目标。所有动脉运行的最大“残量/目标”比为
`0.5600385064`，最大字段相对峰值差为 `1.0712628633e-11`。这个相对指标
不能推广成所有 FSI 测试的绝对场误差。

RCR 新模式独立覆盖 generalized-alpha、2 rank、两个时间步及重启：added_mass
与 twolevel 的字段绝对差分别为 `5.8240910428e-9` 和 `1.8453738537e-11`，
门槛为 `2e-8`；重启差均为零。full/start/resumed 各有 `4/2/2` 次真实残量
检查，记录在 `build/cloud-3.23.7-release/fsi_tube_rcr/metrics.json`。
既有 BE/BDF2 RCR 回归使用直接解，不构成两种新增模式在这些格式下的验证。

源码 PR #49 已合入 main `296246e`；本文继续保留为 `website/drafts/` 草稿，等待独立人工审阅，不自动发布。

## 9. 适用范围与失效模式

单体系统可解不能代替 \(F\) 单独可解的要求。不能靠偷偷添加压力规范或删除反馈
掩盖不可解的内块。更强密度比、高 Reynolds 数、接近不可压结构及跨节点规模
均需要额外算例证据。当前两层方法没有完整耦合 AMG、弹性旋转/谱粗模态、
多节点扩展或跨分区重启的验收证据。

相对容差 Krylov 的响应通常是非线性的。FGMRES 支持变化的预条件器，
但不会自动消除 Schur 内部不精确乘法的误差；需控制内层误差并核对外层真实残量。
达到内层迭代预算与因子失败、非有限值等实质故障不是同一种结果，
不能都记作“收敛”。

## 10. 参考与复核练习

1. PETSc v3.23.7
   [fieldsplit.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c)：
   `PCFieldSplitSchurGetSubKSP`、Schur 配置和 FULL apply。
2. PETSc v3.23.7
   [schurm.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/utils/schurm/schurm.c)：
   `MatMult_SchurComplement`、`MatSchurComplementGetKSP`。
3. PETSc v3.23.7
   [mg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mg.c)：
   `PCSetUp_MG` 的 Galerkin initial/reuse 路径。
4. PETSc v3.23.7
   [mgfunc.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mgfunc.c)：
   插值引用和 smoother getter 副作用。

练习：固定 \(A_{ff}\)、\(K\)，只改变压力耦合。完整流体 Schur 应随之改变，
速度单独消元的近似可能不变。再改变矩阵数值，检查复用后的粗矩阵等于重新计算的
\(P^\mathsf TA_vP\)。两项分别检验反馈和更新，不能靠一次最终解误差小相互替代。
