# 整体 FSI 多重网格、压力增强与精确 Matrix-free 求解

本文说明当前源码中的算法、调用选项和使用边界。验收所用提交、实际算例、原始日志及 PR 状态由
[项目进度](CODEX_PROGRESS.md)、[会话记录](CODEX_SESSION_LOG.md)和本轮证据索引记录；下面的命令是调用示例，不能作为已经运行的证据。

适用对象是现有共形、低阶、约束消元后的单体 FSI 系统。`monolithic_mg` 对流体速度、压力、结构速度和 ALE 网格未知量共同建立代数多重网格。它是显式选择的预条件器；现有默认求解配置保持原状。

## 1. 功能与入口

| 功能 | 当前实现与入口 | 主要边界 |
| --- | --- | --- |
| 整体 FSI Multigrid | `-pc_recipe monolithic_mg`；完整混合矩阵的递归 Galerkin 层级 | 代数聚合；不需要几何网格层级。层数取决于实际可压缩粗空间 |
| Multilevel Vanka | 默认 `-monolithic_mg_smoother vanka`；细层混合重叠 patch、中间层完整混合聚合块 | 最粗层使用完整耦合求解；界面标记来自真实布局及插值支撑 |
| Added-mass-aware 压力 Schur | `-pc_recipe hybrid -pc_plan_schur_approx added_mass` | 显式结构顺应性反馈；结构及流体逆仍采用节点块近似 |
| 能量最小化插值 | `-monolithic_mg_energy_steps`，默认 1 | 最小化经行均衡后的非负正规能量，保留候选及锚点；不假设 FSI Jacobian 正定 |
| 自适应谱粗空间 | `spectral_modes`、`spectral_tolerance`、`spectral_refresh_period` | 聚合体局部低能量特征向量；可按刷新周期重建，非全局残差学习 |
| PCD Robin 与速度质量增强 | `-pc_plan_pcd_robin`、`-pc_plan_pcd_velocity_mass` | 真实入口辅助边界和离散 Laplace 混合；仍要求空间均匀正黏度 |
| Vanka 批量分解与缓存 | 混合 patch 自动使用同尺寸 LU 批处理、相同行集合复用和精确数值缓存 | 不改变局部误差检查；没有额外 CLI 开关 |
| Chebyshev / Block Chebyshev | `-monolithic_mg_smoother chebyshev` 或 `block_chebyshev` | 在经过缩放/白化的隐式正规算子上执行固定阶数多项式 |
| 混合精度 V-cycle | `-monolithic_mg_single_precision true` | float 稀疏系数和算术、Vanka float 因子；FP64 setup、粗解及原始残量保留 |
| 粗层 MPI 聚合 | `-monolithic_mg_coarse_processes`，默认 1 | 最粗层由 PETSc `PCTELESCOPE` 聚合；中间层保留原 communicator |
| Pipelined FGMRES | `-ksp_type pipefgmres -ksp_pc_side right` | 使用 PETSc 实现；通信重叠收益取决于实际 MPI 环境 |
| 精确 Matrix-free FSI + assembled P | `-fsi_matrix_free -nonlinear_matrix_free_pc_interval N` | 精确方向作用与完整 assembled P 分开；当前仍保留完整 AIJ 预条件矩阵 |

源码入口：[层级与选项](../../src/algebra/monolithic_fsi_mg.cpp)、[层平滑器](../../src/algebra/fsi_level_smoother.cpp)、
[混合 patch](../../src/algebra/interface_patch_pc.cpp)、[压力 Schur](../../src/algebra/pressure_schur_pc.cpp)、
[物理 PCD 辅助装配](../../src/physics/fsi_pressure_operators.cpp)、[非线性算子管理](../../src/algebra/nonlinear_system.cpp)。

## 2. 常用调用

在已配置的 Release 环境中，先为所用 rank 数准备分区。以下使用仓库双域小例展示调用方式；实际是否产生多个网格层须检查 `pc_monolithic_mg levels=`。

