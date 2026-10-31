# EONSim 并行稀疏矩阵装配

本文解释 EONSim 当前如何把 Tet4 网格分区映射为 PETSc 分布式稀疏矩阵，并区分网格分区、自由度分区和矩阵行分区。

**内容状态：** 源码对应说明。实现细节以链接指向的仓库版本为准；本文不是大规模性能报告。下文以 Tet4 路径为例；PR #23 已增加 Tri3/Quad4 二维标量及语义 PC 树，当前支持范围见 [集成验收](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/FEM_INTEGRATION_VALIDATION.md)。

## 1. 数据流概览

1. 串行预处理阶段使用 METIS 按四面体共享面关系进行网格划分。
2. 每个 rank 获得自己的单元、owned 节点和 ghost 节点，并写入独立 HDF5 分区文件。
3. FieldLayout 将节点编号映射为分量交错的代数编号，并生成本地 owned 行的对角/非对角预分配计数。
4. PETSc MPIAIJ 保存全局分布式矩阵的本地行。
5. 单元核计算局部贡献，PETSc 汇总远程行插入。
6. 物理验收 fields 与 PC 分组分开；默认字段 IS 或显式语义 PcBlock 树供 PCFieldSplit 构造预条件器。

## 2. 网格分区与节点所有权

当前 MeshPartition 保存本 rank 的节点和单元。节点按 owned 在前、ghost 在后排列。节点 owner 由其相邻单元分区确定；当前实现采用相邻单元分区编号的最小值作为节点 owner。

这意味着一个共享节点只在一个 rank 上拥有最终代数行，但其他相邻 rank 可以保存该节点的 ghost 副本，以便计算本地单元贡献。

当前 METIS 处理发生在离线预处理阶段。求解阶段读取每个 rank 自己的 HDF5 分区文件；这不等同于并行 METIS 或在线重分区。

源码：
- [MeshPartition 定义](https://github.com/saitoasukakawaii/EONSim-new/blob/main/include/eonsim/mesh.hpp)
- [METIS 分区与 HDF5 写入](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/mesh/partition.cpp)

## 3. Node-major 代数编号与 Field IS

普通多分量场采用节点优先的交错编号：

$$
I(n,c)=I_{node}(n)N_c+c,
$$

其中 n 是节点，c 是分量，N_c 是每节点分量数。

例如三维速度与压力按每节点四个分量排列：

$$
[u_{x,0},u_{y,0},u_{z,0},p_0,
u_{x,1},u_{y,1},u_{z,1},p_1,\ldots]^T.
$$

FieldLayout 同时建立 velocity、pressure 等字段的索引集合。因而矩阵可以采用 node-major 排列，而预条件器仍然可以按物理场分块。

注意：Field IS 是本地 owned 行对应的全局代数索引集合，不是把所有 rank 的场变量复制到每个进程。

源码：
- [FieldLayout 接口](https://github.com/saitoasukakawaii/EONSim-new/blob/main/include/eonsim/field_layout.hpp)
- [FieldLayout 实现](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/field_layout.cpp)

## 4. MPIAIJ 对角与非对角预分配

对每个本地 owned 行，EONSim 遍历网格邻接稀疏图，统计列自由度中有多少属于本 rank 的 owned 列，多少属于远程 rank 拥有的列。

因此每行有两个预分配计数：

- d_nnz：本地列块（diagonal block）的非零元数量；
- o_nnz：远程列块（off-diagonal block）的非零元数量。

LinearSystem 使用 PETSc MatCreateAIJ。这里的 diagonal/off-diagonal 指按 MPI 行列拥有关系划分，不等于物理场的对角块和耦合块。

矩阵创建后启用 MAT_NEW_NONZERO_ALLOCATION_ERR，防止装配时静默发生超出预分配的新增非零元。

源码：
- [AlgebraLayout 与 LinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/main/include/eonsim/linear_system.hpp)
- [MPIAIJ 创建与装配](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/linear_system.cpp)

## 5. 单元贡献与远程行装配

局部单元可能同时包含本 rank 拥有的节点和其他 rank 拥有的 ghost 节点。单元只由其所属 rank 积分一次；该单元的矩阵贡献可包含远程 owned 行。

EONSim 通过 PETSc 的 ADD_VALUES 插入单元贡献，并在 assembly 阶段由 PETSc 完成远程行贡献的汇总。不要把 ghost 节点理解为另一份独立全局自由度，也不要在每个 rank 上重复积分共享单元。

## 6. 非线性与 FSI 的稀疏图

当前 NonlinearSystem 在固定 AlgebraLayout 下持有 ghost Vec、AIJ Mat 和本地试算缓冲。矩阵图由 layout 的 diagonal/off-diagonal 计数预分配，并启用 MAT_KEEP_NONZERO_PATTERN。

FSI 的 ReducedLayout 处理界面自由度别名、固定分量消元和有效编号。它使用 PETSc MATPREALLOCATOR 从本地单元自由度集合推导保守稀疏图，再建立 AIJ 预分配结构。

这与普通场的节点交错布局不同：FSI 的有效未知量可能因为界面共享和约束消元而减少，不能简单用节点数乘分量数推算最终 DOF 数。

源码：
- [ReducedLayout](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/reduced_layout.cpp)
- [NonlinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/nonlinear_system.cpp)

## 7. 物理场分块与 MPI 分块是两个维度

MPIAIJ 的 diagonal/off-diagonal 表示进程拥有关系；PCFieldSplit 的 velocity/pressure/mesh/structure 等 IS 表示物理字段分组。一个矩阵可以同时具有 MPI 分布式结构和物理场块结构。

因此不能把 AIJ 的 off-diagonal block 误认为 FSI 的流固耦合块，也不能因为 DOF 采用 node-major 编号就认为不能使用 FieldSplit。

## 8. 当前边界与下一步研究

当前实现采用离线 METIS、分区 HDF5、MPIAIJ 和 assembled 装配。已有阶段/单元计时、开关扰动与独立流体 COO 测量，见 [知识索引](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/research/KNOWLEDGE_LOG.md)。扩大问题规模时仍需测量：
- 网格预处理时间和峰值内存；
- 每 rank owned/ghost 数量与边界比例；
- d_nnz/o_nnz 分布及矩阵非零元数量；
- 单元装配时间、远程插入与 assembly 通信时间；
- KSP/PC 时间、迭代次数和每 rank 内存。

只有实测表明瓶颈存在，再评估 ParMETIS、并行输入、线程化装配、矩阵自由算子或其他稀疏存储方式。
