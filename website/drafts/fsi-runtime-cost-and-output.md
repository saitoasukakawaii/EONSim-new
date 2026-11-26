---
title: "EONSim 开发记录：重复切线、分区与输出成本"
description: "用实际 J/USER 工作量、分区身份和逐数组输出对照解释性能收益与回退。"
contentStatus: draft
taskId: "FSI-PERF-03"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/53"
baseCommit: "2dcb06c26a0359175e4f5a771d5bbff6dfc928af"
resultCommit: "7e8868e433fb0040806a6faf3ba8cd289a2aa3f1"
date: "2026-11-26"
---

# EONSim 开发记录：重复切线、分区与输出成本

## 目标与证据范围

本文面向维护单体 ALE/FSI 求解器的开发者，说明怎样把重复数值工作、负载分配和输出编码的
成本分别量清，同时保留完整导数、物理验收与并行失败传播。生产实现和候选二进制固定为
`7e8868e`，实验驱动随后更新为 `3e366c8` / `7d86f38`；每次均先推送、后执行。
实际源码、全部命令、输入、失败、二进制哈希和独立审计统一见
[FSI-PERF-03 证据索引](../../docs/research/data/fsi-runtime-2026-11-26/README.md)。

开发与验收已经完成。最近的 GitHub 权威核验显示 [PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53)
为 open / Draft、head `7d86f38`，尚未合并；最终证据 head 的四项保护检查通过后按用户授权合并。
PR 状态后续以 GitHub 为准。本文保持 `contentStatus: draft`，未公开发布。

## 开发前状态：先辨认重复的工作

基线 main `2dcb06c` 已有精确稀疏图、局部 COO 去重、残量 COO 和求解器对象复用。
本轮源码审查发现，压力方向仍占用前向 AD 宽度，默认 AIJ 仍传入较宽的局部块，线程团队按批次重建，
最终验收与反力提取重复评价残量。语义 Schur 在 `SNESSolve` 前准备的起点 Jacobian 也可能在普通
Newton 回调中再次组装。离线分区存在逐 rank 重扫，ASCII 边界文件则保存了整个本地节点集。
这些观察用于确定改动范围；每项机制单独能快多少，仍须由相应对照给出。

## 理论与实现：把有效期和数据身份写清楚

