# 单体 FSI：平滑周期压力与接受步历史

适用：现有 Tet4 刚体/弹性体单体 FSI、共形双域及 BE/BDF2/generalized-alpha。
仍是小规模验证；不支持非匹配界面、自动重网格或跨分区重启。

## 载荷配置

保留数值 `fsi.pressure` 作为均值 p0。可选配置：

```yaml
fsi:
  pressure: 1
  pressure_time: {amplitude: 0.25, period: 0.1, ramp_time: 0.05}
  output_interval: 5
```

`amplitude`、`period` 必填，`ramp_time` 默认 0；参数有限、周期正、启动时间非负。
允许有符号压力。所有既有 pressure_tags 共用同一波形；不支持表格、逐标签波形或表达式。

压力为 `p(t) = s(t) * (p0 + amplitude*sin(2*pi*t/period))`。
启动时间正时，`x=clamp(t/ramp_time,0,1)`，`s=x^3*(10-15*x+6*x^2)`；否则 `s=1`。
未设置 pressure_time 时始终保持原恒压路径，包括 checkpoint 签名。
启用时波形参数参与签名，修改波形不能恢复旧 checkpoint；输出频率不影响物理签名。

BE/BDF2 在候选步终点评价，generalized-alpha 在共同 `t_n+alpha_f*dt` 评价；
alpha 启动步沿用 BE。重试从同一 accepted 时间重新评价压力。
压力是时间函数，在一次 Newton 内固定；受压面的面积与法向仍随 trial 几何变化，
原 ALE 压力几何切线保留。物理 kernel 不做时间推进或 I/O。

## 输出契约

`output_interval=0`（默认）仅保留原最终场。正整数启用历史：

- `<stem>.csv`：每个已接受步一行，不含初态或拒绝步。
- `<stem>_step<N>.vtu`：N 为已接受步号；按配置间隔以及本次运行的终点输出；MPI 使用 rank 片和 PVTU。
- `<stem>.pvd` 与 `<stem>_solid.pvd`：流体和弹性固体的实际时间序列，包含变形网格、已有场与适用算法历史。
- 原 `<stem>.vtu` 和 `<stem>_solid.vtu` 最终场保持兼容。

CSV 的 `endpoint_position/velocity` 为弹性界面**节点算术平均轴向**位移/速度，
刚体则为单自由度位置/速度；不是面积平均或点探针。
`evaluation_*` 的力、平衡和功率均对应残量评价时间；`applied_pressure` 同样对应
`evaluation_time`，不能与 generalized-alpha 终点量误当作同一时间层。
`evaluation_body_balance` 是现有轴向组合动量平衡诊断，不是全部固体自由度残量范数。

恢复运行的 CSV、PVD 和步骤文件使用 `<stem>_restart<恢复步号>`，仅含后续接受步；
原历史不变。原最终场仍写原路径。每次全新运行应选择独立输出目录/前缀，避免重用旧序列；
不支持多个 writer、自动拼接历史或并发可视化读取期间覆写同名运行。

所有 rank 完成流固片写入后才写 PVTU/PVD；PVD 临时文件关闭成功后通过 rename 发布。
写片或发布失败统一传播为 fatal I/O 错误，不缩步、不写该步 CSV。
已接受物理状态和已成功发布的 checkpoint 不回滚；失败文件可能保留，不能作为成功结果。
此输出不是断电持久化事务，流固两份 PVD 不保证联合原子替换。

## 运行示例

在仓库锁定 PETSc 3.23.7 环境下，从仓库根目录运行：

```bash
python cases/fsi/generate_periodic.py --output build/fsi-periodic
build/cloud-3.23.7-release/eonsim -case build/fsi-periodic/case.yaml -prepare build/fsi-periodic/part -parts 2
mpiexec -n 2 build/cloud-3.23.7-release/eonsim -case build/fsi-periodic/case.yaml -partition build/fsi-periodic/part
python cases/fsi/plot_history.py build/fsi-periodic/solution.csv
```

绘图入口需要 matplotlib，生成 PNG，不增加求解器依赖。
ParaView 同时打开 `solution.pvd` 和 `solution_solid.pvd`，按时间播放。
输出坐标已经包含位移，不要再次 Warp By Vector。压力载荷驱动弹性端块响应；
该示例不是 Turek–Hron 基准或实验验证。

