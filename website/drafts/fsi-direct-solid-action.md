---
title: "EONSim：固体直接方向导数与零初值多重网格作用"
description: "在保留装配对照与原接受门槛的前提下，降低精确 matrix-free FSI 的局部作用成本。"
contentStatus: draft
taskId: "FSI-MF-02"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/62"
baseCommit: "6bb6f438b63c4a375cb143532640532cbb47921d"
resultCommit: "b7d727bd10231c22987b18114d1e25d622b2b8f1"
date: "2026-11-26"
---

# 固体直接方向导数与零初值多重网格作用

状态：未发布草稿。适合已理解有限元残量及 Newton 线性化、准备实现矩阵无关作用的开发者。
学习目标是区分“没有装配全局 J”和“没有计算完整局部 J”，并从实际时间映射推导一个方向的作用。

## 目标与开发前状态

【实现观察】#61 的流体方向作用已经直接计算；固体仍调用完整 `solid_element(..., true)`，
生成12×12单元切线，再乘一个方向。Neo-Hookean还形成9×9材料切线，并计算该次作用不使用的
残量、能量与应力输出。整体MG每层清零初始校正后，首次残量仍执行A乘零向量。

本轮只改变这些作用的计算方式。原残量、装配切线、时间历史、预条件矩阵及接受门槛保留。
源码固定于[b7d727b](https://github.com/saitoasukakawaii/EONSim-new/commit/b7d727bd10231c22987b18114d1e25d622b2b8f1)，
实际命令、输入、原件和独立审计见[证据索引](../../docs/research/data/fsi-mf-02-2026-11-26/README.md)。

## 从当前离散推导方向作用

【推导】参考构形Tet4、节点速度未知量v、时间参考位移d₀，写成

\[
F=I+\sum_a(d_{0,a}+h_d v_a)\otimes\nabla N_a,
\qquad \delta F=h_d\sum_a\delta v_a\otimes\nabla N_a.
\]

`h_d`是位移对速度的链系数；惯性系数另用有效时间步`h_v`。BE/BDF2当前映射可取同一
有效步长，generalized-alpha允许二者不同。静力状态为位移，`h_d=1`、忽略历史位移且无惯性项。

线弹性直接计算

\[
\delta P=\mu(\delta F+\delta F^T)+\lambda\operatorname{tr}(\delta F)I.
\]

现有可压缩Neo-Hookean能量为

\[
W=\frac\mu2(F:F-3)-\mu\ln J+\frac\lambda2(\ln J)^2,
\quad J=\det F>0.
\]

令Q=F⁻ᵀ，c=λlnJ−μ，则P=μF+cQ。由δlnJ=Q:δF、δQ=−QδFᵀQ得到

\[
\boxed{\delta P=\mu\delta F+\lambda(Q:\delta F)Q-cQ\delta F^TQ.}
\]

只形成这些3×3量，随后直接收缩至节点：

\[
\delta r_{a,i}=V\sum_J\delta P_{iJ}\nabla_JN_a
+\frac{\rho V}{h_v}\sum_b m_{ab}\delta v_{b,i},
\qquad m_{ab}=\frac{1+\delta_{ab}}{20}.
\]

静力省略质量项。方向为零时仍检查NH当前构形；不能因为输出应为零就绕过非有限F或非正J。
新旧路径均先累加位移梯度再加I，避免在几何检查之前额外改变求和次序。

参考面法向支撑的方向作用为

\[
\delta r^\Gamma_a=\sum_b A_\Gamma m^\Gamma_{ab}
(k h_d+c_d)n(n\cdot\delta v_b),
\qquad m^\Gamma_{ab}=\frac{1+\delta_{ab}}{12}.
\]

这是固定参考面积、法向的模型，不能推广为随当前几何变化的接触或追随载荷导数。
多个支撑面分别累加；非连续局部节点和斜面法向不能用轴对齐假设替代。

## 已知零初值的 V-cycle

【推导与实现】每次递归cycle首先在全部rank设置x=0，因此第一次残量r=b−Ax就是b。
实现直接复制rhs；若`pre_smooth=0`，在限制至粗层之前使用同一个已知状态。
后续残量仍完整计算，失败后的通信顺序、粗校正和identity行处理保持。

默认一前一后平滑时，每个非粗层用于构造残量的矩阵乘由3次减至2次。这只统计外层cycle的
层残量乘，不包括Vanka/Chebyshev内部、传递或粗解；不能声称全部矩阵乘或通信减少三分之一。
已知状态不需要范数归约，也不能替换为各rank自行检测零向量后选择不同collective分支。

## 实际修改与验证

| 文件 | 实现 |
| --- | --- |
| `src/physics/solid_element.cpp` | solid_element_action及WallSupportFace::action；保留完整装配对照 |
| `src/physics/fsi.cpp` | matrix-free固体分支直接作用，保留界面方向映射和逐面累加 |
| `src/algebra/monolithic_fsi_mg.cpp` | 已知零状态残量、实际/省略作用计数及谱重建保留 |
| `tests/verify_solid_element.cpp` | 完整切线和残量差分双参考；可选局部核配对计时 |
| `tests/verify_monolithic_fsi_mg.cpp` | pre=0、pre=2/post=0、FP32、空owner、失败恢复与计数 |

【数值证据】Release定向4/4通过；14组固体、12组支撑的直接作用对原切线最大归一化差
3.40×10⁻¹⁶和1.49×10⁻¹⁶，残量中心差分也通过。11次受影响FSI全部通过，覆盖1/2rank，
包含NH、支撑、移动RCR、非等步长GA和FGMRES/PIPEFGMRES。额外9次固定输入成本运行
单独计数，包括1参考、2warmup和3对旧/新二进制。

独立审计合计20run/60接受步/156条真残量，最大保存场差3.20×10⁻¹³，owner/ghost差为0；
真残量与原门槛之比最大0.009044。核查的是求解时记录的原算子残量标量，没有保存J/b/dx，
因此不是离线重新计算Jdx−b。完整数值范围、哈希和限制在审计JSON中。

## 性能证据与限制

【性能证据】AMD EPYC 9V74共享单机、9个可见CPU、Release/GNU15.3/OpenMPI5.0.8/PETSc3.23.7，
每rank单OMP/BLAS线程。局部核每种配置7对、每条路径每对20,000次，变化状态并交替次序：

| 模型 | 支撑 | 旧路径中位ns | 直接作用中位ns | 配对耗时降低中位 |
| --- | --- | ---: | ---: | ---: |
| 线性 | 无 | 404.42 | 91.27 | 76.94% |
| 线性 | 有 | 484.98 | 119.05 | 75.75% |
| NH | 无 | 935.73 | 162.96 | 82.08% |
| NH | 有 | 979.75 | 177.00 | 81.94% |

降低率是每对比值的中位数，因此不要求等于两个独立中位耗时的比值。
350DoF、2rank的同输入移动血管3对测量中，两版均155次外层迭代、173次MF作用；
MF作用阶段rank0耗时中位降低23.27%，范围22.40%–32.26%。整程序wall比值中位1.0144，
范围0.9131–1.0699，未见稳定收益。线性阶段也有跨零波动。

没有改变完整assembled P的存储，没有证明网格无关、总内存下降或多节点扩展。
局部作用成本与完整Newton/Krylov、预条件setup、MPI、输出成本应分别报告。

## 参考与进一步检查

- 当前[固体残量、材料与直接作用源码](https://github.com/saitoasukakawaii/EONSim-new/blob/b7d727bd10231c22987b18114d1e25d622b2b8f1/src/physics/solid_element.cpp)。
- 独立的[Neo-Hookean完整材料切线](https://github.com/saitoasukakawaii/EONSim-new/blob/b7d727bd10231c22987b18114d1e25d622b2b8f1/src/physics/hyperelastic.cpp)。
- [单体FSI契约](../../docs/architecture/L2_MONOLITHIC_FSI.md)和[时间映射](../../docs/development/TIME_INTEGRATION.md)。

练习：从上式分别令`h_d=h_v`、关闭惯性、或施加纯刚体旋转，核对方向作用与完整切线。
后续只有针对明确更大算例的成本和收敛目标，再设计相应验证，不由局部测量推断未运行的规模收益。
