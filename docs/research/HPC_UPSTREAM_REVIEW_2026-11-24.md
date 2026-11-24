# HPC 开源软件调研与 EONSim-new 开发报告

2026 年 11 月 24 日 · 性能对照基线 `89a1a3d` · 提交审阅时的主线 `f7ec770` · 数值环境 PETSc 3.23.7 / CPU / MPI

**当前最值得投入的是弹性管瞬态对照与求解阶段计时。** 刚性管的流量幅值已经有解析参照，弹性管的静态平衡也有跨程序参照。两项圆管验证还留下两个问题。一是截面平均压力与施加牵引的关系，二是加载早期的壁面响应。单独加速单元计算可以同时推进。本轮在同一单元公式上减少了重复积分，固定网格流体在单进程下的单元核耗时下降 29.6%，整次运行耗时下降 2.6%。弹性 FSI 的端到端时间没有显示稳定收益。以下性能数字均来自本地同机配对，圆管精度另列其来源。

## 1. 这次重新查了什么

8 月报告第 34 节的 41 项全部重新查阅。另查 Kokkos、Kokkos Kernels、RAJA、PERIGEE、svMultiPhysics、svZeroDSolver、4C、Ginkgo、SUNDIALS，共 50 个项目。47 个项目固定到公开 Git 提交并读取实现、头文件、发行说明或仓库说明。另 3 项采用官方在线源码页或文档。附表逐项给出实际读取入口和深度。PETSc 的工作锁与上游版本各读一份，项目数计一次。上游阅读属于源码或文档研究，运行证据来自 EONSim-new。仓库内 10 月的 20 组学习矩阵也用来核对哪些设计已经落地。[10 月学习矩阵](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md)

### 近期版本中，哪些变化影响当前开发

