# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 主分支：main
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场有限元求解器。
- 已交付主线：P0–P8 及 B0–B5 小算例基线；不代表大规模生产扩展。
- 公开知识网站：website/，VitePress；生产内容以合并到 main 的文章为准。
- 持续研发基础设施：PR #3 已合并，进度文件、任务队列、会话日志、文章模板和知识采集 Skill 已进入 main。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 不代表已完成大规模生产扩展 |
| 网站框架与初始知识栏目 | 已合并 | VitePress 构建由 CI 验证 |
| Codex 跨任务进度管理 | 已合并 | CODEX_PROGRESS、TASK_QUEUE、SESSION_LOG |
| 知识文章模板与采集 Skill | 已合并 | 草稿需人工审核，不自动发布 |
| PETSc NonlinearSystem 生命周期审计 | 本 PR 审查中 | Vec/Mat 图跨时间步复用，SNES/KSP/PC 每次 solve 重建 |
| NonlinearSession 性能优化 | 暂不实施 | 先完成 SOLVER-02 性能基线 |

## 当前焦点

**SOLVER-01：PETSc NonlinearSystem 生命周期审计。**

源码审计报告：docs/development/NONLINEAR_SESSION_LIFECYCLE_AUDIT.md。知识说明草稿：website/drafts/petsc-nonlinear-object-lifecycle.md。

审计结论：当前不直接重构持久化 NonlinearSession。主要 Vec、AIJ Mat 和稀疏图已经跨时间步复用；下一步先测量每次 solve 的 SNES/KSP/PC setup 开销。

## 最近完成

- PR #3 合并：持续研发进度、任务队列、会话日志、知识模板、知识采集 Skill。
- PR #3 的 VitePress Website Build Check 成功。
- 用户提供 Codex Cloud GitHub 通信验收报告：api.github.com REST API 查询 HTTP 200，gh 身份有效，仓库 API 和 PR 查询成功。
- 完成 NonlinearSystem 源码生命周期审计；未修改 C++，未运行性能基准。

## 恢复工作

新 Codex Task 开始时：
1. 读取本文件和 CODEX_TASK_QUEUE.md。
2. 查看 Git 状态、当前分支和最近提交。
3. 按任务读取 AGENTS.md 和相关 L1/L2 主题契约。
4. 完成一个可验证增量后，更新本文件、任务队列和会话日志。
5. 代码与知识草稿使用同一开发分支，但知识草稿不得自动进入正式栏目。

## 最近一次检查点

- 当前分支：audit/petsc-nonlinear-lifecycle。
- 当前 PR：生命周期审计与知识草稿 PR，等待人工审核。
- 下一任务：SOLVER-02 多时间步 solver setup 性能基线。
- 不要直接实现持久化 SNES/KSP/PC，除非实测证明 setup 开销显著，并明确 callback context、PC reset 和矩阵数值更新策略。

## 更新规则

- 只在真实完成任务或改变当前焦点时更新。
- 测试结果必须记录实际执行命令和结果；未运行的测试写明“未运行”。
- 不把建议、计划、推断写成已实现或已验证。
- 详细会话过程写入 CODEX_SESSION_LOG.md。
