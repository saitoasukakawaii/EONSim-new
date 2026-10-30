# EONSim Codex Goal 驱动的持续研发流程

本文定义如何在 ChatGPT 网页版 Codex Cloud 中，把一次性编程请求转化为有边界、可验证、可接续的多轮研发目标。

## 1. 三层状态模型

| 层级 | 载体 | 负责什么 | 生命周期 |
|---|---|---|---|
| 当前目标 | Codex Goal | 当前一个里程碑内的多轮调查、实现、测试和修复 | 当前 Codex thread |
| 跨任务状态 | CODEX_PROGRESS / CODEX_TASK_QUEUE / CODEX_SESSION_LOG | 在不同 Task、不同会话之间恢复项目状态 | 随 Git 持久化 |
| 代码与证据 | Git 分支、PR、测试日志、基准结果、知识草稿 | 保存实际变更和可审核证据 | 按 PR 审核 |

Codex Goal 是 thread-scoped，不是仓库级全局任务队列，也不会替代 Git。新 Cloud Task 有独立工作区；重要工作必须 commit/push，并写回进度文件。

## 2. 何时使用 Goal

适合多轮调查、修改、构建、测试和再次修改的求解器任务；profiling 后根据数据决定下一步的性能优化；解析解/MMS 验证；多文件重构；需要生成实验报告和知识草稿的研究任务。

不适合一行代码修复、单次解释、短代码审查或没有可检查完成条件的“持续优化整个项目”。

**原则：一个 Goal 对应一个可验收的里程碑，不对应整个 EONSim 的无限期开发。**

## 3. 在 Codex Cloud 启动 Goal

1. 在网页版 Codex 选择已发布的 EONSim-new Cloud Environment。
2. 创建或打开当前里程碑的 Cloud Task。
3. 确认仓库、分支和工作区状态。
4. 在该 Task 的输入框中使用 /goal 命令，写清楚结果、验证证据、约束、工作范围和阻塞条件。

命令形式：

```text
/goal <目标结果>，由 <可检查证据> 验证；保持 <不可破坏的约束>。只在 <允许范围> 内工作。每轮结束记录实际变更、测试结果和下一项行动。若遇到权限、缺失依赖、资源上限或需要用户决策，停止并说明阻塞，不要猜测或绕过。
```

生命周期命令：

- `/goal`：查看当前 Goal；
- `/goal pause`：暂停；
- `/goal resume`：恢复；
- `/goal clear`：清除当前 Goal。

Goal mode 从 Codex 0.128.0 起提供。OpenAI 公开发布说明列出的界面包括 Codex app、IDE extension 和 CLI；Codex Cloud 文档说明 Cloud Task 可从 web 启动和继续，但没有明确保证每个网页版 Codex Cloud composer 都提供 /goal。

因此，在 ChatGPT 网页版 Codex Cloud 中，先在输入框输入 /，检查命令菜单是否实际提供 Goal。只有当前界面提供该命令时，才使用 /goal 启动目标。若网页 composer 不提供 /goal，不要把普通提示词误认为已激活自动 Goal；可以在支持 Goal mode 的 Codex app、IDE extension 或 CLI 中使用。若坚持使用网页版 Cloud，则继续同一个 Cloud Task，并在每轮结束后明确要求继续，直到本里程碑验收完成。跨 Task 状态由 GitHub 状态文件和已提交代码恢复。

生命周期命令（仅在当前界面支持 Goal mode 时使用）：
- /goal：查看当前 Goal；
- /goal pause：暂停；
- /goal resume：恢复；
- /goal clear：清除当前 Goal。

## 4. 每轮执行循环

1. **Reconcile**：读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md，核对 main、当前分支、未合并 PR 和工作区状态。
2. **Select**：只领取最高优先级、依赖已满足的一个 ready 任务；若没有 ready 任务，列出候选并等待用户决定，不得擅自把 deferred 改成 ready。
3. **Plan briefly**：确定最小变更、相关数学/架构契约和验收命令；不要停留在计划阶段。
4. **Execute**：检查源码，修改代码或文档，保持单一职责。
5. **Verify**：运行相关构建、测试、解析解/MMS、MPI 对照或 benchmark。不能运行时明确记录原因。
6. **Capture**：更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、CODEX_SESSION_LOG；有可复用知识时使用 eonsim-knowledge-capture Skill，生成 website/drafts 草稿。
7. **Persist**：在独立分支 commit/push；创建或更新 PR。不要直接推送 main。
8. **Audit**：核对 diff、测试日志、数值结果、性能数据和公开文章中的主张。
9. **Continue or stop**：验收未满足且无阻塞时继续；达到验收条件则完成 Goal。需要人工审核、合并 PR、提供数据或做架构决策时暂停并交还用户。

## 5. 人工审批边界

Codex 可以在独立分支中自主读取代码、实现限定范围内的修改、运行已授权测试、生成报告和知识草稿、commit/push、创建或更新 PR。

必须等待用户合并 PR 到 main，或决定改变物理模型、离散方法、核心架构、收敛容差、网络权限及公开文章发布。不得自动合并 main，不得为了测试通过而放宽数值准则。

## 6. 连续性与停止条件

Goal 不是无限后台循环。它只在目标仍 active、thread 空闲、没有待处理用户输入且预算允许时继续。用户中断、预算耗尽、权限/依赖问题或需要决策时应停止并写检查点。

Cloud Task 工作区彼此隔离。跨 Task 恢复依赖 GitHub 中已提交的代码和状态文件，而不是旧 VM 内存。Goal 完成不代表整个 EONSim 项目完成。

## 7. 每个里程碑的交付清单

- [ ] 一个独立任务 ID 和明确验收条件；
- [ ] 对应源码/数学契约已阅读；
- [ ] 代码变更位于独立分支；
- [ ] 相关测试已运行并记录真实输出；
- [ ] 性能数据附硬件、软件版本、网格/DOF、MPI rank、容差和重复次数；
- [ ] CODEX_PROGRESS、CODEX_TASK_QUEUE、CODEX_SESSION_LOG 已更新；
- [ ] 知识草稿已生成（如有），但没有自动发布；
- [ ] PR 已创建或更新；
- [ ] 最终报告说明完成项、未完成项、风险和下一任务。

## 8. 当前推荐的第一个 Goal

当前下一项任务是 SOLVER-02：测量多时间步算例中的 solver setup 开销。不要直接实现持久化 NonlinearSession。

建议先使用 cases/fluid/transient.yaml，再使用 cases/fsi/elastic.yaml；具体命令必须先从当前 README、case runner 和 CLI 解析代码确认。使用现有 -solver_report，记录首步与后续步的 setup、Schur setup、SNESSolve、assembly、ghost、linear 和内存指标。首轮不启用会增加额外评价开销的 -linear_report。

至少进行多次重复运行，固定 commit、Release 构建、CPU/内存、MPI/PETSc 版本、rank、网格和容差。时间指标有包含关系，不能简单相加。若当前 Cloud VM 资源或 MPI 环境不足，记录可复现的限制，不伪造结果。

只有测量证明 setup 是值得优化的成本，才创建下一 Goal 设计持久化 SNES/KSP/PC 的最小原型。
