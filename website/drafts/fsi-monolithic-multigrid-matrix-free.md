---
title: "整体 FSI 多重网格：混合粗块、结构顺应性与流水线故障恢复"
description: "完整混合 Galerkin、受约束插值、局部谱增强，以及精确方向算子和 MPI 生命周期的实现与有限验证。"
contentStatus: draft
algorithm: "Monolithic FSI multigrid and exact matrix-free flexible Krylov"
sourceReferences:
  - "https://doi.org/10.1137/100803031"
  - "https://petsc.org/release/manualpages/KSP/KSPPIPEFGMRES/"
  - "https://fenapack.readthedocs.io/en/latest/demos/navier-stokes-pcd.html"
eonsimCommit: "3b5cbddb928dfa789dc1f3f424dba451f33107e6"
---

# 整体 FSI 多重网格：混合粗块、结构顺应性与流水线故障恢复

本文面向已经了解 Newton、Schur 补及 AMG 的数值软件开发者。学习目标是区分完整混合层级
与场分裂 AMG，理解粗层 patch 的正确规模，以及矩阵自由回调错误为何必须尊重 Krylov
通信协议。本文是未发布草稿；操作参数见[使用指南](../../docs/development/FSI_MONOLITHIC_MULTIGRID.md)，
可复现原件见[证据索引](../../docs/research/data/fsi-monolithic-mg-2026-11-26/README.md)。

## 1. 问题定义与证据等级

研究对象是当前 EONSim 的共形低阶三维 FSI：流体速度和压力、结构速度及 ALE 网格位移，
经过接口未知量消元和边界约束后，使用同一物理残量及 Newton 修正。结构位移、加速度、
电路和时间历史只在共同接受后提交。预条件器的近似不能改变这个物理接受过程。

- **理论**：下述块消元是代数恒等式；插值采用明确的正正规能量；PETSc 文档与标记源码
  支持所用 Krylov、telescope 及回调协议。这里没有一般 FSI 粗空间稳定性证明。
- **实现**：源码固定为 `3b5cbddb928dfa789dc1f3f424dba451f33107e6`，对应 PR #61。
- **验证**：独立制造解、方向导数、原始场/历史和日志残量的实际检查；失败原件保留。
- **性能**：共享单主机、Release、PETSc 3.23.7、最多 4 rank。单次时间仅反映已测运行，
  不支持独占硬件、多节点扩展性或普遍加速结论。

## 2. 完整混合 Galerkin 层级

设约束后的 assembled 预条件矩阵为 \(A_0\)，层间插值为 \(Z_\ell\)。每层保留

\[
A_{\ell+1}=Z_\ell^T A_\ell Z_\ell.
\]

流体、压力、结构、ALE 的跨场项一同进入该乘积。细层候选含实际语义启用的平移、旋转、
压力常数及标量模式；局部 QR 去除相关列，后续层传播同一候选的粗系数。候选提供可表达
的物理方向，不应被称为包含时间项、边界及全部耦合的动态 Jacobian 的精确零空间。

这与仅在速度块上使用 AMG、在最外层额外做一次界面校正不同。所有非最粗层执行平滑，
最粗层执行完整混合求解；没有把流固系统改成交替的单场时间推进。

## 3. 缩放正规能量与局部谱增强

FSI Jacobian 非对称且不定。为避免把 \(z^T A z\) 当作正能量，实现使用行均衡后的

\[
E(Z)=\|D_r^{-1}A Z\|_F^2.
\]

令 \(B=D_r^{-1}A\)，把下降方向投影到 \(\Delta Z N_c=0\)，保持
\(Z N_c=N_f\)。同时固定局部秩揭示的锚点行，防止新增谱列在下降中塌缩。
非零方向使用一维精确最小化

\[
\alpha=-\frac{\langle BZ,B\Delta Z\rangle_F}{\|B\Delta Z\|_F^2}.
\]

这是有界步数的受约束下降，不是全局最优插值求解。文献 [1] 给出了保留模式并优化能量的
一般框架；本实现采用自己的行均衡、锚点和有界下降细节，不能等同于完整复现其算法。

谱增强在每个聚合体的局部正规矩阵上取相对于局部最大特征值足够小的特征向量，并对物理
候选正交化。`spectral_refresh_period>0` 可按数值刷新周期重建谱基和层级。它不是全局
残差学习，也不是 GenEO 理论条件的实现；局部阈值不能直接推出全局谱界或网格无关性。

## 4. 为什么粗层不宜沿稠密图扩展 patch

细层默认一环 Vanka 包含节点邻域的混合未知量。能量插值扩展支撑后，Galerkin 粗矩阵
可能比原网格图稠密得多。首次 2,299 和 5,367 DoF 实验中，粗层一环 patch 超过 256 行，
程序明确拒绝；703 DoF 时部分粗层 patch 已覆盖整个 225 行层。

