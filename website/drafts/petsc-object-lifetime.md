---
title: PETSc 对象持久化之前应先审计什么
contentStatus: draft
sourceCommit: "0828f41b62391239b14a05e57a161defae1c8866"
---

# PETSc 对象持久化之前应先审计什么

## 更新：缓存存活不等于缓存仍然合算

d844e40后的[S96启动对照](../../docs/research/data/rounder-mesh-startup-screen-2026-11-08/README.md)
把实际LU分解从4次降到1次，却把32步总耗时从95.526秒增到127.681秒。首步BE因子
进入BDF2后对应的有效时间系数已改变，后续需要11–12次线性迭代。FGMRES和当前
真残量仍通过，640个完整HDF数据集也相符，所以这是预条件质量/成本问题，不能把它
描述为接受场错误，也不能凭“少分解”宣称优化成功。

[本次修正](../../docs/research/data/lu-time-coefficient-refresh-2026-11-08/README.md)让流体
驱动在有效积分时间改变时显式请求刷新；代数层把任一rank请求纳入既有集体缓存决策。
空owner也能使所有rank一致重建。缓存失效先销毁旧因子，再分配新因子；其余默认策略、
当前算子及接受规则不变。该时间系数只辅助执行策略，不能混入物理checkpoint历史。
Exact比较是保守失效，包括事件及末步截短；不承诺每种时间序列都只分解两次。

Debug/Release各6项和每配置1005个完整数据集通过，最大差1.46506e-14，v4时钟exact。
实际事件覆盖常步启动2次、变步6次、事件4次和generalized-alpha启动2次。
[独立成本复核](../../docs/research/data/lu-refresh-startup-cost-2026-11-08/README.md)另读2560
数据集：新32耗时57.494秒，对原8前后103.181/87.337秒均达10%收益；新8对后者仅
5.70%而不采用。默认不启用缓存时实际是PREONLY，检查脚本误要求FGMRES的失败也
保留，修正检查后复核已有输出再继续剩余模式。对象生命周期、算子正确性、实际分解
事件和端到端成本是四种不同证据。原长程冻结程序不因当前源码改动而自动更新。

## 更新：中层也检查原连续轨迹

2367903后的[中层筛查](../../docs/research/data/womersley-middle-lu8-2026-11-08/README.md)
在同480种子下额外保留原连续481–488，防止只比较两个重启分支而漏掉共同偏差。
连续原轨迹与新缓存完整历史最大4.60101e-12；新默认与新缓存4.85723e-17，v4时钟exact。
四rank共享WSL CPU21/idle-yield时，旧vector、新默认MUMPS、新缓存八步分别500.678、
101.536、45.120秒；MUMPS实际分解8/1。它是另一规模与资源安排下的局部验证，
不与细网格耗时拼接为扩展性曲线。独立审查后另行从480采用，长程资格仍待完成。

## 更新：细网格实际分解与完整成本

2026-11-08，e435524实现的[完整细筛查](../../docs/research/data/womersley-fine-lu-screen-2026-11-08/README.md)
已完成。相同600种子、四rank/WSL guest CPU0–7，旧默认/新默认/新缓存八步实际分解8/8/1。
同一新版程序默认474.624秒，窗口8为116.530秒，本次局部成本减少75.4479%；其他项目任务
并发运行，没有宿主绑核或扩展性结论。三角求解次数16增至23，说明减少分解并不消除
预条件器作用成本。完整160个HDF数据集最大差1.03433e-16，v4时钟/时间元数据精确。
这组证据同时检查数值状态、真实PETSc事件和端到端成本，再做独立采用审查。长期周期
及误差预算仍未完成；下文较早“细筛查尚未执行”保留其历史时间范围。

## 运行资源也有生命周期

2026-11-08，e435524后的[126份控制前置证据](../../docs/research/data/lu-cache-screen-startup-2026-11-08/README.md)
验证了另一个边界：暂停大MUMPS的数值进程不会释放其因子。若要安全比较另一个大
分解，应让现有数值段自然完成，只暂停等待中的研究driver以阻止下一段自动启动。
独立真实进程fixture确认child可正常结束、parent随后可恢复；实际四rank小算例确认
日志中的分解计数8/1。细网格对照此时仍在等待，不作速度结论。

