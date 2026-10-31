---
title: "算法说明：DoF 身份、界面消元与嵌套 FSI 分块编号"
description: "用可手算的代数反例说明 K/W 的区别，以及 root 行号为什么不能直接用于嵌套 FieldSplit。"
contentStatus: draft
algorithm: "固定仿射映射与父块分布式索引"
sourceReferences:
  - "https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/pc/impls/fieldsplit/fieldsplit.c"
  - "https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/fieldsplit/fieldsplit.c"
eonsimCommit: "f44c3e0e81f090637f6f21a7b63a9d12d3e30424"
---

# DoF 身份、界面消元与嵌套 FSI 分块编号

**未发布草稿，待人工审查。** 面向准备接入多物理分块预条件的开发者。
学习目标：识别语义身份与代数存储的区别，手算界面映射的残量/切线，正确生成嵌套子块索引。
完整实施契约以 [FEM-G0A 专题设计](../../docs/architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md) 为唯一来源；本文是算法说明，不是新功能教程。

## 1. 问题与证据等级

| 类别 | 本文依据 | 边界 |
|---|---|---|
| 理论 | 固定仿射映射的链式法则、置换关系、索引前缀和 | 不涉及状态相关约束的完整实现 |
| 当前实现 | 固定 SHA 的 reduced_layout、fsi 与 schur_solver 源码 | 新语义接口和三种可选 recipe 尚未实现 |
| 验证 | 标准库 Python/Fraction 合成代数和分区索引测试 | 不是 MPI/PETSc 执行或 FSI 数值验收 |
| 性能 | 专题给出复杂度与数组容量估算 | 无实测数据，无加速或扩展性结论 |

## 2. 数学定义与关键推导

设 x 为完整物理槽，q 为约束后独立未知量，g 为固定历史/边界 lifting。
一次 Newton 内 K、W、g 固定时：

```text
x = Kq + g
R_reduced(q) = Wᵀ R(Kq+g)
J_reduced = Wᵀ J K
```

K 展开试探量，W 选择并合并测试行，二者职责不同。
当前 BE 弹性 FSI 的结构未知量是速度：`ds=ds_n+dt*vs`；界面 `uf=vs`、`dm=ds`。
因此界面 dm 对 vs 的列系数是 dt，但人工网格方程的界面测试行被丢弃，不应加入结构动量。

一个无量纲合成例的完整槽为 `[uI,uΓ,vs,dmΓ,fixed]`，独立量 `[uI,vs]`，取 dt=2、历史位移 3、固定值 5。
其 K、W 及非对称 5×5 矩阵在专题 §6.1 完整列出，可手算得到：

```text
J_reduced = [[2,6],[3,21]]
R_reduced(q) = [2*q0+6*q1+28, 3*q0+21*q1-12]
q=[1,2] -> R_reduced=[42,33]
```

误用 W=K 会得到 `[42,189]`，因为人工网格行被错误计入。
交换独立坐标 `q=P*y` 时必须同时变换方程行：`R_new=PᵀR_reduced(Py)`、`J_new=PᵀJ_reduced P`；对应 Jacobian 为 `[[21,3],[6,2]]`。
这说明坐标排列与物理残量分组应分开；更换 PC 树不能更换物理验收尺度或 RMS 分母。

## 3. 算法步骤与数据映射

准备时先确定独立代表和 owner，再根据 canonical role 生成 PC 树。共享界面可以有 fluid/solid/mesh 多个标签，但每个独立行只属于一个兄弟块。
保持当前 root 存储，选择 IS 即可改变分组；无需先搬动解向量。

父块 B 的 rank r 保留 root 行列表 `L_B[r]`。其子矩阵的新全局行号为：

```text
offset_B[r] = sum(len(L_B[s]) for s < r)
parent_global(root=L_B[r][k]) = offset_B[r] + k
```

