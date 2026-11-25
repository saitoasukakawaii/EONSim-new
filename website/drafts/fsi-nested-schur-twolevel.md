---
title: "单体 FSI：完整流体 Schur 响应与两层速度粗校正"
description: "区分完整流体消元、压力近似和联合速度粗空间，说明嵌套 PETSc 配置与验收边界。"
contentStatus: draft
algorithm: "Nested Schur complement and two-level coupled velocity correction"
sourceReferences:
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mg.c"
eonsimCommit: "d9f58572e67ffa3636460e21d6d864ea560c8329"
---

# 单体 FSI：完整流体 Schur 响应与两层速度粗校正

**未发布算法草稿；本轮实现尚未数值验证。** 目标读者是已有鞍点问题、Krylov 和
分布式稀疏矩阵基础的开发者。学习目标是判断“保留了流固耦合”的具体含义，
区分 Schur 内层求解器的角色，并用独立证据验收粗校正算法。

| 证据类别 | 本文状态 |
|---|---|
| 理论 | 块消元和 Galerkin 投影由矩阵恒等式得到 |
| 实现 | 源码提交 `d9f58572e67ffa3636460e21d6d864ea560c8329`，已推送 |
| 验证 | 本轮未运行，不把测试代码存在写成通过 |
| 性能 | 本轮未测量，不给出加速比或可扩展性结论 |

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

基线为 `f50a4a4338689c9a065bee30ae4a7f3f52c5002e`；新增实现为
[`d9f58572e67ffa3636460e21d6d864ea560c8329`](https://github.com/saitoasukakawaii/EONSim-new/commit/d9f58572e67ffa3636460e21d6d864ea560c8329)。
入口及待执行命令见
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
本轮没有耗时证据，不选择“普遍最快”的方案。

## 8. 验证策略

待验收包括：独立稠密结构 Schur oracle；独立插值及粗矩阵、缺失分量、约束、
空 rank、两次数值更新；不同 main/inner/upper 对象与前缀；全恒等和零残量配置；
FSI/RCR 同分区直接解全场、端口历史、真实原矩阵残量；重启与失败缩步恢复。

结果须引用源码 SHA、Release/PETSc 版本、MPI rank、命令和原始输出。
**目前这些内容尚未作为本轮通过证据记录。**

## 9. 适用范围与失效模式

单体系统可解不能代替 \(F\) 单独可解的要求。不能靠偷偷添加压力规范或删除反馈
掩盖不可解的内块。更强密度比、高 Reynolds 数、接近不可压结构及跨节点规模
均需要额外算例证据。

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
