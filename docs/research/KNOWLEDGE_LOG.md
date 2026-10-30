# EONSim Knowledge Log

本文件是知识资产索引，不代替文章正文、文献阅读笔记或实验原始数据。

## HPC-02 / 2026-10-30

[固定 COO 装配草稿](../../website/drafts/fluid-coo-assembly.md)：实现/测量提交 `ceea57d`，
区分局部贡献求和、实际错误同步、1/2/4 rank 验证和 36 次配对性能测量。
保留准备/内存成本、WSL 环境和既有 MPI 故障测试超时限制；仅独立流体 Jacobian。
待人工审查，未发布。

## 状态定义

- idea：值得研究的主题，尚无完整内容。
- draft：已有草稿，尚未审核。
- review：正在人工审核。
- published：已合并到 main 并出现在公开网站。
- superseded：被更新版本替代，保留历史链接。

## 已发布知识

| Topic | 状态 | 主题 | 文章 |
|---|---|---|---|
| HUB-K001 | published | CFD 求解器学习路径 | [CFD](/learning/cfd) |
| HUB-K002 | published | 有限元与固体力学 | [FEM](/learning/fem) |
| HUB-K003 | published | HPC 与并行计算 | [HPC](/learning/hpc) |
| HUB-K004 | published | EONSim 并行稀疏矩阵装配 | [Parallel Sparse Assembly](/knowledge/parallel-sparse-assembly) |
| HUB-K005 | published | EONSim 单体 FSI 架构 | [Monolithic FSI](/knowledge/monolithic-fsi) |
| HUB-K006 | published | EONSim 构建与运行 | [Build and Run](/tutorials/build-and-run) |

## 候选知识主题

| Topic | 状态 | 主题 | 文章/预期证据 |
|---|---|---|---|
| HUB-K007 | draft | PETSc 非线性求解器对象生命周期 | [PETSc object lifetime](../../website/drafts/petsc-object-lifetime.md)；源码审计已完成，性能尚未测量 |
| HUB-K008 | idea | Newton 变量/残量一致缩放 | 数学推导、Jacobian 变换、Jv 与线搜索验证 |
| HUB-K009 | idea | Schur/GAMG 网格规模行为 | 多网格规模迭代数、内存和耗时 |
| HUB-K010 | idea | MPIAIJ 对角/非对角预分配和装配成本 | d_nnz/o_nnz、远程插入、MatAssembly 计时 |
| HUB-K011 | idea | PETSc SNES/KSP/PC setup profiling | 多时间步日志、重复运行统计和环境信息 |

## 登记规则

- 只有形成可复用知识的任务才登记；普通 typo、纯格式变更不登记。
- 每个条目关联文章路径、源码 commit、参考来源和验证证据（如有）。
- 没有运行数据时不得填写性能数值；没有测试时不得标记为已验证。
- 草稿位于公开仓库，不能存放私密研究笔记、凭据、受限数据或未授权论文全文。
- 发布状态只有在文章进入正式栏目并合并到 main 后才改为 published。

## SOLVER-01 / 2026-10-30

草稿：[PETSc 对象生命周期](../../website/drafts/petsc-object-lifetime.md)。证据：固定提交源码审计；无新增数值/性能实测。待人工核对上下文生命周期与计时边界，未发布。

## SOLVER-01B / 2026-10-30

[诊断开销测量草稿](../../website/drafts/nonlinear-setup-baseline.md)：已运行1/2 rank重复测量，具有源码/输出一致性/性能样本证据；无持久化优化收益证据。待人工审核。

## SOLVER-02 / 2026-10-30

[多时间步setup草稿](../../website/drafts/multistep-setup-profile.md)：源码/重复输出/性能证据已归档；无持久化收益证据，等待人工审核。

## SOLVER-05 / 2026-10-30

[重复线性求解的 KSP 所有权](../../website/drafts/linear-solve-ksp-lifetime.md)：代码提交 c47f00d；PETSc 官方生命周期资料、旧实现失败及修复后 1/2 rank 创建/销毁计数与数值验证。无性能数据，未发布；待审核作用域销毁和测试边界。

## SOLVER-03 / 2026-10-30

[Newton 缩放算法草稿](../../website/drafts/newton-scaling.md)：审查基线 717b25b，规格与精确代数脚本 6dc2baf。理论推导、当前代码和独立代数验证分开列示；无 PETSc 集成及性能证据。待审核尺度配置、约束变换及停止准则，未发布。

## SOLVER-04 / 2026-10-30

[Schur 网格测量草稿](../../website/drafts/schur-mesh-profile.md)：脚本/源码提交 79eb826，6 个直接参考、18 个 Schur 样本及原始证据入 Git。包含理论、实现、数值对照与性能证据；仅 108–1372 DoF、1/2 rank，不支持网格无关性或跨节点扩展结论。待人工审核计时与误差口径，未发布。

## SOLVER-04B / 2026-10-30

[求解器层级算子尺寸草稿](../../website/drafts/solver-level-dimensions.md)：提交 124bed3，记录元数据/communicator 语义、实际代码与 Release 1/2/4 rank 验证。无性能收益证据；未设置算子的哨兵分支未单独触发。待人工审核，未发布。

## HPC-01A / 2026-10-30

[装配阶段计时草稿](../../website/drafts/assembly-phase-timers.md)：提交 fff4895，记录时间规约数学、阶段实现与 Release/Debug 针对性验证；无性能收益或纯 kernel/通信归因证据。待人工审核边界及失败路径，未发布。

## HPC-01B / 2026-10-30

[装配阶段测量草稿](../../website/drafts/assembly-phase-baseline.md)：脚本提交 d1708e1，6 个参考和 18 个 Schur 样本、30 份日志及 JSON 入 Git；包含理论/代码/数值与性能证据，未拆分纯 kernel/插入或纯通信。待审核计时与归因边界，未发布。

## HPC-01C / 2026-10-30

[瞬态装配草稿](../../website/drafts/transient-assembly-profile.md)：测量82081d5，独立固体验证0f90585，统计f92e57b；18次运行180步，1/2/4 rank，最终物理解对照和逐步分布入Git。理论、实现、数值与性能证据分开；无纯kernel归因或多节点结论，待人工审核。

## HPC-01D / 2026-10-30

[流体单元计时草稿](../../website/drafts/fluid-element-timing.md)：源码1722265，解释kernel/插入边界与有/无切线计数；Release/Debug各通过steady/transient/tagged 1/2 rank开关对照。没有性能收益或计时扰动证据；仅独立流体，待人工审核，未发布。

## HPC-01E / 2026-10-30

[流体单元计时扰动草稿](../../website/drafts/fluid-element-overhead.md)：脚本1423b99，30个计量样本/15对及6次预热，逐rank数据和39份日志入Git；理论、实现、数值一致性及性能观测分开。范围不支持固定开销或加速结论，待人工审核，未发布。


## QA-01 / 2026-10-30

[profiling日志校验草稿](../../website/drafts/profile-log-validation.md)：实现7b91030，11项回归覆盖72份归档日志与损坏日志负对照；说明NaN比较、整数原因码与根节点完整性。没有新增数值或性能测量；待人工审查协议范围，未发布。
