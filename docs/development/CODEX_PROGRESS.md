# EONSim Codex Development Progress

更新时间：2026-10-31（Asia/Shanghai）

## 最新交付：G0B → G0 → G5 → G1 已合入 main

[PR #23](https://github.com/saitoasukakawaii/EONSim-new/pull/23) 已合并，main实现提交
`9cc2e102e8e32f929de1c9a790c1ae527b931fa2`，功能分支最终源码`9e5a1eddf06a02f5e64201d3eff2d55638ddbf13`。
G0B/G0/G5/G1及本整体任务完成；INFRA-01最终集成验收也已补齐。

- DoF语义、独立代表/重建、owned/ghost、存储、物理验收与PC树分离；physics/quantity/hybrid真实PETSc路径验收通过。
- BE、变步BDF2、一阶/二阶generalized-alpha接入各适用独立场、ALE和单体FSI；共同stage、完整链式切线、accepted历史、拒绝与checkpoint已验证。
- Gmsh2.2/4.1 ASCII规范化、Tri3/P1、Quad4/Q1及相容混合二维Poisson/扩散、命名材料与D/N/Robin、纯Neumann、并行分区/输出/重启闭环完成。
- 用户授权WSL2本地Debug/Release各60/60、兼容锁13/13；最终源码109份哈希由独立审查逐份核对，所有测试无失败/跳过。
- [PR云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182613)同样60/60/13通过，
  [push CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199162462)成功，
  [网站及草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182529)成功。
  GitHub合并预览tree与功能提交完全一致；[交付证据](../research/data/fem-integration-2026-10-31/delivery-ci.json)。

用户入口：[DoF与PC](DOF_AND_PC_GROUPING.md)、[时间支持矩阵](TIME_INTEGRATION.md)、[二维标量](SCALAR_2D.md)、[完整验证记录](FEM_INTEGRATION_VALIDATION.md)。
验证最多4rank；没有生产存储重排、二维流体、三维混合体或跨分区重启。G2/G4只实施必要子集，其它阶段仍deferred。
G0性能72样本对应原检查点，小问题直接解更快；没有新的G1性能结论。知识文章保留website/drafts，不发布。
后续只能按具体需求领取新任务，不能把本任务完成解释为G0–G8全部完成。

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
| 通用 FEM 与 20 组上游学习规划 | 文档已集成 | 16 份 Markdown 随设计分支合入；本次已授权G0/G5/G1；其它阶段仍deferred，按需依赖子集除外 |
| FEM-G0A DoF/FSI 分块详细设计 | 已审查合入 | [专题](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)、标准库参考模型及 20 项测试交付；无 C++ 接入或数值验收 |
| 可复现云环境与 MPI 故障 CI | 基线数值验收通过，review | 72a3356主环境Debug/Release各35/35，旧版7/7；新分支CI待检查 |
| G0B/G0语义DoF与三recipe | 实现及数值验收通过，review | 主环境Debug/Release各43/43；3.19.6相关检查通过，待整体PR/合并 |

## 当前焦点

截至 2026-10-31，最新 main 为 `dd490a2c28db846c75642b0125690f922eaef44e`，PR #23 的 G0B/G0/G5/G1 集成已完成。

当前开发分支 `codex/primary-petsc-ci-policy` 对应 PR #24：
- 固化 PETSc 3.23.7 为日常主力版本，Debug/Release 是常规 CI 矩阵。
- PETSc 3.19.6 改为仅手动触发的兼容性专项任务，常规 Push/PR 中明确 skipped。
- 在 `AGENTS.md` 中补充第三方依赖兼容策略及跨 Codex Task 持续知识积累要求。
- 当前变更为工程流程、文档和 CI 配置，不修改求解器生产 C++ 代码；PR 检查以 GitHub 实时状态为准，未完成的检查不得标记为通过。

## 最近完成

- BRANCH-02：审查合入 FEM-G0A 分支，清理 7 个已整合的非主分支；本次按用户明确授权直接合入 main。
- FEM-G0A：详细设计、代数参考模型与 20 项测试已合入；没有新增生产 C++ 能力。

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

- PR：[#24 — ci: make legacy PETSc validation opt-in](https://github.com/saitoasukakawaii/EONSim-new/pull/24)，状态 review。
- 开发分支：`codex/primary-petsc-ci-policy`；基线 main：`dd490a2c28db846c75642b0125690f922eaef44e`。
- 日常 CI 只执行 PETSc 3.23.7 Debug/Release；PETSc 3.19.6 手动兼容任务在 PR 检查中应为 skipped。
- `AGENTS.md` 已纳入持续知识积累要求；本任务同步更新任务队列、会话日志和知识索引。
- 本次没有执行 C++ 编译、CTest 或 MPI；CI 的实际状态和证据链接以 PR #24 Checks 为准。

## 恢复规则

每个新 Codex Task 开始时：
1. 读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md 和当前任务相关契约。
2. 检查 main、当前分支、工作区和未合并 PR，避免重复任务。
3. 只领取一个 ready 任务；若没有 ready 任务，先提出候选，不擅自扩展范围。
4. 每项实质开发任务结束时，按 AGENTS.md 更新进度、队列、会话日志和知识索引；无可复用技术成果时不创建文章。
5. 重要改动 commit/push 到独立分支；通过 PR 审核，不直接推送 main。
6. 有复用价值的知识写入 website/drafts/，人工审核后才发布。

Goal 使用说明见 CODEX_GOAL_WORKFLOW.md。Goal 负责当前线程内的多轮执行；GitHub 状态文件负责跨 Task 接续。

## 更新规则

- 只记录已确认的代码、测试和审核状态。
- 未运行的测试和性能实验明确写“未运行”。
- 不把计划、推断写成已实现或已验证。
- 任务合并到 main 后才将队列状态标为 done。
- 每项实质任务记录源码提交、实际测试命令和结果；未运行或未验证的项目明确标注。

