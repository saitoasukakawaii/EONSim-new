# L2：离散、算子与约束

状态：采用。首版以 assembled 低阶 FEM 为执行路径；高阶、partial assembly 和 matrix-free 为需求触发的扩展。

### 物理场的实现顺序

- **标量基础：** 先用 Poisson 贯通 mesh/DoF/装配/求解，并为 ALE 网格扩展复用。热输运和 CHT 是后续业务扩展，不先做完整热求解产品。
- **不可压流：** 先稳定化 Stokes，再 Navier–Stokes；等阶 P1/P1 必须有相容的压力稳定化，不能省掉稳定项换取“先跑通”。先保持低 Reynolds 数，不同时加入湍流闭合。
- **固体：** 先独立静/动态线弹性，再用于小变形单体 FSI；有限变形阶段先在独立结构加入可压缩超弹性再耦合。接近不可压缩时才引入相容混合形式，不以极大体积模量掩盖锁死。
- **刚体与耦合：** 流体/固体独立可用后，做单轴刚体动力学和 ALE，再单体刚体 FSI，最后单体弹性 FSI；分离式算法排在单体主线交付后。
- **时间积分：** BE 是独立瞬态及首个单体 FSI 的共同基线，动态固体/刚体按时间关系恢复位移。BDF2 或 generalized-α 在单体弹性基线后按需求引入，并统一各场、接口和切线系数。具体独立未知量见 [单体 FSI](L2_MONOLITHIC_FSI.md)。

统一定义离散残量 `R(x; history, dt)=0`，Newton 解 `J Δx = -R`。首版采用手写局部一致切线或现有可靠公式；AD 在复杂材料确实降低维护成本时引入。修改时间离散后，切线必须包含对应状态/导数之间的链式系数。

### 求解器选型保持直接

| 系统 | 起步选择 | 扩展方式 |
|---|---|---|
| SPD 热传导、约束充分的线弹性 | CG＋合适 AMG；弹性提供刚体近零空间信息 | 依据迭代数调整层级与粗网格 |
| 含对流的一般非对称系统 | GMRES；预条件随迭代变化时用 FGMRES | 按 block 或区域改善预条件 |
| 速度/压力鞍点 | 小模型先用 PETSc 已配置的 LU 直接解作基线，再转 field-split | 为压力 Schur 构造与离散匹配的近似 |
| 非线性/强耦合 | SNES＋明确残量/Jacobian 回调，必要时线搜索 | 一次只改善一个瓶颈，不嵌套大量自定义求解框架 |

