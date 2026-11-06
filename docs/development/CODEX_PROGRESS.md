# EONSim Codex Development Progress

## FSI-PROD-02A / PR #38检查通过 / 2026-11-06

PR #36、#37 已合入 main `dc378529538259567a78cea9820a202a6187809c`，下方review为历史。
分支 `codex/fsi-tube-qualification`、实现 `a0d228764850fa838229acb6a6e613933070490f`：
同一流体标签的互斥分量混合边界、几何不变的四面体加密和刚性稳态流量基线。
11个串行状态和1/2 rank对照；48边形流量误差1.264676%，12/48边形末档变化
0.410813%/0.024769%，MPI场差2.78e-17、最大净通量4.12e-17。首轮level-2未通过，
保留原结果、门槛不变，追加加密后通过。压强误差仍3.993089%，仅完成流量增量，
PROD-02整体未完成。Debug三项、Release最终两项+复用首轮regions、Python3+26项通过。
[完整证据](../research/data/rigid-tube-2026-11-06/README.md)；
[接口/复现](RIGID_TUBE_QUALIFICATION.md)。本地验收与自审完成；
[PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38) 已创建，待审查，未合并。
云端PETSc3.23.7 Debug/Release各26/26、Python35项、网站与增量证据检查全部通过，
数值测试零失败/零跳过；[云端记录](../research/data/rigid-tube-2026-11-06/cloud-ci.json)。

## FSI-PROD-01 / review / PR #37 / 2026-11-06

