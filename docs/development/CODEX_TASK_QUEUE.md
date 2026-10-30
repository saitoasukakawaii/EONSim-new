# EONSim Codex Task Queue

本队列用于跨 Codex Goal / Cloud Task 接续研发。每个 Goal 只领取一个有明确验收条件的里程碑任务。

## 状态定义

- ready：依赖满足，可以开始。
- in_progress：当前有一个 Goal/Task 正在执行。
- blocked：存在明确阻塞，必须记录原因。
- review：已提交 PR，等待人工审核。
- done：验收证据已记录且 PR 已合并到 main。
- deferred：暂缓，需由需求或性能证据重新触发。

## 当前队列

| ID | 优先级 | 状态 | 任务 | 交付与验收 |
|---|---:|---|---|---|
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | PR #3 已合并；网站构建通过 |
| SOLVER-01 | P1 | done | PETSc NonlinearSystem 对象生命周期审计 | PR #4 已合并；源码审计报告和公开知识草稿已提交；未进行性能实测 |
| SOLVER-02 | P1 | ready | 多时间步 solver setup 性能基线 | 对 transient fluid 与 elastic FSI 使用 -solver_report；记录首步/后续步、重复运行统计、环境和原始日志；不修改求解器 |
| SOLVER-03 | P2 | blocked | 根据 SOLVER-02 证据决定是否设计持久化 NonlinearSession | 只有 setup 成为可重复显著成本时才启动；明确 callback context、矩阵数值、PC/AMG 更新与失败恢复策略 |
| SOLVER-04 | P2 | deferred | Newton 变量/方程一致缩放审查与规格 | 推导未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-05 | P2 | deferred | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合性能数据更新草稿；人工审核后发布 |

## SOLVER-02：多时间步 solver setup 性能基线

### 目标

量化每个时间步的 SNES/KSP/PC setup 成本，判断是否值得进一步设计持久化 NonlinearSession。此任务只测量和分析，不修改求解器。

### 算例顺序

1. cases/fluid/transient.yaml（10 steps）。
2. cases/fsi/elastic.yaml（10 steps）。
3. 若前两项能稳定运行且确有需要，再增加 Schur PC 对照。

### 测量要求

1. 固定 commit、Release 构建、CPU/内存、MPI/PETSc 版本、网格、rank、容差和 PETSc options。
2. 先检查 README、case runner 和 CLI，确定真实可执行命令；不得猜测命令或参数。
3. 每个案例至少 3 次重复运行；报告首步与后续步，给出中位数和离散程度。
4. 使用 -solver_report；首轮不启用 -linear_report。
5. 记录 setup_seconds、schur_setup_seconds、solve_seconds、assembly_seconds、ghost_seconds、linear_seconds、finalize_seconds、RSS、SNES/KSP 迭代数和最终残量。
6. 解释计时区间的包含关系；不得把嵌套时间简单相加。
7. 不放宽容差、不改物理模型；数值结果不一致时先调查，不以速度作为唯一指标。
8. 如果 Cloud 环境不能稳定运行 MPI/FSI，保存失败输出和环境限制，不能伪造性能数据。

### 完成标准

提交可复现命令、环境信息、原始日志、逐步数据、重复运行统计和结论：实施 NonlinearSession 原型、暂缓，或需要更大 HPC 环境补测。

## 任务领取规则

1. 一个 Goal 对应一个主要任务和一个验收终点。
2. 开始时将任务标记为 in_progress；结束时标记为 review 或 done。
3. 任务受阻时记录阻塞与解锁条件，不要无限重试。
4. PR 合并后才能标记 done。
5. 下一 Goal 必须重新读取 main 的最新进度和任务队列。
