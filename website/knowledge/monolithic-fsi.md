# EONSim 单体流固耦合架构

## 1. 单体法的基本思想

单体 FSI 将流体、结构以及界面约束放入一个联合非线性系统中：

$$
\boldsymbol R(\boldsymbol x)=
\begin{bmatrix}
\boldsymbol R_f(\boldsymbol u,p,\boldsymbol d)\\
\boldsymbol R_s(\boldsymbol d,\boldsymbol u)\\
\boldsymbol R_\Gamma(\boldsymbol u,\boldsymbol d)
\end{bmatrix}
=\boldsymbol 0.
$$

Newton 迭代求解：

$$
\boldsymbol J(\boldsymbol x_k)\Delta\boldsymbol x
=-\boldsymbol R(\boldsymbol x_k).
$$

其中 Jacobian 包含流体、结构和跨场耦合导数。

## 2. 单体与分块预条件不是同一个概念

单体法描述的是非线性问题和未知量的联合求解。FieldSplit 或 Schur 补描述的是线性化系统的预条件策略。

因此，使用块预条件器并不意味着使用分区耦合算法。只要每次 Newton 迭代针对完整联合残量和完整耦合 Jacobian 求解，它仍然是单体方法。

## 3. EONSim 当前实现入口

- [FSI 求解驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fsi.cpp)
- [FSI 单元残量与切线](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fsi_element.cpp)
- [有效自由度布局](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/reduced_layout.cpp)
- [Schur 求解器](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/schur_solver.cpp)
- [单体 FSI 数学契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/architecture/L2_MONOLITHIC_FSI.md)

G0/G5 已支持独立的 physics/quantity/hybrid PC 树和 BE、变步 BDF2、共同 stage generalized-alpha；默认存储仍不变。时间映射、算法历史和端点输出的边界见 [时间支持矩阵](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/TIME_INTEGRATION.md)，真实验收最多 4 rank。上述残量矩阵是概念示意；当前 EONSim 显式保留 ALE 内部未知量，接口运动学通过 ReducedLayout 消元，并非另建一组界面乘子方程。

## 4. 阅读时需要区分的状态

- 数学模型：界面运动学、动力学和 ALE 映射的定义。
- 代码实现：当前支持的刚体/弹性、共形双域和有效 DOF 消元路径。
- 数值证据：具体算例、网格、时间步、求解器容差和 MPI rank 对照。

当前共形双域能力不能解释为任意非匹配界面、自动重网格或大规模生产性能保证。

## 5. 当前已合入的 FSI 能力（截至 2026-11-03）

以下均已合入 `main`。这里列出的是当前实现切片，不代表所有 FSI 物理模型都已覆盖。

### 5.1 平滑周期压力与接受步历史（PR #31）

保留 `fsi.pressure` 作为压力均值，可选 `fsi.pressure_time` 指定幅值、周期和启动时间。压力波形采用平滑启动的周期函数；BE/BDF2 在候选步终点评价，generalized-alpha 在共同 stage 评价。波形参数进入 checkpoint 签名，改变物理波形不能静默恢复旧状态。

启用 `output_interval` 后，接受步 CSV 记录响应量，VTU/PVTU 与 PVD 保存流体和固体时间序列。输出中的 `evaluation_time` 与 `time` 分别表示残量评价时刻和物理端点，不能混为一谈。见 [载荷与历史契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/FSI_PRESSURE_HISTORY.md) 和 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31)。

### 5.2 固定速度入口与阶段/终点几何检查（PR #32）

`fsi.inlet` 支持固定入口标签上的仿射速度分布及平滑启动。对 generalized-alpha，本质边界由相邻端点规定值插值得到 stage 值，避免直接取非线性函数的 stage 值后导致恢复端点不满足边界。入口与压力/界面标签及齐次约束交线必须相容；当前不支持移动入口、多入口或任意曲线入口。

