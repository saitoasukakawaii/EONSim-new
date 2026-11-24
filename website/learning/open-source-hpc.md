---
title: HPC 开源软件阅读指南
description: 从 EONSim 的开发问题出发，查阅 50 个上游项目的源码、接口与设计取舍。
outline: [2, 3]
---

# HPC 开源软件阅读指南

同样是读有限元代码，想加速单元积分、设计出口边界、定位并行通信开销，需要找的函数截然不同。下面按开发问题给出阅读入口。随后列出 2026 年 11 月 24 日复查的全部 50 个项目，其中 47 个固定到 Git 提交，3 个取自官方在线源码或文档。

## 从开发问题选入口

| 你正在做什么 | 先看什么 | 回到 EONSim 验证什么 |
|---|---|---|
| 减少单元核中的重复工作 | libCEED 的积分点数据、MFEM 的装配层次 | 先找单元内恒定的量，再用节点力、方向导数和端到端耗时验证改动。[Tet4 算例](/knowledge/tet4-viscosity) |
| 分析单体 FSI 的线性求解成本 | PERIGEE 如何分别计时，PETSc 如何构造 FieldSplit | 在同一残量、网格和容差下记录装配、预条件器建立与应用的时间。[单体 FSI](/knowledge/monolithic-fsi) |
| 给血管出口接一个 RCR 模型 | svZeroDSolver 的 Windkessel 元件和 svMultiPhysics 的时间层 | 设计时先约定外流方向、压力自由度和接受步历史，再以恒流阶跃和单频阻抗核验。这个出口属于后续开发项目。[设计方程](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/HPC_UPSTREAM_REVIEW_2026-11-24.md?plain=1#L97) |
| 评估 GPU 或自适应网格 | Kokkos 的执行与内存空间、RAJA 的循环策略、t8code 的重分区 | 先量出限制算例的环节，再比较同精度下的总时间、内存或迁移误差。[上游架构研究](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/UPSTREAM_ARCHITECTURE_REVIEW.md) |

## 50 个项目的源码与文档

各表标出了实际阅读的材料。“实现 / 接口”可直接进入对应代码；“仓库说明”与“官方文档”用于了解项目能力和适用范围。最后一列说明该材料对 EONSim 的用途，具体采用情况可回到项目记录核实。[完整调研与开发优先级](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/HPC_UPSTREAM_REVIEW_2026-11-24.md)

<!--@include: ../../docs/research/HPC_UPSTREAM_REVIEW_2026-11-24.md#upstream-projects-->
