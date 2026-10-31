# MultiPhysicsHPC 文档入口

当前仓库包含 Tet4 多物理场、Tri3/Quad4 相容混合二维标量、语义 DoF/PC 分组及 BE/BDF2/generalized-alpha 的适用小算例实现；验证最多 4 rank。实际 API 从 include/eonsim 与 src 生成；开发规范中的声明片段仍为注释示例。阶段证据与适用范围见 README 和 ROADMAP。

## 阅读入口

- [Doxygen 与代码注释规范](../development/DOCUMENTATION_AND_COMMENTS.md)：哪些内容值得写、如何写，以及按需生成方式。
- @ref mhpc_numerics "数值与离散接口"
- @ref mhpc_parallel "并行与内存接口"
- @ref mhpc_fsi "单体 FSI 与状态接口"

## 与架构文档的关系

详细设计继续以仓库中的下列文件为准；这些路径用于在仓库中定位，不是假定已经发布的网站页面：

- 总入口：`MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md`
- 实施顺序：`docs/development/ROADMAP.md`
- 单体未知量和接口：`docs/architecture/L2_MONOLITHIC_FSI.md`
- 通用状态：`docs/architecture/L2_MULTIPHYSICS_AND_STATE.md`
- 并行与缓存：`docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md`

当前主线：独立流体、独立固体、单体刚体 FSI、单体弹性体 FSI。文档页面出现某个名字不代表能力已经实现；实现情况以代码及运行记录为准。

