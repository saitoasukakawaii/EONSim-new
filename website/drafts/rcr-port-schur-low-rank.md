---
title: "RCR 端口 Schur：从秩一修正到多出口低秩预条件"
description: "推导增广 RCR 系统的端口消元，说明移动出口、非对称耦合、MPI 合并归约和缓存更新的实现边界。"
contentStatus: draft
algorithm: "RCR port Schur and Sherman–Morrison–Woodbury response correction"
sourceReferences:
  - "https://petsc.org/release/manualpages/PC/PCSHELL/"
  - "https://petsc.org/release/manualpages/KSP/KSPFGMRES/"
eonsimCommit: "28e6d54701abced040752aff70b69d29b35f1d01"
---

# RCR 端口 Schur：从秩一修正到多出口低秩预条件

本文面向已了解不可压缩有限元和块预条件器的读者。学习目标是从 RCR 的实际
Jacobian 看清低秩结构，区分物理消元与预条件近似，并把公式对应到 MPI owner
和数值缓存的生命周期。

**证据状态：** 理论部分由下述块消元直接推导；新路径实现于 frontmatter 所列
生产源码，见 [PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)。
本地 Release 代数 1/2/4-rank 与真实移动出口 FSI 验收已通过，最终物理驱动为
`ad08887f8b357ef16e6a6b49b89d968f531f8053`。现有性能数据只来自共享单机的一次
小算例样本，不建立稳定加速结论。此草稿未发布；第 7、8 节分别记录已执行
证据与未验证边界。PR 的远程 CI/合并状态以对应 head 的记录为准。

## 1. 为什么出口电路会影响全局预条件器

RCR 出口的压力由同一个出口的总流量驱动。总流量由许多离散速度自由度共同
决定，出口压力又通过牵引影响这些自由度。因此，即使电路只增加一个标量
未知量，其影响也不局限于一个速度对角元。

在 EONSim 的增广表达中，每个出口保留一个端口压力未知量 `q`，它与所有场
一起参加 Newton 修正。固定出口、保留对偶关系的一个典型活动速度/端口块为

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
导数。即使出口固定，仅替换 Dirichlet 行而保留矩阵列的处理也可能破坏完整
耦合的转置关系。将 `V` 替换成 `−Uᵀ` 可能仍能产生看似合理的流量曲线，
却改变了所声称求解的端口 Schur。

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

## 7. 验证设计与已执行证据

第一层是独立代数 oracle：对小型、可直接求逆的完整增广矩阵，比较 PCApply
与独立全矩阵解。矩阵应含非对称 `U/V`、非零端口 RHS 和多出口交叉响应；只看
最终外迭代收敛可能掩盖错误的预条件公式。

第二层检查分布式与生命周期：1/2/4 rank，端口散布在不同 owner，存在空 bulk
rank，连续数值更新/复用，奇异与非有限小 Schur 的失败，以及失败后恢复。
统计应证明列响应不会在每次 apply 重算，并区分基础 PC 通信与端口批量规约。

第三层是真实移动边界/多出口 FSI：直接解与新路径比较同分区场、压力/流量历史、
真实线性残量、时间步变化和重启结果。测试必须记录各方案相同的物理配置与
接受阈值；性能则另测 setup、迭代、线性时间和总耗时。

**当前代数证据：** `28e6d54` 的 `pc_rcr_port_mpi1/2/4` 三项均通过，0 跳过。
它们用完整矩阵的独立 long-double 消元核对单/双/三端口；三端口包含第二步
主元交换，另有 20 个数量级尺度差、非对称耦合、端口 RHS、空 rank、缓存复用
和故障恢复检查。合成 nonlinear 场景实际记录两次新 Jacobian、零 USER 更新、
保持 `generation=1`，拒绝后的新会话为 `generation=2`。这支持有界缓存策略
确实执行，不是只根据代码推断。

首次 `94046b1` 上的新三项因失效缓存的 API 错误路径遗留 PETSc 向量读锁失败；
修复采用数值 PC 失败状态并让回调正常返回，PETSc 因而能完成输入锁清理。
成功刷新清除失败状态，测试门槛保持不变，修复后只重跑受影响三项。
首轮另四项旧 PC/自适应检查通过，本轮复用其证据，不重算为新执行。

首轮 FSI 恢复测试暴露驱动对变步终止时间的错误假设：
`.056` 的指定步长总和未达到 `steps*dt=.06`，应用正确补最后一步，恢复尾段
因此多一行。驱动修复把 nominal `dt*steps` 与步长之和对齐，加入终止时间和
历史时刻检查；没有修改生产方程或验收门槛。原始失败和物理输出保留，不把
该首轮报告为全部通过。

**最终物理证据：** 驱动 `ad08887` 推送后，`rcr_port_fsi` 完整通过，0 跳过，
包含 13 次求解与 43 个接受步。单出口包括直接解、无端口包装的 GAMG 基线、
split/GAMG/BoomerAMG 包装、自适应缓存以及跨基础 PC 的 checkpoint/restart；
双出口包括前五种组合。单出口 350 DoF，双出口 1020 DoF，后者的两个出口采用
相反外法向和不同阻抗。它们不是固定几何的替代用例：由网格和完整场重积的
单出口面积变化为 `−5.19735e−4`，双出口为 `+1.35499e−4/+7.10693e−5`。

