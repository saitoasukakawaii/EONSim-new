# CFD 求解器学习路径

## 学习目标

理解不可压缩 Navier–Stokes 方程如何经过空间和时间离散，最终转化为可由 PETSc 求解的代数系统。

## 学习顺序

1. 连续介质与流体运动学：速度、压力、应变率和应力。
2. 控制方程：质量守恒和动量守恒。
3. 边界条件：速度、牵引、压力和周期边界。
4. 弱形式：试验函数、分部积分和边界通量。
5. 空间离散：有限元空间、单元积分和稳定化。
6. 时间离散：Backward Euler、BDF 和 generalized-alpha 的适用范围。
7. 非线性求解：Picard、Newton、残量和一致 Jacobian。
8. 线性求解：Krylov、预条件和速度—压力 Schur 补。
9. 验证：Poiseuille、Womersley、Kovasznay、Taylor–Green 和制造解。

## 不可压缩 Navier–Stokes 方程

对常密度牛顿流体：

$$
\rho\left(\frac{\partial \boldsymbol u}{\partial t}
+ (\boldsymbol u\cdot\nabla)\boldsymbol u\right)
-\nabla\cdot\boldsymbol\sigma=\boldsymbol f,
\qquad \nabla\cdot\boldsymbol u=0.
$$

其中

$$
\boldsymbol\sigma=-p\boldsymbol I+2\mu\boldsymbol\varepsilon(\boldsymbol u),
\qquad
\boldsymbol\varepsilon(\boldsymbol u)=\frac12(\nabla\boldsymbol u+\nabla\boldsymbol u^T).
$$

## EONSim 对应代码

- [流体单元核](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fluid_element.cpp)
- [流体求解驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fluid.cpp)
- [流体边界条件](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/physics/fluid_boundary.cpp)
- [非线性系统](https://github.com/saitoasukakawaii/EONSim-new/blob/main/src/algebra/nonlinear_system.cpp)

## 练习

1. 推导黏性项分部积分后的边界牵引项。
2. 解释等阶 P1/P1 离散为什么需要稳定化。
3. 对比 Newton 与 Picard 线性化的差别。
4. 说明压力 Schur 补为什么不能简单等同于压力质量矩阵。

> 本页是学习路线。具体离散形式、稳定化参数和适用范围应以对应 EONSim 数学契约及代码版本为准。
