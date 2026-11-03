# EONSim Codex Development Progress

## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

更新时间：2026-11-03（Asia/Shanghai）

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。

## FSI-NEXT-02 当前检查点 / 2026-11-03

实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，基线 main `b2755b6`，独立分支 `codex/fsi-next-02-periodic-flow`。周期离散总流量入口、无滑移弹性壁通道与独立表面/体积质量诊断已实现，本地验收和自审完成；状态 review，[PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 已完成自动CI，未合并，不自动合并。[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) Debug/Release各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。
Debug/Release 新 flow 各1/1与旧入口/压力各2项通过；三时间格式、1/2 rank、恢复、非法输入、整体Jv、真实9次缩步重放及零形状拒绝均有证据。Release 六周期、三网格/三步长最大阶段质量残差3.08e-16；累计体积误差随dt减小。空间渐近收敛及严格周期稳态尚未证明，不作性能或大规模结论。
[能力说明](FSI_PERIODIC_FLOW.md)、[完整验收与失败记录](../research/data/fsi-flow-2026-11-03/README.md)。本地与API提交tree一致；不把元数据差异视为数值结果变化。FSI-NEXT-01 已经 PR #32 合入 `b2755b6`；下文其未合并描述仅是历史检查点。

## 历史集成交付：G0B → G0 → G5 → G1 已合入 main

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
- 当前任务基线 main：`06b05c4`（PR #31 已合并）；本分支源码检查点 `32783a5`。早期整合证据按其原提交保留。
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场及 Tri3/Quad4 二维标量有限元求解器。
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
| 通用 FEM 与 20 组上游学习规划 | 文档已集成 | 16 份 Markdown 随设计分支合入；G0B/G0/G5/G1已交付；其它阶段仍deferred，按需依赖子集除外 |
| FEM-G0A DoF/FSI 分块详细设计 | 已审查合入 | [专题](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)、标准库参考模型及 20 项测试交付；无 C++ 接入或数值验收 |
| 可复现云环境与 MPI 故障 CI | 已随 PR #23 完成集成验收 | 最终主锁 Debug/Release 各60/60、兼容专项13/13；证据见 FEM_INTEGRATION_VALIDATION.md |
| G0B/G0语义DoF与三recipe | 已合入 main（PR #23） | DoF语义、物理验收与三种PC树已完成集成验证；不代表生产内存重排 |
| PETSc CI 与持续知识积累规则 | 已合入 main（PR #24） | 日常仅 PETSc 3.23.7 Debug/Release；3.19.6 手动专项；AGENTS 与状态/知识文件同步更新 |

## FSI-NEXT-01 及此前任务的历史检查点

FSI-NEXT-01：基线 `06b05c4`，分支 `codex/fsi-inlet-reliability`，生产实现 `0d93d41`/`69692ee`，最终研究脚本 `32783a5`。固定非零速度入口、弹性顶壁、分布式面积观测与阶段/终点几何检查已完成。本地 PETSc 3.23.7 Debug/Release 各 5 项（4 项主检查 + 1 项旧弹性体补验） 定向检查通过；分场时间研究通过，空间轨迹的时间差/最后空间差为 9.51%；Release 性能完成 10 预热 + 30 正式样本，最多 4 rank。小网格直接法更快，较大网格分块内存更低但无稳定加速结论。全部本地验收与记录完成后创建 PR，尚未合并。见 [能力契约](FSI_INLET_AND_RELIABILITY.md) 与 [验收记录](../research/data/fsi-next-2026-11-03/README.md)。

FSI-LOAD-01 已通过 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31) 在远端合并为 `06b05c4`，本 agent 未执行合并。实现 `a6c6761` 的平滑周期压力、共同阶段取值、缩步/签名和接受步历史已交付；原云端 Debug/Release 各 24/24 与网站通过证据仍见 [验收记录](../research/data/fsi-pressure-2026-11-03/README.md)。本轮只重跑受影响的 `fsi_pressure_state`，其余复用历史通过证据，本次未运行。


