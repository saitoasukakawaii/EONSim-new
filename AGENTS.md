# FEM 项目开发约定

## 当前状态与目标

2026-10-31最新交付：G0B/G0/G5/G1已通过PR #23合入main。具备DoF语义与三种PC树、BE/变步BDF2/两类generalized-alpha及适用ALE/FSI接入、Gmsh4.1与Tri3/Quad4相容混合二维标量闭环。本地及云端主锁Debug/Release各60项、兼容锁13项通过；数量为该检查点实际inventory，后续执行应重新读取。详细适用范围见[集成验收](docs/development/FEM_INTEGRATION_VALIDATION.md)。下文20项等记录为B5历史，不覆盖本次交付；验证仍最多4rank。

这是多物理场 HPC 开发工作区，P0–P8 小算例主线已实现并验证：分布式基础、独立流体/固体、刚体/弹性单体 FSI、有限变形、分块求解及同分区重启。当前验证最多 4 rank，不能将其报告为大规模生产就绪。后续沿具体算例改进精度、规模或新增边界能力；不要将设计示意接口报告为已有实现。

基础完善 B0–B5 已实现：几何/标签边界、区域材料与分量约束、独立共形双域 FSI、BE 回滚缩步与实际时间恢复、解析几何/前向链式 ALE 切线及 Schur/GAMG。Debug/Release 各 20 项 CTest 通过，Schur 与直接解对照覆盖 1/2/4 rank；精度和规模数据见 [B5 记录](docs/development/B5_ACCURACY_AND_PERFORMANCE.md)。下一步依据实际算例的精度/规模需求推进；不将共形双域能力解释为非匹配界面、自动重网格或大规模生产验证。

当前主线已确定为：基础与分布式 → 独立流体 → 独立固体 → monolithic 刚体 FSI → monolithic 弹性体 FSI。分离式 FSI 在单体主线交付后再开发；CHT 等不阻塞当前路线。刚体首版为由流体力参与驱动的单轴运动，给定轨迹不能作为双向 FSI 的完成证据。

## 每次工作

1. 先读 [总原则与决策入口](MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md)，再按下表只读本次相关约束。
2. 沿现有实现完成一个具体算例或一个明确修复；没有代码时按开发路线从 P0 建立最小纵向闭环。
3. 优先具体类型、普通函数和单一可用后端；第二个真实使用者出现后再抽象。
4. 不为普通工作新增审批、计划文档、全量检查、兼容层或未使用的扩展点。
5. 每项实质开发任务开始时读取 CODEX_PROGRESS.md 和 CODEX_TASK_QUEUE.md，领取一个可独立验收的任务；结束时按“持续知识积累要求”更新项目状态、会话日志和知识索引。普通 typo、纯格式调整及无实质技术内容的小修复不强制写会话日志或生成文章。

## 第三方依赖版本兼容与 CI 策略

- 日常主力构建环境固定为仓库锁定的 PETSc 3.23.7；常规 Push、PR 和 main CI 只运行该版本的 Debug/Release 检查。
- PETSc 3.19.6 等历史环境不进入每次开发的自动编译/链接矩阵。保留锁文件和专项运行入口，仅在修改相关兼容代码、第三方 API 适配或 CMake Patch，或用户明确要求时按需验证。
- 遇到第三方依赖版本差异，优先采用能力/符号检测；其次使用依赖官方版本宏和集中式兼容封装。避免在业务代码中散落版本判断，也不要仅因存在版本差异就增加日常多版本构建。
- 必须使用版本限定 Patch 时，将 Patch、适用版本范围、上游来源、文件校验/前置条件和应用方式纳入 Git；通过 CMake 在受控构建目录中可重复地检查并应用，不静默修改系统安装目录。
- 兼容性验证应针对本次修改涉及的 API、宏分支或 Patch 选择最小相关测试；不要求每次提交对所有历史依赖版本重复配置、编译、链接和运行测试。
- 锁文件或恢复脚本的存在只表示环境可复现，不自动代表该版本是日常支持目标或每次提交均已验证。任何未实际执行的兼容性测试必须明确标记为未运行。


## EONSim 持续知识积累要求

每次实质开发任务结束时，必须进行知识沉淀：

1. 记录开发过程中遇到的重要错误、根因、排查过程、失败尝试及最终解决方案。
2. 更新 `docs/development/CODEX_SESSION_LOG.md`，记录真实开发过程和测试证据。
3. 更新 `docs/development/CODEX_PROGRESS.md` 和 `CODEX_TASK_QUEUE.md`，确保跨 Task 状态准确。
4. 对有复用价值的算法、架构、数值方法、HPC 优化和非显然错误，使用 `eonsim-knowledge-capture` Skill 形成技术文章草稿。
5. 更新 `docs/research/KNOWLEDGE_LOG.md`。
6. 对已经确认的长期架构原则，更新对应的 `AGENTS.md` 或 `docs/architecture/` 契约，避免重复犯错。
7. 每项结论必须标注源码提交、实际测试命令和验证结果；未验证内容明确标记为未验证。
8. 普通小修复不强制生成文章，避免知识库膨胀。
9. 知识文章保留在 `website/drafts/`，未经人工审查不得自动发布。

最终目标：使 EONSim 形成可以跨 Codex Task 持续积累、检索和复用的工程知识体系。

