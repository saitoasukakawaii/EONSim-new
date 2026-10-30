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
| HPC-01 | P1 | ready | MPI 稀疏装配与通信 profiling | 源码调用链、分阶段计时、1/2/4 rank 对照、原始日志和性能报告；先测量再决定优化 |
| SOLVER-03B | P2 | deferred | 按 SOLVER-03 规格实现可选一致缩放 | 由具体算例需求触发；单位/非均匀尺度、物理验收、约束/反力、1/2 rank 和失败恢复验证 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合已验证证据更新草稿；人工审核后发布 |

## HPC-01：MPI 稀疏装配与通信 profiling

### 目标

区分有限元局部计算、PETSc 矩阵插入、off-process stash/通信、MatAssembly、ghost/halo 更新和 KSP 的成本，为后续 MPI 稀疏结构优化提供证据。此任务先审计和测量，不预设需要改写装配架构。

### 第一阶段：源码审计

1. 检查 AlgebraLayout、GhostVector、NonlinearSystem::Context::evaluate、物理层局部装配回调及 PETSc Mat/Vec 插入路径。
2. 标记局部单元 kernel、局部矩阵/向量生成、MatSetValues/MatSetValuesLocal、MatAssemblyBegin/End、Vec ghost update 和 KSP solve 的边界。
3. 确认现有 -solver_report、PETSc -log_view、MatGetInfo 等观测能力；避免重复实现已有计时。
4. 区分物理场块、MPIAIJ 对角/非对角存储块和 owned/ghost DOF。

### 第二阶段：受控测量

1. 从已有案例中选择最小可复现的 Poisson/流体/FSI 代表算例；先确认网格和工作量适合当前 Cloud VM。
2. 运行 1/2/4 rank；若资源不允许，明确记录实际可运行的 rank 范围。
3. 固定 commit、构建类型、编译器、PETSc/MPI 版本、网格、DOF、容差和求解器选项。
4. 每组重复运行至少 3 次，保存原始日志；报告中位数和离散程度。
5. 记录总装配、局部计算、矩阵插入、MatAssembly、ghost 更新、KSP 时间、内存、迭代数和最终残量。
6. 若现有计时无法区分阶段，再提出最小侵入式 instrumentation 方案，经代码审查后实施。
7. 不放宽容差、不改变物理模型，不将 1/2/4 rank 小算例结果外推为多节点强扩展结论。

### 完成标准

提交源码调用链图、计时边界定义、可复现命令、环境信息、逐 rank 原始日志、统计表和瓶颈判断。只有当某个阶段在重复测量中稳定占据显著成本时，才建立下一项针对性优化任务。无证据时给出暂缓结论。

## 任务领取规则

1. 一个 Goal 对应一个主要任务和一个验收终点。
2. 开始时将任务标记为 in_progress；结束时标记为 review 或 done。
3. 任务受阻时记录阻塞与解锁条件，不要无限重试。
4. PR 合并后才能标记 done。
5. 下一 Goal 必须重新读取 main 的最新进度和任务队列。
