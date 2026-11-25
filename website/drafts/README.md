# 知识草稿与选题目录

2026-11-24 核对，共 34 篇技术草稿。下表保留原稿链接，方便追溯历史实验；公开页面在独立的知识、学习或教程栏目编辑。正式展示以网站发布 PR 经人工审阅并合入主线为准。[网站贡献规范](../development/contribution.md) · [研究记录](../../docs/research/KNOWLEDGE_LOG.md)

## 2026-11-25 开发增补

| 草稿 | 已有依据与审阅重点 |
|---|---|
| [FSI 嵌套 Schur 与两层校正](fsi-nested-schur-twolevel.md) | PR #49 的完整流体分组、三个 A00 角色和分区常数粗空间；保留其历史默认值与原实验范围。 |
| [FSI 流体响应与嵌套成本](fsi-schur-response-cost.md) | PR #50 的混合节点结构 P、两个单次 PC 默认值、72 次性能对照与独立重放；区分精确 Jacobian、近似 Schur 作用及实际计时边界。 |

## 本次选编的九篇草稿

| 原始材料 | 选取的内容 | 对应网站稿 |
|---|---|---|
| [稳态刚性管的边界与几何](rigid-tube-geometry-and-mixed-boundaries.md) | 端部应力与横向速度约束如何配合 | [振荡圆管的流量与压力](../knowledge/womersley-verification.md) |
| [全场误差与局部质量](tube-field-errors-and-local-mass.md) | 端面流量和域内速度场分别检验什么 | [振荡圆管的流量与压力](../knowledge/womersley-verification.md) |
| [Womersley 流量与压力迹](womersley-flow-and-pressure-traces.md) | 解析解、末周期跨程序波形、固定周向网格加密和原始输出复算 | [振荡圆管的流量与压力](../knowledge/womersley-verification.md) |
| [圆管入口的离散归一化](fsi-circular-inlet-discrete-flux.md) | P1 三角面通量与零归一化系数 | [移动域的质量预算](../knowledge/ale-mass-budget.md) |
| [弹性通道的质量预算](fsi-periodic-flow-mass-budget.md) | 阶段壁面通量与接受步体积差，六周期时间加密 | [移动域的质量预算](../knowledge/ale-mass-budget.md) |
| [四面体黏性项与 ALE 导数](tet4-viscous-work-and-ale-tangents.md) | 节点力、速度切线、几何导数和完整求解时间 | [四面体黏性积分](../knowledge/tet4-viscosity.md) |
| [单元计时的观测开销](fluid-element-overhead.md) | 配对比较中固定诊断开关和运行顺序 | [四面体黏性积分](../knowledge/tet4-viscosity.md) |
| [共享边自由度与 P2 Poisson](p2-edge-space-poisson.md) | 两单元的九个全局自由度、空间加密与积分均值 | [P2 验证教程](../tutorials/p2-verification.md) |
| [P2 瞬态扩散与历史](p2-transient-history.md) | 时间制造解、接受步历史和同分区恢复 | [P2 验证教程](../tutorials/p2-verification.md) |

[HPC 开源软件阅读指南](../learning/open-source-hpc.md)使用主线调研报告的 50 个项目条目，单独计入学习栏目。

## 待编专题及开发记录

每行给出合编方向和下一次编辑应核对的事项。草稿中的时间、分支和性能数据均保留原实验范围。

| 方向 | 草稿 | 下一步 |
|---|---|---|
| 嵌套场分块 | [DoF 身份与界面消元](dof-semantics-and-nested-fsi-blocks.md)、[子矩阵编号](semantic-blocks-and-parent-numbering.md)、[装配置换的验收](assembled-permutation-and-pc-verification.md) | 合编一个小矩阵案例，列出全局编号、父块编号和直接解对照。 |
| 时间积分 | [BDF2 与稳定化](bdf2-time-error-and-stabilization.md)、[generalized-α 阶段量](generalized-alpha-stage-and-physical-output.md) | 以同一可制造问题展示端点、阶段及变步历史，逐一标注适用物理场。 |
| 时变 FSI 边界 | [入口与终点几何](fsi-inlet-endpoint-and-resolution.md)、[周期压力历史](fsi-periodic-pressure-history.md) | 用一个载荷时间轴串起试算、接受、拒绝和恢复，核对单位与初值。 |
| 周期收敛 | [完整场周期判据](fsi-periodic-state-and-error-separation.md) | 从原档案选一组同相位场，分别绘出剩余瞬态、时间差和空间差。 |
| 装配与计时 | [阶段计时边界](assembly-phase-timers.md)、[稳态装配基线](assembly-phase-baseline.md)、[瞬态装配](transient-assembly-profile.md)、[流体核与插入](fluid-element-timing.md)、[多步初始化](multistep-setup-profile.md)、[非线性初始化基线](nonlinear-setup-baseline.md) | 汇总首步与后续步、计时区间包含关系和每个实验的硬件；保留原始基线供开发者复核。 |
| 并行装配 | [固定 COO 图](fluid-coo-assembly.md) | 作为并行装配专题的后续算例，补全重复坐标和并行失败路径的最小例子。 |
| PETSc 对象复用 | [重复线性求解](linear-solve-ksp-lifetime.md)、[对象生命周期](petsc-object-lifetime.md) | 配合一个连续求解案例，列出图、数值和预条件器分别何时需要更新。 |
| 预条件器测量 | [Schur 与网格大小](schur-mesh-profile.md)、[求解器层级尺寸](solver-level-dimensions.md) | 先给出层级尺寸和网格序列，再解释小网格计时的适用范围。 |
| Newton 缩放 | [残量验收和坐标缩放](newton-scaling.md) | 整理带单位的两场残量例题，分别复核各场误差和停止条件。 |
| 离散空间架构 | [通用 FEM 与 DoF 设计](general-fem-dof-architecture.md)、[规范化网格与混合单元](normalized-mesh-and-bilinear-scalar-elements.md) | 对照当前支持的几何与场空间，把已实现组合和设计设想分别列出。 |
| 研发维护 | [增量 CI 与证据复用](incremental-ci-and-evidence-reuse.md)、[MPI 失败与云端复现](mpi-failure-cloud-reproducibility.md)、[计时日志校验](profile-log-validation.md) | 作为维护者参考。编写排障教程时再选取可复现的故障、输入和观测输出。 |
