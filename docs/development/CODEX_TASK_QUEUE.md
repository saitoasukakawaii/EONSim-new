# EONSim Codex Task Queue

本队列用于跨 Codex Goal / Cloud Task 接续研发。每个 Goal 只领取一个有明确验收条件的里程碑任务。

## 状态定义

- ready：依赖满足，可以开始。
- in_progress：当前有一个 Goal/Task 正在执行。
- blocked：存在明确阻塞，必须记录原因。
- review：已提交，等待审核或剩余验收；合并不自动代表全部测试通过。
- done：验收证据已记录且已合入 main；通常走 PR，本次按用户明确授权直接整合。
- deferred：暂缓，需由需求或性能证据重新触发。

## 当前队列

| ID | 优先级 | 状态 | 任务 | 交付与验收 |
|---|---:|---|---|---|
| FEM-INTEGRATION | P1 | in_progress | G0B → G0 → G5 → G1 连续主线交付 | 基线及每阶段真实数值/MPI验证、独立审查、最终CI/PR与允许时合并；当前基线恢复 |
| FEM-G0B | P1 | review | 旧存储上的语义与 physics/quantity/hybrid PC 接入 | 依赖基线；独立验收字段、父编号、唯一界面代表、刚体、空本地块及真实求解 |
| BRANCH-02 | P1 | done | 合入新增 G0A 并清理全部 7 个非主分支 | [源提交与检查](BRANCH_CLEANUP_2026-10-31.md)；保留 main，无生产求解器改动 |
| BRANCH-01 | P1 | done | 清理 18 个已合并分支并整合其余 6 个 | [源提交、取舍和检查](BRANCH_INTEGRATION_2026-10-30.md)；不编译，数值验收不随合并自动完成 |
| HPC-02 | P2 | done | 独立流体固定图 COO Jacobian 装配（PR #21 合并） | 证据见 FLUID_COO_ASSEMBLY_2026-10-30；保留默认路径，Release 既有超时等局限按报告记录 |
| FEM-G0A | P1 | done | DoF 语义、存储排列与 FSI 分块预条件详细设计及独立代数参考验证 | [专题与迁移切片](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)；20 项标准库测试通过，设计分支已审查合入；无 C++/MPI/PETSc 数值验收，G0已按后续授权实施验收 |
| FEM-G0 | P1 | review | DoF 语义、排列与物理场/物理量/混合 PC 树 | 现有 Tet4 结果与置换等价、叶子覆盖互斥、空本地块；依赖 G0B 及真实 1/2/4 rank 验收 |
| FEM-G1 | P2 | ready | 规范化 reader、Gmsh4.1、Tri3/Quad4 二维标量闭环 | G0/G5 后；方向/标签/边界/MMS，禁止将读入等同求解 |
| FEM-G2 | P2 | deferred | entity DoF、不同阶空间与通用 Dirichlet/Neumann/Robin | G0/G1 后；trace、lifting、纯 Neumann、modal/nodal 与混合稳定性 |
| FEM-G3 | P2 | deferred | Hex8 及相容混合体网格 | G1/G2 后；过渡面、真实混合 patch、MPI 与几何验证 |
| FEM-G4 | P2 | deferred | form/约束驱动稀疏图与通用并行 VTU | 随 G2/G3 增量交付；远程/面项连接、字段采样、失败不发布 |
| FEM-G5 | P2 | in_progress | BE 映射、变步长 BDF2、两类 generalized-α | BE/BDF2及共同stage alpha已接入独立场/ALE/单体FSI；待最终完整集成回归，继续G1 |
| FEM-G6 | P3 | deferred | 非一致界面投影/mortar 到移动单体 FSI | G2/G4/G5 后；重现、力/功、搜索覆盖、Jv 与分布式对照 |
| FEM-G7 | P3 | deferred | 高阶批次、partial assembly/matrix-free 与预条件 | 目标业务触发；同精度算子对照、总耗时/内存，不只测 kernel |
| FEM-G8 | P3 | deferred | 配置 schema、inspect、recipe；按需 Python/DSL | 易用性随每阶段交付，native 热循环；暂不建设完整编译器 |
| INFRA-01 | P1 | review | 可复现云端构建、MPI 故障修复与核心数值 CI | 原分支 3 个 CI job 成功；合并时修正 ABI 检查范围与证据解析；72a3356 本次主环境 Debug/Release 35/35、旧版针对性7/7通过；新集成 head CI仍待完成 |
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | 本 PR；文件可用、链接有效、网站构建通过 |
| SOLVER-01 | P1 | done | PETSc NonlinearSession 对象生命周期审计 | 源码调用链、对象生命周期表、setup/assemble/solve 计时方案、复用风险和是否实施的建议；本任务不改求解器 |
| SOLVER-01B | P1 | done | 固定 transient 案例的诊断开销基线（依赖 SOLVER-01 已合并） | 1/2 rank、每组至少 3 次、保存命令与原始日志；固定 rank 输出一致；明确计时边界，不将差异当作持久化收益 |
| SOLVER-02 | P1 | done | 多时间步 solver setup 性能基线 | fluid/elastic、各3次、逐步数据和首步/后续步统计；仅测量分析，不改求解器 |
| SOLVER-05 | P1 | done | 修复重复线性求解 KSP 所有权（依赖 SOLVER-01 审计） | 成功/失败/恢复调用均释放 PC；1/2 rank 回归和 Poisson 验证通过；独立 PR |
| SOLVER-03 | P2 | done | Newton 变量/方程一致缩放审查与规格 | 推导缩放后的未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-03B | P2 | deferred | 按 SOLVER-03 规格实现可选一致缩放 | 由具体算例需求及规格审核触发；单位/非均匀尺度、物理验收、约束/反力、1/2 rank 和失败恢复验证 |
| SOLVER-04 | P2 | done | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| SOLVER-04B | P2 | done | 补齐求解器层级算子尺寸（依赖 SOLVER-04） | 只读已有算子；报告 global/local 行列；Schur 1/2/4 rank 与失败/初态收敛回归通过 |
| HPC-01A | P2 | done | 非线性装配阶段计时（HPC-01 的首个增量） | 分别报告 callback/错误同步/最终装配/约束；明确计时边界；Schur 与失败恢复回归通过 |
| HPC-01B | P2 | done | 稳态流体装配阶段基线（依赖 HPC-01A） | 三网格、1/2 rank、各 3 次；阶段范围/原始证据/直接解对照；不将回调等同纯 kernel |
| HPC-01C | P2 | done | transient fluid/FSI 装配阶段测量（用户同意继续建议任务） | 1/2/4 rank、每组 3 次；首步/后续步统计；物理解对照及原始证据 |
| HPC-01D | P2 | done | 独立流体 kernel/插入计时（用户要求继续上一轮建议） | 显式开关；逐rank/逐步计数；steady/transient/tagged 1/2 rank 开关对照通过 |
| HPC-01E | P2 | done | 流体单元计时开关扰动与基线（继续用户已提出候选） | 1/2/4 rank、交替顺序配对重复、warmup；物理解/迭代不变；原始数据和范围 |
| QA-01 | P2 | done | profiling 日志验收加固（PR #20 已合并） | 真实归档日志可解析；非有限/非整数原因与计数、缺失指标/根节点、重复层级及错序步被拒绝；加入 CTest |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合性能数据更新草稿；人工审核后发布 |

