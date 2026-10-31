# 时间离散实施状态

G5仍在实施。当前支持独立瞬态流体、独立卸载固体、给定位移ALE及单体刚体/弹性FSI的BE与变步BDF2；
独立瞬态流体支持一阶generalized-alpha，独立结构支持二阶generalized-alpha；
ALE及单体FSI已接入共同stage的一阶流体与二阶运动学。独立刚体ODE演示仍仅支持BE。
本表随真实验证更新，不能将这一增量解释为G5完成。

```yaml
time:
  scheme: bdf2 # 默认be
time_control:
  step_sizes: [0.008, 0.012] # 按accepted步序号选择，耗尽后重复末项
  events: [0.055] # 截断候选步；该时刻之后重新用BE启动
  max_retries: 6
  minimum_dt: 0.000001
  reduction: 0.5
```

终止时间仍由该物理配置的`dt*steps`指定。控制器取候选步长、下一事件和终止时间
的最小值；积分器按本次实际步长重算系数。拒绝不推进步序号或历史。
若选择BDF2，候选步增长最多为上一实际accepted步长的2倍；减步没有额外比率下限。
控制器用补偿求和避免累加舍入误差制造多余的近零末步；重启重置浮点补偿，
承诺数值容差内一致，不承诺位级一致。

## 数学及状态契约

设本次步长h，上一实际accepted步长k，r=h/k。BE令q=h、b=0；
BDF2令q=h(1+r)/(1+2r)、b=r²/(1+2r)。统一导数为

`ydot = (y_(n+1) - [y_n + b*(y_n-y_(n-1))]) / q`。

首步或事件后没有有效历史时采用BE。流体惯性使用该导数，代数量压力仍在端点求解。
结构独立未知量为速度；位移为`d_ref+q*v_(n+1)`，加速度为`(v_(n+1)-v_ref)/q`，
局部切线分别使用q和1/q。历史仅在整体物理验收成功后提交。
BE卸载固体保持原物理能量单调验收；BDF2不能套用同一判据，其稳定性涉及历史范数。
BDF2仍检查能量有限和非负，并在振动测试中验证随时间加密恢复无阻尼能量。

BDF2 checkpoint保存前一accepted物理状态和上一实际步长；结构同时保存前一位移和速度。
FSI同时保存前一流体/ALE/结构速度、结构位移及刚体位置速度；ALE保存前一流体状态和网格位移。
事件处保存零有效历史步长，恢复后BE启动。积分器、事件列表与候选步长列表纳入状态签名；
旧BE checkpoint仅能以兼容BE配置恢复，不能静默作为BDF2完整历史。
恢复要求这些配置一致，不能静默替换未来候选步长列表。

## 稳定化与时间阶

原流体默认SUPG/PSPG系数依赖候选步长和accepted速度。改变dt会同时改变空间离散，
固定网格细步参考因此不能自动隔离纯时间误差；压力尤其明显。
可显式设置`fluid.stabilization_tau: 0.05`固定该系数（单位为时间/密度），
其值必须正且有限，并参与checkpoint签名。未设置时保留原BE默认行为。
固定tau不是通用推荐值，使用者需根据物理尺度与网格验证；本轮时间阶证据只针对固定tau。
FSI可使用同义的`fsi.stabilization_tau`；ALE解析均匀流保持测试的强残量为零，不依赖固定tau选择。
不将BDF2公式的二阶性质解释为默认步长相关稳定化下所有变量必然整体二阶。

`tests/verify_fluid_time.py`使用同一Tet4网格、固定tau、压力驱动瞬态，分别检验速度和压力；
`tests/verify_solid_time.py`使用同一Tet4卸载弹性体，检验位移、速度和加速度。
细步生产求解作为同一空间离散的参考，另有不等距二次多项式导数、解析指数衰减oracle。
这里隔离的是时间误差，不声称该粗网格已消除相对连续PDE的空间误差。
测试包括真实Newton拒绝后的历史恢复、事件处重启、末步、变步长和最多4rank对照。
事件测试只证明控制器命中与历史降阶，没有引入真实跳跃载荷；结构时间阶证据目前仅针对线弹性。

