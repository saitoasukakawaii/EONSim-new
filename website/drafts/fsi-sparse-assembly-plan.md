---
title: "算法说明：从稀疏图到可复用的 FSI 装配计划"
description: "区分容量预分配、矩阵列位置和单元贡献映射，说明固定图、COO 与融合残量切线的正确性及成本边界。"
contentStatus: draft
algorithm: "Fixed-pattern monolithic FSI assembly with cached contribution maps"
sourceReferences:
  - "https://petsc.org/release/manualpages/Mat/MatPreallocatorPreallocate/"
  - "https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/"
  - "https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/"
  - "https://petsc.org/release/manualpages/Mat/MatSetOption/"
eonsimCommit: "df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e"
baseCommit: "f7acccb7a8239c60a2d2be193a158ac430851dcf"
benchmarkDriverCommit: "b2ccd96419091c669b8dceae4369c5b255f47f57"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/51"
---

# 算法说明：从稀疏图到可复用的 FSI 装配计划

**审核草稿：本地 Release 8/8 通过，正式性能比较完成 64 次运行、320 个接受步。**
默认装配的 assembly 配对中位数下降 2.72%–11.81%，显式 COO 下降 30.16%–43.37%；
COO 四组的整次墙钟样本范围均跨零，且增加内存，因而保持显式选项，不宣称可靠的整体加速。[E1] [E2]
实现为 `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e`，计时驱动为 `b2ccd96419091c669b8dceae4369c5b255f47f57`。
开发基线是 `f7acccb`；实际旧二进制构建自 `c4fb266`，其编译输入与该主线相同，完整来源见归档。[E1] [E3]
本文面向低阶有限元和 MPI/PETSc 开发者，按**理论、实现、数值验证、性能实测**区分证据；文章尚未发布。

## 1. 问题：预分配之后，为什么仍有装配成本？

**理论。** 稀疏组装至少包含三个层次：

| 层次 | 保存什么 | 能消除什么工作 |
|---|---|---|
| 容量预分配 | 每个 owned row 的本地列、远程列容量 | 插入过程中因容量不足而重新分配 |
| 完整矩阵图 | 各行实际允许的列位置 | 首次数值装配时重新建立列结构 |
| 单元贡献计划 | 单元物理槽到测试行、试探列及贡献位置的映射 | 每次评价重复编号、筛选和部分插入组织 |

这里的 diagonal/off-diagonal 是 PETSc 按列 owner 划分的存储块，并非流体、结构等物理场块。
正确预分配并不等于每次 `MatSetValues` 无须寻找列位置；贡献计划也不能替代 ghost 同步和远程行归约。[P1] [P2]

**实现。** 基线已有 d/o 预分配、持久 AIJ 和错误检测。FSI 布局还经过
`MATPREALLOCATOR → 填零 AIJ → 逐行提取计数 → 新 AIJ`，中间完整列结构被丢弃。
这一冗余发生在系统初始化，不能描述成每次 Newton 都重建图。[S1] [S2]

## 2. 独立测试映射和试探映射

**理论与实现。** 令 \(q\) 为有效未知量，单元完整物理状态为 \(x_e=T_e q+g_e\)，则

\[
R(q)=\sum_e P_e r_e(T_eq+g_e)+R_{\mathrm{port/body}}(q),\qquad
J(q)=\sum_e P_e J_e T_e+J_{\mathrm{port/body}}.
\]

\(T_e\) 重建 trial，\(P_e\) 将局部测试残量累加到有效行；此处不要求 \(P_e=T_e^\mathsf T\)。
EONSim 界面流体速度映射到结构速度；界面网格位移由结构速度和当前时间格式恢复，
而界面网格测试行直接舍弃。人工网格反力不进入结构动量。[S1] [S3]

BE 下网格 trace 的 trial 权重是 \(\Delta t\)；BDF2 或 generalized-alpha 使用各自恢复系数。
计划缓存 row、column 和 trace 标记，数值填充仍使用**本次 attempt** 的 `mesh_dt`。
时间权重在一次 Newton 内固定，下一步或缩步时重新计算；拓扑、分区、有效编号或约束支撑改变则须重建计划。
ALE 坐标移动仍更新几何、梯度、体积、法向及导数，不能由“图不变”推断这些数值也不变。[S1] [S3]

## 3. 保留已经建立的 AIJ 图