子节点 IS 用上式转换；下一层又要用该子节点自己的长度前缀和。
例如 root 行 `[0,1,2,3,7,8,9,10,11,12,13]` 组成 dynamics，root 8 在 dynamics 中编号 5；
去掉两个压力行后，它在 velocity 中编号 3。
root 7 是压力，在 dynamics 中应为 4；误把 7 传下去仍未越界，却选中了 root 10。
参考测试专门拒绝这种“范围正确、语义错位”的输入。

本地空块保留零长度 IS 并参与同序 collective；ghost 只是数据缓存，不产生额外 owned IS。
全局空块默认报配置错误。每次试步更新 dt/lifting/数值；固定拓扑和约束支撑下不在 Newton 内解析选择器或重建索引。
失败不提交 accepted state。输出使用物理重建映射，不按 PC 叶子解释原始系数。

## 4. EONSim 实现位置

- [reduced_layout.cpp:17–102](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/fem/reduced_layout.cpp#L17-L102)：alias、独立行、唯一刚体 owner 与 owned/ghost。
- [fsi.cpp:90–100](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L90-L100)、[148–173](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/physics/fsi.cpp#L148-L173)：展开、dt 链式系数、测试行舍弃和全局刚体项。
- [schur_solver.cpp:40–70](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/schur_solver.cpp#L40-L70)：现有 flow 子编号用 Exscan 构造；尚不是任意递归树。
- [nonlinear_system.cpp:93–175](https://github.com/saitoasukakawaii/EONSim-new/blob/f44c3e0e81f090637f6f21a7b63a9d12d3e30424/src/algebra/nonlinear_system.cpp#L93-L175)：物理字段验收；未来 PC 分组不能回写这一划分。

调用顺序为 FSI 构造 reduced layout → 试步初始展开/装配和验收尺度初始化 → Schur 配置 → 统一非线性求解及最终物理验收 → 成功后共同提交。
第一实施切片拟引入独立 PC 索引计划，保留现有默认行为；没有改变生产源码。

## 5. 成本与验证

深度 d 的树，筛选/生成索引约 O(d*n_owned)，必要排序另计；ghost 不额外计入 IS。
root provenance 与 parent 索引按层存储，典型为 O(d*n_owned) 整数，PETSc COPY_VALUES 还有自己的副本。
矩阵子块、Schur 和 AMG 成本独立于这些索引估算，不能由索引复杂度推断 time-to-solution。

实际执行：`python3 -B docs/research/fem_g0a/test_reference_model.py`。
[原始结果](../../docs/research/data/fem-g0a-2026-10-30/reference-tests.txt) 与 [参考源码](../../docs/research/fem_g0a/reference_model.py) 可供复查。
1/2/4 个模拟分区仅验证编号规则；Fraction 检查精确关系，预期矩阵/残量/两三层 IS 有独立手写常数。
没有求解器调用、MPI 通信、C++ 构建、FSI 稳定性或性能实测。本次不能改变 INFRA-01 的最终集成验收状态。

## 6. 失效边界与审查问题

K/W/g 若依赖状态，导数包含映射本身的变化；固定公式不能直接用于有限转动或变化的非匹配投影。
当前双域预处理重编 joined ID，分区 fingerprint 含 rank 数；不能将这些标识当作跨任意重导入/分区的永久身份。
真正存储重排会影响 ghost、装配/COO、checkpoint 和输出，必须另作切片；PC IS 重组不会自动完成这些迁移。

人工审查重点：结构速度分类是否贴合每个入口，alias 是否只计一次，父编号是否逐层转换，物理验收是否独立于 PC，证据是否只声称其实际范围。

## 7. 官方依据与练习

官方 API 版本核对见专题 §5.2，逐项链接 PETSc v3.19.6/v3.23.7 的 IS、FieldSplit 和 MatCreateSubMatrix 源码；当前 release 文档仅作导航，不能替代旧版证据。

练习：把专题 14 行示例的第二分区压力 root 7 改写成 dynamics 7，手算它实际指向哪一个结构分量；再将 dt 从 2 改成 1/2，说明哪些数字改变、哪些索引可保留。
