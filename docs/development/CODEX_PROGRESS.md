# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 本次整合前主线基线：38a5e516ffe129d1b70c7c1bd8365deb5ded101a（PR #21 合并）；本轮源提交及取舍见整合记录，最终主线以 Git 为准。
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场有限元求解器。
- 已交付主线：P0–P8 与 B0–B5 小算例基线；不代表已完成大规模生产扩展。
- 公开知识网站：website/，VitePress；只有合并到 main 的正式栏目内容进入生产网站。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 当前已验证最多 4 MPI ranks，不等于大规模生产验证 |
| 网站与知识生产基础设施 | 已合并 | PR #2、#3、#6 |
| PETSc 生命周期与多步 setup 基线 | 已完成 | PR #4、#7、#8；持久化 NonlinearSession 暂缓 |
| 重复线性求解 KSP 所有权 | 已修复 | PR #9；成功、失败、恢复及 1/2 rank 回归通过 |
| Newton 缩放规格 | 已完成审查 | PR #10；可选完整坐标缩放仍 deferred |
| Schur/GAMG 网格测量 | 已完成 | PR #11；小规模结果不外推大规模性能 |
| 求解器层级算子尺寸 | 已实现并合并 | PR #12；Release/Debug 针对性测试通过 |
| 非线性装配阶段计时 | 已实现并合并 | PR #13；增加 callback、错误同步、最终装配和约束阶段计时；已有 HPC-01B/C 重复测量 |
| 独立流体缓存 COO Jacobian | 已实现并合并 | PR #21；范围及验证局限见 HPC-02 报告 |
| 通用 FEM 与 20 组上游学习规划 | 文档已集成 | 16 份 Markdown 随设计分支合入；G0–G8 实现均 deferred |
| 可复现云环境与 MPI 故障 CI | 实现已集成，最终验收待执行 | 原分支 CI 有通过记录；本次合并只做静态与纯脚本检查，未编译 |

## 当前焦点

按用户明确要求清理 18 个完全合并的远程分支，并审查、整合余下 6 个分支。
保留架构规划、CI 与恢复证据、网站内容检查和 COO 交付记录；合并旧审计的有效补充，
不恢复已过时的任务状态。具体源提交、取舍和删除清单见 [分支整合记录](BRANCH_INTEGRATION_2026-10-30.md)。
本轮不编译，推送提交使用 `[skip ci]`。G0–G8 仍全部 deferred，无新增 ready 开发任务。

## 最近完成

- PR #21：HPC-02 独立流体可选固定 COO Jacobian；原测试和测量范围以报告为准，本轮未重跑。
- ARCH-01：通用 FEM 架构与学习路线 16 份文档已集成；未发布知识草稿，非实现完成声明。
- BRANCH-01：删除已完全合并的 18 个远程分支，审查整合其余 6 个；按用户明确授权直接合入 main，来源 CI 分支已有 PR #22，本会话未新建 PR。
- INFRA-01：纳入原分支至 787372e 的实现与证据；修正锁定 ABI 检查的启用范围、JUnit 完整性检查和文档，最终集成的数值验收保留 review。

- PR #3：持续研发进度、任务队列、会话日志、知识模板和采集 Skill。
- PR #4：PETSc 对象生命周期源码审计。
- PR #6：Codex Goal 工作流说明及任务状态同步。
- PR #7/#8：非线性诊断开销和多时间步 setup 基线；持久化 NonlinearSession 暂缓。
- PR #9：重复线性求解 KSP 所有权修复。
- PR #10：Newton 缩放规格及独立代数验证；未实现完整求解器缩放。
- PR #11：Schur/GAMG 小规模网格测量。
- PR #12：求解器层级 A 算子 global/local 行列数报告。
- PR #13：非线性装配阶段计时。Release 3 项、Debug 2 项针对性测试通过；未运行重复性能基准。

## 当前检查点

整合分支 `integration/review-branches-2026-10-30`；源分支和提交见整合记录。
本轮执行纯 Python 解析器回归、源文件/脚本语法、依赖锁、Markdown 链接和 Git 差异检查。
未运行 CMake 配置、编译、CTest、MPI、性能实验或网站构建，未触发数值 CI。
原 [INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md) 与 [HPC-02](../research/FLUID_COO_ASSEMBLY_2026-10-30.md)
的测试对应各自记录的提交；不能用其通过结果替代最终集成验收。所有知识草稿保持未发布。

## 恢复规则

每个新 Codex Task 开始时：
1. 读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md 和当前任务相关契约。
2. 检查 main、当前分支、工作区和未合并 PR，避免重复任务。
3. 只领取一个 ready 任务；若没有 ready 任务，先提出候选，不擅自扩展范围。
4. 每完成一个可验证增量，更新进度、队列和会话日志。
5. 重要改动 commit/push 到独立分支；通过 PR 审核，不直接推送 main。
6. 有复用价值的知识写入 website/drafts/，人工审核后才发布。

Goal 使用说明见 CODEX_GOAL_WORKFLOW.md。Goal 负责当前线程内的多轮执行；GitHub 状态文件负责跨 Task 接续。

## 更新规则

- 只记录已确认的代码、测试和审核状态。
- 未运行的测试和性能实验明确写“未运行”。
- 不把计划、推断写成已实现或已验证。
- 任务合并到 main 后才将队列状态标为 done。
