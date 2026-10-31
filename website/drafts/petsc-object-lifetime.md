---
title: PETSc 对象持久化之前应先审计什么
contentStatus: draft
sourceCommit: "0828f41b62391239b14a05e57a161defae1c8866"
---

# PETSc 对象持久化之前应先审计什么

## 研究问题与学习目标

区分存储复用和预条件器复用，避免仅凭重复创建就决定重构。适用于当前 EONSim 小型 assembled CPU/MPI 求解流程。

## 数学与算法（理论）

Newton 步解当前 Jacobian 对应的线性方程。固定非零模式不等于 Jacobian 数值不变；时间步与几何变化后仍需计算当前数值。本文不改变现有离散与接受契约。

## 代码实现证据

[NonlinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp#L328) 的主 Vec/Mat 跨步保留；[流体驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fluid.cpp#L64) 在循环外构造 system，而 solve 内重新建立 SNES。Context 引用每步数据，不能只把 SNES 提升为成员就认为生命周期安全。

## 验证证据

本次执行源码调用链审计。数值回归未运行，完整所有权表见仓库 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md。没有新的数值正确性结论。

## 性能证据

本次未测性能。setup_seconds 不包含 system 构造，finalize_seconds 不包含返回时 SNES 析构；嵌套计时与各 rank 最大值不能直接相加。后续 [多步 setup 测量](multistep-setup-profile.md) 已完成，并继续暂缓持久化原型；本次源码审计本身不提供性能证据。

## 局限与参考资料

不覆盖多节点扩展、GPU 或持久化实现。源码提交已固定；理论接口参考 [PETSc SNES](https://petsc.org/release/manual/snes/) 和 [PCFieldSplitSetIS](https://petsc.org/release/manualpages/PC/PCFieldSplitSetIS/)。待审核问题：重绑上下文策略、PC 更新条件、构造/析构计时覆盖。本文保持草稿，未授权发布。
