# EONSim 单体流固耦合架构

## 1. 单体法的基本思想

单体 FSI 将流体、结构以及界面约束放入一个联合非线性系统中：

$$
\boldsymbol R(\boldsymbol x)=
\begin{bmatrix}
\boldsymbol R_f(\boldsymbol u,p,\boldsymbol d)\\
\boldsymbol R_s(\boldsymbol d,\boldsymbol u)\\
\boldsymbol R_\Gamma(\boldsymbol u,\boldsymbol d)
\end{bmatrix}
=\boldsymbol 0.
$$

Newton 迭代求解：

$$
\boldsymbol J(\boldsymbol x_k)\Delta\boldsymbol x
=-\boldsymbol R(\boldsymbol x_k).
$$

其中 Jacobian 包含流体、结构和跨场耦合导数。

## 2. 单体与分块预条件不是同一个概念

单体法描述的是非线性问题和未知量的联合求解。FieldSplit 或 Schur 补描述的是线性化系统的预条件策略。

因此，使用块预条件器并不意味着使用分区耦合算法。只要每次 Newton 迭代针对完整联合残量和完整耦合 Jacobian 求解，它仍然是单体方法。

## 3. EONSim 当前实现入口

- [FSI 求解驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fsi.cpp)
- [FSI 单元残量与切线](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fsi_element.cpp)
- [有效自由度布局](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/fem/reduced_layout.cpp)
- [Schur 求解器](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/schur_solver.cpp)
- [单体 FSI 数学契约](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/architecture/L2_MONOLITHIC_FSI.md)

G0/G5 已支持独立的 physics/quantity/hybrid PC 树和 BE、变步 BDF2、共同 stage generalized-alpha；默认存储仍不变。时间映射、算法历史和端点输出的边界见 [时间支持矩阵](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/TIME_INTEGRATION.md)，真实验收最多 4 rank。上述残量矩阵是概念示意；当前 EONSim 显式保留 ALE 内部未知量，接口运动学通过 ReducedLayout 消元，并非另建一组界面乘子方程。

## 4. 阅读时需要区分的状态

- 数学模型：界面运动学、动力学和 ALE 映射的定义。
- 代码实现：当前支持的刚体/弹性、共形双域和有效 DOF 消元路径。
- 数值证据：具体算例、网格、时间步、求解器容差和 MPI rank 对照。

当前共形双域能力不能解释为任意非匹配界面、自动重网格或大规模生产性能保证。