对块矩阵 `J=[A B; C D]`，Schur 为 `S=D−C A⁻¹B`。实际实现用子求解作用，不显式形成 `A⁻¹`。压力质量矩阵可作为适用情形的初始近似，不能假定对所有流动、时间步和稳定化都有效；PETSc 的 field-split 也需要问题相容的 Schur 预条件。[PETSc KSP 文档](https://petsc.org/release/manual/ksp/)

## 离散表达与存储表示分开

借鉴 libCEED/MFEM，把算子理解为：全局分布式未知量 → 本地含 ghost 场 → 单元自由度 → 积分点值/梯度 → 物理响应 → 转置累加。对同一试探/检验空间的线性问题，可以用 `A = Pᵀ Eᵀ Bᵀ D B E P` 表示这一分解（此处暂不包含非零本质边界修正）：

| 符号 | 本文语义 | 首版实现责任 |
|---|---|---|
| `P` | 全局 owned 到本地含 ghost 的取值及其反向累加 | MPI/PETSc 适配层 |
| `E` | 本地到单元自由度的 gather/scatter | DofMap/装配计划 |
| `B` | 形函数值、梯度等有限元评价 | 局部 FEM |
| `D` | 积分点系数、几何权重和物理作用 | 几何数据＋物理 kernel |

这是设计分解，不要求显式创建上述矩阵。混合场可以有不同的试探/检验映射；非线性问题用积分点函数及其导数替代固定 `D`，不能强行套成对称正定矩阵。符号用于本文，不混同于各上游库全部 API 的具体记号。

首版只实现 assembled；以后若改 partial assembly 或 matrix-free，保留物理含义，替换存储和 apply 路径。局部积分循环可以融合，避免为每个数学步骤引入一次动态调用。算子作用与几何/系数 setup 分离，但在固定 Tet4 小问题上无须提前做设备调度框架。

## 约束只保留一个事实来源

约束关系由 DoF/constraint 数据描述，装配和解恢复消费同一数据。首版仅实现实际需要的 Dirichlet；周期、悬挂节点、MPC 出现时沿同一语义扩展。不要让 kernel、矩阵后处理和恢复各保存一份独立规则。

FSI 阶段必须增加已明确需要的接口运动学映射：弹性界面速度关联，或有限维刚体运动约束。这些是实际单体装配需求，不要求先实现面向任意约束的通用引擎；当前候选点相关映射的导数不能套用固定约束公式而遗漏。

对线性问题 `Au=b`，以 `u=C û+g` 表示自由未知量到完整场的仿射映射，则缩减系统为 `CᵀAC û=Cᵀ(b−Ag)`。非线性对应 `R̂=CᵀR(Cû+g)`、`Ĵ=CᵀJC`（约束映射固定时）。本节 `C` 与上一节通信映射 `P` 不同；约束随未知量变化的情况需要另行推导。

实现可选择消元或一致的行列处理，不必构造 C。非零边界值修改 RHS/残量的方式必须与切线一致；只清零一行可能破坏 CG 所需对称性。field-split 的 IS、nullspace、图结构和恢复都使用最终有效的代数编号，不从原始 mesh ID 猜测。

## 求解 operator 与预条件器各有职责

### 独立流体的可选固定 COO Jacobian

`-fluid_coo` 只在固定网格独立流体中启用。`NonlinearSystem::set_jacobian_coo` 在首次
solve 前 collective 调用一次，接收本 rank 的全局行/列贡献序列，允许重复项、远程行和空序列。
索引范围及行列长度在准备阶段共同检查；系统额外保留 owned 对角项，以支持仅有约束的行。
PETSc 可以重排准备数组，因此驱动向其传入副本，回调始终使用原始贡献次序。
拓扑、分区或代数编号变化必须重建系统；当前选项不涉及 FSI/ALE、在线重分区或动态稀疏图。

COO 回调看到非空 Mat 时只填借用的 `jacobian_coo_values()` 数值区，不调用矩阵插入或
COO collective。驱动在每次 Jacobian 评价前清零整个缓冲；所有 rank 完成局部评价并汇总
错误后，才用 `MatSetValuesCOO(..., INSERT_VALUES)` 共同覆盖矩阵。该操作仍对重复项求和，
同时恢复上次约束替换前的物理矩阵数值，然后再执行同一 `MatZeroRows`。
失败评价先排空残量 Vec stash，不发布部分 COO 矩阵；原有 domain-error、重试和共同状态
提交规则保持不变。回调不得保存/提交历史，残量-only 评价不触碰 COO 数值。

普通路径的 `assembly_finalize_seconds` 包含 Vec/Mat 最终装配；COO 路径改为包含 Vec
最终装配及集体 COO 数值更新。`callback_seconds` 仍包括局部物理计算和残量插入，COO
下还包含切线缓冲写入。`fluid_element_report.insert_seconds` 在 COO 下测量 Vec 插入及
局部切线复制，**不包含**后续 COO collective。这些指标不可称为纯通信成本，也不可通过
两种路径的 insert 时间直接推导总加速。一次性图准备在 solve/这些阶段计时之外，单独记录
在 `fluid_coo_plan.setup_seconds`，端到端墙钟包括该准备成本。

此扩展采用 PETSc 的[固定 COO 图](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)
和[批量数值更新](https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/)，不新增另一套 MPI
贡献累加逻辑。数值/恢复验收及实测范围见 [HPC-02](../research/FLUID_COO_ASSEMBLY_2026-10-30.md)。

在接口语义上区分 `J_op`（Krylov 使用的 Jacobian 作用）和 `P_mat`（构造预条件的矩阵）；首版二者可就是同一个 Mat。后续采用 matrix-free 时，可保留低阶/简化系数 assembled 预条件矩阵，无需强求完整 Jacobian 存储。近似矩阵仍须满足布局、约束、压力规范和尺度的一致性。

多物理残量按字段报告缩放后的收敛量；温度、速度、压力、位移的原始数值不能直接混成一个无量纲意义不明的总范数。首版在 case 中明确各字段特征尺度或绝对/相对容差，不开发通用单位推理器。

当前 `NonlinearSystem::solve` 从 `AlgebraLayout::fields` 建立 owned 行分组，并检查字段覆盖且互不重叠。剔除 Dirichlet 替换行后，物理方程按 `sqrt(sum((R_i/residual_scale)^2)/N) <= atol + rtol*initial_rms` 接受；约束替换行按 `max(abs(x_i-g_i)/constraint_scale) <= constraint_tolerance` 接受。只有约束而没有物理方程的字段 RMS 为 0；本地空字段仍参与规约。每次检查将所有字段合并为一次平方和规约与一次约束最大值规约，不收集全局向量。原始反力在验收之后单独装配，不进入约束误差范数。

`solver.fields` 非空时要求完整列出实际字段，并显式提供每字段的 `residual_scale`；物理 atol/rtol 默认继承外层 solver，允许字段 rtol=0。约束尺度默认 1，约束绝对容差默认外层 absolute_tolerance。省略整个映射时使用尺度 1 及外层容差，仍执行逐字段检查；这只是原数值单位下的默认值，不是自动无量纲化。每次非线性调用在施加 prescribed 后计算初始范数，尺度与阈值冻结到该调用结束；重试时重新计算初始范数。固体静载的未知量为位移、撤载为速度，约束尺度应按当前求解阶段理解。

默认自定义收敛回调先调用 `SNESConvergedDefault`，其返回正停止原因时再检查字段条件；字段未达标则继续迭代。PETSc options 可以覆盖该回调，最终的重新装配检查始终保留，未达标抛 `StepRejected`，共同状态提交发生在成功返回之后。字段配置错误属于输入错误，不进入缩步。显式字段配置或 `-solver_report` 输出逐字段诊断；最终验收失败总会输出诊断。[PETSc 自定义收敛接口](https://petsc.org/release/manualpages/SNES/SNESSetConvergenceTest/)、[默认收敛测试](https://petsc.org/release/manualpages/SNES/SNESConvergedDefault/)。

当前实现仅缩放接受范数，不改变 J、R 或未知量的求解表示，也未缩放线搜索。`cases/fsi/domains/case.yaml` 给出动量 1 N、连续性 0.01 m³/s、人工网格 0.01 m² 的具体小算例尺度。`nonlinear_acceptance` 的 1/2 rank 检查覆盖 10⁻⁸/10⁸ 方程系数、空本地字段、全约束字段、非零反力及正 SNES reason 的最终拒绝；双域例检查逐块达标、失败不提交及重启。

`-solver_report` 在成功求解后按 rank 顺序输出 `solver_node` 层级：路径、PETSc options prefix、KSP/PC 类型、停止原因数值及名称、该层最后一次迭代数、PETSc 记录的范数及 norm_type。顶层 `linear_iterations` 仍是 SNES 本次调用的累计线性迭代数，子层 `last_iterations` 不作累计解释。`reported_norm` 不是重新计算的物理块残量；`norm_type=0` 表示未计算范数，零值不能作为收敛证据。reason=0 表示没有完成该层求解。

`solver_node` 同时报告 `operator_set` 与 `operator_rows/columns`、`operator_local_rows/columns`，对应此 KSP 的 A 算子（不是可能不同的 P 预条件矩阵）。全局尺寸相对于该算子自身 communicator；local 尺寸是当前 rank 的布局，可为 0。未设置 A 时尺寸为 -1；先用 KSPGetOperatorsSet 判断存在，再读取元数据，不为诊断创建矩阵、装配或做规约。子层 global 尺寸不能按 world rank 相加；这些尺寸不代表非零元、内存或累计工作量。

当前遍历 FieldSplit、ASM/BJacobi 本地块和 MG/GAMG 的粗层/下平滑器；默认共用的上平滑器不重复输出。用户另设的独立上平滑器、额外 Schur A00 求解器和其他 PC 类型的子对象尚未枚举。诊断不调用 PCSetUp 或会创建上平滑器的 getter；未建立或不可读的子树输出 `solver_node_unavailable`，不覆盖原求解结论。识别到顶层 KSP 未收敛或 SNES 线性失败时，先共同刷出所有 rank 的树，再抛出带本 rank 层级的异常，避免后续 MPI_Abort 抢先掩盖远程局部 PC 原因。初始化/配置阶段的 PETSc 错误仍沿原路径报告。

`-linear_report` 同时开启 `-solver_report`，并在每次顶层 KSP 正常收敛后，使用该次实际算子、解与右端项重新计算 `A*x-b`。`linear_residual` 输出原始 L2 范数及右端项范数；`linear_field_residual` 使用与非线性验收相同的 owned 字段划分和尺度，输出方程 RMS 与约束最大值。其独立存储不改变非线性验收基线、解或右端项。这是顶层线性方程的字段残量，不是各子 KSP 的残量，也不作为新的接受条件。KSP 未收敛或开启 PETSc 对角缩放时输出 `linear_residual_unavailable`，避免把不一致的缩放坐标误报为真实残量。

计时输出均取 rank 最大值：`setup_seconds` 为本次 solve 的初始化，不包含 NonlinearSystem 构造；`solve_seconds` 包含初始装配、Schur 配置与 SNESSolve；`schur_setup_seconds` 单独记录显式 Schur 配置；`linear_seconds` 累计顶层 KSP pre/post 回调之间的耗时，包含其中 PC setup 和内层求解；`linear_diagnostic_seconds` 为额外残量测量与输出耗时；`finalize_seconds` 包含最终验收、字段报告及原始反力提取。`linear_started/completed` 统计顶层调用。计时有嵌套关系，且各项最大值可能来自不同 rank，不能相加解释为总耗时；ghost 时间包含在 assembly 时间中。尚无逐子层累计时间或独立 PC setup 计时。

装配细分字段与 `assembly_seconds` 一样，只累计正常完成的 `Context::evaluate`，并在 SNESSolve 返回时冻结，不包含最终验收/原始反力重装配：`callback_seconds` 为物理 assemble 回调（包含 kernel 与 Mat/Vec 插入，不能解释为纯 kernel）；`failure_sync_seconds` 为正常评价路径上的错误状态 MPI_Allreduce 等待；`assembly_finalize_seconds` 为原始 VecAssembly 与 MatAssembly Begin/End；`constraint_seconds` 为约束值替换、约束 VecAssembly 和 MatZeroRows。它们均是 assembly 的子区间，不覆盖清零等全部工作。每项独立取 rank 最大，不能相加还原总时间。失败评价的细分耗时被排除；已有 `ghost_seconds` 在评价开头累计，可能包含后来被拒绝的评价，不能用它与这些字段做严格分解。`assembly_finalize_seconds` 包括本地整理和通信等待，不是纯网络时间；远程插入的准备仍在 callback 内。本增量不提供 kernel/插入各自计时或拒绝评价成本。


跨场材料依赖必须进入导数：例如黏度依赖温度时，一致单体 Newton 需要对应跨场导数。若先用滞后系数或 Picard，明确标记并按完整残量验收。AD 的引入不改变此义务。

依据：[libCEED、MFEM、deal.II、MOOSE 的研究](../research/UPSTREAM_ARCHITECTURE_REVIEW.md)。验证频率只按 [最小验证](../development/BUILD_AND_VALIDATION.md) 执行。


### 独立流体单元级诊断

`-fluid_element_report` 默认关闭，只作用于 `solve_fluid`，不覆盖 FSI/ALE 驱动。启用后每次成功返回的非线性 solve 输出每 rank 的 `rank`、`step`、`local_cells`、`residual_elements`、`jacobian_elements`、`kernel_seconds` 和 `insert_seconds`。两项计数分别是无切线/有切线的已完成单元计算及插入次数；有切线调用同样计算残量，不能把 residual_elements 当作所有残量调用总数。

kernel 区间仅包围 `fluid_element` 调用；insert 区间包围对应体单元 VecSetValues 与可选 MatSetValues，包含本地插入及远程 stash 准备，未拆分 owned/remote 成本。排除状态/编号 gather、参数/几何准备、面载荷计算及插入、最终 Vec/MatAssembly、约束、压力归一化后的反力修正与 I/O。计时在物理驱动层，不向 kernel 引入 MPI/PETSc 或输出。

统计在每个时间步尝试前重置，覆盖该次 solve 中的全部已完成单元调用，**包含最终物理验收和原始反力重装配**；因此不能与 `callback_seconds` 直接相减。若同次 solve 有被拒绝的试探评价，已完成单元工作仍计入；整个 solve 抛错时不输出该次计数，重试重新计数。输出表示非线性 solve 成功，不代替随后时间提交/checkpoint 的成功状态。

时间是 rank-local，未取最大值或求和；使用 PetscSynchronizedPrintf/Flush 按 rank 输出。关闭时不执行单元级时钟读取、计数更新和报告同步；开启时每单元增加时钟读取，开销未量化，不能用本诊断直接证明加速或零开销。

## 编译期拓扑、布局与积分规则

`include/eonsim/discretization.hpp` 统一维护结构常量：

- `CartesianSpace<Dimension>` 给出向量、二阶/四阶张量尺寸及索引。
- `Simplex<Dimension>` 给出 P1 单纯形节点、面节点、Jacobian 体积因子和解析质量权重。
- `NodalLayout<Element, Components>` 推导单元自由度和矩阵尺寸，提供节点优先的 `dof` 与行优先的 `matrix` 索引。
- `FluidLayout<Element>` 定义速度—压力布局；`CoupledLayout<Element, Elastic>` 定义流体、网格及可选弹性结构的偏移。刚体/弹性 FSI 分别实例化，运行时配置选择入口。

现有内核通过 `Tet4Scalar`、`Tet4Vector`、`Tet4Flow`、`Tet4Ale` 等别名使用这些定义；全局节点索引保留调用者整数宽度。模板表达存储与布局，并不意味着已经提供二维物理内核或其他单元类型。

`include/eonsim/quadrature.hpp` 独立维护积分数值：`GaussLegendre<N>` 提供区间 `[0,1]` 的 1–4 点规则，`SimplexGauss<Tet4Topology,4>` 提供二阶精确的四面体对称四点规则，`TetDuffyGauss<N>` 将每轴 Gauss 点映射到四面体，支持 N=2–4。点、重心坐标和权重全部采用 `inline static constexpr` 数组，不在装配过程中生成。四面体权重之和为 1，积分时乘物理体积。

当前 `FluidQuadrature` 选择对称四点规则，`ErrorQuadrature` 选择每轴四点的 Duffy 规则。改变积分策略应修改这些编译期别名并重新验证。`quadrature_moments` 测试按解析单项式积分检查各规则宣称的精确阶数、权重和与质量矩；既有单元导数和 MPI 算例检查装配行为。

数学系数、坐标轴索引、边界物理标签及外部文件格式类型码保留其原有含义，不作为节点数或自由度尺寸处理。

### 外表面几何（B0）

`build_boundary_facets` 为分区持有的每个外表面建立唯一相邻本地 Tet4、面节点局部编号和对顶点；分区将面交给相邻单元 owner，关联构造不需要通信。只在拓扑改变时重建。`triangle_geometry` 用实际三维坐标计算面积，并由对顶点确定单位外法向，不依赖 Gmsh 三角形的排列方向。固定网格驱动缓存面积/法向；FSI 局部残量使用当前 trial 坐标重新评价，因而几何导数仍进入完整耦合切线。

`BoundaryQuadrature=SimplexGauss<Tri3Topology,3>` 在静态模板中维护三点二阶精确规则，权重和为 1，物理面积在调用处相乘。解析线性面载荷仍可用相同拓扑的质量积分矩。局部几何测试覆盖旋转/缩放、闭面法向和、散度定理及非法邻接；不把局部邻接检查当作分区间完整网格拓扑审计。

### 固定网格的标签流体边界（B1）

`fluid.boundaries` 启用显式标签路径。每个外表面标签恰好配置一次，已配置但网格中不存在的标签同样报错；省略该字段时保留既有单位立方体通道基准。标签路径支持三分量或指定笛卡尔分量的速度 Dirichlet、给定牵引与法向压力载荷；分量合并规则见 B2。

- `velocity` / `traction` 使用 `value + gradient*(x-origin)`，坐标为物理坐标，`gradient` 为行优先三行矩阵。速度单位 m/s、牵引单位 Pa，梯度相应除以 m。
- `pressure` 的标量 `value` 表示外加压强 Pa，外法向 n 下 `t=-p*n`，装配残量贡献为 `-integral N*t dA`。它不等同于直接指定节点压力，也不包括黏性切向牵引。
- 非稳态每条条件可设置 `ramp_time`，乘 `min(t/ramp_time,1)`；省略或为 0 时立即施加，稳态使用最终值。初始内部场仍为零，初值字段配置尚未实现。
- 相交速度边界的节点值必须一致；瞬态非零分量还要求相同 ramp。相同约束合并后只在 owned 行施加。自然边界与速度边界共享边缘时，边缘节点仍执行速度约束。
- 全速度边界必须给出 `pressure_gauge: {node: 原始网格ID, value: 压力}`，并检查每个独立 ramp 的闭面净通量相容性。存在牵引/压力边界时禁止额外规范点；首版针对单个连通流体域，不自动处理多连通分量的零空间。

`prepare_fluid_boundaries` 在求解前准备约束和固定几何面载荷，时间步只缩放载荷；牵引不依赖 trial，无额外 Jacobian 项。`summarize_fluid_boundaries` 规约每个标签的面积、外向体积流量和面积平均压力，不收集全局场。边界的完整物理配置参与 checkpoint 签名；64 位规范点 ID 分段编码，避免转 double 丢失低位。

代表案例是 `cases/fluid/rotated_channel.yaml`：2×1.5×0.7 m 的旋转平移通道，标签 11/22/33/44/55/66，线性 Couette 速度及常压力。它检查坐标变换后的精确 patch，不替代非线性一般流动的网格收敛研究。

### 区域与分量约束（B2）

`fluid.regions` / `solid.regions` 是按体 `tag` 的材料列表；配置后要求双向完整覆盖，未配置则使用原有全域材料。流体每区域含 `density/viscosity`；固体含 `young/poisson/density/material`，单元内核不查标签。

边界 `components` 指定全局笛卡尔分量，省略为三个分量。未约束分量为零自然牵引；相交边界逐分量检查冲突。固体 `solid.boundaries` 使用 `type: displacement/traction/pressure`，静载和撤载复用同一约束/载荷准备；恒定位移在动态阶段对应零速度，目前不支持固体时间变化位移。

流体闭面净通量预检查使用与约束装配相同的合并节点值，逐分量按其 ramp 分组后积分。相交标签提供的法向分量必须参与检查，未选分量的占位值不得参与；固定 P1 三角形面采用节点均值精确积分。八顶点立方体的相交分量约束覆盖稳态/独立 ramp、未选分量扰动及真实不相容通量，1/2 rank 验证一致。

固体标签摘要使用参考面积平均位移/速度，P1 面积分为 `area/3 * sum(nodal_value)`，与节点算术平均区分。支座反力为边界替换前的离散残量，正号表示支座对固体的力；只在 owned 节点的实际约束分量求和，不乘面积。每标签只统计该标签位移条件指定的分量，自然载荷标签不输出反力；共享同一受约束 DoF 的标签反力有重叠，独立输出的总支座反力使用合并约束去重。面由相邻单元 owner 唯一积分，节点归属使用完整 `node_boundary_tags`，全部摘要仅规约小数组。未配置标签时保留单位块基准摘要。

`fluid.pressure_normalization: mean` 在法向速度封闭的连通流体域中以最小原始节点 ID 临时定标，求解后减去体积平均压力；该策略是消元再归一化，未声称使用 PETSc 奇异直接解或自动多连通分量零空间。具有自由法向速度的自然边界不能同时指定压力规范。区域、分量和压力策略均加入重启签名。

`regions_verification` 使用两区域 E=100/200、nu=0 的分段精确杆，以及黏度 1/2、法向分量约束和零均压的均匀流，检查 1/2 rank 解及区域配置缺失；固体还包含平移双材料杆的面积平均与反力、旋转非单位几何和相交标签重复约束的总反力检查。


### Schur/GAMG 与一致 ALE 导数（B5）

`-schur_pc` 使用 FGMRES；独立流体分速度/压力，FSI 使用外层乘法 flow/mesh/structure（或 rigid）分裂，flow 内嵌速度/压力 Schur。全局 operator 始终为完整 Jacobian。PETSc FULL Schur 分解配 SELFP 近似 `D−C diag(A)⁻¹B`，不形成 A 的显式逆；速度/压力与网格/弹性块采用 GAMG，刚体块 Jacobi。GAMG 粗层默认 GMRES/Jacobi 并显式启用残差范数；主物理容差未改变。

`fsi_element_tangent` 用解析 `dV/dx`、`d grad(N)/dx` 初始化固定宽度 Dual，前向传播同一个 SUPG/PSPG 残量、网格速度和压力面积项。参考 Laplace 块与接口 BE 链式系数保留。局部状态大小由 Tet4Ale 模板推导，积分规则不包含运行时维护的数据。旧中心差分函数保留用于独立 Jv/轨迹/性能对照。

GAMG 当前只有低 Re 小算例运行证据，不宣称针对高 Re、近不可压结构或网格无关迭代调优完成。实际误差、迭代及 RSS 见 [B5 记录](../development/B5_ACCURACY_AND_PERFORMANCE.md)。
