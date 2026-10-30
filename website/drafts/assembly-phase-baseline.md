---
title: "数值基准报告：回调变快后，装配总时间为何未同比下降"
description: "三网格、1/2 rank 装配阶段测量及其解释边界。"
contentStatus: draft
benchmark: "HPC-01B steady flow assembly"
eonsimCommit: "d1708e1"
---

# 数值基准报告：回调变快后，装配总时间为何未同比下降

## 研究问题与理论

面向 MPI/PETSc 性能分析读者：将本地计算分给更多 rank，是否就会让非线性装配同比加速？
装配既包含局部回调，也包含插入、最终汇总和同步。报告的阶段时间是各 rank 最大值；各阶段的最大值可能来自不同 rank，不能直接相加恢复总时间。

## 算例与算法

使用 EONSim 内置单位通道稳态流体，rho=mu=1、Tet4/P1 稳定化、抛物速度边界与原点压力定标。
三个网格（108/500/1372 DoF）、1/2 rank，按同一容差求直接参考，再重复三次 Schur/GAMG。
完整模型、输入、容差、环境、复现命令和原始数据统一见 [阶段测量报告](../../docs/research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md)。

## 实现证据

[测量脚本](https://github.com/saitoasukakawaii/EONSim-new/blob/d1708e1/scripts/profile_schur_mesh.py) 汇总新增阶段的中位数与范围，并拒绝缺字段、非有限/负计时、越过外层计时及非零拒绝计数。
[计时实现](https://github.com/saitoasukakawaii/EONSim-new/blob/d1708e1/src/algebra/nonlinear_system.cpp) 只累计成功评价；callback 含 kernel 和插入，最终装配含本地工作和通信。

## 数值验证证据

6 个直接参考与 18 个 Schur 样本全部成功，最大节点字段差 4.0834e-12；直接解 1/2 rank 差 5.1626e-15。没有拒绝试探点。
这证明本研究中的离散解对照，不是连续解验证或网格收敛证明。最大字段差混合不同单位，仅作既有回归指标。

## 性能证据

GCC 15.3、PETSc 3.23.7、Open MPI 5.0.8，Release，4 CPU/32 GiB 配额，每 rank 单线程。
n=6 时，callback 中位数从 25.487 ms 降至 13.779 ms，最终装配从 0.138 ms 增至 9.609 ms；assembly 从 26.029 ms 降至 24.684 ms。
每组仅三次、无专门预热或随机化；范围和原始日志见报告。这些数字不能证明纯通信成本、计时器零开销或大规模并行效率。

## 适用范围、局限与审核

仅稳态小网格、1/2 rank；未拆开纯 kernel/插入、未研究失败评价或 FSI。
建议先补目标规模上的装配事件证据，再决定是否改稀疏插入策略；本轮未改求解器。
请审核时间边界、样本数与结论范围。进一步练习：解释为何各阶段最大值的和可能超过外层最大时间。

## 参考资料

- [PETSc performance manual](https://petsc.org/release/manual/performance/)
- [PETSc MatAssemblyEnd](https://petsc.org/release/manualpages/Mat/MatAssemblyEnd/)

本文为待审核草稿，未发布。
