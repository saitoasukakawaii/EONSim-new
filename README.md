# EONSim

C++17 / PETSc 多物理场求解器，包含独立流体、独立固体、单体刚体 FSI 和单体弹性 FSI 的可运行基线。
使用 Tet4 多物理场、Tri3/Quad4 二维标量、MPI owned/ghost 分区、METIS/HDF5 预处理和 PETSc KSP/SNES。
时间格式包含BE、变步BDF2及适用的一阶/二阶generalized-alpha；具体支持矩阵见[时间离散](docs/development/TIME_INTEGRATION.md)。
有限变形固体支持可压缩 Neo-Hookean；耦合流体、结构/刚体和 ALE 同时收敛后提交状态。

当前验证包括随仓库提供的立方体/旋转通道、弹性块和活塞算例；流体/固体支持区域材料与分量约束，弹性 FSI 支持独立共形双网格。尚不包含通用表达式、非匹配界面、重网格或大规模扩展性保证。
各阶段的实际结果与限制见下文及 [开发路线](docs/development/ROADMAP.md)。

2026-10-30 新增 [通用 FEM 架构规划](docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) 与
[20 组上游学习矩阵](docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md)，覆盖多拓扑/空间、边界与非匹配接口、时间格式、DoF/预条件及并行输出。它们提供总体路线；本次G0/G5/G1实现范围见[集成验证](docs/development/FEM_INTEGRATION_VALIDATION.md)，其他阶段不随之完成。

2026-10-31：G0B/G0/G5/G1 已通过 PR #23 合入 main；主锁 Debug/Release 各 60 项及旧锁专项 13 项是该检查点的通过记录，后续运行应读取实际 inventory。PR #24 已将日常 CI 固定为 PETSc 3.23.7 Debug/Release；后续增量 CI 按 PR 改动选测、复用同 PR 成功证据，数值 Push 触发移除，详见[构建与验证](docs/development/BUILD_AND_VALIDATION.md)。下文 P/B 阶段数值与环境保留历史口径，不代表本次重新测试。

## 新增能力与说明

- [DoF语义与三种预条件分组](docs/development/DOF_AND_PC_GROUPING.md)：物理验收字段与PC分组分开，默认存储不变。
- [时间离散、支持矩阵与checkpoint迁移](docs/development/TIME_INTEGRATION.md)：共同stage的单体FSI、完整accepted历史、失败重试。
- [二维Poisson/扩散](docs/development/SCALAR_2D.md)：Tri3、原生Quad4、相容混合网格，命名边界/材料、Neumann零空间、MPI与PVD输出。

## 环境与构建

需要 CMake ≥ 3.21、Ninja、C/C++17 编译器、实数双精度 PETSc、匹配的 MPI、
BLAS/LAPACK、METIS、HDF5 和 yaml-cpp（当前验证版本 0.8.0）。运行已保存的算例不需要 Gmsh 或 Python；
重新生成网格及可选验证脚本需要 Python 3。

云端主验证环境固定PETSc 3.23.7、OpenMPI 5.0.8及GCC15.3，另保留PETSc3.19.6手动故障兼容专项，不进入日常CI。
完整版本/来源见[依赖锁](environments/README.md)，干净恢复及证据查看见[构建与验证](docs/development/BUILD_AND_VALIDATION.md)。

```bash
scripts/cloud/restore.sh 3.23.7
scripts/cloud/run.sh 3.23.7 debug core
scripts/cloud/run.sh 3.23.7 release core
```

已有匹配依赖的手工环境仍可使用原presets（编译并行度按实际CPU/内存配额设置）：

```bash
cmake --preset debug
cmake --build --preset debug --parallel 2
cmake --preset release
cmake --build --preset release --parallel 2
./build/release/eonsim -case cases/poisson/case.yaml
```

预设生成 `build/debug` 和 `build/release`。Debug 设置 `MHPC_DEBUG=1`，Release 设置为 `0`；
两者使用相同方程、约束和停止准则。输入/几何有效性、非有限值、KSP 不收敛和真实残量检查
在 Release 中保留。应用默认将尚未设置的 `OMP_NUM_THREADS`、`OPENBLAS_NUM_THREADS`、
`MKL_NUM_THREADS` 设为 `1`，已有环境设置会保留并在摘要中显示。

P0–B5 历史验证环境使用 GCC 13.3、PETSc 3.23.2（优化构建、实数双精度、32 位 PetscInt）、
OpenMPI 4.1.6、OpenBLAS 0.3.26。应用网格 ID 使用 64 位，进入 PETSc 前检查代数编号范围。
当时的 Debug 应用也链接这套优化 PETSc；它不等同于 PETSc 自身的调试构建。

## 算例与运行

`cases/poisson/case.yaml` 配置单位立方体上的问题：