**实现。** `ReducedLayout::jacobian_pattern` 直接持有 preallocator 填好的最终 AIJ，
通过可移动 `PetscOwner` 将唯一所有权交给 `NonlinearSystem`，不复制第二份矩阵。
转入时检查 communicator、行列 ownership、全局尺寸及 assembled 状态；随后仅刷新数值。
完整图启用 `MAT_NEW_NONZERO_LOCATION_ERR`，使新列位置成为显式错误。
原计数预分配路径仍使用 `MAT_NEW_NONZERO_ALLOCATION_ERR`；两者检查的对象不同。[S1] [S2] [P1] [P4]

准备阶段还移除了仅为临时 VecGhost 编号而构建的完整 nodal field layout。
单元图去重改为固定数组的排序与去重；reduced ghosts 用排序数组保存，owned local ID 直接计算。
旧基线没有同口径的初始化计时，因此本轮不单独量化这些准备改动的加速比例。

默认 `MatSetValues` 路径保留原保守图。显式启用 `-fsi_coo` 时跳过该 PREALLOCATOR/AIJ 图，
由 COO 坐标一次性建立最终结构，避免先建立默认图又替换它。[S1] [S3]

## 4. 从方程依赖推导 COO 掩码

**理论与实现。** 流体 Tet4 有 16 个速度/压力槽和 12 个网格位移槽。
流体方程可依赖全部 28 个 trial 槽；参考网格 Laplace 方程每行只依赖四节点的同一位移分量。
因此在无约束情况下，候选贡献数为

\[
16\times28+12\times4=496,
\]

相较完整 \(28\times28=784\) 少 288 个候选贡献。这是解析结构计数，**不是实测速度提升**。

| 单元形式 | 稠密局部槽数 | 方程依赖允许的候选贡献数 |
|---|---:|---:|
| 流体/ALE Tet4 | 784 | 496 |
| 独立 solid Tet4 | 144 | 144 |
| 旧逻辑共网格弹性单元，同时评价流体与结构 | 1,600 | 496 + 144 = 640 |

掩码先作用于完整物理槽，再过滤被消元的行列；不同物理列即使映射到相同 reduced column，
也保留各自贡献及时间权重。不能按某个 Newton 状态恰好得到的数值零裁剪图。[S3]
RCR 的端口压力、速度和 moving-plane 面积导数以及刚体项另行加入。
出口坐标准备与数值填充使用同一个枚举函数，使动态面积和时间系数不改变贡献次序。

## 5. 每次评价的数据流与失败处理

**实现。** 生命周期分为一次准备和多次数值更新：

1. 准备有效编号、test/trial 映射、单元活动分量和接触界面的单元清单。
2. COO 模式按固定次序准备全局坐标；先计数后 reserve，临时坐标副本在 PETSc setup 后释放。
3. 每次评价同步 owned/ghost 状态，在复用缓冲中展开物理场，计算局部残量及所需切线。
4. 默认路径按缓存编号插入；COO 路径按缓存 local tangent slots 填充值数组。
5. 各 rank 共同汇总局部错误。失败评价排空残量 stash，但不发布部分 COO 矩阵。
6. 成功时 `MatSetValuesCOO(..., INSERT_VALUES)` 覆盖上次矩阵，同时对重复坐标求和；
   后续仍执行统一非线性验收。只有完整时间步通过后才提交物理和电路历史。[S2] [S3] [P3]

COO 后端由显式开关识别，不通过值缓冲指针是否为空判断；零 owned/零贡献 rank 也必须遵守同一 collective 顺序。
残量向量仍沿用 PETSc Vec 插入和最终装配，本次没有新增第二套 MPI 反向累加逻辑。

## 6. 融合残量与切线，以及界面力重放

**实现。** 原 Jacobian 评价分别运行 double 残量和 Dual 残量，再从后者提取导数。
`fsi_element` 现在从同一次 Dual 求值提取 primal residual 和完整 tangent，减少重复当前几何和残量计算。
残量-only 评价仍走 double 路径；metric stabilization、网格速度与压力面导数保持在完整表达式内。[S4]

收敛后的界面力仍由未投影的物理残量重算，只遍历预先筛选的界面相邻单元，复用局部缓冲。
约束界面节点不会被过滤；后续全网格 stage/endpoint 几何检查保持执行。[S3]
融合后 `FSIFluidAleJac` 事件包含该次 Jacobian 的残量，`FSIFluidRes` 不再单独记录这份 double 重算；
前后事件时间必须按一致范围比较，不能只比较名称相同的事件便推断端到端收益。

