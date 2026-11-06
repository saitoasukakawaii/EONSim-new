# 知识专题

专题文章把数学理论、算法设计和 EONSim 的实际实现联系起来。文章应明确标注哪些是理论背景、哪些是当前代码行为、哪些结论有实验支撑。

## 已发布专题

- [EONSim 并行稀疏矩阵装配](/knowledge/parallel-sparse-assembly)：METIS 分区、Owned/Ghost、FieldLayout、MPIAIJ 预分配和 PETSc 装配。
- [EONSim 单体 FSI 架构](/knowledge/monolithic-fsi)：联合未知量、界面约束、统一 Newton 与块预条件；本次已按 2026-11-03 的主线能力更新。

## 当前实现参考

- [单体 FSI 数学契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/architecture/L2_MONOLITHIC_FSI.md)：流体、结构、ALE 与界面耦合的残量和切线约束。
- [FSI 周期流量入口与质量预算](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/FSI_PERIODIC_FLOW.md)：离散入口归一化、无滑移边界、阶段/端点质量诊断及验证边界。
- [FSI 时间积分契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/TIME_INTEGRATION.md)：BE、变步 BDF2、generalized-alpha 的适用范围和时间层语义。
- [二维标量有限元实现说明](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/SCALAR_2D.md)：Tri3/P1、Tri3 几何上的 P2 标量场、边界条件和瞬态扩散。

## 内容状态约定

- **理论说明**：由方程、教材或公开文献支持。
- **代码对应**：指向特定源码路径和版本。
- **已验证**：附有可复现测试、算例参数和误差指标。
- **待验证**：明确标记为设计建议或研究假设，不作为已实现能力宣传。

## 草稿与证据

新形成的技术文章仍保留在公开仓库的 `website/drafts/`，未经人工审阅不会被列为已发布专题。完整文章状态和验证来源见 [知识资产索引](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/research/KNOWLEDGE_LOG.md)。