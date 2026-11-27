---
title: "整体 FSI 的压力粗化与单节点性能"
description: "用保持原方程的对照实验区分多重网格迭代数、应用成本和端到端时间。"
contentStatus: draft
benchmark: "FSI-SCALABLE-01"
sourceReference: "docs/development/FSI_SCALABLE_SOLVER.md"
eonsimCommit: "78a90ad7d3d21cd43a4ca591d0e86cb388948704"
---

# 整体 FSI 的压力粗化与单节点性能

## 验证目标

面向实现并行有限元预条件器的读者。本算例考察压力像粗化与插值构造成本，以及粗层 MPI 参与数对端到端成本的影响。

## 理论

若压力插值列正交，\(P_p P_p^T\) 是压力粗空间的正交投影。离散散度作用 \(B P_v\) 的投影剩余可以独立量化未捕获的耦合。完整局部散度像有可能满秩。保留必需模式，再选择投影剩余的主奇异方向，可以在预算内优先保留局部散度像的能量；全局粗层稳定性仍需独立检查。

## 实现

`src/algebra/monolithic_fsi_mg.cpp` 从实际矩阵取聚合体的压力行，包括与远端非压力未知量的连接。严格 QR 与截断 Gram 特征分解分别由配置选择。截断只改变预条件器。粗层重分布由 PETSc Telescope 在指定 rank 子集上执行。[PETSc Telescope](https://petsc.org/release/manualpages/PC/PCTELESCOPE/)

## 验证与性能

计算使用共形 Tet4 弹性 FSI 双域、压力载荷和 ALE，五步，每步 0.02。小规模使用 MUMPS 直接参考，大规模比较同方程迭代轨迹、完整最终场与原算子真实残量。703 自由度的直接参考对照通过，压力层从 125 降至 36 和 5。1、2、4 rank 的制造解将压力自由度从 24 降到 8。

PETSc 3.23.7 Release、双 EPYC 7763、8 MPI × 1 OpenMP 下，10,387 自由度三次交错对照的中位数为 10.651、3.598 和 3.775 秒，分别对应原 Braess–Sarazin、关闭能量优化、关闭能量优化后增加压力压缩。第三个配置比第二个少 18 次外迭代。108,379 自由度时二者的单次试跑分别为 37.135 和 40.596 秒。详见[实现报告](../../docs/development/FSI_SCALABLE_SOLVER.md)与[实验索引](../../docs/research/data/fsi-scalable-01/README.md)。

## 审阅问题

有界压力基实际保留的低频模式能否在更细网格改善 Schur 谱？粗层数据移动何时能用更低的局部求解成本抵消？本算例的固定物理、网格窗口和单节点证据为这些对照提供实测起点。
