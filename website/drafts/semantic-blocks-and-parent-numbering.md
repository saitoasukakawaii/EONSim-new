---
title: "从语义 DoF 到嵌套 PETSc 子矩阵"
description: "保持物理验收和存储编号不变时的分块接入与错误路径。"
contentStatus: draft
taskId: "FEM-G0B"
baseCommit: "72a335604a50c1ae27516b8bde15e05564b5748b"
resultCommit: ""
date: "2026-10-31"
---

# 从语义 DoF 到嵌套 PETSc 子矩阵

## 研究问题与读者

面向实现分布式多物理场求解器的开发者：同一套未知量如何改变预条件分组，同时保留物理残量验收？为什么一个没有越界的嵌套 IS 仍可能选择错误行？

## 数学理论

每个独立代表只有一个 owned 行；多个界面物理槽可以引用它。固定映射为 `x=Kq+g`、`R=Wᵀr(x)`、`J=WᵀJ_full K`。本项目界面mesh位移列含时间重建系数，而人工mesh测试行不进入结构动量，因此不能假设W=K。

父块在rank r保留的根编号序列为 L_r，父算子全局编号为 `sum_{s<r}|L_s| + local_position`。子IS使用这个编号，而不是根编号。具体手算例、公式与官方版本依据见 [G0A](../../docs/architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)。

## 算法与当前实现

本草稿对应未完成的开发分支增量，提交后补固定引用，不将工作区文件称为已合并能力。

| 源码 | 职责 |
|---|---|
| `include/eonsim/dof_semantics.hpp` | layout内实体身份和物理量，不包含rank或代数行 |
| `src/fem/reduced_layout.cpp` | 唯一独立代表、shared alias和owned语义 |
| `src/algebra/pc_plan.cpp` | 三recipe、递归父编号、IS和子KSP生命周期 |
| `include/eonsim/reduced_layout.hpp` | 仿射试探重建与测试行投影分离 |
| `src/algebra/nonlinear_system.cpp` | PC数据与物理验收字段分开，保留失败分类 |

准备阶段生成owned索引树，各rank按相同顺序进入collective。全局空块拒绝，局部空块保留；每层核对子矩阵ownership与provenance。子KSP指针借用，返回的指针数组由调用者释放；IS使用COPY_VALUES。Newton中只更新算子数值，不重新解析树。

## 实验验证与局限

当前工作区已执行1/2/4 rank子矩阵手写数值oracle；三recipe独立流体、共形弹性FSI、刚体、超弹性与直接解对照；初态、callback拒绝和恢复；27组COO/FSI重启对照。完整集成与旧PETSc新路径仍在验收，最终记录见 [实施证据](../../docs/development/FEM_INTEGRATION_VALIDATION.md)。

quantity首次测试发现原始压力Jpp的AMG粗层失败；改用明确的Jacobi压力块策略后，原算例精度对照通过。它只证明这些小算例可用，不证明压力块一般可逆或该recipe性能更好。Schur压力算子与原始Jpp是不同对象，不能机械复制同一子求解器配置。

## 性能证据

尚无可比较的性能实验。没有从迭代数、单次耗时或小rank正确性推导加速或扩展性。

## 参考文献与进一步核查

- PETSc v3.19.6/v3.23.7 `PCFieldSplitSetIS`、`MatCreateSubMatrix`、`PCFieldSplitGetSubKSP` 的固定tag链接见G0A §5.2。
- [PETSc v3.23.7 FieldSplit源码](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c)：inner/upper采用实际第二孩子命名前缀；任意该前缀选项都可能创建独立求解器。

进一步阅读练习：把root 7误写成dynamics 7，检查它为何仍在范围内而矩阵值错误。审核问题：固定recipe的options边界、零初态输入检查、临界或奇异块下的失败原因是否可辨认？
