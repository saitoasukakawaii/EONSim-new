---
title: "EONSim 开发记录：profiling 日志验收"
description: "避免非法数值与缺失根节点进入性能统计。"
contentStatus: draft
taskId: "QA-01"
baseCommit: "25e49af"
resultCommit: "7b91030"
date: "2026-10-30"
---

# EONSim 开发记录：profiling 日志验收

## 目标与研究问题

面向测量脚本维护者：日志有十份求解报告，就能作为十个成功时间步的证据吗？本任务修复数字语义和报告完整性检查；不改有限元方程或求解容差。

## 开发前状态

瞬态脚本先将原因码转为浮点数，再用 `reason <= 0` 拒绝失败。NaN 可绕过该判断。稳态脚本检查已有根节点是否失败，却没有要求每个 rank 都存在根节点；缺失节点可能被误接受。负对照在原实现中复现了这些问题。

## 理论与设计依据

Python 浮点 NaN 与有序数的大小比较返回假，因此“不是小于等于零”不足以证明“是正整数”。收敛原因和迭代计数应按整数读取；时间和残量要求有限且非负。这里没有新的数学推导，离散与验收契约仍见[离散算子文档](../../docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。

求解报告与时间步记录必须交替出现并完整覆盖1至10步。稳态层级的 `(rank, path)` 必须唯一，各rank必须有根节点；检查空集合不能作为根求解成功证据。

## 实现与对应源码

实现提交 [7b91030](https://github.com/saitoasukakawaii/EONSim-new/commit/7b91030)：

| 文件 | 实际修改 |
|---|---|
| [profile_schur_mesh.py](https://github.com/saitoasukakawaii/EONSim-new/blob/7b91030/scripts/profile_schur_mesh.py) | 共享整数/有限测量读取，检查统计字段、rank数和根层级完整性 |
| [profile_multistep_setup.py](https://github.com/saitoasukakawaii/EONSim-new/blob/7b91030/scripts/profile_multistep_setup.py) | 原因码正整数、迭代非负整数、报告/接受步顺序 |
| [test_profile_validation.py](https://github.com/saitoasukakawaii/EONSim-new/blob/7b91030/tests/test_profile_validation.py) | 真实归档日志和定向损坏负对照 |
| [CMakeLists.txt](https://github.com/saitoasukakawaii/EONSim-new/blob/7b91030/CMakeLists.txt) | 注册无需MPI启动的profile_log_validation测试 |

## 实验验证

| 实际命令 | 结果 |
|---|---|
| `python3 tests/test_profile_validation.py` | 11项通过，包含72份归档日志及负对照 |
| `python3 -O tests/test_profile_validation.py` | 11项通过；优化模式保留检查 |
| `cmake --build --preset release --target eonsim --parallel 4`，Debug同命令 | 两模式成功；重新生成CMake，求解器无需重编译 |
| `ctest --preset release -R '^profile_log_validation$' --output-on-failure`，Debug同命令 | 各1/1通过 |

归档数据包括18份[瞬态日志](../../docs/research/data/transient-assembly-2026-10-30)、18份[稳态日志](../../docs/research/data/assembly-phase-2026-10-30)和36份[开关测量/预热日志](../../docs/research/data/fluid-element-overhead-2026-10-30)。负对照包含NaN、无穷、分数/负计数、零原因码、缺字段/根节点、重复节点、rank不一致及错序/缺失时间步。零迭代计数仍可通过。

这是解析器回归证据；本轮没有重新运行物理求解，没有新增数值准确性证据。全套CTest未运行。

## 性能证据

本轮未测量性能，不能从解析器测试耗时推断求解器性能或MPI扩展能力。

## 适用范围、限制与审核问题

协议面向固定十步且无拒绝评价的既有测量。正原因码要求沿用原测量约束，不适合作为所有PETSc调用（例如没有实际KSP求解的初态收敛）的通用判据。没有验证所有可能的子层级拓扑，也没有检测日志中所有未知字段或证明日志来源真实性。

人工审核重点：上述严格协议是否符合后续测量需求；若未来加入重试或可变步数，应同步调整明确的测量协议和测试。草稿不自动发布。

## 参考与进一步阅读

- [Python 浮点比较语义](https://docs.python.org/3/reference/expressions.html#value-comparisons)。
- [Python math.isfinite](https://docs.python.org/3/library/math.html#math.isfinite)。
- [PETSc KSPConvergedReason](https://petsc.org/release/manualpages/KSP/KSPConvergedReason/)。
- 练习：从归档日志移除一个rank的根节点，同时保留子节点，观察仅检查rank集合为何不足。
