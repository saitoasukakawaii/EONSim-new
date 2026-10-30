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
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | 本 PR；文件可用、链接有效、网站构建通过 |
| SOLVER-01 | P1 | done | PETSc NonlinearSession 对象生命周期审计 | 源码调用链、对象生命周期表、setup/assemble/solve 计时方案、复用风险和是否实施的建议；本任务不改求解器 |
| SOLVER-01B | P1 | done | 固定 transient 案例的诊断开销基线（依赖 SOLVER-01 已合并） | 1/2 rank、每组至少 3 次、保存命令与原始日志；固定 rank 输出一致；明确计时边界，不将差异当作持久化收益 |
| SOLVER-02 | P1 | done | 多时间步 solver setup 性能基线 | fluid/elastic、各3次、逐步数据和首步/后续步统计；仅测量分析，不改求解器 |
| SOLVER-05 | P1 | done | 修复重复线性求解 KSP 所有权（依赖 SOLVER-01 审计） | 成功/失败/恢复调用均释放 PC；1/2 rank 回归和 Poisson 验证通过；独立 PR |
| SOLVER-03 | P2 | done | Newton 变量/方程一致缩放审查与规格 | 推导缩放后的未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-03B | P2 | deferred | 按 SOLVER-03 规格实现可选一致缩放 | 由具体算例需求及规格审核触发；单位/非均匀尺度、物理验收、约束/反力、1/2 rank 和失败恢复验证 |
| SOLVER-04 | P2 | done | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| SOLVER-04B | P2 | done | 补齐求解器层级算子尺寸（依赖 SOLVER-04） | 只读已有算子；报告 global/local 行列；Schur 1/2/4 rank 与失败/初态收敛回归通过 |
| HPC-01A | P2 | done | 非线性装配阶段计时（HPC-01 的首个增量） | 分别报告 callback/错误同步/最终装配/约束；明确计时边界；Schur 与失败恢复回归通过 |
| HPC-01B | P2 | done | 稳态流体装配阶段基线（依赖 HPC-01A） | 三网格、1/2 rank、各 3 次；阶段范围/原始证据/直接解对照；不将回调等同纯 kernel |
| HPC-01C | P2 | done | transient fluid/FSI 装配阶段测量（用户同意继续建议任务） | 1/2/4 rank、每组 3 次；首步/后续步统计；物理解对照及原始证据 |
| HPC-01D | P2 | done | 独立流体 kernel/插入计时（用户要求继续上一轮建议） | 显式开关；逐rank/逐步计数；steady/transient/tagged 1/2 rank 开关对照通过 |
| HPC-01E | P2 | done | 流体单元计时开关扰动与基线（继续用户已提出候选） | 1/2/4 rank、交替顺序配对重复、warmup；物理解/迭代不变；原始数据和范围 |
| QA-01 | P2 | review | profiling 日志验收加固（用户继续上一轮候选；依赖 HPC-01E） | 真实归档日志可解析；非有限/非整数原因与计数、缺失指标/根节点、重复层级及错序步被拒绝；加入 CTest |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合性能数据更新草稿；人工审核后发布 |

## HPC-01C：多时间步装配阶段测量

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

SOLVER-02 测量已完成，见 docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md；结论为暂缓持久化原型，已由 PR #8 合并。后续优化需由业务规模或新增性能证据触发。

SOLVER-03 本轮因用户要求继续研发而领取，仅完成审查、规格及独立代数验证；实际求解器缩放实现仍需后续独立任务，不引入配置键。

SOLVER-03 规格及精确代数验证见 [审查报告](../research/NEWTON_SCALING_SPEC_2026-10-30.md)，已由 PR #10 合并；未实现求解器坐标缩放。

SOLVER-04 本轮范围：稳态流体单位立方体，2/4/6 subdivisions，1/2 rank；各组直接解参考及 3 次 Schur 重复，保存原始日志、字段差、层级、内存与计时，不外推大规模性能。

SOLVER-04 已完成本轮有界测量，见 [报告](../research/SCHUR_MESH_PROFILE_2026-10-30.md)；已由 PR #11 合并。后续大网格/FSI 或粗层成本测量需明确目标，不根据小样本直接调参。

HPC-01A 实现成功评价的阶段计时，已由 PR #13 合并；HPC-01 尚缺纯 kernel/插入分离与目标规模证据，保持 deferred，不把诊断接线当作完整 profiling 结论。

HPC-01B 已完成稳态三网格装配阶段重复测量，见 [报告](../research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md)，已由 PR #16 合并。未据此改求解器或作纯通信成本归因。

HPC-01C 已完成 fluid/elastic、1/2/4 rank、18次运行及180步测量，见 [报告](../research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md)，已由 PR #17 合并。没有新增 ready 任务；后续仍由用户选择。

HPC-01D 已实现独立流体显式单元计时，并通过 Release/Debug 三案例1/2 rank开关对照，已由 PR #18 合并。FSI/ALE、owned/remote插入分离与计时扰动测量未完成；无新增ready任务。

HPC-01E 已完成1/2/4 rank、每配置5对测量及6次预热，见 [报告](../research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md)，已由 PR #19 合并。观测范围不足以支持固定开销或优化结论；无新增ready任务。