修复将 `patch_overlap` 与 `coarse_patch_overlap` 分开，默认分别为 1 和 0。粗层 entity
已经是前一层完整混合聚合体的基，零额外图重叠仍包含其全部物理列和谱列。跨聚合体项继续
存在于完整粗矩阵和层残量；没有截断 patch 行或提高上限。显式要求粗层扩展后超限仍拒绝。

同尺寸 patch 使用至多 8 lane 的独立主元 LU 批处理。相同行集合可共享一次分解计算；
每个 patch 保留自身因子存储。精确相等的数值刷新复用旧因子。另一个实际故障说明了缓存
契约的重要性：重复分布式 `MatPtAP` 会改变深层末位舍入，精确缓存因此正确失效。现在
使用共同的源矩阵数值状态判断，未变化时保留 Galerkin 矩阵，避免无用乘积和因子重建。

## 5. 结构顺应性压力 Schur 与 PCD 增强

把联合速度动量块写成

\[
A_v=\begin{bmatrix}F&E\\G&K\end{bmatrix},\quad
B=\begin{bmatrix}B_f\\B_s\end{bmatrix},\quad C=[C_f\ C_s].
\]

用实际结构代表块的节点逆 \(H_s\approx K^{-1}\)，并令
\(H_f\approx(F-EH_sG)^{-1}\) 为更新后的流体节点逆，则构造

\[
\widehat S=D-C_sH_sB_s-(C_f-C_sH_sG)H_f(B_f-EH_sB_s).
\]

时间步、质量和刚度通过实际 \(K\) 进入结构反馈。两侧耦合分别取真实 \(E,G,B,C\)，
不假设互为转置；保留完整压力稳定化 \(D\)。节点近似仍是近似，不等于精确结构逆。

PCD 的入口 Robin 使用当前 ALE 相对速度，并精确积分三个 P1 因子的三次面项
\(-\int_{\Gamma_{in}}\rho[(u-w)\cdot n]pq\,dS\)。符号及辅助入口边界概念与 [2] 的
BRM2 说明核对，生产积分另以独立 Hammer 三次规则验证。

速度质量增强以物理 lumped \(M_u\) 构成
\(K_{new}=(1-\theta)K_{geo}+\theta[-C\,\mathrm{diag}(M_u)^{-1}B]\)，并同步设置
\(F_{new}=F_{old}+\mu(K_{new}-K_{old})\)。保留物理压力质量和辅助边界的黏度尺度，
避免破坏 Stokes 质量极限。这是带几何部分的离散 Laplace 混合版本，不是标准加性 PCDR；
当前仍要求空间均匀正黏度。
精确辅助求解下，保留稳定化的稳态作用极限为 \((\mu^{-1}M_p+D)^{-1}\)，
只有 \(D=0\) 时简化为 \(\mu M_p^{-1}\)。

## 6. 精度、并行和平滑成本

FP32 V-cycle 实际存储 float CSR 系数，并在层矩阵、限制及延拓中使用 float 稀疏乘加。
Vanka 用 FP32 因子及 FP64 残量细化，必要时回退；粗解和外层保持 FP64。FP64 setup
矩阵仍然保留，所以 float 数值数组减半不意味着总内存减半。

Chebyshev 对 \(B=DAC\) 的隐式 \(B^TB\) 平滑；\(C\) 为列缩放或同实体块白化。
正上界取 \(1.05\|B\|_1\|B\|_\infty\)，应用时不做全局 dot 或特征值估计。它不是
直接对不定 Jacobian 使用 SPD 多项式。当前小例的外层迭代远多于 Vanka，不能称为默认更快。

最粗层通过 PETSc `PCTELESCOPE` 在缩小的 communicator 上求解 [3]；中间层仍保留
原 communicator。PIPEFGMRES 使用 PETSc 的右预条件实现，实际重叠效果依赖 MPI 进展 [4]。

## 7. 精确 Jv、assembled P 和失败的通信协议

流体/ALE 单元使用单方向 AD，包含几何、稳定化和移动压力面的导数；结构和壁支撑局部切线、
RCR 方向项及接口消元链系数同样进入精确作用。当前 Newton 状态与线搜索试探状态分开保存。
assembled P 可按显式间隔更新，每次新的 nonlinear solve 先刷新。小例中 P 组装由 6 次
降为 3 次；Jv 仍使用当前状态。当前 P 保留完整稀疏图，不能宣称总稀疏矩阵存储下降。

注入错误发现了两种不同的库协议问题：

1. PETSc 3.23.7 `KSPSolve_Private` 在 Krylov 调用前锁定 RHS；回调提前返回会跳过解锁。
   仅替换 trial 向量不足以恢复。实现隔离 trial 和残量 RHS，并重新准备新残量的 COO 计划。
