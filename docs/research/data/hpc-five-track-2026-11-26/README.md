# HPC-05：FSI 五项优化的实现、验证与性能证据

交付 [PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)。基线为已合并 #54 的
`main@f8dbd6991f8057fc84d0a49dc6d9c9b3c38028fe`；最终生产二进制源为
`27889707a3c650d532c2845b2f6da7fc5d2324d4`，最终测试驱动源为
`ceaa680c5c2c521abc71f0014337dc3ea16796a9`。合并状态以 PR 的 GitHub 记录为准。

所有生产与仓库验证驱动变更均先同步远程，再构建或用于算例。初始实现为 `eec28ec`；
`bb4fd3b` 修复 HDF5 测试的 C++ 声明；`2788970` 改进行强度归一化和原生 HDF5 验证；
`9c4af0d` 扩展真实 FSI overlap 测试；`8f7af90/a63aa2e` 增加并修正规模研究诊断；
`ceaa680` 增加所有选中迭代模式共同的更严格 KSP 请求。每次通过 Git API 同步后核对
本地/远端完整 Git tree 相同，再采用远端 commit 身份。后续文档/证据提交不计作新数值执行。

## 1. 实现与默认值

| 路线 | 已实现 | 数学及运行边界 |
| --- | --- | --- |
| FSI Block AMG | 语义节点图的有界聚合；平移/结构参考旋转；局部两遍 QR；完整 `PᵀAP` 后使用分布式 GAMG | 不丢流固交叉项，不把缩减 scalar AIJ 强制设为 blocksize 3；默认 recipe 不变 |
| MPI | owned/halo 两阶段 ghost exchange；回调异常先完成通信；稳定字段范数合并归约 | overlap 显式开启；归约协议须在各 rank 一致；字段计数减少不等于全部 MPI collective 减半 |
| 单元 SIMD | 连续 AD 通道、被动标量重载、原位累加、融合乘积累加、OpenMP SIMD | 不开 fast-math，不改变 lane 内加和；别名和 IEEE 特例有验证 |
| 自适应 PC | 行强度漂移、年龄、迭代增长、时间系数上下文控制数值更新；有界失败重建 | 每次需要的真实 J 仍组装；独立物理验收保持；只有旧 PC 的迭代耗尽可重建后重试一次 |
| 并行 HDF5 | collective hyperslab、owner 唯一点、全局 connectivity、静态/时间 XDMF、原子发布 | 支持首阶 Tet4/Tri3/Quad4；scalar P2 明确拒绝；checkpoint 格式不变；不声称 fsync 耐久性 |

可选控制：

```text
-pc_recipe hybrid -pc_plan_schur_approx nodal
-pc_plan_velocity_solver aggregate
-pc_plan_velocity_aggregate_nodes 16
-pc_plan_velocity_coarse_space rigid
-fsi_overlap true
-nonlinear_adaptive_pc true
-nonlinear_pc_max_reuse 4
-nonlinear_pc_change_tolerance 0.1
-nonlinear_pc_iteration_growth 1.5
-vtu_format hdf5
```

这是开关语法，不是任意生产算例的通用最优配置。`-fsi_overlap`、aggregate、自适应 PC、
HDF5 均保持显式选择。稳定合并范数与 `EONSIM_ENABLE_ELEMENT_SIMD` 默认开启；
`-nonlinear_fused_reductions false` 可做两次归约对照。资格不符的手动 lag/reuse/EW
配置不会静默套用自适应策略。行漂移是采样指标，不是完整矩阵差范数。

## 2. 环境、来源和计时方法

本地 PETSc **3.23.7 Release**、GCC **15.3.0**、Open MPI **5.0.8**、parallel HDF5
**1.14.6**。共享主机报告 AMD EPYC 9V74、9 个可见逻辑 CPU；没有可验证的 cgroup
配额读数，不推断独占物理核心或节点规格。依赖 OMP/BLAS/MKL 均限制为 1。
算例性能任务串行执行，没有相互重叠；源审查与轻量元数据读取不计作算例性能作业。

每次完整求解的 wall 使用阻塞子进程 wait，独立 watchdog 提供超时；不使用轮询等待的
量化时间。分项为每步最大 rank 时间，区间可能重叠，不能相加成总 wall。`linear_seconds`
包含 KSP 内的 PC setup 和内层求解。`ghost_seconds` 包含相关拷贝、发起与等待；
pending 期间的 owned 计算时间不代表实测隐藏网络时间。输出阶段含关闭/发布，不含 fsync。

性能表中“配对变化”先计算同轮 `candidate/baseline-1`，再取中位数和范围；它通常不同于
两个独立中位数之比。预热排除。计时从不作为正确性通过条件。

