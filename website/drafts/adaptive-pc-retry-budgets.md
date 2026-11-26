---
title: "EONSim 开发记录：自适应预条件器重试的求解预算"
description: "保持应用级 Newton 和函数评价上限，避免内部 SNESSolve 重启悄悄追加预算。"
contentStatus: draft
taskId: "HPC-06"
pullRequest: "https://github.com/saitoasukakawaii/EONSim-new/pull/56"
baseCommit: "2d0e9b79e90ac0b7332b22e900e50e3306a68a35"
resultCommit: "bce292a1870c38686e44514e2879009ebb9a736a"
date: "2026-11-26"
---

# 自适应预条件器重试的求解预算

## 目标与适用读者

面向维护PETSc非线性求解器与自适应预条件器的开发者：理解一次应用级solve为何可以包含
两次库级SNESSolve，却必须共用同一迭代预算。本文讨论EONSim的NEWTONLS/FGMRES路径，
没有提出新的FSI离散方程或AMG算法。

## 开发前状态

HPC-05已允许旧PC耗尽KSP迭代时，在最后一个已接受Newton状态重建PC并重试一次。旧实现
累计报告两次SNES迭代数，却没有扣除已消耗的上限。若第一次已接受1步、用户总上限为4，
第二次又取得4步，就可能在第5步收敛并返回。这是预算契约漏洞；最终物理残差检查仍然存在。
原线性对角回归在第一轮修正失败，已用Newton步为0，因此无法识别该问题。

## 设计依据：应用预算与库计数

**理论/API。** PETSc的SNESSolve重置函数/线性计数，NEWTONLS重新从迭代0开始。
对有效Newton上限M、已接受步数k，重试额度应为max(0,M-k)；对有限函数评价上限F、
已用SNES评价数n，额度应为max(0,F-n)。负的无限函数上限保持不变。

有效设置必须通过SNESGetTolerances读取，不能只读应用配置，因为PETSc选项可覆盖它。
这不是所有物理组装的硬上限：EONSim已有的显式初始/重试起点及最终验收组装不属于SNES
函数计数。预算恢复与物理接受基线是不同责任，二者都不能因内部重启丢失。

上游依据：[PETSc 3.23 SNES接口](https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/src/snes/interface/snes.c.html)、
[NEWTONLS](https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/src/snes/impls/ls/ls.c.html)、
[默认收敛测试](https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/src/snes/interface/snesut.c.html)。
实际构建使用锁定PETSc3.23.7。

## 实际修改

**实现。** 固定源码为bce292a1870c38686e44514e2879009ebb9a736a。

| 文件 | 改动及目的 |
| --- | --- |
| src/algebra/nonlinear_system.cpp | 读取有效预算、扣除已用计数；重试后检查恢复，异常路径由局部作用域守卫恢复 |
| tests/verify_adaptive_pc.cpp | 真实晚发生的KSP耗尽、两类预算拒绝/成功、选项覆盖与同会话下一次调用 |
| docs/architecture/L2_DISCRETIZATION_AND_OPERATORS.md | 明确应用级预算与SNES函数计数的范围 |

既有一次重试资格、fresh J、USER Schur刷新、字段接受基线和时间历史语义保持。诊断增加
newton_used/newton_remaining以及snes_functions_used/snes_functions_remaining，便于从
原日志判断是否在已接受更新后重试。

## 能发现旧缺陷的回归

**验证设计。** 采用可分C1方程。每行权重d为正整数；x≥1时F=d(x²−2)，x<1时额外加
(6d−2)(x−1)²+(4d−1)(x−1)³。由此F(0)=−1、J(0)=1，第一步所有未知量都到达1；
在x=1时J=2d，各行谱不同，旧单位对角PC在两次Krylov预算内不能收敛。重建对角PC后，只剩
共同的标量Newton轨迹；指定容差下总共需要5次接受更新。

**实际证据。** 固定旧main的求解器重新编译并链接新测试后准确失败。修复后本地五项
Release检查在1/2/4rank通过：总Newton预算4拒绝、5成功；有限函数预算4拒绝；PETSc
选项覆盖配置有效；下一物理context复用同一会话时仍可执行完整5步。4rank含空owner。
源码CI另实际执行17项Release且全部通过。

真实动脉两档网格的direct/aggregate/adaptive共6次短轨迹、24接受步、48线性修正通过。
独立原始日志与owner-VTU重放得到最大真实残差/原门槛0.745355513，最大五场归一化差
4.68297e-13，小于原2e-6门槛。动脉自然重试次数为0，不能把它作为缺陷的自然触发证据。

执行命令、原日志、负对照、源/二进制身份和独立审计均见
[完整验证记录](../../docs/research/data/adaptive-retry-budget-2026-11-26/README.md)。

## 结果、限制与进一步阅读

**性能。** 本轮没有重复性能采样，不对加速比作新结论。此前五条HPC优化的性能/规模证据
保持原范围，不能从这里推导多节点扩展能力。

可复用经验是：故障恢复测试应覆盖失败前已经完成工作这一情形，同时核验恢复后的下一次
调用。可进一步检查自己的库包装层是否在Krylov重启、非线性重试或时间步回退中混淆应用
预算与内部计数；不据此新增无证据的通用重试框架。本文为未发布开发草稿。
