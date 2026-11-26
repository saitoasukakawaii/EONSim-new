# EONSim-new 当前实现、验证与开发边界

核对日期：2026-11-26。固定主线：[3472a18（PR #59 合并）](https://github.com/saitoasukakawaii/EONSim-new/commit/3472a18a5c7ad112084ec551a28a11d84bd3c4e7)。本页是活跃状态入口；历史设计、实验记录、开发日志和网站草稿保留其原始日期、源码及测量语义，不代表当前默认设置。

## 能力矩阵

| 方向 | 当前已合入的实现 | 证据与限制 |
|---|---|---|
| FEM / 时间 | 三维 Tet4 多物理；二维 Tri3/P1、Quad4/Q1、直边 Tri3/P2 标量 Poisson/扩散，含 D/N/Robin 与纯 Neumann；适用 BE、变步 BDF2、generalized-alpha | [二维标量](SCALAR_2D.md)、[时间契约](TIME_INTEGRATION.md)；P2 不等于三维高阶 FSI 或一般混合空间 |
| 单体 FSI | 共形双域、ALE、刚体单轴及弹性体、Neo-Hookean、参考法向组织支撑、压力/流量入口、固定及受限平面移动 RCR 端口、同分区重启 | [生产里程碑](FSI_PRODUCTION_ROADMAP.md)；合成管道及分叉，不等于患者特异性/高 Re/预应力资格认证 |
| 稀疏装配 | 固定 reduced AIJ 图、物理块预分配、默认固定残量 COO、可选 FSI Jacobian COO，独立 test/trial 投影与贡献映射 | [#51](https://github.com/saitoasukakawaii/EONSim-new/pull/51)、[#52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)；assembled CPU 路径，不是 matrix-free |
| 单元与运行 | 24 lane 速度/ALE AD + 4 精确压力列，紧凑 AIJ、有界线程批次、参考核/初始切线与合资格 SNES/KSP/PC 会话复用，鲜残量验收 | [#52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)、[#53](https://github.com/saitoasukakawaii/EONSim-new/pull/53)；跨 solve 数值 PC 默认刷新，非所有配置均可复用 |
| FSI Block PC | 语义 physics/quantity/hybrid/added_mass；联合速度 coupled、twolevel、scalar GAMG、aggregate、hypre BoomerAMG、递归 field_amg；完整约束后块的压力 nodal、LSC/BFBt、物理 ALE PCD | [分块 PC](FSI_BLOCK_PRECONDITIONER.md)、[高级 PC](FSI_ADVANCED_PRECONDITIONERS.md)；新方案显式选择，并非全部组合可用 |
| 界面及精度 | 真实界面 mixed Vanka/patch，跨 owner overlap、重叠权重；局部 FP32 LU，FP64 残量细化及 FP64 回退 | [#59](https://github.com/saitoasukakawaii/EONSim-new/pull/59)；根部或 RCR bulk 后校正，不是每个 AMG 层的 smoother；其他全局代数仍 FP64 |
| RCR | 外层 port Schur，分开提取实际 U/V，单出口 Sherman–Morrison / 多出口 Woodbury 响应，batched MPI reductions，同代缓存 | [#58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)、[端口 PC](RCR_PORT_PRECONDITIONER.md)；完整隐式 Jacobian 不被替换，近似 bulk 响应由外层 FGMRES 处理 |
| MPI / SIMD | 可选 owned/halo ghost 交换重叠、稳定合并字段范数，连续 AD lane SIMD 与融合累加 | [#55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)、[#57](https://github.com/saitoasukakawaii/EONSim-new/pull/57)；PETSc/MPI 仍在主线程，尚无多节点性能证据 |
| 自适应 PC | 可选数值 PC/USER Schur 复用，漂移/年龄/dt/迭代失效，每次新鲜 J；受限 stale-PC 重建重试，保留原 Newton/function 预算 | [#55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)、[#56](https://github.com/saitoasukakawaii/EONSim-new/pull/56)、[#57](https://github.com/saitoasukakawaii/EONSim-new/pull/57)；强变化动脉仍频繁刷新 |
| 分区和输出 | 稳定分桶、owner 前缀、显式正整数标签成本；ASCII VTU 默认、可选 appended binary 和 collective MPI-HDF5/XDMF 一阶结果输出 | [运行优化](FSI_RUNTIME_OPTIMIZATION.md)、[#55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)；parallel HDF5 构建才支持 HDF5 输出，checkpoint 是独立协议 |

## 使用入口（显式选择，不改变默认）

- `-fsi_coo`：可选 Jacobian COO；默认残量 COO 与 Jacobian 后端独立。
- `-fsi_overlap true`：owned/halo ghost overlap。
- `-nonlinear_adaptive_pc true`：合资格的自适应 PC 数值复用。
- `-vtu_format ascii|binary|hdf5`：结果格式；HDF5 需要 parallel HDF5。
- `-pc_recipe hybrid -pc_plan_velocity_solver field_amg -pc_plan_velocity_coarse_space rigid -pc_plan_schur_approx bfbt`：联合速度物理粗空间与压力 Schur 的一种显式组合。
- `-pc_plan_interface_smoother vanka -pc_plan_patch_precision single`：启用真实界面后校正及局部 FP32；需要实际有效界面。支持条件、选项限制及前缀见[高级 PC](FSI_ADVANCED_PRECONDITIONERS.md)。
- `-pc_plan_rcr_ports true`：需要实际 RCR 端口及支持的根 FGMRES/bulk 配置，详见[端口 PC](RCR_PORT_PRECONDITIONER.md)。

## 已核对的最新证据

以下均为已合并 PR 的既有记录，不是本次文档审查重新执行的数值测试。

| PR | 已交付与主要证据 |
|---|---|
| [#51–#53](https://github.com/saitoasukakawaii/EONSim-new/pull/53) | 装配和 runtime；#53 的初始切线复用每 10 步 J/USER 30→20，配对 wall 中位下降 12.06%–25.59%，默认新旧及线程/COO 对照收益混合。 |
| [#54](https://github.com/saitoasukakawaii/EONSim-new/pull/54) | 78/78 物理运行，656 接受步，1,282 线性修正；scalar GAMG/rigid twolevel 的小样本并非稳定加速。 |
| [#55](https://github.com/saitoasukakawaii/EONSim-new/pull/55) | 112/112 网格对照，703–17,839 DoF、1/2 rank，560 步、1,120 修正；J 更新 10 不变，USER 更新 10→2–3；20 配对 SIMD 核中位下降 30.99%–34.58%，字段归约 6→3。MPI 整程序时间波动跨零。HDF5 较大输出约 19.66 万单元，较 ASCII 快但此主机慢于 binary。 |
| [#56](https://github.com/saitoasukakawaii/EONSim-new/pull/56) | 5/5 定向 Release、6/6 动脉对照，修复重试预算；无新增性能结论。 |
| [#57](https://github.com/saitoasukakawaii/EONSim-new/pull/57) | 43/43 Release、44/44 Python 源码 CI；16 配对运行，2 rank 线性时间中位 −4.49%，整程序 wall 波动跨零。 |
| [#58](https://github.com/saitoasukakawaii/EONSim-new/pull/58) | 65/65 Release、54/54 Python 源码 CI；13 次 FSI、43 接受步，端口代数/物理对照；未证明普遍加速。 |
| [#59](https://github.com/saitoasukakawaii/EONSim-new/pull/59) | [源码 CI 45787454655](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45787454655) 85/85 选测 Release、54/54 Python；最终受影响 PCD 38 次真实求解、108 步、225 修正，最坏真残量/门槛 0.00927309。2 rank 三档 703/2299/5367 DoF：nodal 82/99/131、BFBt+patch 94/109/140、PCD+patch 144/166/225 外迭代；FP32 局部因子数组 216272→108136 字节。均不能外推为网格无关、全局内存减半或稳定加速。 |

历史 B/G 阶段验收及最新 HPC 研究的环境不同，不相加为一次测试。正确性部分覆盖 1/2/4 rank；合成曲管曾通过 8 个本地 MPI rank；32 分片准备和 19.66 万单元输出不是 32-rank 或同规模 FSI 求解。没有新的多节点/GPU/百万 DoF 生产规模结论。CI 执行数和历史复用数须分开统计。

## 仍待完成的目标（建议优先级，非已批准工期）

1. P0：在真实物理网格系列上建立迭代增长与 time-to-solution 门槛，优化 field AMG/PCD/BFBt，改进粗层和界面处理，确认附加质量强耦合收益。不要把现有根级 patch 称为层级平滑器。
2. P0：真实单机强/弱扩展及多节点基准，分开测量装配、PC setup/apply、通信和 I/O，报告 rank 最大内存；扩大密度比、时间尺度及长周期。
3. P1：患者几何、预应力、材料标定及网格/时间收敛；任意移动端口、跨分区重启、非共形接口等按目标问题单独验收。
4. P1/P2：再按测量决定更广泛混合精度、预条件粗层改造、matrix-free/partial assembly、AMR、高阶三维、GPU 等。现有路径是 assembled CPU/MPI，不提前声明已实现。

当前任务、具体失败和历史上下文：[队列](CODEX_TASK_QUEUE.md) · [进度](CODEX_PROGRESS.md) · [会话记录](CODEX_SESSION_LOG.md) · [路线](ROADMAP.md)。原始证据：[HPC 五项](../research/data/hpc-five-track-2026-11-26/README.md) · [RCR](../research/data/rcr-port-2026-11-26/README.md) · [高级 PC](../research/data/fsi-advanced-2026-11-26/README.md)。