新增 FEM-G0–G8 的详细设计、依赖与验收唯一入口是 [通用 FEM 规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) §13。ARCH-01 的规划文档已随 BRANCH-01 集成，不能解释为 G0–G8 实现完成。FEM-G0A 设计与参考验证已按用户后续授权审查合入，子任务 done；本轮只做分支整合，不执行其它阶段。

## HPC-01C：多时间步装配阶段测量

### 目标

使用 PR #13 新增的阶段计时字段，建立可复现的 MPI 装配测量基线。此任务只运行测量、解析日志和分析，不修改求解器代码。

### 执行要求

1. 读取 L2 离散算子计时契约及 PR #13 的实现，准确解释 callback_seconds、failure_sync_seconds、assembly_finalize_seconds、constraint_seconds、assembly_seconds、ghost_seconds 和 linear_seconds。
2. 从现有案例中选择至少一个装配成本足够稳定的代表算例；如资源允许，再增加 transient fluid 或 FSI。
3. 固定 main commit、Release 构建、CPU/内存、编译器、PETSc/MPI 版本、网格、DOF、容差和 PETSc options。
4. 在可用资源范围内运行 1/2/4 rank；每个配置至少 3 次重复，保存原始日志。
5. 报告每步与每次运行的中位数、离散程度和 rank-max 口径；区分首步与稳定步骤。
6. 阶段时间有包含关系且 rank 最大值可能来自不同 rank，不得直接相加或将 callback/assembly_finalize 解释为纯 kernel/纯网络时间。
7. 同时检查 SNES/KSP 迭代数、最终残量和物理解差；不放宽容差。
8. 不将单节点多 rank 结果写成多节点强扩展结论。若 Cloud VM 资源不足，记录阻塞并提供在 HPC 上复现的命令。

