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
| BRANCH-01 | P1 | done | 清理 18 个已合并分支并整合其余 6 个 | [源提交、取舍和检查](BRANCH_INTEGRATION_2026-10-30.md)；不编译，数值验收不随合并自动完成 |
| HPC-02 | P2 | done | 独立流体固定图 COO Jacobian 装配（PR #21 合并） | 证据见 FLUID_COO_ASSEMBLY_2026-10-30；保留默认路径，Release 既有超时等局限按报告记录 |
| FEM-G0 | P1 | deferred | DoF 语义、排列与物理场/物理量/混合 PC 树 | 现有 Tet4 结果与置换等价、叶子覆盖互斥、空本地块；本轮只规划 |
| FEM-G1 | P2 | deferred | 规范化 reader、Gmsh4.1、Tri3/Quad4 二维标量闭环 | G0 后；方向/标签/边界/MMS，禁止将读入等同求解 |
| FEM-G2 | P2 | deferred | entity DoF、不同阶空间与通用 Dirichlet/Neumann/Robin | G0/G1 后；trace、lifting、纯 Neumann、modal/nodal 与混合稳定性 |
| FEM-G3 | P2 | deferred | Hex8 及相容混合体网格 | G1/G2 后；过渡面、真实混合 patch、MPI 与几何验证 |
| FEM-G4 | P2 | deferred | form/约束驱动稀疏图与通用并行 VTU | 随 G2/G3 增量交付；远程/面项连接、字段采样、失败不发布 |
| FEM-G5 | P2 | deferred | BE 映射、变步长 BDF2、两类 generalized-α | 独立场到 FSI；时间收敛、压力/界面功、拒绝和完整历史重启 |
| FEM-G6 | P3 | deferred | 非一致界面投影/mortar 到移动单体 FSI | G2/G4/G5 后；重现、力/功、搜索覆盖、Jv 与分布式对照 |
| FEM-G7 | P3 | deferred | 高阶批次、partial assembly/matrix-free 与预条件 | 目标业务触发；同精度算子对照、总耗时/内存，不只测 kernel |
| FEM-G8 | P3 | deferred | 配置 schema、inspect、recipe；按需 Python/DSL | 易用性随每阶段交付，native 热循环；暂不建设完整编译器 |
| INFRA-01 | P1 | review | 可复现云端构建、MPI 故障修复与核心数值 CI | 原分支 3 个 CI job 成功；合并时修正 ABI 检查范围与证据解析；最终集成的数值验证未运行 |
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

新增 FEM-G0–G8 的详细设计、依赖与验收唯一入口是 [通用 FEM 规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) §13。ARCH-01 本轮仅形成本地文档草案，不属于已合并的 done 开发任务；用户明确暂不开发，因此不得自动领取这些 deferred 候选。

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
