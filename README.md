# EONSim

C++17 / PETSc 多物理场求解器。当前完成 **P0 标量 Poisson 与 P1 分布式基础**：
YAML 配置 → Gmsh Tet4 网格 → 几何/积分 → 稀疏装配 → 非零 Dirichlet lifting →
PETSc KSP → 误差摘要与 VTU。后续路线是分布式基础、独立流体/固体、单体刚体/弹性体 FSI。

分布式求解使用预处理后的本地分区；当前尚未实现一般源项/边界表达式、流体、固体或 FSI。首个标量算例服务离散与求解链验证。

## 环境与构建

需要 CMake ≥ 3.21、Ninja、C/C++17 编译器、实数双精度 PETSc、匹配的 MPI、
BLAS/LAPACK 和 yaml-cpp（当前验证版本 0.8.0）。运行已保存的算例不需要 Gmsh 或 Python；
重新生成网格及可选验证脚本需要 Python 3。

```bash
cmake --preset debug
cmake --build --preset debug --parallel
cmake --preset release
cmake --build --preset release --parallel
./build/release/eonsim -case cases/poisson/case.yaml
```

预设生成 `build/debug` 和 `build/release`。Debug 设置 `MHPC_DEBUG=1`，Release 设置为 `0`；
两者使用相同方程、约束和停止准则。输入/几何有效性、非有限值、KSP 不收敛和真实残量检查
在 Release 中保留。应用默认将尚未设置的 `OMP_NUM_THREADS`、`OPENBLAS_NUM_THREADS`、
`MKL_NUM_THREADS` 设为 `1`，已有环境设置会保留并在摘要中显示。

这台机器验证使用 GCC 13.3、PETSc 3.23.2（优化构建、实数双精度、32 位 PetscInt）、
OpenMPI 4.1.6、OpenBLAS 0.3.26。应用网格 ID 使用 64 位，进入 PETSc 前检查代数编号范围。
Debug 应用当前也链接这套优化 PETSc；它不等同于 PETSc 自身的调试构建。

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
支持 Gmsh **2.2 ASCII**，Tet4（type 4）和边界三角形（type 2）；一阶点/线实体可读但不参与体积分。
高阶单元、其他体单元、Gmsh 4.x/binary 会明确拒绝。每个外表面必须有标签三角形，
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
cmake --build --preset debug --parallel
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
机器路径用本地命令或忽略的 `CMakeUserPresets.json` 设置。当前机器 PATH 中的 ParaView
带有 MPICH 启动器，而本项目使用 OpenMPI；可通过 `-DMPIEXEC_EXECUTABLE=/usr/bin/mpiexec`
设置匹配的启动器，多 rank 求解必须传入匹配的分区目录。

```text
include/eonsim/       具体配置、网格、Tet4、线性系统与结果类型
src/core/            YAML 解析与强类型配置
src/mesh/            Gmsh 输入、拓扑/标签检查
src/fem/             不依赖 MPI/PETSc 的 Tet4 几何与局部扩散核
src/algebra/         PETSc 生命周期、装配入口、约束与线性求解
src/physics/         Poisson 算例组装、制造解与积分误差
src/io/              VTU 输出
src/main.cpp         初始化、配置、运行与摘要
cases/poisson/       可运行 YAML、网格及生成器
```

一个 `eonsim_core` library 和一个 `eonsim` 应用。下一步按
[开发路线](docs/development/ROADMAP.md) 继续 P2 独立流体。
设计约束入口为 [AGENTS.md](AGENTS.md) 与 [总原则](MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md)。

## P2 独立流体

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
