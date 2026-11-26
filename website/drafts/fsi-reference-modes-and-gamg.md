---
title: "缩减 FSI 系统的旋转粗模态与联合速度 AMG"
description: "用真实参考坐标与语义行构造粗空间，区分预条件层级复用和数值更新。"
contentStatus: draft
algorithm: "Reference-coordinate rigid modes and coupled velocity GAMG"
sourceReferences:
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/agg.c"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/gamg.c"
eonsimCommit: "codex/fsi-block-amg-robustness"
---

# 缩减 FSI 系统的旋转粗模态与联合速度 AMG

未发布算法草稿。目标读者为了解有限元、块预条件和分布式稀疏矩阵的开发者。
本稿的实现状态与实际实验分开记录：代码完成并推送之后才运行验证；当前未预写通过结果。

## 问题与数学对象

共形单体 FSI 将界面速度消元为唯一代表，联合速度块 $A_v$ 同时包含流体、结构和两者之间
的非对角项。压力和 ALE 仍由外层语义树处理，主 Newton 方程 $J\Delta x=-R$ 保持完整。

在参考位置 $X_i$ 上，三个位移/速度平移候选为 $e_j$，三个旋转候选为
$e_j\times(X_i-X_c)$。每个代数行只取它的实际物理分量。本质约束行对应的候选值设为零。
惯性、约束和非对称耦合使这些向量通常不是 $A_v$ 的精确零空间；它们作为粗近似信息。

twolevel 原有分片常数按 rank、domain、entity kind、component、mode、space 分组，
新增固体 P1 旋转后用两次正交化剔除线性相关候选。插值 $P$ 保持分布式稀疏结构，
粗矩阵为 $A_c=P^T A_vP$。ASM 处理局部误差，粗校正为
$z\leftarrow z+P A_c^{-1}P^T(r-A_vz)$。

GAMG 使用活动标量行上的一个归一化常数近模态，由 PETSc 根据完整 $A_v$ 构造聚合层级，
不为每个 MPI rank 或每个物理分量添加全局模态。`rigid` 仅支持 twolevel；在 GAMG 上
请求它会明确报错。两条算法的粗空间不同，scalar GAMG 不等于向量弹性 AMG。

该边界来自固定版本实现：PETSc 3.23.7 的聚合会为每个 aggregate 保留 nvec 个粗列，
局部 QR 没有按真实局部秩截断。即使全局平移/旋转向量线性无关，只有一个活动分量的
aggregate 或独立 body 仍可能生成零粗列。因此本轮不向不规则 scalar AIJ 盲目附加六模态；
packed-vector 辅助空间及相应转移算子仍需独立实现和证据。

## 几何、约束与并行身份

坐标由物理布局提供，按 owned 独立代表排序，接口 alias 不复制。缩减后的节点可能缺少
一个或多个分量，有限维刚体和端口也不是三分量节点，因此不能将矩阵强制标为 blocksize 3。
P1 顶点、body 和边界压力由明确的 `DofKey` 区分；body 的零占位坐标没有几何意义。

旧镜像弹性示例尤其容易出错：流体逻辑网格的 $x$ 与固体物理参考位置不同，后者为
$1+h(1-x)$，$h$ 是固体厚度。粗模态必须采用与结构单元一致的变换。双域输入已经存储实际
参考位置，无须该映射。ALE 当前坐标不会在每次 Newton 迭代重定义参考粗空间。

## 层级复用和更新

固定拓扑与参考基允许复用插值。PETSc 3.23.7 的 GAMG reuse 分支仍重新计算 Galerkin
矩阵数值并更新各层算子，不能把这称为使用旧 Jacobian。系数变化过大时固定插值可能变差，
因此保留 `pc_gamg_reuse_interpolation false`。配置或约束变化由现有会话机制共同重建。

默认 PREONLY 的含义是一次 V-cycle。粗 GMRES 根据右端和容差改变工作量，因此外层仍用
FGMRES；一次 PREONLY 正收敛理由不证明满足某个备用内层 rtol。

## 实现与证据

实现位于 `src/algebra/coupled_velocity_pc.cpp`、`src/algebra/pc_plan.cpp`、
`src/fem/field_layout.cpp`、`src/fem/reduced_layout.cpp` 和 `src/physics/fsi.cpp`。
配置及最终证据入口为 [FSI 分块预条件器](../../docs/development/FSI_BLOCK_PRECONDITIONER.md)。

代数验证应检查模态张成空间、约束零行、独立 Galerkin 作用、真实残量及矩阵数值更新，
而不要求正交化后某列的符号固定。物理验证应在相同密度、步长和输入分区下与直接解比较，
包括 RCR 历史、重启、真实非线性回滚及全部接受步。性能须分别报告建立、线性解和总时间。
此处待推送后追加实际命令/来源/结果；没有多节点、GPU 或百万自由度结论。

## 进一步检查

对 twolevel 改变参考坐标原点后，比较保留下来的模态张成空间是否一致。删除一个节点分量后，检查
剩余空间是否仍正交、有限且对约束行为零。随后改变矩阵系数，分别比较固定插值与重建
插值的迭代数和总成本，避免仅凭层数或迭代减少判断优化有效。
