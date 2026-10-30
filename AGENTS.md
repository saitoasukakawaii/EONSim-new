# FEM 项目开发约定

## 当前状态与目标

这是多物理场 HPC 开发工作区，P0–P8 小算例主线已实现并验证：分布式基础、独立流体/固体、刚体/弹性单体 FSI、有限变形、分块求解及同分区重启。当前验证最多 4 rank，不能将其报告为大规模生产就绪。后续沿具体算例改进精度、规模或新增边界能力；不要将设计示意接口报告为已有实现。

基础完善 B0–B5 已实现：几何/标签边界、区域材料与分量约束、独立共形双域 FSI、BE 回滚缩步与实际时间恢复、解析几何/前向链式 ALE 切线及 Schur/GAMG。Debug/Release 各 20 项 CTest 通过，Schur 与直接解对照覆盖 1/2/4 rank；精度和规模数据见 [B5 记录](docs/development/B5_ACCURACY_AND_PERFORMANCE.md)。下一步依据实际算例的精度/规模需求推进；不将共形双域能力解释为非匹配界面、自动重网格或大规模生产验证。

当前主线已确定为：基础与分布式 → 独立流体 → 独立固体 → monolithic 刚体 FSI → monolithic 弹性体 FSI。分离式 FSI 在单体主线交付后再开发；CHT 等不阻塞当前路线。刚体首版为由流体力参与驱动的单轴运动，给定轨迹不能作为双向 FSI 的完成证据。

## 每次工作

1. 开始时先读取 [研发进度](docs/development/CODEX_PROGRESS.md) 和 [任务队列](docs/development/CODEX_TASK_QUEUE.md)，按进度文件中的持续开发协议恢复、选取任务并交付独立 PR。再读 [总原则与决策入口](MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md)，再按下表只读本次相关约束。
2. 沿现有实现完成一个具体算例或一个明确修复；没有代码时按开发路线从 P0 建立最小纵向闭环。
3. 优先具体类型、普通函数和单一可用后端；第二个真实使用者出现后再抽象。
4. 不为普通工作新增审批、计划文档、全量检查、兼容层或未使用的扩展点。

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
| 下一步功能或里程碑 | [开发路线](docs/development/ROADMAP.md) |

公开网站内容默认先写入 website/drafts/，并按网站贡献规范标注理论、实现和验证状态；未经人工审查及合并到 main，不得视为已发布。网站草稿目录被生产构建排除，但仓库公开，禁止放入秘密或敏感资料。

研究文件提供来源；无需每次重读所有上游项目。处理某子目录时，如该目录存在 AGENTS.md，读取其局部增量规则。

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
