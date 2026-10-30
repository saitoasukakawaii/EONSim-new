---
title: 小型非线性求解的诊断开销测量边界
contentStatus: draft
---

# 小型非线性求解的诊断开销测量边界

## 研究问题与理论

重复创建对象不自动证明分配是瓶颈。Newton 的 Jacobian 数值更新与预条件器 setup 必须和存储分配区分；本次不改变数学模型。

## 实现与算法

使用 scripts/benchmark_nonlinear_setup.py，固定 transient 算例，1/2 rank 各三次诊断开关对照；子进程失败、非有限输出、字段变化或步骤报告缺失都会中止。求解器源码基线为 c1c7508；详细测量见仓库 docs/research/NONLINEAR_SETUP_BASELINE_2026-10-30.md。

## 实验与性能证据

全部12个测量运行成功，固定 rank 的输出差为0。1 rank 报告关/开端到端中位数分别为1.316755/1.318050秒；2 rank为1.316658/1.317176秒。包含启动与I/O，不能当作纯求解耗时；详细范围及原始日志随研发报告提交。

## 局限

未隔离构造析构；没有优化版对照；不宣称加速或大规模扩展性。需要更细分计时和更大案例，暂缓持久化实现。草稿未经审核不发布。

## 参考资料

[PETSc profiling](https://petsc.org/release/manual/profiling/)；[固定源码](https://github.com/saitoasukakawaii/EONSim-new/tree/c1c7508)。
