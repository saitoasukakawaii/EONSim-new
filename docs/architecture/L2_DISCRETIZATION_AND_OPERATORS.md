# L2：离散、算子与约束

状态：采用。首版以 assembled 低阶 FEM 为执行路径；高阶、partial assembly 和 matrix-free 为需求触发的扩展。

2026-10-30 的扩展契约集中于 [通用 FEM 规划](GENERAL_FEM_ARCHITECTURE_PLAN.md)：§4 区分空间/基/DoF 泛函，§5 规定一般边界与 lifting，§7 分离排列和 PC 树，§8 从形式项及约束支撑生成图，§11 规定批次模板分派。G0 已接入语义身份与 PC 树，G1 已实现二维标量所需边界和图/输出子集；完整多阶空间、通用形式图和高阶批次仍待实现。独立流体 COO 的范围不变。

### 物理场的实现顺序

- **标量基础：** 先用 Poisson 贯通 mesh/DoF/装配/求解，并为 ALE 网格扩展复用。热输运和 CHT 是后续业务扩展，不先做完整热求解产品。
- **不可压流：** 先稳定化 Stokes，再 Navier–Stokes；等阶 P1/P1 必须有相容的压力稳定化，不能省掉稳定项换取“先跑通”。先保持低 Reynolds 数，不同时加入湍流闭合。
- **固体：** 先独立静/动态线弹性，再用于小变形单体 FSI；有限变形阶段先在独立结构加入可压缩超弹性再耦合。接近不可压缩时才引入相容混合形式，不以极大体积模量掩盖锁死。
- **刚体与耦合：** 流体/固体独立可用后，做单轴刚体动力学和 ALE，再单体刚体 FSI，最后单体弹性 FSI；分离式算法排在单体主线交付后。
- **时间积分：** BE 是独立瞬态及首个单体 FSI 的共同基线，动态固体/刚体按时间关系恢复位移。G5 已引入变步 BDF2 与两类 generalized-alpha，统一适用各场、接口和切线系数；具体支持矩阵见 [时间契约](../development/TIME_INTEGRATION.md)。具体独立未知量见 [单体 FSI](L2_MONOLITHIC_FSI.md)。

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
拓扑、分区或代数编号变化必须重建系统；`-fluid_coo` 不涉及 FSI/ALE、在线重分区或动态稀疏图。

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

### FSI 固定图、贡献计划与数值更新

默认 AIJ 与显式 `-fsi_coo` 共用
[`fsi_coupling_pattern.hpp`](../../include/eonsim/fsi_coupling_pattern.hpp) 的物理依赖：
流体测试行依赖流体与 ALE 列，参考网格 Laplace 的每个分量只依赖同一网格分量，
结构测试行依赖结构速度。掩码先作用于物理局部槽，再分别使用 test-row 与 trial-column
映射；接口 mesh 的测试行丢弃，试探列仍通过结构速度或刚体速度的别名参与耦合。
分量约束只删除相应映射，不能把行列合成同一个有效编号集合。

| 未约束 Tet4 的物理依赖槽 | 支持规模 | 完整局部矩阵槽数 |
|---|---:|---:|
| 流体与 ALE | `16*28 + 3*4*4 = 496` | 784 |
| 固体 | `12*12 = 144` | 144 |
| 同一单元评价流体与结构的旧弹性模式 | `496 + 144 = 640` | 1600 |

这些是物理依赖槽数，约束、接口别名和相邻单元合并后才得到代数图。绝不根据某个
Newton 状态的数值零删图。所有 owned 对角项、固定 RCR 的速度与压力耦合、移动 RCR 的
压力/速度行对面内几何列的导数均保留；刚体行列通过同一接口映射和其自身对角项进入图。
两种矩阵路径具有相同的唯一坐标集合，不能把贡献条数当成最终唯一 `nnz`。

默认路径由 reduced layout 的 PREALLOCATOR 直接填充最终 AIJ，并将所有权转给
`NonlinearSystem`，不从完整图反查容量后重建矩阵。数值写入按同一物理掩码打包紧凑矩形，
过滤负行列并保留重复代数 ID 与物理行列次序；当前接口 `mesh_dt` 只在打包时应用。
准备期检查别名测试行的块次序，不能证明贡献累加次序保持时，该单元回退 dense 插入。
最终图填充完成后才开启 `MAT_IGNORE_ZERO_ENTRIES`；该选项不用于推导图。
`MAT_NEW_NONZERO_LOCATION_ERR` 继续拒绝未声明的非零位置；未提供完整图的通用计数
预分配路径仍使用 allocation 检查。紧凑块必须和完整局部切线的物理依赖同步维护。

