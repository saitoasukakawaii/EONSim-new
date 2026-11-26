---
title: "RCR 端口 Schur：从秩一修正到多出口低秩预条件"
description: "推导增广 RCR 系统的端口消元，说明移动出口、非对称耦合、MPI 合并归约和缓存更新的实现边界。"
contentStatus: draft
algorithm: "RCR port Schur and Sherman–Morrison–Woodbury response correction"
sourceReferences:
  - "https://petsc.org/release/manualpages/PC/PCSHELL/"
  - "https://petsc.org/release/manualpages/KSP/KSPFGMRES/"
eonsimCommit: "b731d4713ab8428e02fb52af6547e1aa3097eca0"
---

# RCR 端口 Schur：从秩一修正到多出口低秩预条件

本文面向已了解不可压缩有限元和块预条件器的读者。学习目标是从 RCR 的实际
Jacobian 看清低秩结构，区分物理消元与预条件近似，并把公式对应到 MPI owner
和数值缓存的生命周期。

**证据状态：** 理论部分由下述块消元直接推导；现有 RCR 符号已在 frontmatter
所列基线提交核实。新路径正在 `codex/rcr-port-schur` 实现，尚未执行本轮验证，
尚无本轮性能结论。此草稿未发布，源码提交与运行证据在实际验收后更新。

## 1. 为什么出口电路会影响全局预条件器

RCR 出口的压力由同一个出口的总流量驱动。总流量由许多离散速度自由度共同
决定，出口压力又通过牵引影响这些自由度。因此，即使电路只增加一个标量
未知量，其影响也不局限于一个速度对角元。

在 EONSim 的增广表达中，每个出口保留一个端口压力未知量 `q`，它与所有场
一起参加 Newton 修正。固定出口的一个典型速度/端口块为

\[
J=\begin{bmatrix}A&b\\-b^T&Z^{-1}\end{bmatrix}.
\]

这里 `b` 包含有方向的通量积分权重；`Z` 为当前时间离散产生的有效总阻抗，
不是任意指定的预条件参数。`q` 是压力，不能与流量混用。
由第二行消元 `q`，速度算子得到正的秩一项 `Zbbᵀ`：

\[
K=A+Zbb^T.
\]

上述符号来自基线 `src/physics/fsi.cpp::outlet_jacobian_entries` 中的
`(+weight,-weight,1/total_impedance)`。只记忆“低秩项取减号”容易把实际的
RCR 修正方向弄反；先写出增广块再消元能够避免这类错误。

## 2. 从一出口推到多出口

若 `H=A⁻¹`，单出口 Sherman–Morrison 公式为

\[
(A+Zbb^T)^{-1}
=H-\frac{Z(Hb)(b^TH)}{1+Zb^THb}.
\]

这条式子需要分母非零。多个出口令 `B=[b₁,…,b_k]`，独立出口的 `Z` 为对角
阻抗矩阵，则

\[
(A+BZB^T)^{-1}
=H-HB(Z^{-1}+B^THB)^{-1}B^TH.
\]

小矩阵中的 `b_iᵀ H b_j` 表示第 `j` 个端口激励经 bulk 传播后在第 `i` 个
端口产生的响应，通常不为零。把这个小矩阵只保留对角，相当于又做了一层
独立出口近似，不能称为完整多出口 Woodbury 修正。

## 3. 移动出口需要一般的非对称分块

EONSim 的真实 bulk 还含流体压力、固体速度和 ALE 位移。移动出口的面积和
积分权重依赖当前几何；端口流量行对 ALE/接口映射列也有导数，而端口压力列
不会生成这些转置项。因此，完整矩阵一般具有

\[
J=\begin{bmatrix}A&U\\V&D\end{bmatrix},\qquad V\ne-U^T.
\]

直接从已经施加约束的 Jacobian 分别提取 `U` 和 `V`，可以保留实际几何链式
导数。将 `V` 替换成 `−Uᵀ` 可能仍能产生看似合理的流量曲线，却改变了所声称
求解的端口 Schur。

