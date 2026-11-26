# FSI 分块预条件器

## FSI-PC-04：联合速度多层与参考几何粗空间（2026-11-26）

本轮从已合并 #53 的 `main@858f021` 接续，分支 `codex/fsi-block-amg-robustness`。
实现和本地验收已完成；最终源码/驱动为 `88e6c335`，交付 [PR #54](https://github.com/saitoasukakawaii/EONSim-new/pull/54)。
所有实现/修复均先推送，再构建/验证；合并状态以该 PR 为准。
本节以下的 #49/#50 记录是其各自源码的历史证据。

```text
-pc_recipe hybrid -pc_plan_schur_approx nodal
-pc_plan_velocity_solver gamg
-pc_plan_velocity_coarse_space constants
```

`-pc_plan_velocity_solver gamg` 在完整流固速度块上构造 PETSc 聚合 GAMG，保留流固
非对角项；适用于完整 FSI 的 hybrid/quantity 树。默认 PREONLY 应用一个 V-cycle，
平滑器 ASM/ILU，粗解 GMRES/Jacobi。显式 FGMRES 保留有界内迭代；外层必须为 FGMRES。
不存在统一 xyz 编号的缩减矩阵继续使用 scalar AIJ，不将 blocksize 强行设为 3。

`-pc_plan_velocity_coarse_space constants|rigid` 只作用于 twolevel/gamg，省略时为 constants。
twolevel constants 保留原来的 rank/domain/component 分片常数；rigid 为固体顶点组增加
参考坐标旋转候选，流体常数和单轴刚体标量保持。GAMG 只接受 constants，采用所有活动
标量行上的一个归一化常数向量（包括 body），不按 MPI rank 或物理分量复制近模态。
`gamg + rigid` 在建立层级前明确拒绝。PETSc 3.23.7 的 scalar-AIJ 聚合为每个 aggregate
固定生成 nvec 个粗列，小型非单点或仅覆盖部分物理分量的 aggregate 可能使多向量
局部 QR 秩亏；全局正交不能消除该问题。
本轮未实现 packed-vector 辅助空间，不把 scalar GAMG 描述为弹性旋转 AMG。

每行按 `DofKey` 的物理分量评价旋转 `omega cross (X-Xc)`，不假设连续三个行号属于同一节点。
精确恒等行在所有候选模态中为零；缺失分量、共线点及空 owned rank 允许存在，依赖/零模态
经两次正交化后剔除。非 P1 顶点的几何模态明确拒绝。参考位置与 owned 独立代表一一对应，
接口 alias 不创建第二个位置，body/端口占位坐标不被当成顶点。旧镜像弹性算例使用与固体核
一致的物理参考域变换。这里只提供 near-nullspace，不对完整动态 FSI 矩阵声明精确零空间。

GAMG 默认复用插值，但每次矩阵变化仍刷新 Galerkin 数值和平滑器；与沿用旧 Jacobian 不同。
可通过各速度 KSP 前缀的 `pc_gamg_reuse_interpolation false` 强制重建，以应对系数显著变化。
同一 SNES 会话的拓扑、语义、参考位置和约束集合必须固定；现有配置/约束失效机制共同重建。
全恒等矩阵直接使用精确 Jacobi，不构造空 AMG。配置报告记录实际模态数与层级。

验证入口沿用 `pc_plan_mpi1/2/4`、`fsi_block_efficiency`、`fsi_tube_rcr`，并通过
`verify_time_retry.py --recipe hybrid --velocity-solver gamg` 或
`verify_time_retry.py --recipe hybrid --velocity-solver twolevel --velocity-coarse-space rigid`
检查实际回滚/重启。
鲁棒性实验必须记录实际密度、时间步、源/输入摘要、正收敛理由和独立真实残量；所有比较使用
相同物理配置的直接解。密度比变化不自动等同于精确附加质量数，高 Re/多节点/生产规模
仍须单独证据。算法开关保持可选。

本地 a7e0 的代数 3/3、物理 4/4、两种实际缩步/重启均通过；88e6 的生产差异仅为报错前
刷新，受影响 COO 1/1 通过，其余复用本轮此前通过证据，未重复运行。默认插值复用的数值
更新已验证；强制 `reuse_interpolation=false` 未单独执行实验。
最终 88e6 动脉 **78/78 runs、656 步、1,282 次修正** 独立重放通过，包含 8 条 32 步轨迹及
30 次密度比/时间步对照。最大真实残量/门槛 `0.6010255`、最大五场差 `2.6171e-9 < 2e-6`。
细网格 rigid 的完整轨迹外迭代 `5445→5050`，四步 wall 配对中位变化 `−10.79%`
但范围跨零；粗网格无时间收益，GAMG 两档小网格亦无速度优势，不切换默认。
[完整命令、来源、失败与证据](../research/data/fsi-block-multilevel-2026-11-26/README.md)。

固定版本依据：[PETSc v3.23.7 agg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/agg.c)
和 [gamg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/gamg.c)。

## 历史交付：FSI-PC-03

**当前状态：本轮实现、默认路径本地验收与独立证据重放均已完成。**
本轮基线为 `296246e53d895f29ea3d0f7e5c960dc26b1426dc`，工作分支为
`codex/fsi-block-efficient-schur`，见 [PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50)。
`664a623` 的独立代数、RCR 与恢复检查通过；驱动 `66b0a62` 配合同一生产二进制
完成 72 次动脉运行，含 12 条完整 32 步轨迹。结构 nodal 没有显示可靠效率收益，
保留为显式可选项。完整比较支持把 added_mass 流体响应和 twolevel 联合速度响应
改成单次 PC 应用。最终源码 `c4fb266` 已先推送、后重新编译并通过 clean Release
9/9 定向回归，覆盖默认路径与用户覆盖。来源、CI 与重放见
[本轮验证索引](../research/data/fsi-block-efficiency-2026-11-25/README.md)。

上一轮求解器实现检查点为
`b8ac03ab162715fca24009f18903da8116ef4ecc`；其 PETSc 3.23.7 Release 代数检查
为 3/3，覆盖 1/2/4 rank。最终验收提交
`b52281d7585ead08e545f29f8d83eca9177e7eac` 的八项物理/恢复选测全部通过，
动脉 60 次运行全部通过。验证器加固提交
`ff81e5bb1a8e02a3f484d855ea074461b716ff66` 的 23 项正负对照均通过。
后两个提交未改变上述求解器实现，仅加固测试精度、执行预算和证据完整性。

源码提交 `b52281d` 的四项必需 CI 检查也已通过：53 项数值选测与 58 项 Python
检查通过，网站构建和草稿隔离检查通过。固定源码、运行编号及各检查状态见
[源码 CI 收据](../research/data/fsi-block-2026-11-25/ci-source-b522.json)；
该收据对应上述源码提交，不预先代表后续文档提交的检查状态。

上一轮工作分支为 `codex/fsi-block-completion`，基线为
`f50a4a4338689c9a065bee30ae4a7f3f52c5002e`，PR #49 已合并。
本轮按用户授权遵循“源码先推送、再验证、通过必需 CI 后合并”。
上一轮实际命令、环境、历史失败和最终收据见
[验证索引](../research/data/fsi-block-2026-11-25/README.md)及
[原始证据归档](../research/data/fsi-block-2026-11-25/evidence.tar.xz)。
下文 `build/...` 为原始证据来源路径，其归档映射由该索引记录；开发过程另见
[会话日志](CODEX_SESSION_LOG.md)。

本实现服务现有共形、约束消元后的单体刚体/弹性 FSI。选择预条件器不改变完整
Jacobian、物理残量、时间离散、约束或接受步条件。压力规范及边界条件仍由算例决定。

## 1. 选择与适用范围

| 选项 | 实际行为 | 约束 |
|---|---|---|
| `-pc_recipe physics` | fluid 内 velocity/pressure Schur；外层 fluid、solid、mesh 乘法分裂 | 独立流体或完整 FSI |
| `-pc_recipe quantity` | velocity、原始 pressure、mesh 乘法分裂 | 原始压力默认 Jacobi；没有压力 Schur |
| `-pc_recipe hybrid` | dynamics 内 velocity/pressure Schur；外层 dynamics、mesh 乘法分裂 | 独立流体或完整 FSI |
| `-pc_recipe added_mass` | dynamics 内完整 fluid/structure Schur；fluid 内 velocity/pressure Schur；外层 dynamics、mesh 乘法分裂 | 仅完整 FSI；完整 fluid 子块须可解 |
| `-pc_plan_velocity_solver split` | hybrid/quantity 的速度块分 fluid_interior、structure | 默认值 |
| `-pc_plan_velocity_solver coupled` | 完整流固速度矩阵上 GMRES/ASM/ILU | 仅完整 FSI 的 hybrid/quantity |
| `-pc_plan_velocity_solver twolevel` | 完整流固速度矩阵上 PREONLY 应用一次 PCMG V-cycle，含 ASM 平滑和全局粗校正 | 仅完整 FSI 的 hybrid/quantity；可显式选择 FGMRES |
| `-pc_plan_velocity_solver gamg` | 完整流固速度 scalar AIJ 上 PREONLY 应用一次 PETSc GAMG V-cycle | 仅完整 FSI 的 hybrid/quantity；仅 constants 近模态；当前小网格无速度优势 |
| `-pc_plan_velocity_coarse_space rigid` | twolevel 为固体 P1 语义行增加参考坐标旋转，剔除约束/零/依赖模态 | 仅 twolevel；默认 constants 保留；gamg+rigid 明确拒绝 |
| `-pc_plan_schur_approx diagonal` | PETSc SELFP 压力近似 | 默认值 |
| `-pc_plan_schur_approx nodal` | 语义节点块逆构造压力近似 `D−CHB` | 要求存在压力 Schur；不作用于 fluid/structure Schur |
| `-pc_plan_structure_approx a11` | 结构 Schur 的 P 取结构块 `K` | `added_mass` 的默认值 |
| `-pc_plan_structure_approx nodal` | 局部完整流体块逆构造结构近似 `K−G H_F E`，默认 PREONLY 应用 P 的预条件器 | 仅 `added_mass`；局部流体块须可逆；实验选项，尚无效率优势证据 |

独立流体的 physics/quantity/hybrid 均退化为 velocity/pressure Schur。
added_mass 与 twolevel 是不同的流固分组方式，不能同时选择。
前者消去完整流体响应，后者在联合速度块内部增加粗校正。
这些语义入口与旧 `-block_pc`、`-schur_pc` 互斥。

## 2. 压力 Schur 与数值更新

对速度/压力块

\[
J_{vp}=\begin{bmatrix}A&B\\C&D\end{bmatrix},\qquad
S_p=D-CA^{-1}B,
\]

nodal 用每个语义节点实际保留的 1–3 个速度分量的小块逆 \(H\)，形成
\(\widetilde S_p=D-CHB\)。分组区分实体、域、空间与模式，不假设 xyz 连续。
完整 \(D\) 保留离散稳定化以及属于压力块的 RCR 端口项。

nodal USER 矩阵在每次成功且施加约束后的 Jacobian 装配后更新。
句柄和乘积符号结构复用；同一个语义子树的 main/inner/upper 实例共享该矩阵，
每次装配只刷新一次。奇异、非有限或不完整节点块共同报错。
这项近似不是 PCD 或 LSC。

## 3. 完整流体响应与 added_mass

固定本次网格块近似，令 \(s\) 表示独立结构速度，

\[
J_d=\begin{bmatrix}F&E\\G&K\end{bmatrix},\qquad
F=\begin{bmatrix}A_{ff}&B_f\\C_f&D_f\end{bmatrix},\qquad
S_s=K-GF^{-1}E.
\]

added_mass 的 PETSc `MatSchurComplement` 保留完整流体 velocity/pressure 块及
两向交叉块，包括压力反馈。它不同于仅消去流体速度的
\(K-G_vA_{ff}^{-1}E_v\)。默认结构 Schur 预条件矩阵取已装配的 \(K\)，
默认 FGMRES（rtol \(10^{-2}\)、最多 20 次）配 GAMG；单自由度结构用 Jacobi。
流体响应默认 PREONLY，应用一次内部速度/压力 Schur 预条件器。
记实际流体响应为 \(\mathcal B_F\)，结构算子的实际应用是

\[
\widetilde{\mathcal S}_s(v)=Kv-G\mathcal B_F(Ev).
\]

默认类型改变会改变这个近似作用，不能说它仍应用精确 \(F^{-1}\)。
完整根 Jacobian 与物理残量保持不变。保留备用 rtol \(10^{-4}\)、max_it 20；
显式设置 `-fieldsplit_dynamics_fieldsplit_fluid_ksp_type fgmres` 可恢复原迭代预算。
只设置 rtol 或 max_it 不会使 PREONLY 开始迭代。独立 inner/upper 需要各自的类型选项。

公式中的精确逆是数学定义。实际内层求解有限精度、有限工作量；
相对容差停止的 Krylov 响应通常不是固定线性映射。外层 FGMRES 接受变化的
预条件作用，但不能把 Schur 内部的近似矩阵乘法自动变成精确乘法。
应控制内层误差，并检查完整原始 Jacobian 的真实残量和原非线性接受条件。
内层达到工作上限可作为有界近似；PC 因子失败、非有限值及其它实质失败必须传播。
用户开启 `ksp_error_if_not_converged` 会更严格地拒绝内层上限。

默认 PC 从已装配的预条件矩阵 P 构建；KSP 的 A 保留上述隐式 Schur 对象。
这样也防止 GAMG 创建时的 `useAmat` 标志在用户切换 PC 类型后误导局部矩阵提取。
如果 P 数值上严格对角、对角项有限且非零，则默认用 Jacobi 精确应用其逆，
不构造不必要的层级；显式用户 PC 选项仍最后生效。

完整系统可解不保证 \(F\) 单独可解。流体子块存在未处理的压力零空间时，
须修正算例规范/边界或选择其它 recipe；程序不自动添加压力钉点。
外层 ALE 仍为乘法分裂，未构造包含 ALE 消元的全系统精确 Schur。

### 3.1 可选的结构 nodal 近似

`-pc_plan_structure_approx nodal` 用同一流体实体实际保留的速度与压力
分量组成 1–4 维局部块 \(F_i\)。实体种类、ID、域、空间与模式参与分组；
压力独有节点及 RCR 边界压力保留为独立小块，不按代数行相邻关系分组。
构造

\[
H_F=\operatorname{blockdiag}(F_i^{-1}),\qquad
P_s=K-GH_FE.
\]

这近似包含局部速度—压力耦合及两向流固交叉项。\(E\) 与 \(G\) 分别从
原 Jacobian 提取，不假设互为转置。先按行、列平衡局部矩阵，再作选主元消元，
恢复原单位的逆；压力与动量数量级不同不应被直接当作局部奇异性。
真实奇异、非有限或不完整块仍共同拒绝，不添加压力钉点或任意对角正则项。

结构 KSP 的 A 保留上述隐式 Schur 对象，其实际响应取决于流体子 KSP；USER P 使用上式。
新模式默认 PREONLY，应用一次由 \(P_s\) 构建的 GAMG/Jacobi 预条件器，
避免默认结构 FGMRES 反复触发完整流体 Schur 乘法。
用户仍可显式选择结构 FGMRES；该选择会重新引入隐式 Schur 作用的成本。
生产代码仍要求外层求解成功、有限的重算物理残量及原逐字段接受条件。
`-linear_report` 只报告 \(J\Delta x-b\)；本轮验证脚本另行强制真实线性残量门槛，
该诊断本身不是新增的运行时接受门槛。

压力 Schur 与结构 Schur 的两个 nodal 选项独立；例如：

```text
-pc_recipe added_mass
-pc_plan_schur_approx nodal
-pc_plan_structure_approx nodal
-fieldsplit_dynamics_pc_fieldsplit_schur_fact_type lower
```

局部逆没有保留跨节点的完整流体传播，不能据此宣称获得精确附加质量或
网格无关收敛。RCR 单自由度可能通过 \(GH_FE\) 引入端口范围的填充。
和压力 nodal 一样，固定图下复用符号乘积与 USER P 句柄，每次约束后
Jacobian 装配只刷新一次。该选项的数值正确性和实际效率须分别验证。

## 4. 两层联合速度校正

twolevel 的默认 `constants` 对完整流固速度矩阵 \(A_v\) 构造稀疏插值 \(P\)：
每个 rank 内，对每个实际存在的
`(domain, kind, component, mode, space)` 分组建立一个单位 Euclidean 范数的
分片常数列。初始化时数值为精确恒等行的行不进入粗空间，插值为零。

\[
A_c=P^\mathsf T A_vP,\qquad
r_c=P^\mathsf T(r-A_vz),\qquad z\leftarrow z+PA_c^{-1}r_c.
\]

PCMG V-cycle 在粗校正前后用 ASM 平滑；细层和 Galerkin 粗层均看到流固非对角项。
该常数配置的每个有效细行只有一个插值非零元；各粗自由度由贡献细行所在 rank 拥有，
允许本地没有速度行或粗列。当前 P1 两域最多约 \(6p\) 个粗自由度，
\(p\) 为 MPI rank 数；其它实体种类、空间和模式会增加列数。

| 层 | 默认配置 |
|---|---|
| 联合速度 | PREONLY，一次 PCMG V-cycle；备用 rtol `1e-4`、max_it `20` 供显式 FGMRES 使用 |
| 细平滑器 | Richardson，1 次；ASM overlap `1` |
| ASM 局部解 | PREONLY、ILU(1)、RCM |
| 粗解 | GMRES/Jacobi，rtol `1e-10`，max_it `200`，unpreconditioned norm |
| 全恒等块 | 明确退化为一层 PREONLY/Jacobi，不构造空粗矩阵 |

粗 GMRES 可随右端改变工作量，因此一次 V-cycle 也不保证是固定线性逆；最外层要求 FGMRES。
若用户显式启用联合速度迭代，只允许 FGMRES。hybrid 的恢复入口是
`-fieldsplit_dynamics_fieldsplit_velocity_ksp_type fgmres`，quantity 则用
`-fieldsplit_velocity_ksp_type fgmres`；独立 Schur inner/upper 使用各自前缀。
PREONLY 的 `CONVERGED_ITS` 表示一次 PC 应用完成，不代表达到了备用 rtol。
不允许用 `pc_type`、`pc_mg_levels`、`pc_mg_galerkin` 等选项改变固定拓扑。
局部因子、overlap、内外容差及粗解仍可调节。
`-pc_plan_report` 的 `pc_twolevel` 行报告实际粗维数和层数。

PCMG 随矩阵数值变化重新计算 \(P^\mathsf TA_vP\)，固定图时复用符号结构。
同一个配置周期内，分区、语义、图及约束集合必须保持不变；结构变化需重建求解器。
可选 `rigid` 在固体 P1 分组增加参考旋转并正交/截断，行可有多个插值非零元；其粗维数
不能再按上述常数配置估算。可选 `gamg` 是另一条完整速度多层路径，见本文首节。
本轮没有谱粗空间或 packed-vector 弹性 AMG，不承诺网格无关迭代或大规模加速。

## 5. 独立 Schur inner/upper

| A00 角色 | hybrid 压力 Schur 的常见 prefix |
|---|---|
| 因子主速度解 | `fieldsplit_dynamics_fieldsplit_velocity_` |
| Schur 算子内部速度解 | `fieldsplit_dynamics_fieldsplit_pressure_inner_` |
| FULL 因子的回代速度解 | `fieldsplit_dynamics_fieldsplit_pressure_upper_` |

没有独立选项时可复用 KSP；设置对应前缀后，对每个不同实例应用相同语义子树和
各自选项。别名只配置一次。独立 upper 仅适用于 FULL；
LOWER、UPPER、DIAG 与独立 `_upper_` 选项组合会提前报错。

added_mass 对应 `fieldsplit_dynamics_fieldsplit_structure_inner_` 和
`...structure_upper_`，其 A00 是完整 fluid 子树，子前缀继续递归。
以 `-pc_plan_report` 的实际 prefix 为准。
`PCFieldSplitGetSubKSP` 在 Schur 模式不能单独用于识别全部三个角色。

## 6. 验证结果、失败历史与性能

### 6.1 证据清单

以下均为单机进程验证，不能解释为多节点扩展结果。

| 提交与检查 | 实际结果 | 证据范围 |
|---|---|---|
| `b8ac03a`：`pc_plan_mpi1/2/4` | 3/3 通过 | 独立完整流体 Schur、插值/Galerkin oracle、数值刷新、缺失分量、恒等退化、空 owned rank、Schur 角色及失败/错误配置 |
| `b8ac03a`：`fsi_tube_rcr`、`pc_twolevel_retry`、`pc_recipe_restart`、`pc_recipe_hybrid`、`schur_verification` | 5 项通过 | 对应物理场、RCR 历史、同分区续算和已执行回滚检查；具体 ranks 以每项日志为准 |
| `b8ac03a`：`fsi_tube` | 未通过 | 细动脉网格 added_mass 在 130 s 执行预算内完成 10/32 步，随后超时；不能以已完成步代替完整轨迹验收 |
| `b8ac03a`：`pc_added_mass_retry` | 未通过 | 两次 Newton 预算下后续网格字段精度不足，触发缩步并耗尽重试 |
| `ff81e5b`：验证器正负对照 | 23/23 通过 | 12 个正常输入接受、11 个损坏输入拒绝；仅复核比较/审计函数，没有新求解 |
| `b52281d`：最终选测 | 8/8 通过 | 六种模式的完整 32 步动脉轨迹、重复计时、RCR、收紧外层精度后的 retry、原恢复行为 |

原始证据位置为 `build/validation-history/algebra-b8ac03a/summary.json`、
`build/validation-history/physical-b8ac03a/evidence/summary.json` 和
`build/diagnostics/validation-guards/summary.json`。验证器对照使用提交中的函数或
断言，检查缺数组、截短数据、后续数组中的 NaN、缺线性报告、无穷 RHS、负范数等，
保留原始成功输出；这些对照不能计作额外的 MPI 求解通过。

历史代数选测的实际 CTest 选择式为：

```bash
ctest --test-dir build/cloud-3.23.7-release -j 1 -V \
  -R '^(pc_plan_mpi1|pc_plan_mpi2|pc_plan_mpi4)$'
```

首轮物理选测的选择式为：

```bash
ctest --test-dir build/cloud-3.23.7-release -j 1 -V \
  -R '^(fsi_tube|fsi_tube_rcr|pc_added_mass_retry|pc_recipe_hybrid|pc_recipe_restart|pc_twolevel_retry|schur_verification)$'
```

最终八项选测为 `fsi_tube`、`fsi_tube_rcr`、`pc_recipe_retry`、
`pc_added_mass_retry`、`pc_twolevel_retry`、`pc_recipe_hybrid`、`schur_verification`
和 `time_retry_verification`，全部通过；本地完成时间为 2026-11-25 11:58 UTC。
`pc_recipe_restart` 的通过来自上面的历史批次，没有列为本次重跑。
当前收据为 `build/cloud-3.23.7-release/evidence/summary.json`。最终选择式为：

```bash
ctest --test-dir build/cloud-3.23.7-release -j 1 -V \
  -R '^(fsi_tube|fsi_tube_rcr|pc_recipe_retry|pc_added_mass_retry|pc_twolevel_retry|pc_recipe_hybrid|schur_verification|time_retry_verification)$'
```

收据中的完整命令还包含 JUnit、CTest dashboard 输出及锁定依赖环境。
测试入口见 [verify_pc_plan.cpp](../../tests/verify_pc_plan.cpp)、
[verify_schur.py](../../tests/verify_schur.py)、
[verify_fsi_tube.py](../../tests/verify_fsi_tube.py) 和
[verify_time_retry.py](../../tests/verify_time_retry.py)。

### 6.2 完整轨迹与精度结果

动脉回归比较 direct、physics_lower、coupled_diagonal、coupled_nodal、
twolevel_nodal、added_mass 六种模式。两套网格分别为 1027 DoF / 1 rank 和
3024 DoF / 2 rank，每种模式仍要求完整 32 步。每次 Newton 修正独立重算完整
Jacobian 的真实残量，目标为 `max(1e-23, 1e-10*rhs_norm)`，比较舍入余量为
`1.00001`；流体速度、压力、网格位移、壁速度和壁位移的同网格直接解相对峰值差
上限仍为 `2e-6`。日志缺失、NaN 或无穷值不构成通过。

最终 60 次运行全部通过：12 条完整轨迹合计 384 个接受步、768 次 Newton 线性
修正，**768/768 均满足真实残量目标**。最大“实测残量/目标”比为
`0.5600385064`；全部动脉比较中的最大字段相对峰值差为 `1.0712628633e-11`。
完整 added_mass 的粗/细网格墙钟分别为 `59.382126` / `408.075013` s；
它通过了精度验收，但在本组小网格中没有速度优势。原始逐修正与逐场数据在
`build/cloud-3.23.7-release/fsi_tube/arterial-block/results.json`。

`b52281d` 将完整 added_mass 单次执行预算明确设为 600 s，`fsi_tube` 总预算为
1200 s；其它动脉单次运行仍为 130 s。改变的是容许执行的时间，不是求解容差、
非线性接受条件、步数或字段门槛。通过完整轨迹的每种模式继续做一次预热和
三次交错的四步计时，记录中位数；CI 没有“必须加速”的条件。

retry 验证只把外层线性精度收紧为 `-ksp_rtol 1e-11 -ksp_atol 1e-15`，
两次 Newton 预算和原物理接受条件保持不变。已执行的单 rank 诊断由失败改为
完成 32 个接受步至 `t=0.04`，与已有直接解的 Float64 最大绝对差分别为
流体 `6.04e-14`、固体 `2.62e-15`；该诊断见
`build/diagnostics/retry-b8ac03a/summary.json`。最终 `pc_added_mass_retry` 和
`pc_twolevel_retry` 的 1/2 rank 回归均已通过，保留直接解对照、同分区续算及
强制失败后历史不提交的检查。
失败路径没有输出最终非线性字段残量，诊断中测得的线性字段残量不能冒充该量。

RCR 新模式覆盖 generalized-alpha、2 rank、两个时间步及同分区重启。
added_mass / twolevel 相对直接解的最大字段**绝对**差分别为
`5.8240910428e-9` / `1.8453738537e-11`，均小于该测试的 `2e-8` 门槛；
两者重启差均为零。各模式的 full/start/resumed 真残量检查数为 `4/2/2`。
来源为 `build/cloud-3.23.7-release/fsi_tube_rcr/metrics.json`。这些绝对差与
前面的动脉相对峰值差是不同指标；已有 BE/BDF2 RCR 回归使用直接解，不能把它们
计作新增两种预条件器在这些时间格式下的 RCR 验证。


### 6.3 已拒绝的调参尝试

以下均针对同一个 3024 DoF、2 rank 动脉输入，在同一已推送的 `b8ac03a`
Release 二进制上保留严格残量/字段条件。环境为单机 Linux、PETSc 3.23.7，
MPI 按核映射并绑核，OMP/OpenBLAS/MKL 各 1 线程。表中仅为首个接受步的
顶层累计迭代和 rank 最大线性区间时间，**不是完整轨迹计时中位数或扩展性结论**。
该线性区间包含 PC setup 与全部嵌套求解，不能拆成未测量的子层成本。

| 配置 | 首步外层迭代 | 首步线性时间 / s | 本次执行结局 |
|---|---:|---:|---|
| 保留流体/结构 FGMRES 20/20 与 GAMG | 92 | 13.6533 | 原完整轨迹在 130 s 时完成 10 步后超时 |
| 结构上限改为 4 | 489 | 17.8489 | 四步诊断在 80 s 时仅完成 3 步 |
| 结构上限改为 2 | 1152 | 23.3240 | 四步诊断在 80 s 时仅完成 3 步 |
| 结构与流体速度均改 ASM overlap 1 / ILU(1) / RCM | 491 | 49.6610 | 四步诊断在 80 s 时仅完成 1 步 |
| 结构、流体速度、压力的 GAMG 粗解改 PREONLY/LU/MUMPS | 92 | 29.3489 | 四步诊断在 80 s 时仅完成 2 步 |

该轮因此保留 20/20 GAMG 配置；上表候选均未采用。后续单次流体响应比较见 6.6。
粗 LU 仅改变预条件器的粗逆，仍保留完整 Schur；其数学可用性不能替代速度证据。
完整命令和日志摘要分别保留于
`build/diagnostics/arterial-budget-b8ac03a/results.json`、
`build/diagnostics/arterial-asm-b8ac03a/results.json`、
`build/diagnostics/arterial-coarse-lu-b8ac03a/results.json`。

### 6.4 最终三样本计时

以下来自 `b52281d` 最终动脉结果。每种配置先完成完整轨迹及一次预热，再执行
三次交错的四步运行；表内三个统计量分别取三样本中位数。墙钟由启动进程前至
进程退出测量，包含相同的诊断和输出；线性区间仍包含内部求解和 PC setup。
每次四步运行包含八次 Newton 修正。两套网格及 rank 数一起变化，不能将该表
解读为强扩展曲线。完整环境与每条命令见证据归档。

| 网格 / MPI rank | 模式 | 外层迭代中位数 | 线性时间中位数 / s | 墙钟中位数 / s |
|---|---|---:|---:|---:|
| 1027 DoF / 1 | `direct` | 8 | 0.059785 | 0.415753 |
| 1027 DoF / 1 | `physics_lower` | 386 | 0.384190 | 0.766624 |
| 1027 DoF / 1 | `coupled_diagonal` | 334 | 0.177158 | 0.565688 |
| 1027 DoF / 1 | `coupled_nodal` | 331 | 0.159509 | 0.565938 |
| 1027 DoF / 1 | `twolevel_nodal` | 288 | 0.588150 | 0.967359 |
| 1027 DoF / 1 | `added_mass` | 179 | 6.839241 | 7.239584 |
| 3024 DoF / 2 | `direct` | 8 | 0.303184 | 0.767447 |
| 3024 DoF / 2 | `physics_lower` | 766 | 3.015633 | 3.627327 |
| 3024 DoF / 2 | `coupled_diagonal` | 646 | 1.032484 | 1.619708 |
| 3024 DoF / 2 | `coupled_nodal` | 645 | 0.928008 | 1.521485 |
| 3024 DoF / 2 | `twolevel_nodal` | 563 | 3.795757 | 4.378000 |
| 3024 DoF / 2 | `added_mass` | 354 | 45.805123 | 46.404431 |

两层和 added_mass 均减少了外层迭代，但其每次预条件作用更昂贵；本组数据
不支持把它们当作普遍更快的默认值。所有候选保留同一严格精度检查，CI 不设
加速门槛。最终完整轨迹和三样本数据均保留，不能仅选择较少迭代的一列作为结论。

### 6.5 使用入口

以下仅为配置示例，实际验收使用上面的脚本和其固定输入：

```bash
build/cloud-3.23.7-release/eonsim -case cases/fsi/elastic.yaml \
  -prepare results/fsi-block-p2 -parts 2
mpiexec -n 2 build/cloud-3.23.7-release/eonsim \
  -case cases/fsi/elastic.yaml -partition results/fsi-block-p2 \
  -pc_recipe hybrid -pc_plan_velocity_solver twolevel \
  -pc_plan_schur_approx nodal -pc_plan_report -linear_report
mpiexec -n 2 build/cloud-3.23.7-release/eonsim \
  -case cases/fsi/elastic.yaml -partition results/fsi-block-p2 \
  -pc_recipe added_mass -pc_plan_schur_approx nodal \
  -pc_plan_report -linear_report
```

`-linear_report` 仅报告诊断，不改变接受准则。FSI-PC-04 已补完整速度块 scalar GAMG、
twolevel 参考旋转及有限密度比/步长对照；完整单体多场 AMG、多节点规模、跨分区重启
和任意高 Reynolds 数的生产验证仍不在这些证据范围内。

### 6.6 本轮单次响应比较

生产二进制来自先推送的 `664a623`，固定旧/新选项的比较驱动来自先推送的
`66b0a62`；后者未改变生产 C++。两套网格共 12 次四步筛选、12 条完整 32 步轨迹、
12 次预热和 36 次交替计时，72/72 运行通过。每次计时均为独立进程的四步轨迹。
所有候选保留 `max(1e-23, 1e-10*rhs_norm)` 的真实线性残量目标与 `2e-6`
的五场相对峰值差门槛，未放宽精度来获得速度。最大真实残量/目标比为
`0.5547250921`，最大五场相对峰值差为 `3.1382e-11`。

下表为三次交替样本的独立中位数。单机 INTEL XEON PLATINUM 8573C，
PETSc 3.23.7 Release、Open MPI 5.0.8，MPI 按核绑定，OMP/OpenBLAS/MKL 各 1 线程。
线性区间包含 PC setup 和嵌套求解；墙钟包含启动、同样的诊断与输出。

| DoF / rank | 明确固定的配置 | 外层迭代 | 线性时间 / s | 墙钟 / s |
|---|---|---:|---:|---:|
| 1027 / 1 | added_mass，流体 FGMRES20 | 179 | 6.482707 | 6.885585 |
| 1027 / 1 | added_mass，流体 PREONLY | 332 | 0.974291 | 1.368866 |
| 1027 / 1 | twolevel，速度 FGMRES20 | 288 | 0.614463 | 1.017857 |
| 1027 / 1 | twolevel，速度 PREONLY | 380 | 0.119125 | 0.515940 |
| 3024 / 2 | added_mass，流体 FGMRES20 | 354 | 44.477524 | 45.057488 |
| 3024 / 2 | added_mass，流体 PREONLY | 661 | 6.506006 | 7.148527 |
| 3024 / 2 | twolevel，速度 FGMRES20 | 563 | 3.931200 | 4.585011 |
| 3024 / 2 | twolevel，速度 PREONLY | 682 | 0.609956 | 1.237586 |

在这些样本上，added_mass 的线性时间约降至原来的 1/6.65 和 1/6.84，
twolevel 约降至 1/5.16 和 1/6.45，外层次数均增加。
细网格直接法、coupled_nodal 的线性中位数分别为 `0.257188`、`1.014540` s；
本次改进不意味着 added_mass 优于这两个基线，直接法在两套小网格上仍最快。
网格大小与 rank 数同时变化，这不是强扩展实验。

结构 nodal 的首轮独立四步样本没有产生可靠收益：细网格结构 PREONLY 的
nodal / a11 分别为 `65.788333` / `68.456574` s，而原 a11 结构 FGMRES 为
`49.117077` s。该选项保留作实验，未提升为默认值。验证器初版还漏过一次早期
KSP 类型损坏；`66b0a62` 改为逐次、逐 rank 检查后，25 项正负对照全部符合预期。
历史失败保留，不能把初版写成全部通过。

### 6.7 最终默认源码与独立重放

`c4fb266edec94afbf610cb1379dd1595ed96ae40` 的两处 KSP 默认类型更改在推送后重新编译。
本地 PETSc 3.23.7 Release 的 `pc_plan_mpi1/2/4`、`fsi_tube_rcr`、
`pc_added_mass_retry`、`pc_added_mass_nodal_retry`、`pc_twolevel_retry`、
`pc_recipe_restart`、`pc_recipe_hybrid` **9/9 通过**，收据 `dirty=false`。
精确结构 Schur oracle 显式恢复迭代流体响应；新默认则用非零 RHS 核对一次
`KSPSolve` 与一次 `PCApply` 等价。独立 main/inner/upper 的 prefix、类型和预算
分别核对。刚体、弹性双域及 Neo-Hookean 的新增两 rank 变体也核对实际默认类型，
所有字段误差和物理/恢复门槛保持原值。

同一推送的独立重放检查 2,635 份归档文件、72 份运行日志、1,248 次线性修正、
2,028 份必要求解器观测、468 份体 VTU 及 156 个保存状态的 780 项字段比较，全部通过。
其中 130 项是直接参考自身对照，650 项是其他模式；原初筛和失败控制仅做哈希核验。
重放不执行求解器，亦不把有限的原墙钟及其重算中位数当作新的计时。
[本地源码收据](../research/data/fsi-block-efficiency-2026-11-25/default-summary.json) ·
[重放结果](../research/data/fsi-block-efficiency-2026-11-25/replay-result.json)。

## 7. 源码与官方依据

- [语义树](../../src/algebra/pc_plan.cpp)：`make_pc_plan`、`configure_pc_plan`。
- [Schur 角色](../../src/algebra/schur_solver.cpp)：`configure_schur_subsolvers`。
- [粗校正](../../src/algebra/coupled_velocity_pc.cpp)：`configure_coupled_velocity_twolevel`。
- PETSc **v3.23.7**：
  [fieldsplit.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c)、
  [schurm.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/utils/schurm/schurm.c)、
  [mg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mg.c)、
  [mgfunc.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mgfunc.c)。