执行边界：
- “实质开发任务”包括算法/架构设计、生产代码修改、非平凡错误修复、数值验证、MPI/HPC 优化、依赖/CI 基础设施变更；普通 typo、纯格式调整和机械性小改动除外。
- 每项实质任务都更新进度、队列、会话日志和知识索引；没有可复用技术成果时，不创建文章草稿。
- 测试证据记录命令、构建配置、依赖版本、rank 数及实际结果；未运行、跳过、取消、失败必须分别如实记录，不能写成通过。
- 只有确实改变长期架构或工程规则时才修改架构契约；不得为了满足记录要求制造无意义文档或重复文章。
- 所有文章草稿都留在 `website/drafts/`；公开栏目发布必须经过人工审核和 PR 合并。

## 按任务读取

| 改动涉及 | 阅读文件 |
|---|---|
| 新模块、库选型、目录或依赖 | [L1 模块依赖](docs/architecture/L1_LAYERS_AND_DEPENDENCIES.md) |
| FEM、边界约束、残量/Jacobian、线性求解 | [L2 离散算子](docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md) |
| 材料历史、时间积分、多场/界面、checkpoint | [L2 耦合状态](docs/architecture/L2_MULTIPHYSICS_AND_STATE.md) |
| 刚体/弹性 FSI、ALE、界面消元或耦合切线 | [L2 单体 FSI](docs/architecture/L2_MONOLITHIC_FSI.md) |
| MPI、owned/ghost、缓存、线程、GPU | [L2 并行与内存](docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md) |
| CMake、Debug/Release、错误传播、检查 | [L3 构建与验证](docs/development/BUILD_AND_VALIDATION.md) |
| API 注释、数值代码说明、Doxygen | [L3 文档与注释](docs/development/DOCUMENTATION_AND_COMMENTS.md) |
| 公开知识网站、教学文章、网站预览和发布 | [网站贡献规范](website/development/contribution.md) 与 [网站说明](website/README.md) |
| 文献到数学/软件规格、整体研发阶段与 Codex 工作流 | [EONSim 工程研发总纲](docs/development/EONSim_ENGINEERING_PROGRAM.md) |
| Codex Goal 驱动的多轮持续研发 | [CODEX_GOAL_WORKFLOW](docs/development/CODEX_GOAL_WORKFLOW.md) |
| 跨 Task 进度恢复与任务队列 | [CODEX_PROGRESS](docs/development/CODEX_PROGRESS.md)、[CODEX_TASK_QUEUE](docs/development/CODEX_TASK_QUEUE.md)、[CODEX_SESSION_LOG](docs/development/CODEX_SESSION_LOG.md) |
| 将实质研发成果整理为公开知识草稿 | [eonsim-knowledge-capture Skill](.agents/skills/eonsim-knowledge-capture/SKILL.md) |
| 下一步功能或里程碑 | [开发路线](docs/development/ROADMAP.md) |

公开网站内容默认先写入 website/drafts/，并按网站贡献规范标注理论、实现和验证状态；未经人工审查及合并到 main，不得视为已发布。网站草稿目录被生产构建排除，但仓库公开，禁止放入秘密或敏感资料。


研究文件提供来源；无需每次重读所有上游项目。处理某子目录时，如该目录存在 AGENTS.md，读取其局部增量规则。

## Codex Goals 与跨 Task 接续

复杂且需要多轮调查、修改、测试的里程碑，可在 Codex Cloud 当前 thread 中由用户启动 Codex Goal。一个 Goal 只对应一个有证据验收条件的里程碑，不要设置“无限优化整个项目”这类无边界目标。Goal 的具体写法、生命周期和停止条件见 [CODEX_GOAL_WORKFLOW.md](docs/development/CODEX_GOAL_WORKFLOW.md)。Goal 只保存当前 thread 的目标状态；跨 Task 的唯一持久化事实来源是 Git 中的 CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md 和已提交代码。新 Task 开始前必须重新读取这些文件和最新 main。

## 不随优化改变的规则

- 局部物理 kernel 不做 MPI、PETSc 插入或 I/O；代数层不依赖具体物理实现。
- DoF 所有权、约束与 field layout 保持一致；分布式求解不反复收集全局场。
- 残量评价不提交材料/时间历史；必要场和整体耦合收敛后才提交。
- FSI 使用统一残量、主 Newton 和共同状态提交；首个基线包含 ALE 与跨场导数。分块预条件允许，不能用交替单场时间推进替代单体求解。
- Debug 增加内部诊断，Release 保留输入/几何有效性与求解失败检查；两者使用同一数学模型和停止准则。
- 未实现功能明确报告；不静默换模型、放宽容差或把失败结果标为成功。
- 数值和并行 API 注释写清实际契约；实现注释解释非直观原因。只写相关内容，不要求逐行注释、注释覆盖率或每次生成文档。

## 最小验证与交付

按构建与验证文档选择相关检查：普通代码改动编译受影响目标并运行一个相关小算例；通信改动补 1/2 rank 对照；数值公式改动补一个针对性数值检查。文档改动只阅读和检查链接。通过后不无理由重复测试，不要求测试先行或覆盖率指标。

交付说明改动、实际执行的验证与尚未实现的能力。只有真实改变架构决策时才更新对应主题文档；不要求每次改动新增记录。用户本次明确要求优先于这些项目默认值。