```text
-div(k grad u) = f,   k = 2
u_exact = 1 + x + 2y + 3z + x² + 2y² + 3z²
f = -12k
全部外边界：u = u_exact
```

`exact_solution: affine` 可选择 `u_exact = 1+x+2y+3z`、`f=0`，用于 patch test。
这两种制造解是明确支持的配置，不提供运行时表达式语言。坐标采用 SI 单位，标量场为本阶段验证量。

默认网格包含 125 个节点、384 个正定向 Tet4、192 个边界三角形，存在 27 个自由内部未知量。
边界 physical tags `1..6` 分别为 `x_min/x_max/y_min/y_max/z_min/z_max`，体区域 tag 为 `10`。
支持 Gmsh **2.2/4.1 ASCII** 的明确子集，Tet4（type 4）和边界三角形（type 2）；一阶点/线实体可读但不参与体积分。
高阶单元、其他三维体单元、4.0/binary、参数化和分区Gmsh输入会明确拒绝。每个外表面必须有标签三角形，
当前制造解要求所有外表面均施加 Dirichlet 条件。

YAML 中的路径相对 YAML 文件；命令行覆盖路径相对当前目录：

```bash
./build/debug/eonsim -case cases/poisson/case.yaml -diagnostics full
./build/release/eonsim -case cases/poisson/case.yaml \
  -output results/custom/solution.vtu -ksp_rtol 1e-12
```

`-diagnostics full` 额外检查约束后矩阵的对称性。默认求解器为 CG/Jacobi；
`-ksp_*`、`-pc_*` 通过 PETSc options 覆盖默认设置。摘要显示实际求解器、容差、停止原因、
迭代数和真实残量 `||Au-b||₂`。收敛失败返回非零退出码，不输出新的结果文件。

输出文件可直接在 ParaView 打开：

- `results/poisson/solution.vtu`：Tet4 网格、`u`、`u_exact`、节点误差、原始 64 位 mesh ID 和体标签。
- `results/poisson/solution_boundary.vtu`：带 physical tags 的边界三角形及相同节点场。

节点误差与 FEM 场的 L2 误差不同：二次函数在 P1 单元内部仍有插值误差，即使某些节点值精确。
L2 和 H1 半范误差使用单元内积分计算；摘要还包含体积、解的积分以及输入、准备、装配、
求解、误差评价和输出耗时。该小算例的耗时不代表 HPC 性能结果。

## 验证与网格加密

```bash
cmake --preset debug -DBUILD_TESTING=ON
cmake --build --preset debug --parallel 2
ctest --preset debug
```

Release 同理使用 `release` preset。可选验证仅使用 Python 标准库，包含：

- 同一二次制造解的 `4³` / `8³` 立方网格，每个小立方体分成 6 个 Tet4；检查 L2 二阶、H1 半范一阶。
- 内部节点扰动后的仿射 patch test，检查非零 lifting、体积和解积分，以及大于 32 位的原始网格 ID。
- VTU 场和 physical tags；KSP 达到迭代上限、倒置单元的明确失败。

本机 Debug/Release 均通过，三种成功算例的节点解模式间最大差为 `0`：

| 算例 | Tet4 数 | L2 误差 | H1 半范误差 |
| --- | ---: | ---: | ---: |
| 二次制造解，4 等分 | 384 | 0.06488504793 | 0.5400617249 |
| 二次制造解，8 等分 | 3072 | 0.01622126198 | 0.2700308624 |
| 畸变网格仿射解，4 等分 | 384 | 1.06e-11 | 1.80e-10 |

默认算例真实残量约 `1.67e-14`，7 次 CG 迭代。验证日志、VTU 和 `metrics.json`
保存在对应构建目录的 `verification/`。P1 另验证真实的 1/2 rank 分布式对照，见下节。

重新生成加密网格：

```bash
python3 cases/poisson/generate_mesh.py --subdivisions 8 --output results/cube8.msh
./build/release/eonsim -case cases/poisson/case.yaml \
  -mesh results/cube8.msh -output results/poisson8/solution.vtu
```

## P1 分布式运行

预处理是单进程离线操作；METIS 按四面体共享面分区，每个 HDF5 文件保存本 rank 单元、
owned/ghost 节点、边界标签和 owned 行完整邻接。求解时不读取原始 Gmsh 文件，不收集全局场。

```bash
./build/release/eonsim -case cases/poisson/case.yaml -prepare results/partition2 -parts 2
/usr/bin/mpiexec -n 2 ./build/release/eonsim -case cases/poisson/case.yaml \
  -partition results/partition2 -output results/poisson2/solution.vtu
```