```bash
FSI_BIN=./build/release/eonsim
FSI_CASE=cases/fsi/domains/case.yaml
FSI_PART=results/fsi_mg_part2

"$FSI_BIN" -case "$FSI_CASE" -prepare "$FSI_PART" -parts 2

FSI_RUN=(mpiexec -n 2 "$FSI_BIN" -case "$FSI_CASE" -partition "$FSI_PART"
  -ksp_pc_side right -ksp_norm_type unpreconditioned
  -ksp_rtol 1e-12 -ksp_atol 1e-15 -ksp_max_it 1500 -ksp_gmres_restart 100
  -linear_report -solver_report -pc_plan_report)

# 整体层级、每层 Vanka、最粗层聚合到一个进程。
"${FSI_RUN[@]}" -pc_recipe monolithic_mg -ksp_type fgmres \
  -monolithic_mg_coarse_limit 48 -output results/fsi_mg.vtu

# FP32 稀疏 V-cycle 与 FP32 Vanka 因子，外层和物理残量保持 FP64。
"${FSI_RUN[@]}" -pc_recipe monolithic_mg -ksp_type fgmres \
  -monolithic_mg_coarse_limit 48 -monolithic_mg_single_precision true \
  -output results/fsi_mg_fp32.vtu

# PETSc pipelined flexible GMRES。
"${FSI_RUN[@]}" -pc_recipe monolithic_mg -ksp_type pipefgmres \
  -monolithic_mg_coarse_limit 48 -output results/fsi_mg_pipe.vtu

# 每次 Newton 使用新的精确方向算子；每两次 Jacobian 回调刷新 assembled P。
"${FSI_RUN[@]}" -pc_recipe monolithic_mg -ksp_type fgmres \
  -monolithic_mg_coarse_limit 48 -fsi_matrix_free \
  -nonlinear_matrix_free_pc_interval 2 -output results/fsi_mg_mf.vtu
```

`coarse_limit=48` 是上述小例的显式设置，源码默认值是 96。命令行容差也是示例设置，不是修改模型验收门槛的接口。PIPEFGMRES 使用右预条件；普通 GMRES 的正交化选项不要不加区分地复制到 pipelined 方法。

选择多项式平滑器时，在整体 MG 命令上添加以下一种组合：

```text
-monolithic_mg_smoother chebyshev -monolithic_mg_polynomial_degree 3
-monolithic_mg_smoother block_chebyshev -monolithic_mg_polynomial_degree 3
```

### 压力增强路径

附加质量压力近似与物理 PCD 属于 `hybrid` 块预条件路径，使用其自己的压力 Schur；它们不是 `monolithic_mg` 的嵌套参数。

```bash
"${FSI_RUN[@]}" -pc_recipe hybrid -ksp_type fgmres \
  -pc_plan_velocity_solver field_amg -pc_plan_velocity_coarse_space rigid \
  -pc_plan_schur_approx added_mass -output results/fsi_pressure_compliance.vtu

"${FSI_RUN[@]}" -pc_recipe hybrid -ksp_type fgmres \
  -pc_plan_velocity_solver field_amg -pc_plan_velocity_coarse_space rigid \
  -pc_plan_schur_approx pcd -pc_plan_pcd_velocity_mass true \
  -pc_plan_pcd_velocity_mass_weight 0.5 -output results/fsi_pcd_mass.vtu
```

PCD Robin 在已配置 `fsi.inlet.tag` 的速度/流量入口案例上添加 `-pc_plan_pcd_robin true`。
仅有压力牵引入口、没有显式速度/流量入口标签的案例不能启用该选项。
`-pc_recipe added_mass` 是既有的流体—结构 Schur 树；本轮新入口
`-pc_recipe hybrid -pc_plan_schur_approx added_mass` 指的是压力 Schur 中的结构顺应性消元，两者的块排列和近似不同。

### RCR 端口的前缀

含边界压力端口时，整体 MG 和物理 PCD 要配合 `-pc_plan_rcr_ports true`。
端口 Schur 位于最外层，其 bulk 求解器前缀为 `rcr_bulk_`。例如，含 RCR 的整体 MG 使用：

```text
-pc_recipe monolithic_mg -pc_plan_rcr_ports true
-rcr_bulk_monolithic_mg_coarse_limit 48
-rcr_bulk_monolithic_mg_single_precision true
-rcr_bulk_monolithic_mg_coarse_processes 1
```

