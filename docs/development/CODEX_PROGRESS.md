# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 当前主分支基线：c1c7508b1b7287084a6e3fcbbb3fd3666f9e84b0
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场有限元求解器。
- 已交付主线：P0–P8 与 B0–B5 小算例基线；不代表已完成大规模生产扩展。
- 公开知识网站：website/，VitePress；只有合并到 main 的正式栏目内容进入生产网站。
- 网站构建：GitHub Actions Website Build Check；Cloudflare Pages 生产分支为 main（以实际 Pages 设置为准）。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 当前已验证最多 4 MPI ranks，不等于大规模生产验证 |
| 网站框架与初始知识栏目 | 已合并 | VitePress 构建由 CI 验证 |
| Codex 跨 Task 状态管理 | 已合并（PR #3） | CODEX_PROGRESS、CODEX_TASK_QUEUE、CODEX_SESSION_LOG |
| 知识文章模板与采集 Skill | 已合并（PR #3） | 草稿需人工审核，不自动发布 |
| PETSc 对象生命周期审计 | 已合并（PR #4） | 主 Vec/Mat 图跨时间步复用；SNES/KSP/PC 每次 solve 重建 |
| NonlinearSession 持久化 | 未实施 | 先完成 SOLVER-02 性能基线，依据证据决策 |

## 当前焦点

**SOLVER-02：建立多时间步 solver setup 性能基线。**

SOLVER-01 审计报告：
- docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md
- 审计结论：需要额外测量，暂不直接重构持久化 NonlinearSession。
- 知识草稿：website/drafts/petsc-object-lifetime.md。

## 最近完成

- PR #3 合并：持续研发进度、任务队列、会话日志、知识模板和采集 Skill。
- PR #4 合并：PETSc 生命周期源码审计与知识草稿；Website Build Check 成功。
- Codex Cloud 的 api.github.com 网络访问已按用户提供的验收报告恢复；GitHub REST API 查询 HTTP 200，gh 身份和仓库权限可读取。
- SOLVER-01 为源码审计；未运行 C++ 数值测试或性能基准。

## 当前检查点

- 当前 main：c1c7508b1b7287084a6e3fcbbb3fd3666f9e84b0。
- 下一任务：SOLVER-02 多时间步 solver setup profiling。
- 推荐顺序：先 transient fluid，再 elastic FSI；必要时再测 Schur 配置。
- 使用 -solver_report；首轮不启用 -linear_report。
- 不直接实现持久化 SNES/KSP/PC，除非性能证据支持。

## 恢复规则

每个新 Codex Task 开始时：
1. 读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md 和当前任务相关契约。
2. 检查 main、当前分支、工作区和未合并 PR，避免重复任务。
3. 只领取一个 ready 任务。
4. 每完成一个可验证增量，更新进度、队列和会话日志。
5. 重要改动 commit/push 到独立分支；通过 PR 审核，不直接修改 main。
6. 有复用价值的知识写入 website/drafts/，人工审核后才发布。

Goal 使用说明见 [CODEX_GOAL_WORKFLOW.md](CODEX_GOAL_WORKFLOW.md)。Goal 负责当前线程内的连续多轮执行；GitHub 状态文件负责跨 Task 接续。

## 更新规则

- 只记录已确认的代码、测试和审核状态。
- 未运行的测试和性能实验明确写“未运行”。
- 不把计划、推断写成已实现或已验证。
- 任务合并到 main 后才将队列状态标为 done。