`solution.pvtu` 引用各 rank 的 VTU；边界有独立 `solution_boundary.pvtu`。
本机两个分区含 188/196 个单元，owned 节点 74/51，ghost 节点 0/25，全局仅 125 个节点。
标量仍采用相同局部核；PETSc 完成远程装配累加及解的 owner→ghost 同步。
`poisson_parallel` 自动检查 1/2 rank 解与积分（容差 1e-10）、PVTU、field IS 和分区缺失的失败退出。
预处理新增依赖 METIS/HDF5，优先复用当前 PETSc 安装中的头文件和库，避免混合 HDF5 ABI。

## 依赖与代码结构

项目继续使用现有 `cmake` 模块：

| 模块 | 用途 | 目标 |
| --- | --- | --- |
| `EONSimBlasLapackProvider.cmake` | 选择 BLAS/LAPACK，默认 AUTO | `EONSimBLAS::BLASLAPACK` |
| `EONSimPETScProvider.cmake` | 使用 CMake 配置包或 pkg-config 查找 PETSc | `PETSc::PETSc` |
| `FindMPI.cmake` | MPI C/C++ 探测；Linux 转交 CMake 实现 | `MPI::MPI_C`、`MPI::MPI_CXX` |

Poisson 应用现在必须有 PETSc；`OFF` 或 `AUTO` 未找到时配置失败，不再构建无求解能力的 Hello 程序。
Provider 自动读取 `PETSC_DIR`、`PETSC_ARCH`；也可用 `EONSIM_PETSC_ROOT`、
`EONSIM_PETSC_ARCH`、`EONSIM_PETSC_PKG_CONFIG_PATH` 覆盖提示。环境中的 `PETSC_ARCH`
在显式架构为空时仍会被 Provider 采用；切换到无架构安装前缀时，需同时取消该环境变量。

BLAS 可显式设置 `-DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS|SYSTEM|MKL|BLIS_FLAME|ACCELERATE`。
此选项控制 EONSim 直接依赖，已安装 PETSc 自身使用的 BLAS 不会随之改变。
机器路径用本地命令或忽略的 `CMakeUserPresets.json` 设置。历史本地环境曾在 PATH 中混入 ParaView 的 MPICH 启动器；本项目验证使用 OpenMPI。手工环境可通过 `-DMPIEXEC_EXECUTABLE=/usr/bin/mpiexec`
设置匹配的启动器，多 rank 求解必须传入匹配的分区目录。

```text
include/eonsim/       配置、网格、有限元、DoF/PC、时间积分与求解接口
src/core/            YAML 解析与强类型配置
src/mesh/            Gmsh 输入、拓扑/标签检查
src/fem/             Tet4/Tri3/Quad4 几何、场布局、有效编号与界面消元
src/algebra/         PETSc 生命周期、装配、约束、KSP/SNES 与分块求解
src/physics/         Poisson、二维标量扩散、流体/固体、刚体、ALE 与单体 FSI
src/io/              VTU/PVTU、二维 PVD 序列、accepted 历史 HDF5 checkpoint
src/main.cpp         初始化、配置、运行与摘要
cases/               poisson/scalar2d/fluid/solid/motion/fsi 可运行 YAML 和网格
```

一个 `eonsim_core` library 和一个 `eonsim` 应用；所有模式通过 `-case` 选择。
设计约束入口为 [AGENTS.md](AGENTS.md) 与 [总原则](MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md)。

## 非线性字段验收

独立流体/固体、ALE 流体及单体 FSI 在返回接受状态前，逐字段检查非约束方程行的残量，
并单独检查 Dirichlet 替换行的约束误差。显式配置示例见 `cases/fsi/domains/case.yaml`：

```yaml
solver:
  relative_tolerance: 1e-10
  absolute_tolerance: 1e-12
  maximum_iterations: 30
  fields:
    velocity:  {residual_scale: 1}
    pressure:  {residual_scale: 0.01}
    mesh:      {residual_scale: 0.01}
    structure: {residual_scale: 1}
```

`residual_scale` 是**已装配方程行**的尺度：本双域例的动量取 1 N、连续性取 0.01 m³/s、
人工网格取 0.01 m²；`pressure` 的尺度不是压力未知量的 Pa。尺度由算例确定，不自动推断。
每字段还可指定 `absolute_tolerance`、`relative_tolerance`、`constraint_scale` 和 `constraint_tolerance`。
物理方程按 `rms(R/residual_scale) <= atol + rtol*initial_rms` 接受；约束按
`max(abs(x-prescribed)/constraint_scale) <= constraint_tolerance` 接受，原始反力不参与这两个范数。
初始范数取本次求解施加边界值后的状态；缩步、重启后的新求解重新计算。

`solver.fields` 非空时必须覆盖实际非线性字段，遗漏或未知名称报错；省略时各尺度为 1，
物理容差及约束绝对容差继承外层 solver。字段内未写的物理容差也继承外层；
`constraint_scale` 默认 1，`constraint_tolerance` 默认外层绝对容差，`relative_tolerance` 可为 0。
独立流体为 velocity/pressure，独立固体为 structure，FSI 再含 mesh 和 structure 或 rigid。
显式配置会输出每字段的行数、初始/最终范数、阈值和接受状态；默认配置可用 `-solver_report` 查看。