| 参数类别 | 无 RCR wrapper | 有 RCR wrapper |
| --- | --- | --- |
| 层级选项 | `-monolithic_mg_*` | `-rcr_bulk_monolithic_mg_*` |
| 最粗层 KSP | `-monolithic_mg_coarse_*` | `-rcr_bulk_monolithic_mg_coarse_*` |
| 全局 recipe / PCD 控制 | `-pc_recipe`、`-pc_plan_schur_approx`、`-pc_plan_pcd_*` | 名称保持相同 |
| Matrix-free 与外层 KSP | `-fsi_matrix_free`、`-nonlinear_matrix_free_pc_interval`、`-ksp_type` | 名称保持相同 |

不要同时传入 `monolithic_mg` 与旧块树的 `-pc_plan_velocity_solver`、`-pc_plan_schur_approx` 或
`-pc_plan_patch_*`。实现会拒绝这些未被整体层级消费的参数。其他 RCR 约定见
[端口预条件器说明](RCR_PORT_PRECONDITIONER.md)。

## 3. 整体层级的选项和默认值

下表后缀接在 `-monolithic_mg_` 后；有 RCR wrapper 时按上一节改前缀。所有 MPI rank 必须使用一致的选项。

| 后缀 | 默认 | 允许值与含义 |
| --- | --- | --- |
| `aggregate_nodes` | 12 | 2–128；一次聚合最多包含的节点/上一层聚合块数 |
| `aggregate_rows` | 192 | 8–512；聚合体最大活动行数；单个语义块不能被截断以凑上限 |
| `max_levels` | 8 | 1–20；包含最细及最粗层 |
| `coarse_limit` | 96 | 正整数；达到此全局行数后停止继续粗化 |
| `energy_steps` | 1 | 0–3；受候选和锚点约束的插值能量下降步数 |
| `spectral_modes` | 2 | 0–8；每聚合体最多添加的独立局部谱模态数 |
| `spectral_tolerance` | 0.1 | [0,1]；相对于局部正规矩阵最大特征值的选取阈值 |
| `spectral_refresh_period` | 0 | 0–1000000；0 保留插值；正值按显式数值刷新周期重建谱基、插值和层级 |
| `pre_smooth` / `post_smooth` | 1 / 1 | 各 0–8，两者之和须大于 0 |
| `smoother` | `vanka` | `vanka`、`chebyshev`、`block_chebyshev` |
| `patch_overlap` | 1 | 0–2；最细层混合 patch 的图扩展层数 |
| `coarse_patch_overlap` | 0 | 0–2；中间层混合 patch 的图扩展层数；0 保留每个完整聚合体基，不向相邻聚合体扩展 |
| `patch_maximum_size` | 256 | 1–2048；单 patch 最大行数；超限共同失败，不丢弃耦合行 |
| `patch_damping` | 1 | (0,2]；patch 或多项式增量的阻尼 |
| `polynomial_degree` | 3 | 1–32；Chebyshev 固定迭代次数 |
| `eigenvalue_ratio` | 0.1 | (0,1)；所平滑谱区间下界与上界之比 |
| `single_precision` | `false` | 启用 float 层矩阵/传递作用及 Vanka float 因子 |
| `coarse_processes` | 1 | 正整数；最粗层进程预算，实际取不超过预算且整除原 communicator 大小的最大值 |

层 Vanka 的 FP32 改进目前使用类型默认值：最多 3 次 refinement，分量后向误差容差 `1e-10`。
这些值尚未暴露为 `monolithic_mg_*` CLI 参数。旧根部界面 wrapper 的 `-pc_plan_patch_refinement_*`
只属于旧 wrapper；其调用方式见[既有高级预条件器文档](FSI_ADVANCED_PRECONDITIONERS.md)。

最粗层聚合到单进程后默认 `PREONLY + LU`；多进程粗解默认有界 `GMRES + ASM`、局部 LU，
相对容差 `1e-12`、最多 200 次迭代。通过上述 `monolithic_mg_coarse_` 前缀配置 PETSc 子求解器；
启用 telescope 后，其内部 KSP 再追加 `telescope_`。不得覆盖所请求的 telescope 类型/进程缩减因子来伪装聚合已经生效。

## 4. 数学作用与刷新

