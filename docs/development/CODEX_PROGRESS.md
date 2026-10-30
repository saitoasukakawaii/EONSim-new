# EONSim Codex Development Progress

更新时间：2026-10-30（Asia/Shanghai）

本文件是跨 Codex Task 的当前状态摘要。它只记录已确认的项目状态、当前工作和恢复入口；详细数学契约仍以对应 L1/L2 文档为准。

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 主分支：main
- 软件定位：C++17、MPI、PETSc、三维 Tet4/P1 多物理场有限元求解器。
- 已交付主线：P0–P8 及 B0–B5 小算例基线；能力范围和证据见 ROADMAP.md 与 B5_ACCURACY_AND_PERFORMANCE.md。
- 公开知识网站：website/，使用 VitePress；生产内容以合并到 main 的文章为准。
- 网站构建：GitHub Actions 的 Website Build Check；Cloudflare Pages 生产分支应为 main。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 不代表已完成大规模生产扩展 |
| 网站框架与初始知识栏目 | 已合并 | VitePress 构建由 CI 验证 |
| Codex 跨任务进度管理 | 已合并（PR #3） | 通过本文件、任务队列和会话日志恢复 |
| 知识文章模板与采集流程 | 已合并（PR #3） | Codex 只生成公开草稿，人工审核后发布 |
| PETSc NonlinearSession 优化 | 待审计 | 先确认对象生命周期和实际性能瓶颈，再决定是否实现 |

## 当前焦点

**Milestone 1：建立持续研发与知识生产工作流。**

本 PR 为该工作流建立状态文件、文章模板和 Codex Skill。合并后，下一项软件研发任务是审计 PETSc 非线性求解对象的生命周期，不直接预设需要重构。

## 最近完成

- 建立 EONSim Research & Learning 网站框架及初始学习/知识文章。
- 配置网站 PR 构建检查；最近一次主分支网站构建成功。
- 建立文献到数学规格、算法规格、软件契约和验收测试的研发总纲。
- Codex Cloud 的 api.github.com 出站访问已按用户提供的验收报告恢复；REST API 查询返回 HTTP 200。

## 恢复工作

新 Codex Task 开始时：

1. 读取本文件。
2. 读取 CODEX_TASK_QUEUE.md，选择最高优先级且无阻塞的任务。
3. 查看 Git 状态、当前分支和最近提交，确认没有未提交工作。
4. 按任务读取 AGENTS.md 和相关 L1/L2 主题契约。
5. 完成一个可验证增量后，更新本文件、任务队列和会话日志。
6. 代码与知识草稿使用同一开发分支，但知识草稿不得自动进入正式栏目。

## 最近一次检查点

- 当前焦点：Milestone 1 持续研发与知识生产基础设施；PR #3 已创建，等待人工审查和合并。
- 下一任务：PR #3 合并后领取 SOLVER-01，进行 PETSc NonlinearSession 生命周期审计。
- 下一任务边界：先分析 src/algebra/linear_system.cpp、src/algebra/nonlinear_system.cpp 及调用链，记录 Vec/Mat/SNES/KSP/PC 的创建、更新和销毁时机；不在审计任务中修改求解器实现。
- 验收：提供源码位置、对象生命周期表、每时间步/每 Newton 迭代的分配与装配路径、可能的复用边界、正确性风险和是否值得优化的结论。

## 更新规则

- 只在真实完成任务或改变当前焦点时更新。
- 测试结果必须记录实际执行命令和结果；未运行的测试写明“未运行”。
- 不把建议、计划、推断写成已实现或已验证。
- 详细会话过程写入 CODEX_SESSION_LOG.md，不要把本文件写成逐日流水账。

## 2026-10-30 新检查点

已同步 origin/main 0828f41，PR #3 已合并。完成 SOLVER-01 源码审计，分支 docs/solver-baseline-audit，待 PR 审核。结论：主 Vec/Mat 已跨步复用，SNES 每次 solve 创建；需要 setup/析构进一步测量，暂不实施优化。后续按审计报告设计最小 profiling 实验。以上检查点取代旧的“PR #3 待合并”状态。
