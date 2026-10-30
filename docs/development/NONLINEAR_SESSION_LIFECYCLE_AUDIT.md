# PETSc NonlinearSystem 生命周期审计

日期：2026-10-30  
审计基准：main commit 0828f41b62391239b14a05e57a161defae1c8866  
范围：只读源码审计；未修改 C++ 求解器，未运行性能基准。

## 1. 结论

当前 EONSim 已经跨时间步复用了主要分布式向量和 AIJ 矩阵对象，并非每步重建整个非线性系统。每次 solve() 重新创建的主要对象是 SNES 及其内部 KSP/PC，以及 callback context、字段接受状态、诊断状态和 FieldSplit 配置。

**当前不建议立即重构为持久化 NonlinearSession。** 应先使用已有 solver_report 对多步算例进行基线测量，确认 SNES/KSP/PC 创建与 setup 是否构成可重复的主要耗时，再决定是否实施。此报告确认的是源码生命周期，不是已实测的性能瓶颈。

## 2. 调用方生命周期

四个主要驱动均在时间循环前构造一个 NonlinearSystem，并在循环中重复调用 solve()：

| 驱动 | 构造 | 时间循环 | 每步调用 |
|---|---|---|---|
| 流体 | src/physics/fluid.cpp:64 | :65 | :135 |
| 固体 | src/physics/solid.cpp:67 | :68 | :95 |
| ALE | src/physics/ale.cpp:24 | :25 | :83 |
| FSI | src/physics/fsi.cpp:102 | :103 | :176 |

因此 transient fluid、transient solid、ALE 和 FSI 的同一个 NonlinearSystem 实例跨时间步存活。稳态流体和静力固体通常只调用一次。

## 3. 对象生命周期

### 3.1 跨多个 solve() 复用

NonlinearSystem 成员持有以下对象，生命周期覆盖驱动中的时间循环：

| 对象 | 创建位置 | 当前行为 | 复用条件 |
|---|---|---|---|
| solution ghost Vec | nonlinear_system.cpp:328-337 | 每次 solve 覆盖 owned 初值并同步 ghost | communicator、owned/ghost 映射和布局不变 |
| residual ghost Vec | 同上 | 每次评价清空 owned 行并重新装配 | 布局不变 |
| scratch ghost Vec | 同上 | Jacobian 回调的残量暂存 | 布局不变 |
| AIJ Mat | 同上 | 矩阵对象及预分配图跨 solve 保留 | 稀疏图和有效 DOF 不变 |
| local_trial | nonlinear_system.hpp:47 | 本地试算数组复用 | local-to-global 长度不变 |
| AlgebraLayout | 构造函数复制 | const 布局长期持有 | 分区、有效编号、字段或稀疏图改变时重建 |

矩阵启用 MAT_NEW_NONZERO_ALLOCATION_ERR 和 MAT_KEEP_NONZERO_PATTERN。每次 Jacobian 评价会调用 MatZeroEntries 并重新装配数值，但保留 AIJ 对象和已有非零模式。矩阵图复用不等于矩阵数值复用。

### 3.2 每次 solve() 重新创建

| 对象 | 位置 | 生命周期 |
|---|---|---|
| SNES | nonlinear_system.cpp:353, 363 | solve() 局部 PetscOwner，函数退出时销毁 |
| 内部 KSP / PC | SNESGetKSP / KSPGetPC | 由 SNES/KSP 管理，随每次新建的 SNES 生命周期 |
| FieldAcceptance | solve() 局部 | 每次重新校验字段分区、约束和接受尺度 |
| Context | solve() 局部 | 保存本次 assemble 回调、约束和工作数组引用 |
| LinearDiagnostics | solve() 局部 | 保存线性求解计时及可选诊断状态 |
| FieldSplit IS | solve() 字段循环 | 每次重新创建字段索引并交给 PCFieldSplit |
| Schur 子求解配置 | schur_solver.cpp:40-67 | Schur 路径每次重新配置 PC、FieldSplit 和子 KSP |

SNESSetFunction、SNESSetJacobian、SNESSetConvergenceTest 注册的回调均引用本次 solve() 的局部 Context；KSP PreSolve/PostSolve 回调引用局部 LinearDiagnostics。若持久化 SNES，必须先把这些状态改为稳定的成员/PImpl 所有权，并明确每次 solve 如何更新回调输入。不能只把 SNES 句柄移动到类成员。