### 完整混合 Galerkin 与受约束插值

记 assembled 预条件矩阵为 \(P_{\rm asm}\)，细层为 \(A_0=P_{\rm asm}\)，层间插值为 \(Z_\ell\)：

\[
A_{\ell+1}=Z_\ell^T A_\ell Z_\ell.
\]

所有实际跨场块随该投影传入粗层。物理候选共有 22 个槽位，按实际语义启用流体/结构/ALE 三分量常数、压力常数、刚体/边界/标量候选及参考坐标旋转。
聚合体局部 QR 去除零列和相关列，后续层传播同一候选的粗系数；候选不被宣称为完整动态 FSI 的精确零空间。

局部谱增强从经行均衡的混合主子块的正规矩阵提取小特征值向量，并加入与既有候选独立的部分。
能量下降最小化

\[
E(Z)=\|D_\ell A_\ell Z\|_F^2,
\qquad ZN_{\ell+1}=N_\ell,
\]

其中 \(D_\ell\) 为行均衡尺度。秩揭示选取的锚点行保持不变，防止只保留物理候选的约束下新增谱列塌缩。
实现审核候选重构误差与能量不增；这既不是对不定 \(A_\ell\) 的 SPD 能量最小化，也不是离散 inf-sup 或网格无关收敛证明。
详细契约见[公共头文件](../../include/eonsim/monolithic_fsi_mg.hpp)。

默认数值刷新更新 Galerkin 矩阵、全部非最粗层因子和最粗层数值解，保留插值。
源矩阵 numeric state 未变化时跳过重复 Galerkin 产品，避免分布式累加舍入变化造成无意义的精确缓存失效。
设置正的 `spectral_refresh_period` 才会周期性重建谱基与插值；这是按刷新周期进行的局部谱适配，不是全局残差模态学习。

### 每层 Vanka、缓存与混合精度

每个活动节点或粗聚合体产生一个混合种子；同一实体中的不同物理场共同进入 patch。
最细层默认按矩阵图扩展一层。中间层默认 `coarse_patch_overlap=0`，一个 patch 保留其聚合体的全部物理候选及谱基列；
当前最多 22 个物理候选槽加 8 个谱列，因此完整粗聚合块大小有界。它是混合块 Vanka，不按场或单个粗变量拆分。
Galerkin 图经能量插值后可能稠密；在该图上直接沿用细层 overlap 会使一个 patch 扩张到大部分网格层。
粗层跨聚合体耦合继续参与完整矩阵残量、传递和后续粗校正。显式设置正的 `coarse_patch_overlap` 时仍执行原大小上限检查，
超限即共同失败，既不截断耦合行，也不自动提高上限或静默减少用户选择的 overlap。
patch 可包含远程行，校正按全部 MPI rank 的真实覆盖次数加权。精确 identity 行直接求解；不会人为添加压力 pin 或局部对角移位。

同尺寸 patch 的独立主元 LU 使用有界 AoSoA 批处理；相同局部行集合复用分解，刷新前后完全相同的稀疏数值复用已存因子。
缓存的有效性检查保留 graph、ownership、约束和矩阵身份要求，失败刷新使旧代不可用。

FP32 patch 使用行列均衡、部分选主元和 FP64 残量改进；不满足原分量后向误差标准时明确回退 FP64。
混合 V-cycle 另外以 float 保存层稀疏系数并执行层 matvec、限制和延拓算术；输入及行系数缩放控制转换范围。
外层向量、物理残量、FP64 Galerkin/setup 矩阵、粗解以及 Chebyshev 的白化算子仍保留。
`fp32_value_bytes` 只统计 float CSR 系数；`factor_bytes` 只统计局部 LU 值数组，不能用它们声称整个层级或程序内存减半。

### Chebyshev 的正规算子

层 Jacobian 通常不对称且不定。多项式平滑器构造

\[
B=DAC,\qquad B^TB\,y=B^TDr,\qquad \delta x=Cy.
\]