## 7. 内存与性能实测

**理论。** 本 rank 的 K 个 COO 贡献需约 8K bytes 的 double 值缓冲；16-bit local tangent slots
另需约 2K_cell bytes，准备期还有坐标及其可修改副本，PETSc 另持有归约/通信计划。
`coo_value_bytes` 只统计值缓冲和补充 owned diagonals，不能当作总内存。[S2] [S3]
一百万个完全未约束流体 Tet4 的 496 项值缓冲合计为十进制 3.968 GB，784 项则为 6.272 GB；
MPI 下按本地单元分摊，尚未计端口、索引和 PETSc 内部开销。贡献数也不等于唯一矩阵 nnz。

**性能实测。** 共享 Linux 主机标识 Intel Xeon Platinum 8573C，可见 CPU 0–8，未确认独占物理核绑定。
使用 PETSc 3.23.7、Open MPI 5.0.8、GCC 15.3.0、SuperLU_DIST 9.1.0 的 Release 构建，每 rank 一个线程。
两套独立流固网格各运行五个 BE 步，dt=0.02、E=100、ν=0.3、压力=1；rtol=1e-10、atol=1e-12。
双方均为 PREONLY/LU，启用真实线性残量诊断；候选另有一次初始化报告，其归约计入 wall。
每组一对预热、三对交替测量；两网格、1/2 rank、默认/COO 两个 campaign 共 48 次测量和 16 次预热。[E1] [E2]

下表为逐对变化百分比的中位数；方括号是三对样本的最小/最大值，不是置信区间。
各模式均与其 campaign 的原基线配对，不能用两列中位数之比推算默认与 COO 的配对收益。

| 单元 / DoF / ranks | 默认 assembly | COO assembly | COO 整次 wall [最小, 最大] |
|---|---:|---:|---:|
| 771 / 703 / 1 | -11.81% | -43.37% | -1.02% [-2.93, +0.94] |
| 771 / 703 / 2 | -7.75% | -30.16% | +6.59% [-2.57, +13.95] |
| 6,147 / 5,367 / 1 | -2.72% | -39.18% | -0.26% [-15.99, +5.43] |
| 6,147 / 5,367 / 2 | -3.04% | -38.50% | -3.01% [-7.05, +23.30] |

这四组的 assembly 所有配对样本均下降。COO 的 wall 范围全部跨零；小样本、五步计算没有建立可靠的整体收益。
两网格唯一 nnz 分别由 36,643 降至 27,226、364,635 降至 260,010，即减少 25.70%、28.69%；
但细网格单 rank 峰值 RSS 中位数为 119.742→153.074 MiB，配对变化 +27.81%。选择 COO 需考虑摊销和内存预算。[E1] [E2]
候选矩阵均记录 `matrix_mallocs=0`、`nnz_unneeded=0`；后者表示多余容量，不是数值零的数量。[E2]

`fsi_assembly_plan.setup_seconds` 是布局、计划、系统三段准备区间之和的 rank 最大值，并非整个启动时间。
旧基线没有该初始化细分，不能从通用 solver setup 时间声称纯 sparse-pattern 初始化改善了某个百分比。
assembly/solve/ghost 等区间嵌套，最大值又可能来自不同 rank，不应相加恢复墙钟。[E1] [E3]

## 8. 数值验证、计时修复与复现

**数值验证。** df6e9ac 在先推送后执行的干净工作树上完成锁定 Release **8/8** 选测，零失败、跳过或超时：
`nonlinear_acceptance` 及其 2-rank 变体、`fsi_element_jacobian`、`fsi_coo_verification`、
`fsi_metric_stabilization`、`time_retry_verification`、`domains_verification`、`fluid_coo_verification`。
它们覆盖图所有权、24 组单元配置的 48 个方向差分、刚体/弹性/Neo-Hookean、RCR、变步长、重启和失败回滚；
FSI COO 测试 owned 场最大差 4.618e-13，真实 cutback 三次后接受 dt=0.0125；单元方向差分最大相对差 2.239e-10。[E1] [E4]
关联 b2 的远端 CI 在 PR merge SHA `ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0` 上另通过
Release 55/55 和 65 项 Python 检查；它与本地 df6e9ac 的 8/8 分开记录。
Debug 和 PETSc 3.19.6 的 CI jobs 为 skipped，未把它们算作通过。[E5]

