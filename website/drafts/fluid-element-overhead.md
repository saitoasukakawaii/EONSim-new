---
title: "数值基准报告：单元计时也会扰动测量"
description: "流体计时开关的配对实验与观测范围，区分求解时间和端到端时间。"
contentStatus: draft
benchmark: "HPC-01E"
eonsimCommit: "1423b99"
---

# 数值基准报告：单元计时也会扰动测量

## 研究问题与理论

面向科学计算性能分析读者：新增细粒度计时后，能否假设观测开销为零？本实验比较同一输入、同一求解器开启/关闭单元计时的耗时。
每对相对变化为 `T_on/T_off-1`。多个配对比值的中位数通常不等于两个独立中位数之比；运行顺序、调度和输出也会影响差异，不能直接将所有差值归因为时钟成本。

## 算法与实现

[脚本](https://github.com/saitoasukakawaii/EONSim-new/blob/1423b99/scripts/benchmark_fluid_element_report.py)在1/2/4 rank下对两个模式分别预热，再进行5组交替顺序配对。两种模式均启用solver_report，仅切换fluid_element_report。
输入为500 DoF、10步BE transient fluid；模型、容差、软件与资源信息、命令和原始证据统一见[测量报告](../../docs/research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md)。

## 数值验证证据

30个统计样本及6次预热完成，逐步SNES/KSP迭代轨迹一致。最终物理字段同rank开关/重复最大差3.3307e-16，跨rank4.4409e-16；逐rank/步单元计数有效且重复一致。
这不代替物理模型验证或逐步场对照，混合单位最大绝对差仅为回归指标。

## 性能证据

单rank的配对solve相对变化中位数+3.56%，范围-0.10%至+27.68%；双rank为+0.60%，四rank为-0.64%，后二者范围都跨越零。不能将负值当作开启计时带来的加速，也不能宣称开销固定。
开启模式的十步kernel/insert累计rank最大值中位数分别为：1rank 20.956/23.230 ms，2rank 8.918/9.536 ms，4rank 8.072/7.198 ms。它们包含最终验收/反力回调，未包含所有装配工作，不能与callback_seconds直接相减。
端到端wall和solve定义不同：前者还包含MPI启动、输出及报告同步。完整范围见报告JSON。

## 适用范围与审核问题

仅独立流体小模型、单节点、每组5对，共享VM；未独占、未隔离各类扰动，没有显著性结论。建议保持诊断默认关闭，调查时显式开启；优化前补目标规模证据。
请审核配对统计和时间范围。练习：构造三对耗时，说明“比值的中位数”和“中位数的比值”为什么不同。

## 参考资料

- [EONSim计时契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)
- [PETSc performance manual](https://petsc.org/release/manual/performance/)

待人工审核草稿，未发布。
