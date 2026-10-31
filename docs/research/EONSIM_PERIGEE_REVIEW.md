# EONSim 与 PERIGEE：本地源码审查依据

阅读提示：下文 EONSim 指该次审查的原工程快照，不是当前 EONSim-new 的能力清单；其串行/全局场路径限制不能移作当前实现结论。当前进度见 [项目状态](../development/CODEX_PROGRESS.md)。

状态：研究记录，不作为新的强制流程。审查日期：2026-10-29。当前规范见根目录 MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md。

当前项目已选择 [单体刚体 → 单体弹性体 FSI](../architecture/L2_MONOLITHIC_FSI.md)。下述参考项目的分段/分离式实现属于研究事实，不构成本项目先开发分离式算法的要求。

本文是设计基线，不代表软件已经实现。依据是两个本地工作树的构建配置、应用入口、网格/自由度、装配、求解、时间推进及耦合实现；没有重新编译、运行两套工程或测量其性能。EONSim 审查基线 HEAD 为 `1074f9d6cfa3c43fc5cd7a7f527371ef6d4eec5e`，含现有未提交改动；PERIGEE HEAD 为 `201eae4a4821f3a733ccbd20b72537169d32839c`，另有未跟踪 `audit/`。结论针对这些本地版本，已有报告仅作辅助证据。

## 从两套代码中得到的架构判断

### PERIGEE：围绕完整计算流程组织

实际主链为：`preprocess.cpp → 分区 HDF5 → driver.cpp → PTime_FSI_Solver → PNonlinear_FSI_Solver → PGAssem_FSI / PLocAssem → PETSc → 独立后处理`。[P1–P6]

| 观察到的实现 | 应吸收的思想 | 新工程中的取舍 |
|---|---|---|
| 预处理使用 METIS、节点重编号，按 rank 写分区；求解器读取本 rank 数据 | 将全局准备工作移出反复执行的求解循环 | 首版允许串行离线分区；求解阶段必须只驻留本地网格及必要 ghost |
| `APart_Node` 显式区分 local/ghost；`PDNSolution` 用 `VecCreateGhost` | 所有权和邻居数据是核心模型 | 一个统一 `MeshPartition`/`DofMap`，不用全局向量复制冒充分布式 |
| `PLocAssem` 形成单元残量/切线，`PGAssem` 写入全局矩阵 | 局部数学与并行装配分开 | 保留这条边界，局部缓冲区改用 RAII；不照搬大量默认空实现的虚函数 |
| `PGAssem_FSI` 探测非零图，再按对角/非对角非零数精确预分配 | 内存结构先确定，数值反复更新 | 先实现可靠 AIJ 预分配；装配成为瓶颈后再切换缓存 COO |
| 流体、固体局部核形成速度/压力块，driver 用 `PCFieldSplitSetIS` | 物理场布局要能直接指导预条件 | DoF 层产生显式 field index set，不依赖猜测矩阵排列 |
| generalized-α 同时管理状态及其导数；材料拆分等容/体积响应 | 时间层、材料层、空间装配各有明确责任 | 首版 BE 跑通；动力学需求出现后再引入 generalized-α 和混合固体 |
| FSI 的力学场组合装配，Newton 内另解网格运动 | 对耦合强度作有意识的算法选择 | 不把该路径概括为“所有未知量一次完全单体求解” |

PERIGEE 值得学的是“分区数据进入真实求解器”的直接性。其首版可接受的限制也很清楚：串行预处理有全局内存上限；FSI 中有相同局部基函数数目的假设；大量公共接口和具体求解器带有 PETSc/领域类型。新工程应保持计算链简洁，同时缩小接口和可变状态的范围。[P1、P3、P7]

### EONSim：围绕能力复用与模块化演进

EONSim 已建立 `core / mesh / linalg / discretization / physics / multiphysics / runtime / compiler` 等模块，实体化 DoF、标量输运算子、时间历史与 owned/ghost 向量均有具体实现。[E1–E5]

| 观察到的实现 | 应吸收的思想 | 需要避免的演进成本 |
|---|---|---|
| 目录契约要求能力落在最低可复用层，应用只组合组件 | 按职责归属，而非按某个算例堆代码 | 不一次复制完整目标目录树，只创建当前需要的模块 |
| `DofManager` 区分实体、字段、分量；标量核统一 capacity/diffusion/advection/reaction | 网格与场解耦，热与组分输运共用数学结构 | 首版只做 P1，保留字段语义；不为尚未实现的高阶族增加复杂分支 |
| `DistributedVectorExchange` 缓存 halo，先算内部行再等待边界值 | 通信计划复用，并给通信/计算重叠留出空间 | 首版用 PETSc ghost 通信；不要同时维护第二套完整通信系统 |
| `SolutionHistory` 有 accept/snapshot/rollback | 已接受状态与试算状态分开 | 先实现一次 accept 和明确失败退出，自动回退策略后加 |
| PETSc A9 缓存 COO，但注释仍说明单 rank/单活跃非线性矩阵 | 固定图上的数值更新可以单独优化 | 不把局部装配提速等同于全流程 HPC 扩展性 |
| 模型编译器与多种离散方法已有参考路径 | 长期可以把建模描述与执行计划分开 | 首版直接配置具体物理模块，暂不引入 IR、DSL、JIT 和插件 ABI |

