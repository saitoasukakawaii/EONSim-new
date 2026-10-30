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

- Branch / PR: feat/codex-continuous-development-workflow；PR #3。
- Objective: 建立跨 Codex Task 的进度恢复、任务队列、会话记录和公开知识草稿模板。
- Changed files: CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、website/templates/、知识采集 Skill、AGENTS.md。
- Implementation: 定义任务状态、领取规则和知识文章证据分级。
- Tests and results: GitHub Actions Website Build Check 成功；未运行 EONSim C++/PETSc/MPI 测试。
- Performance evidence: 无。
- Limitations: 自动从测试日志提取数据和自动发布未实现；知识草稿仍需人工审核。
- Next task: SOLVER-01 生命周期审计。

## 2026-10-30 — SOLVER-01 — PETSc 非线性对象生命周期审计

- Branch / PR: docs/solver-baseline-audit；PR #4，已合并。
- Base commit: 0828f41b62391239b14a05e57a161defae1c8866。
- Objective: 确认 NonlinearSystem 的 Vec、Mat、SNES、KSP、PC、IS 和 callback context 生命周期。
- Changed files: docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md、website/drafts/petsc-object-lifetime.md，以及进度/队列/知识索引。
- Implementation: 只读检查 NonlinearSystem、Schur solver、PetscOwner 和 fluid/solid/FSI 调用链。主 Vec/Mat/稀疏图跨时间步复用；SNES/KSP/PC 及回调上下文每次 solve 重建。
- Tests and results: PR #4 的网站生产构建和 git diff --check 通过。未运行 C++ 数值测试、MPI 对照或性能基准。
- Performance evidence: 无；源码审计不能证明 SNES/KSP/PC setup 是实际瓶颈。
- Knowledge draft: website/drafts/petsc-object-lifetime.md。
- Limitations: 当前计时不能完整归因 SNES 创建/销毁及 PC/AMG setup。
- Next task: SOLVER-02 多时间步 solver setup 性能基线。

## 2026-10-30 — GOAL-LOOP-01 — Codex Goal 工作流

- Branch / PR: docs/codex-goal-driven-development-loop；本次 PR。
- Objective: 把 Codex Goals、GitHub 跨 Task 状态文件和人工 PR 审核连接成可重复的研发循环。
- Changed files: CODEX_GOAL_WORKFLOW.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、KNOWLEDGE_LOG.md、AGENTS.md。
- Implementation: 同步 PR #4 合并后的真实项目状态；将 SOLVER-01 标记为 done、SOLVER-02 设为 ready；记录每个 Goal 一个可验收里程碑的执行规则。
- Tests and results: 本次为文档工作流更新；应由 PR 的 Website Build Check 验证。未运行 EONSim C++/PETSc/MPI 测试。
- Performance evidence: 无。
- Limitations: Goal 继续执行仍受 thread 空闲状态、预算、用户输入和阻塞条件约束；不构成无限后台运行。
- Next task: 用户在 Codex Cloud 启动 SOLVER-02 Goal，完成多时间步 profiling。
