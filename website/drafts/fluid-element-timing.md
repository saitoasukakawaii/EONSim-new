---
title: "EONSim 开发记录：独立流体 kernel 与插入计时"
description: "用显式诊断区分体单元计算和 PETSc 插入，并验证开启后物理解不变。"
contentStatus: draft
taskId: "HPC-01D"
baseCommit: "2e7e9a9"
resultCommit: "1722265fc4c5ac625ffea144d06f424528fdb8f6"
date: "2026-10-30"
---

# EONSim 开发记录：独立流体 kernel 与插入计时

## 研究问题与理论

面向 FEM/MPI 开发者：先前 callback_seconds 同时包含单元计算和稀疏插入，无法支持分别归因。本增量在独立流体驱动层加入显式诊断，不改变局部方程或求解算法。
FEM 体单元计算形成残量向量及可选切线矩阵，随后由 VecSetValues/MatSetValues 累加到分布式代数对象。插入耗时包括本地条目处理与远程 stash 准备；真正的最终装配在后续阶段，不能把插入时间等同于通信时间。

## 算法与实际实现

通过 `-fluid_element_report` 开启，在 state/编号 gather 之后计时 `fluid_element`，随后分别计时该体单元的 VecSetValues 与可选 MatSetValues。每次非线性 solve 成功返回后按 rank 输出本地累计时间与残量/切线单元计数。
关闭时不执行单元级时钟读取、计数更新或报告同步；kernel 内没有新增 MPI、PETSc 或 I/O。

- [驱动实现](https://github.com/saitoasukakawaii/EONSim-new/blob/1722265fc4c5ac625ffea144d06f424528fdb8f6/src/physics/fluid.cpp)
- [开关对照测试](https://github.com/saitoasukakawaii/EONSim-new/blob/1722265fc4c5ac625ffea144d06f424528fdb8f6/tests/verify_fluid_element_report.py)
- [完整计时字段契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)

`residual_elements` 表示无切线的单元调用；`jacobian_elements` 表示有切线的调用（也产生残量）。它们不是两个互不相关的物理模型。
计时包含最终物理验收及原始反力回调，不能与在 SNESSolve 返回时冻结的 callback_seconds 直接相减；面载荷、最终装配、约束、压力归一化后反力修正不包含在单元计时中。

## 验证证据

Cloud 工具链为 GCC15.3、PETSc3.23.7、OpenMPI5.0.8，资源配额4 CPU/32 GiB。执行：

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim --parallel 4
ctest --preset release -R '^fluid_element_report$' --output-on-failure
cmake --build --preset debug --target eonsim --parallel 4
ctest --preset debug -R '^fluid_element_report$' --output-on-failure
```

每个构建的测试覆盖 steady、10步 transient、rotated_channel 标签边界，1/2 rank，每组开启/关闭对照。比较全部节点物理字段（含速度、压力、动量残量），开关绝对差阈值1e-12，跨rank阈值2e-8；检查计时有限非负、每rank/每步报告恰好一次、无切线/有切线计数均为本地单元数的正整数倍。
Release 与 Debug 均通过。以 Release steady 双rank输出为例，本地单元数190/194，无切线调用1140/1164、有切线调用570/582，即每rank六次无切线遍历、三次有切线遍历。临时日志可在 `build/release/fluid_element_report/` 重建。

## 性能证据与局限

本轮是诊断实现与数值不变性验证，没有重复性能实验或计时开销估计；不得从单次诊断值宣称加速。开启时逐单元时钟读取有额外开销。
仅覆盖独立流体，未给 FSI/ALE 增加同样计时。整个 solve 失败时不输出该次计数，重试重新开始；同次成功 solve 中若存在被拒评价，已经完成的单元工作仍会计入。本轮没有构造这种拒绝路径的新专门测试。
原始每rank时间允许后续分析不均衡，但尚未分别计时本地/远程插入。完整 HPC-01 仍需目标规模下的测量，不由本增量自动完成。

## 审核与进一步学习

请审核计时区间和计数语义，以及是否需要针对目标规模量化逐单元计时的扰动。练习：解释为何有切线调用也计算残量，而无切线计数不是全部残量评价次数。

## 参考资料

- [PETSc MatSetValues](https://petsc.org/release/manualpages/Mat/MatSetValues/)
- [PETSc VecSetValues](https://petsc.org/release/manualpages/Vec/VecSetValues/)
- [PETSc performance manual](https://petsc.org/release/manual/performance/)

待人工审核草稿，不进入生产构建。
