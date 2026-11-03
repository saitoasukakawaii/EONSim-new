---
title: "P2 瞬态扩散：一致质量、时间层和完整历史"
description: "将共享边空间接入三种时间格式，并验证恢复与失败不污染历史。"
contentStatus: draft
algorithm: "P2 diffusion with BE, variable-step BDF2 and first-order generalized-alpha"
taskId: "FEM-G2C"
eonsimCommit: "d19a03268577b33ddfb41177037d9bbc1f76d273"
---

# P2 瞬态扩散：一致质量、时间层和完整历史

面向已理解 P1/P2 装配和隐式时间推进的开发者。本草稿未经审核、未发布。
学习目标是区分几何节点与场自由度、端点与 stage、算法历史与物理解，以及数值拒绝与 I/O 失败。

## 1. 方程与适用范围

**理论：** 在固定平面域求解 `c du/dt - div(k grad(u)) = f`，c、k 为正的统一常数。
几何是直边 Tri3，场是六节点二次 Lagrange；边界使用 D/N/正系数 Robin。
本增量不包括曲边、分区迁移、多材料、高阶流体或大规模性能验证。

**实现：** `src/physics/scalar_p2.cpp` 保留原实体空间和局部积分规则，复用
`TimeHistory`、`AlphaStep`、`TimeStepper` 和 `LinearSystem`。空间身份由原始端点 ID 对定义，
不以中点坐标替代实体身份；背景见 [P2 稳态草稿](p2-edge-space-poisson.md)。

## 2. 为什么必须使用一致质量矩阵

参考重心坐标 λᵢ 下，顶点函数是 λᵢ(2λᵢ−1)，边函数是 4λᵢλⱼ。
面积 A 的仿射三角形满足

`∫ λ₀ᵃ λ₁ᵇ λ₂ᶜ dΩ = 2 A a! b! c! / (a+b+c+2)!`。

因此顶点函数积分为零，边函数积分为 A/3。对一致质量矩阵
`Mᵢⱼ = ∫ c Nᵢ Nⱼ dΩ` 按行求和得到 `∫ c Nᵢ dΩ`；直接行和集总会使顶点质量为零。
这并不说明一致质量矩阵奇异：对任何非零有限元函数 v，`vᵀ M v = ∫ c v² > 0`。

**验证：** `tests/verify_tri_p2.cpp` 用独立整数矩阵除以 360 对照参考面积 1/2 的每个质量项，
同时检查既有刚度/载荷和六个二次单项式重现。没有以实现自己的同一积分结果当 oracle。

## 3. 统一时间方程与边界时刻

以 q 表示时间映射的有效步长，以 r 表示由 accepted 历史计算的参考场，离散方程为

`(M/q + K + B_R) y = F(t_eval) + M r/q`。

BE 取 q=h、r=u_n。变步 BDF2 令实际步长比 η=h/h_previous，
`q=h(1+η)/(1+2η)`，`r=u_n+η²/(1+2η)(u_n-u_previous)`；无有效历史时用 BE。
当前控制器限制增长比不超过 2，事件命中后重置有效历史。

一阶 generalized-alpha 的 y 是 stage 场，使用项目已有 `AlphaStep` 计算 q 和 r。
源项和自然边界在 `t_n+alpha_f h` 评价；Dirichlet 施加
`y_D=(1-alpha_f)u_n+alpha_f*g(t_n+h)`，再恢复端点 u_(n+1)。
将 `g(t_eval)` 直接当作 stage 约束，对一般非线性时间函数不能保证端点边界正确。
具体参数和算法导数定义以 [时间契约](../../docs/development/TIME_INTEGRATION.md) 为准。
首次和事件后接受一个 BE 启动步；本实现没有改写已有积分器。

瞬态全 Neumann 问题的质量项约束常数模态，应保留物理均值；只有稳态纯 Neumann 才应用
相容性检查、常数零空间和 FE 体积零均值。不能把稳态的均值归一化套到热量随源项增长的瞬态问题。

## 4. 历史提交与分布式恢复

每次候选步从 accepted 状态构造参考场；局部贡献先评价并汇总错误，再进入 PETSc 插入和求解。
求解失败时，仅 `LinearSolveFailure` 交给已有控制器做有限缩步；输入和 I/O 异常终止。
成功后才提交 accepted、BDF2 前一状态/实际步长、alpha 算法导数/ready，以及物理时钟。

