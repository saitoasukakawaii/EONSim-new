# L2：分布式、内存与执行后端

状态：采用。MPI/CPU 为首版路径；libCEED、Kokkos、GPU 只在满足触发条件后接入。

2026-10-30 扩展设计见 [通用 FEM 规划](GENERAL_FEM_ARCHITECTURE_PLAN.md) §7–8、§10–11：rank 内排列与任意字段 IS 分开；通用图考虑面项/约束支撑；VTU 继续 rank 分片并在完整写入后发布索引；runtime 批次选择 native 模板核。当前 FSI 已有下述可选 OpenMP 批次；高阶和通用设备路径仍按具体需求与测量引入。

## HPC 的必做项与延后项

### 首版必须正确的部分

- **通信语义明确：** 状态由 owner 向 ghost 同步；本地贡献向 row owner 累加。一个物理贡献只计算一次，避免 ghost 单元重复积分。PETSc Mat/Vec 装配已负责的远程累加，不再额外手工累计一遍。[PETSc ghost 更新](https://petsc.org/release/manualpages/Vec/VecGhostUpdateBegin/)
- **求解中不复制全量数据：** 不在每步/每次 Krylov 操作中 gather 全局场或矩阵；小规模调试导出、离线预处理不受此限制。标量范数和通量的规约属于正常集体通信。
- **稀疏图有预分配：** 每个 rank 区分本地列与远程列；边界/耦合贡献也进入图。独立流体与 FSI 已有显式固定 COO Jacobian，FSI 另默认使用残量 COO；PETSc 负责远程坐标项的最终累加。[PETSc COO 预分配](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)
- **缓存有明确作用域：** 参考形函数/积分点可长期缓存；物理梯度、Jacobian、法向与面积在 ALE 移动后更新。图、几何与数值缓存不要混在一个“全部有效”标记中。
- **并行失败可结束：** 一般错误在共同阶段汇总；不可恢复的 PETSc/MPI 错误采用作业级退出。避免一个 rank 抛异常返回、其余 rank 永久等待 collective。
- **从第一阶段记录低成本计时：** prepare、assembly、linear solve、nonlinear step、communication、I/O，以及 owned/ghost/nnz、迭代数。诊断计时可以重叠，汇总时不把重叠阶段直接相加。

### 性能优化的固定顺序

**算法/预条件 → 分区与内存 → 图及缓存复用 → 通信与计算重叠 → OpenMP/SIMD → GPU 或 matrix-free。**

这是评估优先级，不要求为了进入下一项先实现缺少收益证据的后端。默认每 rank 单线程，
避免 MPI ranks × OpenMP × BLAS 线程超卖。线程只算局部贡献并写私有或明确不重叠的缓冲，
PETSc 插入在受控阶段完成；不能假定共享 Mat 可并发写。MPI 调用集中在主线程，使用满足
该模型的 thread level。

Matrix-free 适合在高阶、内存或算子应用成本成为问题时引入，且必须同时有可用预条件；不能只实现 `Jv` 就宣称求解器更快。GPU 先迁移已测得的热点和必要数据驻留，再决定是否采用 Kokkos 等执行层。

扩展性在 Release 下测量。固定问题测强扩展，固定每 rank 工作量测弱扩展；同时报告求解器迭代数、最慢 rank 时间和每 rank 峰值内存。强扩展效率采用 `E(p)=(T(p₀)/T(p))·(p₀/p)`，明确基准 rank 数 `p₀`。串行分区时间单独列出，并另报端到端耗时，避免掩盖准备阶段瓶颈。

### FSI 的固定图与贡献缓冲

默认 AIJ 从物理依赖掩码和独立 test/trial 映射生成固定图，PREALLOCATOR 填入的最终矩阵
由 `ReducedLayout` 移交 `NonlinearSystem`，不复制一份相同图。约束、接口别名、刚体和
RCR 的支撑必须同时进入图；当前数值为零不构成删图理由。具体掩码及插入契约见
[离散算子](L2_DISCRETIZATION_AND_OPERATORS.md#fsi-固定图贡献计划与数值更新)。

显式 `-fsi_coo` 将本 rank 的 `K` 条贡献一次合并为 `U` 个不同 `(row,column)` 坐标，
长期保存 32 位贡献到值槽的 scatter 索引及局部 tangent 槽；超过索引容量共同拒绝。
准备阶段利用 owned 连续、ghost 后缀有序的 `local_to_global` 把贡献按本地行分桶，
按全局行顺序遍历桶并只排序桶内列。输出唯一坐标序和原贡献到值槽的映射与全量坐标
排序相同；缺失测试行共同报错。K 项临时行数组在分桶后释放，行 offsets/order 等
准备期暂存不跨 solve 保留；不为降低初始化成本改变原始数值加和顺序。
数值缓冲为 `U + owned` 个标量，额外 owned 项保留对角位置。主线程每次按固定贡献顺序
累加重复值，跨 rank 的加和仍由 PETSc 完成。`K`、各 rank 的 `U` 之和、最终矩阵唯一
`nnz` 是不同计数；报告值缓冲时也要区分 rank 总量与最大 rank。
默认残量 COO 保留自己的贡献次序及缓冲，不从矩阵去重次序推导；
`-fsi_residual_coo false` 只切换残量插入方式。

全局 BAIJ 不是当前 FSI 存储后端。约束消元后，每个节点的流体、网格和结构分量数不同，
还有接口别名及单自由度 body/port，owned 范围没有统一的方块大小。直接采用固定块存储
需额外 padding 或编号重构；不能从未约束速度有三个分量推断整个缩减系统可用 `bs=3`。
这是布局适配边界，不是 BAIJ 更慢的性能结论；固定方块要求见
[PETSc BAIJ 定义](https://petsc.org/release/manualpages/Mat/MatCreateBAIJ/)。

### FSI 的有界 OpenMP 批次

CMake 的 `EONSIM_ENABLE_OPENMP` 在工具链可用时接入 OpenMP；运行默认仍为
`-fsi_threads 1`。显式 `-fsi_threads N` 只用于单体 FSI，当前接受 `1..256`；`N>1`
要求 OpenMP 构建和至少 `MPI_THREAD_FUNNELED`。不支持时明确报错，不静默改成串行。

每批最多 64 个单元，每个 worker 复用自己的 residual/tangent 工作区，输入几何、历史、
时间系数和 expanded trial 场在该批次内只读。worker 不调用 PETSc、MPI、日志事件或 I/O，
不写物理历史；残量 COO 按单元 offset 写不重叠区间，切线写不重叠的批次缓冲。
每次装配只创建一个 OpenMP 团队，各批次在共同 barrier 处完成 worker 写入后，由原始
主线程按单元顺序完成 compact COO scatter-add 或普通 Mat/Vec 插入；下一批在插入完成后开始。
不同单元映射到相同代数坐标不授权 worker 并发累加同一个值槽，也不需要浮点 atomics。
批次存储与本地单元总数无关，不缓存所有单元的完整 dense Jacobian。

worker 异常先在受保护区保存，主线程插入异常也在团队内捕获；线程经过共同 barrier 后
一致结束，所有线程 join 后才在主线程重抛并进入既有 rank 间错误同步。
失败的部分 COO 缓冲不发布，普通插入已存在的 stash 必须排空；后续重试重新清零
缓冲并更新 trial/time 系数。接口力重放在批次结束后使用原始物理残量，与线程数无关。
请求线程数不等于实际同时工作的线程数，`FSIElementBatch` 计时包含批次调度和插入，
不能与内部 `FSIInsert` 直接相加。实现本身不构成线程加速或多节点扩展性的证据。

## Owner、view 和执行空间

### 离线分区与输出的数据路径

`prepare_partitions` 仍是单 rank 离线 METIS；默认空成本表保留原输入、seed、
分配与 fingerprint。每个 cell/face 按原输入顺序只归入一个 owner 桶，节点
代数编号由 owner 计数/前缀和形成，保留 rank-major/input-node-major 次序。
局部编号仍是 owned 在前、ghost 在后。单次全网格 fingerprint 不在每 rank 重算。

显式 `-partition_cell_weights tag:cost,...` 只适用于 `-prepare`，未指定 tag 的
成本为 1；不存在的 tag、非正或超范围成本/总量在写文件之前拒绝。它不是材料
参数，也不从物理域名称推测成本。非空表采用独立 fingerprint domain 并纳入
实际 cell owner 序列，避免与不同分配的分片/checkpoint 混用；空表身份保持兼容。
`-partition_report` 才收集 METIS、layout、write 计时及各 rank/tag 负载。
prepare 总计不含调用前 mesh import，P2 空间构建计入 layout 而保存计入 write。

VTU 默认保留 ASCII；边界 piece 默认只保存其单元引用的节点，按原 local 顺序
重新编号 connectivity，并映射所有点字段和稳定整数 ID。可用
`-vtu_compact_boundary false` 选择完整本地点集，`-vtu_boundary false` 关闭
边界 companion 与索引，`-vtu_format binary` 选择 little-endian raw appended
数据、UInt64 长度头与流式有界暂存。输出配置在主线程、首次输出前设置一次；
无 MPI gather、无 PETSc 依赖、无整场编码副本。PVTU 仍只在所有 piece 写完后发布。
格式详见 [VTK XML](https://docs.vtk.org/en/latest/vtk_file_formats/vtkxml_file_format.html)。

### Owner 与求解器生命周期

首版 owner 可用 `std::vector`/RAII PETSc wrapper；C++17 的 view 用已有轻量类型或指针＋长度即可，不因 `std::span` 尚不可用就自建大型容器库。view 不负责释放且不得超过 owner 生命周期。accepted/trial 必须是独立可写存储，或有明确且正确的交换协议；浅拷贝不是状态快照。

`NonlinearSystem` 的成功 SNES/KSP/PC 会话可在配置、完整 PETSc options 和 owned 约束行
列表不变时复用；当前初值、约束值、时间系数和矩阵数值仍逐次更新。会话拥有字段/归约
工作区及 Schur 数值更新对象，SNES 在它所引用的 USER 矩阵之前销毁，回调只在本次 solve
绑定当前上下文。异常退出使会话失效，下次重建；固定图与编号的生命周期独立于会话。
`-nonlinear_reuse false` 保留每次新建对照，非默认 SNES/lagged-PC、`-snes_ksp_ew true`
和 `-verify_operator_permutation true` 路径也不跨调用复用。关闭复用或不符合资格的
会话在成功返回时也立即释放；异常退出同样不保留会话。
具体适用条件与数值刷新见[求解器会话契约](L2_DISCRETIZATION_AND_OPERATORS.md#非线性求解器会话与每次验收)。

引入 Kokkos 后，分别说明 execution space、memory space 和 layout。`View` 复制通常仍引用同一存储；独立历史需要独立分配并复制内容，或经证明安全的缓冲交换。不要假定 device view 可由任意 CPU 代码解引用。

主机到设备数据转换、布局转换和后端句柄借用集中在一个 adapter 边界；一次 timestep/solver phase 内保持数据驻留。核函数不自行决定数据上传和下载。首版仍以 CPU 存储为准，不预建空 GPU mirror。

## 通信与异步工作的完成责任

组件接收所属 communicator，应用入口才决定使用 MPI_COMM_WORLD；首版 communicator 可以相同，无须先实现动态拆分。非阻塞通信在完成前不得覆写/释放发送缓冲，也不得读取尚未就绪的接收缓冲。

当前非线性驱动仍先完成 ghost 更新，再调用完整装配回调；没有 interior/boundary
双阶段 callback，也未实现 MPI 通信与单元计算的重叠。若后续引入，必须先识别只依赖
owned trial 值的单元，保证 ghost 完成前不读远程值，并在所有 rank 上共同结束已发起的
通信后再传播失败。`ghost_seconds` 包含本地 Vec 取值，`assembly_finalize_seconds`
包含本地整理和 COO 归并；二者均不能直接当作可隐藏的网络等待。逐项取最大 rank 的
`callback_seconds` 和 `failure_sync_seconds` 可能来自不同 rank，不能相加推断通信占比。
是否值得改变 callback 契约应由实际分区、通信等待和可重叠 owned 工作量的测量决定。

普通 Mat/Vec 双插入路径的最终装配按共同的 `VecBegin → MatBegin → VecEnd → MatEnd`
次序排空两个独立 stash，允许已经发起的两类装配通信同时推进；被拒绝试探点使用相同
次序。该有限范围的调整不拆分物理回调，也不等于 ghost 与 kernel 计算重叠。
COO 路径继续使用 PETSc 的集体数值更新，不额外实现另一套通信协议。

设备数据交给 MPI/PETSc 或 CPU 消费时，由边界保证先前写入已完成，并确认使用的库/配置支持该 memory space。GPU-aware MPI 支持和执行 stream 依赖是具体部署条件，不能从“使用了 Kokkos”推断。尚未支持时采用显式 host staging，记录传输代价即可。

只在必要的数据依赖、跨库边界和测量点同步，不在每个 kernel 后机械加 fence。测量异步设备工作时，计时区间要覆盖实际完成；整段求解性能同时包含通信、数据移动与预条件。普通 CPU 首版不增加这些设备设施。

## 缓存失效与后端引入条件

| 变化 | 失效/更新的内容 |
|---|---|
| 拓扑、分区、DoF 或约束结构变更 | 对应编号、通信计划、稀疏图、相关算子 setup |
| ALE 坐标变化 | 物理梯度、体积/面积/法向及其 qdata；拓扑不变时通常不重建图 |
| 材料状态、场值或步长变化 | 依赖这些量的系数、时间权重、局部残量/切线；预条件按策略更新 |
| 求解器配置、PETSc options 或约束行集合变化 | 同一 NonlinearSystem 内重建 SNES/KSP/PC 会话；不改变既有图的有效性要求 |

最初用明确的准备/更新时间点即可；缓存增多后再加简单 epoch 标记。不要引入自动依赖图框架，亦不要只用一个模糊的 valid 布尔值覆盖所有数据。

| 扩展 | 开始实现前的具体证据 |
|---|---|
| libCEED | 已有目标单元/算子受支持，局部算子成本或存储成为问题，有预条件路线 |
| Kokkos | 自有 kernel 需要跨 CPU/GPU，目标编译器满足所选版本要求，可规划驻留和数据布局 |
| matrix-free | 矩阵存储/应用成本有实测压力，Jv 与预条件一起设计 |
| 子 communicator/多速率 | 实际子模型的负载或时间尺度表明需要独立调度 |

优先选择一种局部执行路径。若采用 MFEM/libCEED 已管理的 backend，不在外层再平铺一份相同设备缓冲与执行循环。首版低阶 Tet4 不因“高阶库通常更快”而自动获益，应以同一完整算例的总耗时判断。

依据：[libCEED、MFEM、LifeV、Kokkos](../research/UPSTREAM_ARCHITECTURE_REVIEW.md)。

