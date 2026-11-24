---
title: "仿射四面体中的黏性项与 ALE 几何导数"
description: "用精确节点力、方向导数和成对测量检查一次局部核优化。"
contentStatus: draft
benchmark: "transient fluid and elastic FSI on affine Tet4"
sourceReference: "https://github.com/CEED/libCEED/releases/tag/v1.1.2"
eonsimCommit: "4095e4bd4e18a350e62fd2e295d88de3a6d48640"
---

# 仿射四面体中的黏性项与 ALE 几何导数

面向正在实现低阶 NS/FSI 单元的开发者。在当前变形的四面体上，哪些量会随积分点改变？这个问题可以先用纸笔回答。

仿射 Tet4 上，$g_a=\nabla N_a$ 为常量。对单元内常黏度和线性速度场，黏性应力也处处相同。速度测试分量 $i$ 的节点力为 $V_e\mu\sum_j(\partial_j u_i+\partial_i u_j)g_{aj}$。固定单元几何时，速度切线为 $V_e\mu[\delta_{ik}(g_a\cdot g_b)+g_{ak}g_{bi}]$。在一次残量求值内提取这个常项即可。在 ALE 的下一次 Newton 试算中，体积和梯度都须由新的节点坐标计算。

`include/eonsim/fluid_residual.hpp` 中的同一残量供普通浮点与自动微分使用。固定几何切线在 `src/physics/fluid_element.cpp`，FSI 的几何导数经 `src/physics/fsi_element.cpp` 进入局部雅可比。简单剪切有解析节点力，刚体转动应得零黏性力。还可以单独扰动流体或网格自由度，将切线作用与中心差分比较。本次 FSI 最大相对方向导数误差为 $8.97\times10^{-11}$。

在同一 AMD EPYC 9V74 上，PETSc 3.23.7 Release、384 个四面体、单 MPI 进程，固定网格瞬态流体六对测量的单元核耗时中位变化为 −29.6%，整次墙钟为 −2.6%。弹性 FSI 的单进程墙钟中位变化为 +1.9%，范围跨过零。入口数据、容差、计时边界及双进程结果见[测量记录](../../docs/research/data/tet4-viscosity-2026-11-24/README.md)。

进一步阅读时可对比 libCEED 对几何数据的构造与作用阶段。可将黏度改成空间变化的 $\mu(x)$ 或将 Tet4 改为曲边映射，重新写出残量积分后，再判断哪些项可以提取。[libCEED 固定版本例程](https://github.com/CEED/libCEED/blob/3e4923a9e20c2077457664cae137ca59c1438064/examples/ceed/ex1-volume.c)
