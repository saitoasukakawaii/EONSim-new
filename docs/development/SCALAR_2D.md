# 二维标量有限元

本增量提供平面 Tri3/P1、Quad4/Q1 及共边相容混合网格上的 Poisson 与瞬态扩散。
它不是二维流体、曲面 PDE、非匹配接口或三维混合体网格支持。验证最多 4 MPI rank。

## 方程与局部离散

求解 `capacity*u_dot - div(k*grad(u)) = source`；Poisson 删除时间项。
P1 使用参考三角形，Q1 使用参考正方形上的双线性几何和形函数；Quad4 不拆成三角形。
梯度和 Jacobian 在积分点评价。体积分使用四点 Gauss 的二维张量积，
Tri3 经过 Duffy 映射；边积分使用四点 Gauss。畸变 Q1 的刚度一般不是多项式，
该规则并不声称对任意畸变精确，实际加密与 patch 测试验证其误差。
平面双线性 Quad4 的 detJ 在参考坐标上为仿射函数，因此四角正值检查覆盖整个参考方形。

共享顶点只有一个 H1 标量 DoF；语义 space=2 表示该相容 P1/Q1 空间，
局部基函数由单元类型决定。owned/ghost、完整稀疏行图、AIJ 装配和约束消元复用既有代数层。
默认节点存储仍为 owner 连续、rank 内节点交错，没有实现新的全局内存排列。

## 运行一个混合网格算例

在已恢复的 PETSc/MPI 环境中：

```sh
python cases/scalar2d/generate.py build/scalar-example --n 8 --topology mixed --distorted
build/cloud-3.23.7-debug/eonsim -case build/scalar-example/case.json -prepare build/scalar-example/part -parts 4
mpiexec -n 4 build/cloud-3.23.7-debug/eonsim -case build/scalar-example/case.json -partition build/scalar-example/part
```

生成器支持 `--topology tri|quad|mixed`、`--version 2.2|4.1` 和 `--permuted`。
默认算例为非零 Dirichlet、Neumann、Robin 混合边界的仿射场 patch test。
一般用户问题可用下面配置替换生成目录内的 `case.json`（保存为同目录 `case.yaml`）：

```yaml
mesh: mesh.msh
output: diffusion.vtu
scalar2d:
  mode: diffusion # poisson 为稳态
  diffusivity: 1
  capacity: 1
  dt: 0.02
  steps: 10 # 终止时间=dt*steps
  source: 1
  initial: 2
  boundaries:
    - {region: left, type: neumann, value: 0}
    - {region: right, type: neumann, value: 0}
    - {region: bottom, type: neumann, value: 0}
    - {region: top, type: neumann, value: 0}
time:
  scheme: bdf2 # be / bdf2 / generalized_alpha
solver:
  relative_tolerance: 1.0e-11
  absolute_tolerance: 1.0e-12
```

该绝热单位方形问题有精确解 `u=2+t`，积分随时间增加 t。
`source`、`initial` 和一般边界 `value` 可为常数，或：

```yaml
value:
  polynomial: [1, 2, 3, 0, 0, 0]
  rate: -1
```

其含义为 `(c0+c1*x+c2*y+c3*x²+c4*x*y+c5*y²)*exp(rate*t)`。
当前没有任意表达式解释器。区域系数可用 `regions: {domain: 1, '20': 2}` 指定；
键为二维 physical name 或正整数 tag，未列出的区域采用 diffusivity。capacity 当前为统一常数。

## 边界与零空间

`region` 是一维 physical name 或正整数 tag。每个外边必须显式配置：

- `dirichlet`：`u=value`，支持非零消元；交角处冲突值明确拒绝。
- `neumann`：`k*grad(u).n=value`，n 为外法向。
- `robin`：`k*grad(u).n+coefficient*u=value`，coefficient 必须正且有限。

注意这里 Neumann 的 value 是扩散算子使用的外向梯度通量；若将物理扩散通量定义为
`j=-k*grad(u)`，则 `j.n=-value`。
纯 Neumann Poisson 检查离散 `integral(source)+integral(value)=0`，
相容性门槛为 `1e-11*max(1,||assembled_rhs||_1)`；不相容载荷报错。
随后设置 PETSc 常数零空间，仅去除门槛内舍入分量，并将最终解归一为物理体积零均值。
为确保该单一零空间的含义，本实现明确拒绝不连通域；没有逐分量零空间功能。
瞬态质量矩阵约束常数模态，不施加稳态均值归一化。

## Gmsh 规范化与支持子集