求解器在提交 accepted 历史前检查阶段和终点流体/固体几何。界面观测采用参考面面积加权，并按真实双域面邻接筛选界面面片；不能仅凭三个节点属于界面节点集就判定一个三角面是流固界面。见 [入口与可靠性契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/FSI_INLET_AND_RELIABILITY.md) 和 [PR #32](https://github.com/saitoasukakawaii/EONSim-new/pull/32)。

### 5.3 周期体积流量入口、无滑移弹性壁与质量预算（PR #33）

新增 `fsi.inlet.flow_rate`，与原有 `value/origin/gradient` 仿射入口互斥。周期目标流量为 `Q(t)=s(t)[mean+amplitude*sin(2*pi*t/period)]`，其中 `s(t)` 为平滑启动函数。入口横向形状采用矩形坐标上的 `phi=r1*(1-r1)*r2*(1-r2)`，但归一化积分使用实际入口三角网格上的 P1 插值 `phi_h`：

`I_h = integral_Gamma_in(phi_h dA)`,  `u = Q(t)*phi_h/I_h*e_axis`。

因此离散边界积分匹配目标总流量，而不是仅对连续解析形状作归一化。当前仅支持固定平面、轴对齐矩形入口，法向为负坐标轴方向；过粗网格若离散形状积分为零会明确拒绝。

通道算例使用真实弹性顶壁与夹持边界，刚性底壁和侧壁施加三分量无滑移约束。质量诊断独立计算当前表面通量和体单元散度，并分别记录 stage 预算、端点体积和有限步体积 secant。stage 残差与 secant 预算不是同一个时间离散量，不应强制二者在有限步上都达到机器零。

复现入口见 [FSI 周期流量能力说明](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/FSI_PERIODIC_FLOW.md)、[验收证据](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/research/data/fsi-flow-2026-11-03/README.md) 和 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33)。

## 6. 验证证据与解释边界

| 里程碑 | 验证证据 | 可支持的结论 |
|---|---|---|
| FSI-LOAD-01 | PR #31 云端 PETSc 3.23.7 Debug/Release 各 24/24 项相关检查通过；网站检查通过 | 时变压力评价时间、接受步历史、重启和 I/O 失败路径有针对性验证 |
| FSI-NEXT-01 | 本地 Debug/Release 各累计 5 项针对性检查；1/2/4 rank 小规模研究 | 固定入口、几何有效性、界面诊断及记录范围内的时间/空间/性能比较有证据 |
| FSI-NEXT-02 | PR #33 云端 Debug/Release 各 29/29 项通过；网站构建和草稿隔离检查通过 | 周期流量入口、无滑移通道、质量预算及恢复路径有针对性验证 |

FSI-NEXT-02 的 Release 六周期研究覆盖三种网格和三种时间步，最大阶段质量残差为 `3.08e-16`。对 n=2 网格，时间步从 `.002`、`.001` 缩小到 `.0005` 时，后处理梯形通量积分的累计体积误差绝对值从 `4.97e-8` 降到 `4.26e-9` 和 `6.25e-10`。这项梯形积分是独立后处理检查，不是求解器时间格式的改变。

## 7. 适用范围与未验证事项

- 当前 FSI 主线是共形双域单体求解；这里的算例以 Tet4/P1 为主。
- 周期流量入口目前限于固定、轴对齐矩形入口和单一负坐标轴法向；不支持移动入口、多入口或任意截面。
- checkpoint 恢复限于相同分区/相同 rank 的既有契约；不代表跨分区迁移或跨机器格式兼容。
- 尚未证明非匹配界面、自动重网格、大规模 MPI 扩展、高 Reynolds 数稳定性或实验验证。
- FSI-NEXT-02 的网格差异仍未呈现空间渐近收敛，六周期结束时仍有剩余瞬态；不能宣称严格周期稳态。
- 全局质量预算不等于逐单元局部强守恒。FSI-NEXT-02 没有独立性能研究，不据此宣称速度提升。

## 8. 源码与证据入口

- 当前主线：[`4f3a995de45d`](https://github.com/saitoasukakawaii/EONSim-new/commit/4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e)。
- FSI-LOAD-01 实现：[`a6c6761`](https://github.com/saitoasukakawaii/EONSim-new/commit/a6c6761084f2003c72593107c6aa5cbc351d75bb)。
- FSI-NEXT-01 实现：[`0d93d41`](https://github.com/saitoasukakawaii/EONSim-new/commit/0d93d413f2a9c5ce97665f66925a52a786919937)，邻接补强 [`69692ee`](https://github.com/saitoasukakawaii/EONSim-new/commit/69692ee29269502a90deb845eecc30880b80fda7)。
- FSI-NEXT-02 实现：[`9bde797`](https://github.com/saitoasukakawaii/EONSim-new/commit/9bde79765ee57a2c42eb2964ac8297ec6246e3a7)，合并提交 [`4f3a995`](https://github.com/saitoasukakawaii/EONSim-new/commit/4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e)。
- 时间离散范围：[TIME_INTEGRATION.md](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/TIME_INTEGRATION.md)。