令 `H` 为 bulk 逆或其近似，缓存

\[
Y=HU,\qquad \widehat S_p=D-VY.
\]

对残量 `(r_b,r_p)`，一次端口预条件作用为

\[
z=Hr_b,\quad q=\widehat S_p^{-1}(r_p-Vz),\quad x_b=z-Yq.
\]

当 `H=A⁻¹` 时，从第一行得 `x_b=A⁻¹(r_b-Uq)`，代入第二行即可得到上式，
故它是精确块逆。当 `r_p=0`，bulk 的一般低秩形式为

\[
H+HU(D-VHU)^{-1}VH.
\]

这里是加号；代入 `V=-Bᵀ` 后才成为前节固定出口的减号形式。
全端口 RHS 也必须参与作用，仅校正 bulk 而丢弃 `r_p` 不能构成增广系统预条件器。

## 4. GAMG 和 BoomerAMG 在哪一层

端口 Schur 包裹的是整个非端口 bulk 求解。bulk 内部仍然可以先分离动力学和
ALE，再在动力学内部使用速度/压力 Schur；GAMG、BoomerAMG、两层或 ASM
作用于所选速度块。端口小系统与这些局部/多层近似相互组合，不直接替代它们。

| 层次 | 处理的问题 |
| --- | --- |
| 完整 Jacobian 与外层 FGMRES | 求满足原线性化方程与真实残量门槛的修正 |
| 端口 Schur | 出口标量与全 bulk 的响应耦合 |
| bulk recipe | 流固/ALE、速度/压力等块间近似 |
| 速度基础 PC | 速度块的空间误差平滑、粗空间或局部因子 |

严格 Woodbury 恒等式要求固定线性 `H`。一次 AMG cycle 可以是固定线性作用，
但若粗层或内层使用按残量停止的 Krylov 求解，整体 `H` 一般不是线性的。
此时缓存各列 `H U_j` 不意味着任意线性组合的响应等于 `H(Uc)`；算法应称为
近似端口响应预条件器。PETSc 的 FGMRES 允许这样的非线性/可变内层作用；
外层原始 Jacobian 与独立残量验证负责检查最终修正的准确性。

BoomerAMG 的每次 cycle 数、内部 tolerance 与外层 `ksp_max_it/ksp_rtol` 是
不同控制项。也不能从开启 hypre 推断已获得向量弹性旋转近空间，或从一个
小网格通过推断网格独立收敛。

## 5. 一次端口归约如何实现

把 `V` 的每一行按 bulk owner 存成分布式列 `w_i=V_iᵀ`。
每个 rank 计算自己 owned 行上的

\[
g_i^{(r)}=\mathbf1_{r=\operatorname{owner}(q_i)}(r_p)_i
-\sum_{j\in\mathrm{owned}(r)}(w_i)_jz_j.
\]

把全部 `k` 个值放入同一缓冲后一次 Allreduce 得到 `r_p−Vz`。
setup 也把全部 `k²` 个 `D−VY` 项合并规约；端口 owner 的 `D` 条目只贡献一次。
空 bulk rank、没有端口 owner 的 rank 仍参加相同顺序的 collectives。

这个优化减少逐出口点积的同步次数，不删除 bulk AMG 的通信。可报告的准确
结论是“端口 apply 的 `k` 个内积合并为一次批量规约”，不是“每次 Krylov 只通信一次”。
完整场和 bulk 矩阵继续分布式存储，只有 `k` 或 `k²` 的端口量在 rank 间复制。

## 6. 缓存必须与基础 PC 同代

可长期复用的是固定 owned 映射、子矩阵索引和工作缓冲；数值缓存为
`A/U/V/D`、bulk PC、`Y` 与小 Schur 因子。缓存刷新必须先形成新的 bulk 近似，
再用它建立新的响应列；否则 `Y=HU` 中的 `H` 与实际 apply 的 `H` 不一致。