## 独立场generalized-alpha

```yaml
time:
  scheme: generalized_alpha
  rho_infinity: 0.5 # [0,1]，默认0.5
```

采用新时刻权重`x_f=(1-af)*x_n+af*x_(n+1)`。两类格式共有`af=1/(1+rho)`，
一阶`am=(3-rho)/(2*(1+rho))`，二阶`am=(2-rho)/(1+rho)`；
`gamma=1/2+am-af`，二阶还取`beta=(1+am-af)^2/4`。
这与项目使用版本的[PETSc3.23.7 alpha1](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ts/impls/implicit/alpha/alpha1.c)
及[alpha2](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ts/impls/implicit/alpha/alpha2.c)一致，
不能直接代入采用旧时刻权重的公式。

流体stage速度和压力为未知量；惯性系数`q=af*gamma*h/am`，
速度参考`v_ref=v_n+af*h*(1-gamma/am)*a_n`。
结构stage位移为`d_ref+(beta*h/gamma)*v_f`，其中
`d_ref=d_n+h*(af-beta/gamma)*v_n+af*h²*(1/2-beta/gamma)*a_n`。
质量链系数为1/q，材料刚度链系数为beta*h/gamma，两者显式分离。
端点状态由stage反解，算法导数按当前gamma更新；checkpoint保存这些算法历史及rho。

流体Dirichlet使用端点边界值的af插值，保证恢复出的端点满足边界；自然载荷在`t_n+af*h`评价。
压力与速度均在共同stage进入残量，输出为端点压力；均压归一化的stage反力修正同时乘af。
所有物理残量验收针对该格式的stage方程。流体输出`stage_momentum_residual`明确标记stage量，
不能当作端点瞬时反力；日志同时记录`time`和`evaluation_time`。

首次及声明事件之后接受一个BE启动步，随后采用alpha。此启动策略与PETSc的两次半步
导数探测不同，不声称直接复用了TS启动实现。对于实际固定tau流体测试，rho=0/0.5/1的
早期与终点速度、端点压力均验证近二阶；rho=1的无衰减压力误差模态不能靠耗散掩盖。

结构checkpoint的acceleration保存算法历史；VTU额外输出`algorithmic_acceleration`。
VTU的`acceleration`则在当前卸载模型的最终accepted端点通过一致质量方程`M*a+f_int(d)=0`恢复，
因此不把算法加速度的一阶时间偏移解释为物理加速度。该恢复多一次质量求解，未作性能收益声明。
结构`momentum_residual`及反力摘要使用此端点方程残量，另外保留`stage_momentum_residual`；
不得将无外载恢复公式直接用于未来任意时变载荷模型。
无载线弹性振动中rho=1在BE启动后保持能量；rho较小的粗步测试显示更强数值阻尼。

