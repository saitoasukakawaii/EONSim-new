---
title: "EONSim 开发记录：固定 COO 图与安全并行装配"
description: "独立流体的可选 COO Jacobian、错误同步和配对测量。"
contentStatus: draft
taskId: "HPC-02"
pullRequest: ""
baseCommit: "24eae624ee93b3e1989312e1b1b273217571310f"
resultCommit: "ceea57d568db08c5181122cea66f5b9458c6200c"
date: "2026-10-30"
---

# 固定 COO 图与安全并行装配

## 目标与读者

面向理解有限元局部矩阵和 MPI 行所有权的开发者，本文说明何时可以缓存装配图、
为什么批量插入必须服从错误同步，以及怎样区分局部性能与端到端成本。
这是待审草稿；完整数据见 [HPC-02 报告](../../docs/research/FLUID_COO_ASSEMBLY_2026-10-30.md)。

## 理论：贡献次序与唯一坐标

设第 e 个 Tet4 的流体切线为 16×16 矩阵，有效编号映射为 g_e，则

$$J_{ij}=\sum_e\sum_{a,b:g_e(a)=i,g_e(b)=j}J^e_{ab}.$$

COO 记录单元贡献序列，同一坐标可以多次出现，也可以位于其它 rank 的 owned 行。
MPI 对角/非对角存储块由列所有权划分，不等同 velocity/pressure 物理字段块。
拓扑、分区和有效编号不变时，图可复用；材料、速度或 dt 改变后，依赖它们的数值仍须更新。

PETSc 的 COO INSERT_VALUES 先对重复坐标求和，再覆盖矩阵。固定图不改变上述求和公式，
但可能改变浮点累加顺序。验证应比较容差下的场、残量和反力，不能只比较退出码。

## 实现：局部失败与 collective 的顺序

实现提交 `ceea57d` 的实际修改：

| 文件 | 修改与目的 |
|---|---|
| `include/eonsim/nonlinear_system.hpp` | 图设置和借用缓冲，明确顺序、生命周期与回调职责 |
| `src/algebra/nonlinear_system.cpp` | 清零、同步错误后更新 COO、补 owned 对角，避免旧数值或失败污染 |
| `src/physics/fluid.cpp` | `-fluid_coo` 和固定单元切线打包，复用原物理 kernel |
| `tests/verify_coo_jacobian.cpp` | 精确解、重复/远程项、空贡献与局部失败恢复 |
| `tests/verify_fluid_coo.py` | 真实流体场、Schur、双向重启和错误入口 |

执行顺序为：

1. 首次 solve 前共同验证图，补约束所需的 owned 对角。PETSc 可以修改索引，故传入副本。
2. 每次 Jacobian 评价前清零缓冲；本地 kernel 计算并填值。残量仍走原 Vec 插入。
3. 汇总所有 rank 的 callback 错误，排空残量 stash；失败时不发布部分 COO 矩阵。
4. 成功时共同调用 MatSetValuesCOO，再按同一规则替换 Dirichlet 行。
5. 非线性及字段验收通过后才接受状态；失败后的新评价重新覆盖缓冲。

若在物理回调末尾直接调用 COO collective，一个 rank 可能已经在局部检查处抛异常，
其余 rank 却进入通信。错误同步必须位于两者之间。这里复用现有错误阶段和 PETSc
通信计划，不另实现 MPI 矩阵贡献累加器。

## 验证证据

Debug/Release 的新 COO 回归在 1/2/4 rank 通过；7 类真实流体每种构建执行 87 个命令，
旧/COO/跨 rank/Schur/重启比较最大字段差约 5.19e-12，包含原始动量反力。
代数例额外检查缺省约束对角、空贡献 rank、新零项、改变约束、局部拒绝与同对象恢复。

原有 solver_failures_mpi 在本机 PETSc 3.19.6 上超时；未修改主分支也复现相同现象。
因此不能声称整个套件通过。其根因尚未确定，其它版本未重验；新 COO 自身的 MPI
失败检查通过不替代该旧测试。命令和日志见研究报告。

## 性能证据

WSL2/i9-12900K、GCC13.3、PETSc3.19.6、OpenMPI4.1.6，每 rank 单线程；固定 10 步
瞬态、384/3072 Tet4、500/2916 DoF、1/2/4 rank，3 对交替测量并预热双方。
36 个计量运行的逐步迭代轨迹一致；连同 12 个预热，最大字段差不超过 6.67e-16。

本样本装配配对耗时中位数下降约 45–62%，solve 下降约 8–44%，端到端墙钟中位变化
约 -11% 到 0%，多组范围跨零。8³ 单 rank 峰值 RSS 中位数约 89.64→102.74 MiB，
准备约 45 ms。solve 不包含图准备而 wall 包含，不能用 solve 改善替代 wall 结论。
没有独占主机、置信区间、多节点或大规模证据；原始数据与计时嵌套边界见报告。

## 限制与进一步思考

当前只启用固定网格独立流体的 Jacobian；残量 COO、FSI、移动 ALE、GPU 不在范围内。
默认保持原路径，后续扩大范围需由实际成本和明确验收目标触发。

读者可检查：单元贡献次序改变后哪些数据需重建？新算子某个非对角项变零而未清除旧值，
会如何影响 Newton 增量？为什么逐步取 rank 最大值再相加，与先累加再取最大值不等价？

## 参考

- [PETSc MatSetPreallocationCOO](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)。
- [PETSc MatSetValuesCOO](https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/)。
- [L2 离散契约](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。
- [HPC-02 实测与限制](../../docs/research/FLUID_COO_ASSEMBLY_2026-10-30.md)。
