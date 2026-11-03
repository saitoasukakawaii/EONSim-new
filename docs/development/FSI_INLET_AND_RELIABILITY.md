# 单体 FSI：固定速度入口、界面观测与几何有效性

## 入口

`fsi.inlet` 是共形独立双域弹性 FSI 的可选固定外边界速度，三分量同时消元：

```yaml
fsi:
  inlet:
    tag: 1
    value: [0.1, 0, 0]
    gradient: [[0, -0.1, 0], [0, 0, 0], [0, 0, 0]]
    origin: [0, 0, 0]
    ramp_time: 0.02
```

空间函数 `g(X)=value+gradient*(X-origin)` 使用参考坐标、全局笛卡尔分量。
`value` 和 `tag` 必填，其余默认零；参数必须有限，启动时间非负。
启动因子 `s=10*x^3-15*x^4+6*x^5`，`x=clamp(t/ramp_time,0,1)`；零启动时间取 1。

入口不得与压力标签或整个界面标签重合；必须属于流体域。
与既有齐次分量约束相交处对应空间分量必须为零；与流固界面交线处三分量均为零，
并且结构约束须已夹持这些自由度。非零矛盾不是通过覆盖旧约束解决。
入口 ALE 三分量固定；不支持移动入口、部分分量自然条件、空间曲线表达式或多入口。

BE/BDF2 使用终点规定值；generalized-alpha 使用
`g_stage=(1-alpha_f)*g(t_n)+alpha_f*g(t_n+dt)`，保证通过阶段映射恢复的终点满足规定值。
这是本质边界的终点插值，与自然压力直接取阶段时间值的契约不同。
启动步仍为 BE。重试重新计算候选终点和阶段；初态也包含零启动时间入口。
所有入口参数进入 checkpoint 签名；旧无入口配置的签名不变。

## 示例

```bash
python cases/fsi/generate_wall.py --output build/fsi-wall --subdivisions 4 --nonlinear
build/cloud-3.23.7-release/eonsim -case build/fsi-wall/case.json -prepare build/fsi-wall/part -parts 2
mpiexec -n 2 build/cloud-3.23.7-release/eonsim -case build/fsi-wall/case.json -partition build/fsi-wall/part
```

在仓库锁定的 PETSc 3.23.7 环境中运行。单位流体通道与厚度 .25 的固体顶壁共享 y=1 界面；
两端夹持，z 侧约束法向位移，固体其余外表面为零自然牵引。
入口轴向速度 .1*(1-y) 平滑启动，出口压力为零，刚性侧面无穿透滑移。
生成器同时提供线弹性与 Neo-Hookean 变体，不是无滑移实验通道或标准文献基准。

## 观测与几何

接受步 CSV 在旧字段后追加：

- `reference_interface_area`、`current_interface_area`；
- `area_displacement_x/y/z`、`area_velocity_x/y/z`：以参考三角形面积加权的终点均值；
- `stage_min_fluid_j/solid_j`、`endpoint_min_fluid_j/solid_j`：阶段/终点的最小体积比。

体积比为当前有向单元体积/参考有向单元体积，即仿射 Tet4 的 det F；
不是长宽比或完整的网格质量指标。刚体没有结构网格，对应 solid_j 记为 1。
正但接近零的值用于诊断，不自动改变求解模型；非正或退化几何在历史提交前拒绝。
阶段有效不能代替终点有效。实际拒绝会按有限缩步策略处理；耗尽后保留旧 checkpoint。

界面面片在启动阶段按稳定节点 ID 分布式路由计数，独立双域中仅保留恰有一个流体和一个固体邻接单元的面；
候选内部面即使三个节点都属于界面，也会消去。每步只归约面积积分和极值，不收集全局场。
面积积分使用线性面形函数，禁止把节点平均直接当作面积平均。
原 `position/velocity` 节点平均字段保留。`body_balance` 在弹性体中只累计自由轴向界面测试行，
不将夹持反力标成残量失衡；`fluid_force` 仍包含整个界面的轴向流体反力，二者不能直接混用。

## 验证与研究入口

`fsi_inlet`：三格式、逐步终点边界、1/2 rank、启动/周期段恢复、波形签名、整体切线、
Neo-Hookean 入口缩步与重放、真实 alpha 终点反转时 checkpoint/输出不提交及恢复。
`fsi_diagnostics` / `fsi_diagnostics_mpi`：解析面积积分、仿射体积比、阶段有效终点反转、跨 rank 内部面消去。
原 `fsi_pressure_state` 作为无入口路径的受影响回归。

`scripts/study_fsi_next.py` 提供 `inlet-time`、`accuracy` 和 `performance` 三种独立研究，
不会在普通 CTest 中自动执行整个性能/空间网格矩阵。实际结果以验收证据为准。

FSI-NEXT-01 的 [验收记录、数据和图](../research/data/fsi-next-2026-11-03/README.md)
包含 Debug/Release 定向检查、逐场时间阶、时间误差受控的空间比较以及最多 4 rank 的配对性能测量。
