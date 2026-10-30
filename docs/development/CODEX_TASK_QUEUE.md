# EONSim Codex Task Queue

本队列用于跨 Codex Task 接续开发。状态变化必须以实际实现、测试或审核结果为依据。

## 状态定义

- ready：依赖满足，可以开始。
- in_progress：已有 Task 正在处理。
- blocked：存在明确阻塞。
- review：已提交，等待人工/PR 审查。
- done：验收证据已记录并合并到 main。
- deferred：暂缓，需由需求或性能证据重新触发。

## 当前队列

| ID | 优先级 | 状态 | 任务 | 交付与验收 |
|---|---:|---|---|---|
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | 已合并 PR #3；网站构建通过 |
| SOLVER-01 | P1 | review | PETSc NonlinearSystem 对象生命周期审计 | 本 PR 的 NONLINEAR_SESSION_LIFECYCLE_AUDIT.md；源码调用链、对象生命周期、复用风险和结论 |
| SOLVER-02 | P1 | ready | 多时间步 solver setup 性能基线 | 使用现有 -solver_report 测量 transient fluid 与 elastic FSI；区分首步/后续步和 setup/assembly/linear 时间；本任务不修改求解器 |
| SOLVER-03 | P2 | deferred | Newton 变量/方程一致缩放审查与规格 | 推导未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-04 | P2 | deferred | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P2 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合实测数据更新草稿；人工审核后发布 |

## SOLVER-01：生命周期审计

审计报告：docs/development/NONLINEAR_SESSION_LIFECYCLE_AUDIT.md。

主要结论：
- NonlinearSystem 在 fluid、solid、ALE、FSI 的时间循环外构造。
- solution/residual/scratch ghost Vec、AIJ Mat、稀疏图和 local trial 缓冲跨时间步复用。
- SNES 及其内部 KSP/PC、Context、FieldAcceptance、LinearDiagnostics 和 FieldSplit 配置在每次 solve() 中重建。
- 回调引用 solve() 局部上下文，因此持久化 SNES 需要先解决稳定的 callback context 所有权。
- 矩阵数值每次 Jacobian 评价重新装配；矩阵图复用不等于 PC 数值或 AMG hierarchy 复用。
- 当前尚无数据证明 SNES/KSP/PC setup 是主要瓶颈，因此暂不实现持久化 NonlinearSession。

## SOLVER-02：性能基线测量

目标：量化多时间步中每次 solve() 的 setup 开销，判断是否值得进一步实现持久化 SNES/KSP/PC。

建议算例：
- cases/fluid/transient.yaml（10 steps）；
- cases/fsi/elastic.yaml（10 steps）；
- 必要时增加 Schur PC 配置作为独立对照。

测量要求：
1. 固定 commit、Release 构建、硬件、MPI/PETSc 版本、网格、rank、容差和 PETSc options。
2. 相同输入重复运行，报告首步与后续步；多次运行报告中位数。
3. 使用 -solver_report；首轮不启用 -linear_report，以避免额外诊断开销。
4. 记录 setup_seconds、schur_setup_seconds、solve_seconds、assembly_seconds、ghost_seconds、linear_seconds、finalize_seconds、RSS、SNES/KSP 迭代数。
5. 明确时间指标存在包含关系，不能简单相加。
6. 不放宽容差，不更改物理模型，不把不同精度结果直接比较。

完成标准：交付可复现运行命令、环境信息、原始日志、逐步数据和重复运行统计，并给出是否进入 NonlinearSession 原型的结论。未执行的算例必须标为未运行。

## 任务领取规则

1. 一个 Codex Task 只领取一个主要任务。
2. 开始时把状态改为 in_progress，结束时改为 review 或 done。
3. 任务受阻时记录具体阻塞，不要反复空转。
4. 任务合并后再将其标记为 done。
5. 新增任务必须有目标、依赖和可观察验收标准。
