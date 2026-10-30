# EONSim Codex Task Queue

本队列用于跨 Codex Task 接续开发。任务按依赖和优先级排序；完成后更新状态并在必要时补充新任务。队列不是对功能已实现的声明。

## 状态定义

- ready：依赖满足，可以开始。
- in_progress：已有 Task 正在处理。
- blocked：存在明确阻塞，必须记录原因。
- review：实现已提交，等待人工/PR 审查。
- done：验收证据已记录并合并到主线。
- deferred：暂缓，需由需求或性能证据重新触发。

## 当前队列

| ID | 优先级 | 状态 | 任务 | 交付与验收 |
|---|---:|---|---|---|
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | 本 PR；文件可用、链接有效、网站构建通过 |
| SOLVER-01 | P1 | review | PETSc NonlinearSession 对象生命周期审计 | 源码调用链、对象生命周期表、setup/assemble/solve 计时方案、复用风险和是否实施的建议；本任务不改求解器 |
| SOLVER-02 | P1 | blocked | 若 SOLVER-01 证明存在重复分配且可安全复用，再设计 NonlinearSession 最小实现 | 明确 Vec/Mat/SNES/KSP/PC/IS/context 生命周期；保持数值结果一致；提供性能基线 |
| SOLVER-03 | P2 | deferred | Newton 变量/方程一致缩放审查与规格 | 推导缩放后的未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-04 | P2 | deferred | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P2 | deferred | 将已验证的 PETSc 生命周期专题整理成教学文章 | 文章链接源码 commit、实验配置和真实结果；草稿经审核后发布 |

## SOLVER-01 任务说明

### 目标

确认当前 EONSim 的 PETSc 非线性求解对象是否在时间步、Newton 迭代或重复求解之间被不必要地创建/销毁，以及这种行为是否构成实际性能瓶颈。

### 必须检查

- LinearSystem 和 NonlinearSystem 的构造、析构和调用位置；
- Vec、ghost vector、Mat、SNES、KSP、PC、IS 和 callback context 的所有权；
- 稀疏图、矩阵数值、预条件器数值及 AMG 层级分别何时失效；
- 时间步改变、网格/ALE 几何改变、约束变化和场布局变化对复用的影响；
- 当前日志或 profiling 是否足以证明 setup 开销值得优化。

### 禁止事项

- 不要仅凭“重复创建对象”就判定一定需要持久化。
- 不要在本次审计中改写求解器或新增抽象层。
- 不要把 Mat 稀疏图复用等同于矩阵数值复用。
- 不要把 KSP/PC 对象复用等同于预条件器数值或 AMG hierarchy 可安全复用。
- 不得为了性能放宽 SNES/KSP 容差或改变物理模型。

### 完成标准

交付一份简洁审计报告，包含源码引用、生命周期表、潜在收益、失效条件、风险、建议的最小实验和明确结论：实施、暂缓或需要额外测量。

## 任务领取规则

1. 一个 Codex Task 只领取一个主要任务，除非两个任务共享同一不可分割的改动。
2. 开始时把状态改为 in_progress，结束时改为 review 或 done。
3. 任务受阻时记录具体阻塞，不要反复空转。
4. 任务合并后再将其标记为 done。
5. 新增任务必须有目标、依赖和可观察验收标准。

SOLVER-01：审计报告位于 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md。结论为需要额外测量；SOLVER-02 保持 blocked，尚无重复 setup 为瓶颈的性能证据。
