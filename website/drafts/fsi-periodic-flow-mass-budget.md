---
title: "周期流量入口与移动流体域的质量预算"
description: "离散入口归一化、stage 与体积 secant 的区别及真实 FSI 验证。"
contentStatus: draft
algorithm: "P1 inlet flux normalization and moving-domain mass diagnostics"
sourceReferences: []
eonsimCommit: "9bde79765ee57a2c42eb2964ac8297ec6246e3a7"
---

# 周期流量入口与移动流体域的质量预算

面向实现低阶 ALE/FSI 的开发者。目标是区分“规定入口速度形状”“规定离散总流量”和“验证移动域质量预算”。本稿为待人工审核草稿。

## 数学与假设（理论推导）

假设不可压流体、固定进出口、无滑移可变形壁、共形 P1 速度和仿射 Tet4 几何。入口流入为正，出口和壁面沿流体外法向为正。散度定理与移动域输运关系给出

$$
Q_{in}-Q_{out}=\int_{\Gamma_w}u\cdot n\,dA=\frac{dV_f}{dt}.
$$

若矩形入口节点形状为横向归一化坐标的乘积 `phi=r1(1-r1)r2(1-r2)`，必须积分其 **P1 插值** 而非连续四次多项式。令

$$
I_h=\sum_{F\subset\Gamma_{in}}\frac{A_F}{3}\sum_{a=1}^3\phi_a,
\qquad u_a(t)=\frac{Q(t)}{I_h}\phi_a e_x.
$$

负 x 外法向下，离散入口积分恰为 Q(t)。只在边界周边有节点的网格可能 I_h=0，此时应拒绝并加密，不能除以零或静默施加零流量。该形状不是充分发展矩形管解析解。

## 时间层与预算（理论/实现）

BE/BDF2 的本质边界规定终点值；generalized-alpha 求解阶段值，由相邻端点波形插值，保证恢复后的端点正确。阶段质量残差

$$
r_s=Q_{in,s}-Q_{out,s}-\int_{\Gamma_{w,s}}u_s\cdot n_s\,dA
$$

与当前阶段的体散度积分相反。另一方面，`(V_(n+1)-V_n)/dt` 是 secant；它通常不等于 BDF2/alpha 所用的阶段运动学导数。即使 r_s 达到舍入精度，也不能要求用 secant 替换壁面通量后的残差机器为零。一般 Tet4 体积还是位移的非线性函数，时间离散与体积函数不能任意交换。

因此同时输出：阶段通量/体散度、端点体积、有限步体积率，以及不同步长下的累计通量积分误差。不能用后处理积分的名称声称求解器更改了时间格式。

## 源码与分布式组织（实现证据）

固定源码提交见 frontmatter：[fsi.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/9bde79765ee57a2c42eb2964ac8297ec6246e3a7/src/physics/fsi.cpp)，配置在 `src/core/config.cpp`，案例在 `cases/fsi/generate_wall.py`。

一次初始化归一化入口并验证边界交线；每步由统一 SNES 求解流体、固体、ALE；阶段和终点几何都有效之后计算诊断，再共同提交。MPI 只归约标量，不收集全局场。新诊断沿用分布式界面邻接识别，内部面不能被计为壁面。

拒绝步不输出接受历史；恢复从物理位移重建体积，避免独立累计体积状态失配。所有入口参数进入 checkpoint 签名。没有改变长期单体架构、稳定化或求解容差。

## 实测及边界（验证证据）

[完整验收、命令、原始 CSV/日志](../../docs/research/data/fsi-flow-2026-11-03/README.md)。Debug/Release 新增检查通过，覆盖三时间格式、1/2 rank、无滑移/界面相容、整体 Jv、真实缩步重放与恢复。六周期研究最大阶段质量残差 3.08e-16；n=2 时 dt=.002/.001/.0005，梯形通量积分累计体积误差绝对值分别 4.97e-8/4.26e-9/6.25e-10。该积分是后处理检查，不是新的推进算法。

n=2/3/4 的位移仍有网格敏感性，末周期仍有剩余瞬态；未证明空间渐近收敛或严格周期稳态。全局质量平衡不证明逐单元强守恒、充分发展流或高 Re 稳定性。

## 性能与进一步检查

没有性能结论；仅执行小型 1/2-rank 验证。新诊断需遍历本地单元/边界并归约少量标量，其开销未专项测量。

练习：对同一张入口网格分别用连续归一化常数与 I_h，比较实际输入流量；再比较 stage 预算、端点梯形累计预算与 secant 混合预算。更高阶单元或移动入口需要重新推导积分和几何时间关系，不能直接套用本实现。

参考入口：本文质量关系由散度定理和移动域体积导数直接推导；项目 [时间契约](../../docs/development/TIME_INTEGRATION.md) 与 [FSI 能力说明](../../docs/development/FSI_PERIODIC_FLOW.md) 给出具体实现范围。未使用未经核实的文献引用。

## 合入状态与云端验收补记（2026-11-03）

实现已通过 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 合入 `main`，合并提交为 [`4f3a995`](https://github.com/saitoasukakawaii/EONSim-new/commit/4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e)。实现提交仍为 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`。

PR 云端 PETSc 3.23.7 Debug/Release 各 29/29 项相关检查通过，零失败、零跳过；[数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) 和 [网站/草稿隔离 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264) 均成功。对应证据保存在 `docs/research/data/fsi-flow-2026-11-03/README.md` 与 `delivery-ci.json`。

本文仍为 draft：源码已合入不代表文章已经过人工编辑审核或进入正式知识栏目。