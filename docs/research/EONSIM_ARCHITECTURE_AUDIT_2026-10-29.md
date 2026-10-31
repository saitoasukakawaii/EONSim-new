# EONSim 架构与数值实现审查

2026-10-31 阅读提示：本文保留历史审查及复验。后续已有独立流体 COO、G0 语义 PC、G5 高阶时间与 G1 二维标量交付；持久 SNES/PC 按测量暂缓，完整 Newton 缩放未实现。最新能力与证据见 [集成验收](../development/FEM_INTEGRATION_VALIDATION.md)。

审查日期：2026-10-29。初始基准 commit：`e3c8dbd0521e9cf0f4ad0c6102a164aa65765ad8`，另包含未提交修改。审查期间共享工作区继续更新，本文已按新增源码和针对性复验修订，明确标记已解决的早期发现。后续方案见 [下一阶段详细设计](../architecture/EONSIM_NEXT_STAGE_DESIGN.md)，现行约束仍以各 L1/L2 主题文件为准。

审查收尾时上述代码更新已提交为 `9c01f22d310b5314055230c6462e566f336c06d5`；审查的文档改动保持未提交。除明确标记的后续修复外，下列“当前”指这一代码快照，首次失败记录只作为前后对照。后续开发已落实 A2 与 A3 的字段验收，见各项的修复与验证记录。

## 结论与证据范围

EONSim 已形成真实的三维低阶 FEM、多场单体求解和 MPI 局部数据链。适合沿现有代码收敛为可靠的 FSI 求解应用，当前没有足够收益支持整体换框架。最需要投入的是结果判定、状态恢复和适用范围内的精度/规模研究。更新后的 B5 已有数千自由度和 1/2/4 rank 记录，仍不能支持“大规模 HPC 生产就绪”的结论。

后续开发已处理 **A2 标签观测、A3 字段验收、A4 检查点发布、A5 失败分类、A7 分量通量、A8 整体导数阈值**，并完成 A6 的 residual-only 和参考几何缓存。持久求解会话、完整 Newton 变量/方程缩放与更大规模证据仍待推进。早期复现的 Schur 失败和压力归一化反力不一致已经由共享工作区中的新代码处理，本次复验通过，不再作为未解决问题。

本次阅读配置、网格/分区、编号、几何/积分、物理核、SNES/KSP、时间步、checkpoint、输出与相关测试；运行少量 Release 检查和问题复现。没有进行全仓逐行证明、完整 Debug/Release 回归、跨节点扩展或 GPU 测量。上游参考使用官方文档和指定源码，不把上游的能力计入 EONSim。

审查开始时，7 个 tracked 文件已有修改，4 个文件未跟踪：`dual.hpp`、`fluid_residual.hpp`、`schur_solver.hpp`、`schur_solver.cpp`。随后工作区增加了 Schur 粗层范数设置、压力归一化反力修正、验证脚本和 B5 数据。这些均非本次审查写入的代码；本次只写审查/设计及文档导航、状态说明，未修改或提交求解源码。

## 当前能力清单

| 范围 | 源码事实 | 能力边界 |
|---|---|---|
| P0/P1 | Gmsh 2.2 ASCII、Tet4、离线 METIS、各 rank HDF5、owned/ghost、AIJ 预分配 | 全局预处理仍串行；求解不反复收集全局场 |
| 流体 | P1/P1、SUPG/PSPG、Stokes/NS、BE、标签速度/牵引/压力 | 低 Re 基线；四点积分不精确覆盖全部三次 SUPG 被积项 |
| 固体 | 线弹性、可压缩 Neo-Hookean、静载/撤载、参考构形残量与切线 | 不是通用动态载荷应用；无塑性/黏弹历史，无近不可压缩混合格式 |
| FSI | 单轴刚体、弹性/超弹性、共形 ALE、运动学消元、统一 SNES 与提交 | 无六自由度、非匹配、接触、重网格或分离式适配器 |
| B2 | 独立流体/固体区域材料、全局笛卡尔分量约束、压力均值归一化 | 均值方案是临时定点求解后平移，不是 PETSc nullspace 实现；没有通用法向滑移约束 |
| B3 | 两份独立共形网格、节点/面双射、相反法向、联合分区 | 每个 FSI 域当前一个体标签/一组材料；独立编号不等于非匹配界面 |
| B4 | 真实时间、有限次缩步、accepted 历史回滚、checkpoint v2 | 成功后保持缩小步长；没有误差估计、自适应增长或二阶时间格式 |
| B5 工作区实现 | 固定宽度前向 AD 与解析仿射几何导数；Schur/GAMG；空间/时间与小规模记录 | 更新后局部导数及 Schur 1/2/4 rank 对照通过；迭代数仍随网格增长，适用范围限已有低 Re 小例 |

