---
title: 移动流体域的质量预算
description: 用离散入口归一化、同一时间层的通量，以及接受步体积变化核验单体 FSI。
---

# 移动流体域的质量预算

弹性血管可以在一个时间步内储存流体。固定的进出口、不可压流体和无滑移可动壁满足 $Q_{\rm in}-Q_{\rm out}=\mathrm dV_f/\mathrm dt$。入口流入为正，出口流出为正。检查这条关系时，需要先确认求解器在边界上实际施加的流量，再对齐通量和体积的时间层。

## 从节点速度得到指定入口流量

在固定平面入口上给一个沿内法向单位矢量 $e$ 的形状。令 $g_i$ 是节点形状值，$n_T$ 是三角面片外法向，$A_T$ 是其面积。P1 三角面上每个形函数的积分为 $A_T/3$，因此离散的单位形状流量和速度系数为

$$
D_h=-\sum_T\frac{A_T}{3}(e\cdot n_T)\sum_{i\in T}g_i,
\qquad u_i(t)=\frac{Q(t)}{D_h}g_i e.
$$

对同一个 P1 边界场积分就得到 $Q(t)$。圆盘可取 $g_i=\max(0,1-r_i^2/R^2)$。如果节点全在圆周，$D_h=0$，网格需要内部节点才能施加该形状。代码在各进程拥有的流体边界面上积分，用一次标量归约获得 $D_h$。[离散入口的实现](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/src/physics/fsi.cpp) · [圆管几何与接口条件](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/development/RIGID_TUBE_QUALIFICATION.md)

## 在同一阶段检查通量，在接受步上检查体积

1. 在求解阶段 $s$ 的同一构形和时间上计算 $r_s=Q_{{\rm in},s}-Q_{{\rm out},s}-\int_{\Gamma_{w,s}}u_s\cdot n_s\,\mathrm dA$。独立计算体散度积分，可核对面法向与阶段场。
2. 在每个接受步记录 $V_n$、$V_{n+1}$ 以及实际步长。$(V_{n+1}-V_n)/\Delta t$ 是步内平均体积率；BDF2 或 generalized-α 的阶段导数使用自己的时间权重。
3. 对接受端点的净流量 $Q_{\rm in}-Q_{\rm out}$ 做梯形积分，与首末体积差比较，并在同一张网格上减小步长。[时间积分契约](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/development/TIME_INTEGRATION.md) · [周期流量算例](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/development/FSI_PERIODIC_FLOW.md)

## 六周期算例中的两个读数

下表来自共形弹性壁通道的 Release 双进程研究。固定每方向两等分网格，流域和固域各有 48 个四面体。六个加载周期使用同一网格与载荷。最后一列是累计端点通量积分减去首末体积差的绝对值。

| 步长 | 接受步数 | 最大阶段通量残差（绝对值） | 累计体积误差（绝对值） |
|---:|---:|---:|---:|
| 0.002 | 310 | $5.20\times10^{-18}$ | $4.972\times10^{-8}$ |
| 0.001 | 620 | $5.64\times10^{-18}$ | $4.264\times10^{-9}$ |
| 0.0005 | 1,240 | $5.64\times10^{-18}$ | $6.247\times10^{-10}$ |

阶段通量残差始终很小，累计体积误差随时间加密下降。全局积分对正负局部误差可能相互抵消，位移、周期收敛和局部分辨率还需分别核对。练习时可从原始接受步 CSV 重算梯形积分，再对照各分辨率的壁面位移和相邻周期差。[原始数据、脚本与完整算例](https://github.com/saitoasukakawaii/EONSim-new/blob/5781ae0c01953d123e91cd0ea9f44cd970674b93/docs/research/data/fsi-flow-2026-11-03/README.md)