`FsiAssemblyPlan` 缓存活动分量、测试行、试探列、接口 mesh trace 掩码和接口相邻单元。
拓扑、分区、有效编号与约束支撑固定时计划有效；当前 ALE 坐标变化不重建图。
每次时间步尝试重新使用 `mesh_dt`，不会缓存 generalized-alpha/BDF2 或缩步后的旧链系数。
端口的符号准备和数值评价共用枚举函数，其数值使用本次 trial 几何、压力和时间系数。

`-fsi_coo` 跳过默认 PREALLOCATOR 图。准备阶段把本 rank 的 `K` 条单元/端口/刚体贡献
按 reduced local row 分桶，再按全局行号遍历各桶、在桶内按全局列号排序，合并为 `U`
个不同坐标。输出仍按全局 `(row,column)` 排序，保留 `uint32_t` 的原贡献到数值槽映射。
所有发出的非负测试行须存在于 `local_to_global`；缺失时共同报错。K 项临时行数组在
分桶后释放，随后仅积累 U 项唯一全局坐标；分桶不改变数值贡献的原始累加次序。
超过该索引宽度的本地贡献数共同报错，不截断索引。每次评价先清零 `U` 个值及额外 owned
对角值，再按固定单元、端口、刚体次序累加；接口别名和跨单元重复值在本 rank 合并，
跨 rank 的贡献继续由 PETSc 求和，不额外复制 MPI 反向累加。
`K` 个 scatter 索引及单元局部 tangent 槽仍需存储，值缓冲按 `U + owned` 增长。
图准备的排序、临时坐标、PETSc 内部计划和长期数值缓冲须分别核算。

FSI 残量默认独立启用固定 Vec COO 计划，`-fsi_residual_coo false` 恢复逐单元
`VecSetValues` 对照路径，与矩阵是否使用 COO 无关。残量序列包含单元测试行、每个端口
的牵引与流量行以及 owner 上的刚体项；负行忽略，重复/远程行由 PETSc 累加。
所有 rank 的回调成功后，代数驱动才共同发布 Mat/Vec COO 缓冲；失败缓冲不发布，
已有普通插入的 stash 仍排空。约束替换、原始反力、域错误和时间步提交规则保持一致。
装配模式不是物理状态，可在同分区 checkpoint 恢复时切换。
`NonlinearSystem` 为每个实际发布的回调 Vec 准备残量 COO；不能假定 `VecDuplicate` 会复制
通信计划。持久 residual Vec 在 setter 中准备，SNES 线搜索工作 Vec 首次使用时准备，
后续按对象身份复用；借用 Vec 不被额外保有。Jacobian-only 回调的 scratch 残量没有消费者，
不建立 COO 计划、不发布该残量或替换其约束；物理回调、零缓冲和矩阵约束仍保留。
普通 Vec 插入模式仍共同排空 stash，初始化需要 J 和 R 时仍发布完整残量。

解析 FSI 单元的流体部分由一次 24 方向 Dual 评价同时输出 primal 残量和速度/ALE 导数；
四个节点压力列直接按精确 P1 积分填写。固定和当前 metric 稳定化都与压力无关，
压力 primal 仍参与所有速度/ALE 方向；当前 metric 的 tau 从同一次求值传出，不另算一遍。
若材料或稳定化将来依赖压力，必须同时扩展解析列或恢复相应 AD 方向。
参考网格 Laplace 系数按单元缓存并直接填写同分量切线，当前压力面积项直接使用解析导数。
当前体积和面几何有效性仍检查，零压力不能绕过面检查；FD 参考路径保留。
界面力从接口相邻流体/结构单元的原始物理残量重放，端口牵引另外纳入，不能用已投影残量替代。

默认 `-fsi_threads 1`；OpenMP 构建可显式增加线程数，采用最多 64 单元的有界批次。
线程只评价纯 kernel 并写各自工作区或不重叠的贡献缓冲，主线程按固定次序做 compact
COO 累加和 PETSc 插入。失败在线程 join 后再进入 rank 间错误同步。详见
[线程与通信契约](L2_PARALLEL_MEMORY_AND_BACKENDS.md)。