### 完成标准

提交可复现命令、环境信息、逐 rank 原始日志、统计表、阶段边界解释和瓶颈结论；明确下一步是优化、需要更细计时，还是暂缓。知识草稿保留在 website/drafts/。

## 任务领取规则

HPC-02 基线：24eae624ee93b3e1989312e1b1b273217571310f。预计工程工作量 7–9 小时：接口与失败语义 1–1.5h，固定图缓存及流体接线 2h，数值/MPI/恢复回归 2–2.5h，Release 配对测量和文档/复核 2–3h。此为工作量估计，不作为实际耗时或完成证据。
范围为独立固定网格 Tet4 流体的 Jacobian COO；残量仍使用原 Vec 插入，FSI/ALE/固体、方程、停止容差和默认装配算法不改变。验收包括空贡献 rank、重复索引、远程行、重复更新清零、非零约束与原始反力、单 rank 局部拒绝后的共同失败和同对象恢复；真实案例覆盖 steady/transient/tagged、压力归一化和同分区重启。性能只报告实测配对数据，不预设加速门槛。

1. 一个 Goal 对应一个主要任务和一个验收终点。
2. 开始时将任务标记为 in_progress；结束时标记为 review 或 done。
3. 任务受阻时记录阻塞与解锁条件，不要无限重试。
4. PR 合并后才能标记 done。
5. 下一 Goal 必须重新读取 main 的最新进度和任务队列。

SOLVER-02 测量已完成，见 docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md；结论为暂缓持久化原型，已由 PR #8 合并。后续优化需由业务规模或新增性能证据触发。

SOLVER-03 本轮因用户要求继续研发而领取，仅完成审查、规格及独立代数验证；实际求解器缩放实现仍需后续独立任务，不引入配置键。

SOLVER-03 规格及精确代数验证见 [审查报告](../research/NEWTON_SCALING_SPEC_2026-10-30.md)，已由 PR #10 合并；未实现求解器坐标缩放。

SOLVER-04 本轮范围：稳态流体单位立方体，2/4/6 subdivisions，1/2 rank；各组直接解参考及 3 次 Schur 重复，保存原始日志、字段差、层级、内存与计时，不外推大规模性能。

SOLVER-04 已完成本轮有界测量，见 [报告](../research/SCHUR_MESH_PROFILE_2026-10-30.md)；已由 PR #11 合并。后续大网格/FSI 或粗层成本测量需明确目标，不根据小样本直接调参。

HPC-01A 实现成功评价的阶段计时，已由 PR #13 合并；HPC-01 尚缺纯 kernel/插入分离与目标规模证据，保持 deferred，不把诊断接线当作完整 profiling 结论。

HPC-01B 已完成稳态三网格装配阶段重复测量，见 [报告](../research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md)，已由 PR #16 合并。未据此改求解器或作纯通信成本归因。

HPC-01C 已完成 fluid/elastic、1/2/4 rank、18次运行及180步测量，见 [报告](../research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md)，已由 PR #17 合并。没有新增 ready 任务；后续仍由用户选择。

HPC-01D 已实现独立流体显式单元计时，并通过 Release/Debug 三案例1/2 rank开关对照，已由 PR #18 合并。FSI/ALE、owned/remote插入分离与计时扰动测量未完成；无新增ready任务。

HPC-01E 已完成1/2/4 rank、每配置5对测量及6次预热，见 [报告](../research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md)，已由 PR #19 合并。观测范围不足以支持固定开销或优化结论；无新增ready任务。

## INFRA-01 阶段记录

基线为 PR #21 合并后的 38a5e51。原分支 d3f69d1 的 [GitHub Actions run 41060786421](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41060786421) 已完成且成功：PETSc 3.23.7 Debug / Release 与 3.19.6 Release 三个 job。本轮只读取历史结果，不重新触发工作流。

源分支后续至 787372e 的恢复说明、精简证据、资源检测、包缓存隔离与单机 MPI 传输适配也已纳入。5745fd3 的 CI 41063030121 三个 job 成功；来源分支已创建 PR #22，本次按用户要求整合。原分支完整记录见 [INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md)；其云端执行属于先前开发会话。

依赖锁、恢复脚本、MPI 失败处理和测试已随分支集成；合并审查额外把 OpenMPI/int32 检查限定为云端显式启用，并使 JUnit 解析拒绝重复、缺失与错误结果。6 项纯 Python 解析器回归通过。

