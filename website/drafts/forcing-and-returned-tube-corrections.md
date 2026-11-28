---
title: "逐校正验证弹性管的线性容差"
description: "用返回向量的原方程残量、求解设置和完整物理轨迹约束 inexact Newton。"
contentStatus: draft
algorithm: "Inexact Newton"
eonsimCommit: "757588fa86e32cb19a59c575c2d78a346e4c21c6"
---

# 逐校正验证弹性管的线性容差

时间步内，装配矩阵 $A_k$ 与右端 $b_k$ 定义当前 Newton 校正。令 $x_k$ 为线性求解器实际交回的 FP64 向量，接受条件为

$$
\|b_k-A_kx_k\|_2 \le \max(a_k,\eta_k\|b_k\|_2).
$$

两边使用同一组原变量。非零初猜可以改变 Krylov 轨迹，分母仍取原右端。零右端由有量纲的绝对门槛 $a_k$ 控制。各 rank 只计拥有的方程行。分量后向误差用每行的 $|b_i|+\sum_j |A_{ij}x_j|$ 作分母，可帮助区分抵消误差与块内停滞。

固定模式下 $\eta_k$ 取声明的相对容差。在已有的 inexact Newton 实现中，前后右端范数的比值、forcing 的下限和上限共同决定下一次请求。新时间步和重试重新初始化这段历史。审计器从运行前声明独立重算 $\eta_k$，并与 PETSc 的实际设置、校正标识及返回向量比较。PREONLY 的直接因子解使用显式 LU 精化容差。实现见 `src/algebra/nonlinear_system.cpp` 中的 `LinearPolicy`、`linear_end` 和 `guarded_krylov_convergence`。

B 管首步第一次校正的右端范数约为 $5.52652\times10^{-9}$。作业 469 使用直接参考候选的相对容差 $10^{-8}$，生产原残量为 $1.58077\times10^{-17}$，低于本次门槛 $5.52652\times10^{-17}$。较早的严格作业 456 使用 $10^{-10}$，其失败保留在原协议下。物理资格还要求两个独立算法在每个时间步分别接受，在同一组 SI 特征尺度下逐相位比较两域完整场、通量与终端电路历史。

每次减少 Krylov 迭代后，都要重新计入 Newton 校正、线搜索、设置及输出时间。B20 的固定容差从 $10^{-6}$ 改到 $10^{-4}$ 时，Newton 校正由 40 增至 60。这里的敏感性结论限定于冻结网格和 $\Delta t=1/32$ s。逐次作业、MPI 布局和计时口径见[阶段报告](../../docs/development/FSI_SCALABLE_05.md)。
