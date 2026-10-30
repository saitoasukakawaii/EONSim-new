---
title: "EONSim 开发记录：MPI失败传播与可复现云端验证"
description: "从rank-local PC失败到共同退出，再验证accepted状态恢复。"
contentStatus: draft
taskId: "INFRA-01"
baseCommit: "38a5e51"
resultCommit: "d3f69d1"
date: "2026-10-30"
---

# EONSim 开发记录：MPI失败传播与可复现云端验证

## 目标与研究问题

面向维护MPI数值程序与CI的开发者：某个rank的局部LU失败时，为什么诊断本身可能死锁？
怎样证明失败后的第二次求解没有使用受污染的trial状态？本次沿用既有方程、停止条件与测试，不新增物理模型。

## 理论与依据

这里没有新的有限元推导。关键是分布式控制流契约：所有参与同一个collective的rank必须以一致顺序进入它。
正的本地KSP原因码不能在所有版本/配置下当作共同收敛证据；PC失败枚举也不一定为正数。
accepted与trial分离，不等于库内部对象状态自动恢复；库函数提前返回可以留下未完成的借用状态。

这些约束对应[并行契约](../../docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)及[状态契约](../../docs/architecture/L2_MULTIPHYSICS_AND_STATE.md)。

## 实现：实际源码与算法

源码提交[ d3f69d1 ](https://github.com/saitoasukakawaii/EONSim-new/commit/d3f69d1)：

| 位置 | 行为 |
|---|---|
| [nonlinear_system.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/d3f69d1/src/algebra/nonlinear_system.cpp) | 旧版postsolve先统一PC失败标志；本地保留原始原因树；fatal callback后更换trial Vec |
| [verify_solver_failures.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/d3f69d1/tests/verify_solver_failures.cpp) | 三种报告模式、fatal Jacobian与同对象恢复、accepted不变、精确解检查 |
| [verify_checkpoint.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/d3f69d1/tests/verify_checkpoint.cpp) | 在测试故意破坏current前等待所有读者完成 |
| [cloud入口](https://github.com/saitoasukakawaii/EONSim-new/tree/d3f69d1/scripts/cloud) | 锁恢复、配额控制、预检、原CTest、JUnit/JSON和超时后代清理 |

PETSc3.19.6的PREONLY可能在rank0给出4、rank1给出-11；原真实残量诊断的MatMult/VecNorm因此只被部分rank调用。
修复先归约“是否PC失败”，独立于报告开关。失败时共同返回错误；诊断不额外setup或做collective。
原因码作为分类证据保留，不用其大小作逻辑真假比较。

主环境还复现fatal Jacobian早退后trial Vec只读锁残留。修复Duplicate并交换持久trial Vec，而非强行弹出PETSc内部锁；旧向量由SNES/Mat已有引用管理。下一次solve重新写入accepted副本并同步ghost，矩阵/COO图保持。

## 验证证据

[INFRA-01报告](../../docs/research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md)记录具体环境、最小复现、上游行号和最新验收结果。

- 未改main在独立云端3.19.6环境复现原60秒超时；最小PETSc程序确认rank原因码分叉。
- 修复后的两套环境针对性检查各7/7通过，断言恢复解为0.1、原accepted输入不变、错误分类不混淆。
- 主环境Debug/Release完整短套件各35/35通过；Poisson阶数2/1、MPI最大差约3.55e-15、COO最大字段差约3.31e-12。最终head CI仍以报告更新为准。
- 真实两rank超时负例确认为Timeout且后代已终止/回收；这属于故障基础设施验证，不能混入成功求解次数。
- OpenMPI5两槽位/四rank启动验证确认需要PRRTE映射变量；不以减少rank掩盖问题。

## 性能证据

未进行新性能实验。失败标志归约是旧版可靠性适配；不声称其开销为零，也不从小规模测试推导强扩展效率。

## 范围、局限与审核问题

已验证Linux云端、两个锁定PETSc/OpenMPI组合、正常顶层KSPSolve。没有覆盖任意PETSc提前异常、transpose/MatSolve、不同MPI ABI、GPU或多节点。
主锁要求x86-64-v3，自动资源探测面向cgroup v2。应用Debug仍使用优化PETSc包。
草稿保持未发布。审核重点是失败阶段、原始原因保留及新trial/旧Vec引用的生命周期，而非仅检查退出码。

## 参考与进一步阅读

- [PETSc3.19.6 PREONLY](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/ksp/impls/preonly/preonly.c)：rank-local失败原因。
- [PETSc3.20.0 PREONLY](https://github.com/petsc/petsc/blob/v3.20.0/src/ksp/ksp/impls/preonly/preonly.c)：PCReduceFailedReason。
- [PETSc3.23.7 SNESComputeJacobian](https://github.com/petsc/petsc/blob/v3.23.7/src/snes/interface/snes.c#L2966)：callback前后Vec读锁。
- [最小复现源码](../../docs/research/reproductions/petsc319-preonly.cpp)。
- 练习：关闭所有报告再运行局部PC失败，说明为何只给诊断加保护不足以保证旧SNES的共同退出。