### 3.3 每次残量/Jacobian 评价

Context::evaluate()（nonlinear_system.cpp:约 255-300）执行：
1. 解向量 ghost 更新；
2. 覆盖 residual owned 部分；
3. 若请求 Jacobian，调用 MatZeroEntries；
4. 调用物理层 assemble；
5. 规约错误并完成 Vec/Mat assembly；
6. 施加约束残量行和 Jacobian 行处理。

因此，Newton 迭代中的单元积分和矩阵数值装配仍然发生；持久化 SNES 不会自动消除这些成本。

## 4. PC / Schur setup

nonlinear_system.cpp:371-425 每次 solve 读取 PETSc options、配置 KSP/PC、设置 FieldSplit 并建立字段 IS。

Schur 路径在 nonlinear_system.cpp:433-435 调用 configure_schur_solver。schur_solver.cpp:40-67 中重新设置 KSP operators、建立 velocity/pressure 或 flow/mesh/structure 分块、调用 PCSetUp，并配置子 KSP/GAMG。

非 Schur FieldSplit 的 PC setup 可能由 PETSc 延迟到第一次线性求解。因此不能只看显式 Schur setup 时间来估算所有 PC 成本。

## 5. 已有性能观测

启用 -solver_report 时，nonlinear_system.cpp:429-500 输出：
- setup_seconds：进入 SNESSolve 前的 SNES 创建、回调注册、选项和字段配置；
- schur_setup_seconds：显式 Schur 配置和 PCSetUp；
- solve_seconds：SNESSolve 整体时间，可能包含延迟 PC setup；
- assembly_seconds、ghost_seconds；
- linear_seconds、finalize_seconds；
- 当前/峰值 RSS。

这些时间不是互斥分项，solve_seconds 包含 SNESSolve 内部的装配和线性求解，不能简单相加。-linear_report 会增加额外残量和范数诊断，首轮基线优先只使用 -solver_report。

## 6. 持久化 NonlinearSession 的风险

- 回调上下文：Context、FieldAcceptance、LinearDiagnostics 和 assemble 回调当前均为 solve() 局部状态。
- 矩阵数值：时间步、速度场、SUPG/PSPG 参数、ALE 几何和 FSI 状态会改变矩阵数值。
- PC 失效：约束、FieldSplit、Schur 近似、矩阵数值和 dt 变化可能要求 PCReset/PCSetUp 或重建。
- 失败恢复：StepRejected、SNES domain error、PC/KSP 失败后，必须可靠重置上一步状态。
- PETSc options：当前每次 solve 执行 SNESSetFromOptions；持久化后须定义选项何时重新读取。
- MPI 生命周期：所有 rank 必须以相同顺序创建、reset、setup 和销毁 collective PETSc 对象。

复用 KSP/PC 句柄不等于复用预条件器数值；复用 PC 对象也不代表 GAMG hierarchy 对变化的矩阵始终有效。

## 7. 下一步：先测量

优先使用现有多步案例：
- cases/fluid/transient.yaml：独立瞬态流体，10 steps；
- cases/fsi/elastic.yaml：单体弹性 FSI，10 steps；
- 必要时增加 Schur 配置作为独立对照。

固定 commit、Release 构建、硬件、MPI/PETSc 版本、网格、rank、容差和 PETSc options。相同输入重复运行数次，报告首步与后续步，并记录每步 setup、Schur setup、SNESSolve、assembly、ghost、linear 和内存数据。比较不同预条件配置时保持物理问题、收敛准则和误差一致。

只有当每步 SNES/KSP/PC 创建与 setup 是稳定且显著的耗时，同时定义了矩阵图、矩阵数值、PC 数值和 AMG hierarchy 的失效/重建规则，才进入持久化原型开发。

## 8. 审计决定

**当前暂缓持久化 NonlinearSession。下一任务是建立多步算例的 solver setup 性能基线。**

## 9. 源码依据

审计基于 main commit 0828f41b62391239b14a05e57a161defae1c8866：
- [NonlinearSystem 接口](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/include/eonsim/nonlinear_system.hpp)
- [NonlinearSystem 实现](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp)
- [Schur solver](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/schur_solver.cpp)
- [Fluid driver](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fluid.cpp)
- [Solid driver](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/solid.cpp)
- [ALE driver](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/ale.cpp)
- [FSI driver](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fsi.cpp)