\(D\) 做行均衡；point 模式的 \(C\) 归一化列，block 模式按同实体列块做 Cholesky 白化。
`MatCreateNormal` 隐式作用 \(B^TB\)。固定阶数多项式针对
\([\eta\Lambda,\Lambda]\)，其中 \(\Lambda=1.05\|B\|_1\|B\|_\infty\)、\(\eta=\texttt{eigenvalue_ratio}\)。
下方低频交给粗校正。谱界在 setup 计算，应用期间没有用于范数或特征值估计的全局 dot reduction；稀疏 halo 通信仍然存在。
正规方程可能加重谱条件数，实际收敛和总成本必须结合粗空间测量。[平滑器契约](../../include/eonsim/fsi_level_smoother.hpp)

## 5. 结构顺应性压力 Schur 与 PCD

### Added-mass-aware 压力近似

将 `hybrid` 联合动量块分为流体与结构：

\[
A=\begin{bmatrix}F&E\\G&K\end{bmatrix},\qquad
B=\begin{bmatrix}B_f\\B_s\end{bmatrix},\qquad
C=\begin{bmatrix}C_f&C_s\end{bmatrix},\qquad S=D-CA^{-1}B.
\]

\(H_s\) 取结构节点块逆，\(\widehat F=F-EH_sG\)，\(H_f\) 再取 \(\widehat F\) 的流体节点块逆，得到

\[
\widehat S=D-C_sH_sB_s
-(C_f-C_sH_sG)H_f(B_f-EH_sB_s).
\]

因此实际结构刚度、惯性及时间映射经 \(K\) 的顺应性进入压力近似，结构反馈同时修正流体动量和两侧压力耦合。
\(E,G\) 及 \(B,C\) 分别提取；非对称 ALE 情形不会被强行换成转置。界面 alias 只属于一个结构代表，不重复计数。
该近似保留完整压力稳定化 \(D\)，没有用人为密度比代替耦合算子；节点块逆仍是局部近似。
默认压力辅助逆为一次 GAMG 作用，不能将其称为精确 \(\widehat S^{-1}\)。[实现契约](../../include/eonsim/pressure_schur_pc.hpp)

### PCD 入口 Robin

在显式速度/流量入口 \(\Gamma_{\rm in}\) 的压力输运辅助算子上增加

\[
-\int_{\Gamma_{\rm in}}\rho\,[(u-w)\cdot n]\,q\,p\,d\Gamma.
\]

当前 ALE 几何、外法向和相对速度取自同一 trial；Tri3 三次被积项采用精确重心积分。
`fluid.convection=false` 时此对流 Robin 项为零。已有压力牵引边界继续约束辅助 Laplace 校正，原压力质量及物理压力未知量保持其模型含义。
缺少入口标签、入口非流体邻接、没有辅助牵引边界或空间变黏度都会明确拒绝。

### 速度质量增强

| 控制项 | 默认 | 含义 |
| --- | --- | --- |
| `-pc_plan_pcd_robin` | `false` | 上述入口辅助 Robin 项 |
| `-pc_plan_pcd_velocity_mass` | `false` | 发布并使用几何集中速度 \(L^2\) 质量 |
| `-pc_plan_pcd_velocity_mass_weight` | 0.5 | \(\theta\in[0,1]\)；只在启用质量增强时可指定 |

对 active fluid velocity traces 组装几何集中质量 \(M_u\)，构造
\(K_M=-C\operatorname{diag}(M_u)^{-1}B\)，并应用与原 \(K_p\) 相同的辅助边界行。
结构内部行不属于该流体质量空间，其权重取零。随后

\[
K_\theta=(1-\theta)K_p+\theta K_M,\qquad
F_\theta=F_p+\mu(K_\theta-K_p),
\]

\[
T_\theta=K_\theta+F_\theta M_p^{-1}D,\qquad
\mathcal B_p r\approx T_\theta^{-1}F_\theta M_p^{-1}r.
\]

同时修改输运中的扩散部分保留了该 PCD 模型的稳态 Stokes 质量极限；原反应、对流及 Robin 项继续参与。
默认混合权重保留几何 Laplace 份额。这是离散 Laplace 混合增强，不等同于文献中的完整加法 PCDR 公式；也没有声称在所有瞬态和强耦合条件下优于原 PCD。

## 6. Matrix-free 与 Krylov 的运行约束

