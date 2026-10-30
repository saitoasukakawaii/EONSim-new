# 20 组上游项目的学习路线与 EONSim 取舍

日期：2026-10-30。EONSim 源码基线：`38a5e516ffe129d1b70c7c1bd8365deb5ded101a`（PR #21）。本文研究官方文档、教程和作者论文，**没有编译这些项目，没有逐个审计完整源码，也没有进行性能横评**。用户给出的顺序保留为索引，不视为质量或性能排名。在线 `latest/release/master` 会变化；下面是访问当日的设计证据，不是依赖版本锁。

配套决策见 [通用 FEM 架构规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md)。2026-10-29 的固定源码快照仍保留在 [原上游研究](UPSTREAM_ARCHITECTURE_REVIEW.md)，不可将其 SHA 说成今天最新版本。

## 学习矩阵

每行的“迁移产物”是建议以后在 EONSim 验证的设计，不表示上游采用 EONSim 的数值方案，也不表示要链接该依赖。

| 序号 / 项目 | 官方阅读入口与重点 | EONSim 的具体迁移产物 | 暂不照搬的部分 |
|---|---|---|---|
| 1 Firedrake | [项目与功能](https://www.firedrakeproject.org/)：UFL、代码生成、PETSc、空间与算子预条件 | 用户弱式/模型描述 → 已校验的问题计划 → native kernel；保存生成来源和诊断映射 | 完整 PDE 编译器、JIT 工具链不作为近期前置工作 |
| 2 PETSc/DMPlex | [DMPlex](https://petsc.org/release/manual/dmplex/) 的 topology、section、closure；[field IS](https://petsc.org/release/manualpages/PC/PCFieldSplitSetIS/) | 实体与 DoF 分离，独立字段布局、owner/ghost；用任意 IS 建预条件树；作为并行网格管理首选评估候选 | DMPlex 本身不自动赋予 EONSim 任意单元、非匹配 FSI 或正确弱式 |
| 3 deal.II | [step-37](https://dealii.org/current/doxygen/deal.II/step_37.html)：FEEvaluation、向量化、matrix-free 与多重网格 | 固定类型批处理、约束进入 gather/scatter、算子和预条件共同设计；参考已有 step-6 约束研究 | 不为低阶 Tet4 直接复制整套高阶多重网格框架 |
| 4 MFEM | [FEM 结构](https://mfem.org/fem/)、[装配层次](https://mfem.org/performance/) | Mesh / FESpace / Form / Operator 分离；true DoF、assembled / partial assembly 切换 | 官网特定页面的单元支持描述不代替目标版本能力测试；整库替换需单独选择 |
| 5 libCEED | [Interface Concepts](https://libceed.org/en/latest/libCEEDapi/)：restriction、basis、QFunction | 局部算子表达与存储/设备解耦；积分点核不接触 MPI/PETSc；未来矩阵自由 adapter | 它不是全套网格、分区、边界条件和全局求解器 |
| 6 Trilinos/Phalanx/Panzer | [Phalanx 指南](https://trilinos.github.io/docs/phalanx/user_guide.html)、[Panzer](https://trilinos.github.io/panzer.html)：字段评价依赖、evaluation type、Sacado | 残量 / 切线 / Jv 共用物理表达；准备期检查材料输入输出依赖，选择所需子计算 | 先用小型静态计划；不引入 Trilinos 第二套线性代数，也不逐积分点调度动态 DAG |
| 7 AMReX | [MultiFab](https://amrex-codes.github.io/amrex/tutorials_html/MultiFab.html)、[GPU 支持](https://amrex-codes.github.io/amrex/docs_html/GPU.html) | 批次数据布局、显式 halo、内存驻留、计算/通信完成责任 | block-structured AMR 数据模型不等同于非结构 FEM 网格 |
| 8 DUNE | [设计简介](https://dune-project.org/about/dune/)、[grid interface](https://www.dune-project.org/modules/dune-grid/) | traits、轻量 view、拓扑与坐标映射分离；静态多态表达局部算法 | 通用接口应有两个真实使用者后再提炼，不能仅追求模板层数 |
| 9 NGSolve | [Symbolic Integrators](https://docu.ngsolve.org/latest/how_to/symbolic_integrators.html) | 试探/测试空间拥有导数与 trace 语义；非线性残量、线性化和 apply 共用表达 | 不把字符串公式解释器放入热循环；高阶空间支持仍需单独验证 |
| 10 PyFR | [Developer Guide](https://pyfr.readthedocs.io/en/latest/developer_guide.html)：Controller、Stepper、Elements、Interfaces、Backend、Mako | 时间控制与格式分开；按单元类型分批；可追溯的 native kernel 生成和后端边界 | FR 数值通量及可压缩流模型不能直接替换当前不可压稳定化 CG-FSI |
| 11 Trixi.jl | [文档与教程](https://trixi-framework.org/TrixiDocumentation/stable/)：DGSEM、flux differencing、SBP、limiter | 方程、空间离散、数值通量、时间推进分别验证；将守恒和离散熵等性质变成针对性证据 | Julia 多重分派不机械翻译成 C++ 模板；当前 FSI 不因此宣称熵稳定 |
| 12 Devito | [项目与编译器](https://www.devitoproject.org/) | 表达式依赖分析、公共子表达式、循环融合、缓存键和生成代码可检查性 | 结构网格 stencil 优化不直接适用于非结构单元 gather/scatter |
| 13 GetFEM | [GWFL](https://getfem.org/userdoc/gasm_high.html)、[generic assembly bricks](https://getfem.org/userdoc/model_generic_assembly.html) | volume / boundary / interface 的弱式项组合；自动求导前明确变量与数据的角色 | 用户声明 linear/symmetric 必须可核验；不能错误缓存依赖未知量的项 |
| 14 Kratos | [ModelPart 与共享数据](https://kratosmultiphysics.github.io/Kratos/pages/Kratos/For_Users/Crash_Course/Data_Structure/Generate_New_Modelpart.html) | 区域视图、element/condition 职责、应用与过程生命周期；同网格不同物理不复制所有权 | 不把每节点字符串变量字典和深继承作为 kernel 的数据访问方式 |
| 15 Feel++ | [文档入口](https://docs.feelpp.org/home/index.html)、[Coefficient Form PDE](https://docs.feelpp.org/toolboxes/latest/cfpdes/index.html) | C++ 弱式 DSL 与现成物理 toolbox 分层；配置、命名区域、案例可读性 | 近期只做强类型问题描述；表达式模板编译成本列入未来评估 |
| 16 ExaDG | [官方仓库](https://github.com/exadg/exadg)、[作者架构论文](https://mediatum.ub.tum.de/doc/1580268/adhcx4zk8kvk2rchke0w8l5er.Arndt2020_Chapter_ExaDGHigh-OrderDiscontinuousGa.pdf) | 高阶 DG 的矩阵自由算子、块求解和多重网格一体设计；以 time-to-solution 比较 | 不只移植高速 matvec 而遗漏粗层、平滑器和通信 |
| 17 Uintah | [作者论文：Dynamic Task Scheduling](https://www.sci.utah.edu/publications/meng10/Meng_TaskSchedulingUintah2010.pdf)，2010，task graph 与 DataWarehouse | accepted/trial 版本和任务读写依赖显式；未来任务调度的缓冲完成责任 | 目前不建设通用异步 runtime；论文性能数字不属于 EONSim |
| 18 GEOS | [Constitutive developer guide](https://geosx-geosx.readthedocs-hosted.com/en/latest/coreComponents/constitutive/docs/constitutiveDeveloperGuide.html) | 按 region / element / quadrature point 储存材料和导数；将对象管理与执行核分开 | 不为了插件自由度让积分点每次查找全局对象仓库 |
| 19 SU2 | [Software Components](https://su2code.github.io/docs_v7/Software-Components/)、[Advanced AD](https://su2code.github.io/docs_v7/Advanced-AD-Techniques/) | 预留目标泛函、Jv/VJP、几何与参数导数；伴随需完整离散链与梯度校验 | 局部 AD 切线不等于已有多步离散伴随；暂不实现优化器 |
| 20a Elmer | [CSC 官方介绍](https://docs.csc.fi/apps/elmer/)、[Solver Manual](https://www.nic.funet.fi/index/elmer/doc/ElmerSolverManual.pdf) | 多物理模型选择、边界/材料配置及成熟案例；区分松耦合迭代和整体块系统 | 不把顺序调用多个 solver 的收敛视为单体 FSI 收敛 |
| 20b oomph-lib | [The data structure](https://oomph-lib.github.io/oomph-lib/doc/the_data_structure/html/index.html) | Node / internal Data / element / problem 的职责，多物理残量组合与跨场导数 | 通用 DoF 不全在节点；避免为组合模型复制整套单物理驱动 |

## 建议的学习顺序

1. **解决当前扩展阻力：** PETSc section/IS → MFEM 空间/形式 → deal.II 约束；产物是拓扑、空间、DoF、约束四份小契约及一个现有 Tet4 对照案例。
2. **解决 FSI 正确性和使用体验：** oomph-lib、Kratos、GEOS，结合现有单体 FSI；产物是接口力/功约定、状态生命周期、字段语义与配置示例。
3. **有高阶算例后优化执行：** libCEED、deal.II、ExaDG、DUNE；产物是 assembled 与 matrix-free 相同算子的对照、预条件方案和总成本测量。
4. **表达模型成为维护瓶颈后研究编译层：** Firedrake、NGSolve、GetFEM、Feel++、Phalanx/Panzer；再用 PyFR/Devito 学习代码生成和缓存。先将现有残量表达成受限 IR，再评估是否需要一般 DSL。
5. **业务触发专项：** DG/守恒律看 Trixi；GPU/AMR 看 AMReX；异步任务看 Uintah；优化/反演看 SU2；成熟多物理配置与案例看 Elmer。

每次学习只选一个垂直问题：阅读官方概念 → 沿一条算例调用链 → 写出 EONSim 的数据/数学契约 → 未来做最小原型 → 比较正确性、内存、准备成本和总求解时间。**本轮仅完成前三类资料研究与契约规划，没有执行原型。**

## 依赖与迁移边界

- PETSc 继续作为唯一全局代数/非线性后端。目标部署当前使用的 PETSc 版本须另行核对，在线 3.26 文档不能证明现有 3.19 环境拥有相同细节。
- 若决定采用 DMPlex、MFEM 或 deal.II 管理网格/空间，先确定唯一权威 owner；EONSim 使用适配后的连续批次视图。不能让两套库同时维护可变拓扑和 DoF 编号。
- MFEM/deal.II 是替代性 FEM 承载方案；libCEED 是可选局部算子方案；AMReX/Uintah 是专项思想来源。不要组成“所有库均为必需”的技术栈。
- 移植代码前逐文件审查所选版本许可和归属，保存来源；概念借鉴、算法实现和代码复制分别记录。
- 上游宣称的性能、支持单元或稳定性不转化为 EONSim 的验收结果。性能证据必须来自同精度、同容差、同问题的本项目测量。