[binary-sources.json](binary-sources.json)固定 ELF 哈希及来源：主程序基线实际源是
`88e6c335`，与 main `f8dbd69` 的生产源码相同。微基准基线是保存于 main 时的已有产物，
只由 SHA256 固定身份，未独立确认其原始构建 commit，也未为了本轮重新构建。
候选主程序 SHA256：`b4fe71840296bb0533d95a59c906d3062b14d3bfc1203dac60dfb1f590d0b3d9`。

原 benchmark 自动附带的 `*-build_receipt.json` 来自保留构建目录的历史 `7e8868e` 活动，
**不是当前候选的构建凭据**。该旧文件原样保留作为环境历史，不改写其中的 commit。
本轮身份使用 binary-sources.json、每次命令的显式 build-source、实测 ELF 哈希、先推送后
执行的增量构建日志及最终源码 CI；不能把旧 receipt 的 passed 记为本轮通过。

## 3. 本地功能验收

首轮 **15/15** 定向 CTest 通过：AMG/PC 三项、自适应三项、ghost 三项、非线性验收两项、
FSI/流体单元 Jacobian 两项、HDF5 两项。覆盖 MPI 1/2/4（HDF5 为 1/2）、空 owner、
真实 Galerkin 更新、实际 PCShell setup 次数、IEEE/别名、极小/极大范数，以及通信在
owned/halo 残量/Jacobian 回调的 recoverable/fatal 故障后的完成责任。

`2788970` 只改变自适应漂移路径，增量重编后相关 **3/3 adaptive** 再验通过；未把此前
不受影响的测试计作重新执行。21 项 profile Python 检查也通过。完整构建及失败日志均保留。

`verify_fsi_coo.py --threads 2 --overlap` 的 **37 次运行均符合预期**，其中 3 次是预期失败
（两次 fatal 批次注入、一次重试耗尽），不计作正常收敛。覆盖刚体/共享弹性/独立
neo-Hookean 双域、移动/固定 RCR、全局 Jacobian、跨后端重启、真实时间步回退、第二批
worker/insert 可恢复及致命失败。原参考关闭 overlap/合并归约，优化路径开启；已接受的
迭代轨迹、场量、历史、矩阵规模均核对。回退从 `.1` 减到 `.0125`，保留 3 次拒绝。

共享 CTest `Testing/Temporary/LastTest.log` 被并行 HDF5 作业覆盖的副本明确标为
`ctest-collided-other-job.log`，不作为 SIMD/MPI 七项的原始日志；独立 `ctest.log` 的
七项通过状态完整。没有为了覆盖这段历史而重复运行测试。

## 4. SIMD、MPI 和组合装配

SIMD：GCC 的独立等效 Release 编译报告确认 16-byte 向量化，反汇编包含 packed-double
指令。24 次程序调用、48 条核记录；每条计算 50,000 个单元，四设置各五个测量配对，
另排除一个预热对。所有基线/候选 checksum 精确一致。

| 设置 | 压力面 | 核 wall 配对中位变化 | 配对范围 |
| --- | --- | ---: | ---: |
| 固定 τ | 无 | −32.14% | [−40.06%, −27.39%] |
| 固定 τ | 有 | −30.99% | [−38.94%, −30.46%] |
| 几何度量 τ | 无 | −34.58% | [−42.76%, −32.41%] |
| 几何度量 τ | 有 | −34.24% | [−39.95%, −33.14%] |

同二进制 MPI 消融：n8/2 ranks、五步、预热一对及三测量对共 **8 runs**。每步字段范数
归约 **6→3**，ghost exchange 仍为 6；ghost 阶段配对中位 **−41.340%**，wall 中位
**−0.891%**，范围 **[−10.675%, +8.033%]**。该证据不能支持稳定的整程序加速结论。

旧/新整程序组合对照：n4/n8 × 1/2 ranks，共 **32 runs**。装配阶段配对中位
**−11.19%～−17.51%**，wall 变化混合（约 **−1.23%～+1.95%**）。不把 SIMD 和 MPI
的组合收益拆成未经消融的单独因果贡献。

两组共 40 runs、200 步、400 次真实线性修正、240 个保存状态，经独立回放和 2,304 次
文件哈希断言通过。最大场差 `2.220446049250313e-16`，历史差 `3.2751579226442118e-15`；
所有轨迹都是五步 `[Newton=2,Krylov=2]`，真实残差门槛没有放宽。

## 5. 聚合 AMG 和自适应 PC 的网格系列

