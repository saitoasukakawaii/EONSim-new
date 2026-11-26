---
title: "EONSim：固定 Schur 图复用与通信重叠中的重复工作"
description: "复用节点逆的 COO 结构，避免两阶段场展开重复，并验证输出对照器自身。"
contentStatus: draft
taskId: "HPC-07"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/57"
baseCommit: "55a04f73d2004970184f96ae6a3a1abc540d8076"
resultCommit: "4c7edc6cc14219acfc97d39b9651c935a1c875ac"
testCommit: "8e6c0137205fd4eb288137e03296d116e920488d"
date: "2026-11-26"
---

# 固定 Schur 图复用与通信重叠中的重复工作

## 目标与适用读者

面向维护分布式有限元求解器的开发者，说明已经实现的优化路径里还会出现哪些重复
工作，以及如何分别证明数值等价、工作量减少和实际耗时变化。本例是小规模共形
monolithic FSI；不涉及改变物理方程或构造新的 AMG 理论。

## 节点 Schur：固定结构与当前数值

**数学关系。** 对分块矩阵，当前节点近似采用

\[
\widehat S=D-C H B,\qquad H=\operatorname{blockdiag}(A_{ii}^{-1}).
\]

这里节点块可含一至三个速度分量，或一至四个混合速度/压力分量；约束和不完整分量
由已有语义分组处理。在当前 `NonlinearSystem` 的固定图生命周期内，节点分组、行列
所有权和逆块的可能非零位置保持不变，数值随 Jacobian 更新。

**实现证据。** 旧更新每次重建覆盖计数、分配逆块数组、逐节点调用矩阵插入并显式
装配。`4c7edc6` 在 `src/algebra/pc_plan.cpp` 的 `NodalSchur` 中，一次准备完整 COO 图，
保留 offsets 和紧凑值缓冲；每次重新提取当前节点矩阵，做同样的主元求逆/均衡，全部
rank 数值检查通过后覆盖所有逆块位置。符号矩阵乘积及 USER Schur 对象继续复用。

完整覆盖包括当前为零的元素，否则“前一轮非零、本轮为零”可能留下旧值。缓存的只是
固定结构，不是旧逆块；每次新值仍经过有限性和奇异性检查。实现保留受支持的
`MatGetValues` 接口，没有缓存 PETSc 内部 CSR 指针或依赖子矩阵内部位置稳定。

**验证证据。** 独立余子式 oracle 对照四次更新：原值、整体缩放、节点非对角项为零、
恢复非零。既有混合结构 Schur oracle 同时覆盖非对称、约束、极端量纲、非有限/奇异
拒绝和恢复。1/2/4 rank 全部通过，包括空 owner；实际求解仍检查真实线性残差。

## 重叠通信：两个阶段不必重复展开同一值

**实现证据。** `src/physics/fsi.cpp` 的 owned 阶段使用已就绪值进行场展开，ghost
交换完成后 halo 阶段曾再次展开整场。本次缓存仅远端物理槽位，halo 阶段只补齐这些
槽位。分类依赖消元后的 trial 别名，而不是直接依赖 mesh-node owner，因此界面和
刚体别名仍正确。当前步的 lifting、入口值和时间系数在 owned 阶段完整更新。

零单元阶段跳过 OpenMP 团队；端口/刚体项位于单元团队之后，仍在 halo 阶段执行。
故障恢复时下一次评价从当前 trial 重新展开；原 ghost 排空和共同错误传播路径保持。

**验证证据。** 双线程 overlap 的刚体/弹性、AIJ/COO、移动端口重启、真实缩步以及
第二批 worker/insert 故障检查通过。单 rank 实测 `FSIElementBatch` 事件从 58 降至 29，
这是空 halo 团队被消除的直接证据。

## 对照脚本也会隐藏错误

**实现事实。** 原 ASCII/HDF5 对照使用 `zip(ids,tags)` 和 cell ID 字典。短数组可能
在 `zip` 处被截断，重复身份可能被字典覆盖，负连接索引可被 Python 当作倒数索引。
只检查 DataItem 的形状还不能发现等形数据集绑定被交换。

本次在转换之前校验完整长度、唯一身份、整数类型、索引范围和 mixed 流消耗情况；
核对拓扑类型、域完整性、属性类型/中心和具体数据集绑定，同时比较 VTK 单元类型。
九项有意破坏输入的回归新增到已有 validator 测试模块，全模块 30 项通过。
新校验器重新读取历史真实 writer 输出，14 份对照精确通过；复用历史输出不等于新跑
物理求解，其来源和哈希在证据中单独记录。

### MPI 日志合并也可能造成验收误报

远端故障注入检查曾因如下合并日志被误判为缺少注入记录：

```text
EONSim rank fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1
```

另一个 rank 尚未写完的 stderr 前缀出现在完整 stdout 记录之前，原来的行首匹配因此
漏掉标记；实际故障已正确发生在双线程团队的 worker、第二批单元。修复只调整该故障
记录的解析：允许标记前的交错前缀，要求标记恰好出现一次、完整字段序列保持完整，并
保留预期 mode、`team > 1`、`batch = 1`、线程编号范围和 worker/主线程角色检查。
缺字段、重复标记、非整数字段或多余冲突字段仍被拒绝。生产求解代码和数值接受门槛
没有因这次日志修复改变；原始失败日志与后续验收分别留存，避免将记录格式问题计为
求解失败或直接略过故障注入门槛。

## 性能观察与限制

最终测试源码 `8e6c013` 的远端验收实际执行 43/43 Release、44/44 Python，失败和
数值跳过均为 0；原件与成功的增量验收收据见完整证据，不把文档提交复用算成新执行。

**性能证据。** PETSc3.23.7/GCC15.3.0/OpenMPI5.0.8 Release，共享单机，n8 双域
5,367 DoF，1/2 rank、两线程，五步；每档一组预热和三组交替配对，共16次运行。
80 个接受步、160 次线性修正通过原门槛；新旧字段、历史和迭代轨迹相同。

2-rank 线性时间配对中位下降4.49%，范围为下降3.67%至13.28%；wall中位下降6.42%，
但范围包含一次增加14.38%。1-rank wall中位下降0.93%，也有正负波动；2-rank最大
rank峰值RSS中位增加1.08%。因此本轮证据支持消除具体重复工作，不支持普遍端到端加速。
PETSc的MatZeroEntries事件减少9次，COO图准备1次并更新10次；全程序的MatAssembly
事件1-rank仍为239，2-rank为561→563，不能从应用层显式调用减少推断底层通信减少。

## 可复核来源与进一步检查

- [完整命令、固定源、失败环境尝试、性能和原始证据](../../docs/research/data/hpc-followup-2026-11-26/README.md)。
- [固定源码](https://github.com/saitoasukakawaii/EONSim-new/tree/4c7edc6cc14219acfc97d39b9651c935a1c875ac)：`src/algebra/pc_plan.cpp`、`src/physics/fsi.cpp`、`scripts/verify_hdf5_outputs.py` 与对应测试。
- [离散算子契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)与[并行内存契约](../../docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)。

进一步复核可从三个问题开始：某个缓存是否只有结构固定？新值为零时是否彻底覆盖？
计时减少能否与直接工作量证据对应？多节点、不同网格与不同材料条件仍需各自实测，
不能将本例的三组配对推广到这些条件。本文保留为未发布草稿。
