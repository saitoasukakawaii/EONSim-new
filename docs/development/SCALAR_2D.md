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