`-fsi_matrix_free` 通过 `MatShell` 提供当前 Newton 冻结状态上的精确 \(Jv\)：流体/ALE 使用单方向链式微分，结构使用局部本构切线作用，入口提升、界面消元、支撑及 RCR 导数沿原装配映射进入同一方向响应。
方向应用不提交材料或时间历史。[FSI 作用实现](../../src/physics/fsi.cpp)、[单元方向接口](../../include/eonsim/fsi_element.hpp)

`-nonlinear_matrix_free_pc_interval` 默认 1，范围 1–1000，每次新的非线性 solve 的首个修正总刷新 assembled P。
随后按该间隔复用 P，精确方向算子仍随每次 Newton 线性化更新。间隔大于 1 只有在实际发生多个相应修正时才减少装配；应读取 `assembled_pc_reuses`。

当前 P 是完整 AIJ 矩阵，尚未提供另一个低阶、稀疏化或 partial-assembly P。因此不能仅凭开启 Matrix-free 宣称全局矩阵存储或总内存减少。
组装成本、每次方向作用成本和外层迭代次数需要一起比较，尤其本实现仍在每次方向应用中计算局部结构切线。

精确 Matrix-free 要求 `fgmres` 或 `pipefgmres`，使用自身 P 刷新间隔；它拒绝 `-fsi_fd_tangent`、PETSc SNES FD/MF 替代算子、手工 Jacobian/PC lag/reuse、EW 覆盖以及另一个 `-nonlinear_adaptive_pc` 策略。
PIPEFGMRES 的异步归约由 PETSc 管理，实际能否隐藏同步等待取决于 MPI progress、算例大小和预条件工作量。

## 7. 诊断、验证与解释边界

| 报告/查询 | 需要查看的内容 |
| --- | --- |
| `-pc_plan_report` → `pc_monolithic_mg` | 实际层数、粗进程数、精度、谱层级重建次数 |
| `pc_monolithic_mg_level` | 每层细/粗行数、实际新增谱模态、候选重构误差、能量变化 |
| `pc_monolithic_mg_smoother` | 每个 rank/非最粗层的实际 overlap、最大 patch、patch 行总数、被覆盖的 owned 行数、interface patch 数、分解批次、缓存、FP32 因子及多项式谱界 |
| `interface_patch_pc` / patch stats | LU 数组字节、setup/apply fallback、refinement 次数；均有明确局部计数范围 |
| `pressure_schur` | 实际 `kind`、数值更新、`velocity_mass`、`mass_blend` |
| `-solver_report` | 实际 KSP 类型、迭代数、组装次数、`matrix_free_actions`、`assembled_pc_reuses`、时间和 RSS |
| `-linear_report` | 原始线性算子的显式残量；Matrix-free 时对应当前精确 \(Jv\) |

空 owner 或没有本地界面的 rank 可以报告零 patch/零 interface patch。每层覆盖应按全部 rank 汇总，且核对全部非最粗层，不能只看 rank 0。
粗层 overlap 为零时，实际 `patch_rows` 和 `covered_owned_rows` 的全 rank 总和均应等于该层活动行数。
有重叠时 `patch_rows` 包含重复覆盖，`covered_owned_rows` 仍按每个 owner 的唯一活动行计数。
配置报告中的层级存在不等于已经证明每层执行；定向代数验证另检查实际 application 计数，物理验证对照直接轨迹、保存场、历史与原始残量。

相关入口为 `interface_patch_mpi{1,2,4}`、`fsi_level_smoother_mpi{1,2,4}`、`monolithic_fsi_mg_mpi{1,2,4}`、
`added_mass_pressure_mpi{1,2,4}`、`matrix_free_mpi{1,2,4}` 及 `monolithic_fsi_physical`。
[物理驱动](../../tests/verify_fsi_multigrid.py)可显式选择 `default`、`moving`、`scaling`、`coupling` 段，保留失败原件和每次执行来源。
新增/受影响源码遵循先同步远端再执行选测；已验证且未受影响的证据不因普通文档提交重跑。

实现多层算子、通过小 rank 数值对照与实现网格无关收敛是不同结论。
物理网格加密后的迭代变化、强附加质量区间的稳健性、多节点通信及端到端时间收益，应以各自实测范围报告。
粗过程聚合、float 系数或局部分解次数减少本身不构成整个程序加速或内存减半的证据。
