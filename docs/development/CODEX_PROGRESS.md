# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 当前主分支基线：8c8a4af7448908dc7756f6ea7f9b4676d1d6af00
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场有限元求解器。
- 已交付主线：P0–P8 与 B0–B5 小算例基线；不代表已完成大规模生产扩展。
- 公开知识网站：website/，VitePress；只有合并到 main 的正式栏目内容进入生产网站。
- 网站构建：GitHub Actions Website Build Check；Cloudflare Pages 生产分支为 main（以实际 Pages 设置为准）。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 当前已验证最多 4 MPI ranks，不等于大规模生产验证 |
| 网站框架与初始知识栏目 | 已合并 | VitePress 构建由 CI 验证 |
| Codex 跨任务进度管理 | 已合并（PR #3） | 通过本文件、任务队列和会话日志恢复 |
| 知识文章模板与采集流程 | 已合并（PR #3） | Codex 只生成公开草稿，人工审核后发布 |
| PETSc NonlinearSession 优化 | 已审计、待细分测量 | 先确认对象生命周期和实际性能瓶颈，再决定是否实现 |

## 当前焦点

PR #7 已合并；SOLVER-02 完成fluid/elastic多时间步测量，等待审核。结论为暂缓持久化原型；当前没有继续重构的性能依据。

## 最近完成

- PR #3 合并：持续研发进度、任务队列、会话日志、知识模板和采集 Skill。
- PR #4 合并：PETSc 生命周期源码审计与知识草稿；Website Build Check 成功。
- Codex Cloud 的 api.github.com 网络访问已按用户提供的验收报告恢复；GitHub REST API 查询 HTTP 200，gh 身份和仓库权限可读取。
- SOLVER-01 为源码审计；未运行 C++ 数值测试或性能基准。

## 当前检查点

基线8c8a4af；分支perf/multistep-setup-profile；报告docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md。下一任务需在本PR合并后依据需求选择，不自动实施NonlinearSession。

## 恢复规则

每个新 Codex Task 开始时：
1. 读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md 和当前任务相关契约。
2. 检查 main、当前分支、工作区和未合并 PR，避免重复任务。
3. 只领取一个 ready 任务。
4. 每完成一个可验证增量，更新进度、队列和会话日志。
5. 重要改动 commit/push 到独立分支；通过 PR 审核，不直接修改 main。
6. 有复用价值的知识写入 website/drafts/，人工审核后才发布。


## 更新规则

- 只记录已确认的代码、测试和审核状态。
- 未运行的测试和性能实验明确写“未运行”。
- 不把计划、推断写成已实现或已验证。
- 任务合并到 main 后才将队列状态标为 done。
