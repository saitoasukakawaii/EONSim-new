# 周期流量驱动的无滑移弹性壁通道

状态：FSI-NEXT-02 实施中；验收与源码提交见任务队列和研究记录。不是文献标准基准或生产尺度验证。

## 输入及边界

在独立共形双域弹性 FSI 的 `fsi.inlet` 下，`flow_rate` 与原 `value/origin/gradient` 仿射入口互斥：

```yaml
fsi:
  inlet:
    tag: 1
    ramp_time: 0.02
    flow_rate:
      mean: 0.01
      amplitude: 0.005
      period: 0.1
      axis: 0
      lower: [0, 0, 0]
      upper: [0, 1, 1]
```

坐标以米计时，流量为 m³/s、时间为 s。通道示例采用合成 SI 参数（密度/黏度为 1、弹性模量 100），不对应人体主动脉。
正流量指流入；当前仅支持法向为负坐标轴、固定平面、轴对齐矩形入口。`axis` 为轴向索引 0/1/2；该方向上下界相等，其余两方向严格递增。反向入口法向、移动入口、多入口及任意截面不在范围内。

波形为 `Q(t)=s(t)[mean+amplitude*sin(2*pi*t/period)]`，`s` 是原入口的五次平滑启动函数。允许带符号的流量，但本次多周期研究不构成高 Re 回流稳定性验证。
横向形状取 `phi=r1*(1-r1)*r2*(1-r2)` 的节点 P1 插值，不是解析充分发展矩形管解。对实际入口三角网格积分得到 `I_h=integral(phi_h dA)`，规定 `u=Q(t)*phi_h/I_h * e_axis`，因此每个网格上的离散积分流量等于目标，而非仅使连续解析形状归一化。只有周边节点的过粗入口会产生零积分，明确拒绝，不能声称已经施加非零流量。

入口全分量 ALE 固定；原有交线相容检查保持有效。BE/BDF2 取终点值；generalized-alpha 使用两端点规定值的阶段插值，恢复后终点流量精确符合目标。缩步重算波形，所有波形和矩形参数进入 checkpoint 签名。

## 可复现算例

```bash
python cases/fsi/generate_wall.py --periodic-flow --subdivisions 4 --output build/flow-channel
```

原生成器默认滑移/仿射入口保持不变。`--periodic-flow` 将刚性底壁与两侧设为三分量零速度；弹性顶壁通过共享界面自由度满足流固速度相等，结构两端及两侧夹持。出口零自然压力，进出口网格固定。`--nonlinear` 可选 Neo-Hookean，默认线弹性。

先用 `scripts/cloud/restore.sh 3.23.7 <prefix>` 恢复锁定依赖，再通过 `scripts/cloud/run.sh 3.23.7 debug explicit <prefix> <selection.json>` 编译验证；清单为 `{"tests":["fsi_flow","fsi_inlet","fsi_pressure_state"]}`。Release 将模式替换即可。容器 root 执行需要显式设置 OpenMPI/PRRTE 的 allow-run-as-root 两组环境变量，普通用户不需要。

## 质量诊断的时间和符号

仅流量入口模式追加质量 CSV 字段，每个接受步一行：

| 字段 | 含义 |
|---|---|
| `stage_volume`、`endpoint_volume` | 当前流体 Tet4 有向体积之和 |
| `stage_inlet_flow`、`endpoint_inlet_flow` | 流入为正，实际几何上的速度通量积分 |
| `stage_outlet_flow`、`endpoint_outlet_flow` | 所有压力出口向外通量之和 |
| `stage_wall_flux`、`endpoint_wall_flux` | 其余真实流体边界的向外速度通量；本例为移动壁贡献，刚壁为零 |
| `stage_divergence`、`endpoint_divergence` | 独立按体单元积分的 div(u) |
| `volume_secant_rate` | `(V_(n+1)-V_n)/dt`，不是 BDF2/alpha 算法导数 |
| `stage_mass_residual` | `Qin_stage-Qout_stage-wall_flux_stage` |
| `secant_mass_residual` | `Qin_stage-Qout_stage-volume_secant_rate` |
| `target_endpoint_flow` | 原始目标终点波形，用独立测试表达式复核 |

连续不可压且无滑移时 `Qin-Qout=dV/dt=integral_wall(u.n dA)`。P1 表面通量与体散度独立积分满足散度定理，因此 `stage_mass_residual=-stage_divergence`。
这一检查证明当前离散求解的全局连续性，不证明每个单元局部强守恒或精确空间解。

有限步 secant 与阶段速度并非同一时间离散量；BDF2 或 generalized-alpha 不应要求该差为机器零。研究脚本同时计算时间加密趋势及用终点通量梯形积分得到的累计体积差，分别报告，不能用其中一项替代另一项。终点与阶段均检查正几何。

所有积分只遍历 rank 持有的单元及其边界，MPI 仅归约标量；界面面片沿用原分布式邻接识别，内部面不算外边界。拒绝步不输出质量历史；恢复的旧体积由保存的物理位移重建，不引入另一份可失配的累计体积状态。

## 验证范围

`fsi_flow` 覆盖三时间格式、精确离散流量、刚壁无滑移、界面相容、两种独立质量积分、1/2 rank、同分区恢复、签名拒绝、非法参数、Neo-Hookean 整体 Jv 和真实缩步重放。
`scripts/study_fsi_flow.py` 是单独的六周期/步长/网格研究入口，不自动作为普通 CTest 的大矩阵。
空间差异仅作为分辨率敏感性报告；未证明渐近收敛、实验一致性、大规模 MPI 或高 Re 稳定性。