同一生成双域物理：Young 模量 100、Poisson 比 .3、压力 1、五步 `dt=.02`，保留四字段
尺度和边界。每组共享分区，公共外层 `rtol=5e-11`；独立门槛为
`||J dx-rhs|| <= 1e-12+1e-10*||rhs||`，场/历史门槛 `2e-9`。

n4/n6/n8 的 **102/102 runs**、n12 的 **10/10 正确性 runs** 通过。合计 560 步、1,120
次真实线性修正、672 个保存状态、5,998 次文件哈希断言及实际 solver 树独立回放通过。
最大真实残差/门槛为 .419418 以下，最大场差 `3.9968e-15`，历史差 `3.2085e-14`。

| n | 消元后总 DoF | 第一粗维数，1/2 rank | 2-rank twolevel 外迭代 | aggregate | aggregate + adaptive |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4 | 703 | 59 / 60 | 150 | 152 | 152 |
| 6 | 2,299 | 172 / 174 | 192 | 187 | 188 |
| 8 | 5,367 | 379 / 393 | 264 | 244 | 244 |
| 12 | 17,839 | 1,158 / 1,164 | 414 | 370 | 370 |

上述迭代数均为五步累计。辅助 GAMG 实际为两级，n12 底层有 17/13 个方程。迭代仍随
网格增长；不能报告 mesh-independent 或多节点强/弱扩展已成立。

n8/2-rank 的三次独立中位线性时间：coupled `.425123s`、twolevel `.247413s`、fresh
aggregate `.270783s`、adaptive aggregate `.195364s`。Fresh aggregate 减少部分外迭代，
总线性耗时仍更高，未分离 setup/apply/inner 各自贡献，因而不是普遍更快。其 fresh/adaptive 同轮配对线性中位 **−27.852%**，范围
**[−34.163%, −19.988%]**；wall **−13.350%**，范围 **[−16.753%, −5.323%]**。

实际 USER Schur 更新 **10→3**（n4/n6）、**10→2**（n8/n12），每个配置的完整 J 始终
为 10 次。真实 USER 更新逐步等于策略刷新决策，另有 PCShell setup 调用次数测试，
没有仅凭 `pc_reuses` 宣称实际节省。六组配对 wall 中位改善为 3.39%～13.35%，但
n8/1-rank 的范围含 +3.892%，须保留波动边界。n12 没有重复性能测量。

## 6. 完整动脉轨迹与保留的真实残差失败

原共同请求 `5e-11` 下，粗网格 fresh aggregate 的第 14 步第二次修正报告
`CONVERGED_RTOL`，估计范数 `7.352087088e-20`；独立残差为 `2.937458505e-19`，
固定门槛为 `2.429719522e-19`，比值 **1.2089702**。完整输出和物理场一致没有覆盖该
严格失败；原 receipt 和日志保留为 failed。