FEM-G2C 已获用户授权执行，基线 main `1bc87a7`，分支 `codex/p2-transient-diffusion`。目标为 P2 瞬态扩散三种时间格式、完整历史恢复及接受步输出；完成验收后创建 PR。实现 `d19a032` 已完成；本地 Debug 分项与 Release 五项 P2 检查、8 项双 rank 历史故障补验通过。[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 云端 PETSc 3.23.7 Debug/Release 各 15/15 相关检查通过，网站及草稿隔离通过，任务 done，已由远端合并为 `dff9116`（本 agent 未执行合并）。证据见 `docs/research/data/p2-transient-2026-11-03/`。

FEM-G2B：基线 c0745ea，分支 codex/p2-boundary-extension，源码 d6ec424；P2 Robin 与纯 Neumann 已实现，本地 Debug 1/2 rank 相关验证通过，[PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28) 云端 Debug/Release 各 10/10 相关检查通过，已合入 main（1bc87a7），复用历史验收，本次未重跑。

FEM-G2A 已合入 main（c0745ea），原实施基线 main `35bf1a1`，分支 `codex/fem-g2a-p2`。代码 edfc73c 已接入共享边空间、HDF5 分区、P2 稳态 D/N 求解及二次 VTU/PVTU；本地 Debug 1/2 rank 数值验证通过，[PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) 云端 Debug/Release 各 19/19 相关检查通过，任务 done，2026-11-01 已合入 main（c0745ea）。PR #26 已合并；下述待审描述属于合并前检查点。

CI-INCREMENTAL-01 已实现并在 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 待审（review，未合并）；分支 `codex/pr-incremental-ci`，实现提交 `8f695cc`，含约束提交 `ef20e03`。自动数值 CI 仅 PR 选测，文档/证据后续提交可复用同 PR 成功记录；全量仅手动显式选择。云端首次 Debug/Release 各仅 poisson_verification 1/1 通过；文档提交 `0072295` 的第二次运行实际零构建、零数值测试，完整继承原来源，见 [首次验收](../research/data/ci-incremental-2026-10-31/initial.json)与[复用验收](../research/data/ci-incremental-2026-10-31/reuse.json)。本地 24 项选测/receipt 测试与 6 项证据解析通过，另补 2 项手动入口测试通过；未运行全量、旧锁数值测试或本地求解器构建。默认 main 行为要在 PR 合并后才改变。

DOCS-01 已通过 PR #25 合入，合并提交 `be21882`；G0B/G0/G5/G1 与 PR #24 工程策略保持已交付。当前 main tip 以 Git 为准。
CI-INCREMENTAL-01 将日常数值 CI 改为 PR 选测的 PETSc 3.23.7 Debug/Release；3.19.6 仍仅手动兼容专项，main 上生效以合并为准。合并状态由本地 Git 历史确认，本次未查询 PR #24 的远程 Checks，不能据合并推断其逐项测试结果。

DOCS-01 的开发分支 `codex/markdown-progress-audit` 已合并；范围、逐文件处理与静态验证见 [文档审查记录](MARKDOWN_AUDIT_2026-10-31.md)。

此前 TEST-POLICY-01：仅修改验证约束，不开发、不编译项目。基线 `3df1c31`；约束提交 `ef20e03` 已随 PR #26 推送待审（review，未合入 main）。默认仅检查新增或受影响行为，历史已通过且未受影响的测试不重跑；全量仅在用户明确要求时运行。规则见 [构建与验证](BUILD_AND_VALIDATION.md)。该文档任务未运行构建、数值测试或 CI，也未修改工作流；后续 CI-INCREMENTAL-01 承接自动选测实现。

## 最近完成

- BRANCH-02：审查合入 FEM-G0A 分支，清理 7 个已整合的非主分支；本次按用户明确授权直接合入 main。
- FEM-G0A：详细设计、代数参考模型与 20 项测试已合入；没有新增生产 C++ 能力。

- PR #21：HPC-02 独立流体可选固定 COO Jacobian；原测试和测量范围以报告为准，本轮未重跑。
- ARCH-01：通用 FEM 架构与学习路线 16 份文档已集成；未发布知识草稿，非实现完成声明。
- BRANCH-01：删除已完全合并的 18 个远程分支，审查整合其余 6 个；按用户明确授权直接合入 main，来源 CI 分支已有 PR #22，本会话未新建 PR。
- INFRA-01：整合时修正锁定 ABI 范围和 JUnit 完整性；当时未完成的最终数值验收已由 PR #23 补齐。

- PR #3：持续研发进度、任务队列、会话日志、知识模板和采集 Skill。
- PR #4：PETSc 对象生命周期源码审计。
- PR #6：Codex Goal 工作流说明及任务状态同步。
- PR #7/#8：非线性诊断开销和多时间步 setup 基线；持久化 NonlinearSession 暂缓。
- PR #9：重复线性求解 KSP 所有权修复。
- PR #10：Newton 缩放规格及独立代数验证；未实现完整求解器缩放。
- PR #11：Schur/GAMG 小规模网格测量。
- PR #12：求解器层级 A 算子 global/local 行列数报告。
- PR #13：非线性装配阶段计时。Release 3 项、Debug 2 项针对性测试通过；未运行重复性能基准。
- PR #24（已合并）：PETSc 3.19.6 从日常矩阵移出；新增持续知识积累项目级规则。

## FSI-NEXT-01 合并前检查点（历史）

FSI-NEXT-01 本地实施与数值研究完成，源码/脚本 `32783a5`；PR 与云端选测状态后续补记。
当前 main 为 `06b05c4`；未运行全量或历史锁；知识文章保留草稿。

### DOCS-01 历史检查点

- 源码基线：`a508e3d`；PR #24 已合入，旧 `codex/primary-petsc-ci-policy` 不再是当前待交付任务。
- DOCS-01 已通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合入 main（`be21882`）。
- 本地只做 Markdown 静态检查；远程 [PR 数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324586) 的 3.23.7 Debug/Release 各 60/60 通过，无失败/跳过；3.19.6 job 按策略 skipped。
- [网站构建与草稿/模板隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324560) 通过；草稿仍未提升为正式文章。无新性能实验。
- PR #23 的 60/60/13 为归档验证，不作为本次新运行结果；实际测试 inventory 随源码/构建配置读取。

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

