---
title: "重复线性求解中的 PETSc 对象所有权"
description: "用 PC 析构计数验证正常返回和异常退出时的 KSP 释放。"
contentStatus: draft
taskId: "SOLVER-05"
baseCommit: "a48de95"
resultCommit: "c47f00d11f6ba6edf07d6eab4d9711db64140a7d"
date: "2026-10-30"
---

# 重复线性求解中的 PETSc 对象所有权

## 研究问题与读者

面向使用 PETSc 与 C++ RAII 的开发者：一个成员变量由 RAII 管理，是否就能保证重复创建对象不会泄漏？本例回答调用方覆盖 owner 内指针时的问题。

## 开发前状态

基线的 `LinearSystem::solve` 每次将 `solver_.put()` 传给 `KSPCreate`。
`put()` 只返回内部指针地址，没有先销毁旧对象。第二次调用覆盖第一次 KSP 的地址，最终析构只能释放最后一次对象。
这是源码确认的所有权缺陷；旧实现上的新测试在第一次调用后即报告 PC 尚未释放，未继续测量累计泄漏字节数。

## 理论与数学背景

测试解对称正定系统 `A x = b`，其中 `A = [[2,-1],[-1,2]]`、`b = [0,3]`，精确解为 `[1,2]`。
生命周期修复不改变方程。CG 仍由 PETSc 执行，EONSim 仍检查真实残量。

资源管理依据是每个创建的 KSP 必须有可达的所有者调用 `KSPDestroy`；它负责释放关联 PC 的引用。C++ 栈对象在正常返回及异常展开时析构。此论证不覆盖进程强制终止或非对称 MPI 异常造成的挂起。

## 算法与代码实现

1. 在一次 `solve` 的作用域创建 `PetscOwner<KSP, KSPDestroy>`。
2. 配置算子、KSP、PC 和容差，执行求解及已有验收。
3. 复制结果后返回，或在失败时抛出异常；两条路径均析构该 owner。

矩阵和向量继续属于 `LinearSystem`；KSP 每次重新读取选项。

固定提交源码：

- [线性求解实现](https://github.com/saitoasukakawaii/EONSim-new/blob/c47f00d11f6ba6edf07d6eab4d9711db64140a7d/src/algebra/linear_system.cpp)
- [生命周期回归测试](https://github.com/saitoasukakawaii/EONSim-new/blob/c47f00d11f6ba6edf07d6eab4d9711db64140a7d/tests/verify_linear_lifetime.cpp)

## 数值与生命周期验证

测试注册一个作用为恒等映射的 shell PC，统计创建与销毁次数。
同一个系统依次执行成功、成功、迭代上限为零的预期失败、恢复成功；每次返回后均要求创建数等于销毁数。每个 rank 最终各创建/销毁四次，成功调用检查 owned 和 ghost 解误差小于 `1e-10`。

实际执行（先激活 Cloud 工具链）：

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim verify_linear_lifetime --parallel 4
ctest --preset release -R '^(linear_lifetime|linear_lifetime_mpi|poisson_verification|poisson_parallel)$' --output-on-failure
cmake --build --preset debug --target verify_linear_lifetime --parallel 4
ctest --preset debug -R '^linear_lifetime(_mpi)?$' --output-on-failure
```

Release 4/4 通过；Debug 2/2 通过。修复前 Release `linear_lifetime` 失败，报 `Solve retained its KSP/PC after return or failure`。使用 PETSc 3.23.7、Open MPI 5.0.8、GCC 15.3；MPI 规模为 1/2 rank。未运行全套 CTest。

## 性能证据

未测量内存增长、释放字节数或运行加速；析构计数不能换算成性能收益。

## 适用范围、局限与审核问题

本修复针对 `LinearSystem::solve`，不实现持久化非线性会话，不保证其他 owner 的 `put()` 可被安全重复覆盖。
测试覆盖正常路径和收敛失败路径，未注入所有 PETSc API 错误，也不构成大规模 HPC 验证。
请审核作用域销毁与调用者预期是否一致，以及计数测试是否足以约束未来重构。练习：如果改为复用同一个 KSP，应如何重新定义测试的创建/销毁时点？

## 参考资料

- [PETSc KSPCreate](https://petsc.org/release/manualpages/KSP/KSPCreate/)
- [PETSc KSPDestroy](https://petsc.org/release/manualpages/KSP/KSPDestroy/)
- [PETSc PCShellSetDestroy](https://petsc.org/release/manualpages/PC/PCShellSetDestroy/)
- [离散与算子契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)

本文为待人工审核草稿，不进入生产网站。
