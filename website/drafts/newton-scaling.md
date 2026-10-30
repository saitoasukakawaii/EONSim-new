---
title: "算法说明：验收尺度与 Newton 坐标缩放"
description: "从现有 EONSim 字段验收出发，区分方程变换、线搜索和物理结果验证。"
contentStatus: draft
algorithm: "fixed diagonal Newton scaling (proposal)"
eonsimCommit: "717b25b5abb4d62e4c219c1b751fd0b9676d9352"
---

# 算法说明：验收尺度与 Newton 坐标缩放

## 研究问题

面向已经了解 Newton 法和 PETSc 的读者：在残量验收时除以特征尺度，是否意味着线性方程与线搜索也完成了无量纲化？EONSim 当前实现中的答案是否定的。

## 理论：变量与方程必须一起变换

对已处理约束的物理方程 F(x)=0，选取单次求解内固定的正对角尺度 Sx、Sr。

```text
x=Sx y
Fhat(y)=Sr^-1 F(Sx y)
Jhat=Sr^-1 J Sx
Δx=Sx Δy
```

这来自链式法则。精确 Newton 增量映射相同，但加权残量 merit 与未加权 merit 不同，线搜索步长可能改变。
Dirichlet 行 x_i-g_i 在变换后对角为 s_i/r_i，不应无条件覆盖为 1。
完整数学定义、单位、Schur 推导和候选接线要求统一见 [研发规格](../../docs/research/NEWTON_SCALING_SPEC_2026-10-30.md)，本文不复制完整契约。

## 算法与并行映射（候选，未实现）

初始化固定尺度与物理验收阈值；每次从 y 恢复物理 trial，组装并施加约束后缩放残量/Jacobian，再由 SNES 求步长。
物理验收和原始反力保留独立的物理坐标缓冲区，接受之后才提交历史。
owned/ghost 和 field IS 不变；尺度和 scratch 使用分布式局部存储，不收集全局场。

## 实现证据

[基线 nonlinear_system.cpp](https://github.com/saitoasukakawaii/EONSim-new/blob/717b25b5abb4d62e4c219c1b751fd0b9676d9352/src/algebra/nonlinear_system.cpp) 中，`FieldAcceptance::measure` 使用尺度检查字段；`Context::evaluate` 将物理方程传给 PETSc。
`NonlinearSystem::solve` 在最终验收后重新组装原始反力。这些均已存在；完整坐标缩放尚未实现，也没有新增 YAML 开关。

## 数值验证证据

[精确代数脚本](https://github.com/saitoasukakawaii/EONSim-new/blob/6dc2baff56435a86efd051cb3c87571ec31ae7c7/scripts/verify_newton_scaling.py) 使用 Fraction 检查小型二次系统的增量与 Jv、非零约束、试探点、加权 merit、逆预条件作用及 Schur 恒等式。

```sh
python3 scripts/verify_newton_scaling.py
```

已执行并通过两组尺度和两种错误公式的负对照。精确算术消除了该验证中的舍入误差；它不是 PETSc 数值收敛或 MPI 证据。EONSim 浮点、1/2 rank、回滚及物理算例验证仍属未来实现验收。

## 性能证据与局限

本轮无性能测量。理论上增加局部向量存储与矩阵缩放工作，不能据此宣称条件数、迭代数或总耗时改善。
候选方案限定固定正对角尺度；不覆盖随 trial 改变的尺度、所有 SNES 类型、自动单位推理或大规模 HPC。

## 审核与进一步学习

请核对独立未知量尺度的配置语义，以及缩放后 SNES 容差和物理验收之间的关系。
练习：用规格中的两块矩阵推导缩放后 Schur 补，解释为什么 GAMG 重新建立层级不保证原迭代轨迹不变。

## 参考资料

- [PETSc SNES manual](https://petsc.org/release/manual/snes/)
- [PETSc MatDiagonalScale](https://petsc.org/release/manualpages/Mat/MatDiagonalScale/)
- [PETSc PCFIELDSPLIT](https://petsc.org/release/manualpages/PC/PCFIELDSPLIT/)

本文为公开草稿，未发布。
