# EONSim Codex Development Progress

更新时间：2026-10-31（Asia/Shanghai）

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

2026-10-31 接续：已 fetch 核实最新 main 为 `47b5bd46c992fcf64cf163361053ceb0091fa5a5`，无开放 PR；工作分支 `codex/fem-time-mesh`。
该 SHA 的云端数值 CI 已成功（主锁 Debug/Release 各43项，兼容锁Release 10项，无失败/跳过），见 [主线CI证据](../research/data/fem-integration-2026-10-31/main-ci.json)。
独立只读审查确认 g0.json 的100份源码哈希与该SHA一致；完整G0仍需补强真实装配置换、逐recipe物理观测和受控性能证据。
本轮用户明确授权 WSL2 开发/验证并由云端CI复验；锁定依赖恢复中，不复用PATH中的ParaView MPI。
以下旧检查点保留为历史；当前总任务仍 in_progress，G5/G1未完成。

从最新main `72a3356` 开展用户授权的G0B→G0→G5→G1整体任务。G0A已合入，未重复开发。
G0检查点已有生产实现、真实数值/MPI验收与独立审查；下一步推送验证检查点并进入G5。
G5/G1尚未实现，整体任务仍in_progress。正式PR在全部阶段验证/审查完成后创建，不直接推送main。

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

- 分支：`codex/fem-g0-g5-g1`，源基线`72a335604a50c1ae27516b8bde15e05564b5748b`。
- 新语义PC树与K/W映射，保留默认方程、编号、验收和旧选项。主环境最新Debug/Release完整43项全部通过，无跳过。
- PETSc3.19.6：失败/状态10项、三recipe/重启7项通过；最新所有权负例及hybrid真实缩步4项补验通过。
- [实际命令、来源清单与结果](FEM_INTEGRATION_VALIDATION.md)。独立审查问题已修复；源码/数值通过不自动等于远程CI或main合并。
- 下一增量：G5统一时间映射与accepted历史，先保留BE回归，再BDF2/两类generalized-alpha及FSI验证；之后G1二维标量闭环。
- 旧快照未提交G0A文件已stash/归档，不混入本分支。知识草稿未发布，未创建正式PR。

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

## 2026-10-31：FEM-INTEGRATION 已启动

从 main `72a3356` 建立 `codex/fem-g0-g5-g1`，执行用户新授权的 G0B→G0→G5→G1 整体任务。当前G0实现与数值验收已完成至review，继续G5；G0A已合入，INFRA基线验收已补齐，新分支CI仍待检查。阶段依赖、验收与工作量估计见 [任务队列](CODEX_TASK_QUEUE.md#fem-integration2026-10-31-授权与检查点)。