原始一阶文献：[Jansen、Whiting、Hulbert 2000预印本](https://www.lncc.br/~alm/lncc/jmac/turbulencia/genalf.pdf)
§3式(23)、§4式(24)–(27)。原始二阶文献[Chung、Hulbert 1993](https://doi.org/10.1115/1.2900803)
的出版社全文本轮访问返回403，仅核实出版信息；参数实现以上述版本化官方源码和独立代数核对为据。
压力stage选择另核对[Liu等2020](https://arxiv.org/abs/2002.01098)的两种压力评价比较；
其高阶稳定空间的结果不能替代本项目P1稳定化与启动的实际验收。

## BDF2 的单体FSI与ALE

`reduced.slot`的位移试探列系数由实际dt替换为q；lifting由当前时间参考位移给出。
结构、刚体与网格速度采用同一q和相容历史，因此界面处网格速度等于共享结构速度。
测试行仍按原物理方程合并，不将位移列系数误乘入界面反力。
输出`interface_power`与`body_power`为共享接口各分量残量与离散接口速度的内积，
`power_balance`为两者之差；这衡量离散界面功率一致性，不等于连续时间积分能量守恒。

`verify_domains.py --scheme bdf2`覆盖压力/位移/速度重启及MPI、整体有限差分Jacobian和功率。
`verify_fsi_time.py`分别验证弹性和刚体单体FSI的速度、压力与网格位移时间阶，
并检查变步长及启动后的非线性拒绝轨迹。`verify_ale_time.py`检查真实移动网格上的
均匀流与剪切流保持、解析正弦网格速度的时间阶和完整历史重启。

## generalized-alpha 的单体FSI与ALE

流体采用一阶参数，结构及刚体采用二阶参数，统一使用同一rho和af。
共同stage上的压力、几何、速度与接口力进入同一个Newton残量；
流体惯性链为1/q_fluid，结构/刚体惯性链为1/q_solid，
网格运动、界面位移lifting和结构材料链为beta*h/gamma。
共享物理速度不意味着共享算法加速度：流体、结构/刚体、网格分别保存其算法历史。
接口网格速度直接采用共享速度未知量，避免极小重试步从位移反算产生额外消减误差。

FSI输出端点速度、压力、位移和网格速度；额外的algorithmic_acceleration字段是算法历史，
不宣称等于端点连续物理加速度。日志stage_fluid_force、stage_body_balance及stage_*power
均为共同stage量；time为端点，evaluation_time为残量评价时刻。
端点几何独立于stage检查：仅stage有效不足以提交；任一rank发现端点反转时共同拒绝，
accepted未知量、算法历史和checkpoint均不更新。
ALE给定位移在端点满足解析运动，stage取端点插值；初始网格速度由解析运动导数延拓。

实际时间验收在同一空间离散上与细步BDF2参考比较，rho=0/0.5/1均覆盖弹性及刚体FSI；
速度、压力、位移随加密趋近二阶。该证据不构成任意非线性FSI的稳定性定理。
事件处恢复后BE重新启动，变步长及完整算法历史接受1/2/4 rank和重启对照。
ALE解析网格速度测试需解析启动瞬态，alpha使用h=1/16、1/32、1/64；
更粗rho=0.5样本有启动误差抵消，不能据其非渐近比率作时间阶结论。

## 当前支持矩阵与证据边界

| 模型 | BE | 变步BDF2 | generalized-alpha | 主要证据 |
|---|---|---|---|---|
| 独立瞬态流体 | 支持 | 支持 | 一阶系统 | 固定tau速度/压力时间阶、早期压力、MPI与重启 |
| 独立卸载结构 | 支持 | 支持 | 二阶系统 | 线弹性振动/能量/物理加速度阶；Neo-Hookean Jacobian与拒绝 |
| 给定运动ALE | 支持 | 支持 | 一阶流体/二阶运动学 | 均匀流/剪切流保持、解析网格速度、端点拒绝 |
| 单体刚体FSI | 支持 | 支持 | 一阶流体/二阶刚体 | 双向运动、压力/速度/位移时间阶、接口功率 |
| 单体弹性FSI | 支持 | 支持 | 一阶流体/二阶结构 | 共形双域、压力/速度/位移时间阶、完整J、接口运动与功率 |
| 独立刚体ODE演示 | 支持 | 明确拒绝 | 明确拒绝 | 原BE演示；不是单体刚体FSI |
| 稳态模型 | 不适用 | 明确拒绝 | 明确拒绝 | 不静默以BE替代所选高阶格式 |

所有并行时间证据最多4rank、同分区重启；未作跨分区checkpoint迁移。
FSI非线性材料有切线和拒绝测试，但时间阶表使用线弹性，不推广为任意大变形二阶证明。
ALE有真实端点反转负例；FSI的独立端点检查已审查但尚无直接反转负例。
公开接口稳定后的完整Debug/Release、兼容锁与云端回归以最终整合证据为准。
