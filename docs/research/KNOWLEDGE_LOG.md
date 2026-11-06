# EONSim Knowledge Log

## 2026-11-06 / 刚性管混合端面与几何误差分离

新增[数值基准草稿](../../website/drafts/rigid-tube-geometry-and-mixed-boundaries.md)，
实现a0d228764850fa838229acb6a6e613933070490f。理论：充分发展端面应力相容性、
Poisson域单调性给出的cos^4几何界；实现：互斥分量条件、保持多边形的red细分；验证：
11状态/1–2rank、固定门槛加密、Debug/Release与重算；无性能证据。首轮误差抵消及不通过记录保留。
流量误差1.264676%通过，压力仍3.993089%，不扩张为全场/瞬态FSI资格。待审问题是端面定义、
几何界适用对象及剩余局部质量误差；稿件未发布。[证据](data/rigid-tube-2026-11-06/README.md)。

## 2026-11-06 / 质量预算的非有限值拒绝

源码 `80571b102e31dd2e7664a64a39a92efc8402045c`；`max(0., abs(NaN))`可保留0，故初始状态和累积量必须在最大值归约前验证。时间差容差不能替代接受步长严格为正的检查。扩充[既有周期FSI草稿](../../website/drafts/fsi-periodic-state-and-error-separation.md)，未发布。26项Python检查通过，9组归档22400行重算与原36个预算值一致；无新PETSc/MPI或性能证据。命令与复现详见[会话日志](../development/CODEX_SESSION_LOG.md)。PR #35已合并为815755e，下方未合入描述为历史。


## 2026-11-05 / 固定算子周期误差分离与可恢复证据

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](data/fsi-next-03/local-recovery-2026-11-05/README.md)。

[知识草稿](../../website/drafts/fsi-periodic-state-and-error-separation.md)区分理论、实现与实际验证；无性能结论。
人工审查重点：固定τ解释、经验尾项收缩假设、50/100采样含义与非均匀观测阶。草稿未发布。


## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 自审中的复用知识

连续历史仍可能缺失尾部，必须同时核对声明终点；原时间矩阵在校验配置、CSV SHA和可执行文件后重新分析通过。归档明确区分完整标量历史、最后四周期场和可恢复checkpoint，逐文件SHA回读核对。正式场差使用100实际相位，50/100统计差检验相位积分；20相位重建误差另列。相关说明补入原草稿，完整空间/时间污染预算仍未验收，不发布。

## FSI-NEXT-03 误差分离补充

草稿 [周期状态与误差分离](../../website/drafts/fsi-periodic-state-and-error-separation.md) 补充已验证的三格式时间阶和质量预算阶，以及尚在验证的等长追加周期衰减估计、实际密集采样oracle。时间证据 `data/fsi-next-03/time-accuracy-final/`；默认稳定化空间序列仍在运行。经验几何尾项估计必须注明衰减持续的条件，不能写成严格渐近误差界。未发布，无PR。

## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

2026-10-31 状态同步：G0B/G0/G5/G1 与 INFRA-01 已完成 PR #23 集成，PR #24 已合入。以下按任务保留原证据；历史“待验收”只适用于对应检查点。全部 drafts 仍未发布。

2026-11-03 状态同步：当前 main 为 `4f3a995de45d`。FSI-LOAD-01、FSI-NEXT-01、FSI-NEXT-02 已分别通过 PR #31/#32/#33 合入；FEM-G2A/B/C 已通过 PR #27/#28/#29 合入。下列文章均仍是 drafts，源码合入不自动等于知识文章发布；历史检查点保留其当时状态和原始证据。

本文件是知识资产索引，不代替文章正文、文献阅读笔记或实验原始数据。

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。

## FSI-NEXT-02 / 2026-11-03

