---
title: "EONSim 开发记录：重复切线、分区与输出成本"
description: "从实际工作量计数、分区身份和输出语义审查 CPU/MPI 性能优化。"
contentStatus: draft
taskId: "FSI-PERF-03"
pullRequest: ""
baseCommit: "2dcb06c26a0359175e4f5a771d5bbff6dfc928af"
resultCommit: ""
date: "2026-11-26"
---

# EONSim 开发记录：重复切线、分区与输出成本

## 目标与读者

本文面向维护单体 ALE/FSI 求解器的开发者，解释如何消除重复数值工作，
同时保留物理验收、并行失败传播和可审计的数据身份。文章尚未公开发布。

## 开发前状态

基线 main 已有精确稀疏图、局部 COO 去重和求解器会话复用。
但语义 Schur 在 `SNESSolve` 前预装配起点 Jacobian，随后首个普通 Newton
回调再次装配同一状态；最终残量、AD 压力方向与跨批次线程管理也仍有重复成本。
离线分区对每个 rank 重扫全网格；ASCII 边界文件保存整个本地节点集。
这是源码观察，尚不是性能测量结论。

## 设计依据与证据分级

**理论。** 对当前离散式，压力以均值和梯度线性进入流体残量，稳定化 tau
不依赖压力。可直接形成四个压力列，并对速度和 ALE 位置保留完整 24 方向
前向链式导数；这不允许删除压力值对几何或速度导数的贡献。

**实现。** 首次 Schur 配置必须看到有效 Jacobian；一次性复用只允许相同
Vec/Mat、所有 owner 值逐项相等且没有中间物理评价的状态。后续会话从新残量
开始，首个正常回调刷新数值 Jacobian 与 USER Schur。对象复用不等于旧数值复用。
默认分区仍使用原 METIS 输入；显式带权分区将实际归属序列纳入身份，防止
不同分片集合共享旧指纹。二进制输出遵循 VTK XML 的 appended/raw 格式。

**数值验证。** 当前仅完成实现与静态审查；执行结果待代码推送后补齐。

**性能。** 当前未测量。后续成对样本会区分 wall、装配、线性解、分区和输出；
并列记录原始失败、配对范围、二进制 SHA、rank、网格及容差。

## 实际修改

| 文件 | 修改 | 原因 |
|---|---|---|
| `src/physics/fsi_element.cpp` | 24 方向 AD 与解析压力列 | 减少每次核调用工作量 |
| `src/physics/fsi.cpp` | 紧凑 AIJ、有界持久团队、第二批故障观测 | 减少填充与团队创建成本，验证部分装配后的恢复 |
| `src/algebra/nonlinear_system.cpp` | 新鲜最终残量复用、一次性起点切线、工作量计数 | 避免重复评价，显示每次真正执行的工作 |
| `src/mesh/partition.cpp` | 稳定分桶、前缀编号、显式成本、身份和阶段报告 | 移除每 rank 全局扫描并保护带权分区兼容性 |
| `src/io/vtu.cpp` | 边界节点裁剪与可选二进制 | 减少重复数据及文本转换 |

## 验证记录

待远程同步后执行。最终来源、命令和结果统一链接至
[性能证据索引](../../docs/research/data/fsi-runtime-2026-11-26/README.md)。
没有运行的算例不会记作通过。复用历史 CI 证据与本轮新执行分别计数。

## 限制与复核问题

rank 的独立最大时间不能相加为总时间。失败同步中的等待可能来自负载不平衡，
单纯看到该计时大不能证明 MPI 自身慢。单元权重需来自实际算例成本，不能从
“流体/固体”标签猜测通用常数。小规模共享主机结果不证明多节点或 GPU 扩展性。

复核者应关注：一次性切线是否在任何试探评价后失效；边界紧凑映射是否保留
大整数 ID、方向及字段分量；带权分片混用是否被拒绝；实测加速是否伴随相同
接受轨迹和真实残量。可练习开启对照开关，核对每步 Jacobian 计数与 wall 的关系。

## 参考资料

- [PETSc SNESSetInitialFunction](https://petsc.org/release/manualpages/SNES/SNESSetInitialFunction/)
- [VTK XML file formats / AppendedData](https://docs.vtk.org/en/latest/vtk_file_formats/vtkxml_file_format.html)
- [EONSim 离散算子契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)
- [EONSim 并行内存契约](../../docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)
