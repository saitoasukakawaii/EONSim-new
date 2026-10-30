---
title: "PETSc 非线性求解器对象生命周期：哪些对象已经复用，哪些每步重建？"
description: "基于 EONSim 源码审计 NonlinearSystem 的 Vec、Mat、SNES、KSP、PC 和回调上下文生命周期。"
contentStatus: draft
knowledgeType: implementation-audit
audience:
  - graduate-students
  - scientific-software-developers
tags:
  - PETSc
  - SNES
  - KSP
  - HPC
sourceCommit: "0828f41b62391239b14a05e57a161defae1c8866"
lastVerifiedCommit: ""
---

# PETSc 非线性求解器对象生命周期

> **内容状态：** 源码审计草稿。本文未包含性能基准，不对持久化 SNES/KSP/PC 的收益作定量判断。

## 1. 核心问题

瞬态 CFD、ALE 和 FSI 求解通常在多个时间步中重复调用非线性求解器。一个常见优化方向是将 SNES、KSP 和 PC 从每次求解的局部对象提升为跨时间步复用的对象。

但在决定是否重构之前，必须先确认哪些对象已经被复用，以及 callback、矩阵数值和预条件器状态是否允许跨时间步保持。

## 2. EONSim 当前的对象分层

EONSim 的 NonlinearSystem 在时间循环之前构造。其 solution、residual、scratch ghost Vec 和 AIJ Mat 由类成员持有，因此跨多个 solve() 调用存活。

每次残量/Jacobian 评价会覆盖残量并清零、重新装配矩阵数值；AIJ 非零模式则通过预分配和 MAT_KEEP_NONZERO_PATTERN 保留。

与此相对，SNES 在每次 NonlinearSystem::solve() 中创建。SNES 内部的 KSP/PC、字段接受状态、回调 Context、线性诊断状态和 FieldSplit 索引在每次 solve 中重新配置。

## 3. 为什么不能简单把 SNES 提升为成员

当前 SNES 回调引用本次 solve() 的局部 Context；Context 又引用本次 assemble 回调、约束数据和 FieldAcceptance。线性求解计时回调也引用局部 LinearDiagnostics。

因此，持久化 SNES 需要先建立稳定的 callback context 所有权，并定义每次 solve 对约束、assemble 回调、诊断状态和求解器 options 的更新流程。简单移动 SNES 句柄不能解决这些生命周期问题。

## 4. 矩阵复用与预条件器复用的区别

至少需要区分四层：

1. **矩阵对象复用：** 同一个 PETSc Mat 对象跨时间步存活。
2. **稀疏图复用：** 非零模式和预分配结构保持。
3. **矩阵数值复用：** 当前 Jacobian 系数不重新计算；对瞬态流动和 FSI 通常不能直接假设。
4. **预条件器状态复用：** PC 数值、子求解器或 AMG hierarchy 跨时间步保留；必须依据矩阵变化和迭代表现决定是否更新。

EONSim 当前已经复用前两层，但每次 Jacobian 评价会刷新矩阵数值。后两层是否可以复用，尚需测量和验证。

## 5. 性能测量先于重构

现有 solver_report 能记录 setup、Schur setup、SNESSolve、assembly、ghost、linear 和内存指标。可先用 cases/fluid/transient.yaml 和 cases/fsi/elastic.yaml 建立多时间步基线。

需要固定代码 commit、硬件、软件依赖、网格、MPI rank 和收敛容差；区分首步与后续步，并进行重复运行。没有实际测量前，不应声称持久化 SNES/KSP/PC 能带来特定加速比。

## 6. 当前结论

源码审计建议暂缓持久化 NonlinearSession。下一步应先测量多步算例中的 SNES/KSP/PC setup 开销，再决定是否构建最小复用原型。

详细源码审计见 [NONLINEAR_SESSION_LIFECYCLE_AUDIT](../../docs/development/NONLINEAR_SESSION_LIFECYCLE_AUDIT.md)。