PETSc 3.23.7 [残差 API](https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/manualpages/KSP/KSPGetResidualNorm.html)
及 [FGMRES 源码](https://web.cels.anl.gov/projects/petsc/vault/petsc-3.23/docs/src/ksp/ksp/impls/gmres/fgmres/fgmres.c.html)
确认递推估计用于收敛测试，并不等于显式 `J dx-rhs`。`ceaa680` 只给验证驱动增加公共
`--outer-rtol 1e-11`，保留原默认 5e-11；两种 aggregate 配置、两网格共同使用一次更严格
请求。独立门槛始终为 `max(1e-23,1e-10*||rhs||)`（原舍入 margin 1.00001），物理门槛
`2e-6` 及生产默认均保持，没有逐模式寻优或放宽通过标准。

修正后 quick **6/6**、full **30/30**，共 312 步、624 次真实修正独立复核通过。包含六条
32 步完整轨迹；最大真实残差/门槛 **.8439101351**，最大五场归一化差 **7.5813e-12**。
原失败位置残差为 `2.050466190e-19`，在原门槛内。78 个保存时间点、输入/输出/源文件
哈希、实际层级及由各字段 RMS×方程数重构的残差全部审计。

粗/细网格 adaptive 仍刷新 **61/62** 次、复用 **3/2** 次，完整 J 均为 64；强变化压力
轨迹没有明显的刷新削减。计时样本是四步窗口，不是 32 步：配对 wall 中位粗/细为
**+1.691%/+12.346%**，范围均跨零，不支持动脉性能提升。生成算例的收益不能迁移为
该压力轨迹的收益。

## 7. HDF5 真实读取及输出成本

Poisson/双域 FSI 的 ASCII/HDF5 × 1/2 ranks：**8/8 solves**、**14/14 精确比较**，
1,298 节点记录、2,226 体/边界单元，坐标、字段、ID、标签、拓扑完全一致。
真实 ParaView `XDMFReader` 成功读取 10 个入口，包括四个 `[.02,.04]` 时间集合。

n32 Poisson 有 35,937 节点、196,608 Tet4 体单元。24 次输出（6 预热、18 测量），6 次
独立精确 ASCII/HDF 对照累计 252,498 点记录、1,253,376 单元。每组求解迭代、残差、
积分和误差一致；观测到的非空数据写入均实际 collective，没有 independent fallback。

| MPI ranks | ASCII output 中位 / s | binary / s | HDF5 / s | HDF5/ASCII 配对变化 | HDF5/binary 配对变化 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | .117940491 | .012727172 | .031628952 | −73.221% | +152.778% |
| 2 | .057236560 | .012047565 | .031440347 | −44.732% | +164.990% |

HDF5 每快照两个文件，约 11.55 MB；binary 在 1/2 ranks 为 2/6 文件，约 13.84/13.93 MB。
这里 HDF5 比默认 ASCII 更省输出时间，但本机 binary 更快；没有并行文件系统或大进程数
证据。原子 entry 发布保留先前快照，同进程仅清理自己已被替代的旧 payload，不删除用户
或其他进程创建的文件。静态入口与 `.series.xdmf` 分离。

## 8. 原始包、失败历史与独立审计

[performance-summary.json](performance-summary.json)提供机器可读汇总；
[archive.json](archive.json)给出分片和整体 SHA256；[archive-manifest.json](archive-manifest.json)
列出每个归档文件的路径、字节及 SHA256。将按名称排序的 `evidence.tar.xz.part*` 拼接后
用 xz/tar 解压到独立目录，恢复 `hpc-five-track/`。复现历史命令须重映射工作区路径，
不得覆盖保留证据。ELF、`.o` 和 Python 缓存未入包，来源由独立哈希收据固定。

主要入口（相对于解压根目录）：

- `hpc-five-track/environment/`：二进制身份、CMakeCache、历史运行环境包装脚本。
- `hpc-five-track/simd-mpi/`：向量化报告、checksum、计时、测试与独立核审计。
- `hpc-five-track/fsi-overlap/`：37 次真实 FSI 组合验证（含 3 次预期失败）。
- `hpc-five-track/assembly-combined/`、`mpi-ablation/`：40 次运行、输入/分区/状态与计时。
- `hpc-five-track/amg/scaling-measured/1795662926528760770/`：102 次网格研究。
- `hpc-five-track/amg/scaling-n12/1795663153095360419/`：10 次较大网格正确性。
- `hpc-five-track/amg/arterial-margin/`：最终共同严格请求的 quick/full。
- `hpc-five-track/io/`：C API/原生 h5dump/ParaView 正确性及 24 次较大输出。
- `independent-assembly-audit.json`、`independent-scaling-audit.json`、`independent-arterial-audit.json`
  均在 `hpc-five-track/` 下，带对应独立回放脚本和日志。

保留失败/中间证据：初次 HDF5 测试混合 `auto` 声明编译失败；缺少 h5py 后改用原生 h5dump
并非数值失败；初次规模驱动未请求 `-pc_plan_report`，18 个粗层元数据审计失败；原始
5e-11 动脉 true-residual 失败；自适应行尺度调整前后 quick 结果分别保留，不混为最终
性能样本。原有源文件身份、失败标签和数值门槛不改写。

## 9. CI 与交付

源码 `ceaa680c` 的 [Core run 45748579007](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45748579007)
实际 **75/75 Release、0 failed、0 skipped、0 复用**；选测阶段六组 Python 共 **75/75** 通过。
selection、Release、receipt 三项成功，merge checkout 为 `10bfcd6e4aaa2d592791bdb67cb08ef172189233`。
[Website check 45748578957](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45748578957)
成功，但该源码 head 没有网站改动，实际安装/构建步骤跳过，不声称新增 VitePress 构建。
最终证据/文档提交再核对最新 head 的四项必需检查，不把复用的 source 执行记为重新运行。

最终文档提交也必须在相同 PR 的最新 head 上通过四项必需检查，随后按用户授权执行锁定
head 的 squash 合并。[源码 CI 原始日志与收据](ci-source-ceaa/receipt.json)单独保存，不混入本地性能归档。
main 的经典保护已从分支元数据核实：所有人均要求
`Select affected checks`、`PETSc 3.23.7 / release`、`Record incremental evidence`、
`Build VitePress`。没有修改保护配置、绕过检查、伪造审核或发布公开网站。

[未发布知识草稿](../../../../website/drafts/hpc-five-track-optimization.md)区分理论、源码、
正确性和性能。此次本地没有运行全套、Debug、旧 PETSc、跨节点或 GPU 验证；当前证据
不能解释为这些能力已通过。
