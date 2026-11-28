# EONSim Codex Development Progress

独立合格的 C20 在 32/64/128 纯 MPI 上分别用时 928.545、630.015、460.145 s，每档一次。[C20 强扩展](FSI_SCALABLE_05.md#c20-的纯-mpi-强扩展)

真实管 B20 在 32 MPI 上保持固定容差并缩减四个 GAMG 粗层，三对正式样本的 T_job 中位数从 53.264 s 降至 37.275 s。[样本与核验](FSI_SCALABLE_05.md#固定精度的真实管-gamg-粗层通信)

A20 的两组通信正式时间均独立核过相同 LU。physics/Telescope 从 2.321 s 降至 1.806 s，整体 MG 的 owner 本地读写从 6.334 s 降至 2.974 s。[真实管通信比较](FSI_SCALABLE_05.md#a20-的两种通信比较)

FSI-SCALABLE-05 已将生产返回向量、实际 forcing 和物理筛选绑定到显式协议。B20 经直接法与独立迭代交叉核验，三档固定容差的计数、完整场差及耗时见[第五阶段](FSI_SCALABLE_05.md)。

FSI-SCALABLE-04 从 #71 推进到原式 LU 精化、现场 B/C 布局复核和独立参考门槛。A4 有严格直接参考，B 首次 Newton 校正仍失败。[数值与性能资格](FSI_SCALABLE_04.md)

FSI-SCALABLE-03 已核验 A 的并行内部筛选、A 的 32/100 步外部回归和合成粗层进程数对照。B 的 20 步直接解在新增逐校正复核中未过严格线性门槛；C 的首次失败已重放并保存原系统。[结果与开放范围](FSI_SCALABLE_03.md)

2026-11-27，FSI-SCALABLE-02。原版 FSILS 的两档 GMRES 配置均通过小型脉动弹性管的启动、100 步及完整 1 s 周期。32 和 128 rank 的 PETSc 分层剖析完成，粗层代价随 rank 增长。见[原始数据及对标报告](FSI_SCALABLE_02.md)。

2026-11-27 核对：主线已合入 #65（`2463f717`）；以下历史记录保留实际执行日期、源码、失败与验收边界。当前能力与开放目标见 [当前能力矩阵](CURRENT_STATUS.md)。历史 review/Draft 不代表当前 PR 状态，历史证据不计为本次执行。

## 2026-11-27 · FSI-SCALABLE-01

由 `main@04e2af9` 创建 `codex/fsi-scalable-01`。已在服务器上完成 Release 构建、压力压缩、自适应粗层重分布和零提升跳过的定向代数与 FSI 对照。10,387 自由度、8 rank 下关闭插值能量优化将端到端中位数从 10.651 秒降到 3.598 秒。64 rank 下 1,046,979 自由度的两种配置均接受五步。108,379 自由度的 8–128 rank 测试均通过数值门槛，32 rank 最快，加速约 1.266 倍。固定 8 rank 的压缩模式平均线性迭代比约 2.00，仍高于 1.3。阶段和最终规模见[实现报告及数据](FSI_SCALABLE_SOLVER.md)。

六档弱扩展均完成三次计时。`796153b6` 最大达 1,259,907 自由度和 128 rank，五步中位数 282.93 秒与整组采样 RSS 中位数 20.80 GiB。相对 4 rank 的弱扩展效率为 6.86%。

同一 108,379 自由度网格的五种 128 核混合配比均通过各三次交错计时，最快为 32 MPI × 4 OpenMP，20.99 秒。该二进制下 128 × 1 为 47.93 秒。

## 2026-11-27 · FSI-SADDLE-01：十三项机制实现与有界验收完成，网格及规模目标仍开放

从 #64 的 `main@036f865e3570905a58da465c91873678de485119` 接续，对应
[PR #65](https://github.com/saitoasukakawaii/EONSim-new/pull/65)，分支 `codex/saddle-point-multigrid`。
最终生产/验证驱动源码 **`ccf1bd7b3727a6b3ddd3a85954a3a78c51a652ba`**。每批实现和修正均先同步远端并核对完整 tree，
再构建及执行；最终文档 head 的四项必需检查及锁定 SHA 合并状态由 PR #65 记录确认。

已实现逐层 pressure/primal AMG、散度约束与真正压力像空间闭包、多层离散 supremizer、
耦合 Schur/Braess–Sarazin、乘性/着色 Vanka、跨 rank 聚合、层级自适应/复用、exact
matrix-free fine、分布式 coarse、逐次 deflated FGMRES 和独立归约批处理。最后一项 Krylov
采用有界 QR/SVD 回收，不宣称完整 harmonic-Ritz GCRO-DR；通信指标也不等同于实际网络延迟。

最终源码新跑 **6/6 MG/smoother（1/2/4 rank）及 12/12 Braess 物理/网格轨迹**。本地不同
CTest 有效覆盖 **17/17**，新增物理配置汇总 **48/48**、网格配置汇总 **18/18**；复用记录均
保留原源码/binary，不冒充最终提交重跑。最大场差 `4.316880187e-12`、历史差
`7.993605777e-15`，低于原 `2e-9`；真实残量 gate 比最大 `0.00948933`，交换缺陷最大
`1.245817331e-15`。原失败和单因子诊断见[证据索引](../research/data/fsi-saddle-01-2026-11-27/README.md)。

固定 703/2299/5367 DoF、2 rank，colored 总迭代 **28/39/50**，全开组合 **27/36/46**；
平均迭代增长比分别 **1.7857 / 1.7037 > 1.3**，近似网格无关仍 **OPEN**。同批 n8 colored
求解时间比既有 mono 减少 34.46%；全开组合反增 69.97%，峰值 RSS 最大 rank 值增加
86.19%，压力 729→729→729 饱和。全部开关同时启用不代表总体加速。

保留并修复：不变 B 的过度重建、正确 guard 被物理审计误拒、粗层无主元 LU 失败、
Braess alpha=1 在 n8 达到1500次仍失败。局部 MUMPS 主元与默认 alpha=2 分别经单因子
诊断和正式复验，未改变模型、外层上限或任何精度门槛。本轮单机最大5367 DoF；旧10387 DoF
仍是历史证据，百万 DoF/多节点/扩展效率未运行。[算法说明](FSI_SADDLE_POINT_MULTIGRID.md)
及[文章草稿](../../website/drafts/fsi-saddle-point-multigrid.md)记录机制、成本和边界；草稿未发布。

[最终源码 CI 45931896224](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896224)
实际新执行 **83/83 Release、54/54 Python**，没有复用数值记录。合并预览
`75bb86a0c5e668d497d0e95eb5ed0be4df824550` 与 `ccf1bd7` 的完整 tree 均为
`014a1de3199b7e476aec00aa63078a13adb60610`，dirty=false；
[源码网站检查 45931896258](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896258)
通过。远端检查与本地分源轨迹分别计数；最终文档 head 的四项检查及合并以 PR #65 为准。


## 2026-11-27 · FSI-SCALE-01：实现与有界验收完成，收敛及规模目标仍开放

本节按北京时间记录，任务起始于 2026-11-26。从已合并 #63 的
`main@88257a9be35008b0063820910843625fa17bb267` 接续，对应
[PR #64](https://github.com/saitoasukakawaii/EONSim-new/pull/64)。最终生产/验证驱动源码为
`50b41ae19067bd8853a482ab853805e23c096ec5`；每批实现及修正均先同步远端、核对完整 tree，
再构建及运行。**实现与本轮有界验收已完成；最终文档提交的四项必需检查及锁定 head 合并结果由 PR #64 记录确认。**

已接入实际缩小符号图的 reduced P、冻结系数与 SIMD 精确方向核、方向 halo 重叠、物理缩放
与粗空间、选择性 Vanka patch、紧凑 native FP32、有限 K-cycle、自适应 Newton forcing、
跨步修正子空间复用，以及记录真实节点/DoF 的强弱扩展驱动。新增压力 supremizer 从原
spectral 预算中替换最多两个方向；局部配对及 FP64 setup 耦合保持不构成全局 inf-sup 证明，
也不保证 native 量化后的配对达到同样精度。原完整 Jv、最终物理字段/约束门槛保持。

`50b41ae` 本地 **3/3 MG CTest（1/2/4 rank）、19/19 Python、9/9 严格网格求解及
15/15 最终双域/移动 NH-RCR 求解**通过。后两批独立审计覆盖 72 接受步、171 条线性残差
记录；最大场差 `2.9099984e-10`、历史差 `4.1689985e-12`，低于原 `2e-9` 门槛，ghost 差为 0。
`30e2941` 的 **9/9 MG/patch/smoother CTest**、12 次 K-cycle 网格求解和 native RSS pair
按原源码保留；没有将它们计作最终源码重新运行。

固定 703/2299/5367 DoF、2-rank、六次严格线性修正，优化 V 总迭代为 97/160/227，
supremizer V 为 92/138/199。平均迭代最大/最小分别 **2.3402 / 2.1630**，均未达到预声明
的 **≤1.3**；`30e2941` 的 K-cycle 也为 2.0612。近似网格无关仍 **OPEN**。实际最大规模
为 **10,387 DoF、一个 host**；百万 DoF、多节点及强弱扩展效率仍 **OPEN / 未运行**。

保留投影舍入、缺 action telemetry、真实残差间隙、guard 提前发布 reason、RSS 采样差异、
Python 负例异常类型等原始失败和中断。`116836b` native-only 的峰值 RSS 曾增加约 35%；
`30e2941` 修复 generation 生命周期、patch/halo 存储后，一次同源 pair 的最大 rank 归一化
峰值 RSS 降低 4.0557%。这不代表总内存减半、带宽减半或普遍端到端加速。

最终源码 [CI 45853312807](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312807)
实际新执行 **4/4 Release、19/19 Python**，另复用 62 项既有 Release 证据，Release 总覆盖
66 项。合并预览 `3ca62ae4c0c037ca59c255fc8cd1754f1101f7ea` 的完整 tree
`7f66c8b02d62ed67606f7bf5f94fd5af34915f6e` 与 `50b41ae` 相同；
[源码网站检查 45853312823](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312823)
成功。最终文档 head 的四项必需检查与锁定 head 合并结果以 PR #64 的实际记录为准，
不能由源码检查推定已合并。

[完整命令、分源结果与失败原件](../research/data/fsi-scale-01-2026-11-26/README.md)、
[运行及数学说明](FSI_SCALABLE_MATRIX_FREE.md)、
[未发布知识草稿](../../website/drafts/fsi-scalable-matrix-free.md)。未追加全量、常规 Debug、
旧 PETSc 或无边界参数扫描；原件审计没有声称离线重算未保存的 J、b、dx。

## 2026-11-26 · FSI-MF-02：固体直接方向核与零初值 V-cycle

从已合并 #61 的 `main@6bb6f438b63c` 接续，交付 [PR #62](https://github.com/saitoasukakawaii/EONSim-new/pull/62)。
生产/数值测试源码 `b7d727bd10231c22987b18114d1e25d622b2b8f1`，完整远端 tree
`f62deb159dcadde5a48aca8a7af4063bc4628204` 先核对一致，再进行 Release 增量构建和验证。

新增线弹性/Neo-Hookean 直接方向作用、一致质量作用及参考面壁支撑方向作用；FSI 的
matrix-free 固体分支不再形成 9×9 材料或 12×12 单元切线，也不计算该作用不使用的
残量/能量。原装配路径保留为独立对照。每个非粗 MG 层利用已知零初值省一次残量矩阵
乘及其 halo 通信，覆盖 `pre_smooth=0`、多次预平滑、无后平滑、FP32、空 owner 与谱重建。

本地 **4/4 定向 CTest**（固体方向核、MG 1/2/4 rank）及 **11/11 真实 FSI** 通过。
14 组固体/12 组支撑直接作用对旧切线最大归一化差为 `3.3998581e-16`/`1.4946835e-16`；
残量中心差分也通过。物理检查含非等步长 generalized-alpha、运动血管、NH、壁支撑、
移动 RCR、FGMRES/PIPEFGMRES，33 接受步、75 条真残量，原门槛保持。

局部核 4 配置、每配置 7 对×20,000 次测量，配对耗时中位降低 **75.75%–82.08%**。
归档旧二进制经 SHA256 核对，与新二进制在同一个 350 DoF、2-rank 移动血管上做
3 对交替测量：两者均 155 次外层迭代、173 次 matrix-free 作用；该作用阶段 rank0
耗时中位降低 **23.27%**，整程序 wall 中位反而增加 **1.44%**，波动范围跨零。
局部收益不等于稳定端到端加速；本轮没有解决完整 P 存储、网格无关或多节点目标。

[原始证据与测量范围](../research/data/fsi-mf-02-2026-11-26/README.md)、
[未发布草稿](../../website/drafts/fsi-direct-solid-action.md)。没有追加本地全量、Debug 或旧锁验证。
源码CI45832884735实际 **42/42 Release、6/6 Python** 通过，0数值失败/跳过/复用；
选测及成功收据的完整tree与b7d727b相同。PR#62已于北京时间21:57由既有保护流程合入
`194c96eda208ae49de1b0a65e5a36d60acca76b6`。后续原件/文档归档单独提交，不算新的数值执行。

## 2026-11-26 · FSI-MG-01：整体多重网格、逐层校正与精确 Matrix-free

从已合并 #59 的 `main@3472a18` 接续，交付 [PR #61](https://github.com/saitoasukakawaii/EONSim-new/pull/61)。
全部十二条请求已实现：完整流体/压力/结构/ALE Galerkin 层级、逐层混合 Vanka、结构顺应性
压力 Schur、保持物理候选的插值能量下降、局部谱增强、PCD Robin/速度质量增强、批量 LU
与精确缓存、两种正规算子 Chebyshev、FP32 V-cycle、粗层 MPI 聚合、PIPEFGMRES 及精确
方向作用/独立刷新 assembled P。最终生产源码 `3b5cbddb928dfa789dc1f3f424dba451f33107e6`。
每次源代码与测试修改都先同步远程、核对完整 tree，再构建和运行。

修复四类实际故障：重复 Galerkin 计算破坏精确缓存；MF 错误遗留 RHS 读锁；流水线错误
遗留 split reduction；稠密粗图的重叠 patch 超限。最终采用源 Mat 数值状态守卫、会话向量
隔离、排空归约后报告原 fatal，以及完整混合聚合体粗 patch。原失败保留，不放宽门槛，
不截断 patch 行、不操作 PETSc 私有锁字段。所有受影响检查通过后才进入归档。

本地有效 22 项 CTest 按源复用：最终源码重跑 12 项、未受修改影响的早期 10 项复用；
覆盖 MPI 1/2/4。最终 28 次真实 FSI 复验全部通过，84 接受步、177 个真残量记录；累计
64 次成功及 4 次已修复的早期 setup 失败分别保存。独立重读原日志/CSV/VTU 和归档摘要，
最终最大保存场/坐标差 `5.66658e-13`、历史差 `7.99361e-15`、真残量/原门槛 `0.00904389`，
owner/ghost 差为 0。没有把日志残量重审写成离线 J 乘积。

源码 [CI 45819157827](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45819157827)
实际 **95/95 Release、54/54 Python**，0 数值失败/跳过/复用；成功收据、JUnit 清单和
merge-preview/source tree 一致性已核实。后续文档 head 复用证据，四项必需检查与锁定
head squash 合并以 GitHub 记录为准，不计作新数值执行。

2-rank、703/2299/5367 DoF 的整体 MG 迭代为 104/151/206，FP32 相同；5367 DoF 层级
为 5367→1354→178→42，粗层进程数 1。小例直接解更快，FP32 线性时间更长；最大 rank
RSS 为 FP64 198.668 MiB、FP32 214.629 MiB。局部因子字节减半，仍保留 FP64 setup 矩阵。
Matrix-free 小例 P 装配 6→3，但完整 P 仍存储。网格无关、总内存/端到端加速和多节点
规模收益尚未证实；局部谱增强不等于全局残量学习，PCD 质量增强不等于标准加性 PCDR。

[完整原件、失败及成本](../research/data/fsi-monolithic-mg-2026-11-26/README.md)、
[使用与数学说明](FSI_MONOLITHIC_MULTIGRID.md)、
[未发布算法草稿](../../website/drafts/fsi-monolithic-multigrid-matrix-free.md)。
没有追加本地全量、常规 Debug、旧 PETSc 或多节点测试；知识文章保留在 drafts。

## 2026-11-26 · FSI-PC-05：物理粗空间、压力 Schur 与界面混合精度

从已合并 #58 的 `main@af4a7fb` 接续，交付 [PR #59](https://github.com/saitoasukakawaii/EONSim-new/pull/59)。
实现递归 field-aware 流固速度 AMG、保留完整 D 的 LSC/BFBt 变体、当前 ALE 物理 PCD、
真实界面混合 patch 后校正与局部 FP32 LU/FP64 细化及回退。默认配置保持；原完整 Jacobian、
物理残量、时间历史和接受门槛保持。每次源码/驱动都先同步并核对完整 tree，再构建和运行。

首版 c5af27d 的界面 4-rank 空 owner 路径暴露 MatIncreaseOverlap 集体调用错序；e565c98
仅临时补空 IS 使所有 rank 参加 setup，1/2/4-rank 复验通过。物理研究还发现旧 PCD 同时
把质量/Laplace/输运边界置单位破坏 Stokes 缩放；最终源码 `19cd26f` 保留物理 Mp，
匹配 Kbc/Ftilde 的黏度尺度。新测试链接旧库实际失败，最终 6 个独立 Stokes 作用 oracle、
4 代积分和 WORLD 空 owner/异黏度拒绝的 2 项 CTest 通过。

当前有效本地覆盖为新 field/pressure/interface 各 1/2/4-rank 三项、最终 PCD 两项及既有
默认路径五项，按各自源码复用；没有把它们都算作最终提交重跑。初始20次、研究60次、
最终受影响PCD38次真实求解都通过独立原件审计。最终38次含108接受步、225已测线性修正；
最坏真残量/门槛0.00927309，最大场差3.19152e-11，历史5.68434e-14，owner/ghost差0。

2-rank、703/2299/5367 DoF 的 PCD+FP32 patch 从825/1199/1731次降至144/166/225；
同配置 nodal 为82/99/131、BFBt+patch为94/109/140。PCD显著改善但仍较慢，迭代仍随
网格增长。六组密度/时间步下BFBt加patch少2.44%–11.96%迭代；PCD小例加patch反而多。
FP32局部因子数组216272→108136字节且与FP64迭代相同，不代表总内存/带宽/耗时减半。
近似网格无关、每层界面 smoother、普遍性能收益及更大规模仍属未达目标。

[完整证据](../research/data/fsi-advanced-2026-11-26/README.md)、[使用与数学说明](FSI_ADVANCED_PRECONDITIONERS.md)
和[未发布草稿](../../website/drafts/fsi-field-amg-pressure-interface.md)记录全部失败、诊断、
新旧来源及独立审计。最终源码 CI 和文档 head 四项检查、锁定 head 合并按 GitHub 核实；
文档证据复用不算新数值执行。没有全量、常规 Debug、旧 PETSc 或多节点追加验证。

最终源码CI [45787454655](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45787454655)
实际85/85 Release选测、54/54 Python通过，0数值失败/跳过/复用；合并预览121e54bb与
19cd源码tree相同，成功增量receipt及官方artifact摘要均已核实。后续文档检查复用此来源。

## 2026-11-26 · RCR-PC-01：端口 Schur 与低秩预条件器

从已合并 #57 的 `main@b731d471` 接续，交付 [PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)。
完成 RCR-aware Port Schur、单出口 Sherman–Morrison、多出口 Woodbury、GAMG/BoomerAMG
组合、出口内积合并归约和同代自适应缓存六项开发。实际约束后的 U/V 分开提取，保留移动
几何与非对称耦合；根 PCSHELL 包裹原语义 bulk，原完整 Jacobian 和物理接受门槛保持。

首版 `94046b1`、失效缓存修复 `28e6d54`、时间计划驱动修复 `ad08887` 均先同步并核对远端
完整 tree，再执行对应构建和验证。首轮故障负控发现 PCApply 提前返回遗留向量读锁，改为
PETSc PC failure 协议；FSI 首次失败为名义终点与变步长和不一致，测试明确终点并加强时间
比较。两次失败原件均保留；后两次只执行受影响验证，不改接受门槛。

本地32/32 Python通过，旧4项代数/自适应在首版通过并复用；修复后新1/2/4rank代数3/3
通过，最终FSI1/1通过。13次求解、43接受步，独立重读96个真残差，最坏与严格门槛之比
0.0997252；最大场差7.57780e-11，历史2.15827e-12，电路1.69548e-13。
总114 Newton迭代中直接参考18次没有额外线性诊断，不计为已观测真残差样本。
实际adaptive为12次新鲜Jacobian、8次PC刷新、4次复用；798个内层solver记录无失败。

GAMG外层迭代单出口145→144、双出口53→53；短样本耗时不作普遍加速结论。
[完整证据](../research/data/rcr-port-2026-11-26/README.md)、[使用文档](RCR_PORT_PRECONDITIONER.md)
及[未发布草稿](../../website/drafts/rcr-port-schur-low-rank.md)已归档。最终源码
[CI45776829333](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45776829333)实际
65/65 Release、54/54 Python通过，0数值失败/跳过/复用，成功receipt已核实。
后续文档head四项必需检查及按用户授权的合并以GitHub为准；文档证据复用不算新数值执行。

## 2026-11-26 · HPC-07：固定 Schur 刷新与重叠场展开

从已合并 #56 的 `main@55a04f7` 接续，交付 [PR #57](https://github.com/saitoasukakawaii/EONSim-new/pull/57)。
生产及首轮测试源码 `4c7edc6cc14219acfc97d39b9651c935a1c875ac` 先同步远程并核对完整 tree，
再做 Release 增量构建。固定节点逆 COO 图与缓冲复用、overlap owned/halo 单次场展开、
空线程批次消除，以及 HDF5 独立校验器的完整拓扑/绑定检查均已实现。

本地 **4/4 Release、30/30 Python** 通过，含 1/2/4-rank 节点 Schur、非零→零→非零
更新、奇异恢复和双线程 FSI。FSI 独立回放确认 34 次正常求解、3 次预期失败，83 接受步；
真实缩步、端口跨后端重启及第二批线程故障路径成立。14 次历史 HDF5 文件精确回放新通过，
70 份原件哈希与已提交归档一致；没有重新运行其物理求解。

首轮源码 CI 42/43 通过，唯一失败来自 MPI stderr 半行前缀导致注入标记解析漏读；原始
日志证实 worker 1/team 2/batch 1 并按预期 fatal 终止。测试解析修复 `8e6c013` 先同步后
定向复验，8/8 Python 与双线程 FSI 1/1（37 次求解）通过，生产代码和接受门槛未改。
最终源码 [CI 45769962561](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45769962561)
实际 **43/43 Release、44/44 Python**，0 failed/skipped/复用，增量验收收据成功。

新旧二进制配对 **16 runs、80 步、160 修正**，96 状态与861哈希断言独立复核通过。
同分区场/历史差均为0，最坏真实残差/原门槛0.0933858014；迭代轨迹不变。
单rank线程批次58→29，MatZeroEntries两档均少9次；全程序MatAssembly未减少。
2rank线性时间配对中位−4.49%，范围[−13.28%,−3.67%]；wall−6.42%，范围含+14.38%，
峰值RSS中位+1.08%，不作普遍整程序加速结论。

[完整命令、来源与证据](../research/data/hpc-followup-2026-11-26/README.md)及
[未发布草稿](../../website/drafts/hpc-fixed-structure-refresh.md)。源码 CI 和最终四项检查、
合并按 GitHub 记录核实；文档提交只复用不受影响证据。没有新增全量、Debug、旧 PETSc、
多节点或百万自由度验证；前五项优化的既有规模边界继续有效。

## 2026-11-26 · HPC-06：自适应 PC 重试预算修复完成

GitHub 已核实五项优化的 [PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)
合并于 `2d0e9b79`；其最终 head 四项检查成功，75 项数值证据复用来源清楚。本次补齐其
原先仍写“未验证”的 PR 描述，并在三路独立复查中发现自适应 PC 恢复的求解级预算漏洞。

[PR #56](https://github.com/saitoasukakawaii/EONSim-new/pull/56) 源码与回归测试
`bce292a1870c38686e44514e2879009ebb9a736a` 已先同步远程、核对完整 tree，再构建验证。
第二次 SNESSolve 仅取得剩余 Newton 与 PETSc 计数的函数评价预算；原始物理接受基线保持，
实际命令行上限保留，原预算在重试后恢复，成功会话可继续复用。

新测试链接旧 main 实现确实失败；修复后本地 **5/5** 定向 Release、1/2/4 rank 通过。
两档动脉直接/aggregate/adaptive **6/6 runs、24 步、48 修正**，独立重读原日志与五场，
最大真实残差/门槛 **0.745355513**，五场最大归一化差 **4.68297e-13**，原门槛不变。
源码 CI 实际 **17/17 Release** 通过（0 跳过、0 复用）；最终文档检查只继承不受影响证据。

[命令、失败与独立审计](../research/data/adaptive-retry-budget-2026-11-26/README.md)。
预算故障由定向非线性回归触发，动脉重建重试为 0；本轮没有新的性能结论。HPC-05 的
AMG/MPI/SIMD/HDF5 性能与规模边界继续有效；其历史证据复用，本次未重跑。

## 2026-11-26 · HPC-05：五项优化实现、验证与独立审计完成

从已合并 #54 的 `main@f8dbd699` 接续，交付 [PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)。
生产源码 `27889707a3c650d532c2845b2f6da7fc5d2324d4`；最终验证驱动 `ceaa680c`。
生产与仓库驱动改动均先推送、核验完整 Git tree，再构建/运行。合并状态以 GitHub 为准。

完成有界语义聚合及 `PᵀAP→GAMG`、owned/halo ghost 重叠与稳定合并字段归约、AD SIMD
与融合累加、有界自适应 PC/USER Schur 更新、parallel HDF5/XDMF 结果输出。新 AMG、
overlap、自适应、HDF5 保持显式选择；完整 J、真实残差与物理接受标准保持。

本地首轮 **15/15** 定向 Release CTest，漂移修正后 **3/3** adaptive 重验，21 项 profile
Python 通过；真实 FSI **37 次运行均符合预期（含 3 次预期失败）**，覆盖双线程、端口、
重启、实际回退及故障排空。
SIMD **20 测量配对** checksum 完全一致，核时间配对中位下降 **30.99%～34.58%**。
MPI 同二进制每步字段归约 **6→3**、ghost 阶段中位 **−41.34%**，整程序 wall 范围跨零。
组合装配及 MPI 的 40 runs/200 步/400 修正、240 保存状态和 2,304 哈希断言独立回放通过。

AMG 网格研究 **112/112 runs、560 步、1,120 次修正**，703～17,839 DoF、1/2 rank。
实际 USER 更新 **10→2–3**，完整 J 始终 10；n8/2-rank fresh/adaptive 配对线性中位
**−27.85%**、wall **−13.35%**。Fresh aggregate 并非普遍比旧 twolevel 更快，迭代仍随
网格增长。独立回放 672 保存状态、5,998 哈希断言通过，不宣称 mesh-independent。

完整动脉曾发生估计残差已收敛而显式残差比为 **1.2089702** 的真实失败，原件保留。
共同外层请求由 5e-11 收紧至 1e-11，原 `max(1e-23,1e-10*rhs)` 验收不变；唯一一次
修正后的 quick/full **36/36 runs、312 步、624 次修正**通过，最坏比 **.8439101351**、
五场相对峰差 **7.5813e-12 < 2e-6**。32 步仍刷新 61/62 次，动脉计时无统一收益。

HDF5 小实算 **8/8**、14 次精确比较和 ParaView 10 入口通过；较大 n32 输出24 runs、
6 次精确比较覆盖19.66万体单元。1/2-rank output 相对 ASCII 中位 **−73.22%/−44.73%**，
却比现有 binary 慢，保留可选。没有多节点或并行文件系统性能结论。

源码 `ceaa680c` 的 [Core run 45748579007](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45748579007)
实际 **75/75 Release、0 failed、0 skipped、0 复用**；选测阶段六组 Python 共 **75/75** 通过。
selection、Release、receipt 三项成功，merge checkout 为 `10bfcd6e4aaa2d592791bdb67cb08ef172189233`。
[Website check 45748578957](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45748578957)
成功，但该源码 head 没有网站改动，实际安装/构建步骤跳过，不声称新增 VitePress 构建。
最终证据/文档提交再核对最新 head 的四项必需检查，不把复用的 source 执行记为重新运行。

[完整来源、失败、命令、计时及独立审计](../research/data/hpc-five-track-2026-11-26/README.md) ·
[未发布草稿](../../website/drafts/hpc-five-track-optimization.md)。本地未运行全量、Debug 或旧 PETSc。

## 2026-11-26 · FSI-PC-04：实现、参数对照与独立审计完成

从已合并 PR #53 的 `main@858f021a34ff5bd178287430d8cd45e52ec19f48` 接续，交付
[PR #54](https://github.com/saitoasukakawaii/EONSim-new/pull/54)。最终生产源码与驱动为
`88e6c3359b742735877177eb4584b987caae1790`；所有实现/修复均先同步远程，再执行构建或算例。
合并状态以 PR 的 GitHub 记录为准，不将证据/文档提交计为新数值执行。

完整联合速度块增加可选 scalar GAMG，twolevel 增加真实固体参考旋转粗空间，补齐
owned/alias/约束/空 rank 语义、main/inner/upper 配置与 Galerkin 数值更新。
`gamg+rigid` 明确拒绝：不规则 scalar 聚合上的多向量局部秩不由全局正交保证；
未实现 packed-vector 辅助空间，不声称完整向量弹性 AMG。默认 recipe/粗空间保持。

本地 a7e0 源码 **7/7** 定向 CTest 与两种新路径的实际缩步/重启通过；最终 88e6 仅补报错前
刷新、计时/取消清理，重编 eonsim 后受影响 COO **1/1**、进程控制 **9/9** 通过。
此前不受影响的代数/RCR/retry 复用本轮通过证据，88e6 本地未重跑；未执行本地全量、Debug 或 3.19.6。
最终 88e6 [源码 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45741570996)
实际 **56/56 Release + 10/10 Python**、三项 core jobs 及网站检查成功；后续证据提交不计新执行。
初始 GAMG setup 顺序失败、远端故障标记交错及 timeout 轮询计时问题均保留原件与修复依据。

最终动脉 **78/78 runs、656 接受步、1,282 次线性修正**，含 8 条完整 32 步轨迹和
30 次 `rho_s/rho_f=1/.1/.01 × dt=1/32,1/128` 对照。独立 raw/log/owned-VTU 重放通过；
最大真实残量/门槛 **0.6010255**，最大五场相对峰值差 **2.6171e-9 < 2e-6**。
另保留 a7e0 的 20 次筛选与 1ab 的 8 次中间准入，不混入最终重复计时样本。

细网格 twolevel rigid 的 32 步外迭代 **5,445→5,050**；三个四步配对 wall 变化中位数
**−10.79%**，范围 **[−13.14%,+0.44%]**。粗网格无收益，GAMG 两档配对 wall 中位数
**+5.35%/+4.83%**。两项保留可选，不作稳定普遍加速结论。
[完整来源、命令、失败与审计](../research/data/fsi-block-multilevel-2026-11-26/README.md) ·
[未发布草稿](../../website/drafts/fsi-reference-modes-and-gamg.md)。
证据仅共享单机、性能 1/2 rank、部分正确性 4 rank；不声称多节点/GPU/大规模验证。

## 2026-11-26 · FSI-PERF-03：实现、验证与性能审计完成

从已合并 #52 的 main `2dcb06c26a0359175e4f5a771d5bbff6dfc928af` 开发，生产源码及候选二进制为
`7e8868e433fb0040806a6faf3ba8cd289a2aa3f1`；带权实验驱动为 `3e366c8`，输出校验修复为 `7d86f38`。
均先推送再运行。本记录核验时 [PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53)
为 open / Draft、head `7d86f38`，尚未合并；开发与验收已完成，最终证据提交的四项必需检查通过后
按用户授权执行受保护的 head-locked squash，交付/合并状态以该 PR 的 GitHub 核验为准。

完成压力解析列与 AD 28→24、紧凑物理块 AIJ、64-cell 批次持久线程团队及异常传播、
最终验收/原始反力共用一次独立新组装、Jacobian-only 路径跳过无用残量 COO 发布。
合资格 Schur 会话支持首次切线一次性消费和后续起点延后，报告实际 J/USER 更新及 rank-local 成本；
离线分区采用稳定分桶/前缀编号、显式成本和带权身份保护，VTU 支持默认 ASCII 紧凑边界、
可选 UInt64/LittleEndian raw binary 与关闭边界。完整跨场导数、贡献次序、物理门槛和 collective 失败语义保持。
[实现与控制项](FSI_RUNTIME_OPTIMIZATION.md)。

本地 PETSc 3.23.7 Release 定向 **17/17** 通过。源码 [7e CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45711876709)
实际 **48/48 Release + 24 Python**；[3e 驱动 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45714273854)
实际 **1 Release + 21 Python**，另 **47 项复用原通过证据，本次未运行**；
[7d 输出驱动 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45715315451)
为 **0 项新数值执行 + 48 项复用原通过证据**。未将复用或文档提交计为新数值执行。

四组 FSI 性能证据 **88 runs / 880 接受步 / 1,760 次线性修正**，独立重读 968 个保存状态、
核验 8,502 条文件哈希收据及全部配对统计。最大场差 `4.440892098500626e-16`、历史差
`2.9841559419667343e-15`；初始切线消融两者精确为 0，同迭代轨迹下每次完整 J/USER **30→20**，
wall 配对中位数下降 **12.060%–25.594%**。显式 `10:5,20:1` 在本例 n=8/2 rank 的 wall 下降
**10.585%**；默认路径收益混合，COO 双线程单 rank wall 中位数 **+3.900%**，不作普遍加速结论。

输出 **32 runs** 的 84 VTU / 28 PVTU 独立解码与源网格对照通过；同紧凑边界下 binary 相对 ASCII
的 output 时间在 1/2 rank 分别 **−81.338% / −82.010%**，字节却 **+0.815% / +3.060%**。
离线 prepare **24 次**，2/8/32 分片的 **168 对 P1 HDF5** 内容对照通过；这不是 32-rank 求解或 P2 证据。
原 IO driver 的 `KeyError('reason')` 及 exit 0 / `CONVERGED_RTOL` 原日志保留，7d 推送后只重跑 output 段。
[完整来源、失败与独立审计](../research/data/fsi-runtime-2026-11-26/README.md) ·
[未发布知识草稿](../../website/drafts/fsi-runtime-cost-and-output.md)。

性能范围为共享单机、1/2 rank、三个测量配对及预热；正确性选测的部分路径另覆盖 4 rank。
各阶段 rank 最大值不能相加为 wall，输出时间不含 fsync；前两组未记录历史分区 shard 哈希的限制已保留。
本地未运行全量、Debug 或 PETSc 3.19.6，未声称多节点、GPU 或任意生产网格的普遍收益。

## 2026-11-25–26 · FSI-PERF-02：实现、验收与性能闭环完成

从已合并 PR #51 的 main `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f` 开发，
分支 `codex/fsi-performance-completion`，交付 [PR #52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)。
首轮实现 `7f3d12ed6d0a1abc67d5f5606bf644b142a3197f`，最终 COO 行分桶修复
`2b0b30bc2e1b036b8b97c9424cc6d41abd5af105`；两次均先推送、后验证。本记录不声称已合并。

完成默认 AIJ 精确物理图、局部 COO K→U 去重及行分桶、默认固定残量 COO、线性 mesh/解析面载荷移出 AD、
64 单元 OpenMP 批次、SNES/KSP/PC 与字段/诊断缓冲复用，以及 owned 约束和普通 Vec/Mat 最终装配交错。
数值 Jacobian/PC 每次更新，失败后共同销毁会话；不改变方程、时间历史、接受门槛或原始贡献相加次序。
整体 BAIJ 和 interior/halo 双阶段回调已完成适配/成本评估，当前证据下不采用。

本地 PETSc 3.23.7 Release 首轮 **13/13** 通过；行分桶后只复验受影响的 FSI 检查 **1/1**，
31 条命令含 1 个预期失败控制。源 CI：7f3 实际 **51/51 Release、65 Python**；
2b0 实际 **28/28 Release、6 Python**，另 **23 项复用 7f3 通过证据，本次未运行**，总覆盖 51 项。
对应 [首轮 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45644776027) 和
[修复 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45649236866) 及网站检查成功。

最终性能证据 **80 次运行 / 1,600 步**，含 20 次预热；另保留 32 次中间 COO 运行。
默认 assembly 配对中位数下降 **9.47%–20.34%**；最终 COO 初始化下降 **20.17%–47.72%**、
RSS 下降 **2.13%–8.89%**。细网格单 rank 的 COO 初始化回退由中间版本 +23.03% 修至 −39.90%。
默认细网格单 rank RSS 增加 4.01%；部分 wall 范围跨零，保留显式矩阵 COO/线程开关，默认单元线程仍为 1。
独立审计重读 5,040 个体 VTU、核验 13,787 份文件哈希，最大字段差 6.661338147750939e-16、
最大真实线性残量/门槛 0.00019408852157546064；每步 SNES/KSP=2/2，新版每次 19/20 步复用。

[完整源码/命令/统计/限制](../research/data/fsi-performance-2026-11-25/README.md) ·
[独立审计](../research/data/fsi-performance-2026-11-25/independent-audit.json) ·
[未发布算法草稿](../../website/drafts/fsi-performance-completion.md)。
默认和线程测量保留实际 7f3 来源；2b0 仅改 COO 初始化，未重复不受影响的性能实验。
未运行本地全量、Debug 或 3.19.6，未声称多节点、GPU 或任意生产规模优化完成。

## 2026-11-25 · FSI-ASSEMBLY-01 已合并 PR #51

从 main `f7acccb7a8239c60a2d2be193a158ac430851dcf` 开发，分支
`codex/fsi-assembly-performance`，交付 [PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51)。
生产实现及候选二进制为 `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e`；
最终性能驱动为 `b2ccd96419091c669b8dceae4369c5b255f47f57`。两次均先推送再运行；
该轮交付时为 Draft，现已核实合入 main `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f`。

最终预分配 AIJ 直接转移所有权，固定单元行列及 trace 映射缓存，融合残量与 AD 切线，
界面力重放限制到实际相邻单元；新增显式 `-fsi_coo` 压缩贡献计划，覆盖刚体和 RCR。
保留独立 test/trial 映射，逐次刷新变步长权重；物理方程、时间历史和接受门槛不变。
默认仍为 MatSetValues 装配。

df6e9ac 的 clean PETSc 3.23.7 Release 本地定向验收 **8/8 通过**，零失败、跳过或超时，
覆盖图所有权、融合单元、默认/COO、刚体/弹性/Neo-Hookean、RCR、变步长、retry 和 restart；
FSI 覆盖 1/2 rank，共享代数路径的独立流体检查包含 4 rank。
融合单元 48 个方向导数的最大相对差为 `2.23866e-10`；新增 COO 检查最大 owned 字段差为 `4.617972670928339e-13`。

b2ccd 驱动的两套网格、1/2 rank、五步成对基准共 **64 次运行、320 个接受步、640 次线性修正**，
其中 48 次测量、16 次预热。每步 SNES/KSP 次数均为 2/2；默认路径场及历史差为零，
COO 最大场差 `2.220446049250313e-16`、历史差 `1.8158547268845473e-15`。
默认 assembly 配对中位数下降 **2.72%–11.81%**，COO 下降 **30.16%–43.37%**；
COO 四组整次 wall 变化范围均跨过零，细网格单 rank 峰值 RSS 配对中位数增加 **27.81%**，故保持可选。
初始 pilot 的 wall 存在约 50 ms 等待轮询量化；b2ccd 改为阻塞等待与独立 watchdog 后重新测量，原记录保留但不进入最终墙钟结论。

独立证据重放核对 3,328 份运行文件哈希、1,152 份 VTU、384 个保存状态及全部 640 次修正，
未发现最终轨迹或配对统计不一致。b2ccd 对应的 PR merge commit
`ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0` 在远端实际执行 **55/55 项 Release 选测**通过，
无历史复用、失败或跳过；选择脚本的 **65 项 Python 检查**及网站构建通过。
[CI 来源](../research/data/fsi-assembly-2026-11-25/ci-source-b2.json) ·
[数值 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206852) ·
[网站 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206859)。

[实际命令、性能范围、独立审计与原始收据](../research/data/fsi-assembly-2026-11-25/README.md) ·
[未发布算法草稿](../../website/drafts/fsi-sparse-assembly-plan.md)。
本地未运行全套、Debug 或 PETSc 3.19.6；CI 的 Debug/3.19.6 手动 job 跳过，55 项为实际选测范围。
旧基线没有新的图初始化计时，未宣称初始化百分比加速；共享主机的小网格结果不代表多节点或长时间生产规模收益。

## 2026-11-25 · FSI-PC-03 实现与验收完成：流体响应成本与结构 nodal 近似

从已合并 #49 的 `296246e53d895f29ea3d0f7e5c960dc26b1426dc` 继续开发，交付入口为
[PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50)。
新增 `-pc_plan_structure_approx nodal`，以同一流体实体活动速度、压力的混合块逆构造
`P_s = K - G H_F E`；行列平衡、语义分组、共享 USER 矩阵刷新、失败同步及 RCR 路径均已验收。
该矩阵未显示可靠性能优势，保持实验性显式选项，默认结构 P 仍为 a11。

最终默认源码 `c4fb266edec94afbf610cb1379dd1595ed96ae40` 将 added_mass 的完整流体响应和
coupled twolevel 的速度响应改为 PREONLY 各应用一次现有 PC；保留显式 FGMRES 的原迭代预算。
完整根 Jacobian 和物理接受条件不变；结构隐式 Schur 的实际作用随近似流体响应改变，不能称为精确流体逆。

先推送后运行的本地 clean PETSc 3.23.7 Release **9/9** 通过：代数 1/2/4 rank、RCR、
三种 retry、同分区 restart 和 hybrid 物理对照，含新增刚体/弹性/Neo-Hookean nodal 与 quantity-twolevel 变体。
性能比较单独固定生产二进制 `664a623`、驱动 `66b0a62`，**72/72** 运行、12 条完整 32 步轨迹通过。
细网格三样本线性时间中位数：added_mass `44.477524 → 6.506006 s`，twolevel `3.931200 → 0.609956 s`；
外层次数增加，直接法在两套小网格上仍最快。最大真实残量/目标比 `0.5547250921`，最大五场相对峰值差 `3.1382040814e-11`。

独立重放通过 2,635 份文件、72 份日志、1,248 次线性修正、468 份体 VTU；
156 个保存状态的 780 项字段检查含 130 项直接参考自身对照。原解析器的一项漏检保留失败记录，
修复后 25/25 正负对照符合预期。c4fb266 的四项必需源码 CI 均通过：15 项新增数值运行通过，
39 项精确复用历史收据。来源另列在验证索引，不将文档提交记为新数值执行。
[配置与数学语义](FSI_BLOCK_PRECONDITIONER.md) · [收据、原始证据与复现](../research/data/fsi-block-efficiency-2026-11-25/README.md) ·
[未发布算法草稿](../../website/drafts/fsi-schur-response-cost.md)。

按本轮用户授权，合并采用全部四项必需检查通过后的 head-locked squash；合并状态以 PR 为准。
未增加全量、Debug 或 PETSc 3.19.6 验证；单机小网格证据不代表完整耦合 AMG、旋转粗模态或多节点扩展性。

## 2026-11-25 · FSI-PC-02 验收通过，已合并 #49

基线为已合并 #48 的 main `f50a4a4338689c9a065bee30ae4a7f3f52c5002e`。
在 `codex/fsi-block-completion` 完成完整流体消元的 `added_mass` FSI 树、
联合速度两层 Galerkin 校正、独立 Schur main/inner/upper 配置与故障诊断。
压力 nodal 近似保留稳定化和 RCR 项，并在同一语义子树的辅助求解器之间共享数值矩阵。
完整 Jacobian、物理残量、时间离散及非线性接受条件保持原契约。
[配置与适用边界](FSI_BLOCK_PRECONDITIONER.md) · [本轮证据与复现](../research/data/fsi-block-2026-11-25/README.md)。

最终验收 head `b52281d7585ead08e545f29f8d83eca9177e7eac` 先推送、后执行锁定
PETSc 3.23.7 Release；干净工作树的 8 项物理/恢复选测全部通过。
另精确复用 `b8ac03a` 的 `pc_plan_mpi1/2/4` 三项代数 oracle 与 `pc_recipe_restart` 通过收据，
这些不记作 b522 的本地新运行。b522 源码远端 CI 的 53 项 Release 选测、58 项 Python 检查、
选测与证据收据均通过；网站 Build VitePress 与草稿隔离检查也通过。
[源码 CI 元数据](../research/data/fsi-block-2026-11-25/ci-source-b522.json) ·
[数值与收据 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963270) ·
[网站 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963330)。

动脉管 60 次运行全部通过；其中 12 条完整 32 步轨迹的 768 次 Newton 修正通过真实残量门槛。
全部样本最大真实残量/目标比为 `0.5600385064`，最大相对场峰值差为 `1.0712628633e-11`。
两套网格的交替计时仍以直接法更快，不把新增粗校正或完整流体 Schur 等同于普遍加速。
历次代数失败、b8 物理批次 5/7、retry 线性精度诊断及未采用的性能选项均保留原证据。
为保留新增 32 步与计时覆盖增加了执行时间预算，未放宽物理或数值接受门槛。

本地实现、针对性验收和源码审查完成，PR #49 已合并至
`296246e53d895f29ea3d0f7e5c960dc26b1426dc`，由下一任务开始时从 GitHub 核实。
未运行全量或 PETSc 3.19.6；最多单机 4 rank 的证据不代表多节点生产规模、
完整耦合 AMG、旋转近零空间或网格无关收敛。

## 2026-11-24 · 弹性管瞬态、血管端口与装配

同一张 48/4/4/6 四面体网格上，两个求解器对人工厚壁管的左端面积增长给出 0.073399% 和 0.064489%。两者相差 0.008910 个百分点，即该载荷静态 Lamé 膨胀量的 4.0975%。逐项控制定位到稳定化系数、端面约束和空间分辨率。改用相同的正四面体参考度量，两个非线性程序给出 0.0646177% 和 0.0646149%，独立同网格线性 DAE 给出 0.0646137%。[分母与离散算子](../research/data/fsi-linear-transient-2026-11-24/tet-order.md)

把半径、物性和时间一起作严格相似变换，八个时刻的全场结果按理论比例复现。另用内径 20 mm、壁厚 2 mm、长度 120 mm、弹性模量 0.4 MPa 的直管作独立对照，80 Pa 双端升压下，两程序的粗网格端面扩张为 0.18680312% 和 0.18680355%。同一根管改成流量入口与 RCR 出口后，1 Hz 出口流量振幅随轴向网格由 6 层加密至 48 层，从入口振幅的 85.78% 降至 81.20%，圆形子午面参考为 80.00%。[尺度与升压](../research/data/fsi-linear-transient-2026-11-24/scaled-tubes.md) · [有均值与无均值的灌流](../research/data/fsi-linear-transient-2026-11-24/perfusion.md)

单体 FSI 支持独立的多出口三元 RCR、各出口下游压力、参考法向组织弹簧和阻尼。固定平面的出口可沿全局法轴约束并在面内变形。定流量圆形入口支持空间转向及周期采样曲线。固定网格流体压力、FSI 压力牵引和下游储液压力均可由采样曲线驱动。独立方程、接受步数据、续算、拒绝步与 MPI 对照分别归档。[端口与分叉](../research/data/fsi-rcr-2026-11-24/README.md) · [面内移动出口](../research/data/fsi-rcr-2026-11-24/planar-outlets.md) · [下游压力](../research/data/fsi-rcr-2026-11-24/reservoir-pressure.md) · [弯管](../research/data/fsi-rcr-2026-11-24/curved.md) · [组织支撑](../research/data/fsi-wall-support-2026-11-24/README.md)

接口力重算、流体/ALE 切线、结构切线、装配与 PETSc 预条件各有分项计时。解析 Tet4 矩的开发保留了前后版本的真实节点场和线性收敛记录。质量历史现复用上一个接受步体积并合并阶段与端点的归约。四十组前后配对的节点场和输出历史逐项一致。[核与装配成本](../research/data/fsi-phase-costs-2026-11-24/moments.md) · [质量历史计时](../research/data/fsi-phase-costs-2026-11-24/mass-history.md)

在 20 mm 管上，直接解与分块迭代的全场结果逐节点复核。24 扇区网格上，改用外层 MGS 后，1 和 2 个 MPI 进程的 64 次 Newton 修正均满足实际矩阵残量界限。48 扇区网格的单进程复核同样为 64/64。原版 svFSILS BIPN 在粗、细网格上分别有 92、117 次报告收敛时未达到其自身缩放矩阵的残量要求。提供了两套可直接运行的输入、PETSc 选项和逐修正原始记录。[EONSim 场分块与可运行算例](../research/data/fsi-linear-transient-2026-11-24/arterial-solvers.md) · [svFSI 的停止准则](../research/data/fsi-linear-transient-2026-11-24/bipn-residual.md)

关闭父支入口，用两端储液压力差驱动刚性 T 分叉。独立三维混合有限元逐步复现了双端流量。网格 2 上仅把固定 PSPG 系数由 0.0025 改为 0.01，1 Hz 的终端流量振幅就增加 52.31%。弹性分叉另以两个端面和壁面的带符号通量核对储量。[分叉导纳和壁面储量](../research/data/fsi-rcr-2026-11-24/junction-harmonic.md)

[#46](https://github.com/saitoasukakawaii/EONSim-new/issues/46) 的镜像核查现从实际 VTU 位移重算七个内腔截面。原场解通过，单点改值、缺截面、错位置和错时刻四个负例均失败。[复算与四个负对照](../research/data/fsi-smooth-load-2026-11-24/reflection-negative-controls.json)

本分支完成了 #46 的镜像截面复核。从两域节点场重算七个截面后，原始计算通过，单点应变加 0.001 与另外三种损坏输入均在相应检查处被识别。[原始场与负对照](../research/data/fsi-smooth-load-2026-11-24/README.md#independent-mirror-audit-of-the-bore-area) · [问题记录](https://github.com/saitoasukakawaii/EONSim-new/issues/46)

PETSc 3.23.7 Release 通过仓库脚本编译。62 项增量 CTest 均有通过记录，其中 56 项取自编译输入完全相同的干净检出，6 项取自最终日志改动后的独立运行。另有 54 项 Python 测试通过。两轮大组选测中出现过周期算例进程信号和限时退出，逐项收据保留了这些失败及其复测结果。[验证来源、退出状态与耗时](../research/data/fsi-smooth-load-2026-11-24/release-validation.md)

## 2026-11-24 · 单体 FSI 的受压面功率与第一秒面积响应

从主线 `951064d` 实现可选的阶段/终点标签历史，修复短时间步下惯性插值的消减误差。12 个 EONSim 工况完成 56 个接受步，端面压强的场重算最大差 1.22e−17 Pa。固定版本 svFSI 的独立重建重放了 0.25 s 对照，并补齐 0.125 s 阶跃响应。1 s 截面面积应变的最大程序间差在三个步长上为解析稳态应变的 5.321%、8.429%、9.028%。36 项 Release 增量检查通过，最终源码 `3697204` 的四项端面检查通过。[算例与验证](../research/data/fsi-pressure-faces-2026-11-24/README.md)

## 2026-11-24 · 网站知识选编送审

以 `5781ae0` 为内容基线，整理 34 篇技术草稿。拟展示四篇证据型专题及教程和一份 50 项开源软件指南，页面、原稿与归档见[编辑目录](../../website/drafts/README.md)。本地验证包括生产构建、公式与图表、草稿隔离、Womersley 归档复算，以及教程指定的 5 项 P2 Release 检查。网站内容通过独立 PR 审阅。

## 2026-11-24 · 开源 HPC 复查与 Tet4 黏性积分

测量基线为 `89a1a3d`，提交审阅时已同步合入 #41 的主线 `f7ec770`。数值提交 `4095e4b` 已在本地完成。PETSc 3.23.7 Release 的 9/9 项通过，独立合成 #41/#42 和新切线的圆管回归 2/2 通过。历史精细网格、外部求解器结果沿用两 PR 的归档。单进程固定网格流体单元核配对时间 −29.6%，整次墙钟 −2.6%；弹性 FSI 整次墙钟暂未显示稳定收益。[调研与后续验收](../research/HPC_UPSTREAM_REVIEW_2026-11-24.md) · [原始配对数据](../research/data/tet4-viscosity-2026-11-24/pairs.json)

## FSI-PROD-02B / 2026-11-20

基线 `89a1a3d` 已含稳态刚性管 PR #38。新增固定网格标签压力的正弦加载及接受步通量、压力历史。
48/8/12 网格的 Womersley 流量幅值误差 1.5047%，相位误差 0.2858°，波形相对 RMS 误差 1.5864%。
同网格与固定版本 svFSI 的复数流量差为解析幅值的 2.0395%，粗网格为 8.7814%。
端面压差幅值在该网格上偏低 7.58%。固定 48 扇区细化径向和轴向后，流量幅值误差降为 0.7554%，端面压差幅值偏低 5.68%。
细网格的跨程序复流量差为 1.3046%。固定 τ 的时间加密观测阶为 1.960 和 1.991。
1/2/4 进程的终点压力分量最大差为 1.11e−18 Pa。静压弹性壁对照由另一项工作提交审查。
[刚性管 PR #41](https://github.com/saitoasukakawaii/EONSim-new/pull/41) · [弹性壁 PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) ·
[复现与原始证据](../research/data/womersley-2026-11-20/README.md)

## CI-DEBUG-ON-DEMAND / 2026-11-13 / review

按用户要求改为 Release-only PR 增量数值 CI；Debug 由手动工作流专项启动。receipt 与历史复用只认 Release；自动合并改为四项必需检查并拒绝仍要求旧 Debug 的分支保护。未改数值模型、容差或 CTest 清单。源码修改不代表 CI 已通过；以 PR Actions 为准，分支保护仍需管理员确认。

## FSI-PROD-02C / review / 2026-11-20

Added radial wall refinement, analytical Lamé and coupled hydrostatic
benchmarks, full moving-volume reconstruction and a pinned external FSI
comparison. The finest isolated wall gives 0.1894% radius/area error and
0.0800% displacement L² error. The 72-sector monolithic BE solution gives
0.5684% area error. On 48 sectors the matched EONSim/svFSI equilibrium
area differs by at most 0.0000227% of the analytical expansion. The
external singular predictor and failed fine GMRES attempt are archived.
Complete step histories at 48 sectors show transient discrepancies up to
9.947% of the static expansion despite close equilibrium agreement.
[PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) · [Initial Release CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/44723204965) ·
[Equations](PRESSURIZED_ELASTIC_TUBE.md) · [Data](../research/data/lame-wall-2026-11-20/README.md)

## FSI-PROD-02 continuation / in_progress / 2026-11-07

Continued the same `codex/fsi-tube-qualification` branch from `92d63f1`, main
`dc37852`; PR #38 remains open. Source `4113ab8300410459dbfb057db5d4978e7d106aa7`.
Restored locked PETSc 3.23.7 in an 8 GiB Linux container. Added exact pressure/velocity
field and local divergence diagnostics, plus a seed-mesh runner. Five actual serial
solves: 96/12/24 sectors/radial/axial gives flow error 0.546409%, velocity L2 0.320760%,
pressure RMS/drop 0.489014%, end-pressure-drop error still 5.140012%. A 96/8/16
1/2/4-rank comparison has maximum field difference 5.31e-16. These isolated results
are not full PROD-02 acceptance; Womersley, elastic walls, default transient tau,
svFSI, error budgets and full review remain pending. No new PR or merge.
Release tube regression 1/1 and Python 6+3+26 checks passed; historical Debug
results reused, not rerun. Root MPI rejection and initial test-oracle arithmetic
mistake are recorded. [Evidence and replay](../research/data/rigid-tube-seeds-2026-11-07/README.md).


## FSI-PROD-02A / PR #38检查通过 / 2026-11-06

PR #36、#37 已合入 main `dc378529538259567a78cea9820a202a6187809c`，下方review为历史。
分支 `codex/fsi-tube-qualification`、实现 `a0d228764850fa838229acb6a6e613933070490f`：
同一流体标签的互斥分量混合边界、几何不变的四面体加密和刚性稳态流量基线。
11个串行状态和1/2 rank对照；48边形流量误差1.264676%，12/48边形末档变化
0.410813%/0.024769%，MPI场差2.78e-17、最大净通量4.12e-17。首轮level-2未通过，
保留原结果、门槛不变，追加加密后通过。压强误差仍3.993089%，仅完成流量增量，
PROD-02整体未完成。Debug三项、Release最终两项+复用首轮regions、Python3+26项通过。
[完整证据](../research/data/rigid-tube-2026-11-06/README.md)；
[接口/复现](RIGID_TUBE_QUALIFICATION.md)。本地验收与自审完成；
[PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38) 已创建，待审查，未合并。
云端PETSc3.23.7 Debug/Release各26/26、Python35项、网站与增量证据检查全部通过，
数值测试零失败/零跳过；[云端记录](../research/data/rigid-tube-2026-11-06/cloud-ci.json)。

## FSI-PROD-01 / review / PR #37 / 2026-11-06

用户目标升级为生产级 FSI。主线 `dd27eef` 已合并 PR #36；下方旧 review 状态为历史。
独立分支 `codex/fsi-production-tube` 实施圆形离散流量入口与共形实体壁圆管，
验收包含三时间格式、1/2/4 rank、质量/界面/正几何、同分区恢复与非法输入。
源码远端 `718b7a6` 与本地 `31a04e6` tree 完全一致。仓库脚本/PETSc 3.23.7
Debug/Release 各两项受影响检查通过（tube 与旧 rectangle flow），网格2项、CI选择26项通过。
最大1/4 rank场差5.43e-14，续算差0，质量残差1.56e-17，Jacobian差9.92e-9。
首次负例预期错误及Debug OpenMP启动失败均保留；PID隔离后完整Debug tube通过。
[本阶段证据](../research/data/fsi-tube-2026-11-06/README.md)。本地验收与自审完成；[PR #37](https://github.com/saitoasukakawaii/EONSim-new/pull/37)
已创建；[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42170183765)
Debug/Release 各31/31通过，零失败/零跳过；网站与增量证据检查通过。
源码/证据head `29d8082` 的合并预览 `92a28b5` 与本地验收tree完全一致。
本阶段完成、待人工审查合并；不自动合并。
[生产路线](FSI_PRODUCTION_ROADMAP.md)；[接口和算例](FSI_CIRCULAR_TUBE.md)。
下一阶段为定量圆管/默认稳定化资格，再到 RCR/外壁支撑、实际几何与多节点规模。


## FSI-QA-01 / review / 2026-11-06

PR #35 已由远端合并，基线为 `815755eb15ffb63299487e8f9163ddc9d242a2f2`；下方“未合入main”为历史。完成有界修复 FSI-QA-01：质量预算拒绝非有限初始状态、非正体积/接受步长及累积算术溢出，源码 `80571b102e31dd2e7664a64a39a92efc8402045c`。26项相关Python检查通过；9组归档时间研究的22400条接受步重新分析，36个预算值与原收据精确一致。未重跑C++/PETSc/MPI求解；默认τ数值资格仍未完成，不改变原数值结论。独立分支 `codex/fsi-mass-history-validation`，尚未合并。


## FSI-NEXT-03 / PR #35验收通过 / 2026-11-05

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。

下列FSI-NEXT-03尚未完成/未创建PR描述为历史检查点，不覆盖本节状态。


## FSI-NEXT-03 恢复计算

2026-11-04 已从远端 a67f329 恢复同一分支，核对 main 仍为 4f3a995。默认三网格归档逐文件校验通过（923/743/678 个文件），重新审计 8600/5000/3700 条接受步。使用仓库 restore.sh 和 run.sh 恢复 PETSc 3.23.7 Release，所得可执行文件 SHA-256 为 b4de28ffc6481701b533ec4772f4f0f604cfc18bc15bc63c858ebebae38352da。单一 MPI 队列的 fsi_periodic、fsi_flow、fsi_inlet、fsi_pressure_state 均通过。旧固定 τ 算例缺少原始场和 checkpoint，固定 τ=.05 的三网格与两步长研究从初态重算。完整误差预算、证据审查及 PR/CI 仍待完成。

## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 三网格周期状态已取得，预算验证继续

默认稳定化n=2/4/8分别在86/50/37周期达到完整场连续三周期判据；独立补查的压降三周期判据、无滑移/界面相容和完整接受历史质量/几何检查通过。20相位初步空间场差均递减，实测阶0.81–2.29，不能宣称全场二阶或已进入统一渐近区。三个状态的可恢复归档均逐文件SHA核对通过。

新Release构建对n=8完整周期重放，最大字段相位RMS差3.83e-14（门槛2e-9）；Release相关7/7通过。随后增加源码指纹和精确压降相位检查，已排入单项控制器回归。n=4/n=8追加周期、三网格半步长和100相位正式预算继续；无PR，整体未完成。

## FSI-NEXT-03 当前连续验证

已保存远端检查点 `4119d86`；此后补充完整接受历史终点校验、100相位正式误差预算审计和可恢复证据归档。时间矩阵原数据经完整性加强后重新分析通过。n=2三个追加十周期块完成，经验收缩率0.54–0.57；n=4追加计算继续，n=8第35周期首次通过完整场阈值，尚不构成连续三周期通过。n=2归档923文件SHA逐一核对通过。半步长三网格、剩余误差预算、最新负例回归和最终审查仍未完成，无PR。

## FSI-NEXT-03 时间精度与质量预算已验证，空间研究继续

本地基础提交 `96f232f`，后续改动尚在同一分支实施。三格式完整第二周期的时间精度矩阵已通过：BE 最小受检阶0.864，BDF2 1.882，generalized-alpha 1.981；参考加密差占最小候选误差3.17%–3.21%。累计质量预算的最大误差阶分别约1、2、2。它们是固定tau、n=2的瞬态验证，不替代稳态空间研究。原始配置、压缩CSV/日志和第二周期场已归档 `docs/research/data/fsi-next-03/time-accuracy-final/`。

新增可选 `fsi.checkpoint_interval`，默认仍每个接受步保存，指定停止点/最终接受步必保存；周期研究仅需每周期保存。仓库编译脚本完成 Debug 7/7 受影响回归，证据 `cadence-debug/`；后续纯Python相位采样/压降检查仍继续针对性验证。默认稳定化n=2已在第86周期通过，n=8仍在运行；从已收敛状态追加周期的瞬态估计和真实100相位输出复核正在实施。没有创建PR，也未声称48小时预算耗尽。


## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

更新时间：2026-11-03（Asia/Shanghai）

## FSI-NEXT-02 已合入检查点 / 2026-11-03

实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，基线 main `b2755b6`，独立分支 `codex/fsi-next-02-periodic-flow`。周期离散总流量入口、无滑移弹性壁通道与独立表面/体积质量诊断已实现，本地验收和自审完成；[PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 已合入 main，合并提交为 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`。
[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) PETSc 3.23.7 Debug/Release 各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。Debug/Release 新 flow 各1/1与旧入口/压力各2项通过；三时间格式、1/2 rank、恢复、非法输入、整体Jv、真实9次缩步重放及零形状拒绝均有证据。
Release 六周期、三网格/三步长最大阶段质量残差3.08e-16；累计体积误差随dt减小。空间渐近收敛及严格周期稳态尚未证明，不作性能或大规模结论。[能力说明](FSI_PERIODIC_FLOW.md)、[完整验收与失败记录](../research/data/fsi-flow-2026-11-03/README.md)。

## 历史集成交付：G0B → G0 → G5 → G1 已合入 main

[PR #23](https://github.com/saitoasukakawaii/EONSim-new/pull/23) 已合并，main实现提交
`9cc2e102e8e32f929de1c9a790c1ae527b931fa2`，功能分支最终源码`9e5a1eddf06a02f5e64201d3eff2d55638ddbf13`。
G0B/G0/G5/G1及本整体任务完成；INFRA-01最终集成验收也已补齐。

- DoF语义、独立代表/重建、owned/ghost、存储、物理验收与PC树分离；physics/quantity/hybrid真实PETSc路径验收通过。
- BE、变步BDF2、一阶/二阶generalized-alpha接入各适用独立场、ALE和单体FSI；共同stage、完整链式切线、accepted历史、拒绝与checkpoint已验证。
- Gmsh2.2/4.1 ASCII规范化、Tri3/P1、Quad4/Q1及相容混合二维Poisson/扩散、命名材料与D/N/Robin、纯Neumann、并行分区/输出/重启闭环完成。
- 用户授权WSL2本地Debug/Release各60/60、兼容锁13/13；最终源码109份哈希由独立审查逐份核对，所有测试无失败/跳过。
- [PR云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182613)同样60/60/13通过，
  [push CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199162462)成功，
  [网站及草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182529)成功。
  GitHub合并预览tree与功能提交完全一致；[交付证据](../research/data/fem-integration-2026-10-31/delivery-ci.json)。

用户入口：[DoF与PC](DOF_AND_PC_GROUPING.md)、[时间支持矩阵](TIME_INTEGRATION.md)、[二维标量](SCALAR_2D.md)、[完整验证记录](FEM_INTEGRATION_VALIDATION.md)。
验证最多4rank；没有生产存储重排、二维流体、三维混合体或跨分区重启。G2/G4只实施必要子集，其它阶段仍deferred。
G0性能72样本对应原检查点，小问题直接解更快；没有新的G1性能结论。知识文章保留website/drafts，不发布。
后续只能按具体需求领取新任务，不能把本任务完成解释为G0–G8全部完成。

## 项目基线

- 仓库：saitoasukakawaii/EONSim-new
- 当前 main：`4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`（FSI-NEXT-02 / PR #33 合并提交）。各历史任务的原始基线与证据仍按对应章节保留。
- 软件：C++17、MPI、PETSc、三维 Tet4/P1 多物理场及 Tri3/Quad4 二维标量有限元求解器。
- 已交付主线：P0–P8 与 B0–B5 小算例基线；不代表已完成大规模生产扩展。
- 公开知识网站：website/，VitePress；只有合并到 main 的正式栏目内容进入生产网站。

## 当前研发状态

| 工作流 | 状态 | 说明 |
|---|---|---|
| EONSim 核心求解器 P0–P8 | 已交付基线 | 当前已验证最多 4 MPI ranks，不等于大规模生产验证 |
| 网站与知识生产基础设施 | 已合并 | PR #2、#3、#6 |
| PETSc 生命周期与多步 setup 基线 | 已完成 | PR #4、#7、#8；持久化 NonlinearSession 暂缓 |
| 重复线性求解 KSP 所有权 | 已修复 | PR #9；成功、失败、恢复及 1/2 rank 回归通过 |
| Newton 缩放规格 | 已完成审查 | PR #10；可选完整坐标缩放仍 deferred |
| Schur/GAMG 网格测量 | 已完成 | PR #11；小规模结果不外推大规模性能 |
| 求解器层级算子尺寸 | 已实现并合并 | PR #12；Release/Debug 针对性测试通过 |
| 非线性装配阶段计时 | 已实现并合并 | PR #13；增加 callback、错误同步、最终装配和约束阶段计时；已有 HPC-01B/C 重复测量 |
| 独立流体缓存 COO Jacobian | 已实现并合并 | PR #21；范围及验证局限见 HPC-02 报告 |
| 通用 FEM 与 20 组上游学习规划 | 文档已集成 | 16 份 Markdown 随设计分支合入；G0B/G0/G5/G1已交付；其它阶段仍deferred，按需依赖子集除外 |
| FEM-G0A DoF/FSI 分块详细设计 | 已审查合入 | [专题](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)、标准库参考模型及 20 项测试交付；无 C++ 接入或数值验收 |
| 可复现云环境与 MPI 故障 CI | 已随 PR #23 完成集成验收 | 最终主锁 Debug/Release 各60/60、兼容专项13/13；证据见 FEM_INTEGRATION_VALIDATION.md |
| G0B/G0语义DoF与三recipe | 已合入 main（PR #23） | DoF语义、物理验收与三种PC树已完成集成验证；不代表生产内存重排 |
| PETSc CI 与持续知识积累规则 | 已合入 main（PR #24） | 日常仅 PETSc 3.23.7 Debug/Release；3.19.6 手动专项；AGENTS 与状态/知识文件同步更新 |

## FSI-NEXT-01 及此前任务的历史检查点

FSI-NEXT-01：基线 `06b05c4`，分支 `codex/fsi-inlet-reliability`，生产实现 `0d93d41`/`69692ee`，最终研究脚本 `32783a5`。固定非零速度入口、弹性顶壁、分布式面积观测与阶段/终点几何检查已完成。本地 PETSc 3.23.7 Debug/Release 各 5 项（4 项主检查 + 1 项旧弹性体补验） 定向检查通过；分场时间研究通过，空间轨迹的时间差/最后空间差为 9.51%；Release 性能完成 10 预热 + 30 正式样本，最多 4 rank。小网格直接法更快，较大网格分块内存更低但无稳定加速结论。已通过 PR #32 合入 main（merge commit `b2755b6`）；此处保留其实现/验证来源和历史测量边界。见 [能力契约](FSI_INLET_AND_RELIABILITY.md) 与 [验收记录](../research/data/fsi-next-2026-11-03/README.md)。

FSI-LOAD-01 已通过 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31) 在远端合并为 `06b05c4`，本 agent 未执行合并。实现 `a6c6761` 的平滑周期压力、共同阶段取值、缩步/签名和接受步历史已交付；原云端 Debug/Release 各 24/24 与网站通过证据仍见 [验收记录](../research/data/fsi-pressure-2026-11-03/README.md)。本轮只重跑受影响的 `fsi_pressure_state`，其余复用历史通过证据，本次未运行。


FEM-G2C 已获用户授权执行，基线 main `1bc87a7`，分支 `codex/p2-transient-diffusion`。目标为 P2 瞬态扩散三种时间格式、完整历史恢复及接受步输出；完成验收后创建 PR。实现 `d19a032` 已完成；本地 Debug 分项与 Release 五项 P2 检查、8 项双 rank 历史故障补验通过。[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 云端 PETSc 3.23.7 Debug/Release 各 15/15 相关检查通过，网站及草稿隔离通过，任务 done，已由远端合并为 `dff9116`（本 agent 未执行合并）。证据见 `docs/research/data/p2-transient-2026-11-03/`。

FEM-G2B：基线 c0745ea，分支 codex/p2-boundary-extension，源码 d6ec424；P2 Robin 与纯 Neumann 已实现，本地 Debug 1/2 rank 相关验证通过，[PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28) 云端 Debug/Release 各 10/10 相关检查通过，已合入 main（1bc87a7），复用历史验收，本次未重跑。

FEM-G2A 已合入 main（c0745ea），原实施基线 main `35bf1a1`，分支 `codex/fem-g2a-p2`。代码 edfc73c 已接入共享边空间、HDF5 分区、P2 稳态 D/N 求解及二次 VTU/PVTU；本地 Debug 1/2 rank 数值验证通过，[PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) 云端 Debug/Release 各 19/19 相关检查通过，任务 done，2026-11-01 已合入 main（c0745ea）。PR #26 已合并；下述待审描述属于合并前检查点。

CI-INCREMENTAL-01 已通过 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 合入 main（merge commit `35bf1a1`）；分支 `codex/pr-incremental-ci`，实现提交 `8f695cc`，含约束提交 `ef20e03`。自动数值 CI 仅 PR 选测，文档/证据后续提交可复用同 PR 成功记录；全量仅手动显式选择。云端首次 Debug/Release 各仅 poisson_verification 1/1 通过；文档提交 `0072295` 的第二次运行实际零构建、零数值测试，完整继承原来源，见 [首次验收](../research/data/ci-incremental-2026-10-31/initial.json)与[复用验收](../research/data/ci-incremental-2026-10-31/reuse.json)。本地 24 项选测/receipt 测试与 6 项证据解析通过，另补 2 项手动入口测试通过；未运行全量、旧锁数值测试或本地求解器构建。该策略已随 PR #26 合入 main 后生效。

DOCS-01 已通过 PR #25 合入，合并提交 `be21882`；G0B/G0/G5/G1 与 PR #24 工程策略保持已交付。当前 main tip 以 Git 为准。
CI-INCREMENTAL-01 将日常数值 CI 改为 PR 选测的 PETSc 3.23.7 Debug/Release；3.19.6 仍仅手动兼容专项，main 上生效以合并为准。合并状态由本地 Git 历史确认，本次未查询 PR #24 的远程 Checks，不能据合并推断其逐项测试结果。

DOCS-01 的开发分支 `codex/markdown-progress-audit` 已合并；范围、逐文件处理与静态验证见 [文档审查记录](MARKDOWN_AUDIT_2026-10-31.md)。

此前 TEST-POLICY-01：仅修改验证约束，不开发、不编译项目。基线 `3df1c31`；约束提交 `ef20e03` 已随 PR #26 合入 main（`35bf1a1`）。默认仅检查新增或受影响行为，历史已通过且未受影响的测试不重跑；全量仅在用户明确要求时运行。规则见 [构建与验证](BUILD_AND_VALIDATION.md)。该文档任务未运行构建、数值测试或 CI，也未修改工作流；后续 CI-INCREMENTAL-01 承接自动选测实现。

## 最近完成

- BRANCH-02：审查合入 FEM-G0A 分支，清理 7 个已整合的非主分支；本次按用户明确授权直接合入 main。
- FEM-G0A：详细设计、代数参考模型与 20 项测试已合入；没有新增生产 C++ 能力。

- PR #21：HPC-02 独立流体可选固定 COO Jacobian；原测试和测量范围以报告为准，本轮未重跑。
- ARCH-01：通用 FEM 架构与学习路线 16 份文档已集成；未发布知识草稿，非实现完成声明。
- BRANCH-01：删除已完全合并的 18 个远程分支，审查整合其余 6 个；按用户明确授权直接合入 main，来源 CI 分支已有 PR #22，本会话未新建 PR。
- INFRA-01：整合时修正锁定 ABI 范围和 JUnit 完整性；当时未完成的最终数值验收已由 PR #23 补齐。

- PR #3：持续研发进度、任务队列、会话日志、知识模板和采集 Skill。
- PR #4：PETSc 对象生命周期源码审计。
- PR #6：Codex Goal 工作流说明及任务状态同步。
- PR #7/#8：非线性诊断开销和多时间步 setup 基线；持久化 NonlinearSession 暂缓。
- PR #9：重复线性求解 KSP 所有权修复。
- PR #10：Newton 缩放规格及独立代数验证；未实现完整求解器缩放。
- PR #11：Schur/GAMG 小规模网格测量。
- PR #12：求解器层级 A 算子 global/local 行列数报告。
- PR #13：非线性装配阶段计时。Release 3 项、Debug 2 项针对性测试通过；未运行重复性能基准。
- PR #24（已合并）：PETSc 3.19.6 从日常矩阵移出；新增持续知识积累项目级规则。

## FSI-NEXT-01 合并前检查点（历史）

FSI-NEXT-01 本地实施与数值研究完成，源码/脚本 `32783a5`；PR 与云端选测状态后续补记。
当前 main 为 `06b05c4`；未运行全量或历史锁；知识文章保留草稿。

### DOCS-01 历史检查点

- 源码基线：`a508e3d`；PR #24 已合入，旧 `codex/primary-petsc-ci-policy` 不再是当前待交付任务。
- DOCS-01 已通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合入 main（`be21882`）。
- 本地只做 Markdown 静态检查；远程 [PR 数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324586) 的 3.23.7 Debug/Release 各 60/60 通过，无失败/跳过；3.19.6 job 按策略 skipped。
- [网站构建与草稿/模板隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324560) 通过；草稿仍未提升为正式文章。无新性能实验。
- PR #23 的 60/60/13 为归档验证，不作为本次新运行结果；实际测试 inventory 随源码/构建配置读取。

## 恢复规则

每个新 Codex Task 开始时：
1. 读取 AGENTS.md、CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md 和当前任务相关契约。
2. 检查 main、当前分支、工作区和未合并 PR，避免重复任务。
3. 只领取一个 ready 任务；若没有 ready 任务，先提出候选，不擅自扩展范围。
4. 每项实质开发任务结束时，按 AGENTS.md 更新进度、队列、会话日志和知识索引；无可复用技术成果时不创建文章。
5. 重要改动 commit/push 到独立分支；通过 PR 审核，不直接推送 main。
6. 有复用价值的知识写入 website/drafts/，人工审核后才发布。

Goal 使用说明见 CODEX_GOAL_WORKFLOW.md。Goal 负责当前线程内的多轮执行；GitHub 状态文件负责跨 Task 接续。

## 更新规则

- 只记录已确认的代码、测试和审核状态。
- 未运行的测试和性能实验明确写“未运行”。
- 不把计划、推断写成已实现或已验证。
- 任务合并到 main 后才将队列状态标为 done。
- 每项实质任务记录源码提交、实际测试命令和结果；未运行或未验证的项目明确标注。

