---
title: "数值基准报告：瞬态求解的首步与后续装配成本"
description: "fluid/elastic FSI 的 1/2/4 rank 重复测量，区分时间步与独立运行样本。"
contentStatus: draft
benchmark: "HPC-01C"
eonsimCommit: "82081d5"
---

# 数值基准报告：瞬态求解的首步与后续装配成本

## 研究问题与理论

面向 MPI/PETSc 开发者：首步成本是否能代表整个瞬态计算？同一次运行中的多个时间步不是独立实验重复；物理状态、ramp 和迭代负荷均会随时间变化。
各阶段 rank 最大值也可能来自不同进程，不能将它们直接求和当作总时间。

## 算法、设置与源码

沿用 EONSim 的 BE transient fluid 与 monolithic elastic FSI，各10步，默认直接线性解；1/2/4 rank，每组3次。首步取第1步，后续取每次运行第2–10步均值，再对3次运行统计。
[完整问题、容差、环境及原始证据](../../docs/research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md) 统一保存于研究报告。
[测量脚本](https://github.com/saitoasukakawaii/EONSim-new/blob/f92e57b/scripts/profile_multistep_setup.py) 已包含阶段校验、独立固体输出检查和逐步统计；实际测量启动版本为82081d5，后续验证与统计提交单独记录。

## 数值验证证据

18次运行、180个接受步全部成功。最终主输出跨rank最大差6.6614e-16，独立固体场2.4287e-17。残量、迭代原因及阶段时间检查通过。
这是最终离散解一致性，不是逐步场验证或真实实验验证；混合单位字段差仅作回归指标。

## 性能证据

4 CPU/32 GiB配额，Release、GCC15.3、PETSc3.23.7、OpenMPI5.0.8，每rank单线程。逐步和逐次分布、min/max见报告JSON。
fluid单rank首步solve中位数18.341 ms，后续均值的中位数8.696 ms。四rank后续callback降至1.254 ms，但最终装配升至1.512 ms，solve为8.446 ms。
没有专门预热或随机化；不据此承诺加速。callback包含kernel与插入，最终装配不是纯网络时间。

## 适用范围与审核

仅单节点、小案例、最终输出对照。尚未分离纯kernel/插入，也未量化计时开销或拒绝评价成本。
请审核独立样本数、首步/后续分组及跨rank比较口径。练习：为什么不能把三个运行各九个后续步当作27次独立重复？

## 参考资料

- [PETSc performance manual](https://petsc.org/release/manual/performance/)
- [EONSim计时契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)

待人工审核草稿，不进入生产构建。
