# L2：分布式、内存与执行后端

状态：采用。MPI/CPU 为首版路径；libCEED、Kokkos、GPU 只在满足触发条件后接入。

2026-10-30 扩展设计见 [通用 FEM 规划](GENERAL_FEM_ARCHITECTURE_PLAN.md) §7–8、§10–11：rank 内排列与任意字段 IS 分开；通用图考虑面项/约束支撑；VTU 继续 rank 分片并在完整写入后发布索引；runtime 批次选择 native 模板核。高阶/线程/GPU 路径仍待需求与测量触发，本轮没有性能实验。

## HPC 的必做项与延后项

### 首版必须正确的部分

- **通信语义明确：** 状态由 owner 向 ghost 同步；本地贡献向 row owner 累加。一个物理贡献只计算一次，避免 ghost 单元重复积分。PETSc Mat/Vec 装配已负责的远程累加，不再额外手工累计一遍。[PETSc ghost 更新](https://petsc.org/release/manualpages/Vec/VecGhostUpdateBegin/)
- **求解中不复制全量数据：** 不在每步/每次 Krylov 操作中 gather 全局场或矩阵；小规模调试导出、离线预处理不受此限制。标量范数和通量的规约属于正常集体通信。
- **稀疏图有预分配：** 每个 rank 区分本地列与远程列；边界/耦合贡献也进入图。缓存 COO 可作为下一步优化，PETSc 支持重复及远程坐标项。[PETSc COO 预分配](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)
- **缓存有明确作用域：** 参考形函数/积分点可长期缓存；物理梯度、Jacobian、法向与面积在 ALE 移动后更新。图、几何与数值缓存不要混在一个“全部有效”标记中。
- **并行失败可结束：** 一般错误在共同阶段汇总；不可恢复的 PETSc/MPI 错误采用作业级退出。避免一个 rank 抛异常返回、其余 rank 永久等待 collective。
- **从第一阶段记录低成本计时：** prepare、assembly、linear solve、nonlinear step、communication、I/O，以及 owned/ghost/nnz、迭代数。诊断计时可以重叠，汇总时不把重叠阶段直接相加。

### 性能优化的固定顺序

**算法/预条件 → 分区与内存 → 图及缓存复用 → 通信与计算重叠 → OpenMP/SIMD → GPU 或 matrix-free。**

默认单 rank 单线程，避免 MPI ranks × OpenMP × BLAS 线程超卖。引入 OpenMP 时，线程只算局部贡献并写线程私有缓冲，PETSc 插入在受控阶段完成；不要直接假定共享 Mat 可并发写。MPI 调用集中在主线程，使用满足该模型的 thread level。

Matrix-free 适合在高阶、内存或算子应用成本成为问题时引入，且必须同时有可用预条件；不能只实现 `Jv` 就宣称求解器更快。GPU 先迁移已测得的热点和必要数据驻留，再决定是否采用 Kokkos 等执行层。

扩展性在 Release 下测量。固定问题测强扩展，固定每 rank 工作量测弱扩展；同时报告求解器迭代数、最慢 rank 时间和每 rank 峰值内存。强扩展效率采用 `E(p)=(T(p₀)/T(p))·(p₀/p)`，明确基准 rank 数 `p₀`。串行分区时间单独列出，并另报端到端耗时，避免掩盖准备阶段瓶颈。

## Owner、view 和执行空间

首版 owner 可用 `std::vector`/RAII PETSc wrapper；C++17 的 view 用已有轻量类型或指针＋长度即可，不因 `std::span` 尚不可用就自建大型容器库。view 不负责释放且不得超过 owner 生命周期。accepted/trial 必须是独立可写存储，或有明确且正确的交换协议；浅拷贝不是状态快照。

引入 Kokkos 后，分别说明 execution space、memory space 和 layout。`View` 复制通常仍引用同一存储；独立历史需要独立分配并复制内容，或经证明安全的缓冲交换。不要假定 device view 可由任意 CPU 代码解引用。

主机到设备数据转换、布局转换和后端句柄借用集中在一个 adapter 边界；一次 timestep/solver phase 内保持数据驻留。核函数不自行决定数据上传和下载。首版仍以 CPU 存储为准，不预建空 GPU mirror。

## 通信与异步工作的完成责任

组件接收所属 communicator，应用入口才决定使用 MPI_COMM_WORLD；首版 communicator 可以相同，无须先实现动态拆分。非阻塞通信在完成前不得覆写/释放发送缓冲，也不得读取尚未就绪的接收缓冲。

设备数据交给 MPI/PETSc 或 CPU 消费时，由边界保证先前写入已完成，并确认使用的库/配置支持该 memory space。GPU-aware MPI 支持和执行 stream 依赖是具体部署条件，不能从“使用了 Kokkos”推断。尚未支持时采用显式 host staging，记录传输代价即可。

只在必要的数据依赖、跨库边界和测量点同步，不在每个 kernel 后机械加 fence。测量异步设备工作时，计时区间要覆盖实际完成；整段求解性能同时包含通信、数据移动与预条件。普通 CPU 首版不增加这些设备设施。

## 缓存失效与后端引入条件

| 变化 | 失效/更新的内容 |
|---|---|
| 拓扑、分区、DoF 或约束结构变更 | 对应编号、通信计划、稀疏图、相关算子 setup |
| ALE 坐标变化 | 物理梯度、体积/面积/法向及其 qdata；拓扑不变时通常不重建图 |
| 材料状态、场值或步长变化 | 依赖这些量的系数、时间权重、局部残量/切线；预条件按策略更新 |

最初用明确的准备/更新时间点即可；缓存增多后再加简单 epoch 标记。不要引入自动依赖图框架，亦不要只用一个模糊的 valid 布尔值覆盖所有数据。

| 扩展 | 开始实现前的具体证据 |
|---|---|
| libCEED | 已有目标单元/算子受支持，局部算子成本或存储成为问题，有预条件路线 |
| Kokkos | 自有 kernel 需要跨 CPU/GPU，目标编译器满足所选版本要求，可规划驻留和数据布局 |
| matrix-free | 矩阵存储/应用成本有实测压力，Jv 与预条件一起设计 |
| 子 communicator/多速率 | 实际子模型的负载或时间尺度表明需要独立调度 |

优先选择一种局部执行路径。若采用 MFEM/libCEED 已管理的 backend，不在外层再平铺一份相同设备缓冲与执行循环。首版低阶 Tet4 不因“高阶库通常更快”而自动获益，应以同一完整算例的总耗时判断。

依据：[libCEED、MFEM、LifeV、Kokkos](../research/UPSTREAM_ARCHITECTURE_REVIEW.md)。