已有 `PcSchurUpdates` 是统一更新入口。开启自适应 PC 后，旧近似可以有界
复用，完整 Jacobian 仍保持新鲜。时间系数变化、矩阵漂移、使用年龄、迭代增长
和失败恢复各自提供更新条件；不得在 shell 的普通 apply 内暗中跟随 Jacobian
状态重建，否则外层“保留 PC”的策略与实际行为不符。

任何重建失败都先使本轮缓存不可用；不能混合新 `U` 与旧 `Y`，也不能把失败的
响应列当作成功。C 回调中的错误要转为 PETSc 返回/失败状态，并保证所有 MPI
rank 在共同阶段结束。物理时间历史仍只由外部整体接受步提交。

## 7. 应怎样验证

第一层是独立代数 oracle：对小型、可直接求逆的完整增广矩阵，比较 PCApply
与独立全矩阵解。矩阵应含非对称 `U/V`、非零端口 RHS 和多出口交叉响应；只看
最终外迭代收敛可能掩盖错误的预条件公式。

第二层检查分布式与生命周期：1/2/4 rank，端口散布在不同 owner，存在空 bulk
rank，连续数值更新/复用，奇异与非有限小 Schur 的失败，以及失败后恢复。
统计应证明列响应不会在每次 apply 重算，并区分基础 PC 通信与端口批量规约。

第三层是真实移动边界/多出口 FSI：直接解与新路径比较同分区场、压力/流量历史、
真实线性残量、时间步变化和重启结果。测试必须记录各方案相同的物理配置与
接受阈值；性能则另测 setup、迭代、线性时间和总耗时。

**当前验证状态：待执行。** 代码入口和最终命令见
[开发说明](../../docs/development/RCR_PORT_PRECONDITIONER.md)。新源码先推送，
再运行验收；不得将这份验证设计引用为已通过实验。

## 8. 适用范围、复杂度和限制

每次更新需要 `k` 次 bulk 响应和小系统分解；本地响应数据约为
`O(n_local k)`，Gram 工作约为 `O(n_local k²)`，稠密分解约为 `O(k³)`。
每次 apply 只做一次 bulk 响应，再增加 `O(n_local k+k²)` 的端口修正。
出口数大时更新和内存成本增加，必须与节省的外迭代比较。

算法需要可用的 bulk 近似和非奇异端口 Schur。它不能修复不适定的边界问题、
奇异的物理 Jacobian、错误的几何或不一致的单位。小 Schur 的失败不能通过
任意修改实际阻抗或放宽物理容差来隐藏。

本轮尚无性能数据；多节点、百万自由度、GPU、任意密度/Reynolds 数或任意
出口数量的通用加速均未由本文建立。

## 9. 源码与参考

- 已核实的物理基线：
  [fsi.cpp at b731d471](https://github.com/saitoasukakawaii/EONSim-new/blob/b731d4713ab8428e02fb52af6547e1aa3097eca0/src/physics/fsi.cpp)，
  `outlet_jacobian_entries`。
- 开发中入口：`include/eonsim/rcr_port_pc.hpp`、`src/algebra/rcr_port_pc.cpp`、
  `src/algebra/pc_plan.cpp` 和 `src/algebra/nonlinear_system.cpp`；当前分支
  `codex/rcr-port-schur`，本轮验证提交待实际推送后记录。
- [PETSc PCSHELL](https://petsc.org/release/manualpages/PC/PCSHELL/)：自定义 PC 接口。
- [PETSc KSPFGMRES](https://petsc.org/release/manualpages/KSP/KSPFGMRES/)：非线性/可变预条件作用。
- [PETSc PCGAMG](https://petsc.org/release/manualpages/PC/PCGAMG/)：多层与插值复用。
- [PETSc PCHYPRE](https://petsc.org/release/manualpages/PC/PCHYPRE/)：BoomerAMG 参数语义。

阅读练习：把一般公式中的 `V` 写为 `−Uᵀ+E`，推导忽略几何耦合 `E` 对端口
Schur 产生的差异；再思考为何两个端口几何支撑互不相交，交叉响应仍可能非零。