文件适配器先生成无 DoF、无 MPI 所有权的 MeshImportData，再进行拓扑/几何/求解能力校验。
外部节点和单元 ID 保留，连接转为本地索引；非连续 ID 和记录顺序不影响物理解。
坐标始终三分量，拓扑维数独立；二维域当前必须位于同一常 z 的 XY 平面。
顺时针 Tri3/Quad4 规范化为逆时针，边界连接依照邻接单元定向，外法向为 `(dy,-dx)/length`。
检查重复顶点/单元、非流形边、外边标记完整性、连通性、退化和反转。
不提供任意几何重叠/自交网格的全局交叉检测，也不自动修补悬挂节点。

支持 Gmsh 2.2 与 4.1 ASCII、data-size=8；4.1 读取 Entities、PhysicalNames、Nodes 和 Elements。
4.1 实体的 physical groups 在规范化层完整保留；当前求解适配器要求每个域单元和外边
恰有一个正 physical group，多组归属明确拒绝。未使用的合法 0–3 维名称保留于分区文件。
拒绝二进制、4.0、参数化节点、周期、Gmsh 自带分区/ghost、高阶以及未支持拓扑。
2.2 仅接受最多两个单元 tags，额外分区 tags 不静默丢弃。

三维仍为原 Tet4 路径，现在也可由规范化 4.1 ASCII 输入；不增加 Hex/Prism/Pyramid 支持。
二维分区为 HDF5 元数据版本 3，三维保留版本 2，并能读取无新增名称/连接偏移数据集的旧 Tet4 文件。
二维文件不能交给旧三维求解器；入口检查物理模型与分区拓扑维数。

## 时间、重启与输出

复用 [G5 时间映射](TIME_INTEGRATION.md)：BE、实际历史步长 BDF2、
一阶 generalized-alpha；alpha 的 stage 标量为独立未知量，端点值和算法导数分别恢复。
Dirichlet 按端点值插值，源项及自然边界在共同 stage 评价；拒绝不提交历史。
checkpoint 保存格式所需完整历史、步长/ready、参数及二维拓扑/所有权签名。
缺字段、改变格式/物理参数/网格或不同分区明确拒绝，不静默改用 BE。
瞬态标量捕获 `LinearSolveFailure` 后由 TimeStepper 按配置有限缩步；稳态直接报错。输入、I/O 等普通异常不因此重试。这与三维非线性驱动将线性/PC 故障作为终止错误的策略不同。

每个接受步写 VTU（Tri=5、Quad=9、边=3）、并行 PVTU 及 PVD 时间序列。
`output.vtu` 为最终接受状态；`output_stepN.*` 为当前运行的各步。
恢复时新序列使用 `output_restartK.pvd` 及同前缀时间片，K 为 checkpoint 步号，
原 PVD 和原时间片不覆盖；`output.vtu` 更新为本次最新状态。
同一个 checkpoint 重复恢复到同一输出前缀会替换同名 restartK 片段；如需保留多条分支轨迹，
使用不同 `-output` 前缀。PVD 仅列本运行接受的步，不虚构未写出的初态/拒绝步。

`stage_boundary_flux` 独立积分有限元梯度；`stage_flux_balance` 为
`integral(capacity*u_dot)-integral(source)-integral(k*grad(u).n)`。
连续 Galerkin 单元梯度通量不保证有限网格上局部守恒，非仿射解的该差值应随加密收敛，
不能把装配残量恒等式当独立通量证据。`l2_error/h1_error` 仅在 manufactured 模式输出。

## 验证入口

`verify_element2d` 对照独立解析质量/刚度矩阵并检查 Gauss 点不足以发现的角点反转。
`mesh_import_verification` 验证坏格式拒绝及 2.2/4.1 Tet4 的 1/2/4 rank 等价。
`scalar2d_space` 验证仿射 patch、畸变混合网格、空间加密、边界通量、纯 Neumann、双材料及并行。
`scalar2d_time` 验证三格式时间阶、事件/完整历史重启、绝热积分守恒及输出。
`scalar2d_failure` 验证真实 KSP 失败、accepted/checkpoint 不污染、缩步重放和旧 PVD/时间片保留。
最终 Debug/Release 与兼容锁结果记录于 [集成验证](FEM_INTEGRATION_VALIDATION.md)，
不将可编译接口或小型参考模型替代这些真实 PETSc/MPI 证据。


## P2 稳态三角形增量（FEM-G2A）

配置 `scalar2d.degree: 2` 选择直边 Tri3 上的二次 Lagrange 场；默认 1 保留 P1/Q1。当前支持统一扩散系数的稳态 Poisson 与瞬态扩散、Dirichlet、Neumann 与正系数 Robin。regions 及 Quad4/混合网格明确拒绝。几何仍为三顶点，场具有三个顶点和三个边中点 DoF，不支持高阶 Gmsh 几何输入。

沿用 `-prepare <目录> -parts 2` 和 `-partition <目录>`；准备时必须使用同一份 degree=2 配置。分区 HDF5 保留原几何格式，新增版本 1 的 scalar_p2 组；旧 P1 分区不能直接作 P2 求解，需重新 prepare。串行无 partition 入口使用同一空间构造。

