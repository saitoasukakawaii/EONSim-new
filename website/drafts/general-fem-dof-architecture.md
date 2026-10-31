---
title: "从固定节点布局走向多空间 FEM：DoF、约束与预条件分层"
description: "以 EONSim 的 Tet4/BE 单体 FSI 为基线，解释物理语义、存储排列和求解分组的区别。"
contentStatus: draft
knowledgeType: theory
audience:
  - graduate-students
  - scientific-software-developers
tags:
  - finite-elements
  - multiphysics
  - software-architecture
sourceCommit: "38a5e516ffe129d1b70c7c1bd8365deb5ded101a"
lastVerifiedCommit: ""
---

# 从固定节点布局走向多空间 FEM

> **内容状态：理论与设计草稿，含静态源码对应。** lastVerifiedCommit 留空：本轮没有编译或运行数值测试。sourceCommit 只标识已阅读代码，不代表新增能力已经验证。未发布。

## 学习目标

区分拓扑、有限元空间和代数向量；解释 FSI 的试探展开与测试行投影；用同一套 DoF 语义组织不同预条件树，而不复制求解器。

## 问题背景与适用范围

原设计基线 38a5e51 的计算域是三维 Tet4，三角形用于边界。后续 PR #23 已增加 Tri3/Quad4 二维标量、语义 DoF/PC 与 G5 时间格式，见 [集成验收](../../docs/development/FEM_INTEGRATION_VALIDATION.md)；下文通用多空间设计仍不等于全部实现。节点具有固定数量的字段分量，这种布局足以支撑现有 P1 小算例，但不能直接表达 P2/P1、modal、高阶边/面 DoF 或界面乘子。扩展首先改变数据语义，再选择模板优化。

以下只讨论布局与耦合契约，不证明某个离散的稳定性，也不提供高性能实现。完整工程规划见 [通用 FEM 设计](../../docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md)；上游证据见 [学习矩阵](../../docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md)。

## 数学模型与约束

设 z 是各物理局部核所需的完整系数，x 是独立代数未知量。固定仿射约束写为 `z=Kx+g`；测试行的组合为 W，则

$$
R(x)=W^T r(Kx+g),\qquad J(x)=W^T J_{local}K.
$$

普通同一试探/测试空间的约束消元常有 W=K。FSI 的 ALE 界面位移从结构运动恢复，但人工网格边界“反力”不属于物理结构动量；因此不能无条件把 K 同时用于测试行。若映射随候选状态变化，还要对映射求导。

共形速度接口把流体界面速度和结构速度关联，在同一物理测试行累加双方动量残量。非一致接口若采用运动学传递 `u_f=H u_s`，并定义 f 为作用在各侧的已积分界面力，则 `f_s=−Hᵀf_f` 保持两侧虚功和为零。牵引密度的传递必须考虑质量/面积权重。

## 数值组织的三个层次

| 层次 | 表达内容 | FSI 例子 |
|---|---|---|
| 语义 | 区域、空间、实体、模式、分量、物理量 | solid.velocity 的边/顶点模式 |
| 存储 | owner/ghost 与代数排列 | rank 内 node-major 或 quantity-major |
| 求解分组 | 预条件块及其嵌套关系 | dynamics → velocity/pressure；velocity → fluid/solid |

共享接口 DoF 有一个代数身份。它可带两个物理标签，但普通 PC 分块树不能在同层重复计入；显式重叠方法需自己的 restriction/prolongation 与权重。索引集合无需连续，因此切换分组不一定需要重排全局向量。

空间决定 DoF 的数学含义。Lagrange nodal 系数可对应插值点值，Legendre modal 系数通常不可以；Legendre 基不自动给出 H1 连续性。边界约束、可视化和 checkpoint 都须理解这种区别。

## EONSim 实现映射

- [discretization.hpp](../../include/eonsim/discretization.hpp) 的 Simplex/NodalLayout 表达当前固定拓扑与节点顺序，尚非任意空间实现。
- [field_layout.cpp](../../src/fem/field_layout.cpp) 以节点编号乘分量生成全局 DoF 和字段集合。
- [reduced_layout.cpp](../../src/fem/reduced_layout.cpp) 实现当前 FSI 的缩减映射；通用非匹配接口尚未实现。
- [vtu.cpp](../../src/io/vtu.cpp) 输出节点字段与 Tet4/Tri3；未来 modal/DG 空间应先采样。

独立空间和 DoF 语义、批次执行与任意字段 IS 是迁移设计，不是上述文件已经完成的重构。

## 验证与证据

本轮仅阅读固定提交源码和官方资料，并进行文档一致性、链接和差异检查。没有执行 CMake、编译、求解器、MPI、数值或性能测试；未来阶段的验证清单不是本轮结果。

未来至少检查：置换前后物理解一致、约束后图无漏项、字段叶子覆盖互斥、接口虚功、非零边界 lifting、跨 rank 对照，以及新时间格式的完整历史重启。性能同时记录准备、装配、PC、求解和输出，不能由静态模板数量推断加速。

## 局限与待研究问题

非一致界面采用消元、mortar 还是 Nitsche，须由目标案例和稳定性证据决定；采用自有空间、DMPlex 或成熟 FEM 库也尚未做原型比较。本文不规定所有场共用一种 basis，不承诺高阶/GPU/AMR 实现。

## 参考资料

- [PETSc DMPlex 与 PetscSection](https://petsc.org/release/manual/dmplex/)：实体和数据自由度分离。
- [PETSc PCFieldSplitSetIS](https://petsc.org/release/manualpages/PC/PCFieldSplitSetIS/)：显式索引集合定义求解块。
- [libCEED Interface Concepts](https://libceed.org/en/latest/libCEEDapi/)：restriction、basis 与局部算子分层。
- [MFEM 装配层次](https://mfem.org/performance/)：离散形式与存储表示分开。

官方在线资料访问于 2026-10-30；版本可能变化。本项目取舍不构成对上游全部实现的审计。

## 思考与练习

1. 当速度是 P2、压力是 P1 时，为什么 `node_id*components+c` 不能作为统一 DoF 定义？
2. 当界面 H 依赖当前几何时，固定 H 的 Jacobian 省略了哪些导数？
3. 保持存储不变，只更换 PC 分组时，哪些对象应重建，哪些应复用？
