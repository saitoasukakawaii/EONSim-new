---
title: "EONSim 开发记录：非线性装配计时的边界"
description: "区分回调、错误同步、最终装配与约束处理，避免把嵌套计时误读为纯计算或通信。"
contentStatus: draft
taskId: "HPC-01A"
baseCommit: "615af36"
resultCommit: "fff489538d683578f434bd7395b43a43ceef8f23"
date: "2026-10-30"
---

# EONSim 开发记录：非线性装配计时的边界

## 研究问题

面向分析 MPI/PETSc 装配瓶颈的开发者：已有 assembly_seconds 与 ghost_seconds 为什么不足以区分应用回调、同步等待及最终装配？本任务增加可观察的阶段边界，不据此预判瓶颈。

## 理论与数学背景

对 Newton 的 R(x)、J(x) 评价，分布式装配包含本地贡献计算、插入与跨 owner 累加。计时区间不等于数学算子的独立成本。
若每 rank 的阶段时间为 t(r,k)，报告的是 max_r t(r,k)。一般 `sum_k max_r t(r,k)` 不等于 `max_r sum_k t(r,k)`，因此不同阶段的 rank 最大值不能直接相加。

## 算法与实际实现

`Context::evaluate` 用 steady_clock 分别记录回调、错误状态规约、Vec/Mat 最终装配、约束替换；只有正常完成的评价才将四段加入累计量。拒绝/异常路径仍先完成部分装配清理，随后沿原逻辑传播错误。
在 SNESSolve 返回时冻结计数，最终物理验收及原始反力重装配不进入这些字段。report 使用已有一次 MPI_Allreduce，从 10 个数扩展为 14 个数，不新增规约次数。

| 新字段 | 包含内容 | 不能解释为 |
|---|---|---|
| callback_seconds | assemble 回调，含 kernel 与矩阵/向量插入 | 纯 kernel 时间 |
| failure_sync_seconds | 正常评价中的错误状态 Allreduce | 失败试探点的总成本 |
| assembly_finalize_seconds | 原始 Vec/Mat Assembly Begin/End | 纯网络通信 |
| constraint_seconds | 约束值替换、VecAssembly、MatZeroRows | 所有边界物理计算 |

- [实现](https://github.com/saitoasukakawaii/EONSim-new/blob/fff489538d683578f434bd7395b43a43ceef8f23/src/algebra/nonlinear_system.cpp)
- [回归检查](https://github.com/saitoasukakawaii/EONSim-new/blob/fff489538d683578f434bd7395b43a43ceef8f23/tests/verify_schur.py)
- [唯一计时契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)

## 数值验证证据

激活 Cloud 工具链后执行：

```sh
cmake --build --preset release --target eonsim verify_solver_failures --parallel 4
ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure
cmake --build --preset debug --target verify_solver_failures --parallel 4
ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure
```

Release 3/3（37.19 秒）、Debug 2/2（2.28 秒）通过。Schur 包含四类问题的 1/2/4 rank 直接解对照；新增断言检查每段有限、非负且不大于外层 assembly 最大时间（允许输出舍入误差）。失败测试检查定义域拒绝、恢复、PC 故障及初态收敛行为。
这些测试验证数值行为与计时基本不变量，没有证明计时器开销可忽略或能准确隔离所有通信。

## 性能证据

本轮没有重复性能实验，不报告加速或瓶颈归因。新增时钟读取在正常求解中也执行，开销尚未量化。

## 适用范围、局限与审核问题

本增量只细分非线性适配层成功评价。清零等工作不在四个细分区间中；ghost_seconds 的既有口径还包含后来被拒绝评价的 ghost 工作。不能用五个子项做严格的总量分解。
纯 kernel 与插入、拒绝评价成本、逐子层 KSP 累计成本仍未分离。HPC-01 的完整 profiling 目标仍未完成。
请审核计时边界与成功/失败路径的一致性。练习：构造两个 rank 各自在不同阶段最慢的例子，解释阶段最大值之和为什么会高估总时间。

## 参考资料

- [PETSc MatAssemblyBegin](https://petsc.org/release/manualpages/Mat/MatAssemblyBegin/)
- [PETSc MatAssemblyEnd](https://petsc.org/release/manualpages/Mat/MatAssemblyEnd/)
- [PETSc performance manual](https://petsc.org/release/manual/performance/)

本文为待人工审核草稿，不进入生产网站。
