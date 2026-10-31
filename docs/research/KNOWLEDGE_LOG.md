# EONSim Knowledge Log

2026-10-31 状态同步：G0B/G0/G5/G1 与 INFRA-01 已完成 PR #23 集成，PR #24 已合入。以下按任务保留原证据；历史“待验收”只适用于对应检查点。全部 drafts 仍未发布。

本文件是知识资产索引，不代替文章正文、文献阅读笔记或实验原始数据。

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