## 每个受压面的压力、流量与载荷功率

在算例的 `fsi` 段设置 `pressure_face_history: true`。程序在每个接受步为每个受压标签写一行到
`<stem>_pressure_faces.csv`。共形双域使用 `domains.pressure_tags` 的配置顺序，旧立方体使用标签 1。
此开关默认为关闭，可以与任意 `output_interval` 配合，也可以从已有检查点开始启用。
续算写入 `<stem>_restart<N>_pressure_faces.csv`，其中 N 是恢复步号。

`stage_` 列使用 `evaluation_time` 的位形、速度、压强与边界载荷。`endpoint_` 列使用 `time` 的相应量。
BE、BDF2 和 generalized-α 的 BE 启动步在终点加载。后续 generalized-α 步在共同阶段加载，
终点的 `prescribed_pressure` 是同一波形在输出时刻的取值。

| 后缀 | 定义和 SI 单位 |
|---|---|
| `area` | 当前构形各三角面的面积和，m² |
| `mean_pressure` | 有限元静压的面积均值，Pa |
| `mean_normal_traction` | 流体侧 Cauchy 正应力 $n^T\sigma n$ 的面积均值，拉为正，Pa |
| `outward_flow` | $Q=\int_\Gamma u\cdot n\,dA$，相对于空间坐标，流出为正，m³/s |
| `prescribed_pressure` | 配置的外加压力 $p_b(t)$，Pa |
| `pressure_power` | 外压对流体做功的速率 $-p_b Q$，W，输入能量为正 |

这里 $n$ 是当前流体外法向，$\sigma=-pI+\mu(\nabla u+\nabla u^T)$。每个平面三角形的 P1 压力、速度面均值
由三个顶点精确积分，速度梯度来自相邻流体 Tet4。跨进程先按标签求积分和，再用全局面积归一化。
弱式施加的压力牵引与单元侧恢复应力可以分别比较。功率取流体材料速度，移动端面的相对流量还需要扣除网格速度。
端面功率的时间积分应记录所用求积规则，特别是从静止启动的第一个 BE 步。

## 针对性检查

`fsi_pressure_state` 覆盖三时间格式的载荷取值、1/2 rank、启动段/周期段恢复、
配置变化拒绝、恒压兼容、完整装配 Jacobian、接受序列、快照几何及局部 I/O 失败。
BDF2/alpha 的 Neo-Hookean 检查实际缩步并重放接受步长。
`fsi_pressure_convergence` 固定 tau=0.05，同一双域网格比较细步参考下的时间误差。
局部压力面积切线及波形端点包含在 `fsi_element_jacobian`。
实际执行结果见任务会话日志和 `docs/research/data/fsi-pressure-2026-11-03/`；
测试注册或上述描述本身不表示已经通过。

## 流体散度耗散对照

`fsi.grad_div_viscosity` 和独立流体的 `fluid.grad_div_viscosity` 接受空间均匀、有限且非负的系数 γ，单位为 Pa·s。两者默认取 0。对于仿射 Tet4，将 $V_e\gamma(\nabla\!\cdot u)\,\partial_i N_a$ 加到动量行，连续性残量和已有 SUPG/PSPG 系数沿用原定义。该项对离散速度所作的功为 $\sum_e V_e\gamma(\nabla\!\cdot u)^2$。固定网格切线和 ALE 的当前体积、空间梯度及其导数都包含此项。接受步的端面 `mean_normal_traction` 仍按物理牛顿应力 $-pI+2\mu\epsilon(u)$ 计算。

可用同一时刻的空间散度 RMS 和截面位移一起衡量系数的影响。均匀 γ 与 svFSI 每个积分点的 τC 定义不同，不能从一个工况直接移植数值。显式 0 可恢复旧格式检查点；改变非零系数会触发物理签名不匹配。[相同载荷下的实测结果](../research/data/fsi-smooth-load-2026-11-24/README.md)

弹性管还可按固体外表面标签配置参考法向支撑。其接受步历史包含弹簧储能、阻尼耗散和对壁做功。[支撑模型与输出列](FSI_WALL_SUPPORT.md)