按用户要求，本次不编译，不运行 CMake 配置、CTest、MPI、性能或网站构建。最终集成提交的 Debug/Release 数值回归与环境恢复没有重新验证；原分支成功记录不能替代这些检查。该任务保留 review，后续按用户安排完成集成验收，不自动开启下一轮构建。


## FEM-G0A 范围与交付

10 小时是工程量预算，不是实测耗时。以 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424` 为源码事实基线，开始时最新 main 一致且开放 PR 查询为空。
任务从 in_progress 转为 review；2026-10-30 先按要求本地交付，2026-10-31 用户追加授权提交并推送 `docs/fem-g0a-dof-design`，不创建 PR、不合并、不触发 CI。三种分组、固定 K/W 与 lifting/置换、父块分布式编号、所有权/失效/成本和后续切片见专题。
20 项 Python 标准库参考测试只证明合成代数与分区索引逻辑；不构成真实 MPI/PETSc、FSI 稳定性、性能或 INFRA-01 最终集成验收。FEM-G0 整体不标 done。


## BRANCH-02 / 2026-10-31

用户追加授权合并并清理远程分支，替代上面 FEM-G0A 原交付阶段的“不合并”限制。已审查 G0A 源提交并复验 20 项参考测试；检查工具的 UTF-8/CRLF 修复通过正反例。FEM-G0A 为设计子任务完成，FEM-G0 整体及 G0B/G5/G1 的生产开发尚未执行，INFRA-01 的最终集成数值验收仍 review。分支及提交清单见合并清理记录。

## FEM-INTEGRATION：2026-10-31 授权与检查点

接续检查点：`47b5bd4` 已合入G0，主线数值CI成功；新分支 `codex/fem-time-mesh`。
整体任务 in_progress。G0B已有实现；G0完整验收补强 in_progress；G5、G1仍为已授权待依赖完成。
本轮剩余工程量估计（非实测耗时）：基线复核3–5h，G0补验4–8h，G5 35–55h，G1 25–40h，最终集成6–10h。
用户明确允许当前WSL2验证，并要求CI云端复验。前序4CPU/32GiB云机记录不用于描述当前执行器。

用户已明确授权 G0B/G0/G5/G1 实现、依赖恢复、真实构建/MPI验证、阶段提交推送、审查后PR和受保护规则约束的主线合并。其它 deferred 阶段仅实施本闭环必需子集。ready 表示已授权，仍须遵守行内依赖，不代表可并行跳过前置验收。

- 基线 main：`72a335604a50c1ae27516b8bde15e05564b5748b`；开始时无未合并 PR。分支 `codex/fem-g0-g5-g1`。G0A 已合入，复用现有20项参考验证，不重复开发。
- 快照旧未提交 G0A 文件已保护至 git stash（`preserve restored FEM-G0A work before integrated implementation`）及 `/workspace/recovery/fem-g0a-20261031/`，不混入本实现。
- 工程量估计（不是实际耗时）：基线3–5h，G0B/G0 16–24h，G5 35–55h，G1 25–40h，最终集成6–10h。
- 资源：cgroup 4 CPU、32 GiB；使用仓库锁恢复 PETSc3.23.7 于 `/workspace/eonsim-cloud`，命令退出0。基线首次配置发现快照旧缓存引用已消失的 `/tmp/infra-pristine` Ninja；旧目录移至证据区保留，正在从空构建目录重跑。
- 当前没有新增生产能力或完成数值验收；INFRA-01 保持 review。证据临时目录 `/workspace/engineering-evidence/`，完成后提交精简可复现结论。
- 后续顺序：主环境 Debug/Release all → 3.19.6 failure/state → G0B生产适配及G0验收 → G5 → G1 → 完整回归与审查/CI/主线交付。

### 基线验收更新

锁定主环境从新的依赖前缀恢复，清空（移走保护）快照中的旧构建产物后运行 Debug/Release `all`，实际各35项全部通过。3.19.6 Debug `mpi-failure` 7项全部通过。运行时链接及2/4 rank主环境预检通过；恢复命令再次执行成功。精简机器可读清单见 [baseline.json](../research/data/fem-integration-2026-10-31/baseline.json)。Release/legacy 的 dirty 标记包括任务文档及尚未接入构建的新头文件；当时生产代码仍为72a3356。

G0B/G0当前生产实现、独立审查与主环境43/43各模式通过；兼容环境10项失败状态、7项分组重启、最新4项补验通过。状态review，待整体CI/PR/main；G5/G1尚未实现。
