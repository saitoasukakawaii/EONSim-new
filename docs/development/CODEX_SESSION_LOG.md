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


## 2026-10-30 — SOLVER-01 — PETSc 非线性求解对象生命周期审计

- Branch / PR: audit/petsc-nonlinear-lifecycle；本次审计 PR。
- Base commit: 0828f41b62391239b14a05e57a161defae1c8866。
- Objective: 确认 NonlinearSystem 的 Vec、Mat、SNES、KSP、PC、IS 和 callback context 生命周期，判断是否应立即实现持久化 NonlinearSession。
- Changed files: docs/development/NONLINEAR_SESSION_LIFECYCLE_AUDIT.md；website/drafts/petsc-nonlinear-object-lifecycle.md；CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md；docs/research/KNOWLEDGE_LOG.md。
- Implementation: 只读检查 NonlinearSystem、Schur solver 及 fluid/solid/ALE/FSI 调用方。确认 Vec/AIJ Mat/稀疏图跨时间步复用；SNES/KSP/PC 和 callback 相关状态每次 solve 重建。
- Commands executed: 通过 GitHub 仓库接口读取当前 main 源码并创建文档；未在 Codex Cloud 本机执行构建或运行命令。
- Tests and results: 未运行 C++ 构建、CTest、MPI 算例或性能基准。本次是只读源码审计和文档变更。
- Performance evidence: 无；现有 solver_report 可用于后续基线测量。
- Knowledge draft: website/drafts/petsc-nonlinear-object-lifecycle.md。
- Limitations / unresolved issues: 尚未量化 SNES/KSP/PC setup 的耗时占比；未验证持久化对象的 reset/reconfigure 原型。
- Next task: SOLVER-02 多时间步 solver setup 性能基线。
