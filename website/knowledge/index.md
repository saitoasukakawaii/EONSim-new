# 知识专题

专题文章把数学理论、算法设计和 EONSim 的实际实现联系起来。文章应明确标注哪些是理论背景、哪些是当前代码行为、哪些结论有实验支撑。

## 已发布专题

- [EONSim 并行稀疏矩阵装配](/knowledge/parallel-sparse-assembly)：METIS 分区、Owned/Ghost、FieldLayout、MPIAIJ 预分配和 PETSc 装配。
- [EONSim 单体 FSI 架构](/knowledge/monolithic-fsi)：联合未知量、界面约束、统一 Newton 与块预条件。

## 内容状态约定

- **理论说明**：由方程、教材或公开文献支持。
- **代码对应**：指向特定源码路径和版本。
- **已验证**：附有可复现测试、算例参数和误差指标。
- **待验证**：明确标记为设计建议或研究假设，不作为已实现能力宣传。
