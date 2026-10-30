# SOLVER-01：PETSc 非线性对象生命周期审计

日期：2026-10-30。源码基线：`0828f41b62391239b14a05e57a161defae1c8866`。结论：**需要额外测量，暂不实施持久化 SNES 重构。** 本任务只审计，不修改求解器。

## 调用链与所有权

| 对象 | 创建及所有权 | 更新与销毁 |
| --- | --- | --- |
| NonlinearSystem | fluid.cpp:64、solid.cpp:67、fsi.cpp:102 在时间循环之前构造 | 驱动结束时析构；不在每个 Newton 迭代新建 |
| solution/residual/scratch Vec、ghost 布局、AIJ Mat | nonlinear_system.cpp:328 构造，成员 PetscOwner 持有 | 跨时间步和缩步尝试保留；类析构释放 |
| SNES | nonlinear_system.cpp:353、363，每次 solve 的局部 PetscOwner | 每次 solve 返回或异常退出释放；一次 solve 内跨 Newton 迭代保留 |
| 顶层 KSP/PC | SNESGetKSP / KSPGetPC 借用，由 SNES/KSP 管理 | 随本次 SNES 生命周期；不能由借用方独立销毁 |
| FieldSplit IS | 每次配置局部创建，PETSC_COPY_VALUES | PCFieldSplitSetIS 保留其所需引用；局部 owner 释放调用方引用 |
| FieldAcceptance、Context | solve 栈对象；Context 引用约束、边界值、assemble、acceptance 等 | 不可直接挂到跨调用的 SNES 上；引用对象/步长捕获离开作用域会悬空 |
| LinearDiagnostics | solve 栈对象；linear_report 才额外 VecDuplicate | KSP 回调借用；本次调用后释放，持久化时必须清理或重绑回调 |
| 子 KSP / AMG | schur_solver.cpp 中 PCSetUp 和 PETSc setup 路径建立 | 属于 PC；对象保留不代表数值因子/AMG 层级可以保留 |
| LinearSystem | linear_system.cpp 构造 Mat/ghost Vec，成员 owner 持有 | solve:62 每次 KSPCreate 写入 solver_.put()；不能未经修改直接循环调用 solve 实现复用 |

最后一项为代码风险：PetscOwner::put() 只是返回内部指针，不先销毁原对象。若在同一 LinearSystem 上再次调用 solve，旧 KSP 指针可能被覆盖；当前 Poisson/motion/ale 调用方式不构成该风险已触发的证据。本任务不报告已实测内存泄漏。

## 每步与每次迭代

驱动循环建立当前步的边界值及 assemble 闭包，调用 system.solve。每次 solve 初始化解、字段接受基线、SNES/KSP/PC 与回调。Context::evaluate 更新 ghost，清零残量；有 Jacobian 时 MatZeroEntries，然后局部装配并执行 Vec/MatAssembly。回调可由 Newton、线搜索和失败 trial 重复调用，因此不能把回调次数当作时间步数。

当前已复用的是主 Vec/Mat 的存储及预分配；没有跨 solve 保留 SNES 树。不能把“每次 solve 建 SNES”误写为“每次 Newton 迭代新建所有 PETSc 对象”。

## 失效条件与风险

- 布局、分区、communicator、owned/ghost 或未知量规模变化：重建 Vec/Mat/IS 及求解树。
- 约束集合变化：重建约束/字段映射；即使图仍允许这些行，也必须清理旧约束影响。只有边界数值变化亦需重新应用值。
- dt、材料、状态、ALE 几何变化：通常不改变拓扑，但改变残量/Jacobian 数值；不得复用旧数值代替重装配。
- 稀疏图固定不意味着 LU/ILU 数值因子或 GAMG 层级仍有效；PC 更新策略需要单独测量与收敛验证。
- retry 必须重置接受基线、错误状态、诊断计数及当前步闭包；accepted 历史仍只在物理驱动接受后更新。
- 持久化上下文需拥有稳定存储，明确重绑生命周期。全局 PETSc options 默认值也不能未经核对按每步重复追加。

## 现有计时能证明什么

nonlinear_system.cpp:428 起的 setup_seconds 只覆盖 solve 内初始化，不含 NonlinearSystem 构造；solve_seconds 从初始残量评价之前计时，含初始装配、Schur 配置及 SNESSolve。schur_setup_seconds 为其中的重叠子区间，不应再次累加。assembly/ghost、linear_seconds 同样可能是嵌套统计。输出按 rank 分别取最大值，因此这些最大值不能直接相加解释为同一 rank 的总耗时。

finalize_seconds 在返回前求值，不含函数返回时 SNES 的 RAII 销毁成本，也不含之后的报告打印。当前汇总不足以把 SNES 分配/析构、PC 数值 setup 与 AMG 层级建立分别归因。重复创建已由源码确认，但没有本次性能测量证明它是瓶颈。

## 最小后续实验（未执行）

以 cases/fluid/transient.yaml 为首个固定案例，Release、固定 PETSc/MPI 版本和容差、单线程、1/2 rank。先在固定提交编译；每组至少 3 次独立运行，记录网格/DoF、迭代、真实残量及端到端时间分布。使用 -solver_report 与 PETSc -log_view 观察 setup/assembly/solve，并用关闭报告的对照估计诊断开销。计时必须另覆盖构造与析构，避免将子计时相加。

只有重复 setup 成为显著成本且回归通过，才进入 SOLVER-02 的最小设计；优先独立流体，按对象存储、矩阵图、矩阵数值、PC 数值、AMG 层级分别决定策略。补充失败回滚、dt 缩步、边界变化及重启对照后才考虑 FSI。无加速比承诺。

## 源码与契约证据

- [NonlinearSystem 与 Context](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp#L246)
- [主存储创建与 solve](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp#L328)
- [计时输出](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp#L428)
- [独立流体时间循环](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fluid.cpp#L64)
- [固体驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/solid.cpp#L67)
- [FSI 驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fsi.cpp#L102)
- [LinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/linear_system.cpp#L55)
- [PetscOwner](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/include/eonsim/linear_system.hpp#L24)
- [Schur setup](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/schur_solver.cpp)

数学与接受契约沿用 docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md。本次证据为源码审查；数值测试和性能实验未执行，不对最新提交补造通过记录。

## 分支整合补记（2026-10-30）

旧分支 `audit/petsc-nonlinear-lifecycle` 的 [独立审计](https://github.com/saitoasukakawaii/EONSim-new/blob/51ef2e50b70c5906aa80cdd526a51cac1f142572/docs/development/NONLINEAR_SESSION_LIFECYCLE_AUDIT.md) 使用同一源码基线，确认了相同的持久化风险。补充调用方为 [ALE 驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/ale.cpp)：同样在时间循环外持有 NonlinearSystem。保留本报告作为唯一审计入口，旧稿可从固定提交追溯，不再维护第二套状态表和同题草稿。

上述行号和生命周期说明均针对历史基线。后续 [多步测量](MULTISTEP_SETUP_PROFILE_2026-10-30.md) 已完成；本轮集成的 CI 分支还会在 fatal callback 后更换 trial Vec 以隔离遗留只读锁，这属于异常恢复，不能据此把正常时间步说成每步重建全部 Vec。旧分支的“下一步建立基线”及 SOLVER-02 ready 状态不恢复到当前任务队列。