**实现：** checkpoint 沿用 v3 generation 发布。几何签名不足以描述 P2 场的数组顺序，
因此额外散列 P2 实体 ID、语义 ID、代数编号、owner、连接和边界标签。整数按原始类型散列，
不转成 double；超过 2^53 的相邻整数不能靠 double 表示区分。
局部恢复异常在共同阶段汇总，随后校验跨 rank 时钟及历史标志一致；不收集全局场。

BDF2 恢复需要 previous 和 previous_dt；alpha 需要 rate 和 ready。
checkpoint、输出中 `algorithmic_rate` 是算法历史，不宣称为精确瞬时导数。
仅保证同分区、同 rank、相容参数恢复。签名不是恶意篡改防护协议，也不提供跨机器格式迁移保证。

## 5. 输出发布与故障边界

每个 rank 写二次三角形分片，关闭并重命名成功后参与错误规约；所有分片成功后发布 PVTU，
最后发布 PVD。索引路径进行 XML 属性转义。失败时可能留下分片/临时文件，但不新增全局索引。
这个顺序不意味着整个输出目录具备事务回滚。

恢复输出采用 `_restartK` 前缀，原时间序列和原时间片不覆盖。重复从同一个 K 恢复到同一前缀
会替换该恢复分支；需要保存多条轨迹时使用不同输出前缀。PVD 只记录当前运行接受并完成输出的步。

## 6. 实际证据

源码提交：`d19a03268577b33ddfb41177037d9bbc1f76d273`。主要入口为 `solve_scalar_p2`，测试为
`tests/verify_scalar_p2_time.py` 的 time/restart/failure 三组。

- 本地 PETSc 3.23.7、单 rank 单线程、真实 1/2 rank；Debug 分项和 Release 五项相关 CTest 通过。
- 可精确表示的二次空间多项式乘 exp(-t)，避免空间误差掩盖时间阶；最细级 BE 0.988、BDF2 2.157，alpha rho=0/0.5/1 分别 2.157/2.006/1.997。交替步长 BDF2 也通过二阶门槛。
- 检查时变 Dirichlet 的端点值、显式用户 D/N/Robin 与制造解路径对照；绝热 c=2、u(0)=2、f=1 的积分在 t=.32 达到 2.16。
- 事件处和有效历史中的 checkpoint 与连续运行对照通过；1/2 rank 使用实体身份比较，包含乱序网格输入。
- 真实 KSP 迭代预算触发缩步，重新运行相同实际步长的轨迹与恢复结果一致。重试耗尽保持 checkpoint 和既有输出；双 rank 分片故障不会发布索引。
- 系统 h5py 3.14.0 本地补验 8/8：缺失 previous/rate、非法历史标志、非有限状态及变更 P2 边语义身份全部拒绝。h5py 未成为日常构建依赖。

实际命令、原始 dirty 标志、提交对应关系和数值结果见
[证据目录入口](../../docs/research/data/p2-transient-2026-11-03/source.json)。Release 可复现入口：

```sh
bash scripts/cloud/run.sh 3.23.7 release explicit .cloud docs/research/data/p2-transient-2026-11-03/release-plan.json
```

首次 time 测试误向 BE/BDF2 传入 rho_infinity，配置被正确拒绝；修正测试配置后通过。
未放宽误差门槛、延长失败超时或减小 MPI rank 来掩盖问题。初次沙箱 socket 拒绝按权限流程处理。
未运行全量、旧 PETSc、超过 2 rank 的本轮验证；无性能证据，不据这些小算例宣称可扩展性。

## 7. 成本、限制和进一步练习

局部贡献缓冲随本 rank 单元数线性增长；它使局部数据错误在插入前传播，但本任务没有测量其性能代价。
P2 目前未实现独立边界梯度通量日志，质量增长验收不能替代任意场的局部通量守恒证明。

进一步练习：由重心坐标积分独立推导矩阵某一顶点行；比较节点均值与 FE 体积均值；
将时间测试的空间场改为正弦，观察空间误差平台如何污染时间阶判断。

## 8. 来源与审阅问题

公式来源为本页重心坐标积分推导，以及已有
[时间契约](../../docs/development/TIME_INTEGRATION.md) 中固定版本的一阶 generalized-alpha 来源；
实现与局限见 [二维标量指南](../../docs/development/SCALAR_2D.md)。
审阅重点是 stage/端点边界、accepted 提交点、P2 签名覆盖和真实失败证据；本页尚未作为正式知识发布。
