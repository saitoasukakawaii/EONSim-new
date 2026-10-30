---
title: "数值基准报告：小网格上的 Schur/GAMG 行为"
description: "三个网格、1/2 rank 的直接解对照与重复性能测量。"
contentStatus: draft
benchmark: "SOLVER-04 steady flow"
eonsimCommit: "79eb826"
---

# 数值基准报告：小网格上的 Schur/GAMG 行为

## 研究问题与理论

面向准备调优 PETSc 块求解器的读者：随着网格增加，当前 Schur/GAMG 的迭代与成本如何变化？
对块 Jacobian `[A B; C D]`，精确 Schur 补为 `D-C A^-1 B`。EONSim 使用 SELFP 近似与 GAMG 子块，不由这个名称推断网格无关收敛。

## 算例、算法与源码

使用稳态单位立方体通道，Tet4/P1 速度压力、既有稳定化，密度/黏度均为 1，内置抛物速度边界和原点压力定标。
同一网格先求直接参考，再用 FGMRES、FULL Schur/SELFP、GAMG 运行三次。压力定标一致，按原始节点 ID 和 owner 比较节点物理字段。

- [测量脚本](https://github.com/saitoasukakawaii/EONSim-new/blob/79eb826/scripts/profile_schur_mesh.py)
- [Schur 实现](https://github.com/saitoasukakawaii/EONSim-new/blob/79eb826/src/algebra/schur_solver.cpp)
- [完整设置、命令、结果及证据入口](../../docs/research/SCHUR_MESH_PROFILE_2026-10-30.md)

## 数值验证证据

108、500、1372 DoF，分别在 1/2 rank 运行；6 个直接参考、18 个 Schur 样本全部通过。与直接解最大节点字段差小于 4.084e-12。
这是同一离散方程的求解器一致性证据，不是对连续方程精度或实验真实性的证明。n=6 输出压差仍偏离输入参数，详细离散误差见研究报告。

## 性能证据

Release，GCC 15.3、PETSc 3.23.7、Open MPI 5.0.8，4 CPU/32 GiB 配额，每 rank 单线程。
单 rank 累计 KSP 迭代为 25/31/39；solve 中位数为 0.006406/0.025670/0.076670 秒。双 rank 为 27/31/39，solve 为 0.015056/0.038243/0.087477 秒。
每项三次，无专门预热或随机化，范围与原始日志已归档。计时嵌套，子块 last_iterations 是最后一次调用，不能相加当作总工作量。

## 适用范围、局限与审核问题

本次没有网格无关收敛或并行加速证据；最大仅 1372 DoF，不外推跨节点或 FSI。未测每层矩阵尺寸和独立 PC 累计成本，不提出未经验证的调参结论。
请审核参考解比较口径、计时包含关系和误差表述。进一步练习：解释为何代数解一致而空间离散误差仍可显著。

## 参考资料

- [PETSc PCFIELDSPLIT](https://petsc.org/release/manualpages/PC/PCFIELDSPLIT/)
- [PETSc PCGAMG](https://petsc.org/release/manualpages/PC/PCGAMG/)

本文为待人工审核草稿，不进入生产构建。