正式两组 campaign 的 320 个接受步均为两次 SNES、两次累计 KSP 迭代，共 640 次线性修正。
默认场和历史差均为零；COO 最大场差 2.220e-16，历史差 1.816e-15；
真实线性残量除以 `1e-12+1e-10*rhs_norm` 的最大比为 0.0001603。
独立重算核验 1,152 份 VTU 分片、384 个保存状态和配对统计，未发现正式数值证据差异。[E2] [E3]

**实际修复。** 初始驱动的 POSIX `Popen.wait(timeout=...)` 使短命令 wall 出现约 50 ms 轮询粒度。
b2ccd 将其改为阻塞 wait 加独立 watchdog，先推送再重复两个正式 campaign；原 64 次 pilot 保留，
其墙钟不参与上述最终结论。生产 C++ 未改变，8 项源码选测证据保持来自 df6e9ac。[E1] [E3]

实际选测通过 `scripts/cloud/run.sh 3.23.7 release explicit` 执行，完整命令、选测清单及退出状态见收据。[E4]
性能复现使用固定二进制及 b2 驱动；例如以下命令指定一个新目录，COO campaign 另追加 `--candidate-options -fsi_coo`：

```bash
python scripts/benchmark_fsi_assembly.py --baseline BASE --candidate CANDIDATE \
  --baseline-commit c4fb266edec94afbf610cb1379dd1595ed96ae40 \
  --candidate-commit df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e \
  --mpiexec mpiexec --work NEW_DIRECTORY --subdivisions 4 8 --ranks 1 2 --steps 5 --repeats 3
```

本次 FSI 性能仅覆盖两套小网格和单机 1/2 rank；没有多节点、GPU、matrix-free 或长时间生产算例的加速证据。
练习：分别统计实际分区的贡献数、唯一 nnz 和峰值 RSS，并用足够长的轨迹检验 setup 摊销，而不改变方程或容差。

## 9. 固定源码与官方文档

- [S1] [有效编号与最终图](https://github.com/saitoasukakawaii/EONSim-new/blob/df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e/src/fem/reduced_layout.cpp)，`build_layout`。
- [S2] [矩阵接管、COO 和失败同步](https://github.com/saitoasukakawaii/EONSim-new/blob/df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e/src/algebra/nonlinear_system.cpp)，`NonlinearSystem`、`Context::evaluate`。
- [S3] [FSI 装配计划、端口和力重放](https://github.com/saitoasukakawaii/EONSim-new/blob/df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e/src/physics/fsi.cpp)，`FsiAssemblyPlan`、`outlet_jacobian_entries`、`solve_fsi_impl`。
- [S4] [融合局部 kernel](https://github.com/saitoasukakawaii/EONSim-new/blob/df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e/src/physics/fsi_element.cpp)，`fsi_element`；[方向导数检查](https://github.com/saitoasukakawaii/EONSim-new/blob/df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e/tests/verify_fsi_element.cpp)。
- [P1] PETSc [MatPreallocatorPreallocate](https://petsc.org/release/manualpages/Mat/MatPreallocatorPreallocate/)，填零图与一次性 preallocator 使用。
- [P2] PETSc [MatSetPreallocationCOO](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)，固定坐标贡献和索引数组语义。
- [P3] PETSc [MatSetValuesCOO](https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/)，重复坐标求和及 INSERT/ADD 语义。
- [P4] PETSc [MatSetOption](https://petsc.org/release/manualpages/Mat/MatSetOption/)，位置错误、分配错误和保留图选项。

- [E1] [本轮证据、方法与复现](../../docs/research/data/fsi-assembly-2026-11-25/README.md)，含源码与二进制哈希、失败记录及 pilot 边界。
- [E2] [正式性能统计](../../docs/research/data/fsi-assembly-2026-11-25/performance-summary.json)，仅 `perf-default-final`、`perf-coo-final`。
- [E3] [独立证据审计](../../docs/research/data/fsi-assembly-2026-11-25/independent-audit.json)，原始场、轨迹、哈希与配对统计重算。
- [E4] [本地 Release 原始收据](../../docs/research/data/fsi-assembly-2026-11-25/release-summary.json)，源码 df6e9ac，8 项选测。
- [E5] [远端 CI 源码与运行记录](../../docs/research/data/fsi-assembly-2026-11-25/ci-source-b2.json)，数值 run 45632206852、网站 run 45632206859。
