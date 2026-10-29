# 九个上游项目的架构研究与取舍

研究日期：2026-10-29。状态：研究依据，**不自动成为本项目依赖或开发门禁**。

本次读取官方仓库 README、关键接口/示例和官方技术文档，未克隆完整仓库、编译、跑性能或逐行审计全部实现。下述“观察”描述已阅读的材料，“采用/延期”是对本项目的设计判断。默认分支可能是开发分支；下列 SHA 用于固定研究证据，不代表推荐使用这些开发版本作为依赖。

## 研究快照

| 项目 | 读取分支 | 固定 commit |
|---|---|---|
| [CEED/libCEED](https://github.com/CEED/libCEED) | main | `5d79e7f706491bfc59538f31402d0cd075762c21` |
| [mfem/mfem](https://github.com/mfem/mfem) | master | `d259866bb8e42b13042907308cdba11947778a4e` |
| [dealii/dealii](https://github.com/dealii/dealii) | master | `f8c1bebcf6d5d3a97a404ed2ad6c553f3820b411` |
| [KratosMultiphysics/Kratos](https://github.com/KratosMultiphysics/Kratos) | master | `11e646f21d2d9afc81265c4236176701c10a307c` |
| [idaholab/moose](https://github.com/idaholab/moose) | next | `738016cea7d7da39d08fa470faab2e9153f45fe4` |
| [4C-multiphysics/4C](https://github.com/4C-multiphysics/4C) | main | `d3a2cfc7ef3e68366b6544a39b55003c1483e93d` |
| [lifev/lifev](https://github.com/lifev/lifev) | master | `1099b021d80ba3009449716cc0f47afba0baf025` |
| [SimVascular/svMultiPhysics](https://github.com/SimVascular/svMultiPhysics) | main | `b9c2ddc68a5f4ae3afb8f1608758c294843bae8c` |
| [kokkos/kokkos](https://github.com/kokkos/kokkos) | develop | `ee6c96c4749070e182849cb9a06fab92b2efb0f5` |

用户输入中连在一起的 URL 已分别解析为 deal.II、Kratos、svMultiPhysics 和 Kokkos 四个独立项目。

## libCEED：把局部离散表达为可执行算子

**观察：** libCEED 将自由度收集、基函数求值、积分点物理与转置累加分开。其 API 工作重点在局部 L-vector 层；全局向量、跨 rank 通信和全局求解由宿主程序管理。示例把几何积分数据构建与质量算子作用分成两个 operator。[接口理论](https://libceed.org/en/latest/libCEEDapi/)、[固定源码：ex1-volume.c](https://github.com/CEED/libCEED/blob/5d79e7f706491bfc59538f31402d0cd075762c21/examples/ceed/ex1-volume.c)

**采用：** 局部 kernel 不依赖 PETSc/MPI；积分点物理与形函数、几何映射分开；区分 setup 数据与每次 apply 数据。首版 assembled 可以保持这条结构，并不要求先接 libCEED。

**延期：** 高阶、设备算子或矩阵内存成为瓶颈时，再做 libCEED adapter。它不代替分区、约束、时间步和非线性预条件器。不能仅因 kernel 上 GPU 就称为端到端 GPU 求解。

## MFEM：网格、空间、场、形式与代数系统之间有清楚转换

**观察：** ex1p 明确经历 ParMesh、ParFiniteElementSpace、ParBilinearForm、FormLinearSystem、求解与 RecoverFEMSolution；同一示例选择 full/partial assembly，并配相应预条件。这里的场向量和求解器 true DoF 向量不是可随意混用的同一概念。[固定示例](https://github.com/mfem/mfem/blob/d259866bb8e42b13042907308cdba11947778a4e/examples/ex1p.cpp)、[官方装配说明](https://mfem.org/performance/)

**采用：** 明确“网格拓扑—有限元空间—场值—受约束代数未知量”的转换；算子表达与存储方式分开；示例作为完整计算链，而不是只有零散单元测试。

**取舍：** 若项目目标主要是常规 FEM 多物理应用，应先考虑直接用 MFEM 承担网格/空间/装配，比重写所有基础设施更快。若主要研究特殊离散或需精确控制内核，则保留小型自有 FEM。两条路线只选一条为主路径，不能同时维护两套全功能网格/DoF。

**边界：** 文档和分支对具体单元/积分器的 partial assembly 支持可能不同；采用时对目标单元、目标算子核对，本文不把某个概览页面的支持范围当成所有版本的事实。

## deal.II：约束是离散层的正式对象

**观察：** step-6 把悬挂节点和边界值放进 AffineConstraints，并在局部到全局散入时处理；FEValues 按 update flags 计算所需几何/形函数量。step-37 将 MatrixFree 的映射/索引缓存与具体算子作用分开，并为平滑器提供对角信息。[step-6](https://github.com/dealii/dealii/blob/f8c1bebcf6d5d3a97a404ed2ad6c553f3820b411/examples/step-6/step-6.cc)、[step-37](https://github.com/dealii/dealii/blob/f8c1bebcf6d5d3a97a404ed2ad6c553f3820b411/examples/step-37/step-37.cc)

**采用：** 约束统一进入编号、图结构、装配和解恢复；只计算 kernel 需要的几何量；共享几何/DoF 缓存，而不是每种物理场重建一份。

**延期：** AMR、hp、多重网格和复杂模板体系随真实需求引入。学习抽象边界，不把教程中的全部类层级变成首版前置设施。

## Kratos：领域模型与分析生命周期分离

**观察：** ModelPart 管理节点/单元/边界实体与子模型；AnalysisStage 将初始化、推进、预测、求解、完成和输出组织成外层生命周期。C++ 内核配合 Python 调度提供应用扩展入口。[ModelPart](https://github.com/KratosMultiphysics/Kratos/blob/11e646f21d2d9afc81265c4236176701c10a307c/kratos/includes/model_part.h)、[AnalysisStage](https://github.com/KratosMultiphysics/Kratos/blob/11e646f21d2d9afc81265c4236176701c10a307c/kratos/python_scripts/analysis_stage.py)、[项目说明](https://github.com/KratosMultiphysics/Kratos/blob/11e646f21d2d9afc81265c4236176701c10a307c/README.md)

**采用：** 用有名字的区域/边界视图表达物理归属；配置和编排在外层，局部数值在 C++ 内层；用户流程有少数明确阶段。

**取舍：** 本项目首版通过 C++ 直接组合即可，Python 不是必要依赖；不复制全局变量注册表、所有 application/plugin 和任意时刻都可插入回调的框架。这里借鉴生命周期组织，不把某个基类循环直接复制为本项目的收敛提交策略。

## MOOSE：按弱式项和材料属性组织物理

**观察：** Kernel 表示弱式残量项，Materials 生产供 kernel 消费的属性；Executioner 管理求解和时间推进。MultiApps/Transfers 组织独立应用之间的数据交换和耦合迭代，与单一方程系统的完全耦合不是同一个实现层级。[Kernels](https://github.com/idaholab/moose/blob/738016cea7d7da39d08fa470faab2e9153f45fe4/framework/doc/content/syntax/Kernels/index.md)、[Materials](https://github.com/idaholab/moose/blob/738016cea7d7da39d08fa470faab2e9153f45fe4/framework/doc/content/syntax/Materials/index.md)、[Executioner](https://github.com/idaholab/moose/blob/738016cea7d7da39d08fa470faab2e9153f45fe4/framework/doc/content/syntax/Executioner/index.md)、[MultiApps](https://github.com/idaholab/moose/blob/738016cea7d7da39d08fa470faab2e9153f45fe4/framework/doc/content/syntax/MultiApps/index.md)

**采用：** 材料和残量项分开；材料参数依赖当前温度/变形时，残量与切线保持相容；清楚区分“一个系统内的耦合”和“多个应用交换数据”。

**取舍：** 可先把多个弱式项融合在一个具体热/流体 kernel 内实现，理解上可组合不意味着每个乘法都建对象。AD 先用于容易出错的局部材料/耦合导数；不因存在 AD 就取消所有数值检查，也不复制完整 Action/Factory/Warehouse 系统。

## 4C：耦合算法依赖字段适配接口

**观察：** Field adapter 暴露 RHS、DoF map、矩阵和时间步 prepare/evaluate/update 等操作；FSI Algorithm 对流体/结构及传递进行组合，monolithic/partitioned 实现在不同目录。接口中的增量含义有具体约定，不能由调用方自行猜测。[Field adapter](https://github.com/4C-multiphysics/4C/blob/d3a2cfc7ef3e68366b6544a39b55003c1483e93d/src/adapter/4C_adapter_field.hpp)、[FSI Algorithm](https://github.com/4C-multiphysics/4C/blob/d3a2cfc7ef3e68366b6544a39b55003c1483e93d/src/fsi/src/4C_fsi_algorithm.hpp)

**采用：** 耦合驱动通过少量能力接口连接各场；字段内部离散/材料细节不暴露给接口传递。单体和分区可共用场残量，耦合算法保持独立。

**取舍：** 先实现具体 FSI 适配器，第二种耦合确实需要时再提炼 Field 接口。不要复制 4C 的广泛 adapter 网络或全局问题对象；“增量相对上一步还是上次 Newton”的语义应成为项目明确约定。

## LifeV：多尺度耦合应交换具有物理意义的量

**观察：** MultiscaleInterface 定义流量、平均法向应力/总应力、面积及其变化量的边界接口；CommunicatorsManager 为不同模型分配 communicator。GitHub README 明示项目已迁移到 Bitbucket，因此此仓库只用于历史设计学习，不据此推断今天的维护和兼容状态。[接口](https://github.com/lifev/lifev/blob/1099b021d80ba3009449716cc0f47afba0baf025/lifev/multiscale/framework/MultiscaleInterface.hpp)、[communicator 管理](https://github.com/lifev/lifev/blob/1099b021d80ba3009449716cc0f47afba0baf025/lifev/multiscale/framework/MultiscaleCommunicatorsManager.hpp)、[迁移说明](https://github.com/lifev/lifev/blob/1099b021d80ba3009449716cc0f47afba0baf025/README.md)

**采用：** 0D/1D/3D 端口传递明确的流量、压力或法向应力、面积和时间层；压力与平均法向应力不能无条件视为相同量。组件接收 communicator，不在内部到处写死 MPI_COMM_WORLD。

**延期：** 首版各场共用 communicator；模型子通信域、独立资源分配和多速率耦合在确有工作负载时加入。不把历史 Epetra/Trilinos 依赖组合直接移植为新工程基线。

## svMultiPhysics：保护完整应用链，逐步收拢历史状态

**观察：** README 说明 C++ 版本源自 svFSI 的 Fortran 迁移，存在过程式遗产；当前源码已经包含 Integrator、SolutionStates、LinearAlgebra 等封装。SolutionStates 明确 old/current/intermediate，Integrator 管理 generalized-α/Newton；线性代数接口可接不同实现。[README](https://github.com/SimVascular/svMultiPhysics/blob/b9c2ddc68a5f4ae3afb8f1608758c294843bae8c/README.md)、[Integrator](https://github.com/SimVascular/svMultiPhysics/blob/b9c2ddc68a5f4ae3afb8f1608758c294843bae8c/Code/Source/solver/Integrator.h)、[SolutionStates](https://github.com/SimVascular/svMultiPhysics/blob/b9c2ddc68a5f4ae3afb8f1608758c294843bae8c/Code/Source/solver/SolutionStates.h)、[LinearAlgebra](https://github.com/SimVascular/svMultiPhysics/blob/b9c2ddc68a5f4ae3afb8f1608758c294843bae8c/Code/Source/solver/LinearAlgebra.h)

**采用：** 重构围绕实际应用链逐段进行；时间层和状态所有权要显式；新核心优先收窄传参边界。不要因为代码历史长就整体重写，也不要把 ComMod 一类大型共享上下文继续扩散成所有物理场的唯一入口。

**边界：** 当前 DEVELOPMENT_PRINCIPLES 自称为选定的初始原则，不能当成“全部已落实”的证据。学习其简单性和组合思想；测试/CI 频率仍按本项目精简规则执行。[设计原则说明](https://github.com/SimVascular/svMultiPhysics/blob/b9c2ddc68a5f4ae3afb8f1608758c294843bae8c/DEVELOPMENT_PRINCIPLES.md)

## Kokkos：执行空间、内存空间、布局各自显式

**观察：** Kokkos 用 execution space、memory space、View 和 parallel dispatch 表达节点内计算。View 复制通常是共享底层存储的浅复制；主机访问设备数据需要满足内存可访问性，异步工作有同步语义。读取时的 README 要求 C++20 或以上。[固定 README](https://github.com/kokkos/kokkos/blob/ee6c96c4749070e182849cb9a06fab92b2efb0f5/README.md)、[View 文档](https://kokkos.org/kokkos-core-wiki/ProgrammingGuide/View.html)、[fence 文档](https://kokkos.org/kokkos-core-wiki/API/core/parallel-dispatch/fence.html)

**采用：** 首版即区分 owner 和 view、数据布局和数据生命周期；明确是谁让数据在何处就绪。引入 GPU 后，状态快照不能用浅复制冒充独立历史；计时不能只测异步 kernel 提交时间。

**取舍：** Kokkos 不代替 MPI/全局求解，亦不等于 libCEED。优先选一个局部执行路线：自有 kernel＋Kokkos，或 libCEED backend；只有具体互操作收益成立时才叠加，避免两套设备存储互相搬运。

## 对本项目的六项新增决定

1. **先确认产品边界。** 常规 FEM 应用优先评估复用 MFEM/deal.II；特殊离散研究才自建对应部分。当前默认仍是一条 PETSc＋小型 FEM 路径，若选库则替换这一职责，不并行造第二套。
2. **将形式与表示分开。** 同一离散问题先 assembled，后续可 partial/matrix-free；求解 operator 与预条件矩阵允许不同。
3. **约束、单位和耦合符号早定。** 这些错误晚修代价高；通用 DSL、全功能注册表和大规模插件框架可以晚做。
4. **引入明确的状态提交点。** 残量/Jacobian 计算不可偷偷提交材料和 0D 历史；所有必要场共同接受时间步。
5. **设备数据只由一个边界负责。** 明确 owner/view、读写、同步、MPI 缓冲生命周期；不多层重复转换。
6. **保留最小验证，不复制上游流程体量。** 上游大规模测试、CI 和兼容矩阵服务其规模；本项目仍以一个相关真实小算例推进。

这些决定的生效位置见 [总原则与分层入口](../../MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md)。研究文件提供理由，实际约束由 L0/L1/L2/L3 文件按主题维护。