`FSIFluidAleJac` 包含融合残量，`FSIFluidRes` 只包含独立残量评价；线程批次用
`FSIElementBatch` 记录批次总成本，worker 不调用 PETSc 事件记录。
`FSIInsert` 包含主线程的残量写入/Vec 插入、切线 scatter/Mat 插入，不包含随后的 COO
collective；线程直接写入的不重叠残量缓冲属于批次区间，不另计到主线程 insert。
这些事件有包含关系，不能相加解释为总装配时间。

`-fsi_assembly_report` 在系统构造时输出 `fsi_assembly_plan` 和 `fsi_execution_plan`。
`pattern_seconds` 包含 reduced 编号、ghost 和默认图准备；`plan_seconds` 包含贡献计划、
本地 COO 去重和共同错误检查；`system_seconds` 包含矩阵接管、Mat/Vec 计划准备和临时
索引释放。`setup_seconds` 是各 rank 本地三个区间之和的最大值，不包括中间的物理数据、
边界和输出准备，不能把各区间独立最大值相加代替它。
`cells/interface_cells/coo_entries/coo_value_bytes` 为 rank 求和，`coo_entries` 是 `U`，
值字节数包含额外 owned 对角值；`coo_value_bytes_max` 为最大 rank 的值缓冲量。
`fsi_execution_plan` 另报原始 `coo_contributions=K`、`coo_scatter_bytes`、残量值缓冲字节数、
请求线程数和批次容量。这些数值不包含 PETSc 内部计划、临时坐标及单元局部槽索引。
`solver_report` 的 `nnz_allocated/nnz_unneeded/matrix_mallocs` 仅描述主矩阵。
同输入前后版本的计时入口是 `scripts/benchmark_fsi_assembly.py`；实现契约不替代数值与性能收据。

在接口语义上区分 `J_op`（Krylov 使用的 Jacobian 作用）和 `P_mat`（构造预条件的矩阵）；首版二者可就是同一个 Mat。后续采用 matrix-free 时，可保留低阶/简化系数 assembled 预条件矩阵，无需强求完整 Jacobian 存储。近似矩阵仍须满足布局、约束、压力规范和尺度的一致性。

多物理残量按字段报告缩放后的收敛量；温度、速度、压力、位移的原始数值不能直接混成一个无量纲意义不明的总范数。首版在 case 中明确各字段特征尺度或绝对/相对容差，不开发通用单位推理器。

### 非线性求解器会话与每次验收

`NonlinearSystem` 除固定 Mat/Vec 和本地 trial 缓冲外，默认复用成功调用的 SNES/KSP/PC
会话、字段分组、归约工作区和诊断 Vec。reuse key 精确比较完整 `SolverConfig`、
`PetscOptionsGetAll` 的完整字符串以及 owned 约束行列表；任何 rank 的 key 改变时全部
rank 共同重建。`SolverConfig` 包含 PC recipe、总容差/迭代上限及各字段尺度/容差。
初值、prescribed 约束值、时间步系数和 Jacobian 数值变化不改变 key，每次调用仍重新
施加约束、计算初始字段范数并更新数值。约束行改变后仍须满足既有图的支撑要求；
分区、布局或图改变则重建整个 `NonlinearSystem`。

跨调用复用只适用于 `SNESNEWTONLS`、Jacobian 与 PC lag 都为 1、未启用显式
reuse-preconditioner 的路径；包括子 PC 在内的相关显式选项也保留每次新建语义。
`-snes_ksp_ew true` 和 `-verify_operator_permutation true` 同样使用每次新建会话。
`-nonlinear_reuse false` 强制每次创建新会话，作为同方程/同容差的对照；关闭复用或不符合
上述资格的会话在成功返回时也立即释放，不保留到下一次调用。
新会话在首次需要 Newton 求解时配置 PC 计划；该次起点 Jacobian 可由首个普通
Newton Jacobian 回调消费一次。必须是相同 Vec/Mat、全部 owner 的初值逐项相等，
并且中间没有残量/Jacobian 评价；任何评价先清除资格，所有 rank 共同决定消费。
已配置的合资格 Schur 会话每次从新残量开始，将初始数值 Jacobian 延后到首个
正常 SNES 回调；每次成功的受约束 Jacobian 都刷新其 USER Schur 矩阵，PETSc
根据当前 Mat 数值状态更新数值 PC。`-nonlinear_initial_jacobian_reuse false`
保留预装配与首个回调各自装配的对照，不将旧时间步 Jacobian 当作新起点切线。
复用对象/符号结构不等于沿用旧 Jacobian 或旧数值因子，也不改变物理验收条件。

