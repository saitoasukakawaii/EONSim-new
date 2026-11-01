---
title: "从顶点场到共享边自由度：P2 Poisson"
description: "直边三角形二次标量空间的分区、图和局部验收。"
contentStatus: draft
taskId: "FEM-G2A"
baseCommit: "35bf1a1"
resultCommit: "edfc73c"
date: "2026-11-01"
---

# 从顶点场到共享边自由度：P2 Poisson

面向已有 P1 装配经验的开发者。本草稿未审核、未发布。

## 理论与实现边界

参考重心坐标下，顶点形函数为 λᵢ(2λᵢ−1)，边函数为 4λᵢλⱼ。六个节点值确定二次多项式；几何仍由三顶点的仿射映射提供。该区分避免把新增场节点错误地解释成曲边几何支持。

源码 edfc73c：include/eonsim/tri_p2.hpp 提供参考值与梯度，src/fem/scalar_p2_space.cpp 提供离线实体空间，src/physics/scalar_p2.cpp 接入既有 PETSc LinearSystem。

实体身份使用原始端点 ID 对，不按浮点坐标合并；边 owner 取邻接单元 rank 最小值。预处理在全局单元连接可用时建立 owned 行完整邻接，不能只使用本 rank 积分单元，否则远程单元的 MatSetValues 会越过预分配图。边界标签也从全局外边传播到各 DoF。

## 实际验证

本地 Debug、PETSc 3.23.7，运行 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json`，清单仅 scalar_p2_verification。1/2 rank 二次 patch 与 n=4/8/16 正弦加密通过；最细 L2/H1 阶为 2.9699/1.9711。独立局部测试还检查六个单项式、解析刚度与载荷。证据保存于 docs/research/data/p2-2026-11-01。云端最终结果待补，不把局部测试等同真实求解。

在 rank 1 缺失组、破坏连接或 owner 的三个实际 MPI 负例中，作业退出且没有发布成功索引。理论身份与文件校验均不能替代数值误差检查。

## 限制与审查问题

仅稳态统一系数、纯 Tri3、D/N 且有 Dirichlet 锚定；不支持曲边、Robin、纯 Neumann、瞬态、混合空间或跨分区重启。没有性能测量。下一步审查应关注空间文件的身份一致性和 MPI 远程行完整性；完整 G2 仍未完成。

练习：对两三角形共享边列出九个全局自由度，解释共享边 owned 行为什么需要九列，而非单个局部单元的六列。

参考：[VTK 二次三角形节点顺序](https://vtk.org/doc/nightly/html/classvtkQuadraticTriangle.html)；仓库 docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md 的空间、稀疏图与输出契约。
