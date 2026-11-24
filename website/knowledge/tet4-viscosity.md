---
title: 四面体黏性项如何只积分一次
description: 从解析节点力和 ALE 方向导数，到单元核、装配与整次求解的配对测量。
---

# 四面体黏性项如何只积分一次

在四节点线性四面体上，给定本次试算的节点坐标后，每个速度形函数的梯度都是常量。如果黏度在单元内也恒定，黏性应力和检验函数的梯度在所有积分点都相同。把这项积分提到积分点循环之外，可以同时写清速度切线和网格运动的导数。

## 从残量推出切线

令 $V$ 为当前单元体积，$g_{aj}=\partial_j N_a$ 为第 $a$ 个形函数梯度的第 $j$ 个分量。对牛顿流体的对称黏性应力，节点 $a$、方向 $i$ 的残量以及对速度自由度 $u_{bk}$ 的固定几何切线为

$$
R^\mu_{ai}=\mu V\sum_j(\partial_j u_i+\partial_i u_j)g_{aj},
\qquad
K^\mu_{ai,bk}=\mu V\big[\delta_{ik}(g_a\cdot g_b)+g_{ak}g_{bi}\big].
$$

积分后的 $V$ 和 $g_a$ 仍依赖网格位移。单体 FSI 每次 Newton 试算都用当前坐标计算这两个量，并在自动微分中传递几何导数。质量、对流和稳定化沿用各自的积分规则。[流体残量](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/include/eonsim/fluid_residual.hpp) · [固定几何切线](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/src/physics/fluid_element.cpp) · [FSI 单元](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/src/physics/fsi_element.cpp)

## 用两个速度场校核

在畸变四面体上令 $u_x=\gamma y$、其余速度分量为零。节点 $a$ 的黏性力应为 $\mu V\gamma(g_{ay},g_{ax},0)$。再令 $u_y=-\gamma x$，得到刚体转动，对称应变率和黏性节点力都为零。两个场都能同时检查残量和切线作用。另行扰动流体与网格自由度，对照中心差分，归档的流体和 FSI 最大相对方向导数误差分别为 $5.67\times10^{-11}$、$8.97\times10^{-11}$。[解析测试](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/tests/verify_fluid_element.cpp) · [数值验证记录](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/tet4-viscosity-2026-11-24/validation.json)

## 单元核节省的时间有多少传到整个求解过程？

测量使用单机 AMD EPYC 9V74、PETSc 3.23.7 Release、384 个流体四面体、10 个后向欧拉步。固定网格流体和弹性 FSI 分别有 500 和 730 个自由度。两版均用 SuperLU_DIST 直接解、相同容差和诊断开关。每组先各预热一次，再交替顺序测六对。下表为单进程每对“优化后耗时 / 基线耗时 − 1”的中位数和样本范围。各计时区间相互包含。

| 算例与计时范围 | 中位变化 | 六对样本范围 |
|---|---:|---:|
| 固定网格流体 · 单元核 | −29.6% | −35.1% 至 −27.1% |
| 固定网格流体 · 装配 | −17.8% | −22.2% 至 −13.0% |
| 固定网格流体 · 整次运行 | −2.6% | −4.1% 至 −0.2% |
| 弹性 FSI · 整次运行 | +1.9% | −5.9% 至 +3.7% |

固定网格流体在这六对中均缩短了整次耗时。弹性 FSI 的范围跨过零，还需分别测量固体装配、ALE 切线和线性求解成本。比较两种实现时应保持诊断开关一致，细粒度计时自身也有开销。[逐对数据与复现命令](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/tet4-viscosity-2026-11-24/README.md) · [计时开关的对照实验](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md)

**进一步试算。** 将黏度换成随空间变化的 $\mu(x)$，写出仍能移出积分点循环的因子；再把几何换成曲边单元，检查 $g_a$ 和体积因子在哪一步开始随积分点变化。[libCEED 的几何量构造示例](https://github.com/CEED/libCEED/blob/3e4923a9e20c2077457664cae137ca59c1438064/examples/ceed/ex1-volume.c)
