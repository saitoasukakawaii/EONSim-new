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