求解器回调通过稳定 holder 只在本次 solve 内绑定当前 Context，退出即解除借用，不保留
物理回调、初值或 prescribed 的栈引用。SNES/KSP/PC 先于所引用的 Schur USER 矩阵销毁。
任何异常或最终 `StepRejected` 使会话失效，下一次调用重新创建；同一次线搜索中已恢复的
domain rejection 不使最终成功的会话失效。fatal callback 遗留的 trial Vec 只读锁通过
替换该 Vec 隔离，固定矩阵图保留。每次调用重置计数与线搜索初始系数。

`solver_report` 的 `solver_reused=0|1` 表示本次是否复用成功会话，`solver_generation`
是同一 `NonlinearSystem` 的 SNES 创建序号，从 1 递增；这些字段是生命周期证据，不是
性能结论。约束按 owned 行直接替换；全局约束行数为零时跳过无效的 `MatZeroRows`。
报告另计实际完成的 `jacobian_assemblies`、SNES 的 `jacobian_callbacks`、
起点预装配/复用/延后，以及应用自建 nodal USER 矩阵的 `user_schur_updates`；
后者不表示 PETSc 所有内部 PC setup。显式 `-solver_rank_report` 在原报告同步阶段
附加 rank-local 时长与 owned/ghost 规模，默认关闭，不在热回调另加报告规约。

当前 `NonlinearSystem::solve` 从 `AlgebraLayout::fields` 建立 owned 行分组，并检查字段覆盖且互不重叠。剔除 Dirichlet 替换行后，物理方程按 `sqrt(sum((R_i/residual_scale)^2)/N) <= atol + rtol*initial_rms` 接受；约束替换行按 `max(abs(x_i-g_i)/constraint_scale) <= constraint_tolerance` 接受。只有约束而没有物理方程的字段 RMS 为 0；本地空字段仍参与规约。默认用 `(scale,sumsq,constraint_max)` 的可合并状态将所有字段放入一次归约，避免直接平方的溢出/下溢；`-nonlinear_fused_reductions false` 保留两次归约对照。各 rank 共同验证协议，不收集全局向量。

SNESSolve 返回后始终做一次独立的全新原始残量组装，不复用 SNES 已接受的函数值。
先保存该次原始残量的 owned+ghost 反力，再替换 owned 约束行，执行原有范数和字段验收。
解从该次组装已同步的 local trial 缓冲复制；只有验收成功才返回解与反力，失败仍使会话失效。
原始反力不进入约束误差范数，也不再另做第二次相同物理组装。

`solver.fields` 非空时要求完整列出实际字段，并显式提供每字段的 `residual_scale`；物理 atol/rtol 默认继承外层 solver，允许字段 rtol=0。约束尺度默认 1，约束绝对容差默认外层 absolute_tolerance。省略整个映射时使用尺度 1 及外层容差，仍执行逐字段检查；这只是原数值单位下的默认值，不是自动无量纲化。每次非线性调用在施加 prescribed 后计算初始范数，尺度与阈值冻结到该调用结束；重试时重新计算初始范数。固体静载的未知量为位移、撤载为速度，约束尺度应按当前求解阶段理解。