恢复责任覆盖整个窗口：原controller继续持有资源锁，新试验只借用它保留的空闲
计算段；每个新作业另有整cgroup内存/超时界限。必须确认新scope已空，才能恢复原
driver；异常清理失败时不能恢复出第二个大分解。这是本次执行策略，不能从fixture
成功推断长程物理资格。

## 后续实现：保留引用仍会失去数值因子

2026-11-08，在d0f9bb3基线上实现默认关闭的MUMPS LU预条件器窗口；
[2859份证据](../../docs/research/data/lu-preconditioner-reuse-2026-11-08/README.md)
记录精确补丁源哈希、两次失败及最终检查。下文原2026-10-30只读审计结论保留其时间范围。

**理论边界**：相邻时间步可以尝试用旧分解预条件当前线性系统，但必须仍由Krylov
迭代求解当前算子，并重新评价当前非线性残量。旧LU上的PREONLY不能完成这一契约。
这里使用FGMRES，保持原字段接受准则；因子不是accepted物理历史，不进入checkpoint。

**实际错误**：首次只给PC增加PETSc引用，所有小流体最终场仍相符，却没有减少跨步
分解。独立的`MatLUFactorNum`事件计数在1/2/4rank均失败。固定3.23.7源码显示
[SNESDestroy先调用SNESReset](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/snes/interface/snes.c)，
它进而调用KSPReset与PCReset；这条reset路径不受额外引用计数保护。
[KSPDestroy对共享PC的保护](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ksp/ksp/interface/itfunc.c)
无法撤销之前发生的reset。

**修正**：只有完整验收成功才保存因子；先保有PC引用、从旧KSP解绑、清除
[DM和应用上下文关联](https://raw.githubusercontent.com/petsc/petsc/v3.23.7/src/ksp/pc/interface/pcset.c)，
再提交缓存。否则每次异常都销毁本次尝试持有的缓存。还需显式设置SNES的预条件器
lag策略，因为Jacobian评价会覆盖单独设置的reuse开关。失效的旧因子在新分解之前
销毁，避免两个大因子同时占用内存。每次新的SNES/KSP仍只借用当次回调。

**验证与限制**：改变算子的AIJ/COO测试给出窗口3对应的实际分解次数1/0/0/1，
并覆盖空owner、单rank选项变化、失败后恢复。Debug10项及明确来源的Release10项
通过；每种build的455个HDF数据集最大差1.0402e-12，时钟精确。第二次尝试因测试
目录混入旧检查点而在独立历史审计中断，改用每次独立目录并保留旧数据。真实研究入口
1/2rank的13态也通过。共享CPU上的这些运行只验证正确性；细网格实际成本与长期
物理资格尚未验证，不能从分解次数减少直接推出总体加速。

## 研究问题与学习目标

区分存储复用和预条件器复用，避免仅凭重复创建就决定重构。适用于当前 EONSim 小型 assembled CPU/MPI 求解流程。

## 数学与算法（理论）

Newton 步解当前 Jacobian 对应的线性方程。固定非零模式不等于 Jacobian 数值不变；时间步与几何变化后仍需计算当前数值。本文不改变现有离散与接受契约。

## 代码实现证据

[NonlinearSystem](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/algebra/nonlinear_system.cpp#L328) 的主 Vec/Mat 跨步保留；[流体驱动](https://github.com/saitoasukakawaii/EONSim-new/blob/0828f41b62391239b14a05e57a161defae1c8866/src/physics/fluid.cpp#L64) 在循环外构造 system，而 solve 内重新建立 SNES。Context 引用每步数据，不能只把 SNES 提升为成员就认为生命周期安全。

## 验证证据

本次执行源码调用链审计。数值回归未运行，完整所有权表见仓库 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md。没有新的数值正确性结论。

## 性能证据

本次未测性能。setup_seconds 不包含 system 构造，finalize_seconds 不包含返回时 SNES 析构；嵌套计时与各 rank 最大值不能直接相加。后续 [多步 setup 测量](multistep-setup-profile.md) 已完成，并继续暂缓持久化原型；本次源码审计本身不提供性能证据。

## 局限与参考资料

不覆盖多节点扩展、GPU 或持久化实现。源码提交已固定；理论接口参考 [PETSc SNES](https://petsc.org/release/manual/snes/) 和 [PCFieldSplitSetIS](https://petsc.org/release/manualpages/PC/PCFieldSplitSetIS/)。待审核问题：重绑上下文策略、PC 更新条件、构造/析构计时覆盖。本文保持草稿，未授权发布。