2. PIPEFGMRES 的 `VecMDotBegin` 和 `VecMDotEnd` 之间执行预条件和矩阵作用。直接从 Jv
   返回错误会遗留 split-reduction 状态，使下一次求解报错。现在先保留共同 fatal 错误，
   暂时返回有限零输出，让库完成归约，然后由收敛回调返回负停止原因。错误后不再调用物理
   kernel，退出后无条件抛出原错误，临时向量不能成为 accepted 状态。

正常路径完整调用原配置的收敛测试，并正确转交其上下文析构责任；没有访问 PETSc 私有锁
或归约结构。标记源码位置为 [5] 的 RHS 锁和 [6] 的管线循环；这两个故障均有失败、修复
及 1/2/4-rank 恢复的真实记录。

## 8. 实现与验证

主要源码：`src/algebra/monolithic_fsi_mg.cpp`、`fsi_level_smoother.cpp`、
`interface_patch_pc.cpp`、`pressure_schur_pc.cpp`、`nonlinear_system.cpp`，以及
`src/physics/fsi_element.cpp`、`fsi.cpp`、`fsi_pressure_operators.cpp`。

当前有效本地定向覆盖为 22 项：压力 8 项、整体/patch/层平滑 9 项、矩阵自由 3 项、
运行环境及局部方向导数 2 项，按对应源码分别执行或复用。最后受影响物理复验 28 次全部
通过；此前四次粗层超限和两轮矩阵自由恢复失败单独保留。全部命令、来源和独立原件审计
在证据索引中列出，不把早期检查伪称为最后 head 重跑。

源码 CI45819157827 实际执行 95/95 项 Release 和 54/54 项 Python 检查，成功收据的
完整清单与 JUnit 相符；merge preview 与生产 source tree 相同。后续文档提交只复用
这些不受影响的证据，不再计为新的数值执行。

物理门槛保持为场和历史绝对差 \(2\times10^{-9}\)，原算子真实线性残量
\(10^{-12}+10^{-10}\|b\|\)。独立审计重读 XML/CSV/log、owner/ghost 和拓扑，
重新检查已记录的残量标量；未保存 J/b/增量，因此没有离线再次执行矩阵乘法的证据。

## 9. 已测行为与适用边界

相同 2-rank、三步六次 Newton 修正的网格对照：

| DoF | 整体 MG FP64 外迭代 | FP32 外迭代 | FP64 线性秒数 | FP32 线性秒数 |
|---:|---:|---:|---:|---:|
| 703 | 104 | 104 | 0.388 | 0.770 |
| 2299 | 151 | 151 | 2.524 | 4.199 |
| 5367 | 206 | 206 | 10.206 | 15.264 |

该窗口中迭代增长近一倍，不能称为网格无关；FP32 也没有显示端到端时间优势。小型共享
主机可能不处于带宽受限区间，且细化、转换及额外数据结构都有成本。多项式、pipeline、
混合精度仍作为显式选项，默认物理求解配置未被这些实验替换。

进一步研究应围绕粗空间稳定性、真正的大规模通信/带宽测量，以及更经济的 assembled P。
本次不把未执行的多节点试验、区域变黏度或百万自由度场景记为完成。读者可思考：为何局部
低正规能量方向不必等于全局最难消除误差？为何更便宜的粗 patch 可增加迭代而降低总时间？

## 10. 参考文献与官方源码

1. Olson, Schroder, Tuminaro. *A General Interpolation Strategy for Algebraic Multigrid Using Energy Minimization*.
   SIAM J. Sci. Comput. 33(2), 966–991 (2011), DOI: [10.1137/100803031](https://doi.org/10.1137/100803031)。
   参考其模式保持约束及非对称问题的能量框架；[作者版原文](https://lukeo.cs.illinois.edu/files/2011_OlScTu_energymin.pdf)。
2. FENaPack：[BRM2 辅助入口边界示例](https://fenapack.readthedocs.io/en/latest/demos/navier-stokes-pcd.html)
   与[数学说明](https://fenapack.readthedocs.io/en/latest/math.html)。
3. PETSc：[PCTELESCOPE](https://petsc.org/release/manualpages/PC/PCTELESCOPE/)，缩小 communicator 上的求解。
4. PETSc：[KSPPIPEFGMRES](https://petsc.org/release/manualpages/KSP/KSPPIPEFGMRES/)，右预条件及异步进展限制。
5. PETSc v3.23.7：[itfunc.c，KSPSolve_Private](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/interface/itfunc.c)。
6. PETSc v3.23.7：[pipefgmres.c，KSPPIPEFGMRESCycle](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/impls/gmres/pipefgmres/pipefgmres.c)。

上游 release 文档可能随版本更新；实际验证依赖固定为 PETSc 3.23.7，故故障推导引用标记源码。
