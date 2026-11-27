---
title: "FSI 鞍点多重网格中的压力配对、散度闭包与谱回收"
description: "说明如何区分 Galerkin 配对、真正的散度交换关系、跨 rank 聚合和逐次 deflated FGMRES。"
contentStatus: draft
algorithm: "Saddle-point AMG and deflated FGMRES"
sourceReferences:
  - "https://doi.org/10.1016/S0168-9274(96)00059-1"
  - "https://doi.org/10.1137/090754674"
eonsimCommit: "codex/saddle-point-multigrid"
---

# FSI 鞍点多重网格中的压力配对、散度闭包与谱回收

本文为未发布算法草稿，面向实现分布式单体 FSI 预条件器的读者。
适用范围为 EONSim 当前共形低阶离散，不能外推到任意稳定混合元、非匹配界面或多节点规模。

## 问题与数学定义

每层算子写为 `A=[F G;D C]`；非压力块同时包含流体、结构与 ALE。
稳定化压力块 `C` 必须保留。压力 Schur 为 `S=C-D F^-1 G`。
Braess–Sarazin 将逆近似为耦合实体块 `H^-1`，对压力做有界 Schur 校正后恢复非压力变量。
完整数学、输入约束和参数见[运行说明](../../docs/development/FSI_SADDLE_POINT_MULTIGRID.md)。

## 算法中三个容易混淆的关系

1. `D_c=Pp^T D Pv` 是 Galerkin 定义，不能单独证明散度保持。
2. `D delta(Pv)=0` 保持插值能量优化前后的离散散度，但原 tentative transfer 可能仍不满足交换图。
3. 压力空间包含 `range(D Pv)` 且压力列正交时，`D Pv=Pp D_c` 才是实际粗细交换关系。

实现分别诊断后两条，不以同一个代数表达式自减作为证明。压力像空间闭包可能达到满秩；
这时保留完整压力自由度，满足交换关系的代价是较弱的压力粗化。必须同时报告矩阵复杂度
与迭代数，不能把单个数学缺陷变小直接解释为整体求解优化完成。

## 数据结构与并行映射

每层保留压力/非压力语义。对实际 rank cut 进行有界完整实体块迁移，以 `T^T A T`
构建新所有权的聚合体，再用 `T P_new` 映回原代数编号。全局物理场不 gather。
迁移计数和真实跨原 owner 的聚合体计数分别保留。

彩色 Vanka 从 patch incidence 的 `R^T R` 冲突图生成分布式 coloring；每色前重算残量。
跨色不能继续使用一次加性校正的 multiplicity 权重，否则实现的已不是相应乘性迭代。
失效必须完成共同通信并恢复借用的 PETSc 数组/子向量后传播。

## 真正的子空间消除

令当前 `A U=C`、`C^T C=I`，每次右预条件作用为

\[
\mathcal B_j=(I-U C^TA)M_j^{-1}(I-C C^T)+U C^T.
\]

外层仍计算原算子残量。回收基经当前 `A` 重新评价，随后每个 Krylov 方向都投影并同步
提升校正，这与仅设置一次非零初值不同。小 SVD 选择有限搜索空间内的弱响应方向；
本实现没有完整 harmonic-Ritz GCRO-DR 重启管理，不用该名称扩大完成范围。

## EONSim 实现

当前实现分支：`codex/saddle-point-multigrid`；固定提交和实际运行结果在验收后补充。

- `src/algebra/monolithic_fsi_mg.cpp`：逐层配对、压力闭包、散度约束、复用和自适应。
- `src/algebra/distributed_mg_layout.cpp`：有界跨 rank 迁移与精确置换。
- `src/algebra/fsi_level_smoother.cpp`、`interface_patch_pc.cpp`：耦合 Schur 和 Vanka 调度。
- `src/algebra/deflated_fgmres.cpp`：当前算子 QR、逐次投影/提升和有界谱压缩。
- `src/algebra/rcr_port_pc.cpp`：端口子空间的精确方向 lifting/restriction。

## 验证与性能证据

当前尚未执行本轮新数值验证。拟使用独立稠密块解、非对称置换作用、跨 rank coloring
约束、变化算子的 deflation 恒等式和真实 FSI 轨迹对照，所有源码先同步远端。
验收记录必须区分通过、失败、未运行及历史复用，不由算法入口推出性能结论。

## 适用范围与进一步阅读

强散度闭包、逐层稳定性和良好粗化不是同一个性质。结构刚度、附加质量、步长、压力
稳定化、网格和 rank 分区都会改变实际代数行为。建议对同一精度下的迭代数、每次 PC
成本、层级复杂度、通信及总内存分别对照。

原始 smoother 文献见 Braess/Sarazin [1997](https://doi.org/10.1016/S0168-9274(96)00059-1)；
flexible recycling 背景见 Hicken/Zingg [2010](https://doi.org/10.1137/090754674)；
分布式 coloring API 见 [PETSc](https://petsc.org/release/manualpages/MatGraphOperations/MATCOLORINGGREEDY/)。
这些来源给出方法背景，不构成 EONSim 当前实现的性能或规模证据。
