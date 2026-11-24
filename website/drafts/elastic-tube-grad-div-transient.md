---
title: "为什么相同端压会得到不同的弹性管扩张量"
description: "用四分之一厚壁圆管区分面积应变的分母、时间加载、离散散度与独立瞬态参照。"
contentStatus: draft
benchmark: "弹性管两端同步平滑升压"
sourceReference: "svFSI 2022.09.26, 94a2ff5"
eonsimCommit: "85546ef04a707764e27a5b06adfc5b20b858e4cb"
---

# 为什么相同端压会得到不同的弹性管扩张量

取一段长 2 m 的直管，内、外半径分别为 1 m 和 1.2 m。管内初始静止，外压为零，两端的压力在 1 s 内同时由零升至 0.02 Pa。初始上下游压差为零，流体仍从两个端面进入，因为扩张的管腔需要补充体积。两个正交对称面限定四分之一圆截面，固体端面轴向约束允许径向运动。流体密度和固体密度均为 1 kg/m³，动力黏度 1 Pa·s，壁材杨氏模量 100 Pa、泊松比 0.3。这些数值用于检验离散方程。[算例输入与场](../../docs/research/data/fsi-smooth-load-2026-11-24/README.md)

## 先说明百分比的分母

在 48 扇区网格上对齐两程序实际装配的阶段压力，步长取 1/128 s。到 1 s，左端的截面积相对于原面积增长 0.073399%（EONSim）和 0.064489%（svFSI），相减为 **0.008910 个百分点**。以 svFSI 此时的扩张量为分母，相对差为 13.82%。改用该压力对应的 Lamé 解析稳态面积应变作统一分母，七个截面的最大差为 4.0975%，最大值恰在同一端面。统一分母便于在其他位置和时间比较接近零的瞬态信号。[截面原始记录](../../docs/research/data/fsi-smooth-load-2026-11-24/README.md#one-term-control-of-discrete-incompressibility)

## 一次改变一个离散项

等阶四面体的离散速度可以留下单元内非零散度。在动量方程中加入

$$
\int_{\Omega_f} \tau_C (\nabla\cdot w)(\nabla\cdot u)\,dV
$$

会改变速度场，也会通过共享的界面速度改变管壁扩张。取 $w=u$ 且 $\tau_C\ge 0$，该项给出非负的散度惩罚。在同一 svFSI 版本中，仅将此项的系数置零，保持原网格、受压面、压强稳定化和收敛容差。在 1 s，原生 svFSI 对 EONSim 的七截面最大差为 4.0975%，消去该项后降到 0.4967%，流体离散散度的体积加权 RMS 则由 5.696e−4 增至 6.673e−4 s⁻¹。这个对照给出了该项对这一细化步长下程序间差异的直接证据。[单项改动与配对计算](../../docs/research/data/fsi-smooth-load-2026-11-24/grad-div.json)

EONSim 也可以使用常系数 grad-div 项。在同一工况分别取 0、1、4 和 16 Pa·s，散度 RMS 随系数增加而下降，与原生 svFSI 的管壁响应差却先缩小后增大。svFSI 的系数随局部度量、速度和时间步变化，某个常数在这个网格上的吻合程度不能确立通用取值。[常系数扫描](../../docs/research/data/fsi-smooth-load-2026-11-24/fixed-grad-div.json)

## 用独立瞬态解检查小振幅极限

从同时静止的流体和管壁出发，将压力和速度、位移一起按振幅展开。对流项与几何更新乘以已有流动的项均从高一阶开始。保留一阶后得到带代数约束的线性系统 $M\dot y+Ky=f(t)$。在同一网格上独立组装质量、黏性、弹性、压强和稳定项，用三阶 Radau IIA 时间推进。这样可以直接检验一套给定半离散方程在第一秒的面积响应。

在固定 PSPG 系数、256 个 EONSim 时间步及 128 个 Radau 时间步下，将峰值压力从 0.02 Pa 减至 0.0002 Pa，默认零 grad-div 的最大一秒截面差由解析稳态面积应变的 0.02017% 降至 0.000187%。该基准验证了同一网格的小振幅实现。判断哪种离散更接近连续弹性管的瞬态响应还需要空间参照，Lamé 解能够检验的是静态极限。[独立方程、方法与 30 次运行](../../docs/research/data/fsi-linear-transient-2026-11-24/README.md)

Independent axisymmetric refinement estimates the 1 s left-end expansion at 0.0788759% of initial area. On the 48-sector mesh the two native values are 0.0733993% and 0.0644891%. The independently calculated tiny-amplitude limit separates model accuracy from intercode agreement. See [the continuum reference](../../docs/research/data/fsi-linear-transient-2026-11-24/axisymmetric.md).
