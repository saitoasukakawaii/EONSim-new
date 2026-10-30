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
| SOLVER-01 | P1 | done | PETSc NonlinearSystem 对象生命周期审计 | PR #4 已合并；源码审计报告和知识草稿已提交 |
| SOLVER-01B | P1 | done | 固定 transient 案例的诊断开销基线 | PR #7 已合并；1/2 rank、重复运行和原始日志归档 |
| SOLVER-02 | P1 | done | 多时间步 solver setup 性能基线 | PR #8 已合并；fluid/elastic、各 3 次，暂缓持久化 NonlinearSession |
| SOLVER-05 | P1 | done | 修复重复线性求解 KSP 所有权 | PR #9 已合并；成功/失败/恢复及 1/2 rank 回归通过 |
| SOLVER-03 | P2 | done | Newton 变量/方程一致缩放审查与规格 | PR #10 已合并；独立代数验证通过，未实现完整求解器缩放 |
| SOLVER-04 | P2 | done | Schur/GAMG 网格规模行为分析 | PR #11 已合并；2/4/6 subdivisions，1/2 rank；不外推大规模性能 |
| SOLVER-04B | P2 | done | 补齐求解器层级算子尺寸 | PR #12 已合并；Release 3 项、Debug 2 项针对性测试通过 |
| HPC-01A | P2 | done | 非线性装配阶段计时 | PR #13 已合并；新增 callback、错误同步、最终装配和约束计时；未做重复性能测量 |
| HPC-01B | P1 | ready | 使用新增阶段计时进行重复 MPI 装配测量 | 代表算例 1/2/4 rank、每组至少 3 次；保存原始日志、环境、统计和阶段口径；不修改物理模型 |
| HPC-01C | P2 | blocked | 若 HPC-01B 仍不能区分 kernel 与插入成本，再增加更细粒度 instrumentation | 必须先说明现有字段不足和计时开销；经最小设计审查后再实施 |
| SOLVER-03B | P2 | deferred | 按 SOLVER-03 规格实现可选一致缩放 | 由具体算例需求触发；单位/非均匀尺度、物理验收、约束/反力、1/2 rank 和失败恢复验证 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合已验证证据更新草稿；人工审核后发布 |

## HPC-01B：重复 MPI 装配阶段测量

### 目标

使用 PR #13 新增的阶段计时字段，建立可复现的 MPI 装配测量基线。此任务只运行测量、解析日志和分析，不修改求解器代码。

### 执行要求

1. 读取 L2 离散算子计时契约及 PR #13 的实现，准确解释 callback_seconds、failure_sync_seconds、assembly_finalize_seconds、constraint_seconds、assembly_seconds、ghost_seconds 和 linear_seconds。
2. 从现有案例中选择至少一个装配成本足够稳定的代表算例；如资源允许，再增加 transient fluid 或 FSI。
3. 固定 main commit、Release 构建、CPU/内存、编译器、PETSc/MPI 版本、网格、DOF、容差和 PETSc options。
4. 在可用资源范围内运行 1/2/4 rank；每个配置至少 3 次重复，保存原始日志。
5. 报告每步与每次运行的中位数、离散程度和 rank-max 口径；区分首步与稳定步骤。
6. 阶段时间有包含关系且 rank 最大值可能来自不同 rank，不得直接相加或将 callback/assembly_finalize 解释为纯 kernel/纯网络时间。
7. 同时检查 SNES/KSP 迭代数、最终残量和物理解差；不放宽容差。
8. 不将单节点多 rank 结果写成多节点强扩展结论。若 Cloud VM 资源不足，记录阻塞并提供在 HPC 上复现的命令。

### 完成标准

提交可复现命令、环境信息、逐 rank 原始日志、统计表、阶段边界解释和瓶颈结论；明确下一步是优化、需要更细计时，还是暂缓。知识草稿保留在 website/drafts/。

## 任务领取规则

1. 一个 Goal 对应一个主要任务和一个验收终点。
2. 开始时将任务标记为 in_progress；结束时标记为 review 或 done。
3. 任务受阻时记录阻塞与解锁条件，不要无限重试。
4. PR 合并后才能标记 done。
5. 下一 Goal 必须重新读取 main 的最新进度和任务队列。
