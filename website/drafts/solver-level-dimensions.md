---
title: "EONSim 开发记录：读取求解器层级算子尺寸"
description: "补齐 GAMG 层级规模证据，同时避免诊断创建原本不存在的矩阵。"
contentStatus: draft
taskId: "SOLVER-04B"
baseCommit: "f1e9594"
resultCommit: "124bed3d7f9e95cdce61633f1109314b32dfecf7"
date: "2026-10-30"
---

# EONSim 开发记录：读取求解器层级算子尺寸

## 研究问题

SOLVER-04 已记录迭代数，却缺少各 GAMG 层的算子尺寸。为了判断粗层规模，需要读取现有 KSP 的元数据，并避免诊断反过来触发对象创建或 setup。
本文面向 PETSc 分布式求解器开发者。

## 理论与数学含义

若某层算子为 A：其全局行列数描述该层线性映射，局部行列数描述当前 rank 的布局。全局尺寸基于 A 自身的 communicator，不是每个 world rank 独立持有的工作量。
因此不能将各 rank 输出的 global rows 相加当作总 DoF。粗层允许本地行数为零，尺寸也不能直接代表非零元、内存或计算成本。

## 算法与实际实现

`describe_solver` 先调用 `KSPGetOperatorsSet`；仅在 A 已设置时调用 `KSPGetOperators` 借用矩阵，再读取 `MatGetSize`、`MatGetLocalSize`。
该新增路径不调用 setup、装配或 MPI 规约。未设置 A 时 `operator_set=0`、四个尺寸为 -1。
读取的是 KSP 的 A，而不是可能不同的预条件矩阵 P。现有层级遍历的范围和限制仍适用。

- [实际实现](https://github.com/saitoasukakawaii/EONSim-new/blob/124bed3d7f9e95cdce61633f1109314b32dfecf7/src/algebra/nonlinear_system.cpp)
- [回归检查](https://github.com/saitoasukakawaii/EONSim-new/blob/124bed3d7f9e95cdce61633f1109314b32dfecf7/tests/verify_schur.py)
- [字段契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)

## 数值验证证据

在既有 Cloud 工具链（GCC 15.3、PETSc 3.23.7、Open MPI 5.0.8）下执行：

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim verify_solver_failures --parallel 4
ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure
cmake --build --preset debug --target verify_solver_failures --parallel 4
ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure
```

Release 3/3、Debug 2/2 通过。Schur 测试包含四类问题的 1/2/4 rank 与直接解对照，新增检查各层尺寸有效、顶层 global rows 等于 DoF，以及每次报告的顶层 local rows 在 world rank 上求和等于 DoF。
失败测试覆盖线性/PC 故障及初态满足方程时零次迭代成功返回。未设置算子的 -1 分支未由本轮集成测试单独构造触发。

旋转通道的实际输出：顶层为 256×256，速度块为 192×192、压力块为 64×64。1/2 rank 时 rank 0 看到速度粗层 6×6、压力粗层 3×3；4 rank 时压力粗层为 1×1。这说明分区改变时粗层结构可能变化，不能仅根据原始网格猜测粗层大小。
日志路径为 `build/release/schur_verification/flow_schur{1,2,4}.log`，可由上述测试重建；本轮未把临时构建日志作为永久性能数据提交。

## 性能证据

未测量诊断开销或求解加速。这是可观测性增量，未改变数学方程、容差、PC 配置或迭代策略。

## 适用范围与审核问题

适用于现有层级报告可遍历的 KSP；尚不提供各层非零元、P 矩阵尺寸、累计子层迭代或独立 PC setup 时间。
请审核 communicator 语义、未设置对象的处理及既有日志解析兼容性。练习：为什么每个 rank 都报告全局 256 行，但两 rank 的本地行数可以不同？

## 参考资料

- [PETSc KSPGetOperatorsSet](https://petsc.org/release/manualpages/KSP/KSPGetOperatorsSet/)
- [PETSc KSPGetOperators](https://petsc.org/release/manualpages/KSP/KSPGetOperators/)
- [PETSc MatGetSize](https://petsc.org/release/manualpages/Mat/MatGetSize/)
- [PETSc MatGetLocalSize](https://petsc.org/release/manualpages/Mat/MatGetLocalSize/)

待人工审核草稿，未发布。
