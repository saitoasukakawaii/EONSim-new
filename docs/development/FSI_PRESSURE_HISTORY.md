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

## 针对性检查

`fsi_pressure_state` 覆盖三时间格式的载荷取值、1/2 rank、启动段/周期段恢复、
配置变化拒绝、恒压兼容、完整装配 Jacobian、接受序列、快照几何及局部 I/O 失败。
BDF2/alpha 的 Neo-Hookean 检查实际缩步并重放接受步长。
`fsi_pressure_convergence` 固定 tau=0.05，同一双域网格比较细步参考下的时间误差。
局部压力面积切线及波形端点包含在 `fsi_element_jacobian`。
实际执行结果见任务会话日志和 `docs/research/data/fsi-pressure-2026-11-03/`；
测试注册或上述描述本身不表示已经通过。

## 显式 LU 预条件复用

`-fsi_lu_pc_reuse_window N` 默认为0，范围0..1000000。显式指定此选项仅支持
线性弹性、周期压力、共形双网格、generalized-alpha；不支持Neo-Hookean、刚体、
入口速度/流量、BE/BDF2或其它物理。非零窗口必须显式选择MUMPS，使用FGMRES和
未预条件残量；与Schur、block、语义PC配方及独立PC滞后选项不相容，错误配置拒绝。

在受支持的已准备算例上可追加：

```text
-pc_factor_mat_solver_type mumps -snes_lag_jacobian -2 -fsi_lu_pc_reuse_window 32
```

步内Jacobian按原选定策略装配，只有已接受求解的LU预条件因子可跨步保留。
流体、固体、网格位移三种有效积分系数任一变化都刷新；启动、事件、步长变化因此各自
按真实系数处理。终点几何拒绝会清除系数标记，下一次重试不能误用已拒绝状态的因子。
LU不进入checkpoint，也不改变物理签名；恢复后新建执行缓存，完整时间/物理历史照常恢复。
窗口不允许改变非线性、分场接受或几何门槛。

[2026-11-09增量验证](../research/data/fsi-retained-lu-validation-2026-11-09/README.md)
实际Debug/Release各三项通过，覆盖新路径1/2/4rank、重启、事件和变步长；3696 HDF
数据集最大差9.7318e-15，v4时钟与时间元数据精确。实际细网格成本及长程资格仍须单独验证，
不能从小算例分解次数减少推断生产加速。新缓存的真实终点几何拒绝路径未单独数值触发。
