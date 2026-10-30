# EONSim Codex Session Log

本文件记录有实质代码、算法、验证或知识产出的开发会话。只记录事实，不写无法复现的“已优化”“性能显著提升”等结论。

## 记录模板

~~~markdown
## YYYY-MM-DD — TASK-ID — 简短标题

- Branch / PR:
- Base commit:
- Objective:
- Changed files:
- Implementation:
- Commands executed:
- Tests and results:
- Performance evidence (if applicable):
- Knowledge draft:
- Limitations / unresolved issues:
- Next task:
~~~

## 2026-10-30 — HUB-01 — 持续研发与知识生产基础设施

- Branch / PR: feat/codex-continuous-development-workflow；[PR #3](https://github.com/saitoasukakawaii/EONSim-new/pull/3)。
- Objective: 为 EONSim 建立跨 Codex Task 的进度恢复、任务队列、会话记录和公开知识草稿模板。
- Changed files: CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、website/templates/ 下的文章模板、知识采集 Skill，以及 AGENTS.md 入口。
- Implementation: 定义状态语义、任务领取规则、SOLVER-01 下一任务边界和知识文章证据分级。
- Commands executed: 通过 GitHub 仓库接口创建/更新文档；未在 Codex Cloud 本机执行命令。
- Tests and results: GitHub Actions Website Build Check 在 PR #3 分支上成功；执行了依赖安装和 VitePress 生产构建。未运行 EONSim C++/PETSc/MPI 测试（本次未修改求解器）。
- Performance evidence: 无，本次未进行性能实验。
- Knowledge draft: 本次新增的是模板和工作流，不将其伪装成已验证的数值研究文章。
- Limitations / unresolved issues: 尚未实现自动从测试日志提取数据或自动发布；Codex 需按 Skill 和 AGENTS 规则执行草稿生成。
- Next task: SOLVER-01 PETSc NonlinearSession 生命周期审计。

## 2026-10-30 / SOLVER-01

- 基线：0828f41（PR #3 已合并）；分支 docs/solver-baseline-audit。
- 变更：新增 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md、website/drafts/petsc-object-lifetime.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG。
- 审计：读取 linear_system/nonlinear_system/schur_solver、PetscOwner 及 fluid/solid/fsi 调用链；主 Vec/Mat 跨步保留，SNES 每次 solve 创建；Context 为借用栈引用；计时不完整覆盖构造析构。结论为需要额外测量，SOLVER-02 保持阻塞。
- 实际验证：仓库根目录 `git diff --check` 通过；`git diff origin/main -- src include CMakeLists.txt CMakePresets.json` 为空；website 目录 `npm run docs:build` 成功；仓库根目录 `test ! -d website/.vitepress/dist/drafts` 成功。
- 数值测试/性能实验：未运行；本任务为静态审计，不能据此声明性能收益。
- 知识沉淀：有，已按 eonsim-knowledge-capture 形成草稿并登记；证据为源码分析，数值与性能仍待测量。
- 下一步：人工审核审计报告，再开展固定 transient case 的重复 profiling。
