# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 当前主分支基线：25e49af（PR #19 合并）
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

## 当前焦点

PR #19 已合并，HPC-01E 完成。按用户继续上一轮候选，QA-01 已加固 profiling 日志校验并加入自动回归，等待独立 PR 审核。未修改 C++ 求解器或新增性能结论。

## 最近完成

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

基线25e49af；分支fix/profile-log-validation；实现提交7b91030。11项Python测试通过，包含72份真实归档日志；Debug/Release新增CTest均1/1通过，eonsim构建成功。下一Task先检查PR；无新增ready任务，后续目标由用户选择。

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
