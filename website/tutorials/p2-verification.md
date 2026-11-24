---
title: 验证 P2 三角形的共享边和时间阶
description: 通过局部解析测试、空间加密和瞬态制造解逐步检验二次有限元。
---

# 验证 P2 三角形的共享边和时间阶

在线性三角形网格上构造二次标量场，要给三个顶点和三条边各分配一个自由度。几何仍由三个角点决定。这个例子适合已经做过 P1 装配、准备检查高阶场或 MPI 分区实现的读者。

## 检查两个相邻三角形

用重心坐标 $\lambda_i$，顶点基函数为 $\lambda_i(2\lambda_i-1)$，边基函数为 $4\lambda_i\lambda_j$。两个共边三角形共有 **4 个顶点和 5 条边，合计 9 个自由度**。分区两边必须用同一对原始端点 ID 辨认共享边，并为其拥有行准备两侧单元贡献的列。单元公式正确而共享边身份错误，仍然会产生错误的全局解。[P2 形函数](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/include/eonsim/tri_p2.hpp) · [共享边与分区实现](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/src/fem/scalar_p2_space.cpp)

## 运行定向验证

从仓库根目录执行。首次运行先恢复 PETSc 3.23.7 的锁定环境。已有该环境时可直接运行第二行。测试清单覆盖局部解析值、稳态 Poisson、瞬态扩散、同分区重启和失败恢复。

```bash
bash scripts/cloud/restore.sh 3.23.7 .cloud
bash scripts/cloud/run.sh 3.23.7 release explicit .cloud docs/research/data/p2-transient-2026-11-03/release-plan.json
```

在 `build/cloud-3.23.7-release/evidence/ctest.log` 中可以按下面的顺序核对结果。[选测清单](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/p2-transient-2026-11-03/release-plan.json)

| 检查 | 观测什么 |
|---|---|
| `tri_p2_oracles` | 六个二次单项式是否重现，参考单元的一致质量、刚度和载荷是否匹配独立解析量。 |
| `scalar_p2_verification` | 先看可精确表示的二次场，再看正弦制造解加密。归档的最细两级给出 $L^2$ 阶 2.9699、$H^1$ 阶 1.9711。 |
| `scalar_p2_time` | 令空间部分为可精确表示的二次多项式，时间乘 $e^{-t}$。归档最细两级的 BE 阶为 0.988，BDF2 为 2.157。 |
| `scalar_p2_restart` 与 `scalar_p2_failure` | 在同一分区上对照连续运行与重启后的完整场，并检查拒绝步能否按实际步长重放。 |

空间试验比较固定问题下不同网格的误差；时间试验固定可精确表示的空间场，再比较不同步长。这两组观测覆盖直边 Tri3 几何上的 P2 标量问题。重启结论适用于相容参数与同一分区。[空间验证数据](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/p2-2026-11-01/debug-numerics.json) · [时间验证数据](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/p2-transient-2026-11-03/release-time.json)

**动手核对。** 在参考三角形上分别积分顶点和边基函数。三个顶点的积分都为零，三个边基函数各为三角形面积的三分之一。据此可以解释纯 Neumann 稳态问题为什么要用有限元积分求物理均值。再检查瞬态的正定一致质量矩阵为何仍然保有常数模态的物理演化。[二维标量模型与边界条件](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/development/SCALAR_2D.md)
