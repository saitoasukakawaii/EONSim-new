---
title: "从 Gmsh 规范化到原生二维混合有限元"
description: "用独立矩阵、patch、空间和时间收敛区分读入成功与求解正确。"
contentStatus: draft
benchmark: "XY scalar Poisson and transient diffusion, Tri3/P1 and Quad4/Q1"
sourceReference: "Gmsh MSH 4.1 specification; MFEM 4.8 BiLinear2DFiniteElement"
eonsimCommit: "G1 source manifest in fem-final.json; base 2fcd2fd with implementation diff"
---

# 从 Gmsh 规范化到原生二维混合有限元

## 验证目标与读者

面向需要从单一 Tet4 求解器扩展到真实多单元路径的开发者。本报告是代码验证，
没有实验数据物理验证或大规模扩展性结论。文章仍为草稿，待人工审查。

## 为什么读取单元不等于实现单元

文件中的 type、external tag、entity 和 physical group 不应直接充当有限元空间或代数编号。
规范化层保留来源身份并将连接转为内部索引，随后再判断模型是否支持。
当前 EONSim 读取 2.2/4.1 ASCII 的一阶子集，明确拒绝高阶、周期、参数化和分区输入；
不是声称实现完整 Gmsh 格式。多 physical groups 在规范化层保留，但当前求解适配器要求单组归属。

Tri3/P1 的几何和梯度是仿射的，Quad4/Q1 则按积分点评价双线性映射和逆 Jacobian。
把四边形拆成两三角形会更换有限元空间，不能作为 Q1 实现。
本实现使用四角 detJ 检查：平面双线性映射的 detJ 是参考坐标的仿射函数，
所以四角正值可约束整个正方形；仅检查中心或 Gauss 点不足以排除角点反转。
该结论不推广到高阶或曲面几何。

共享边上的 P1 和 Q1 迹都是线性的，因此共享两个端点、没有悬挂节点时可以相容耦合。
一个共享顶点保留一个标量 DoF，space=2 标识该 H1 空间；单元类型决定局部基函数。
分区按真实单元连接建立完整 owned 行邻接，不能只收集本 rank 积分单元的局部行贡献。

## 参考问题与设置

单位方形上求解 `c*u_dot-div(k*grad(u))=f`，c=k=1。
仿射 patch 使用 `u=1+x+2y`，混合非零 Dirichlet、Neumann、Robin；
空间加密使用 `u=1+x+2y+x²+2y²`，f=-6，4/8/16格划分并施加内部节点扰动。
边界外向梯度通量定义为 `k*grad(u).n`；物理扩散通量若定义为负梯度，应另取负号。

时间测试采用 `u=(1+x+2y)*exp(-t)`，T=0.2，h=0.05/0.025/0.0125。
该空间场可由 P1/Q1 精确表示，避免空间截断误差掩盖时间阶。
使用 BE、变步 BDF2 和一阶 generalized-alpha（rho=0.5）；
事件处恢复 BE 启动，变步长和重启另行检查。

体积分为每轴四点 Gauss，Tri3 使用 Duffy 映射；边积分为四点 Gauss。
实际PETSc CG/Jacobi求解，rtol=1e-11、atol=1e-12，MPI 1/2/4rank。
畸变 Q1 刚度一般非多项式，固定积分规则的正确性由 patch 和加密验证，不声称解析精确。

## 独立预期结果与实测

单位正方形 Q1 的质量矩阵对角为1/9、相邻为1/18、对角顶点为1/36；
刚度矩阵对应为2/3、-1/6、-1/3。C++ oracle对照这些解析常数，另检查中心有效但角点反转的单元。

畸变混合 patch 的首次实际L2误差约1.4e-13。4→8→16加密的L2阶：
Tri约2.000/1.993，Quad约2.010/2.004，混合约2.004/1.998。
时间测试末次加密BE约0.971、BDF2约2.16、generalized-alpha约2.04；
这些是绝对积分L2误差的比率，不是归一化节点误差。
最终集成数据与命令以[验证记录](../../docs/development/FEM_INTEGRATION_VALIDATION.md)及源码清单为准。

另有不依赖manufactured自动生成器的一般用户问题：分段k=1/2，左右Dirichlet为0/0.75，
上下绝热。解析解在x=0.5连续、斜率从1变为0.5，通量保持1；1/2/4rank实际对照通过。
纯Neumann Poisson拒绝不相容载荷，并使用常数零空间及物理体积零均值。
不连通域被明确拒绝，不能用一个常数模态处理所有分量。

通量诊断独立积分有限元梯度。连续Galerkin梯度不是逐单元守恒通量，
因此非仿射场的边界通量平衡随加密收敛，不要求每个有限网格上机器零。
不能把装配行求和得到的恒等式命名为独立物理守恒检验。

## 失败与输出也属于数值契约

真实KSP失败先在所有rank上统一判断，再决定是否缩步；不能在某rank退出后让其他rank继续规约。
两步checkpoint之后的失败、缩步成功及同轨迹重放对照包括算法历史，失败不会改写accepted检查点。
局部对称质量项只算一次并镜像装配，避免极小步下不同浮点乘法顺序产生可避免的非对称差异；没有放宽容差。

重启不仅要保留原PVD文本，还要保留其引用的数据文件。
新时间轨迹采用独立restart前缀，测试检查原PVD和全部原时间片哈希不变。
只更换PVD文件名、仍覆盖旧stepN.vtu，是索引看似不变而数据已变的错误。

## 可复现路径、限制与进一步检查

源码：`mesh_import.cpp`、`gmsh.cpp`、`partition.cpp`、`element2d.hpp`、`scalar2d.cpp`。
算例生成器及配置见[用户说明](../../docs/development/SCALAR_2D.md)。
测试为element2d_oracles、mesh_import_verification、scalar2d_space/time/failure。
证据区分独立解析oracle、实际PETSc/MPI、源码审查和最终CI；本任务没有二维性能测量。

当前仅常z的XY平面、相容一阶空间、同分区重启；没有二维流体、曲面PDE、任意表达式、
自动悬挂节点修复或完整Gmsh变体。思考题：若域有两个不连通分量，为什么全局源项积分为零
仍不足以保证Neumann相容？若使用高阶几何，四角detJ为正还是否足够？

来源：[Gmsh官方MSH规范与节点顺序](https://gmsh.info/doc/texinfo/gmsh.html#MSH-file-format)，
[MFEM4.8双线性四边形单元](https://docs.mfem.org/4.8/classmfem_1_1BiLinear2DFiniteElement.html)。
它们帮助核对格式与组织；上游能力不替代本项目实际验证。
