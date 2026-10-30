# HPC 与并行计算学习路径

## 学习目标

理解科学计算程序如何从单进程有限元计算扩展到分布式内存 MPI 程序，并掌握 PETSc 的分布式矩阵和求解器接口。

## 学习顺序

1. 共享内存与分布式内存模型；
2. 图划分与网格分区；
3. Owned / Ghost 节点和自由度；
4. Global ID、Local ID 与 PETSc algebra index；
5. MPI halo exchange 和向量同步；
6. AIJ 稀疏矩阵的对角与非对角预分配；
7. 分布式装配和远程行贡献；
8. Krylov 方法、FieldSplit 和 Schur 补；
9. 强扩展、弱扩展、负载均衡和内存分析。

## 两个重要的分布式概念

每个 MPI rank 拥有一部分全局自由度，并可能保存其他 rank 自由度的 ghost 副本。拥有关系决定谁负责最终存储和规约；ghost 副本用于本地单元计算。

对一个 rank 的矩阵行，列可分为：
- 对角块：列自由度也由本 rank 拥有；
- 非对角块：列自由度由其他 rank 拥有。

这正是 PETSc MPIAIJ 预分配所需的两个计数。

## EONSim 对应代码

- [MeshPartition](https://github.com/saitoasukakawaii/EONSim-new/blob/main/include/eonsim/mesh.hpp)
- [FieldLayout](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/field_layout.cpp)
- [ReducedLayout](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/reduced_layout.cpp)
- [PETSc LinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/linear_system.cpp)
- [NonlinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/nonlinear_system.cpp)

## 练习

1. 给定一个 Tet4 单元，画出它在两个 rank 上的 owned/ghost 节点。
2. 对一个本地 owned 行，统计 diagonal 和 off-diagonal 非零元。
3. 解释为什么远程单元可以贡献本地 owned 行。
4. 比较全局编号、局部编号和 Field IS 的职责。