[周期流量入口与移动域质量预算草稿](../../website/drafts/fsi-periodic-flow-mass-budget.md)：实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，已通过 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 合入 main，合并提交 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`。离散P1入口归一化、无滑移、阶段与secant区别、独立积分和同分区恢复均有实现及验证证据。PR 云端 Debug/Release 各29/29，网站/草稿隔离通过；六周期原始CSV/日志见[验收](data/fsi-flow-2026-11-03/README.md)和 `delivery-ci.json`。无性能证据；空间渐近收敛、严格周期稳态、大规模及高Re均未证明。文章仍待人工审核，未发布。

## G5 独立场generalized-alpha / 2026-10-31

[stage与物理输出草稿](../../website/drafts/generalized-alpha-stage-and-physical-output.md)：
新时刻权重、分离惯性/位移链、算法加速度与端点物理加速度、压力stage及启动。
来源[alpha-standalone.json](data/fem-integration-2026-10-31/alpha-standalone.json)，
理论/实现/真实数值分开，无性能声明。待审核：输出时间语义、启动压力与质量恢复的卸载模型限定；保持draft。

## G5 独立场BDF2 / 2026-10-31

[时间误差与稳定化草稿](../../website/drafts/bdf2-time-error-and-stabilization.md)：
不等距BDF2公式、结构速度未知量重建、固定tau的真实速度/压力时间阶，
卸载结构高频模态进入渐近区的验证。理论、实现、数值证据分开；没有性能结论。
源码与测试来源为[bdf-standalone.json](data/fem-integration-2026-10-31/bdf-standalone.json)。
待审核：稳定化限定、非线性结构/跳跃载荷的未验证边界；保持draft。
后续补充ALE/单体FSI BDF2的压力时间阶、移动网格保持与接口离散功率，
来源[bdf-coupled.json](data/fem-integration-2026-10-31/bdf-coupled.json)，已更新同一草稿；
不将接口功率平衡声称为总能量守恒，非线性材料仅验证状态恢复而非时间阶。

## ARCH-01 / 2026-10-30

[通用 FEM / DoF 分层草稿](../../website/drafts/general-fem-dof-architecture.md)：源码阅读基线
`38a5e516ffe129d1b70c7c1bd8365deb5ded101a`。证据类别为理论/设计与静态实现对应；
没有新数值验证或性能实验，lastVerifiedCommit 留空。配套
[架构规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) 与
[20 组上游学习矩阵](FEM_FRAMEWORK_LEARNING_2026-10-30.md)。
待审核非匹配接口的稳定性选择、时间 stage 相容性、DoF 语义与 PC 分组边界；保持未发布。

## HPC-02 / 2026-10-30

[固定 COO 装配草稿](../../website/drafts/fluid-coo-assembly.md)：实现/测量提交 `ceea57d`，
区分局部贡献求和、实际错误同步、1/2/4 rank 验证和 36 次配对性能测量。
保留准备/内存成本、WSL 环境和既有 MPI 故障测试超时限制；仅独立流体 Jacobian。
待人工审查，未发布。

## 状态定义

- idea：值得研究的主题，尚无完整内容。
- draft：已有草稿，尚未审核。
- review：正在人工审核。
- published：已合并到 main 并出现在公开网站。
- superseded：被更新版本替代，保留历史链接。

## 已发布知识

| Topic | 状态 | 主题 | 文章 |
|---|---|---|---|
| HUB-K001 | published | CFD 求解器学习路径 | [CFD](../../website/learning/cfd.md) |
| HUB-K002 | published | 有限元与固体力学 | [FEM](../../website/learning/fem.md) |
| HUB-K003 | published | HPC 与并行计算 | [HPC](../../website/learning/hpc.md) |
| HUB-K004 | published | EONSim 并行稀疏矩阵装配 | [Parallel Sparse Assembly](../../website/knowledge/parallel-sparse-assembly.md) |
| HUB-K005 | published | EONSim 单体 FSI 架构 | [Monolithic FSI](../../website/knowledge/monolithic-fsi.md) |
| HUB-K006 | published | EONSim 构建与运行 | [Build and Run](../../website/tutorials/build-and-run.md) |

## 候选知识主题

| Topic | 状态 | 主题 | 文章/预期证据 |
|---|---|---|---|
| HUB-K007 | draft | PETSc 非线性求解器对象生命周期 | [PETSc object lifetime](../../website/drafts/petsc-object-lifetime.md)；源码审计已完成，后续 setup 测量见 HUB-K011 |
| HUB-K008 | draft | Newton 变量/残量一致缩放 | [缩放规格草稿](../../website/drafts/newton-scaling.md)；独立代数验证，生产缩放仍 deferred |
| HUB-K009 | draft | Schur/GAMG 网格规模行为 | [网格测量](../../website/drafts/schur-mesh-profile.md)；小规模重复数据 |
| HUB-K010 | draft | MPIAIJ 预分配和装配成本 | [阶段测量](../../website/drafts/assembly-phase-baseline.md)、[单元计时扰动](../../website/drafts/fluid-element-overhead.md)；纯通信归因仍未完成 |
| HUB-K011 | draft | PETSc SNES/KSP/PC setup profiling | [多步测量](../../website/drafts/multistep-setup-profile.md)；未证明持久化收益 |

## 登记规则

- 只有形成可复用知识的任务才登记；普通 typo、纯格式变更不登记。
- 每个条目关联文章路径、源码 commit、参考来源和验证证据（如有）。
- 没有运行数据时不得填写性能数值；没有测试时不得标记为已验证。
- 草稿位于公开仓库，不能存放私密研究笔记、凭据、受限数据或未授权论文全文。
- 发布状态只有在文章进入正式栏目并合并到 main 后才改为 published。

## SOLVER-01 / 2026-10-30

草稿：[PETSc 对象生命周期](../../website/drafts/petsc-object-lifetime.md)。证据：固定提交源码审计；无新增数值/性能实测。待人工核对上下文生命周期与计时边界，未发布。

## SOLVER-01B / 2026-10-30

[诊断开销测量草稿](../../website/drafts/nonlinear-setup-baseline.md)：已运行1/2 rank重复测量，具有源码/输出一致性/性能样本证据；无持久化优化收益证据。待人工审核。

## SOLVER-02 / 2026-10-30

[多时间步setup草稿](../../website/drafts/multistep-setup-profile.md)：源码/重复输出/性能证据已归档；无持久化收益证据，等待人工审核。

## SOLVER-05 / 2026-10-30

[重复线性求解的 KSP 所有权](../../website/drafts/linear-solve-ksp-lifetime.md)：代码提交 c47f00d；PETSc 官方生命周期资料、旧实现失败及修复后 1/2 rank 创建/销毁计数与数值验证。无性能数据，未发布；待审核作用域销毁和测试边界。

## SOLVER-03 / 2026-10-30

[Newton 缩放算法草稿](../../website/drafts/newton-scaling.md)：审查基线 717b25b，规格与精确代数脚本 6dc2baf。理论推导、当前代码和独立代数验证分开列示；无 PETSc 集成及性能证据。待审核尺度配置、约束变换及停止准则，未发布。

## SOLVER-04 / 2026-10-30

[Schur 网格测量草稿](../../website/drafts/schur-mesh-profile.md)：脚本/源码提交 79eb826，6 个直接参考、18 个 Schur 样本及原始证据入 Git。包含理论、实现、数值对照与性能证据；仅 108–1372 DoF、1/2 rank，不支持网格无关性或跨节点扩展结论。待人工审核计时与误差口径，未发布。

## SOLVER-04B / 2026-10-30

[求解器层级算子尺寸草稿](../../website/drafts/solver-level-dimensions.md)：提交 124bed3，记录元数据/communicator 语义、实际代码与 Release 1/2/4 rank 验证。无性能收益证据；未设置算子的哨兵分支未单独触发。待人工审核，未发布。

## HPC-01A / 2026-10-30

[装配阶段计时草稿](../../website/drafts/assembly-phase-timers.md)：提交 fff4895，记录时间规约数学、阶段实现与 Release/Debug 针对性验证；无性能收益或纯 kernel/通信归因证据。待人工审核边界及失败路径，未发布。

## HPC-01B / 2026-10-30

[装配阶段测量草稿](../../website/drafts/assembly-phase-baseline.md)：脚本提交 d1708e1，6 个参考和 18 个 Schur 样本、30 份日志及 JSON 入 Git；包含理论/代码/数值与性能证据，未拆分纯 kernel/插入或纯通信。待审核计时与归因边界，未发布。

## HPC-01C / 2026-10-30

[瞬态装配草稿](../../website/drafts/transient-assembly-profile.md)：测量82081d5，独立固体验证0f90585，统计f92e57b；18次运行180步，1/2/4 rank，最终物理解对照和逐步分布入Git。理论、实现、数值与性能证据分开；无纯kernel归因或多节点结论，待人工审核。

## HPC-01D / 2026-10-30

[流体单元计时草稿](../../website/drafts/fluid-element-timing.md)：源码1722265，解释kernel/插入边界与有/无切线计数；Release/Debug各通过steady/transient/tagged 1/2 rank开关对照。没有性能收益或计时扰动证据；仅独立流体，待人工审核，未发布。

## HPC-01E / 2026-10-30

[流体单元计时扰动草稿](../../website/drafts/fluid-element-overhead.md)：脚本1423b99，30个计量样本/15对及6次预热，逐rank数据和39份日志入Git；理论、实现、数值一致性及性能观测分开。范围不支持固定开销或加速结论，待人工审核，未发布。


## QA-01 / 2026-10-30

[profiling日志校验草稿](../../website/drafts/profile-log-validation.md)：实现7b91030，11项回归覆盖72份归档日志与损坏日志负对照；说明NaN比较、整数原因码与根节点完整性。没有新增数值或性能测量；待人工审查协议范围，未发布。


## INFRA-01 / 2026-10-30

[MPI失败与云端恢复草稿](../../website/drafts/mpi-failure-cloud-reproducibility.md)：d3f69d1实现、旧版最小复现和两环境针对性回归；分开控制流理论、源代码、数值/状态与性能未测量。完整套件和CI以INFRA-01报告为准，尚未发布。


## BRANCH-01 / 2026-10-30

本次按 eonsim-knowledge-capture 更新 [MPI 失败与云端恢复草稿](../../website/drafts/mpi-failure-cloud-reproducibility.md)，补充合并验证边界；沿用原开发记录模板，不另建同题文章。新知识为固定 ABI 探针应按环境启用，以及测试结果不能用条数替代名称完整性。6 项合成 XML 回归只证明解析器行为；没有本次编译、MPI 数值或性能证据。原 INFRA-01 数据保留其原提交出处，最终集成验收未运行；草稿仍未发布。取舍见 [整合记录](../development/BRANCH_INTEGRATION_2026-10-30.md)。


## FEM-G0A / 2026-10-30

按 eonsim-knowledge-capture 的 algorithm-note 模板新增 [DoF 身份与嵌套 FSI 分块草稿](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)。固定源码 SHA `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`；理论为固定 K/W、非零 lifting、置换与父编号推导，当前实现为该 SHA 的源码审计，验证仅为标准库 Fraction 合成代数及 1/2/4 模拟分区索引逻辑。没有性能实测、新 C++ 接口或真实 PETSc/MPI 验证，INFRA-01 保持 review。草稿未发布；待人工审查结构速度语义、界面唯一代表、父编号、验收不变性与证据边界。实施契约只在 [FEM-G0A 专题](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md) 维护。

2026-10-31 合并补记：FEM-G0A 源提交 b674d5a 已完成本次设计/参考验证审查，20 项测试复验通过；检查工具修正 UTF-8 与 CRLF 兼容。设计子任务已合入，知识草稿仍为 draft，生产 C++/PETSc/MPI 验收范围不变。详见 BRANCH-02 合并清理记录。

- 2026-10-31，FEM-G0B：[语义DoF与父编号](../../website/drafts/semantic-blocks-and-parent-numbering.md)，draft。理论/工作区实现/实际小rank检查分级；后续集成与兼容证据已在 PR #23 补齐，不自动发布。

## G0 补强 / 2026-10-31

[真实装配置换与PC验收草稿](../../website/drafts/assembled-permutation-and-pc-verification.md)，按benchmark-report模板。区分置换理论、工作分支实现、主锁Debug/Release 43项与兼容补验、72个受控测量样本。该提交 CI 及最终 PR #23 交付已完成；草稿未发布。

- 2026-10-31，G5耦合alpha：更新[stage与算法历史草稿](../../website/drafts/generalized-alpha-stage-and-physical-output.md)，记录共同stage/独立历史、极小步消减误差与端点集体验收；真实数值与源码审查分级，草稿未发布。

- 2026-10-31，G1：[规范化网格与双线性标量单元](../../website/drafts/normalized-mesh-and-bilinear-scalar-elements.md)，benchmark-report草稿。记录文件/拓扑/空间分离、原生Q1、独立矩阵与收敛、零空间和restart数据文件身份；源码/PETSc-MPI/审查分级，无性能测量，未发布。

## DEV-PROCESS-POLICY / 2026-10-31

项目级持续知识积累规则已写入根目录 [AGENTS.md](../../AGENTS.md)，并同步到 [进度](../development/CODEX_PROGRESS.md)、[任务队列](../development/CODEX_TASK_QUEUE.md) 与 [会话日志](../development/CODEX_SESSION_LOG.md)。要求实质任务保存真实过程与测试证据，维护跨 Task 状态；有复用价值的技术成果才形成 `website/drafts/` 文章，且必须经人工审核后才能发布。该条目记录的是研发流程规则，不是算法或数值结果，因此不另建技术文章。源码/规则变更通过 PR #24 追踪；本任务未运行 C++ 编译、CTest、MPI 或性能测试，CI 结果以 PR Checks 的实际状态为准。


## DOCS-01 / 2026-10-31

基线 `a508e3d`，本地分支 `codex/markdown-progress-audit`。全仓 [Markdown 审查](../development/MARKDOWN_AUDIT_2026-10-31.md) 同步现行状态与历史证据边界，并按 eonsim-knowledge-capture 更新已有 DoF、BDF2、alpha、COO、生命周期草稿；原模板与理论/实现/验证/性能分级保留，没有新数值或性能数据。静态检查命令和未验证项见审查记录。没有新技术成果需要独立文章，所有草稿仍为 draft，未发布。

DOCS-01 交付补记：已通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合入 main（be21882）；远程主锁 Debug/Release 各60/60、网站构建及草稿隔离通过，旧锁专项 skipped。命令与运行链接见 [审查补记](../development/MARKDOWN_AUDIT_2026-10-31.md#远程交付补记)。仍无新算法/性能文章，草稿未发布。


## TEST-POLICY-01 / 2026-10-31

验证约束更新的原始检查点：基线 `3df1c31`，由本地分支 `codex/incremental-validation-policy` 交付；该分支当时未推送、未合入 main。约束内容随后由 CI-INCREMENTAL-01 的提交 `ef20e03` 随 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 合入 main（`35bf1a1`）。规则见[增量验证与历史证据复用](../development/BUILD_AND_VALIDATION.md)：仅检查新增或受影响行为，已通过且未受影响的测试不重跑，全量仅在用户明确要求时运行。原始文档检查未运行编译或数值测试；无新算法/性能结论。


## CI-INCREMENTAL-01 / 2026-10-31

[PR 增量 CI 与证据复用草稿](../../website/drafts/incremental-ci-and-evidence-reuse.md)：基线 ef20e03，开发分支 codex/pr-incremental-ci。说明路径映射、精确测试清单、同 PR 成功证据与必需检查状态的边界；PR #26 已合入 main（`35bf1a1`）；本地脚本检查、云端 Debug/Release 各一项 Poisson 和后续文档提交的零构建/零数值运行复用均已验证，见 [initial.json](data/ci-incremental-2026-10-31/initial.json)及[reuse.json](data/ci-incremental-2026-10-31/reuse.json)。无性能结论，不发布。


### FEM-G2A 局部检查点

P2 参考三角形六节点插值、六个多项式的值/梯度重现及反向边迹已通过直接 C++17 编译验证。源码为本条所属提交；命令与范围见 CODEX_SESSION_LOG 的 FEM-G2A 记录。尚无生产求解、MPI 或收敛证据，完整知识草稿待闭环完成后形成。


### 2026-11-01 — FEM-G2A 共享边空间

[草稿](../../website/drafts/p2-edge-space-poisson.md)：源码 edfc73c，参考基函数、离线实体空间与 P2 稳态 Poisson 已实现；本地 Debug PETSc 3.23.7、1/2 rank patch/收敛/失败证据见 data/p2-2026-11-01。理论、实现与实际验证分列，未测性能，PR #27 云端 Debug/Release 各 19 项相关检查通过，实际 merge preview 60ee8e26；证据 data/p2-2026-11-01/cloud.json。PR #27 已合入 main（`c0745ea`）；文章不发布。


### 2026-11-01 — FEM-G2B 边界与物理均值

更新[现有 P2 草稿](../../website/drafts/p2-edge-space-poisson.md)：源码 d6ec424，新增 Robin 边迹矩阵及纯 Neumann 相容性/零空间/体积均值解释。本地 Debug、PETSc 3.23.7、1/2 rank 相关数值及拒绝检查通过；命令见会话日志，证据 data/p2-boundaries-2026-11-01。PR #28 云端 run 41287626201 的 Debug/Release 各 10 项相关检查通过；PR #28 已合入 main（`1bc87a7`），文章仍未发布。


### FEM-G2C 启动检查点（2026-11-02）

基线 `1bc87a7`，当前未提交改动增加 P2 解析一致质量矩阵 oracle；独立 C++17 检查通过，命令与边界见 [会话日志](../development/CODEX_SESSION_LOG.md)。生产瞬态功能、MPI、checkpoint 尚未实现或验证。本检查点不生成文章，不构成功能交付或性能证据。


### FEM-G2C P2 瞬态历史（2026-11-03）

- 草稿：[P2 瞬态扩散：一致质量、时间层和完整历史](../../website/drafts/p2-transient-history.md)，未审核、未发布。
- 实现 `d19a03268577b33ddfb41177037d9bbc1f76d273`；BE/BDF2/一阶 alpha、P2 空间签名及同分区完整历史恢复、接受步输出。
- 理论证据：一致质量的重心坐标积分、统一时间方程和 alpha 边界时刻；实现与验证分开标记。
- 本地 Debug 分项与 Release 五项 P2 检查通过，真实 1/2 rank；8/8 HDF5 历史/空间补验通过；命令及失败尝试见会话日志，原始摘要见 [源码与证据](data/p2-transient-2026-11-03/source.json)。
- 无全量、旧锁、超过 2 rank 新验证或性能结论；PR 云端结果后续登记，不把本地结果称为云端通过。


FEM-G2C 云端补验：[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29)，run 41582475827，PETSc 3.23.7 Debug/Release 各 15/15 相关项通过；网站 run 41582475766 通过。源码仍为 d19a032，merge preview b8c1642；详见 [云端证据](data/p2-transient-2026-11-03/cloud.json)。PR #29 已合入 main（`dff9116`）；草稿未发布。


2026-11-03 合并状态核对：PR #29 已在远端合并为 dff911648e54507e9cca80ad1880c20b867a0c75，本 agent 没有执行合并。最终云端证据补记提交晚于合并，作为纯文档后续 PR 提交；知识文章仍保持 draft。


## 2026-11-03 / FSI-LOAD-01

- 草稿：[单体 FSI 的时变载荷与接受步历史](../../website/drafts/fsi-periodic-pressure-history.md)，未发布。
- 实现：`a6c6761084f2003c72593107c6aa5cbc351d75bb`；理论为项目阶段时间约定与 smoothstep 多项式，代码为候选步压力及集体输出阶段。
- 验证：[PETSc 3.23.7 Debug/Release 本地证据](data/fsi-pressure-2026-11-03/README.md)，含 1/2 rank、时间精度、恢复、实际缩步、I/O 失败及完整装配切线。
- 复用教训：评价时间与终点量不能混记；双域节点 owner 与本地域单元存在性不同；粗步未进渐近区不能放宽精度门槛。无性能或生产规模结论。

FSI-LOAD-01 补充：PR #31 已合入 main（`06b05c4`）；云端主锁 Debug/Release 各 24/24 与网站检查通过；[CI 摘要](data/fsi-pressure-2026-11-03/ci.json)。草稿仍未发布。

## 2026-11-03 / FSI-NEXT-01

- 草稿：[单体 FSI：非零入口、终点有效性与可解释的加密研究](../../website/drafts/fsi-inlet-endpoint-and-resolution.md)，未审核、未发布。
- 实现 `0d93d41`/`69692ee`，研究脚本 `32783a5`。理论证据为本质边界的线性阶段关系、三角面插值积分；实现与实际验证、性能分开描述。
- [本地验收与数据](data/fsi-next-2026-11-03/README.md)：PETSc 3.23.7 Debug/Release 各 4/4，真实 1/2 rank 拒绝/恢复和切线；分场时间阶、时间污染受控的空间轨迹；Release 30 正式性能样本，最多 4 rank。
- 可复用教训：阶段有效不代表终点有效；界面节点集不等于界面面片；加速度放大位移误差，非线性与线性停止条件须相容；时间污染未控制前不解释空间阶。
- 小网格直接法更快，较大网格分块内存较低，但不证明大规模加速；无非匹配界面、重网格或生产规模结论。详细未验证边界和人工审查问题留在草稿中。

FSI-NEXT-01 补验：旧镜像弹性体几何路径 Debug/Release 各 1/1；本地两模式各累计 5 项独立检查通过，详见同一验收目录。PR #32 已合入 main（`b2755b6`）；知识草稿仍未发布。

## 2026-11-06 — Circular FSI inlet and conforming tube (draft)

[Discrete inlet flux normalization](../../website/drafts/fsi-circular-inlet-discrete-flux.md).
Implementation `718b7a6bb97fbb5eed09829a0bb7225d3963ee5f`; mathematical derivation,
MPI implementation and small-case verification are distinguished. Evidence in
[data/fsi-tube-2026-11-06](data/fsi-tube-2026-11-06/README.md). No performance or
physiological accuracy conclusion. Review required; article remains draft.