证据入口：[配置](../../include/eonsim/config.hpp)、[局部网格](../../include/eonsim/mesh.hpp)、[区域材料](../../include/eonsim/regions.hpp)、[独立双域](../../src/mesh/fsi_domains.cpp)、[有效编号](../../src/fem/reduced_layout.cpp)、[时间步](../../include/eonsim/time_step.hpp)。

## 发现与处置状态

### A1：早期 Schur 默认组合失败〔已由共享工作区更新解决，本次复验通过〕

位置：[schur_solver.cpp](../../src/algebra/schur_solver.cpp) 第 25–64 行、[nonlinear_system.cpp](../../src/algebra/nonlinear_system.cpp) 第 112–166 行。

初次运行 `cases/fsi/domains/case.yaml` 对应的 48/51 Tet4 双域例时，直接解及重启检查成功，`-schur_pc` 在 1/2 rank 均失败。单 rank 诊断为第一步、Newton 初始残量 `3.773077140891e-01`，线性迭代 0 次即 `DIVERGED_PC_FAILED / SUBPC_ERROR`，继而 SNES reason=-3。失败没有被误报成功。

源码将外层 flow/mesh/structure 做乘法分块，flow 内使用 full Schur factorization、`SELFP` 及两块 GAMG。`SELFP` 使用 `D-C diag(A)^{-1}B`，其适用性取决于对角近似，不能直接解释为物理上鲁棒的压力 Schur。[PETSc 官方说明](https://petsc.org/release/manualpages/PC/PCFieldSplitSetSchurPre/)

后续共享工作区在 GAMG 的 GMRES 粗解中显式设置 `mg_coarse_ksp_norm_type=unpreconditioned`。本次对原失败的相同双域例重新运行，1/2 rank 均成功，与原直接解的完整字段最大差分别为 `6.1429e-13`、`7.3575e-13`；新增 `verify_schur.py` 的独立流体、双域、刚体、超弹性 1/2/4 rank 对照也全部通过。当前不再把该失败视为阻塞项。子 KSP/PC reason 和粗层收敛的诊断仍应保留，`SELFP` 的适用范围仍需随规模研究。

### A2：标签固体的摘要按 x=0/x=1 选取，通用几何得到错误的零结果〔后续已修复并验证〕

位置：[solid.cpp](../../src/physics/solid.cpp) 的求解后汇总；[main.cpp](../../src/main.cpp) 的固体摘要输出。

把既有双材料条形体沿 x 平移 2 m，保留标签、材料、载荷和位移边界。节点位移最大误差仅 `1.5613e-17 m`；物理加载端位移应为 `0.0075 m`，约束端 x 反力应为 `-1 N`。程序却打印 `tip_displacement=0 reaction_x=0` 和 `status=success`。原因是后处理继续寻找 x=1 和 x=0，找不到端面时把端位移置零。

应让观测量指定 boundary tag、分量/方向、平均方式与构形；支座反力按真实受约束 DoF 汇总。节点算术平均与面积平均也应区分。没有对应观测定义时省略指标或明确拒绝，不能给出伪物理零值。FSI 的 `position/velocity` 目前也是界面节点 x 分量算术平均，适用于现有活塞案例，泛化时须一起处理。

后续修复（2026-10-29）：显式标签模式输出每标签的参考面积、三个全局笛卡尔分量的面积平均位移/速度，以及该标签实际位移约束分量的反力。反力由 owned 节点原始残量求和；总支座反力使用已合并约束去重，避免相交标签重复计数。旧单位块摘要仅在未配置标签边界时输出。当前没有新增任意方向探针配置或修改 FSI 界面摘要。

Release 构建及 `regions_verification`、`solid_verification` 均通过。新增 1/2 rank 平移双材料杆保持端面均值 `0.0075 m`、支座 x 反力 `-1 N`，侧面面积均值 `0.004375 m`（节点算术平均为 `0.00425 m`）；旋转、缩放且交线有重复约束的杆验证全局 y 分量、非单位参考面积和去重后的 `-1 N` 总支座反力。原单位块静载/撤载检查继续通过。日志位于 `build/release/Testing/Temporary/LastTest.log`，新增输入与输出位于 `build/release/regions_verification/`。

### A3：多场接受规则缺少分字段尺度〔字段验收已实现；完整 Newton 缩放待推进〕

位置：[nonlinear_system.cpp](../../src/algebra/nonlinear_system.cpp) 的收敛与返回路径，[config.hpp](../../include/eonsim/config.hpp) 的 `SolverConfig`。

初审时只有一套 SNES 总范数容差，成功返回后仅再次检查总残量有限。配置没有各方程尺度，也没有 per-field 收敛条件。动量、连续性、人工网格和约束行的量纲/大小不同，扩大几何尺度、改变材料刚度或网格人工系数时，单一总范数不能证明每块达到预定精度。此问题是当时能力与 [L2 离散契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md) 的缺口，并非初审已观察到所有案例结果错误。

应在最终有效编号上建立方程行分组，提供冻结于一次时间步的变量/残量尺度，并在所有块通过后才接受。边界替换行与原始反力行不可混入同一种物理残量统计。PETSc 正的停止原因也不一律等于残量达标，例如步长停止或显式跳过收敛检查；保留最终应用侧接受检查。[PETSc 停止原因](https://petsc.org/release/manualpages/SNES/SNESConvergedReason/)

后续实现（2026-10-29）：`solver.fields` 提供完整字段配置，物理方程按缩放后的 RMS 验收，Dirichlet 替换行按独立尺度的最大误差验收；原始反力不混入范数。默认回调在字段未达标时继续迭代，最终重新装配检查不受 PETSc convergence-test 覆盖影响。各字段的初始范数在本次求解施加 prescribed 后冻结，重试/重启新调用重新计算；无显式配置时仍按字段验收，使用尺度 1 和外层容差。此增量不改变 J/R/未知量或线搜索的表示，完整对角缩放与 A5 的 domain-error/PC 分类仍待实现。

验证覆盖：1/2 rank 非线性耦合小系统将人工网格行系数取 10⁻⁸、10⁸，仍得到 `u=m=sqrt(2)`；全约束字段的非零反力不影响接受，局部空字段与全约束字段正确处理。`-snes_convergence_test skip -snes_max_it 0` 返回正 reason 后仍被拒绝；10⁻²⁰⁰ 残量高于 10⁻²¹⁰ 阈值的情况也正确拒绝，避免平方下溢伪收敛。双域 FSI 逐块达标，失败重启尝试不提交步数、不改写原检查点文件。新准则下高压缩步例使用 dt=0.00125、32 步到 t=0.04，与同 dt 参考及重启轨迹一致。

极小残量检查还暴露了本机 PETSc 3.23.2 的零范数缓存路径：NORM_2 下溢为零后，`VecSet(0)` 可能跳过清零，导致后续 ADD_VALUES 累加旧值。驱动改为直接覆盖 owned 残量缓冲，测试同时检查每次评价前确已清零；字段 RMS 则通过全局峰值归一化后平方求和，避免范数自身的下溢/上溢。

实际执行：Debug/Release 均构建 `eonsim` 与 `verify_nonlinear_acceptance`；Release 通过 `nonlinear_acceptance`、`nonlinear_acceptance_mpi`、`domains_verification`、`time_retry_verification`、`solid_verification` 共 5 项，Debug 通过前两项及 `domains_verification` 共 3 项。日志归档为 `build/{release,debug}/field_acceptance_validation.log`。没有执行全量回归或新增大规模性能测量。

### A4：checkpoint 覆盖会丢失上一完整版本〔generation 发布已实现并验证〕

位置：[checkpoint.cpp](../../src/io/checkpoint.cpp) 的写入与发布路径。

初审代码写新检查点前删除旧 `manifest`，随后逐 rank 覆盖 `state_rankN.h5`。若途中进程退出或 I/O 失败，新一代不会被当作完整检查点读取，但原先可恢复的一代也已丢失。这不是断电持久性测试结论，而是明确的覆盖顺序所导致的恢复窗口。

采用不可变 generation 目录：写完所有 rank 数据并确认成功后，最后原子替换当前 generation 指针；发布前始终保留旧目录。HDF5 close/flush 错误必须进入成功判定。当前同 rank/同分区签名继续使用，跨 rank 恢复另行设计；普通文件 rename 不自动承诺所有并行文件系统上的断电持久性。

后续实现（2026-10-29）：v3 每次创建独立 `generation_*`，逐 rank 检查 dataset/dataspace/file close 及 flush，集体确认后写 manifest，最后同目录 rename 替换 `current`。创建、写入、发布阶段的失败向全 communicator 传播；manifest 和 rank 文件时钟一致性在读取时检查。读取稳定根指针或指定旧代，不扫描未发布目录。保留所有代与失败遗留目录，尚无自动清理、并发 writer 协调或断电同步协议；旧 v1/v2 格式明确拒绝。

实际验证：Release 通过 `checkpoint_publication`、`checkpoint_publication_mpi`、`domains_verification`、`time_retry_verification`、`restart_block_verification` 共 5 项；Debug 通过前两项及双域验证共 3 项。故障测试让最后一个 rank 在部分数据写出后发生真实 HDF5 dataset 创建失败，并另以目录阻挡 current 临时文件触发发布失败；两者都在所有 rank 返回失败，原指针、旧 rank 文件字节及恢复状态保持不变。覆盖显式旧代读取、重复 step 新代发布、非法路径指针拒绝；五类物理入口的 1/2 rank 重启对照通过。日志为 `build/{release,debug}/checkpoint_validation.log`。

### A5：SNES trial 域失败与时间步失败未充分区分〔已修复并验证〕

位置：[nonlinear_system.cpp](../../src/algebra/nonlinear_system.cpp) 的装配、SNES 回调及最终 reason 分类。

初审时局部 `StepRejected` 已在 communicator 上汇总，但回调统一返回 `PETSC_ERR_LIB`，使线搜索失去通过 domain-error 协议尝试较小 Newton 步的机会。随后所有非正 SNES reason 都变成缩时间步失败，包括本次子预条件故障。重试有次数上限，故不构成无限循环；问题在于恢复策略和诊断分类过粗。

建议区分：输入/通信/I/O 失败、非法 trial、迭代不收敛、线性/PC 配置失败。当前接受几何有效而新 trial 越界时，用所选 SNES 支持的 domain-error/线搜索路径；该路径失败后才缩 dt。不是每种 SNES 都会自动缩 Newton 步，需按实际版本和求解器验证。[PETSc domain-error 接口](https://petsc.org/release/manualpages/SNES/SNESSetFunctionDomainError/)

后续实现：残量/Jacobian 的域失败分别转为 PETSc domain-error，Release 显式启用 Jacobian 域检查。集体传播最严重失败的首个消息，失败前已产生的远程 Vec/Mat 插入完成装配并排空；下一候选点重新清零。最终线性/PC 故障抛普通异常，输出顶层 SNES/KSP/PC reason，非线性未收敛与最终字段验收仍可缩步。2026-10-30 后续增量已增加本 rank 的子层原因树，覆盖 FieldSplit、ASM/BJacobi 和 MG/GAMG 粗层/下平滑器；未建子树明确标记不可读取，不为诊断调用 setup。

`solver_failures` 在 1/2 rank 下以 log 定义域构造真实越界 Newton 步，默认回溯在同一 dt 恢复；最后一个 rank 在拒绝前向 row 0 插入贡献，验证下一评价不受残留 stash 污染。另检查 Jacobian 域拒绝、普通输入错误、迭代耗尽及真实零主元 PC 故障。Release 单元两项及字段验收、Schur、缩步、双域等五项通过；Debug 单元、字段验收各两项与双域共五项通过。实际 FSI 的非法 PC 配置不发生 step_retry。日志为 `build/release/solver_failure_unit.log` 与 `build/{release,debug}/solver_failure_validation.log`。

2026-10-30 层级诊断验收：Debug/Release 均通过 `solver_failures`、`solver_failures_mpi` 与 `schur_verification`。故障例只让最后一个 rank 的局部 LU 出现数值零主元，异常保留 `FACTOR_NUMERIC_ZEROPIVOT`；另检查无 PC 故障的 KSP 迭代耗尽，以及初态已收敛而 PC 尚未 setup 时诊断不改变成功结果。失败退出前按 rank 共同刷出诊断，避免 MPI_Abort 截断远程原因。四类 Schur 算例在 1/2/4 rank 检查压力子块/粗层前缀及物理解；补充双域 ASM 的 2 rank 对照，最大字段差 7.574e-13。日志 `build/{release,debug}/solver_tree_{schur,failure}_validation.log` 和 `build/release/schur_verification/domains_block_tree2.log`。此增量没有新增真实块残量、PC 时间或完整任意 PC 遍历。

同日后续增量：新增 `-linear_report`，每次顶层 KSP 收敛后重新计算 `A*x-b` 并按物理字段测量，约束单列；对角缩放或未收敛明确标记不可用。新增阶段计时，区分显式 Schur 配置、顶层 KSP 和额外诊断；计时嵌套，尚不能独立归因 PC setup。Debug/Release 的 `nonlinear_acceptance` 和 `solver_failures` 均通过 1/2 rank；专门用 preonly/Jacobi 的已知非零缺陷验证首个速度/网格字段 RMS 均为 1.5、约束为零，并检查尺度变化时诊断不污染验收基线。四类 Schur 的 1/2/4 rank 对照增加线性真实残量、字段覆盖和计时有效性断言，日志保存在 `build/{release,debug}/schur_verification/*_schur*.log`。Release 旋转通道额外启用 PETSc 对角缩放，成功求解且正确报告诊断不可用，日志 `build/release/linear_scaled_probe.log`。

阶段采样：`generate_domains(...,6)` 生成 2299 DoF、144177 非零元的双域例；单机 1/2/4 rank 各运行两次首个时间步，采用 Schur 和 `-solver_report`，线程数固定为 1。solve 时间范围分别为 0.135–0.156 / 0.151–0.159 / 0.125–0.134 s，顶层线性迭代数分别为 56/59/56；装配和线性阶段均占明显比例。物理解跨 rank 最大差约 1.31e-12，固体最大差约 8.24e-14。此样本未证明稳定强扩展，更不代表多节点能力；需要更细 PC setup/迭代计时才能选择优化对象。采样使用与构建一致的 `/usr/bin/mpiexec`；PATH 中另一 launcher 会被分区元数据校验拒绝。原始日志、计时及字段差保存在 `build/release/linear_stage_probe/`。

### A6：热路径仍有可直接消除的重复工作〔局部计算与代数存储已复用，SNES/PC 复用待做〕

位置：[nonlinear_system.cpp](../../src/algebra/nonlinear_system.cpp) 第 15–25、84–106 行，[fluid.cpp](../../src/physics/fluid.cpp) 第 111 行，[solid.cpp](../../src/physics/solid.cpp) 第 79 行，[fsi_element.cpp](../../src/physics/fsi_element.cpp) 第 21 行。

初审时每次 `solve_nonlinear` 都创建 Vec/Mat/SNES，物理驱动每个时间步调用一次。每次回调复制 owned+ghost 全部本地值；独立流体即使只求残量仍使用默认 `compute_tangent=true`；固体入口也总算切线；FSI 每次局部评价重算参考 Laplace 矩阵。它们不是全局场收集，也不是每次 Newton 重分区，但会妨碍预条件层级和存储复用。

后续增量已让固定流体/ALE 驱动按矩阵请求选择 residual-only，线弹性/Neo-Hookean 及 FSI 固体分支跳过无需的材料和单元切线，能量观测也不计算切线。`FsiElementData` 一次构造不可变参考坐标、几何和 Laplace 矩阵；当前 trial 几何及其导数仍逐次更新。参考尺度 h 复用缓存体积。

局部检查覆盖稳态/瞬态、线弹性/Neo-Hookean、流体对流开关：有/无切线的残量与能量完全一致，中心差分用 residual-only 评价后仍通过原 Jv 阈值，反转形变仍拒绝。Release 四个局部单元检查加独立流体、固体、ALE、双域 FSI 共八项通过；Debug 四个单元、双域与标签流体共六项通过，日志 `build/{release,debug}/residual_only_validation.log`。这些局部计算改动未单独量化加速或内存收益。

2026-10-30 增量：具体 `NonlinearSystem` 让三个 ghost Vec、AIJ 矩阵和本地 trial 缓冲在四类物理驱动的时间循环外存活；每次 solve 重置初态、验收基准和矩阵数值。1/2 rank 检查确认多次调用保持矩阵对象身份和 trial 缓冲地址，并覆盖系数变化、非对角贡献清除、约束释放及域拒绝后的恢复。Release 八项检查通过，包含字段验收、失败分类、Schur 1/2/4 rank、真实缩步、五类物理入口重启和 ALE；Debug 字段验收、失败分类各两项及双域验证共五项通过。日志 `build/{release,debug}/workspace_validation.log`。SNES/KSP/PC、因子与 AMG 层级仍逐次创建，COO 和跨步预条件复用未实现。

同机 Release 前后比较：`cases/fluid/transient.yaml`（10 步）与 `cases/fsi/domains/case.yaml`（5 步），默认整体直接解，1/2 rank，OMP/OpenBLAS/MKL 各 1 线程，每配置交替运行旧/新二进制各三次。所有输出字段差为 0，逐步 Newton/KSP 迭代数相同。端到端中位数包含 MPI 启动和输出；小样本没有证实稳定加速，不用来声明规模收益。完整样本及日志在 `build/release/workspace_benchmark/results.json` 及同目录。

| 算例 / rank | 改动前端到端 / s | 改动后端到端 / s | 改动前 solve 总和 / s | 改动后 solve 总和 / s |
|---|---:|---:|---:|---:|
| 瞬态流体 / 1 | 0.7447 | 0.7902 | 0.2762 | 0.3119 |
| 瞬态流体 / 2 | 0.8361 | 0.8410 | 0.3571 | 0.3440 |
| 双域 FSI / 1 | 0.6377 | 0.6349 | 0.1822 | 0.1723 |
| 双域 FSI / 2 | 0.7261 | 0.7171 | 0.2536 | 0.2364 |

### A7：边界与压力语义存在泛化风险〔中，静态确认〕

- [config.hpp](../../include/eonsim/config.hpp) 中固体复用 `FluidBoundary`，`velocity` 枚举实际表示位移；解析器甚至同时接受两种名称。共享仿射函数和分量掩码合理，物理种类应有独立类型。
- [solid.cpp](../../src/physics/solid.cpp) 在参考几何上一次准备 `pressure` 载荷，Newton 中不更新面积/法向。因此它相当于冻结参考面的外力，不是有限变形随动压力；新增真正压力边界时要加入 Nanson 映射及载荷切线。
- 初审发现压力均值平移未同步 `raw_residual`。当前 [fluid.cpp](../../src/physics/fluid.cpp) 已装配 `mean * integral grad(N)` 的反力修正并同步 ghost；更新后的 `verify_regions.py` 以非恒定压力流对照指定规范点，1/2 rank 通过。此项已解决。
- 初审 [fluid_boundary.cpp](../../src/physics/fluid_boundary.cpp) 净通量预检查读取每个条件的完整向量。后续以八顶点立方体复现：只改一个未选分量从 0 到 9，使实际完全相同的均匀速度场被误判失败。现与约束装配共用节点分量合并，逐分量按自己的 ramp 积分。新增稳态/不同 ramp、1/2 rank 的占位值不变性，以及由交汇标签供给的真实发散速度拒绝。Release 标签流体和区域材料两项通过，日志 `build/release/component_flux_validation.log`。物理边界类型分离和有限变形随动压力仍未实现。

### A8：导数、离散精度和物理验证的证据不能互相替代〔中〕

在途 AD 对同一流体残量求导，仿射几何种子和当前压力面积项均进入切线；本次局部 Jv 检查通过。这证明当前离散表达的导数一致性，不证明稳定化参数、积分阶数、边界条件或 BE 时间误差足够准确。

独立流体与 FSI 对 tau 中速度模量的构造不同：前者使用单元平均速度的模，后者使用节点速度平方平均；两者均为冻结策略。此差异应显式说明并针对目标问题决定是否统一，不应在优化时偷偷改公式。现有 advective ALE 的常量保持也不等于守恒 ALE 的离散几何守恒证明。

初审 `verify_domains.py` 调用了 `-snes_test_jacobian`，却未解析差异值并断言阈值；成功退出只表明诊断调用成功。后续已对 1/2 rank 各至少五次完整装配 Jacobian 诊断解析 `||J-Jfd||_F/||J||_F`，要求有限且小于 1e-6。Release 实测最大分别为 4.51104e-10 / 4.49145e-10，日志 `build/release/domains_verification/jacobian{1,2}.log`。这是整体矩阵 Frobenius 比较，和局部方向 Jv 检查不同；Schur 的 AD/FD 最终解对照另行保留。B4 的缩步与直接小步轨迹相符是回滚证据；[B5 记录](../development/B5_ACCURACY_AND_PERFORMANCE.md) 的五组固定空间网格时间步是时间误差证据，二者分别描述。

新增材料 patch：[两层 Couette](../../cases/fluid/layered_channel.yaml) 在 y=0.5 处改变黏度，非零分段速度梯度对应连续剪应力。Release `regions_verification` 的黏度 1/4、4/1 两种顺序均通过 1/2 rank：节点速度/压力最大误差 1.73195e-14，界面剪应力 1.6 Pa，通量分别 0.65/0.35 m³/s，壁面反力与散度达标。默认 YAML 也已独立运行。日志 `build/release/layered_regions_validation.log`；这补上黏度跳跃参与实际解的证据，没有宣称一般界面流动精度或高 Re 能力。

### A9：64 位身份与长期扩展边界需要保留〔后续，非当前规模故障〕

[reduced_layout.cpp](../../src/fem/reduced_layout.cpp) 第 69–92 行把有效整数编号经 double Vec 交换；大于 2^53 的编号无法精确表示。当前规模远未触及，但接口不应承诺任意 64 位 ID；后续用 `MPIU_INT`/整数 `PetscSF` 交换编号。

[fsi_domains.cpp](../../src/mesh/fsi_domains.cpp) 第 66–78 行按合并顺序重编原始 ID，同分区恢复没有问题；外部映射、重分区恢复或网格追踪需要保留 `(domain_id, source_id)`。这些问题应在对应规模/功能出现时处理，不能借此要求现在引入完整 DMPlex 或 AMR。

### A10：状态说明落后于实现〔中，文档确认〕

审查开始时 AGENTS/README 仍把下一步写成 B2、FSI 限镜像逻辑网格；ROADMAP 表格已到 B4，但后续段落仍指向 B2；FSI 契约开头又写“尚未实现”。随后共享工作区更新了 B0–B5 的事实说明与记录；本次补正 FSI 契约开头并添加审查/设计导航。旧状态不再用作最终能力结论，历史性能表仍保留其测量范围。

## 本次执行的验证

环境：现有 Release、PETSc 3.23.2 优化构建、匹配的 `/usr/bin/mpiexec`；运行时 OMP/OpenBLAS/MKL 线程均设为 1。上游网页当前 release 标签可能对应更新版本，不能替代本地依赖版本。

| 检查 | 实际结果 |
|---|---|
| 构建 `eonsim verify_fsi_element verify_fluid_element` | 成功；Ninja 报告无须重建 |
| `verify_fsi_element` | 首次流体/几何方向误差 `3.27808e-11 / 2.33667e-10`；新增非零历史的版本复验为 `3.76647e-11 / 1.96443e-10` |
| `verify_fluid_element` | 四组对流/时间组合通过；最大 Jv 相对误差 `4.59837e-11` |
| `verify_regions.py` | 1/2 rank 双材料固体、分量流体及缺失区域拒绝通过；更新后另通过非恒定压力的归一化反力对照；最大已报解析误差 `4.8883e-15` |
| `verify_domains.py` | 48/51 单元、9 个界面节点；1/2 rank、界面/动量、重启、错位拒绝通过；整体 Jv 阈值缺口见 A8 |
| `verify_time_retry.py` | 1/2 rank 均从 dt=.04 缩至 .0025，16 步到 .04；回滚参考、重启和耗尽失败检查通过 |
| 平移双材料条形体 | 初审解正确但摘要错误；后续修复后 1/2 rank 的面积均值与反力通过，见 A2 |
| 原独立双域 `-schur_pc` | 早期 1/2 rank 失败；更新后相同输入复验通过，完整字段差至多 `7.3575e-13`，见 A1 |
| 更新后的 `verify_schur.py` | 四类问题在 1/2/4 rank 与直接解一致，已报最大字段差 `2.3508e-12`；双域 AD/FD 对照通过 |

生成文件位于 `build/release/architecture_review/`（忽略的本地验证目录）；`run_review.py` 保存首次复现步骤，`schur_diagnostic.log` 是早期失败日志，`updated_*.log` 保存更新后的复验。未由本次审查重跑完整 CTest 或性能/收敛研究。新 B5 文档中的精度/性能数字属于共享工作区提供的测量记录，本次阅读后用于限定能力边界，不冒充本次测量。

可独立重跑正向检查：

```bash
cmake --build build/release --target eonsim verify_fsi_element verify_fluid_element --parallel 4
./build/release/verify_fsi_element
./build/release/verify_fluid_element
python3 tests/verify_regions.py --executable build/release/eonsim --mpiexec /usr/bin/mpiexec --work build/release/review_regions
python3 tests/verify_domains.py --executable build/release/eonsim --mpiexec /usr/bin/mpiexec --work build/release/review_domains
python3 tests/verify_time_retry.py --executable build/release/eonsim --mpiexec /usr/bin/mpiexec --work build/release/review_retry
```

Schur 原失败用例的最短运行命令（当前更新版本已通过）：

```bash
./build/release/eonsim -case cases/fsi/domains/case.yaml -schur_pc -snes_monitor -ksp_converged_reason -output build/release/review_schur.vtu
```

更新后的 `verify_regions.py` 直接生成 `translated_bar.yaml/translated_bar.msh` 和 `rotated_support.yaml/rotated_support.msh`，检查修复后的标签摘要；理论值和原错误输出见 A2。`solid.yaml` 仍保留缺少第二种材料的负向输入，不用它作为正向重跑入口。

## 交付取舍

审查阶段交付详细设计和文档入口修订；后续开发已完成 **A2 标签观测、A3 字段验收、A4 generation 发布、A5 失败分类、A7 分量通量与 A8 整体导数阈值**，并实现 A6 的 residual-only/固定参考缓存，均沿具体算例验证。继续依照 [具体实施顺序](../architecture/EONSIM_NEXT_STAGE_DESIGN.md#实施顺序与验收) 推进持久求解会话、按需 Newton 缩放及精度/规模证据。已解决项不重复安排修复。