用户目标升级为生产级 FSI。主线 `dd27eef` 已合并 PR #36；下方旧 review 状态为历史。
独立分支 `codex/fsi-production-tube` 实施圆形离散流量入口与共形实体壁圆管，
验收包含三时间格式、1/2/4 rank、质量/界面/正几何、同分区恢复与非法输入。
源码远端 `718b7a6` 与本地 `31a04e6` tree 完全一致。仓库脚本/PETSc 3.23.7
Debug/Release 各两项受影响检查通过（tube 与旧 rectangle flow），网格2项、CI选择26项通过。
最大1/4 rank场差5.43e-14，续算差0，质量残差1.56e-17，Jacobian差9.92e-9。
首次负例预期错误及Debug OpenMP启动失败均保留；PID隔离后完整Debug tube通过。
[本阶段证据](../research/data/fsi-tube-2026-11-06/README.md)。本地验收与自审完成；[PR #37](https://github.com/saitoasukakawaii/EONSim-new/pull/37)
已创建；[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42170183765)
Debug/Release 各31/31通过，零失败/零跳过；网站与增量证据检查通过。
源码/证据head `29d8082` 的合并预览 `92a28b5` 与本地验收tree完全一致。
本阶段完成、待人工审查合并；不自动合并。
[生产路线](FSI_PRODUCTION_ROADMAP.md)；[接口和算例](FSI_CIRCULAR_TUBE.md)。
下一阶段为定量圆管/默认稳定化资格，再到 RCR/外壁支撑、实际几何与多节点规模。


## FSI-QA-01 / review / 2026-11-06

PR #35 已由远端合并，基线为 `815755eb15ffb63299487e8f9163ddc9d242a2f2`；下方“未合入main”为历史。完成有界修复 FSI-QA-01：质量预算拒绝非有限初始状态、非正体积/接受步长及累积算术溢出，源码 `80571b102e31dd2e7664a64a39a92efc8402045c`。26项相关Python检查通过；9组归档时间研究的22400条接受步重新分析，36个预算值与原收据精确一致。未重跑C++/PETSc/MPI求解；默认τ数值资格仍未完成，不改变原数值结论。独立分支 `codex/fsi-mass-history-validation`，尚未合并。


## FSI-NEXT-03 / PR #35验收通过 / 2026-11-05

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。

下列FSI-NEXT-03尚未完成/未创建PR描述为历史检查点，不覆盖本节状态。


## FSI-NEXT-03 恢复计算

2026-11-04 已从远端 a67f329 恢复同一分支，核对 main 仍为 4f3a995。默认三网格归档逐文件校验通过（923/743/678 个文件），重新审计 8600/5000/3700 条接受步。使用仓库 restore.sh 和 run.sh 恢复 PETSc 3.23.7 Release，所得可执行文件 SHA-256 为 b4de28ffc6481701b533ec4772f4f0f604cfc18bc15bc63c858ebebae38352da。单一 MPI 队列的 fsi_periodic、fsi_flow、fsi_inlet、fsi_pressure_state 均通过。旧固定 τ 算例缺少原始场和 checkpoint，固定 τ=.05 的三网格与两步长研究从初态重算。完整误差预算、证据审查及 PR/CI 仍待完成。

## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 三网格周期状态已取得，预算验证继续

默认稳定化n=2/4/8分别在86/50/37周期达到完整场连续三周期判据；独立补查的压降三周期判据、无滑移/界面相容和完整接受历史质量/几何检查通过。20相位初步空间场差均递减，实测阶0.81–2.29，不能宣称全场二阶或已进入统一渐近区。三个状态的可恢复归档均逐文件SHA核对通过。

新Release构建对n=8完整周期重放，最大字段相位RMS差3.83e-14（门槛2e-9）；Release相关7/7通过。随后增加源码指纹和精确压降相位检查，已排入单项控制器回归。n=4/n=8追加周期、三网格半步长和100相位正式预算继续；无PR，整体未完成。

## FSI-NEXT-03 当前连续验证

已保存远端检查点 `4119d86`；此后补充完整接受历史终点校验、100相位正式误差预算审计和可恢复证据归档。时间矩阵原数据经完整性加强后重新分析通过。n=2三个追加十周期块完成，经验收缩率0.54–0.57；n=4追加计算继续，n=8第35周期首次通过完整场阈值，尚不构成连续三周期通过。n=2归档923文件SHA逐一核对通过。半步长三网格、剩余误差预算、最新负例回归和最终审查仍未完成，无PR。

## FSI-NEXT-03 时间精度与质量预算已验证，空间研究继续

本地基础提交 `96f232f`，后续改动尚在同一分支实施。三格式完整第二周期的时间精度矩阵已通过：BE 最小受检阶0.864，BDF2 1.882，generalized-alpha 1.981；参考加密差占最小候选误差3.17%–3.21%。累计质量预算的最大误差阶分别约1、2、2。它们是固定tau、n=2的瞬态验证，不替代稳态空间研究。原始配置、压缩CSV/日志和第二周期场已归档 `docs/research/data/fsi-next-03/time-accuracy-final/`。

新增可选 `fsi.checkpoint_interval`，默认仍每个接受步保存，指定停止点/最终接受步必保存；周期研究仅需每周期保存。仓库编译脚本完成 Debug 7/7 受影响回归，证据 `cadence-debug/`；后续纯Python相位采样/压降检查仍继续针对性验证。默认稳定化n=2已在第86周期通过，n=8仍在运行；从已收敛状态追加周期的瞬态估计和真实100相位输出复核正在实施。没有创建PR，也未声称48小时预算耗尽。


## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

更新时间：2026-11-03（Asia/Shanghai）

## FSI-NEXT-02 已合入检查点 / 2026-11-03

实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，基线 main `b2755b6`，独立分支 `codex/fsi-next-02-periodic-flow`。周期离散总流量入口、无滑移弹性壁通道与独立表面/体积质量诊断已实现，本地验收和自审完成；[PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 已合入 main，合并提交为 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`。
[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) PETSc 3.23.7 Debug/Release 各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。Debug/Release 新 flow 各1/1与旧入口/压力各2项通过；三时间格式、1/2 rank、恢复、非法输入、整体Jv、真实9次缩步重放及零形状拒绝均有证据。
Release 六周期、三网格/三步长最大阶段质量残差3.08e-16；累计体积误差随dt减小。空间渐近收敛及严格周期稳态尚未证明，不作性能或大规模结论。[能力说明](FSI_PERIODIC_FLOW.md)、[完整验收与失败记录](../research/data/fsi-flow-2026-11-03/README.md)。

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
- 当前 main：`4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`（FSI-NEXT-02 / PR #33 合并提交）。各历史任务的原始基线与证据仍按对应章节保留。
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

FSI-NEXT-01：基线 `06b05c4`，分支 `codex/fsi-inlet-reliability`，生产实现 `0d93d41`/`69692ee`，最终研究脚本 `32783a5`。固定非零速度入口、弹性顶壁、分布式面积观测与阶段/终点几何检查已完成。本地 PETSc 3.23.7 Debug/Release 各 5 项（4 项主检查 + 1 项旧弹性体补验） 定向检查通过；分场时间研究通过，空间轨迹的时间差/最后空间差为 9.51%；Release 性能完成 10 预热 + 30 正式样本，最多 4 rank。小网格直接法更快，较大网格分块内存更低但无稳定加速结论。已通过 PR #32 合入 main（merge commit `b2755b6`）；此处保留其实现/验证来源和历史测量边界。见 [能力契约](FSI_INLET_AND_RELIABILITY.md) 与 [验收记录](../research/data/fsi-next-2026-11-03/README.md)。

FSI-LOAD-01 已通过 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31) 在远端合并为 `06b05c4`，本 agent 未执行合并。实现 `a6c6761` 的平滑周期压力、共同阶段取值、缩步/签名和接受步历史已交付；原云端 Debug/Release 各 24/24 与网站通过证据仍见 [验收记录](../research/data/fsi-pressure-2026-11-03/README.md)。本轮只重跑受影响的 `fsi_pressure_state`，其余复用历史通过证据，本次未运行。


FEM-G2C 已获用户授权执行，基线 main `1bc87a7`，分支 `codex/p2-transient-diffusion`。目标为 P2 瞬态扩散三种时间格式、完整历史恢复及接受步输出；完成验收后创建 PR。实现 `d19a032` 已完成；本地 Debug 分项与 Release 五项 P2 检查、8 项双 rank 历史故障补验通过。[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 云端 PETSc 3.23.7 Debug/Release 各 15/15 相关检查通过，网站及草稿隔离通过，任务 done，已由远端合并为 `dff9116`（本 agent 未执行合并）。证据见 `docs/research/data/p2-transient-2026-11-03/`。

FEM-G2B：基线 c0745ea，分支 codex/p2-boundary-extension，源码 d6ec424；P2 Robin 与纯 Neumann 已实现，本地 Debug 1/2 rank 相关验证通过，[PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28) 云端 Debug/Release 各 10/10 相关检查通过，已合入 main（1bc87a7），复用历史验收，本次未重跑。

FEM-G2A 已合入 main（c0745ea），原实施基线 main `35bf1a1`，分支 `codex/fem-g2a-p2`。代码 edfc73c 已接入共享边空间、HDF5 分区、P2 稳态 D/N 求解及二次 VTU/PVTU；本地 Debug 1/2 rank 数值验证通过，[PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) 云端 Debug/Release 各 19/19 相关检查通过，任务 done，2026-11-01 已合入 main（c0745ea）。PR #26 已合并；下述待审描述属于合并前检查点。

CI-INCREMENTAL-01 已通过 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 合入 main（merge commit `35bf1a1`）；分支 `codex/pr-incremental-ci`，实现提交 `8f695cc`，含约束提交 `ef20e03`。自动数值 CI 仅 PR 选测，文档/证据后续提交可复用同 PR 成功记录；全量仅手动显式选择。云端首次 Debug/Release 各仅 poisson_verification 1/1 通过；文档提交 `0072295` 的第二次运行实际零构建、零数值测试，完整继承原来源，见 [首次验收](../research/data/ci-incremental-2026-10-31/initial.json)与[复用验收](../research/data/ci-incremental-2026-10-31/reuse.json)。本地 24 项选测/receipt 测试与 6 项证据解析通过，另补 2 项手动入口测试通过；未运行全量、旧锁数值测试或本地求解器构建。该策略已随 PR #26 合入 main 后生效。

DOCS-01 已通过 PR #25 合入，合并提交 `be21882`；G0B/G0/G5/G1 与 PR #24 工程策略保持已交付。当前 main tip 以 Git 为准。
CI-INCREMENTAL-01 将日常数值 CI 改为 PR 选测的 PETSc 3.23.7 Debug/Release；3.19.6 仍仅手动兼容专项，main 上生效以合并为准。合并状态由本地 Git 历史确认，本次未查询 PR #24 的远程 Checks，不能据合并推断其逐项测试结果。

DOCS-01 的开发分支 `codex/markdown-progress-audit` 已合并；范围、逐文件处理与静态验证见 [文档审查记录](MARKDOWN_AUDIT_2026-10-31.md)。

此前 TEST-POLICY-01：仅修改验证约束，不开发、不编译项目。基线 `3df1c31`；约束提交 `ef20e03` 已随 PR #26 合入 main（`35bf1a1`）。默认仅检查新增或受影响行为，历史已通过且未受影响的测试不重跑；全量仅在用户明确要求时运行。规则见 [构建与验证](BUILD_AND_VALIDATION.md)。该文档任务未运行构建、数值测试或 CI，也未修改工作流；后续 CI-INCREMENTAL-01 承接自动选测实现。

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