边身份由排序后的原始端点 ID 对定义；owner 为邻接单元 owner 的最小值。求解只读取本 rank 数据，owned 行图包含远程单元贡献。P2 语义 space=3，vertex/edge 与代数编号分离。输出采用六节点二次三角形 VTU/PVTU，PointData 的 entity_first/entity_second 为 Int64 身份端点，顶点两个端点相同，另提供 owner 与 u；不把中点称为导入网格节点。

源码检查点 edfc73c，本地 Debug PETSc 3.23.7 实际 1/2 rank patch 与正弦加密通过；最细 L2/H1 阶为 2.9699/1.9711。证据见 ../research/data/p2-2026-11-01/。云端与主线合并状态以任务队列为准。本轮不构成完整 G2 或性能验证。

### FEM-G2B 边界扩展

Robin 使用同一约定 `k grad(u).n + coefficient*u = value`，coefficient 必须有限且正；三节点二次边迹同时生成载荷与对称边界矩阵。全 Robin 问题不要求额外 Dirichlet。

所有边界均为 Neumann 时，先检查离散载荷相容性，再复用 PETSc 常数零空间；不固定任意节点，不修补超出相容性容差的载荷。求解后按实际 FE 体积积分去除常数，制造解也使用相同的物理零均值规范进行误差比较。P2 三角形顶点形函数的积分为零，不能用节点算术平均代替体积平均。已有限制为单个连通域；不增加多分量零空间。

实现 d6ec424，本地 Debug PETSc 3.23.7 的 scalar_p2_verification 通过，包含 1/2 rank 全 Robin、纯 Neumann、显式用户载荷与不相容载荷拒绝；云端与合并状态见队列。证据位于 ../research/data/p2-boundaries-2026-11-01/。


### FEM-G2C：P2 瞬态扩散

`degree: 2`、`mode: diffusion` 采用一致质量矩阵，支持 BE、变步 BDF2 和一阶 generalized-alpha。
几何、分区和边空间沿用 G2A；capacity 与 diffusivity 为正的统一常数。将上文绝热算例的
网格生成为 `--topology tri` 并添加 `degree: 2`，重新 prepare 后即可运行；边界、初态和源项
继续使用现有 polynomial/rate 数据格式。

BDF2 保存前一接受状态与实际步长；alpha 保存算法导数与 ready 标志。首步和事件后的第一步
使用 BE，后续按选定格式推进。alpha 的源项/自然边界在共同 stage 评价，Dirichlet 使用端点
数据的 alpha_f 插值，使恢复的端点满足边界值。`algorithmic_rate` 是算法历史，不等同于精确物理导数。

checkpoint 使用既有 v3 generation 发布协议，增加 P2 空间的整数实体身份、代数编号、owner、
连接及边界标签签名。恢复要求同 rank、同分区、同时间格式和物理数据；缺失/非法历史及空间错配
明确拒绝。线性数值失败按 time_control 有限缩步，重试不推进 accepted 历史；输入与 I/O 错误终止。
瞬态全 Neumann 问题由质量项约束常数模态，保留真实均值，不使用稳态零均值归一化。

每步输出六节点二次三角形 VTU/PVTU；PVD 只登记已接受且写入完成的时间片。
重启序列为 `solution_restartK.pvd` 和相同前缀的时间片，保留原序列；重复从相同 K 恢复到
同一输出前缀仍会替换该恢复分支，保留多个分支时应使用不同 `-output`。分片、索引与 PVD
写入错误集体传播，失败不发布新的全局索引；临时文件可能保留，不承诺整个输出目录的事务回滚。

日志报告端点 time、evaluation_time、accepted_dt、time_order 和物理积分；P2 当前未提供
P1/Q1 的 stage_boundary_flux/stage_flux_balance 诊断，不能据日志字段类比推断已有该功能。

源码 d19a03268577b33ddfb41177037d9bbc1f76d273；本地 PETSc 3.23.7 Debug 分项检查、Release 五项相关检查及 1/2 rank 验证通过。
时间阶使用可精确表示的二次空间制造解：最细级 BE 0.988、BDF2 2.157、alpha（rho=0/0.5/1）
2.157/2.006/1.997；变步 BDF2 另有加密检查。8 项双 rank HDF5 历史/空间故障补验通过。
原始结果、实际命令与 dirty/提交对应关系见 [G2C 证据](../research/data/p2-transient-2026-11-03/source.json)。
没有全量、PETSc 3.19.6、超过 2 rank 的新验收或性能测量。PR 云端验收另记，不把本地证据标为云端结果。


G2C 云端补验：[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 的
[run 41582475827](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41582475827)
在 merge preview b8c1642 上通过 Debug/Release 各 15/15 相关检查；
[精简证据](../research/data/p2-transient-2026-11-03/cloud.json)。PR 尚未合并。