| 上游核对结果 | 对 EONSim-new 的具体影响 |
|---|---|
| MFEM 4.10 在 9 月发布，新增适用于 H1 Bernstein 单纯形质量和扩散积分子的 GPU 部分装配。对流、混合量、基函数与后端仍要逐项核对。 | 借鉴几何量和作用阶段的拆分。当前低阶 Tet4 的稳定化 NS 和 ALE 几何切线需要自己的参照解与测试。[发行说明](https://github.com/orgs/mfem/discussions/5487) · [各后端支持表](https://mfem.org/howto/assembly_levels/) |
| libCEED 1.1.2 于 11 月 21 日发布。该版本的体积示例先从几何构造积分点数据，再由另一个算子使用这些数据。 | 将不随积分点变化的工作提到单元层。本轮在当前牛顿试算几何内使用这一思想，保留体积和梯度的几何导数。[发行版](https://github.com/CEED/libCEED/releases/tag/v1.1.2) · [libCEED 源码](https://github.com/CEED/libCEED/blob/3e4923a9e20c2077457664cae137ca59c1438064/examples/ceed/ex1-volume.c) |
| PETSc 上游核对至 3.26.1，EONSim 工作锁为 3.23.7。两版均有 PETSc FieldSplit 的显式 Schur 预条件矩阵分支。 | 继续以 3.23.7 重现实验。当前代码已经使用显式字段 IS、FULL Schur 分解和 SELFP。若研究新的近似，直接在既有树上与直接解对照。[上游下载](https://petsc.org/release/install/download/) · [PETSc locked 源码](https://github.com/petsc/petsc/blob/6f16bb51def9487f6ec368d97c6f85a3baa0b8f6/src/ksp/pc/impls/fieldsplit/fieldsplit.c) · [PETSc current 源码](https://github.com/petsc/petsc/blob/6a416413e7b2a40f0a13d928bcbb657bfe50a5b0/src/ksp/pc/impls/fieldsplit/fieldsplit.c) |
| Kokkos 和 Kokkos Kernels 均核至 11 月的 5.3.0，RAJA 核至 2026.07.1。Kokkos Core 提供执行与内存抽象，Kernels 的 SpMV 接口接收 execution space、矩阵和向量。RAJA 的 `forall` 把循环和执行策略分开。 | 这两套当前主版本均要求 C++20。现有 C++17/CPU 路径可保留为对照。若 GPU 成为部署目标，可在同一单元批次对照 RAJA 与 Kokkos Core，并记录语言标准迁移、内存驻留、传输和预条件成本。调用 Kokkos Kernels 的前提是确有稀疏或批量代数算子可交给它。[RAJA 发行说明](https://github.com/LLNL/RAJA/blob/v2026.07.1/RELEASE_NOTES.md) · [Kokkos 发行版](https://github.com/kokkos/kokkos/releases/tag/5.3.0) · [Kokkos Kernels 源码](https://github.com/kokkos/kokkos-kernels/blob/fa64c039a53dcead68e5f319b777ec5889ef0750/sparse/src/KokkosSparse_spmv.hpp) |
| preCICE 3.5.0 于 11 月发布。IQN-ILS 的实现用接口残差历史和 QR 解小型最小二乘问题。AMReX 26.11 与 t8code 4.0.0-26.11 分别有 ghost 通信及树网格重分区接口。 | preCICE 适合作未来分离式对照。当前单体 FSI 更需要本地残量、几何导数与共同提交的一致性。自适应路线优先验证跨分区解和历史迁移，届时再决定是否接入 t8code。[preCICE 发行版](https://github.com/precice/precice/releases/tag/v3.5.0) · [preCICE 源码](https://github.com/precice/precice/blob/e72f2ffe90094fa3516aee4f5115fb38a65543e9/src/acceleration/IQNILSAcceleration.cpp) · [AMReX 源码](https://github.com/AMReX-Codes/amrex/blob/72d668eb80d1737e4550a5abf2fca5fcbc8ba637/Src/Base/AMReX_FabArray.H) · [t8code 源码](https://github.com/DLR-AMR/t8code/blob/fb60a9b09b1322999a77954b14ef1cd364a479b3/src/t8_forest/t8_forest_general.h) |

### 上游实现如何改变取舍

| 开发问题 | 重新阅读后的判断 |
|---|---|
| 能否把现有 FSI 直接改成 PERIGEE 风格的两场求解？ | PERIGEE 的 FSI 非线性循环在速度–压力更新后另调网格求解器，源码对力学与网格线性求解分别打点。EONSim 的单体雅可比含 ALE 交叉导数。可以先移植分项计时思想，再在同一个完整算子上比较 physics / quantity / hybrid 分组。[PERIGEE 源码](https://github.com/APSIS-ANALYSIS/PERIGEE/blob/329fe3433b6edc3363f107b7096efdf2fc77c4a7/examples/fsi/src/PNonlinear_FSI_Solver.cpp) · [现有分组](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/development/DOF_AND_PC_GROUPING.md) |
| 能否据圆管流量吻合就认定与 svFSI 的 RBVMS 相同？ | EONSim 当前残量可以直接识别对流、对称黏性应力、SUPG/PSPG 和强动量残量。固定版 svFSI 的三维流体实现另有 `vmsFlag`、`tauM`、`tauC` 等分支。相同网格与载荷便于交叉验证，逐项方程、时间层和稳定参数仍需比对。[svFSI 源码](https://github.com/SimVascular/svFSI/blob/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571/Code/Source/svFSI/FLUID.f) · [EONSim 原始残量](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/include/eonsim/fluid_residual.hpp) |
| 分别借鉴哪种结构来做血管出口？ | svZeroDSolver 的 Windkessel 元件有独立电容压力自由度，并将时间导数、代数量和外部压力写入不同系数。svMultiPhysics 的 Integrator 有预测、校正及中间状态。EONSim 可先在单个固定端面实现解析可测的 RCR，再接入单体阶段和 checkpoint。[svZeroDSolver 源码](https://github.com/SimVascular/svZeroDSolver/blob/29e32b2d9961e372ec5f8533200944cefa66f994/src/model/WindkesselBC.cpp) · [svMultiPhysics 源码](https://github.com/SimVascular/svMultiPhysics/blob/f598b82eecd418f07b42e42ecb9f2339155015fa/Code/Source/solver/Integrator.cpp) |
| 什么时候引入 matrix-free 或 GPU？ | deal.II 的 FEEvaluation、libCEED 的局部算子和 MFEM 的装配层次可用于局部作用。Nektar++ 的 Collections 也在一个算子下保留不同执行实现。EONSim 先固定离散和场误差，再比较 `Jv` 加近似预条件矩阵的完整成本。NekRS 的高阶六面体结果只作为试验设计参考。[deal.II 源码](https://github.com/dealii/dealii/blob/02c5025ef5e042381dbd5772a73691520a4b1aea/include/deal.II/matrix_free/fe_evaluation.h) · [MFEM 源码](https://github.com/mfem/mfem/blob/d964264cdb9a13e94a201b6c236c7721e0c8765f/fem/integ/bilininteg_diffusion_pa.cpp) · [Nektar++ 源码页](https://doc.nektar.info/doxygen/5.10.0/_operator_8h_source.html) · [NekRS 源码](https://github.com/Nek5000/nekRS/blob/96b3cf9e5bacede16568826c04a21bc0fe50dc7d/RELEASE.md) |
| 是否需要先建一套通用弱式编译器？ | DOLFINx 允许将系数打包后交给装配，Trilinos/Phalanx 通过显式字段依赖组织求值，MOOSE 区分只求残量与联合求残量/雅可比。可先从现有 Tet4 核中提取能验证的重复工作。Firedrake、Devito、PyFR 的生成和调度路线待多个算子与设备后端出现时再评估。[FEniCSx 源码](https://github.com/FEniCS/dolfinx/blob/fefdb2201b80a8f59527de2d461b9056906661d8/cpp/dolfinx/fem/assembler.h) · [Trilinos 源码](https://github.com/trilinos/Trilinos/blob/bc7b0164a4e1d827802d1d3f7e5377368f0cfb55/packages/phalanx/src/Phalanx_FieldManager_Def.hpp) · [MOOSE 源码](https://github.com/idaholab/moose/blob/d5218841df590f5450df1b7e2e378e068ea0a69d/framework/src/systems/NonlinearSystemBase.C) · [PyFR 源码](https://github.com/PyFR/PyFR/blob/fdb13c17024084536b68dc7ef54c8a030f1cc6a2/pyfr/backends/base/backend.py) |
| 如何处理网格和耦合数据的所有权？ | AMReX 的 `FillBoundary_nowait/finish` 显式区分发起和完成。t8code 将 adapt、partition、ghost 分成操作。preCICE 单独处理无接口节点的进程。当前可以复用这些测试思路，优先覆盖本地空面片、全局通量归约和重启历史。[AMReX 源码](https://github.com/AMReX-Codes/amrex/blob/72d668eb80d1737e4550a5abf2fca5fcbc8ba637/Src/Base/AMReX_FabArray.H) · [t8code 源码](https://github.com/DLR-AMR/t8code/blob/fb60a9b09b1322999a77954b14ef1cd364a479b3/src/t8_forest/t8_forest_general.h) · [preCICE 源码](https://github.com/precice/precice/blob/e72f2ffe90094fa3516aee4f5115fb38a65543e9/src/acceleration/IQNILSAcceleration.cpp) |

## 2. EONSim-new 的实际起点

| 位置和状态 | 可以据此得出的结论 | 下一项需要解释的观测 |
|---|---|---|
| `main@89a1a3d`，已合入 #38 | C++17、PETSc AIJ、MPI owned/ghost、共形双域、单体弹性 FSI、BE/BDF2/generalized-α 和固定网格可选 COO 已有源码与小规模验证。历史刚性稳态细网格的流量误差 0.5464%，同一算例的端面压差误差为 5.1400%。 | 将截面面积平均静压、积分法向牵引与输入压力分开报告。默认稳定化随步长改变，空间和时间误差需要分别评估。[main](https://github.com/saitoasukakawaii/EONSim-new/commit/89a1a3d823396df02fa9e8acb5ded36b70938e9c) · [稳态复算证据](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/research/data/rigid-tube-seeds-2026-11-07/README.md) |
| PR #41，`10197d0`，已合入 `main@f7ec770` | 其归档在 48 扇区、12 径向、18 轴向的 Womersley 管上报告流量幅值误差 0.7554%、相位误差 0.2097°、同网格独立 svFSI 复流量差 1.3046%。 | 此组计算的端面压差幅值比施加载荷低 5.6792%。可对比面平均压强、黏性法向应力、截面位置和端面分量约束；各项归因仍是待检验假设。[PR #41](https://github.com/saitoasukakawaii/EONSim-new/pull/41) |
| PR #42，`0c8f6fb`，未合入 | 其归档的独立厚壁固体最细网格扩张误差 0.1894%。72 扇区单体 FSI 平衡扩张误差 0.5684%。 | 48 扇区静压阶跃的首段最大截面差，从步长 0.5 s 的 9.947% 降至 0.25 s 的 8.444%，均以解析平衡扩张量归一；个别时刻差异随加密增大。静态平衡与瞬态历程需分别判定。[PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) |

上表圆管研究数值取自固定 PR 或主线归档。本轮另对两个 PR 的固定提交与新核做了本地集成回归，范围和结果见第 3 节。既有 MPI 检查主要到单机 4 rank，多节点生产扩展性仍需实际测量。[仓库生产路线](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/development/FSI_PRODUCTION_ROADMAP.md)

## 3. 本轮已实施的开发

**本地数值提交为 `4095e4bd4e18a350e62fd2e295d88de3a6d48640`。** 针对常黏度、仿射几何、线性速度形函数的 Tet4，将黏性内力和固定几何速度切线从四个求积点的循环移到单元层。固定网格流体与独立 ALE 使用解析速度切线。单体 FSI 对共享的流体残量做前向自动微分，体积与形函数梯度在每个 trial 几何上求值并参加求导。这两条切线路径分别做了验证。

设 $V_e$ 为当前单元体积，$g_a=\nabla N_a$，$L=\nabla u_h$。对牛顿流体，黏性部分的单元残量和固定几何速度切线为

$$
R^\mu_{ai}=V_e\mu\sum_j (L_{ij}+L_{ji})g_{aj},\qquad
K^\mu_{ai,bk}=V_e\mu\left[\delta_{ik}(g_a\!\cdot g_b)+g_{ak}g_{bi}\right].
$$

因为 $g_a$、$L$、$\mu$ 在当前单元空间内恒定，这一项积分一次即可。对流、惯性和稳定化仍使用原四点规则。曲边单元、高阶速度或积分点可变黏度需要重新检查这一假设。入口分别为 `include/eonsim/fluid_residual.hpp`、`src/physics/fluid_element.cpp`、`src/physics/fsi_element.cpp`。新增独立检验在畸变四面体上给出简单剪切的精确节点力与刚体转动的零应力，同时将实际 Stokes 残量和雅可比作用与解析节点力逐项对照。

### 编译与数值检查

使用仓库的 `scripts/cloud/restore.sh` 与 `scripts/cloud/run.sh`。主锁为 PETSc 3.23.7、Open MPI 5.0.8、GCC 15.3.0，Release、双精度实数、32 位 PetscInt。

| 实际运行 | 结果 |
|---|---|
| 干净的 `89a1a3d` 对照构建 | 4/4 通过。归档对照可执行文件的 SHA-256 为 `1771725642c3b076eab26e8ca5d6e72503141c76f64d06279a875907d050c555`。 |
| 数值提交 `4095e4b` | 9/9 通过。涵盖两种元素切线、COO、流体时间积分及广义 α、ALE 时间积分、双域、标签边界与独立流体；其中四项的测试驱动覆盖 1/2/4 rank。候选程序的 SHA-256 为 `5f6f7c5ecc077a39fd74db1c17ee7b20386f2bc3d5a6546c3cb85feabd8280fa`。 |
| 独立有限差分方向导数 | 固定几何流体最大相对误差 $5.67\times10^{-11}$。FSI 分别扰动力学和网格自由度，最大相对误差 $8.97\times10^{-11}$；两项原有阈值均为 $2\times10^{-8}$。新增剪切/转动解析检查通过。 |
| 圆管交叉集成 | 独立检出 #41 的 `10197d0` 与 #42 的 `0c8f6fb`，合并两棵源码树后应用同一数值提交。本地集成 `949b57625431` 通过 `womersley_flow` 与 `lame_wall` 两项 Release CTest（2/2）。两 PR 的完整外部 svFSI 计算和历史精细网格研究沿用其归档。 |

与 `main@f7ec770` 同步后，使用仓库 Release 编译脚本验证了 10 项增量选测及 `womersley_flow`，共 11/11 项通过。供复现使用的公开数值提交 [7a0416d](https://github.com/saitoasukakawaii/EONSim-new/commit/7a0416daf37d851155f3fb8e5bf4e24c34d5fc79) 和归档 `4095e4b` 具有相同的 Git 源码树 `6fb5b1d76e2bf1662bceb867a3dc93d2a21ecb68`。

### 配对性能测量

AMD EPYC 9V74，单台共享机器，可见 9 个 CPU，每个 MPI 进程及 BLAS 单线程。两版使用同一份 125 节点、384 个四面体的立方网格，固定流体 500 个代数自由度，弹性 FSI 730 个。选用相同的直接线性求解 PREONLY / LU（SuperLU_DIST）。每例 10 个 BE 接受步，流体 $\Delta t=0.05$、FSI $\Delta t=0.02$，SNES 相对与绝对容差分别为 $10^{-10}$、$10^{-12}$。流体另开两版相同的单元计时选项。两例各用 1/2 rank，按每个组合每版预热一次、正式样本交替次序 6 对，共 **48 次正式求解、8 次预热**。

表中百分数为各对“候选时间 / 基线时间 − 1”的中位数。括号是六对的最小值与最大值。装配和求解器计时按每个接受步的 rank 最大值求和，单元核按每 rank 累积十步后取最大值。整次墙钟包含启动、读写和报告，只比较相同诊断设置。各阶段计时相互包含，不能相加。

| 算例 | MPI | 流体单元核 | 总装配 | 求解阶段 | 整次墙钟 |
|---|---:|---:|---:|---:|---:|
| 固定网格流体 | 1 | -29.6%（-35.1 至 -27.1%） | -17.8%（-22.2 至 -13.0%） | -7.1%（-9.9 至 -2.7%） | -2.6%（-4.1 至 -0.2%） |
| 固定网格流体 | 2 | -30.8%（-52.3 至 +13.4%） | -5.5%（-36.2 至 +36.1%） | -4.2%（-28.5 至 +32.6%） | -3.9%（-9.5 至 +14.1%） |
| 弹性 FSI | 1 | 未单列 | -4.8%（-14.8 至 -1.3%） | +2.0%（-11.2 至 +2.9%） | +1.9%（-5.9 至 +3.7%） |
| 弹性 FSI | 2 | 未单列 | +0.7%（-25.8 至 +8.2%） | +1.0%（-22.0 至 +8.8%） | +1.3%（-18.0 至 +5.2%） |

56 次求解逐对比较所有最终 owned 节点输出，最大数值分量绝对差为 $2.22\times10^{-16}$；FSI 固体输出最大差为 $3.65\times10^{-17}$。这里比较各输出分量的数值差，物理量单位各异。逐步 Newton 与线性迭代数一致。流体核的单进程结果有清晰收益，双进程波动较大。FSI 在两种进程数上的整次时间中位数分别增加 1.9% 和 1.3%，六对的范围都跨越零。单体 FSI 还有宽度 28 的局部几何/力学自动微分、固体装配、线性求解及输出；现有计时不能把剩余成本归因于某一项。

随开发包提供 `docs/research/data/tet4-viscosity-2026-11-24/`，含复现脚本、逐对数据、编译选测和数值收据。Git 提交保存相同的工程内容。此处的验证范围为 CPU 单机小算例。

## 4. 用调研指导接下来的开发

以下均为建议开展的任务。优先级结合已有误差、生产路线和本轮实测确定。建议的门槛用于设计实验，项目可依据目标物理量调整。

| 顺序 | 进入的位置与做法 | 可以交付什么结果 |
|---|---|---|
| 1．解释弹性管的加载瞬态 | 在 #42 的归档上按同一物理时刻对齐端点位移、阶段压力、壁速和流体端面做功。固定网格、单位与谱半径，比较阶跃/光滑升载、相同初始化及至少三档步长；分别采用固定和默认稳定化。每组一次只改变一项。 | 为 1 s 和原峰值时刻给出面积差、相位/幅值、质量和外载功误差，画出全时程与步长变化。把离散化、采样错位和初始状态三类假设逐一验证；保留不能归因的区间。[开放算例](https://github.com/saitoasukakawaii/EONSim-new/pull/42) · [svMultiPhysics 源码](https://github.com/SimVascular/svMultiPhysics/blob/f598b82eecd418f07b42e42ecb9f2339155015fa/Code/Source/solver/Integrator.cpp) |
| 2．在完整 FSI 中定位成本 | 在 `fsi_element.cpp`、`fsi.cpp` 及 `nonlinear_system.cpp` 分出流体/ALE 的残量与 AD 切线、固体核、矩阵插入、PC setup/apply 和输出。先用原有直接法为数值基准，再复用已有三种 PC 树。 | 同网格、同时间步、同容差报告各场误差、真实线性残量、每步迭代、最大 rank 内存、配对墙钟与样本范围。一组规模增大后仍复现的瓶颈，才作为下一项优化对象。[现有层级测量](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/research/SCHUR_MESH_PROFILE_2026-10-30.md) · [PERIGEE 源码](https://github.com/APSIS-ANALYSIS/PERIGEE/blob/329fe3433b6edc3363f107b7096efdf2fc77c4a7/examples/fsi/src/PNonlinear_FSI_Solver.cpp) |
| 3．交付一个可复核的血管 RCR 出口 | 从固定端面、单出口着手。在 `config.cpp` 描述参数，在耦合残量中归约流量，在 `checkpoint.cpp` 保存已接受电容压力。按下文公式检验残量和切线，再扩展多个出口、变步长与共同 stage。 | 恒流阶跃与单频阻抗均有解析参照。要求 Jv 有限差分达到现有方向导数的误差量级，1/2/4 rank 一致，失败重试不重复推进，断点续算复现连续计算。单出口和多出口分别记录结果。[svZeroDSolver 源码](https://github.com/SimVascular/svZeroDSolver/blob/29e32b2d9961e372ec5f8533200944cefa66f994/src/model/WindkesselBC.cpp) · [生产路线](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/development/FSI_PRODUCTION_ROADMAP.md) |
| 4．分开验证外壁支撑和多节点规模 | 先在 #42 的厚壁管参考构形外表面施加法向弹簧及阻尼，并记录支撑功。扩展到足够大的同一网格后，再做单节点与跨节点强、弱扩展。 | 零支撑恢复自由外壁，刚度增大时平衡扩张减小，阻尼非负耗能；随后给出多节点的时间、内存、迭代和通信占比。工作量固定与每 rank 工作量固定分开测。[厚壁管基线](https://github.com/saitoasukakawaii/EONSim-new/pull/42) · [并行约定](https://github.com/saitoasukakawaii/EONSim-new/blob/89a1a3d823396df02fa9e8acb5ded36b70938e9c/docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md) |
| 5．按量测结果选择设备后端或 AMR | 局部核占比高时，以同一批单元对照本机实现与一个设备后端；若矩阵内存先成为瓶颈，试验 matrix-free $Jv$ 加已装配的 $P$；局部空间误差支配且网格加密昂贵时，试验 t8code 历史场迁移。 | 比较满足同一误差与容差的 time-to-solution，记录主机/设备传输字节、峰值内存、设置时间与多步复用；AMR 另验场守恒与同一物理时刻的重启结果。[libCEED 源码](https://github.com/CEED/libCEED/blob/3e4923a9e20c2077457664cae137ca59c1438064/examples/ceed/ex1-volume.c) · [Kokkos 源码](https://github.com/kokkos/kokkos/blob/dc826b0fad122b57fee60223e86154aecb8e60f4/core/src/Kokkos_View.hpp) · [RAJA 源码](https://github.com/LLNL/RAJA/blob/a7230d0fd7b2d8df7433f8f0464e833db42d38df/include/RAJA/pattern/forall.hpp) · [t8code 源码](https://github.com/DLR-AMR/t8code/blob/fb60a9b09b1322999a77954b14ef1cd364a479b3/src/t8_forest/t8_forest_general.h) |

**RCR 的首个验收方程。** 约定固定出口面、外流 $Q>0$，电容压力 $p_c$，近端和远端阻力 $R_p,R_d>0$，顺应性 $C>0$，远端压力 $p_d$。则

$$
p_{out}=p_c+R_pQ,\qquad C\dot p_c=Q-(p_c-p_d)/R_d.
$$

对 BE 与给定常数参数，$\partial p_{out}^{n+1}/\partial Q^{n+1}=R_p+\Delta t R_d/(R_d C+\Delta t)$。在固定构形、同一试探和检验空间，令 $b^Tu=\int_{\Gamma}u\cdot n\,dA$，压力牵引在残量中的导数含这一系数乘 $bb^T$。这样，跨节点端口耦合可以通过一次标量通量归约和局部向量作用实现，并可独立核验符号。对谐波 $e^{i\omega t}$，阻抗为 $R_p+R_d/(1+i\omega R_d C)$，为幅值与相位提供独立检验。若端面也运动，还要约定相对通量，并对法向与面积求几何导数。此段是开发规格。[svZeroDSolver 元件](https://github.com/SimVascular/svZeroDSolver/blob/29e32b2d9961e372ec5f8533200944cefa66f994/src/model/WindkesselBC.cpp)

## 附表　50 个项目的复查入口

“实现 / 接口”表示本轮读取指定文件中的算法、公开接口或例程；“发行 / 仓库说明”表示核对版本与用途；“官方文档”单列。SHA 链接固定到所读文件。Git 标签行是固定版本，SHA 行是调研时读取的仓库快照，后者不等同于稳定发行版。每行最后一栏是对 EONSim 的用途判断。

### 离散、局部算子与编译

| 项目 | 本轮材料 | 固定入口 | 对 EONSim 的用途 |
|---|---|---|---|
| MFEM | 实现 / 接口 | [v4.10 · bilininteg_diffusion_pa.cpp](https://github.com/mfem/mfem/blob/d964264cdb9a13e94a201b6c236c7721e0c8765f/fem/integ/bilininteg_diffusion_pa.cpp) | 装配策略与局部几何数据分工，先在 Tet4 验证。 |
| libCEED | 实现 / 接口 | [v1.1.2 · ex1-volume.c](https://github.com/CEED/libCEED/blob/3e4923a9e20c2077457664cae137ca59c1438064/examples/ceed/ex1-volume.c) | 区分构造 q-data 与施加算子，作为 matrix-free 原型的接口参照。 |
| deal.II | 实现 / 接口 | [v9.8.0 · fe_evaluation.h](https://github.com/dealii/dealii/blob/02c5025ef5e042381dbd5772a73691520a4b1aea/include/deal.II/matrix_free/fe_evaluation.h) | FEEvaluation 的局部求值、积分与 scatter，可指导按单元批处理。 |
| FEniCSx | 实现 / 接口 | [v0.11.0.post0 · assembler.h](https://github.com/FEniCS/dolfinx/blob/fefdb2201b80a8f59527de2d461b9056906661d8/cpp/dolfinx/fem/assembler.h) | 系数打包与装配分开，为多步复用给出具体入口。 |
| Firedrake | 实现 / 接口 | [8e69b94a · assemble.py](https://github.com/firedrakeproject/firedrake/blob/8e69b94aaa583550d7252b8eb504f99fbfc97eb1/firedrake/assemble.py) | 装配器按问题和张量输出分派，供未来弱式编译路线参考。 |
| Devito | 实现 / 接口 | [77c1190b · operator.py](https://github.com/devitocodes/devito/blob/77c1190bc25b174cc80a5f4786cc6764bb202b65/devito/operator/operator.py) | 符号算子的 lowering 与执行生成，用于评估未来规则网格/编译器需求。 |
| Trilinos | 实现 / 接口 | [bc7b0164 · Panzer_IntegrationRule.cpp](https://github.com/trilinos/Trilinos/blob/bc7b0164a4e1d827802d1d3f7e5377368f0cfb55/packages/panzer/disc-fe/src/Panzer_IntegrationRule.cpp) · [补充源码](https://github.com/trilinos/Trilinos/blob/bc7b0164a4e1d827802d1d3f7e5377368f0cfb55/packages/phalanx/src/Phalanx_FieldManager_Def.hpp) | Panzer 积分规则与 Phalanx 显式字段依赖，适合比较物理求值和执行调度。 |
| DUNE | 实现 / 接口 | [b6b3cea8 · numericaljacobianapply.hh](https://github.com/dune-project/dune-pdelab/blob/b6b3cea832963ff356b7732724bf46aa8abf97fd/dune/pdelab/localoperator/numericaljacobianapply.hh) | PDELab 通过局部残量构造雅可比作用，可交叉检查手写切线。 |
| DuMuX | 在线源码 / 文档 | [FV 局部装配源码](https://dumux.org/docs/doxygen/releases/3.6/a00668_source.html) · [当前文档](https://dumux.org/docs/doxygen/master/) | 局部装配和局部残量分工，可参考区域材料及通量实现。 |
| NGSolve | 仓库说明 | [f81e5bdf · README.md](https://github.com/NGSolve/ngsolve/blob/f81e5bdf81016d86ab4eb38b167d78ba743b0ec0/README.md) | 多用途 FEM 框架，保留为空间和变分接口的扩展参考。 |
| GetFEM | 仓库说明 | [d6729fba · README](https://github.com/getfem-doc/getfem/blob/d6729fba5e40c7ca8799f77055f7199f513466b7/README) | 通用有限元与组装语言，供将来弱式表达需求比较。 |
| Feel++ | 仓库说明 | [02aafe38 · README.adoc](https://github.com/feelpp/feelpp/blob/02aafe38d70912de5ae72e48c0a4a3a07a5ffde9/README.adoc) | 变分模型和应用工具箱的组织方式。 |
| Gridap | 仓库说明 | [9ba86188 · README.md](https://github.com/gridap/Gridap.jl/blob/9ba861886a962f3866bfb8305a304cd482ab2c2c/README.md) | 用 Julia 表达弱式，可作为制造解和模型原型的另一条路径。 |
| libMesh | 仓库说明 | [d78e7d06 · README.md](https://github.com/libMesh/libmesh/blob/d78e7d06547d5d95dac50ac5e59ce84d39827d79/README.md) | 经典并行 FEM 基础设施，作为空间与系统组织参考。 |

### 计算内核、代数与运行时

| 项目 | 本轮材料 | 固定入口 | 对 EONSim 的用途 |
|---|---|---|---|
| PETSc | 实现 | [3.23.7](https://github.com/petsc/petsc/blob/6f16bb51def9487f6ec368d97c6f85a3baa0b8f6/src/ksp/pc/impls/fieldsplit/fieldsplit.c) · [3.26.1](https://github.com/petsc/petsc/blob/6a416413e7b2a40f0a13d928bcbb657bfe50a5b0/src/ksp/pc/impls/fieldsplit/fieldsplit.c) | 核对锁版本与上游版 FieldSplit 中实际构造 SELFP 的入口。 |
| Kokkos | 实现 / 接口 | [5.3.0 · Kokkos_Parallel_For.hpp](https://github.com/kokkos/kokkos/blob/dc826b0fad122b57fee60223e86154aecb8e60f4/core/src/Kokkos_Parallel_For.hpp) · [补充源码](https://github.com/kokkos/kokkos/blob/dc826b0fad122b57fee60223e86154aecb8e60f4/core/src/Kokkos_View.hpp) | 策略分派、并行循环与 View，供异构试点和数据驻留评估。 |
| Kokkos Kernels | 实现 / 接口 | [5.3.0 · KokkosSparse_spmv.hpp](https://github.com/kokkos/kokkos-kernels/blob/fa64c039a53dcead68e5f319b777ec5889ef0750/sparse/src/KokkosSparse_spmv.hpp) | SpMV 的执行空间和视图形参，评估是否已有可直接复用的代数核。 |
| RAJA | 实现 / 接口 | [v2026.07.1 · forall.hpp](https://github.com/LLNL/RAJA/blob/a7230d0fd7b2d8df7433f8f0464e833db42d38df/include/RAJA/pattern/forall.hpp) | 从 forall 执行策略进入后端，以同一单元批次对照。 |
| Ginkgo | 实现 / 接口 | [v1.11.0 · executor.hpp](https://github.com/ginkgo-project/ginkgo/blob/4c77a5d826bd1597fd093f39c47688f8cc735690/include/ginkgo/core/base/executor.hpp) | Executor 封装设备操作，可作为线性代数后端边界的参考。 |
| SUNDIALS | 实现 / 接口 | [v7.9.0 · ida.h](https://github.com/LLNL/sundials/blob/312fc0f3684f27209ca9dc9249d194436eb41a7a/include/ida/ida.h) | IDA 的重初始化与导数查询接口，参照未来 0D 电路 DAE 验证。 |

### CFD、高阶和网格

| 项目 | 本轮材料 | 固定入口 | 对 EONSim 的用途 |
|---|---|---|---|
| OpenFOAM | 实现 / 接口 | [64cfdf54 · fvMatrix.H](https://github.com/OpenFOAM/OpenFOAM-14/blob/64cfdf5481e156d52872271e913b273260375e84/src/finiteVolume/fvMatrices/fvMatrix/fvMatrix.H) | Foundation 14 的 fvMatrix 字段方程/求解入口，参考面通量诊断。 |
| SU2 | 实现 / 接口 | [v8.6.0 · CSinglezoneDriver.cpp](https://github.com/su2code/SU2/blob/7048fd35f56d4bf52e586429d6746a36a10255f8/SU2_CFD/src/drivers/CSinglezoneDriver.cpp) | 单区 driver 的每步求解和更新分工，可对照状态提交。 |
| NekRS | 发行说明 | [v26.0 · RELEASE.md](https://github.com/Nek5000/nekRS/blob/96b3cf9e5bacede16568826c04a21bc0fe50dc7d/RELEASE.md) | 26.0 的混合精度相关选择、设备内存和输出能力；与高阶六面体语境一并阅读。 |
| Nek5000 | 仓库说明 | [d083ef34 · README.md](https://github.com/Nek5000/Nek5000/blob/d083ef340f32fd69cc551a07c7fa56a64c743c05/README.md) | 作为谱元 CFD 对标，若切换离散方法再开展专门实测。 |
| Nektar++ | 在线源码 / 文档 | [5.10.0 Operator.h](https://doc.nektar.info/doxygen/5.10.0/_operator_8h_source.html) | Collections 的算子实现枚举，比较相同离散的执行策略。 |
| PyFR | 实现 / 接口 | [fdb13c17 · backend.py](https://github.com/PyFR/PyFR/blob/fdb13c17024084536b68dc7ef54c8a030f1cc6a2/pyfr/backends/base/backend.py) | 核及执行图的后端接口，适合批次/调度试点。 |
| Trixi | 仓库说明 | [bdc0a5a7 · README.md](https://github.com/trixi-framework/Trixi.jl/blob/bdc0a5a71c5af4e95d27349e0f1d854f4144330a/README.md) | DG/高阶双曲求解可用作未来输运模块对照。 |
| Code_Saturne | 仓库说明 | [5d63c158 · README.md](https://github.com/code-saturne/code_saturne/blob/5d63c1583d5526275dcb7d678d3b0f3c9f863731/README.md) | 非结构 CFD 工程案例和数据组织参考。 |
| AMReX | 实现 / 接口 | [26.11 · AMReX_FabArray.H](https://github.com/AMReX-Codes/amrex/blob/72d668eb80d1737e4550a5abf2fca5fcbc8ba637/Src/Base/AMReX_FabArray.H) | 分块网格 ghost 通信的发起与完成接口。 |
| t8code | 实现 / 接口 | [v4.0.0-26.11 · t8_forest_general.h](https://github.com/DLR-AMR/t8code/blob/fb60a9b09b1322999a77954b14ef1cd364a479b3/src/t8_forest/t8_forest_general.h) | 树网格适配、重分区和 ghost 的生命周期。 |
| MFiX-Exa | 官方文档 | [模型与用户手册](https://mfix.netl.doe.gov/doc/mfix-exa/guide/latest/) | 基于 AMReX 的多相 CFD 应用，复查公开说明与源码获取范围。 |

### 流固耦合、材料和多物理应用

| 项目 | 本轮材料 | 固定入口 | 对 EONSim 的用途 |
|---|---|---|---|
| svFSI | 实现 / 接口 | [2022.09.26 · FLUID.f](https://github.com/SimVascular/svFSI/blob/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571/Code/Source/svFSI/FLUID.f) | 按与 #41/#42 相同的 Fortran 版本比对稳定化与参考算例。 |
| svMultiPhysics | 实现 / 接口 | [f598b82e · Integrator.h](https://github.com/SimVascular/svMultiPhysics/blob/f598b82eecd418f07b42e42ecb9f2339155015fa/Code/Source/solver/Integrator.h) · [补充源码](https://github.com/SimVascular/svMultiPhysics/blob/f598b82eecd418f07b42e42ecb9f2339155015fa/Code/Source/solver/Integrator.cpp) | 核查 C++ Integrator 的 predictor 与状态处理，用于时间层对齐。 |
| svZeroDSolver | 实现 / 接口 | [29e32b2d · WindkesselBC.cpp](https://github.com/SimVascular/svZeroDSolver/blob/29e32b2d9961e372ec5f8533200944cefa66f994/src/model/WindkesselBC.cpp) | RCR 压力状态、阻力、顺应性和远端压力的独立对照。 |
| PERIGEE | 实现 / 接口 | [329fe343 · PNonlinear_FSI_Solver.cpp](https://github.com/APSIS-ANALYSIS/PERIGEE/blob/329fe3433b6edc3363f107b7096efdf2fc77c4a7/examples/fsi/src/PNonlinear_FSI_Solver.cpp) | 速度–压力求解和独立网格求解的真实调用顺序及计时。 |
| preCICE | 实现 / 接口 | [v3.5.0 · IQNILSAcceleration.cpp](https://github.com/precice/precice/blob/e72f2ffe90094fa3516aee4f5115fb38a65543e9/src/acceleration/IQNILSAcceleration.cpp) | IQN-ILS 的 QR、空接口进程和分布式残差处理。 |
| 4C | 实现 / 接口 | [29716fd2 · 4C_fsi_algorithm.hpp](https://github.com/4C-multiphysics/4C/blob/29716fd2f85002bdda4b13dbfa353b278ee51e5d/src/fsi/src/4C_fsi_algorithm.hpp) | FSI 驱动对字段适配器的职责边界，可作独立实现比较。 |
| IBAMR | 实现 / 接口 | [c49a3001 · IBHierarchyIntegrator.cpp](https://github.com/IBAMR/IBAMR/blob/c49a300101830ac84b158f3bd1f5e420b729de9f/src/IB/IBHierarchyIntegrator.cpp) | 层级积分器管理浸入边界时间步，触及瓣膜/非匹配界面再作专项。 |
| MOOSE | 实现 / 接口 | [d5218841 · NonlinearSystemBase.C](https://github.com/idaholab/moose/blob/d5218841df590f5450df1b7e2e378e068ea0a69d/framework/src/systems/NonlinearSystemBase.C) | 按 tag 的残量与雅可比求值，帮助区分诊断范围。 |
| Kratos | 实现 / 接口 | [684b53ad · element.h](https://github.com/KratosMultiphysics/Kratos/blob/684b53ad9c510ecb1d8420cef0c20185ca60a58e/kratos/includes/element.h) | Element 局部系统与单独右端项接口，适合比较残量/切线入口。 |
| DAMASK | 仓库说明 | [4e3beb90 · README.md](https://github.com/damask-multiphysics/DAMASK/blob/4e3beb900e5c9b60c21922064fb5378555899d51/README.md) | 材料点本构与不同求解器组合，供血管壁材料历史设计借鉴。 |
| FEBio | 仓库说明 | [552138d6 · README.md](https://github.com/febiosoftware/FEBio/blob/552138d63795563ddc0346abdd7aa1fb91000bdd/README.md) | 生物力学有限元案例，供复杂材料及加载工况对照。 |
| OpenSees | 仓库说明 | [1290bd61 · README.md](https://github.com/OpenSees/OpenSees/blob/1290bd61eecbf235bb7481cca0878721ee128279/README.md) | 结构响应与时间积分的独立对照候选。 |
| Elmer | 实现 / 接口 | [ec425e40 · MainUtils.F90](https://github.com/ElmerCSC/elmerfem/blob/ec425e40abd94db563969d1804cb4345abcc9980/fem/src/MainUtils.F90) | MainUtils 中模型与求解器驱动，供多物理编排参考。 |
| Chrono | 仓库说明 | [e166f3e5 · README.md](https://github.com/projectchrono/chrono/blob/e166f3e5a1383741e86cf1e195a46eba4a66473d/README.md) | 刚体及多体与流体交互，适合作接触/瓣膜阶段的候选。 |
| SPHinXsys | 仓库说明 | [c13c78b6 · README.md](https://github.com/Xiangyu-Hu/SPHinXsys/blob/c13c78b6304acbf22f9263c72ebf0037969b6c94/README.md) | 粒子多物理案例，为大变形或非贴体路线提供对照。 |
| OpenGeoSys | 仓库说明 | [78a1a83f · README.md](https://github.com/ufz/ogs/blob/78a1a83f15d1a8463544efb9698d190e4670afca/README.md) | THMC 多场应用，核对官方项目说明及主开发镜像位置。 |
| GEOS | 仓库说明 | [516fa5f2 · README.md](https://github.com/GEOS-DEV/GEOS/blob/516fa5f2d1d58b86de3e2900b11be7350eb60331/README.md) | 多物理地下流应用，作为区域/本构组织的后续参照。 |
| Palace | 仓库说明 | [b4327c8d · README.md](https://github.com/awslabs/palace/blob/b4327c8d35b4bebac69b53e6a6563ea1b255fdf5/README.md) | 电磁有限元应用，作为未来独立物理模块封装的参照。 |
| Chaste | 仓库说明 | [357af77f · README.md](https://github.com/Chaste/Chaste/blob/357af77f3d8b47aa179dbebbdde04c89ce3f2aca/README.md) | 心脏建模及可复现实例，留作电生理与力学扩展参考。 |

MFiX-Exa 官方说明通过 NETL 周期性发布源码包，下载入口要求注册，本轮以公开文档为据。OpenGeoSys 使用注明主开发站的 GitHub 镜像，仅据此核对项目定位。[MFiX-Exa 获取说明](https://exa-doc.s3.amazonaws.com/user-manual/latest/user_guide/quick-start.html) · [OpenGeoSys 主开发站](https://gitlab.opengeosys.org/ogs/ogs)