**理论。** 当前 P1 Tet4 流体残量中，压力通过均值和梯度线性进入，稳定化 tau 不依赖压力。
四个压力列可以解析形成；速度和 ALE 位置仍保留各 12 个前向 AD 方向，共 24 个。
压力当前值仍参与残量计算，其对速度/几何导数的贡献保留。减少 AD 方向不允许删去完整耦合切线中的列。
实际公式与适用契约见[离散算子](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。

**实现。** 首次 Schur 配置仍需要有效 Jacobian；首个普通回调的一次性消费要求 Vec/Mat 相同、
全部 owner 初值逐项相等且中间没有物理评价。资格在任何评价前清除，所有 rank 共同决定消费。
后续已经配置的合资格会话从新残量开始，把起点 Jacobian 延后到正常 SNES 回调；每次实际组装
仍更新数值和应用自建 USER Schur。对象生命周期、一次性数值消费和延后准备是三个不同概念。

持久线程团队仍使用最多 64-cell 的有界工作区；worker 只算局部 kernel，主线程按固定贡献顺序写入。
worker 或主线程插入异常经共同 barrier 收敛、线程 join 后重抛，再进入原有 collective 错误传播。
最终验收和原始反力共用一次独立的新残量组装；Jacobian-only scratch 残量不再发布无人使用的 COO 数值。
[并行与内存契约](../../docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)记录其边界。

默认分区保持 METIS 输入与稳定顺序，稳定分桶/前缀编号消除逐 rank 全局重扫。
非空成本输入由用户显式提供，并把实际单元归属纳入指纹，防止带权分片与旧身份混用。
这次试验的 `10:5,20:1` 是特定流固算例成本假设，不是所有流体/固体域的固定成本比。

输出默认仍为 ASCII，边界 piece 仅保留实际被其单元引用的节点，顺序沿用原 local 节点数组。
连接、坐标、owner、Int64 稳定 ID、algebra ID 和全部字段同步映射。可选 raw appended binary 使用
LittleEndian、UInt64 字节长度头和有界缓冲流式写入；volume-only 跳过边界 piece 与索引。
写出层不收集全局场、不复制完整编码场，PVTU 在所有 piece 完成后发布。

### 对应源码

| 路径（实现固定于 7e8868e） | 实际改动 |
|---|---|
| [fsi_element.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/7e8868e433fb0040806a6faf3ba8cd289a2aa3f1/src/physics/fsi_element.cpp) | 24 方向 AD 与解析压力列 |
| [fsi.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/7e8868e433fb0040806a6faf3ba8cd289a2aa3f1/src/physics/fsi.cpp) | 紧凑 AIJ、持久团队、第二批故障与 rank-local 成本 |
| [nonlinear_system.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/7e8868e433fb0040806a6faf3ba8cd289a2aa3f1/src/algebra/nonlinear_system.cpp) | 新鲜最终残量、起点切线资格/延后及 J/USER 计数 |
| [partition.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/7e8868e433fb0040806a6faf3ba8cd289a2aa3f1/src/mesh/partition.cpp) | 稳定分桶、前缀编号、显式成本、身份与阶段报告 |
| [vtu.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/7e8868e433fb0040806a6faf3ba8cd289a2aa3f1/src/io/vtu.cpp) | 紧凑边界、raw binary、borrowed field 视图 |

## 数值验证：已经执行的范围

本地 PETSc 3.23.7 Release 定向 **17/17** 通过。第二批线程故障使用 162-cell fixture，2 rank × 2 threads
的 worker/insert 四种模式均命中 `batch=1`；可恢复模式恰好缩步一次 `.008→.004`，fatal 模式无接受步和 VTU。
输出检查覆盖 `2^53+1` 的精确 Int64、二维 Tri3/Quad4 可变 offsets、边界重映射与关闭边界。

| 来源 | 本轮实际执行 | 复用历史通过证据 |
|---|---|---|
| 生产源码 [7e CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45711876709) | 48/48 Release、24 Python | 0 |
| 带权驱动 [3e CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45714273854) | 1 Release、21 Python | 47 Release 项，本次未运行 |
| 输出校验修复 [7d CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45715315451) | 0 项新数值执行 | 48 Release 项，本次未运行 |

部分正确性检查覆盖 4 rank；本地未增加全量、Debug 或 PETSc 3.19.6 验收。
CI 复用和后续文档提交没有被计成新的数值执行。完整命令在证据索引的 CTest 日志和 campaign `commands` 中保存。

## 性能设置与独立审计

运行在共享 AMD EPYC 9V74 主机，记录预算为 9 CPU、10,451,427,328 B 内存；不是独占节点实验。
锁定 GCC 15.3.0、Open MPI 5.0.8、PETSc 3.23.7 Release、METIS 5.1.0、HDF5 1.14.6。
依赖 OpenMP/BLAS 固定 1 线程，单元线程仅在线程组为 2。性能求解使用 1/2 rank。

FSI 采用独立流固 Tet4 网格，n=4/8 分别为 771/6147 总单元、703/5367 自由度；每次 10 个 BE 步、dt=.02。
物理配置与场缩放保持一致，默认/COO/权重比较固定 SuperLU_DIST 直接法，起点切线消融固定 twolevel。
逐次真实线性残量满足 `norm <= 1e-12 + 1e-10 * rhs_norm`，每个物理字段均检查其接受门槛，
全部保存状态与 CSV 的绝对比较门槛为 `2e-9`。

四组共 **88 runs / 880 接受步 / 1,760 次线性修正**，其中 22 次预热、66 次测量；每个配置三个交替配对。
独立审计核验 8,502 条文件哈希收据、968 个保存状态，按 domain+Int64 stable ID 重读体场、拓扑、
ghost/owner 和 CSV。最大场差 `4.440892098500626e-16`，最大历史差 `2.9841559419667343e-15`；
最大真实线性残量/门槛为 `0.0906395256835613`。逐步→运行→配对→median/min/max 全部复算一致，首次审计无错误。
前两组未记录历史 partition shard 哈希的限制保留；后两组具备实际 manifest 与 shard 收据。

### 用工作量计数解释起点切线收益

同一候选二进制、相同 twolevel 设置，仅切换 `-nonlinear_initial_jacobian_reuse false|true`。
每次 10 步的 raw counters 都得到：

| 计数 | false | true |
|---|---:|---:|
| 完整 Jacobian 装配 | 30 | 20 |
| USER Schur 更新 | 30 | 20 |
| Jacobian callbacks | 20 | 20 |
| 起点预装配 | 10 | 1 |
| 首回调一次性消费 | 0 | 1 |
| 后续起点延后 | 0 | 9 |

场、history 的差异精确为 0，Newton/Krylov 轨迹相同。每项变化均按 `candidate/baseline - 1` 逐对计算：

| 网格 / rank | Wall 配对中位变化 | Assembly 配对中位变化 |
|---|---:|---:|
| n=4 / 1 | −12.060% | −31.359% |
| n=4 / 2 | −17.369% | −39.550% |
| n=8 / 1 | −18.080% | −30.974% |
| n=8 / 2 | −25.594% | −36.289% |

显式成本 `10:5,20:1` 的 n=8/2-rank 本例，wall 中位数 **−10.585%**、assembly **−29.089%**，
同时 finalize **+24.555%**。它支持这个案例的负载调整，不支持通用权重推荐。
默认组合优化的 wall 收益混合；COO 双线程在单 rank 的 wall 中位数 **+3.900%**，2 rank 为 **−4.380%**。
局部机制仍保留完整实现，测量中的退步与跨零范围也保留，没有将所有阶段都写成加速。

### 把边界压缩和编码效果分开比较

输出算例为 15,625 节点、82,944 Tet4 单元，四种模式覆盖完整 ASCII、紧凑 ASCII、紧凑 binary、
binary volume-only。修复后的 **32 runs** 含 8 次预热；独立读取 84 VTU、28 PVTU，
核对源网格的全部稳定 ID、方向拓扑、标签、owner、编号和字段。所有解码数字精确相等，
signed zero 按数值相等解释，不声称文件字节相同。

| 公平比较：binary compact / ASCII compact | 1 rank | 2 rank |
|---|---:|---:|
| output 时间配对中位变化 | −81.338% | −82.010% |
| 完整求解 wall 配对中位变化 | −15.558% | −8.829% |
| 输出字节变化 | +0.815% | +3.060% |

ASCII 紧凑边界相对完整边界本身也减少数据；不能把该裁剪收益归给 binary 编码。
Raw binary 省去文本转换，在这个例子却略增字节，因此写出更快不保证文件更小。
输出计时覆盖正常写入和索引发布，不包含 fsync 的持久化保证。

离线 prepare 共 **24 次**，2/8/32 分片的 **168 对 P1 HDF5** 内容比较一致；整次 prepare wall
配对中位数分别为 **−12.248%、−16.536%、−32.702%**。这不是 32-rank 求解或 P2 证据。
HDF5 文件字节可能含不同元数据，比较对象是数组内容；4 组空 dataset 的 h5diff 提示另核对了
一致的零尺寸和类型。内部 partition profile 不含 mesh import，整次命令 wall 与阶段计时分别记录。

## 保留的失败：文本理由不能由数字解析器验证

3e driver 在完成 prepare 段后，首个 Poisson 输出求解正常返回 0，日志为
`reason=CONVERGED_RTOL`、`status=success`。验证器只收集数字键，随后读取文本 reason，
触发 `KeyError('reason')`；失败的是证据解析，不是这次线性求解。

原失败 results/log 没有覆盖。7d 改为单独验证文本收敛理由，并增加分阶段入口；
**先推送修复，再只重跑 output**。已完成的 partition 计时和内容对照继续引用原证据，
没有为了得到绿色总状态重复不受影响的实验，也没有改变方程或数值接受门槛。

## 结果的适用边界与复核练习

三个测量配对给出描述性中位数和范围，不是置信区间。阶段可能嵌套，各自的最大值还可能来自不同 rank，
不能相加解释 wall；错误同步等待也可能反映负载不平衡，单靠该计时不能归因于网络。
共享主机小网格上的 1/2-rank 收益不证明多节点、GPU 或生产尺度扩展性。

复核者可以对照首切线开关，先验证计数由 30→20、场/迭代不变，再读 wall 配对范围；
对输出则固定相同边界语义，再比较编码；对分区则先核对稳定 ID/指纹和所有权，再讨论成本权重。
完整控制项见 [FSI_RUNTIME_OPTIMIZATION](../../docs/development/FSI_RUNTIME_OPTIMIZATION.md)。

## 参考资料

- [PETSc SNESSetInitialFunction](https://petsc.org/release/manualpages/SNES/SNESSetInitialFunction/)
- [VTK XML file formats / AppendedData](https://docs.vtk.org/en/latest/vtk_file_formats/vtkxml_file_format.html)
- [源码、CI 收据、实验与审计索引](../../docs/research/data/fsi-runtime-2026-11-26/README.md)
- [EONSim 离散算子契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)
- [EONSim 并行内存契约](../../docs/architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)