独立审计未调用原验证器辅助函数，而是重新读出 VTU 点场、历史、面观测和日志。
完整点场含坐标、两域速度/位移、流体压力、网格速度及算法加速度；最大场差
`7.57780e−11`，端口/电容历史最大差 `2.15827e−12`，电路与压力功关系最大
缺陷 `1.69548e−13`，均低于原验收门槛。网格与 VTU 重积的出口面积、带符号
通量、终点体积分别与 CSV 相差至多 `5.55e−17/1.08e−19/2.22e−16`。
GAMG checkpoint 恢复到 BoomerAMG 后，终点场与不间断 BoomerAMG 解相差
`5.77105e−11`。

11 个开启诊断的求解记录了 96 个真实线性残差样本，其相对于
`max(1e−12,1e−9*||b||)` 的最大比例为 `0.0997252`，全部通过。
798 条 solver node 记录均有正 KSP reason 和零 PC failure reason。
43 步合计 114 次 Newton 迭代；两个直接解参考的 18 次未开启线性诊断，不能
把它们算成额外实测的真实线性残差样本。

实际速度叶确认为 `preonly/gamg` 或 `preonly/hypre`；端口统计满足每次重建
恰有 `k` 次列响应、每次 apply 一次端口批量规约。自适应单出口保持同一
`generation=1`，记录 12 次完整 Jacobian 装配、8 次 PC 刷新和 4 次复用；
shell 最终为 8 次重建、144 次应用。复用减少了 PC 更新，并没有停止 Newton
对完整 Jacobian 的更新。

代码入口、完整命令、门槛与失败根因见
[开发说明](../../docs/development/RCR_PORT_PRECONDITIONER.md)；原始记录与独立
审计见[本轮证据目录](../../docs/research/data/rcr-port-2026-11-26/)。归档包含
成功与失败尝试，逐文件记录长度和 SHA256；物理审计脚本只读这些输出，不启动
新的物理求解。

## 8. 适用范围、复杂度和限制

每次更新需要 `k` 次 bulk 响应和小系统分解；本地响应数据约为
`O(n_local k)`，Gram 工作约为 `O(n_local k²)`，稠密分解约为 `O(k³)`。
每次 apply 只做一次 bulk 响应，再增加 `O(n_local k+k²)` 的端口修正。
出口数大时更新和内存成本增加，必须与节省的外迭代比较。

算法需要可用的 bulk 近似和非奇异端口 Schur。它不能修复不适定的边界问题、
奇异的物理 Jacobian、错误的几何或不一致的单位。小 Schur 的失败不能通过
任意修改实际阻抗或放宽物理容差来隐藏。

相同两 rank、相同 GAMG 基础速度 PC 的本轮单样本，单出口外迭代为 `145→144`，
双出口为 `53→53`；两组 `solve_seconds` 字段累计分别为
`0.081757→0.076040` 秒和 `0.072828→0.068904` 秒，初始 Schur setup 计时字段
均增加。这里仅复述 PETSc 3.23.7 Release/hypre 2.32、共享单机、350/1020 DoF
日志的阶段计时，外层容差均为 `rtol=1e−11/atol=1e−13`。没有重复样本、
置信区间或跨网格基准，不能把这些很短的时间差解释为稳定加速。

多节点、百万自由度、GPU、任意密度/Reynolds 数或任意出口数量的通用加速
均未由本文建立。本地未执行 Debug、旧 PETSc 或全量验证；远程 CI 的补充
结果另随 PR 最终 head 记录。

## 9. 源码与参考

- 已核实的物理基线：
  [fsi.cpp at b731d471](https://github.com/saitoasukakawaii/EONSim-new/blob/b731d4713ab8428e02fb52af6547e1aa3097eca0/src/physics/fsi.cpp)，
  `outlet_jacobian_entries`。
- 实现入口：`include/eonsim/rcr_port_pc.hpp`、`src/algebra/rcr_port_pc.cpp`、
  `src/algebra/pc_plan.cpp` 和 `src/algebra/nonlinear_system.cpp`；当前分支
  `codex/rcr-port-schur`；当前生产源码
  [28e6d54](https://github.com/saitoasukakawaii/EONSim-new/commit/28e6d54701abced040752aff70b69d29b35f1d01)。
- [PETSc PCSHELL](https://petsc.org/release/manualpages/PC/PCSHELL/)：自定义 PC 接口。
- [PETSc KSPFGMRES](https://petsc.org/release/manualpages/KSP/KSPFGMRES/)：非线性/可变预条件作用。
- [PETSc PCGAMG](https://petsc.org/release/manualpages/PC/PCGAMG/)：多层与插值复用。
- [PETSc PCHYPRE](https://petsc.org/release/manualpages/PC/PCHYPRE/)：BoomerAMG 参数语义。

阅读练习：把一般公式中的 `V` 写为 `−Uᵀ+E`，推导忽略几何耦合 `E` 对端口
Schur 产生的差异；再思考为何两个端口几何支撑互不相交，交叉响应仍可能非零。
