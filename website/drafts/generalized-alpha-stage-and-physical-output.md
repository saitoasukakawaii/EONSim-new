---
title: "generalized-alpha 的 stage、算法历史与物理输出"
description: "区分时间评价位置、共享界面速度和各自的算法导数历史。"
contentStatus: draft
benchmark: "Standalone transient fluid and unloaded solid"
sourceReference: "PETSc v3.23.7 alpha1/alpha2; Jansen 2000; Liu 2020"
eonsimCommit: "See alpha-standalone.json source SHA256 manifest (base bab4fda, dirty implementation)"
---

# generalized-alpha 的 stage、算法历史与物理输出

## 问题与实现契约

本记录以数值基准报告模板组织，关注代码验证，不是性能或实验物理验证。
generalized-alpha的名称不能决定参数约定：EONSim使用新时刻权重，
`x_f=(1-af)x_n+af*x_(n+1)`。一阶流体与二阶结构具有共同af，但am和gamma不同。
具体公式、载荷/边界时刻和源码来源见[TIME_INTEGRATION](../../docs/development/TIME_INTEGRATION.md)。

结构以stage速度为未知量时，惯性导数系数与位移链系数不同。
将两者都当成一个“有效dt”会得到错误Jacobian；当前实现显式传递两种系数。
另外，共享界面速度不意味着可以共享一个算法加速度历史，当前单体接入为各物理场分别保存算法历史。

## 算法加速度为什么不是同精度的端点物理加速度

对常步长平滑运动作Taylor展开，若端点速度近似二阶，
`v_(n+1)-v_n=h*((1-gamma)*a_n+gamma*a_(n+1))`中的算法a一般包含
`(1/2-gamma)*h*真实加速度的一阶时间导数`这一偏移。
stage惯性可保持所需精度，但不能把算法a直接命名为经过验证的二阶物理端点加速度。

在当前无外载结构模型中，EONSim最终输出的物理a由`M*a+f_int(d)=0`恢复；
`algorithmic_acceleration`单独输出并用于checkpoint。恢复方程的原始残量同时提供端点反力，
stage动量残量另以明确名称输出。这一恢复依赖当前卸载模型，未来时变载荷须纳入相应端点外力。

## 参考问题、数值设置与误差

沿用[固定空间BDF2报告](bdf2-time-error-and-stabilization.md)的压力驱动流体与卸载线弹性体：
27节点/48Tet4，固定tau流体，Newton rtol1e-11、atol1e-13，直接线性解，PETSc3.23.7 Debug。
误差为节点分量RMS，与同网格细步BDF2生产解比较；另有指数衰减和谐振子解析oracle。
启动接受一个BE步，不声称等同PETSc两次半步探测启动；测试包含rho=0、0.5、1。

实际观测：流体最终速度阶约1.99–2.02，端点压力约1.90–2.26；
早期t=0.02的端点压力也近二阶，覆盖rho=1的无衰减初始误差风险。
结构位移、速度与恢复的物理加速度近二阶；rho=1在BE启动后保持线弹性能量，
同一粗步问题上rho较小有更强阻尼。事件重启、算法历史、真实拒绝与1/2/4rank对照通过。

## 可复现来源与限制

[源码、命令、退出码和结果清单](../../docs/research/data/fem-integration-2026-10-31/alpha-standalone.json)；
CTest：`time_integration`、`fluid_alpha_verification`、`solid_alpha_verification`及相关局部导数/旧BE回归。
独立场检查点主锁 Debug 7 项通过；这些结果不替代单体 FSI 验收。后续 alpha ALE/FSI 已接入并随 PR #23 交付，耦合证据见下节。非线性材料只覆盖方向导数与拒绝恢复，不声称其全部时间阶。

关键原始/官方来源：[Jansen等预印本](https://www.lncc.br/~alm/lncc/jmac/turbulencia/genalf.pdf)§3–4，
[PETSc3.23.7一阶](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ts/impls/implicit/alpha/alpha1.c)、
[二阶](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ts/impls/implicit/alpha/alpha2.c)，
[Liu等压力评价研究](https://arxiv.org/abs/2002.01098)。Chung1993全文本轮未取得，不作已读全文声明。
评审重点：参数约定、阶段与端点输出、启动压力、物理加速度恢复适用范围。本稿保持draft。

## 单体接入与极小步重试

共同af只统一残量评价位置，不能免除完整耦合时间收敛验证。当前生产FSI中，
流体q与结构q不同，界面位移链和网格速度采用二阶运动学系数；
rho=0/0.5/1的刚体及弹性FSI速度、压力、位移实测趋近二阶。
独立域整体J差分误差约1.8e-9，最多4rank，未作更大规模外推。

极小重试步的算法网格加速度包含二次差分。用打印时刻相减重构步长，会把时钟舍入
放大进历史对照；应记录足够精度的实际步长。界面已有独立速度未知量时，
直接使用它比从两次位移相减恢复速度更稳定，精确算术下二者等价。
本轮保留原验收容差并修正上述两点，非线性拒绝后的同轨迹历史对照通过。

ALE端点反转测试在共同stage仍有效时失败；4rank中仅3rank有反转单元，
所有rank共同拒绝并缩步恢复，失败前后checkpoint哈希一致。FSI实现同类检查，
但本轮没有直接触发其独立端点反转分支，不把ALE证据移作该分支执行证据。
详情见 [alpha-coupled.json](../../docs/research/data/fem-integration-2026-10-31/alpha-coupled.json)；此段无性能收益声明，仍为未发布草稿。
