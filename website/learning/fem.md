# 有限元与固体力学学习路径

## 从连续问题到离散系统

有限元方法的核心过程是：定义控制方程和本构关系；选择试验空间与试探空间；建立弱形式；划分计算域；使用形函数插值；通过数值积分形成单元残量和切线；映射局部自由度到全局代数系统；施加约束并求解。

## 线弹性例子

小变形线弹性满足：

$$
\nabla\cdot\boldsymbol\sigma+\boldsymbol b=\boldsymbol 0,
\qquad
\boldsymbol\sigma=\mathsf C:\boldsymbol\varepsilon(\boldsymbol u).
$$

其中

$$
\boldsymbol\varepsilon(\boldsymbol u)
=\frac12(\nabla\boldsymbol u+\nabla\boldsymbol u^T).
$$

测试函数为 \(\boldsymbol v\)，忽略体力时的典型弱形式为：

$$
\int_\Omega
\boldsymbol\varepsilon(\boldsymbol v):
\mathsf C:
\boldsymbol\varepsilon(\boldsymbol u)\,d\Omega
=
\int_{\Gamma_t}\boldsymbol v\cdot\bar{\boldsymbol t}\,d\Gamma.
$$

## EONSim 对应代码

- [Tet4 离散定义](https://github.com/saitoasukakawaii/EONSim-new/blob/main/include/eonsim/tet4.hpp)
- [单元几何与积分](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/tet4.cpp)
- [固体单元核](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/solid_element.cpp)
- [超弹性材料](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/hyperelastic.cpp)

## 练习

- 手工推导一个线性四面体的应变—位移矩阵。
- 比较单元刚度矩阵和全局稀疏矩阵。
- 用有限差分方向导数检查单元 Jacobian。
- 解释近不可压缩材料为什么可能产生体积锁死。

## EONSim 当前实现：P2 标量空间

EONSim 除了三维 Tet4/P1 多物理场路径，还实现了一个二维标量有限元闭环：几何仍为直边 Tri3，标量场可采用六节点二次 Lagrange P2 空间。新增的边中点是场自由度，不是曲边几何节点；边实体身份由原始端点 ID 对确定，不能用浮点坐标相等来合并实体。

目前已合入的 P2 功能包括：

- 稳态 Poisson 的 Dirichlet/Neumann 边界与共享边自由度分区。
- Robin 边界及纯 Neumann 问题的相容性、常数零空间和有限元体积均值处理。
- 瞬态扩散的一致质量矩阵、Backward Euler、变步 BDF2 和一阶 generalized-alpha。
- P2 场身份签名、同分区完整历史恢复、接受步输出与失败路径检查。

实现范围、边界符号和可复现命令见 [SCALAR_2D 实施说明](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/SCALAR_2D.md)。相关 PR #27/#28/#29 的 PETSc 3.23.7 云端 Debug/Release 选测分别为 19/19、10/10、15/15；这些不是全量测试或性能基准。P2 文章仍处于人工审核草稿状态。