独立流体入口可显式启用 `-fluid_element_report`，按 rank/步输出单元 kernel 与 Vec/Mat 插入时间及残量/Jacobian 单元计数；默认关闭。它包含最终验收/反力回调，与 `solver_report` 的累计区间不同，不能直接相减。详见[计时契约](docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。

`-linear_report` 额外重新计算每次顶层线性求解的 `A*x-b`，输出原始 L2 范数、逐字段缩放 RMS 和约束最大值，并启用 `-solver_report`。该诊断增加 MatMult 和全局规约，不改变收敛条件；未收敛或开启 PETSc 对角缩放时明确报告不可用。阶段计时区分初始化、显式 Schur 配置、顶层 KSP、额外线性诊断和最终验收；计时存在嵌套，不能相加作为总耗时。

`-solver_report` 还输出按 rank 排列的 `solver_node`：可定位 FieldSplit、ASM/BJacobi 和 GAMG 粗层/下平滑器的 options prefix、KSP/PC 原因及最后一次迭代数。主 KSP 未收敛时本地输出原因树并抛出带 rank/phase/reason 的异常；失败诊断不新增 collective；即使只有一个 rank 的局部 LU 零主元，也保留具体原因。`reported_norm` 是 PETSc 记录值，`norm_type=0` 时没有范数判据，不能把零值当作物理块残量已收敛；完整含义与遍历范围见[离散与算子契约](docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md#求解-operator-与预条件器各有职责)。

默认 SNES 收敛回调要求 PETSc 默认停止条件和字段条件均通过。PETSc options 可以替换回调，
但任何正停止原因仍须通过最终重新装配后的字段验收；失败进入既有有限缩步流程，不能提交状态。
当前尺度用于接受检查，尚未对 Newton 方程、未知量或线搜索实施对角缩放，也不保证网格无关误差。

## P2 独立流体

固定网格独立流体可用 `-fluid_coo` 选择缓存 COO Jacobian 装配：

```bash
./build/release/eonsim -case cases/fluid/transient.yaml -fluid_coo -solver_report
```

默认仍逐单元调用 `MatSetValues`。COO 在每个 `NonlinearSystem` 生命周期开始时准备一次
本地单元贡献图，后续 Newton、时间步及重试只更新数值；PETSc 汇总重复坐标和远程行贡献。
残量、边界载荷、约束、字段验收及原始反力使用原路径。此选项仅用于独立固定网格流体，
FSI、给定运动 ALE 和其它物理入口会明确拒绝。两种装配方式可交换同分区 checkpoint。

每 rank 的 `fluid_coo_plan` 报告贡献条目、持久数值缓冲字节数及一次性准备耗时；
`value_bytes` 不含 PETSc 内部图/通信缓存及准备阶段的临时索引数组。该路径需要额外内存，
是否更快取决于规模、分区和后端；[HPC-02 记录](docs/research/FLUID_COO_ASSEMBLY_2026-10-30.md)
给出实际验证、配对测量与限制，不承诺 GPU 或大规模扩展性。

`cases/fluid/{stokes,steady,transient,traction}.yaml` 可直接通过 `-case` 运行；
MPI 运行复用 P1 的 `-prepare` / `-partition`。速度/压力节点交错，
SNES + SuperLU_DIST 为当前小算例基线，PETSc `-snes_*`、`-ksp_*`、`-pc_*` 可覆盖默认值。

单位立方体的平面 Poiseuille 基准：x 方向流动、y 无滑移、z 对称。
默认两端给定抛物线速度并在原点固定压力；`outlet: traction` 改用出口解析牵引并取消压力点约束。
参考解 `u_x=pressure_drop*y*(1-y)/(2*viscosity)`。
四点 Tet4 积分用于 SUPG/PSPG 残量与解析切线；tau 由上一步 accepted 速度与当前 dt 冻结，
整个 Newton 求解中保持不变，稳态初值为零。BE 每步收敛后才提交速度历史。

VTU 包含 velocity、pressure 和约束替换前的 momentum_residual；后者为离散节点动量残量，
不是逐点 Cauchy 应力，只有受约束分量应解释为支座/壁面反力。
固定几何核接收独立网格速度输入；尚未把这一步报告为 ALE 或 FSI。

实际验证：Debug/Release 三模式 1/2 rank 节点结果差小于 2e-10；
局部解析 Jv 相对误差小于 5e-11；强制 SNES 不收敛正确失败退出。
4³→8³ 网格 Stokes 速度 L2 四点积分估计 0.01421→0.004598，散度 0.03225→0.01260，
压降 0.5022→0.7641（参考值 1）。粗网格压降仍偏低，不能作为高精度流动基准。
瞬态 tau 含 dt，因此其长时间离散平衡与稳态 tau 的平衡并不完全相同；
测试将 BE 第 10/20 步相比较，不把这种空间稳定化差异误报为时间推进失败。

## P3 独立线弹性

运行 `-case cases/solid/static.yaml` 或 `-case cases/solid/unload.yaml`。
单位块 x=0/y=0/z=0 各约束对应法向位移，其余切向分量自由；x=1 施加参考面均布牵引。
这是可解析的单轴拉伸验证，不是悬臂全夹持边界。
静力未知量为位移；撤载模式先求静载位移，再从零速度开始 BE，
`d=d_n+dt*v`，使用一致质量矩阵。无材料阻尼。
输出 displacement、velocity、acceleration、约束替换前 momentum_residual。

E=100、nu=0.3、牵引=1 时，静载 x 端位移 0.01、反力 -1、应变能 0.005，
位移最大误差约 3e-17。撤载 dt=0.01、20 步后端位移 -0.00589688，
总能量从 0.005 单调降至 0.00270248；这一衰减包含 BE 算法耗散。
Debug/Release 材料与 BE 链式 Jv、刚体平移、静载/撤载 1/2 rank 对照通过。

## P4 刚体与给定运动 ALE

`cases/motion/rigid.yaml` 输出单轴刚体 BE 时间历程；质量/阻尼/弹簧/外力可配置。
`uniform.yaml` 固定外边界、驱动中心网格节点，由向量 Laplace 扩展内部位移；
在移动网格上保持常量速度。`shear.yaml` 使上壁以恒速沿 x 运动、底壁静止，
侧边给兼容解析速度与位移，检查 `u_x=V*y`、`d_m,x=V*t*y`。
当前几何、网格速度与流体速度/压力写入 VTU；流体收敛后才接受时间历史。

实际 Debug/Release、1/2 rank：5 步非零网格运动的速度误差为零（到输出精度），
剪切网格位移最大误差小于 1e-15；内部网格大幅运动导致反转正确失败退出。
均匀流测试针对当前非守恒 advective ALE 的常量保持，不等同于高阶守恒几何定律证明。
刚体 ODE 与 ALE 在本阶段独立运行，尚不构成双向 FSI。

## P5 单体刚体 FSI

`cases/fsi/rigid.yaml`：单位截面流体活塞，x=0 给压力，x=1 为弹簧/阻尼/质量活塞，
y/z 壁面无穿透、切向自由。活塞速度和位置由流体力驱动，不是给定轨迹。
流体、刚体速度和网格内部位移使用同一 SNES；界面速度直接映射到刚体速度，
网格界面位移为 `q_n+dt*V`，压力规范来自入口牵引。
网格平滑残量不进入刚体动量；流体力使用施加约束前的界面动量残量。

首版用局部中心差分验证了完整耦合切线；B5 已改为解析几何导数与固定宽度前向链式传播，
包括几何、当前面积、网格速度及全部跨场块。`-fsi_fd_tangent` 保留原差分对照路径。
27 节点/48 四面体，dt=0.02，5 步后位移 0.00198413352、速度 0.03297023486、
流体力 0.67283868180。独立参考 `(m+rho*(1+q))*a+c*V+k*q=P` 与离散结果吻合。
Debug/Release 的 1/2 rank、局部/总系统导数、零压力无运动和动量平衡检查通过。

## P6 单体弹性 FSI

`cases/fsi/elastic.yaml` 在流体 x=1 处连接厚 0.25 的弹性块，固体背面固定、
y/z 侧面滚动约束。两域采用匹配的逻辑网格，固体物理参考 x=1+thickness*(1-X)，
因此界面共形；此旧入口保留作回归。B3 的 `fsi.domains` 可导入独立共形双网格，见下文。
独立固体单元直接复用于同一 FSI SNES。
界面流体速度与结构速度共享有效编号，网格界面位移按当前积分格式从结构运动学恢复，默认BE。
输出主 VTU 为流体当前网格，伴随 `_solid.vtu` 为固体当前网格，均包含位移/速度。

E=100、nu=.3、入口压力 1：dt=.02 的 10 步后界面平均位移 0.00223293，
最大瞬态位移约 0.00282，界面力平衡误差约 1e-12。
1D 动态模型只作近似参考（3D Tet4 存在其未描述的横向自由度），静态解析位移
`P*thickness/(lambda+2*mu)=0.001857142857` 则在 200 步后以 1e-8 误差阈值验证。
Debug/Release 的共享界面几何/速度、全局 Jacobian、1/2 rank、零压力与刚体回归通过。

## P7 有限变形 Neo-Hookean

独立入口 `cases/solid/hyperelastic.yaml`，耦合入口 `cases/fsi/hyperelastic.yaml`。
选择 `material: neo_hookean`，使用可压缩能量
`W=mu/2*(tr(F^T*F)-3)-mu*ln(J)+lambda/2*ln(J)^2`；
局部 P、dP/dF 为解析公式，BE 切线包括位移对速度的 dt 系数。
Cauchy 应力按 `sigma=P*F^T/J` 映射，测试同时核对 Nanson 面积牵引关系。
材料切线为解析；FSI 流体几何块现采用 B5 的解析几何与前向链式切线。

独立牵引 20、E=100、nu=.3 时，轴向/横向伸长比 1.2329893744/0.9376077659，
反力 -20；静态与撤载、刚体旋转、能量导数、材料/BE 切线均验证。
同一弹性 FSI 将压力提高到 20，界面最大位移约 0.04728（厚度的 19%）。
0.2 秒位移：2³ 网格/dt=.02 为 0.03299019，4³ 网格为 0.03299158，
dt=.01 为 0.02840273；同载荷线弹性为 0.04579049。
网格差异小，但时间步影响仍明显，当前结果不能称为时间步收敛解。
Debug/Release、1/2 rank、全局 Jacobian 和界面力平衡检查通过。

## P8 分块求解与 checkpoint

四种入口分别为 `cases/fluid/transient.yaml`、`cases/solid/unload.yaml`、
`cases/fsi/rigid.yaml`、`cases/fsi/elastic.yaml`（有限变形用 `hyperelastic.yaml`）。
增加 `-block_pc` 使用 FGMRES 和乘法 field-split：速度/压力合为 flow，
内部网格为 mesh，刚体或结构为 rigid/structure。各分布式块用 ASM＋局部 ILU，
单自由度刚体块用 Jacobi。保留完整耦合 Jacobian，未改变物理方程和 SNES 容差。
不加该选项仍使用单个 SuperLU_DIST 直接解作为小算例基线。

```bash
./build/release/eonsim -case cases/fsi/hyperelastic.yaml -prepare results/part2 -parts 2
/usr/bin/mpiexec -n 2 ./build/release/eonsim -case cases/fsi/hyperelastic.yaml \
  -partition results/part2 -block_pc -solver_report \
  -checkpoint results/checkpoint2 -stop_after 3 -output results/partial.vtu
/usr/bin/mpiexec -n 2 ./build/release/eonsim -case cases/fsi/hyperelastic.yaml \
  -partition results/part2 -block_pc -restart results/checkpoint2 -output results/resumed.vtu
```

每步整体接受后写独立 `generation_*` 目录中的本 rank HDF5，全部文件 flush/close 成功后
写该代 manifest，最后以同目录 rename 替换根目录 `current` 指针。发布失败保留上一完整代；
不扫描或自动选用未发布目录。`-restart` 可以指定检查点根目录，也可以指定某个完整 generation。
当前格式为 v3，旧 v1/v2 文件明确拒绝。保留全部历史代及失败遗留目录，暂不自动清理；
同一根目录只允许一个写入作业，重启时需读取稳定指针或显式代目录。
这里保证进程/I/O 失败下的发布顺序，尚未实现文件系统断电持久性协议。
恢复要求相同 rank 数、网格/分区、物理参数和 dt；可以延长总步数或更换求解器选项。
流体保存 accepted 场；固体保存位移/速度/加速度与能量；FSI 还保存有效未知量、
原始物理场、固体位移、刚体位置/速度和网格历史；BDF2与generalized-alpha保存各自完整历史，
格式/启动/事件及兼容规则见[时间离散](docs/development/TIME_INTEGRATION.md)。无额外不可逆材料内部变量。
缺失文件、参数/分区不匹配或非有限字段会失败退出；不支持跨 rank 重分区恢复。
`-stop_after N` 按累计 accepted 步数主动结束本次运行，恢复的物理时间必须早于请求的结束时间。

历史本地 PETSc 3.23.2 / SuperLU_DIST 9.1.0 的多个 LU 子块同时存在时，
销毁路径出现 communicator 重复释放，Valgrind 已复现；因此分块默认不使用多个 SuperLU_DIST 子因子。
单个整体直接解保持可用。修复外部依赖前，不建议手动把各分块同时改回该 LU 后端。
ASM 路径在 CPU 下的针对性 Valgrind 检查报告 0 个内存访问错误；此结果不代表全依赖库无内存泄漏。

P8 交付时 Debug/Release 的 13 项 CTest 全部通过，包含五类 transient/FSI 配置的 1/2 rank 重启对照，
以及有限变形 FSI 的直接解与分块解 1/2/4 rank 对照。
性能复现脚本为 `scripts/benchmark_fsi.py`；实际规模和数字见
[性能基线](docs/development/PERFORMANCE_BASELINE.md)，不把这些小网格运行解释为大规模扩展性证明。

可选 API 文档：`cmake --preset debug -DMHPC_BUILD_DOCS=ON`，随后
`cmake --build build/debug --target docs`；入口为 `build/docs/html/index.html`。

结构常量由 [discretization.hpp](include/eonsim/discretization.hpp) 的拓扑/场布局模板推导；高斯积分点与权重由独立的 [quadrature.hpp](include/eonsim/quadrature.hpp) 静态模板维护。三维多物理场使用 Tet4，二维标量另有原生 Tri3/P1 与 Quad4/Q1；模板定义和积分规则选择见 [离散算子说明](docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md#编译期拓扑布局与积分规则)。

## 基础完善：几何与标签边界

推进顺序和阶段验收见 [基础完善路线 B0–B5](docs/development/ROADMAP.md)。
B0 统一了外表面与相邻 Tet4 的关系、三维面积/外法向和静态三角形积分规则，并接入流体、固体和 FSI。

B1 固定网格流体现在可使用任意正 physical tag 配置边界；不需要单位立方体坐标。运行：

```bash
./build/release/eonsim -case cases/fluid/rotated_channel.yaml
./build/release/eonsim -case cases/fluid/rotated_channel.yaml -prepare results/rotated2 -parts 2
/usr/bin/mpiexec -n 2 ./build/release/eonsim -case cases/fluid/rotated_channel.yaml -partition results/rotated2
```

该案例是旋转、平移后的 2×1.5×0.7 m 通道：线性剪切速度、出口牵引、常压力 2 Pa。
入口/出口外向流量应分别为 -0.105/+0.105 m³/s，所有边界净通量应接近零。
如需重新生成网格：`python3 cases/fluid/generate_rotated_channel.py`。

`fluid.boundaries` 是条件列表，每条包含 `tag`、`type`、`value`。支持：

- `type: velocity`：三分量速度，`value: [ux,uy,uz]`。
- `type: traction`：三分量牵引 `sigma*n`，`value: [tx,ty,tz]`。
- `type: pressure`：法向压力载荷，标量 `value: p`，按外法向施加 `-p*n`。

前两类可增加 `origin: [x0,y0,z0]` 和三行 `gradient`，表示 `value + gradient*(x-origin)`。
瞬态可在每条条件中配置 `ramp_time`，全局 `dt/steps` 用法不变。标签模式不接受旧通道专用的
`pressure_drop/outlet/ramp_time` 顶层参数；省略 `boundaries` 时继续运行原有通道基准。
法向速度封闭时需要 `fluid.pressure_gauge: {node: 原始网格ID, value: 压力}` 或零均压策略；
压力规范与存在自由法向速度的边界并用会报错。
重复/缺失/多余标签、矛盾速度约束和不相容的全速度边界净通量在求解前失败。

每个标签输出 `area`、`outward_flow` 和 `mean_pressure`，另输出整体 `net_outward_flow` 与 `divergence_l2`。
通用边界模式没有预设解析解，因此不打印旧通道的速度误差。`tagged_fluid_verification` 验证旋转通道
的三种边界配置、仿射牵引、1/2 rank、瞬态 ramp、同分区重启和错误输入。

## B2 区域材料与分量约束

`fluid.regions` 按体标签指定 `density/viscosity`，`solid.regions` 指定 `young/poisson/density/material`；
设置后必须覆盖所有实际体标签，遗漏、多余、重复和非法材料参数会报错。省略时沿用全域材料。例如：

```yaml
solid:
  mode: static
  regions:
    - {tag: 10, young: 100, poisson: 0, density: 1, material: linear}
    - {tag: 20, young: 200, poisson: 0, density: 1, material: linear}
```

速度/位移边界可加 `components: [0, 2]`，仅约束全局笛卡尔 x/z 分量；默认约束全部分量。
固体用 `type: displacement` 和三分量 `value`，牵引用 `type: traction`。每个标签仍只有一条条件；
共享节点按分量合并，冲突报错。未约束的分量为自然条件；不提供任意方向的多点约束。
固体当前支持静载与撤载，边界不接受时间 ramp。显式标签模式为每个标签输出
`solid_boundary_tag`、`reference_area`、`mean_displacement_x/y/z` 和 `mean_velocity_x/y/z`。
均值按参考面积积分，单位依次为 m²、m、m/s；每个面的贡献只由相邻单元 owner 积分。
位移边界仅对其指定分量输出 `reaction_x/y/z`，从节点 owner 的约束前残量求和，表示支座对固体的力 (N)。
相交标签可能重复包含同一约束自由度的反力，不能直接把各标签反力相加；
`support_reaction_x/y/z` 使用已合并的约束，每个自由度只计一次。
旧 `tip_displacement/reaction_x` 摘要仅在省略标签边界的单位块基准中输出。

`fluid.pressure_normalization: mean` 在一个连通的法向速度封闭流体域中先临时点定标，再减去体积平均压力；
输出压力及约束反力使用相同基准。它与 `pressure_gauge` 互斥，不是自动多连通域零空间探测。
双材料精确杆、平移/旋转标签观测、重叠约束反力、混合分量流体及压力归一化见 `tests/verify_regions.py`。

两层 Couette 案例使黏度跳跃直接参与速度梯度和界面牵引：下/上层黏度为 1/4 Pa·s，
顶部速度 1 m/s，压力 2 Pa，解析剪应力 1.6 Pa，出口流量 0.65 m³/s。
`verify_regions.py` 另交换两层黏度，流量变为 0.35 m³/s；两组均检查 1/2 rank 的场、剪应力与壁面反力。
这是共形 P1 分段线性精确例，不是一般流动的网格收敛研究。

```bash
python3 cases/fluid/generate_layered_channel.py
./build/release/eonsim -case cases/fluid/layered_channel.yaml
```

## B3 独立共形流固网格

```bash
./build/release/eonsim -case cases/fsi/domains/case.yaml -prepare results/domains2 -parts 2
/usr/bin/mpiexec -n 2 ./build/release/eonsim -case cases/fsi/domains/case.yaml \
  -partition results/domains2 -schur_pc -output results/domains.vtu
```

该算例实际读取 48 个流体单元和 51 个固体单元，两域节点编号、顺序和内部划分不同，共享 9 个界面节点。
`fsi.domains` 指定 `solid_mesh`、两域体标签、界面标签、`match_tolerance`、压力入口标签及三组齐次分量约束。
界面节点和三角面必须一一匹配，两侧外法向相反；外边界标签须跨域互不重复。
当前每个 FSI 域仍使用一套材料参数；B2 的多材料列表用于独立流体/固体。

预处理合并界面节点后统一 METIS 分区；求解阶段各 rank 只读自己的 HDF5。
两域输出分别为主文件和 `_solid` 文件，共用本地点表；未被该域单元引用的点没有该域物理场含义。
分区格式升级为 v2，旧分区必须重新 `-prepare`。非匹配界面、重网格和在线重分区尚未实现。

## B4 时间步失败恢复

在 YAML 根节点添加：

```yaml
time_control: {max_retries: 6, minimum_dt: 0.0005, reduction: 0.5}
```

`dt*steps` 定义终止物理时间。Newton trial 越出几何/材料定义域时使用 PETSc domain-error 协议，
默认回溯线搜索先尝试较小 Newton 步；最终非线性不收敛才从上一 accepted 状态缩 dt 重算。
输入、线性求解/PC、通信和 I/O 错误不重试；线性失败报告 SNES/KSP/PC reason。
成功后保持缩小的步长，不自动增长；默认 `max_retries: 0`。
这是失败恢复策略，尚无局部截断误差估计。缩步后 accepted 步数可能多于配置 `steps`。

checkpoint v3 按 generation 保存实际 `time/next_dt`；同 rank、同分区恢复可继续缩步后的时间轨迹。
旧 v1/v2 checkpoint 明确拒绝。当前字段验收下，测试使用真实 Neo-Hookean FSI Newton 失败触发 dt=0.04→0.00125，
验证与从头使用小步长的计算及 1/2 rank 重启结果一致。

## B5 导数、Schur 与精度记录

`-schur_pc` 启用速度—压力 Schur/GAMG，可用于独立流体与单体 FSI；与 `-block_pc` 互斥。
FSI 外层仍按 flow/mesh/structure（或 rigid）分块，flow 内部再分速度/压力。
近似 Schur 为 `D−C diag(A)⁻¹B`；速度、压力、网格和弹性块采用 GAMG，刚体块用 Jacobi。
默认粗层为 GMRES/Jacobi，避免多个 SuperLU_DIST 子因子；完整耦合算子和非线性容差保持一致。
子块 PETSc 选项可通过 `-fieldsplit_velocity_*`、`-fieldsplit_pressure_*` 覆盖；FSI 流体子块再加 `fieldsplit_flow_` 前缀。

默认 FSI 切线使用解析体积/形函数梯度导数与固定宽度前向链式传播；积分仍由静态模板维护。
`-fsi_fd_tangent` 只用于差分参考。单元导数、1/2/4 rank 的完整场及整体直接解对照均有自动检查。

[实际精度与性能记录](docs/development/B5_ACCURACY_AND_PERFORMANCE.md) 包含 4³/8³/12³ 通道压力和速度收敛、
5 组 FSI 时间步、703/2299 有效未知量的直接解/Schur/差分切线耗时及内存。
当前测试覆盖低 Re 小规模问题；尚未证明网格无关迭代、高 Re 或大规模生产性能。