**必须据源码修正的三点认识：**

- 分布式基础组件存在，不代表所有上层求解都已分布式。当前 `petsc_snes_solver.cpp` 的生产非线性 CSR 迁移入口检查完整串行 Jacobian，并要求 `communicator_size == 1`；其限制不能推广为“EONSim 所有求解器只支持单 rank”。[E6]
- 当前主应用有逐 rank 读取完整网格、瞬态流动收集完整向量的路径。新工程必须先打通本地状态到局部残量/Jacobian 的链，再讨论大规模 FSI。[E7]
- 架构目标与实际依赖图要分别看：当前 `eonsim_linalg` 的公共依赖包含 `Compiler` 和 `DG`。这说明部分桥接已进入底层；新工程应把编译模型到求解器的适配放在上层，保持代数层独立。[E8]

此外，现有 CHT 文档明确区分了共形接口/解析参考与完整生产 CHT 求解；不能直接将几个 reference 示例合并宣称为流固热求解器。[E9]

### 综合选择

采用 **“小核心＋具体物理模块＋显式耦合驱动”**：以 PERIGEE 的真实分区计算链为执行骨架，以 EONSim 的职责划分和局部算子复用为组织原则。复用两者的数学与数据设计，不整库搬运历史兼容层、验证流程和所有功能开关。

## 本地源码证据索引

下列 `路径:行号` 相对原审查工程根目录：P 项为 PERIGEE，E 项为原 EONSim。对应提交见本文开头；原机器 C:/E: 链接不可移植，改为文本定位，不冒充当前仓库链接。这些来源本次未重新取得，不能构成新的运行验证。

| 编号 | 阅读入口及主要依据 |
|---|---|
| P1 | PERIGEE FSI 预处理（`examples/fsi/preprocess.cpp:358`）：METIS/重编号/逐 rank 分区写出；FSI driver（`examples/fsi/driver.cpp:247`）：按 rank 读取分区 |
| P2 | APart_Node（`include/APart_Node.hpp:1`）；PDNSolution（`src/Solver/PDNSolution.cpp:10`）：owned/ghost 与 PETSc ghost vector |
| P3 | PGAssem_FSI（`examples/fsi/src/PGAssem_FSI.cpp:3`）：精确预分配、局部核到全局矩阵；局部 ALE-VMS 核（`examples/fsi/src/PLocAssem_2x2Block_ALE_VMS_NS_GenAlpha.cpp:3`）：局部块、时间层、稳定项 |
| P4 | field-split 配置（`examples/fsi/driver.cpp:536`）；PETSc 线性求解封装（`src/Solver/PLinear_Solver_PETSc.cpp:3`） |
| P5 | FSI 非线性推进（`examples/fsi/src/PNonlinear_FSI_Solver.cpp:142`），其中 网格单独求解（`examples/fsi/src/PNonlinear_FSI_Solver.cpp:316`）；时间步收敛后提交（`examples/fsi/src/PTime_FSI_Solver.cpp:116`） |
| P6 | generalized-α（`src/Solver/TimeMethod_GenAlpha.cpp:1`）；材料组合（`include/MaterialModel_Mixed_Elasticity.hpp:1`）；项目流程说明（`README.md:1`） |
| P7 | 局部装配公共接口（`include/IPLocAssem.hpp:20`）；构建设置（`cmake/PerigeeSetup.cmake:10`）；应用选择（`CMakeLists.txt:1`） |
| E1 | 源码归属与依赖契约（`docs/architecture/SOURCE_LAYOUT_AND_OWNERSHIP.md:1`） |
| E2 | 实体化 DoF（`include/dof_manager.hpp:20`）；共享标量输运（`include/scalar_transport_operator.hpp:12`） |
| E3 | 分布式向量契约（`include/distributed_matrix.hpp:64`）；halo 与内部/边界行计算（`src/linalg/distributed_matrix.cpp:660`） |
| E4 | 时间历史（`include/time_integrators.hpp:18`）；分布式标量装配入口（`include/distributed_assembly.hpp:13`） |
| E5 | 模型编译入口（`src/compiler/model_compiler.cpp:287`）；COO 缓存作用域（`src/linalg/petsc_a9_cached_coo.cpp:54`）；A9 构建桥接（`src/CMakeLists.txt:5`） |
| E6 | 完整串行 CSR 检查（`src/linalg/petsc_snes_solver.cpp:51`）；单 rank 入口限制（`src/linalg/petsc_snes_solver.cpp:737`） |
| E7 | 瞬态流动完整向量收集（`applications/eonsim/main.cpp:297`）；网格读取（`applications/eonsim/main.cpp:2307`）；已有 D0 报告（`docs/D0_DIST_A1_GATE_REPORT.md:1`），仅作历史辅助 |
| E8 | 实际 Linalg target 依赖（`cmake/EONSimLibraries.cmake:386`） |
| E9 | CHT reference 范围（`docs/STAGE07_FLOW_THERMAL_CHT_GAP_ANALYSIS.md:1`）；非匹配接口参考限制（`include/interface_coupling.hpp:64`） |
| E10 | 构建 preset（`CMakePresets.json:26`）；顶层选项（`CMakeLists.txt:1`） |