默认自定义收敛回调先调用 `SNESConvergedDefault`，其返回正停止原因时再检查字段条件；字段未达标则继续迭代。PETSc options 可以覆盖该回调，最终的重新装配检查始终保留，未达标抛 `StepRejected`，共同状态提交发生在成功返回之后。字段配置错误属于输入错误，不进入缩步。显式字段配置或 `-solver_report` 输出逐字段诊断；最终验收失败总会输出诊断。[PETSc 自定义收敛接口](https://petsc.org/release/manualpages/SNES/SNESSetConvergenceTest/)、[默认收敛测试](https://petsc.org/release/manualpages/SNES/SNESConvergedDefault/)。

当前实现仅缩放接受范数，不改变 J、R 或未知量的求解表示，也未缩放线搜索。`cases/fsi/domains/case.yaml` 给出动量 1 N、连续性 0.01 m³/s、人工网格 0.01 m² 的具体小算例尺度。`nonlinear_acceptance` 的 1/2 rank 检查覆盖 10⁻⁸/10⁸ 方程系数、空本地字段、全约束字段、非零反力及正 SNES reason 的最终拒绝；双域例检查逐块达标、失败不提交及重启。

`-solver_report` 在成功求解后按 rank 顺序输出 `solver_node` 层级：路径、PETSc options prefix、KSP/PC 类型、停止原因数值及名称、该层最后一次迭代数、PETSc 记录的范数及 norm_type。顶层 `linear_iterations` 仍是 SNES 本次调用的累计线性迭代数，子层 `last_iterations` 不作累计解释。`reported_norm` 不是重新计算的物理块残量；`norm_type=0` 表示未计算范数，零值不能作为收敛证据。reason=0 表示没有完成该层求解。

`solver_node` 同时报告 `operator_set` 与 `operator_rows/columns`、`operator_local_rows/columns`，对应此 KSP 的 A 算子（不是可能不同的 P 预条件矩阵）。全局尺寸相对于该算子自身 communicator；local 尺寸是当前 rank 的布局，可为 0。未设置 A 时尺寸为 -1；先用 KSPGetOperatorsSet 判断存在，再读取元数据，不为诊断创建矩阵、装配或做规约。子层 global 尺寸不能按 world rank 相加；这些尺寸不代表非零元、内存或累计工作量。

当前遍历 FieldSplit、ASM/BJacobi 本地块和 MG/GAMG 的粗层/下平滑器；默认共用的上平滑器不重复输出。用户另设的独立上平滑器、额外 Schur A00 求解器和其他 PC 类型的子对象尚未枚举。诊断不调用 PCSetUp 或会创建上平滑器的 getter；未建立或不可读的子树输出 `solver_node_unavailable`，不覆盖原求解结论。识别到顶层 KSP 未收敛或 SNES 线性失败时，本地输出层级并抛出带rank、phase、PETSc返回码与原始reason的异常；失败诊断不引入collective。PETSc <3.20的顶层KSP postsolve独立于诊断开关归约PC失败布尔标志，阻止旧PREONLY局部原因码分叉进入SNES或残量诊断；负PC枚举也表示失败，不能对原始枚举作MAX推断。3.19.6/3.23.7的实证与边界见[INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md)。初始化/配置阶段的 PETSc 错误仍沿原路径报告。

`-linear_report` 同时开启 `-solver_report`，并在每次顶层 KSP 正常收敛后，使用该次实际算子、解与右端项重新计算 `A*x-b`。`linear_residual` 输出原始 L2 范数及右端项范数；`linear_field_residual` 使用与非线性验收相同的 owned 字段划分和尺度，输出方程 RMS 与约束最大值。其独立存储不改变非线性验收基线、解或右端项。这是顶层线性方程的字段残量，不是各子 KSP 的残量，也不作为新的接受条件。KSP 未收敛或开启 PETSc 对角缩放时输出 `linear_residual_unavailable`，避免把不一致的缩放坐标误报为真实残量。

计时输出均取 rank 最大值：`setup_seconds` 为本次 solve 的准备，包含新会话创建或既有会话检查/重绑定，不包含 NonlinearSystem 构造；`solve_seconds` 包含初始装配、Schur 配置/刷新与 SNESSolve；`schur_setup_seconds` 单独记录求解开始时的显式 Schur 配置/刷新；`linear_seconds` 累计顶层 KSP pre/post 回调之间的耗时，包含其中 PC setup 和内层求解；`linear_diagnostic_seconds` 为额外残量测量与输出耗时；`finalize_seconds` 包含最终验收、字段报告及原始反力提取。`linear_started/completed` 统计顶层调用。计时有嵌套关系，且各项最大值可能来自不同 rank，不能相加解释为总耗时；ghost 时间包含在 assembly 时间中。尚无逐子层累计时间或独立 PC setup 计时。

装配细分字段与 `assembly_seconds` 一样，只累计正常完成的 `Context::evaluate`，并在 SNESSolve 返回时冻结，不包含最终验收/原始反力重装配：`callback_seconds` 为物理 assemble 回调（包含 kernel、Mat/Vec 插入或 COO 值缓冲写入，不能解释为纯 kernel）；`failure_sync_seconds` 为正常评价路径上的错误状态 MPI_Allreduce 等待；`assembly_finalize_seconds` 为普通 Vec/Mat 最终装配，启用 COO 时包含实际回调 Vec 首次计划准备及对应的集体数值更新；`constraint_seconds` 为 owned 约束值替换及有约束时的 MatZeroRows。它们均是 assembly 的子区间，不覆盖清零等全部工作。每项独立取 rank 最大，不能相加还原总时间。失败评价的细分耗时被排除；已有 `ghost_seconds` 在评价开头累计，可能包含后来被拒绝的评价，不能用它与这些字段做严格分解。`assembly_finalize_seconds` 包括本地整理和通信等待，不是纯网络时间；远程插入的准备仍在 callback 内。阶段计时本身不提供 kernel/插入各自计时或拒绝评价成本；独立流体另有下述单元级诊断。


跨场材料依赖必须进入导数：例如黏度依赖温度时，一致单体 Newton 需要对应跨场导数。若先用滞后系数或 Picard，明确标记并按完整残量验收。AD 的引入不改变此义务。

依据：[libCEED、MFEM、deal.II、MOOSE 的研究](../research/UPSTREAM_ARCHITECTURE_REVIEW.md)。验证频率只按 [最小验证](../development/BUILD_AND_VALIDATION.md) 执行。


### 独立流体单元级诊断

`-fluid_element_report` 默认关闭，只作用于 `solve_fluid`，不覆盖 FSI/ALE 驱动。启用后每次成功返回的非线性 solve 输出每 rank 的 `rank`、`step`、`local_cells`、`residual_elements`、`jacobian_elements`、`kernel_seconds` 和 `insert_seconds`。两项计数分别是无切线/有切线的已完成单元计算及插入次数；有切线调用同样计算残量，不能把 residual_elements 当作所有残量调用总数。

kernel 区间仅包围 `fluid_element` 调用；insert 区间包围对应体单元 VecSetValues 与可选 MatSetValues，包含本地插入及远程 stash 准备，未拆分 owned/remote 成本。排除状态/编号 gather、参数/几何准备、面载荷计算及插入、最终 Vec/MatAssembly、约束、压力归一化后的反力修正与 I/O。计时在物理驱动层，不向 kernel 引入 MPI/PETSc 或输出。

统计在每个时间步尝试前重置，覆盖该次 solve 中的全部已完成单元调用，**包含最终物理验收和原始反力重装配**；因此不能与 `callback_seconds` 直接相减。若同次 solve 有被拒绝的试探评价，已完成单元工作仍计入；整个 solve 抛错时不输出该次计数，重试重新计数。输出表示非线性 solve 成功，不代替随后时间提交/checkpoint 的成功状态。

时间是 rank-local，未取最大值或求和；使用 PetscSynchronizedPrintf/Flush 按 rank 输出。关闭时不执行单元级时钟读取、计数更新和报告同步；开启时每单元增加时钟读取，开关扰动已在 [HPC-01E](../research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md) 的小算例上测量，不能外推固定开销或用本诊断直接证明加速。

## 编译期拓扑、布局与积分规则

`include/eonsim/discretization.hpp` 统一维护结构常量：

- `CartesianSpace<Dimension>` 给出向量、二阶/四阶张量尺寸及索引。
- `Simplex<Dimension>` 给出 P1 单纯形节点、面节点、Jacobian 体积因子和解析质量权重。
- `NodalLayout<Element, Components>` 推导单元自由度和矩阵尺寸，提供节点优先的 `dof` 与行优先的 `matrix` 索引。
- `FluidLayout<Element>` 定义速度—压力布局；`CoupledLayout<Element, Elastic>` 定义流体、网格及可选弹性结构的偏移。刚体/弹性 FSI 分别实例化，运行时配置选择入口。

现有内核通过 `Tet4Scalar`、`Tet4Vector`、`Tet4Flow`、`Tet4Ale` 等别名使用这些定义；全局节点索引保留调用者整数宽度。这些模板本身不提供新增物理能力；G1另实现原生Tri3/P1与Quad4/Q1二维标量，具体支持范围见[二维契约](../development/SCALAR_2D.md)。

`include/eonsim/quadrature.hpp` 独立维护积分数值：`GaussLegendre<N>` 提供区间 `[0,1]` 的 1–4 点规则，`SimplexGauss<Tet4Topology,4>` 提供二阶精确的四面体对称四点规则，`TetDuffyGauss<N>` 将每轴 Gauss 点映射到四面体，支持 N=2–4。点、重心坐标和权重全部采用 `inline static constexpr` 数组，不在装配过程中生成。四面体权重之和为 1，积分时乘物理体积。

当前 `FluidQuadrature` 选择对称四点规则，`ErrorQuadrature` 选择每轴四点的 Duffy 规则。改变积分策略应修改这些编译期别名并重新验证。`quadrature_moments` 测试按解析单项式积分检查各规则宣称的精确阶数、权重和与质量矩；既有单元导数和 MPI 算例检查装配行为。

数学系数、坐标轴索引、边界物理标签及外部文件格式类型码保留其原有含义，不作为节点数或自由度尺寸处理。

### 外表面几何（B0）

`build_boundary_facets` 为分区持有的每个外表面建立唯一相邻本地 Tet4、面节点局部编号和对顶点；分区将面交给相邻单元 owner，关联构造不需要通信。只在拓扑改变时重建。`triangle_geometry` 用实际三维坐标计算面积，并由对顶点确定单位外法向，不依赖 Gmsh 三角形的排列方向。固定网格驱动缓存面积/法向；FSI 局部残量使用当前 trial 坐标重新评价，因而几何导数仍进入完整耦合切线。

`BoundaryQuadrature=SimplexGauss<Tri3Topology,3>` 在静态模板中维护三点二阶精确规则，权重和为 1，物理面积在调用处相乘。解析线性面载荷仍可用相同拓扑的质量积分矩。局部几何测试覆盖旋转/缩放、闭面法向和、散度定理及非法邻接；不把局部邻接检查当作分区间完整网格拓扑审计。

### 固定网格的标签流体边界（B1）

`fluid.boundaries` 启用显式标签路径。每个外表面标签都须配置，同一标签上的多条条件使用互不重叠的笛卡尔分量。网格中找不到已配置标签时报错。省略该字段时使用原有的单位立方体通道基准。标签路径支持速度 Dirichlet、给定牵引与法向压力载荷。分量合并规则见 B2。

- `velocity` / `traction` 使用 `value + gradient*(x-origin)`，坐标为物理坐标，`gradient` 为行优先三行矩阵。速度单位 m/s、牵引单位 Pa，梯度相应除以 m。
- `pressure` 的标量 `value` 表示外加压强 Pa，外法向 n 下 `t=-p*n`，装配残量贡献为 `-integral N*t dA`。它不等同于直接指定节点压力，也不包括黏性切向牵引。
- 非稳态每条条件可设置 `ramp_time`，乘 `min(t/ramp_time,1)`；省略或为 0 时立即施加，稳态使用最终值。初始内部场仍为零，初值字段配置尚未实现。
- 瞬态标签压力支持 `pressure_time: {amplitude, period, ramp_time}`。标量 `value` 为均值，振幅单位与均值相同。内层可选启动时间平滑缩放整个正弦加载，与外层线性 `ramp_time` 互斥。自然载荷按积分阶段时刻评价，单位压力面残量允许均值为零。命令行 `-fluid_boundary_history` 对每个接受步输出各标签的面积、外向体积流量和面积平均的离散压力。时间、符号与重启契约见[振荡圆管说明](../development/WOMERSLEY_FLOW.md)。
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

`fsi_element_tangent` 用解析 `dV/dx`、`d grad(N)/dx` 初始化固定宽度 Dual，前向传播同一个 SUPG/PSPG 残量与网格速度；当前压力面积项用一致解析导数加入。参考 Laplace 块缓存并直接填写，接口链式系数由所选时间格式提供，默认 BE。局部状态大小由 Tet4Ale 模板推导，积分规则不包含运行时维护的数据。旧中心差分函数保留用于独立 Jv/轨迹/性能对照。

GAMG 当前只有低 Re 小算例运行证据，不宣称针对高 Re、近不可压结构或网格无关迭代调优完成。实际误差、迭代及 RSS 见 [B5 记录](../development/B5_ACCURACY_AND_PERFORMANCE.md)。

### G0B：语义分组接入

`AlgebraLayout::owned_semantics` 为 owned 存储行提供布局内的实体/域/量身份，`fields` 仍唯一负责物理验收。
`pc_recipe` 的三种树使用独立 `PcBlock`，递归保存根provenance与直接父算子全局编号；不改变root存储、图、残量或停止条件。
索引计划在solve准备阶段生成，Newton内仅更新数值。默认旧PC路径保持不变；配置与证据、空块/选项边界见 [实施记录](../development/FEM_INTEGRATION_VALIDATION.md)。

## G1二维标量依赖子集

MeshImportData先表达来源ID、拓扑、实体及physical groups，再适配到有所有权的MeshPartition。
二维P1/Q1共边节点空间使用独立语义space=2，单元核按实际类型评价映射，Quad4不拆分。
标量Dirichlet/Neumann/Robin及纯Neumann零空间仅服务该模型；不因此宣称完整G2已完成。
分区连接偏移、混合VTU/PVTU/PVD属于当前闭环必需的G4子集。
数学、边界符号、积分及运行时支持范围统一维护于[SCALAR_2D](../development/SCALAR_2D.md)。


### FEM-G2A：直边三角形 P2 字段

P2 几何继续使用 Tri3，ScalarP2Space 独立持有顶点/边中点的 cell-to-DoF、owned/ghost 和完整远程行邻接。DofEntity::edge 追加在现有枚举之后；space=3 区分 P2 与 P1/Q1 的 space=2。离线边 ID 按规范原始端点对排序，与代数行编号分离，不把坐标相同当作实体相同。

预处理写出可选 P2 HDF5 组，单个 rank 在求解中只读取本地文件；既有几何分区格式不承载新增场节点。支持范围和命令以 SCALAR_2D 文档为准；该切片不构成完整 G2。


### 可选的聚合粗空间和自适应数值预条件更新（HPC-05）

`-pc_plan_velocity_solver aggregate` 在约束消元后的联合速度图中构造 rank-local 连接聚合，
以 `-pc_plan_velocity_aggregate_nodes`（默认 16）限制每聚合节点数。按域/空间保留平移常数，
`rigid` 选项为结构补充参考旋转；在聚合局部做两遍正交化并剔除退化模态。第一层使用完整
`P^T A P`，粗层再用 GAMG；不强行赋予缩减 scalar AIJ 三分量块大小。默认 recipe 不变，
该构造的网格扩展表现由实际算例判定。

默认每个成功 Jacobian 仍更新数值 PC。显式 `-nonlinear_adaptive_pc true` 仅用于合资格
默认 Newton/FGMRES、当前精确 Jacobian、未设置手动 lag/reuse/EW 的会话。每次仍重新
组装 J；只允许数值 PC 和其 USER Schur 近似滞后。每行 diagonal/absolute-row-sum 变化均以
该行新旧绝对行和的最大值归一化，避免很小的压力对角项独占变化尺度；这是一种采样指标，
不是完整矩阵差范数。该变化、
最大复用次数、上次 KSP 迭代增长、拒绝试探或时间系数 context 变化触发重建。
默认最大复用 4 次、相对变化门槛 .1、迭代增长系数 1.5；各项可显式配置并报告原因及监测成本。
未提供物理 context 时不跨 solve 复用；配置/options/约束或失败仍销毁整个会话。
一次确由复用 PC 引起的 KSP 迭代耗尽可在同一已接受 Newton 状态强制重建后重试一次，
不重试回调、NaN、breakdown 或 PC 错误，不改变字段初始尺度、容差或时间历史。
重试只使用原求解尚未消耗的 Newton 迭代与 PETSc 计数的函数评价预算；以实际 SNES
设置为准，保留命令行覆盖和无限函数评价设置。重试退出后恢复原始上限，成功保留的
会话不会将减少后的预算带入下一时间步。显式初始/重试起点及最终物理验收组装不属于 SNES 函数计数。

### RCR 端口低秩响应（RCR-PC-01）

显式 `-pc_plan_rcr_ports true` 在现有语义recipe外包一层端口PCSHELL，按boundary-pressure
实体识别端口，bulk保留全部其他自由度。完整约束后Jacobian与验收字段不变；U和V必须
分别从真实矩阵提取，不能对移动出口或只替换约束行的矩阵强加V=-Uᵀ。

端口层缓存Y=HU及S=D-VY，应用z=H r_bulk、q=S⁻¹(r_port-Vz)、x_bulk=z-Yq。
H=A⁻¹时是原J的精确块逆；固定可逆线性H对应将A替换为H⁻¹的块逆。
含残量相关内层求解时为响应近似；外层要求FGMRES。
bulk必须以PREONLY执行一次现有语义PC；前缀按原根KSP前缀、rcr_bulk_、原子树前缀组合。
固定索引/图可跨数值刷新复用，bulk、U/V/D、响应和小矩阵必须同代刷新并整体发布；
失败generation不可应用，成功重建后才清除PC failure。缓存随已有PcSchurUpdates决策，
不因单次J数值状态变化擅自绕过自适应复用，也不进入物理checkpoint。
端口层每apply/每generation各一次合并投影归约，基础PC内部通信另计。
实际支持范围、基础GAMG/BoomerAMG配置和证据见[RCR预条件器](../development/RCR_PORT_PRECONDITIONER.md)。
