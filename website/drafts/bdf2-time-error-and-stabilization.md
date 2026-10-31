---
title: "BDF2 时间阶验证：先固定空间离散"
description: "真实 PETSc 求解中，步长相关稳定化、启动历史和结构高频模态如何影响时间阶。"
contentStatus: draft
benchmark: "Standalone fluid and unloaded linear solid"
sourceReference: "Variable-step quadratic differentiation; EONSim production kernels"
eonsimCommit: "See bdf-standalone.json source SHA256 manifest (base e9e4d30, dirty implementation)"
---

# BDF2 时间阶验证：先固定空间离散

## 验证目标与问题

本草稿记录代码验证，不是实验物理验证，也不是性能报告。理论部分来自对不等距三点
二次插值的求导：若r=h/k，时间导数可写成`(y-new_reference)/q`，
其中`q=h(1+r)/(1+2r)`，`new_reference=y_n+r²/(1+2r)*(y_n-y_(n-1))`。
这种写法可复用现有惯性kernel，但结构位移重建也必须使用q，不能只替换加速度。

实现为`time_integration.hpp`中的具体系数与二层历史类型；首次启动用BE，
历史仅在接受后更新。时间控制器负责候选步长、终止与事件，不拥有物理历史。
实现来源以[源码哈希及运行证据](../../docs/research/data/fem-integration-2026-10-31/bdf-standalone.json)为准。

## 数值设置与误差

两问题使用单位立方体、2×2×2细分后的48个Tet4、27节点、P1空间。
流体密度10、黏度1，x端面压力1和0，y端面无滑移，z端面约束法向速度；初始静止。
SUPG/PSPG固定tau=0.05；最终时刻0.2，h=0.02、0.01、0.005；
同网格BDF2参考步长0.000625。自然压力边界确定压力基准，不做事后平移对齐。

固体E=100、nu=0.3、密度1，先施加x端单位牵引获得静态初态，然后卸载振动；
坐标零端面分别约束对应分量，初速度零。最终时刻0.1，
h=0.00125、0.000625、0.0003125；参考步长0.0000390625。
报告节点分量平方差之和除节点数的平方根，不称为积分L2范数。
使用相同空间离散的细步生产解隔离时间误差，不宣称消除了相对连续PDE的空间误差。

Newton rtol=1e-11、atol=1e-13，默认直接线性解。主锁PETSc3.23.7 Debug，
本次授权WSL2，MPI最多4rank，每rank BLAS/OpenMP单线程。没有性能测量结论。

## 结果及根因

| 问题/方法 | 变量 | 两次观测阶 |
|---|---|---|
| 流体BE | 速度 / 压力 | 0.995、0.998 / 1.067、1.038 |
| 流体BDF2 | 速度 / 压力 | 2.006、2.019 / 2.260、2.125 |
| 固体BDF2 | 位移 / 速度 | 1.989、2.014 / 1.990、2.015 |
| 固体BDF2 | 加速度 | 1.952、2.000 |

最初流体测试保留步长相关tau，BE速度观测阶只有约0.59。
这不是更改导数公式就能解决的问题：P1离散强残量一般不为零，改变tau就改变了
离散方程。固定tau后才得到上述纯时间阶；原默认BE配置仍保留旧tau估计。
固定值不是跨网格与跨物理问题的推荐常数。

结构粗步长尚未进入高频模态的渐近区。保持物理问题和验收门槛不变继续细化后，
BE阶趋向1、BDF2趋向2。BDF2最细步最终能量0.0049993968，初态0.005；
细步参考约0.0049999909。BE的逐步物理能量单调性不能直接当作BDF2验收定理。

## 复现及边界

CTest `time_integration`、`fluid_time_verification`、`solid_time_verification`：
解析多项式/指数oracle与真实生产求解分别提供证据，不互相替代。
真实Newton拒绝后对照相同accepted步长轨迹；事件处重启后BE启动；最后短步；
变步长1/2/4rank与同分区重启均通过。相关默认BE与局部导数回归也通过。

后续同分支增量已补ALE与单体FSI BDF2，来源为[bdf-coupled.json](../../docs/research/data/fem-integration-2026-10-31/bdf-coupled.json)：
弹性FSI压力阶1.86/1.97，刚体2.00/2.02，ALE解析网格速度2.02/2.01；最多4rank。
接口功率平衡来自共享速度与两侧离散残量内积，不是总能量时间积分守恒。
本报告未证明非线性结构时间阶或真实跳跃载荷事件；generalized-alpha 后续实现与证据见 [stage 草稿](generalized-alpha-stage-and-physical-output.md)。
G5 已随 PR #23 交付，见 [集成验收](../../docs/development/FEM_INTEGRATION_VALIDATION.md)。评审重点是稳定化对时间阶的限定、历史提交和恢复完整性；
本稿保持draft，不发布。
