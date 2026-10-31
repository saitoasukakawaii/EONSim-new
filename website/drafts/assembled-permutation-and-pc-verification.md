---
title: "真实装配置换与预条件分组验收"
description: "区分编号等价、物理验收和固定问题性能对照。"
contentStatus: draft
benchmark: "G0 supplemental verification"
sourceReference: "PETSc MatPermute and VecScatter"
eonsimCommit: "codex/fem-time-mesh (implementation checkpoint pending commit)"
---

# 真实装配置换与预条件分组验收

## 验证目标与读者

面向维护分布式 FEM 求解器的开发者：一个分块树的索引测试通过，
还不足以说明实际装配、压力规范、界面力和预条件器选择保持物理结果。
本文是未发布草稿，讨论代码验证，不与实验验证或大规模扩展性混同。

## 参考问题与数学

理论：令 P 为置换矩阵，J 为约束后的实际 Newton 切线，R 为同一点残量。
改变代数坐标应满足 Jp=PJPᵀ、Rp=PR。检验 Jp(Pv)=P(Jv) 后，
再解 Jp z=Rp，并检查 J(Pᵀz)−R；只做 PᵀPR=R 只能验证通信往返。
局部编号、owned所有权、物理字段和PC叶子属于不同概念。

参考算例沿用仓库旋转Couette流和共形双域弹性FSI，Tet4/P1、既有SUPG/PSPG及BE。
配置中的材料、载荷、步长和求解容差保持一致；FSI仍由一个Newton求解并共同接受状态。
旋转流另用全速度边界的压力规范点2 Pa及零均压两个变体，防止压力常数掩盖差异。

## 实现步骤

工作分支`codex/fem-time-mesh`的`src/algebra/nonlinear_system.cpp`提供显式诊断
`-verify_operator_permutation`，默认关闭。反序IS跨rank移动编号，向量使用分布式scatter。
PETSc的VecPermute目前不支持非本地置换，不能直接替代这里的通信。
诊断检查矩阵作用、已知离散解及真实Newton修正；它不改变生产存储，也不重新分区。
直接分解要求小型、可逆的约束切线。PETSc3.19.6的辅助PREONLY失败需共同归约后抛出，
避免某rank提前退出而其他rank进入VecNorm。

`tests/verify_schur.py`将三种recipe分别与直接解比较，验收字段长度、有限值、
边界通量和压力、逐步界面力、位置/速度及动量平衡。
`tests/verify_pc_plan.cpp`另检查奇异辅助求解失败及同对象恢复，包含空owned rank。

## 实际数值证据

本轮获用户明确授权在WSL2运行，并要求云端复验；本机GCC15.3/PETSc3.23.7主锁，
兼容锁PETSc3.19.6，均使用锁定OpenMPI和OpenBLAS。主锁Debug/Release完整43项通过，
新增故障负例随后在Debug及旧锁Release的10项选择中通过。旧锁三recipe补验也通过。
记录见`docs/research/data/fem-integration-2026-10-31/g0-supplement.json`；新提交CI尚待完成。
源码基线47b5bd4已有成功云端CI，不能用该旧CI代替本增量。

## 性能观测

`scripts/benchmark_pc_recipes.py`对两小算例、1/2/4rank、直接解及三个recipe分别预热，
每组重复3次并轮换顺序，共72个测量样本。样本最大场差3.307e-12。
记录setup、solve、迭代和RSS，原始报告及依赖锁在
`docs/research/data/fem-integration-2026-10-31/pc-recipes-benchmark.json`。

该次单节点测量中直接解的solve中位数均较低。例如双域FSI的4rank结果为：
直接解0.037970秒，physics 0.112430秒，quantity 0.083247秒，hybrid 0.114371秒。
这些是多时间步solve时间之和的重复中位数，包含内部阶段；不能把各子计时再加一遍。
此结果没有证明某recipe对大问题更快，也不构成强扩展结论。

## 复现与限制

使用仓库`restore.sh`及`run.sh`的Release all入口，再运行性能脚本并提供该构建的
`--environment-evidence .../evidence/summary.json`。脚本保存完整命令、退出码、
二进制和源码哈希、锁定版本及每步报告。运行环境需保持单rank单BLAS/OpenMP线程。
本地shell原有MKL/PETSc路径会污染间接链接；锁定入口现显式隔离库搜索路径。
所有证据只覆盖小网格和最多4rank，不涉及生产存储重排、G5时间新格式或G1二维单元。

## 参考与进一步练习

- [PETSc MatPermute](https://petsc.org/release/manualpages/Mat/MatPermute/)：新编号到旧编号的映射方向。
- [PETSc VecPermute](https://petsc.org/release/manualpages/Vec/VecPermute/)：非本地置换限制。
- 练习：将反序改为非自逆置换，再核对scatter逆向语义和原方程修正残量。
- 审查问题：诊断的算子可逆性前置条件是否清楚？性能问题规模是否足以触发PC选择？
