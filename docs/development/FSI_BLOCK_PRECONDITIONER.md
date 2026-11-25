# FSI 分块预条件器

**当前状态：本轮实现待验证。** 本文对应 `codex/fsi-block-completion`，
基线 `f50a4a4338689c9a065bee30ae4a7f3f52c5002e`，新增源码已推送为
`d9f58572e67ffa3636460e21d6d864ea560c8329`。本轮数值验收尚未完成，
不能引用本文作为测试通过或性能提升的证据。源码提交、实际命令和结果最终登记在
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
| `-pc_plan_velocity_solver twolevel` | 完整流固速度矩阵上 FGMRES、两层 PCMG、ASM 平滑和全局粗校正 | 仅完整 FSI 的 hybrid/quantity |
| `-pc_plan_schur_approx diagonal` | PETSc SELFP 压力近似 | 默认值 |
| `-pc_plan_schur_approx nodal` | 语义节点块逆构造压力近似 `D−CHB` | 要求存在压力 Schur；不作用于 fluid/structure Schur |

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

added_mass 用 PETSc `MatSchurComplement` 应用完整流体 velocity/pressure 响应，
包括压力反馈。它不同于仅消去流体速度的
\(K-G_vA_{ff}^{-1}E_v\)。结构 Schur 预条件矩阵取已装配的 \(K\)，
默认 FGMRES（rtol \(10^{-2}\)、最多 20 次）配 GAMG；单自由度结构用 Jacobi。
流体响应默认 FGMRES（rtol \(10^{-4}\)、最多 20 次）配其内部速度/压力 Schur。

公式中的精确逆是数学定义。实际内层求解有限精度、有限工作量；
相对容差停止的 Krylov 响应通常不是固定线性映射。外层 FGMRES 接受变化的
预条件作用，但不能把 Schur 内部的近似矩阵乘法自动变成精确乘法。
应控制内层误差，并检查完整原始 Jacobian 的真实残量和原非线性接受条件。
内层达到工作上限可作为有界近似；PC 因子失败、非有限值及其它实质失败必须传播。
用户开启 `ksp_error_if_not_converged` 会更严格地拒绝内层上限。

完整系统可解不保证 \(F\) 单独可解。流体子块存在未处理的压力零空间时，
须修正算例规范/边界或选择其它 recipe；程序不自动添加压力钉点。
外层 ALE 仍为乘法分裂，未构造包含 ALE 消元的全系统精确 Schur。

## 4. 两层联合速度校正

twolevel 对完整流固速度矩阵 \(A_v\) 构造稀疏插值 \(P\)：
每个 rank 内，对每个实际存在的
`(domain, kind, component, mode, space)` 分组建立一个单位 Euclidean 范数的
分片常数列。初始化时数值为精确恒等行的行不进入粗空间，插值为零。

\[
A_c=P^\mathsf T A_vP,\qquad
r_c=P^\mathsf T(r-A_vz),\qquad z\leftarrow z+PA_c^{-1}r_c.
\]

PCMG V-cycle 在粗校正前后用 ASM 平滑；细层和 Galerkin 粗层均看到流固非对角项。
每个有效细行只有一个插值非零元；各粗自由度由贡献细行所在 rank 拥有，
允许本地没有速度行或粗列。当前 P1 两域最多约 \(6p\) 个粗自由度，
\(p\) 为 MPI rank 数；其它实体种类、空间和模式会增加列数。

| 层 | 默认配置 |
|---|---|
| 联合速度 | FGMRES，rtol `1e-4`，max_it `20`；可显式选择 PREONLY |
| 细平滑器 | Richardson，1 次；ASM overlap `1` |
| ASM 局部解 | PREONLY、ILU(1)、RCM |
| 粗解 | GMRES/Jacobi，rtol `1e-10`，max_it `200`，unpreconditioned norm |
| 全恒等块 | 明确退化为一层 PREONLY/Jacobi，不构造空粗矩阵 |

粗 GMRES 可随右端改变工作量，因此联合速度迭代使用 FGMRES；最外层要求 FGMRES。
不允许用 `pc_type`、`pc_mg_levels`、`pc_mg_galerkin` 等选项改变固定拓扑。
局部因子、overlap、内外容差及粗解仍可调节。
`-pc_plan_report` 的 `pc_twolevel` 行报告实际粗维数和层数。

PCMG 随矩阵数值变化重新计算 \(P^\mathsf TA_vP\)，固定图时复用符号结构。
同一个配置周期内，分区、语义、图及约束集合必须保持不变；结构变化需重建求解器。
该方法没有坐标旋转模态、谱粗空间或完整多层 AMG，不承诺网格无关迭代或大规模加速。

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

## 6. 待执行入口与证据

以下命令是配置示例，**本轮尚未执行**：

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

待验收：独立稠密 Schur oracle、`P`/`PᵀAP`、两次数值更新、恒等退化、空本地块、
main/inner/upper、零残量错误配置、FSI/RCR 直接解全场对照、重启与失败缩步恢复。
入口包括 [verify_pc_plan.cpp](../../tests/verify_pc_plan.cpp)、
[verify_schur.py](../../tests/verify_schur.py) 和
[verify_fsi_tube.py](../../tests/verify_fsi_tube.py)。
`-linear_report` 仅报告诊断，不改变接受准则。
性能比较须固定精度，并记录真实残量、内外迭代、setup/apply 和整次时间。
**当前无本轮通过收据或性能结论。**

## 7. 源码与官方依据

- [语义树](../../src/algebra/pc_plan.cpp)：`make_pc_plan`、`configure_pc_plan`。
- [Schur 角色](../../src/algebra/schur_solver.cpp)：`configure_schur_subsolvers`。
- [粗校正](../../src/algebra/coupled_velocity_pc.cpp)：`configure_coupled_velocity_twolevel`。
- PETSc **v3.23.7**：
  [fieldsplit.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c)、
  [schurm.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/ksp/utils/schurm/schurm.c)、
  [mg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mg.c)、
  [mgfunc.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/mg/mgfunc.c)。
