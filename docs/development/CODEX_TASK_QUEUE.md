# EONSim Codex Task Queue

B20 的可选粗层通信配置已完成同精度三对。其他网格继续以自身参考核验，A20 跟踪代表网格退化界限，C20 待独立资格后再开展通信比较。[B20 通信基线](FSI_SCALABLE_05.md#固定精度的真实管-gamg-粗层通信)

FSI-SCALABLE-05 沿用冻结物理输入，按各自资格跟踪 C 长窗、真实网格通信实验及 svFSI。B20 固定档已选定，旧严格残量失败仍可重放。[阶段收据](FSI_SCALABLE_05.md)

FSI-SCALABLE-04 的结构内部关联舍入可达性及 B 的严格参考保留为 STRICT-v1 研究项。首系统回放已有按块量化及原式残量证据。[数据与复跑](FSI_SCALABLE_04.md)

FSI-SCALABLE-03 继续跟踪 B 首校正的结构块误差、C 的独立 20/32/100 步、B/C 原版对标、物理网格强扩展及七周期资格。B/C 的原始矩阵、右端、行映射和校验值见[第三阶段收据](FSI_SCALABLE_03.md)。

FSI-SCALABLE-02 位于 [#70](https://github.com/saitoasukakawaii/EONSim-new/pull/70)。小管外部对照已有资格。跟踪 B/C 资格、owner 本地字段消融、粗层归约、固定 rank 迭代增长和强扩展。运行状态与指标见[第二阶段报告](FSI_SCALABLE_02.md)。

2026-11-27 核对：主线已合入 #65（`2463f717`）；以下历史记录保留实际执行日期、源码、失败与验收边界。当前能力与开放目标见 [当前能力矩阵](CURRENT_STATUS.md)。历史 review/Draft 不代表当前 PR 状态，历史证据不计为本次执行。

## FSI-SCALABLE-01 · 规模与优化实测

基线、具备独立直接参考的小 FSI、近似及联合压力空间、粗层通信器选择和单节点扩展证据已建立。128 rank 的最大合成规模为 1,259,907 自由度。网格无关迭代目标与强扩展速度门槛仍开放，五十万及百万网格保留完整强扩展矩阵任务。下一批按[本轮证据](FSI_SCALABLE_SOLVER.md)审计高 rank 的 PC 应用求解和归约。分布式网格前处理、一般跨分区重启以及混合精度层级复用各保留独立验收。

## FSI-SADDLE-01 / implementation and bounded validation complete; convergence and scale OPEN / 2026-11-27

基线 `main@036f865e`（#64），最终生产/驱动 `ccf1bd7b3727a6b3ddd3a85954a3a78c51a652ba`，交付
[PR #65](https://github.com/saitoasukakawaii/EONSim-new/pull/65)。十三项方向已有实际实现和对应证据；
执行顺序为源码/修复同步 → 核对 tree → Release 定向与真实 FSI 验证 → 原件归档 →
四项必需检查及锁定 head squash 合并。最终检查/合并状态以该 PR 记录为准。

最终源码新执行6项MG/smoother及12条Braess轨迹全通过；不同CTest有效集合17项、
新增物理配置48条、网格18条全通过，按原执行源码分源复用，不重跑无关路径。
初版失败、正确重建的审计误判、局部LU极小主元、Braess迭代耗尽及单因子修正均归档。
原严格残量与 `2e-9` 保存场/历史门槛保持；[完整证据](../research/data/fsi-saddle-01-2026-11-27/README.md)。

仍开放：预声明的703/2299/5367 DoF窗口平均迭代增长比≤1.3；当前colored=1.7857、
all=1.7037，均未达标。all压力闭包饱和并增加建层/RSS成本；不能从迭代减少推断总耗时下降。
百万自由度、多节点、扩展效率、普遍inf-sup界及完整harmonic-Ritz GCRO-DR均没有完成证据。
后续应针对粗化效率和实际工作量推进，不放宽门槛、不用无限参数扫描或默认全量测试替代证据。

[最终源码 CI 45931896224](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896224)
实际新执行 **83/83 Release、54/54 Python**，没有复用数值记录。合并预览
`75bb86a0c5e668d497d0e95eb5ed0be4df824550` 与 `ccf1bd7` 的完整 tree 均为
`014a1de3199b7e476aec00aa63078a13adb60610`，dirty=false；
[源码网站检查 45931896258](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896258)
通过。远端检查与本地分源轨迹分别计数；最终文档 head 的四项检查及合并以 PR #65 为准。


## FSI-SCALE-01 / implementation and bounded validation complete; convergence and scale OPEN / 2026-11-27

北京时间记录，任务起始于 2026-11-26；基线 `main@88257a9`（#63），分支
`codex/fsi-scalable-matrix-free`，对应 [PR #64](https://github.com/saitoasukakawaii/EONSim-new/pull/64)。
十二项方向已有实际代码或规模验证入口，最终生产/驱动 `50b41ae19067bd8853a482ab853805e23c096ec5`。
每批源码及修正均先推送并核对 tree，再构建、运行；**最终文档 head 的四项必需检查及锁定 head 合并结果由 PR #64 记录确认**。

最终本地 MG 1/2/4 rank **3/3**、Python **19/19**、严格网格 **9/9** 与最终物理
**15/15** 通过，原物理/约束、严格真残量、inexact 当次 forcing 及 `2e-9` 场差门槛保持。
`30e2941` 的 MG/patch/smoother **9/9**、K-cycle 网格及 native RSS pair 分源复用，
未伪称最终源码重跑。失败、缺诊断、真实残差缺陷、RSS 负例和中断均保留在
[证据索引](../research/data/fsi-scale-01-2026-11-26/README.md)。

仍开放：固定 703/2299/5367 DoF 窗口，supremizer V 总迭代 92/138/199，平均最大/最小
**2.1630 > 1.3**；优化 V 为 2.3402，历史 K 为 2.0612，近似网格无关 **OPEN**。
最大实测 **10,387 DoF / 单 host**，百万 DoF、多节点和扩展效率 **OPEN / 未运行**。
native 在 `116836b` 的 RSS 负例经 `30e2941` 修复后仅有一次同源 pair 最大 rank 峰值
降低 4.0557%的证据；稳定端到端、总内存及带宽收益仍须按规模实测，不能由数组字节推断。

[源码 CI 45853312807](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312807)
实际 **4/4 Release、19/19 Python**，另复用 62 项 Release、总覆盖 66；预览
`3ca62ae4c0c037ca59c255fc8cd1754f1101f7ea` 与源码的完整 tree 均为
`7f66c8b02d62ed67606f7bf5f94fd5af34915f6e`。
[源码网站检查 45853312823](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312823)
成功，最终文档 head 检查/合并待办；不绕过保护、不增加参数扫描或全量验证。
[运行指南](FSI_SCALABLE_MATRIX_FREE.md)与[未发布草稿](../../website/drafts/fsi-scalable-matrix-free.md)
记录选项、数学范围及后续真实规模验收入口。

## FSI-MF-02 / implementation and bounded validation complete / 2026-11-26

从已合并 #61 的 `main@6bb6f438b63c` 接续，开发分支 `codex/fsi-mg-performance-followup`。
交付 [PR #62](https://github.com/saitoasukakawaii/EONSim-new/pull/62)，生产/测试源码 `b7d727b`。
固体与壁支撑直接精确方向核已接入，取消 matrix-free 每次作用中的完整局部切线；
整体 MG 每个非粗层利用已知零初值省去一次残量矩阵乘及 halo 通信。原方程、装配路径、
门槛与默认选项保持。先同步完整 tree，后增量构建；4/4 定向 CTest、11/11 物理解通过。
另有 9 次固定输入成本对照（1 直接参考、2 warmup、3 对旧/新二进制），不与 11 次混计。
局部核耗时中位降低 75.75%–82.08%；350 DoF/2-rank 的 MF 作用阶段中位降低 23.27%，
外层迭代均155。wall未见稳定收益。[原件与测量范围](../research/data/fsi-mf-02-2026-11-26/README.md)。
仍开放：更大真实 FSI 的近似网格无关、完整 P 存储成本、稳定端到端收益与多节点扩展。
已通过的未受影响检查复用原证据；本轮没有扩大为全量或无边界参数调优。

## FSI-MG-01 / twelve implementations and bounded validation complete; broader performance remains open / 2026-11-26

[PR #61](https://github.com/saitoasukakawaii/EONSim-new/pull/61)完成全部十二条 P0/P1/P2 路径，
最终生产 `3b5cbdd`，每次修改先同步远端并核对 tree，再构建及验证。完整耦合层级、每层
混合 Vanka、结构顺应性压力 Schur、能量插值、局部谱增强、PCD 两增强、批量缓存、
Chebyshev 两变体、真实 FP32 稀疏循环、粗层聚合、PIPEFGMRES 和精确 MF/assembled P
均有实现与有界验收，参数见[操作指南](FSI_MONOLITHIC_MULTIGRID.md)。

本地有效 22 项 CTest 中最终重跑 12 项、10 项复用未受影响证据；最终 28 次 FSI、84 步、
177 真残量全部通过原门槛，累计 64 成功与 4 个已修复 setup 失败分别保存。缓存失效、
读锁、流水线归约和粗 patch 四类故障已闭环；[原件及独立审计](../research/data/fsi-monolithic-mg-2026-11-26/README.md)。
源码 CI45819157827 实际 95/95 Release、54/54 Python，成功收据与同源 tree 已核实。
最终文档 head 四项检查及精确 head squash 以 GitHub 为准；没有跳过保护或改数值门槛。

仍开放的性能目标：更大真实 FSI 的近似网格无关、低总内存和稳定端到端收益、多节点通信
扩展。现 703/2299/5367 DoF 的 MG 迭代 104/151/206，直接解更快；FP32 只证明部分
值/因子精度与字节变化，整体 RSS 和时间没有下降。局部谱筛选并非全局误差学习，PCD 仍
要求统一正黏度，MF 保留完整 P。不得用十二条代码路径完成来宣称这些性能目标也已完成。

## FSI-PC-05 / implementation and bounded validation complete; performance goals remain open / 2026-11-26

[PR #59](https://github.com/saitoasukakawaii/EONSim-new/pull/59)交付递归field AMG、稳定化
LSC/BFBt与物理PCD、真实界面mixed patch、FP32因子/FP64细化回退。最终生产/驱动19cd26f，
每次源码均先同步远端再执行。空owner collective与PCD边界质量极限两个实际缺陷已修复并
用独立负控/1–4rank验证闭环；最终PCD38求解108步225修正独立审计全通过。

[证据与失败记录](../research/data/fsi-advanced-2026-11-26/README.md)区分初始20、研究60和
最终38；未受修改影响检查复用，不伪称全在最终head重跑。四项必需检查和锁定head合并
依GitHub核实；草稿未发布，默认不改。

本节保留 FSI-PC-05 的历史验收边界；其中逐层 smoother 和 PCD Robin/速度质量增强现由
上方 FSI-MG-01 完成。其余仍开放目标为真实 FSI 近似网格无关、变黏度、多节点更大规模
和稳定端到端收益。FSI-PC-05 当时的网格2rank nodal82→131、最终PCD
144→225；BFBt六组patch少2.44%–11.96%迭代但小例成本高，FP32只证明因子数组减半。
不能把“代码路径实现”当作这些尚未达成性能目标的关闭依据。

最终源码CI45787454655实际85/85 Release、54/54 Python通过，成功receipt与
merge-preview/source tree一致性已核实；未放宽门槛或改变保护。

## RCR-PC-01 / implementation and validation complete / 2026-11-26

[PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)完成用户要求的六项P0/P1：完整
RCR端口Schur、单/多出口低秩响应、GAMG/BoomerAMG组合、端口层单次合并归约、同代
缓存与自适应更新。最终生产源28e6d54、FSI驱动ad08887；每次源码/驱动修复均先同步远端。

本地32项Python、旧4项代数/自适应通过；新1/2/4rank代数修复后3/3、真实FSI1/1通过。
13runs/43步，96个实测真残差全部满足原门槛；114 Newton总数另含直接参考18次。
独立原件回放及683项归档摘要通过；最大场差7.57780e-11，adaptive刷新/复用8/4。
失效缓存read-lock与变步长终点测试错误的失败原件、修复及复验分开保存。

[完整证据](../research/data/rcr-port-2026-11-26/README.md)。最终源码CI45776829333实际
65/65 Release、54/54 Python通过，0数值跳过/复用，成功receipt已独立核实并归档。
最终文档head四项检查与精确head合并以GitHub为准。原默认路径保留，新开关显式选择；
单/双出口GAMG迭代145→144/53→53，不宣称普遍性能或多节点规模收益。

## HPC-07 / implementation and validation complete / 2026-11-26

从已合并 #56 的 `main@55a04f7` 接续用户要求，交付
[PR #57](https://github.com/saitoasukakawaii/EONSim-new/pull/57)，源 `4c7edc6`。
完成固定节点逆 COO 图/值缓冲复用、FSI overlap 单次场展开与空线程批次消除，以及
HDF5 独立对照的拓扑/长度/重复身份/数据集绑定拒绝。完整 Jacobian、节点逆数值检查
及原物理接受门槛保持。代码完整远端 tree 核对后才构建和运行。

本地4项Release（1/2/4rank）、30项Python通过；37次FSI求解包含34正常、3预期失败，
83接受步与24组字段/历史对照已独立复核。HDF5校验器14次旧文件精确回放通过，未
重新生成物理输出。16次配对实验/80步/160修正/96状态通过，场和历史差为0；线程批次
58→29、矩阵清零少9次，但全程序装配事件没有减少，wall波动仍跨零。

首轮CI42/43，唯一失败是MPI日志前缀拼接引发的测试解析误报；测试修复8e6c013先同步，
再通过8项Python和1项FSI定向复验（37次求解）。生产与数值门槛保持，失败原件保留。
最终8e6c013的CI45769962561实际43/43 Release、44/44 Python，0失败/跳过/复用，
增量验收收据成功；两组绿色CI和首次失败原件均归档。

[完整证据](../research/data/hpc-followup-2026-11-26/README.md)。源码CI与最终文档head
的四项必需检查通过后按用户授权合并，状态以GitHub为准。没有追加全量、多节点或
参数调优；最终文档不触发不受影响数值检查的重复执行。

## HPC-06 / implementation and validation complete / 2026-11-26

从已合并 #55 的 `main@2d0e9b79e90ac0b7332b22e900e50e3306a68a35` 接续五项优化，
交付 [PR #56](https://github.com/saitoasukakawaii/EONSim-new/pull/56)，生产/测试源码
`bce292a1870c38686e44514e2879009ebb9a736a`。完整 Git tree 远端核对后才开始构建与算例。
三路源码复查未发现 AMG、ghost/SIMD 或 HDF5 新阻塞；已修复自适应 PC 重试重新取得
完整 Newton/函数评价预算的问题，保留有效命令行设置并在下一时间步前恢复原预算。

旧 main 求解器链接新测试，准确命中预期 Newton 预算失败；新源码本地 **5/5** 定向
Release 通过，覆盖 1/2/4 rank、晚发生的真实 KSP 耗尽、两类预算、选项覆盖及保留会话。
真实动脉 **6/6 runs、24 步、48 次修正**；独立原日志/owner-VTU 重放及 22 条哈希断言通过，
最坏真实残差/原门槛 **0.745355513**，五场最大归一化差 **4.68297e-13 < 2e-6**。
动脉没有自然触发 PC 重建重试；缺陷触发证据来自定向非线性测试，不混淆两者。
源码 CI [45757133771](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45757133771)
实际 **17/17 Release、0 skipped、0 复用**，网站检查成功。最终文档 head 的检查与合并状态
以 GitHub 为准；不把随后证据复用计为新数值执行。

[完整证据](../research/data/adaptive-retry-budget-2026-11-26/README.md)与
[未发布草稿](../../website/drafts/adaptive-pc-retry-budgets.md)已归档。HPC-05 其余路径复用
原通过证据，本次未重跑；没有新增性能采样、全量、Debug、旧 PETSc 或多节点验证。

## HPC-05 / implementation and validation complete / 2026-11-26

用户要求的五项开发、先推送后验证、原始证据和独立审计已完成。交付
[PR #55](https://github.com/saitoasukakawaii/EONSim-new/pull/55)，生产源 `2788970`，驱动源 `ceaa680`。
最终四项必需检查及锁定 head squash 依 GitHub 权威状态完成，不追加用户审批。

| 已关闭任务 | 已执行证据与范围 |
| --- | --- |
| P0 Block AMG | 有界节点聚合、平移/旋转局部 QR、完整 Galerkin、辅助 GAMG；1/2/4-rank 代数检查；四档网格112次对照 |
| P0 MPI | owned/halo 交换、异常排空、稳定合并范数；37 次真实 FSI 运行均符合预期（含 3 次预期失败）；字段归约6→3 |
| P1 SIMD | 连续导数 lane、被动标量与融合累加；IEEE/别名/Jacobian检查；20配对核中位下降30.99%～34.58% |
| P1 adaptive PC | 每次新鲜 J、有界数值复用、时间/漂移/迭代失效；真实 setup及USER更新证据；生成例10→2–3，强变化动脉保持谨慎刷新 |
| P2 HDF5 | collective hyperslab、owner唯一、原子XDMF与时间集合；8次小实算、24次较大输出、原生精确比较和ParaView |

严格动脉失败已保留并用所有候选共用的更严格 KSP 请求关闭，验收门槛未降低；最终36次
quick/full全部通过。Ghost/单元/刷新/输出机制有分别的执行证据，但没有普遍加速或多节点
扩展的承诺。n12只有正确性，HDF5在此主机慢于binary，动脉adaptive无统一时间优势。

[最终证据索引](../research/data/hpc-five-track-2026-11-26/README.md)及未发布草稿已完成。
后续只有用户提出新规模/平台/算例时才增加对应验证，不把本任务扩展成无限参数调优或全量测试。

## FSI-PC-04 / implementation and validation complete / 2026-11-26

从 GitHub 已核验的 main `858f021a34ff5bd178287430d8cd45e52ec19f48`（#53 已合并）
继续 FSI block preconditioner，分支 `codex/fsi-block-amg-robustness`。
用户授权顺序为完成代码、推送远程、算例验证、通过四项必需检查后锁定 head squash 合并。

本轮已关闭联合速度 scalar GAMG、twolevel 参考旋转模态、语义/约束/空 rank、真实数值
刷新、直接解密度比/时间步对照、RCR/恢复及独立审计任务。最终源码/驱动为 `88e6c335`，
交付 [PR #54](https://github.com/saitoasukakawaii/EONSim-new/pull/54)，合并状态由 GitHub 核验。

本地 a7e0 **7/7** 定向 CTest 和两种新路径的 1/2-rank 实际缩步/重启通过；88e6 修复错误标记
刷新后只复验受影响 COO **1/1**，计时/取消控制 **9/9**。其余复用本轮此前通过证据，未重复执行。
88e6 源码 CI 实际 **56/56 Release + 10/10 Python**，其四项必需检查成功；最终文档提交状态以 PR 为准。
最终 **78/78 动脉 runs / 656 步 / 1,282 次修正** 经独立来源、原始日志、五场及统计重放。
最大场差 `2.6171e-9`，原 `2e-6` 门槛不变；失败原件和修复过程均归档。

细网格 rigid 迭代 **5,445→5,050**，四步 wall 配对中位变化 **−10.79%**，范围跨零；
粗网格与 GAMG 无时间收益，保持显式选项，不默认切换。
`gamg+rigid` 因 scalar aggregate 局部秩风险拒绝，不将未实现的向量辅助空间写成完成。
[命令、来源、性能边界和归档](../research/data/fsi-block-multilevel-2026-11-26/README.md)。
本轮适用项已完成或给出有证据的采用判断；未追加无限优化任务。
多节点/GPU、百万自由度和任意密度/Re 的普适收敛不属于本地证据能够支持的结论。

## FSI-PERF-03 / implementation and validation complete / 2026-11-26

基线为已合并 #52 的 `2dcb06c`；生产源码/二进制 `7e8868e`，实验驱动 `3e366c8` / `7d86f38`，
全部遵循先推送、后验证。实现与验收完成；本记录最近核验的
[PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53) 为 open / Draft、head `7d86f38`。
剩余交付步骤是最终证据提交、其四项必需检查和用户已授权的受保护 head-locked squash；
合并结果只按 GitHub 权威状态更新，不新增用户审批步骤。

| 已识别任务 | 已完成及证据边界 |
|---|---|
| 核与默认写入 | 压力列解析化，AD 28→24；紧凑物理块 AIJ，完整导数及贡献次序保持 |
| 批次线程与失败 | 64-cell 持久团队；2 rank × 2 threads 的第二批 worker/insert 恢复和 fatal 均验收 |
| 重复数值工作 | 最终新残量共用于独立验收/反力；同状态首切线一次性复用、后续起点延后；真实 J/USER 计数 |
| 分区与身份 | 稳定分桶/前缀编号；显式权重、带权指纹、双分区实验收据；P1 的 168 对 HDF5 内容对照 |
| 输出 | ASCII 默认紧凑边界、raw binary UInt64/LittleEndian、volume-only；32 次输出逐数组/拓扑精确对照 |
| 性能与审计 | 88 FSI runs / 880 步 / 1,760 次线性修正；8,502 条哈希收据及 raw→pair 统计重放无误 |

本地定向 Release **17/17**；源码 CI 实际 **48 Release + 24 Python**，驱动 CI 实际
**1 Release + 21 Python、47 项复用**，IO 修复 CI **0 项新数值执行、48 项复用**。
原 IO `KeyError('reason')` 的失败尝试保留；求解本身 exit 0、`CONVERGED_RTOL`，7d 推送后仅重跑 output。
[完整命令、CI 来源与独立审计](../research/data/fsi-runtime-2026-11-26/README.md)。

初始切线消融每次完整 J/USER **30→20**、wall 中位数 **−12.060%～−25.594%**，场/历史差精确 0；
成本 `10:5,20:1` 的 n=8/2-rank 本例 wall **−10.585%**。默认收益混合，COO 双线程单 rank wall
**+3.900%**；权重与线程不作为通用推荐。Binary 相对同紧凑 ASCII 的 output 时间
**−81.338% / −82.010%**，字节 **+0.815% / +3.060%**，分别为 1/2 rank。
性能仅共享主机 1/2 rank；部分正确性路径覆盖 4 rank，2/8/32 分片准备仅是离线 P1 数据验证。
[草稿](../../website/drafts/fsi-runtime-cost-and-output.md) 保持未发布；本任务没有追加全量、Debug、
3.19.6 或无限优化项，多节点/GPU 和不同生产网格仍需各自证据。

## FSI-PERF-02 / implementation and validation complete / 2026-11-25–26

基线 main `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f`，分支 `codex/fsi-performance-completion`，
[PR #52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)。实现 `7f3d12e`，最终 COO 修复 `2b0b30b`，
均先推送后执行。开发与验收完成；PR 状态以 GitHub 为准，本记录未声称已经合并。

| 已识别优化项 | 关闭结论 |
|---|---|
| 默认 sparse pattern | 共用物理耦合块、独立 test/trial 投影；unique nnz 降低 25.70% / 28.69% |
| COO 坐标与容量 | rank 内 K→U，local-row buckets 消除已测初始化回退，原始相加次序保持 |
| 残量与单元核 | 固定残量 COO；线性 mesh/解析压力面移出 AD，完整跨场导数与几何检查保留 |
| 并行执行 | 64-cell 有界 OpenMP 批次、主线程 PETSc/MPI 与确定性 scatter；默认 1 线程 |
| 求解器生命周期 | 合资格 Newton 的 SNES/KSP/PC 与诊断缓冲复用，每次更新数值，失败/配置变化共同重建 |
| 约束/最终通信 | owned 数组替换，全局零约束跳过 MatZeroRows，普通双 stash Begin/End 交错 |
| BAIJ / halo 双阶段 | 已评估，异构编号/实测 ghost 占比不支持本轮采用；不声称已实现 |

本地 7f3 **13/13** 定向通过，2b0 受影响 FSI **1/1** 复验通过；云端 7f3 **51/51**，
2b0 **28/28 新执行 + 23 项复用原通过证据**，覆盖 51 项；Python 分别实际 65 / 6 项。
最终三组性能 campaign **80 runs / 1,600 accepted steps**，含 20 warmups；中间 COO 32 runs 另归档。
独立审计已完成原始字段/历史/迭代/残量/文件摘要复核，未改变容差。

默认 assembly 中位数下降 **9.47%–20.34%**；COO 初始化下降 **20.17%–47.72%**，
峰值 RSS 下降 **2.13%–8.89%**。wall 的波动与默认细网格单 rank RSS +4.01% 均如实记录。
[完整验收、统计与归档](../research/data/fsi-performance-2026-11-25/README.md) ·
[算法草稿，未公开发布](../../website/drafts/fsi-performance-completion.md)。
当前 CPU/MPI 适用项已完成或给出有证据的采用判断；无无限优化任务。
GPU、多节点扩展及不同生产网格的调优未在本任务中实现或验证。

## FSI-ASSEMBLY-01 / merged as #51 / 2026-11-25

Implementation and local acceptance are complete on
`codex/fsi-assembly-performance`, from main
`f7acccb7a8239c60a2d2be193a158ac430851dcf`.
[PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51) was delivered as Draft
and is now verified merged at `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f`.
The article remains unpublished.

Delivered ownership transfer of the final reduced AIJ, cached fixed cell maps,
fused fluid/ALE residual and tangent evaluation, interface-adjacent force replay,
and opt-in compressed FSI COO including rigid/RCR contributions. Test/trial maps
remain distinct and time-dependent weights refresh on every attempt. Physical
equations, time history and acceptance gates are unchanged. MatSetValues remains
the default assembly backend.

Implementation `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e` was pushed before
its clean PETSc 3.23.7 Release **8/8** focused acceptance. Coverage includes
matrix ownership, element derivatives, 1/2-rank FSI, RCR, variable time steps,
retry and restart, plus the shared solver's existing 1/2/4-rank fluid COO path.
The external wall timer's approximately 50 ms polling quantization was fixed
in driver `b2ccd96419091c669b8dceae4369c5b255f47f57`, pushed before both final
campaigns. The pilot evidence is retained; its wall measurements are superseded.

The final paired comparison has **64 runs, 320 accepted steps and 640 linear
corrections**: 48 measured runs and 16 warmups, two grids, 1/2 ranks and five
steps per run. Iteration trajectories match. Default assembly paired medians
fall **2.72%–11.81%**; COO falls **30.16%–43.37%**. Every COO wall-change range
crosses zero, and fine-grid single-rank peak RSS rises **27.81%**. COO therefore
remains optional; these measurements do not establish general end-to-end gains.
Independent evidence replay confirmed saved fields, histories, correction gates,
file hashes and the paired statistics.

For source b2ccd964, CI actually executed **55/55 selected Release checks** on
PR merge commit `ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0`, with no reused,
failed or skipped numerical checks. The **65 Python selection checks** and
Website Build Check also passed.
[CI metadata](../research/data/fsi-assembly-2026-11-25/ci-source-b2.json) ·
[Numerical run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206852) ·
[Website run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206859).

[Commands, raw evidence and measured limits](../research/data/fsi-assembly-2026-11-25/README.md) ·
[Algorithm draft](../../website/drafts/fsi-sparse-assembly-plan.md).
No local full-suite, Debug or PETSc 3.19.6 run was added; CI Debug and 3.19.6 jobs
were skipped. Multi-node scaling, larger production problems and a measured
baseline-to-candidate initialization speedup remain unverified. Later documentation
commits must retain their CI provenance instead of claiming fresh numerical runs.

## FSI-PC-03 / validated / 2026-11-25

Implementation and targeted acceptance are complete on
`codex/fsi-block-efficient-schur`, from merged #49/main
`296246e53d895f29ea3d0f7e5c960dc26b1426dc`.
[PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50) is the delivery
record and authoritative merge state.

Delivered optional mixed-fluid nodal structural `P_s = K - G H_F E`, numeric
refresh shared by semantic Schur roles, and independent nonsymmetric/scaled
oracles. The nodal structural path remains experimental: correctness passed,
but its measured screening did not establish useful efficiency.

The complete 72-run arterial campaign instead supports two bounded default
changes: added-mass fluid PREONLY and coupled twolevel velocity PREONLY.
Existing a11 structural FGMRES and explicit override budgets remain available.
The full physical Jacobian and physical gates are unchanged; the actual
implicit structural action uses the configured approximate fluid response.

Final source `c4fb266edec94afbf610cb1379dd1595ed96ae40` was pushed before its
clean PETSc 3.23.7 Release 9/9 acceptance and independent archive replay.
The 72-run campaign has separate binary/driver provenance, reproduced by
2,635 hashes, 1,248 correction checks and all saved physical fields.
All four required source CI checks passed: 15 newly executed numerical tests
and 39 compatible historical receipts cover the 54-test required selection.
[Evidence, failures, commands and CI](../research/data/fsi-block-efficiency-2026-11-25/README.md).

The current user authorizes source → remote push → verification → merge
following successful validation and all four protected checks. This replaces
the prior task's user-review restriction. Use a head-locked squash and keep
the knowledge article in website/drafts. Larger grids, stronger density ratios,
full coupled AMG and multi-node scaling remain separate research validation
needs; this delivery does not claim those properties.

## FSI-PC-02 / merged as #49 / 2026-11-25

Completed the existing conforming monolithic FSI block paths from merged #48
(`f50a4a4338689c9a065bee30ae4a7f3f52c5002e`): complete-fluid structural Schur
response, coupled two-level coarse correction, separately configurable Schur
inverse actions, and direct-solution/true-residual checks. The physical
Jacobian, acceptance thresholds, time integration, circuit histories and
ownership contracts are preserved.

Local implementation, source review and targeted acceptance are complete.
Pushed head `b52281d7585ead08e545f29f8d83eca9177e7eac` passed all 8 final locked
PETSc 3.23.7 Release physical/recovery checks with a clean source tree.
Reuse exactly the `b8ac03a` receipts for `pc_plan_mpi1/2/4` and
`pc_recipe_restart`; those four checks were not rerun locally at b522.
The b522 source CI passed all 53 selected Release numerical checks and 58
Python checks; selection, Release validation and evidence receipt are green.
The website Build VitePress and draft-isolation checks also passed.
[Source CI metadata](../research/data/fsi-block-2026-11-25/ci-source-b522.json) ·
[Numerical/receipt run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963270) ·
[Website run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963330).
[Evidence, failures and replay](../research/data/fsi-block-2026-11-25/README.md).

All 60 arterial runs passed; 12 complete 32-step trajectories contributed 768
accepted true-residual checks. Maximum residual/target ratio:
0.5600385064; maximum relative field-peak difference: 1.0712628633e-11.
Report measured timing without requiring a universal speedup: the direct
solver remained faster on the two tested grids. Full coupled AMG, elasticity
rotations, multi-node scaling and cross-partition restart are not established
by these tests.

The pushed archive replay passed all file, log and full-trajectory checks.
PR #49 is merged at `296246e53d895f29ea3d0f7e5c960dc26b1426dc`, verified
from GitHub before FSI-PC-03 began. The prior task's user-review restriction
is retained in its historical session record, not as an active block on the
newly authorized task.

## 2026-11-24 · 血管 FSI 后续验收

1. **灌流管空间收敛。** 在 20 mm 直管保持轴向分辨率的同时加密入口边界层和圆周，复测流量、端面法向应力、近端面积与壁面储量。现有 48 个轴向单元已将出口传递振幅带到 81.20%，独立参考为 80.00%。[可复用的物性、流量与端口](../research/data/fsi-linear-transient-2026-11-24/perfusion.md)
2. **分叉与出口。** 转入一般斜面上的可变面积出口、影像几何、初始预应力及更宽的雷诺数范围。固定斜面入口、三个坐标法轴上的可动出口、独立下游压力、理想化 T 分叉长时储量与恒流分配已有实测。[弯管](../research/data/fsi-rcr-2026-11-24/curved.md) · [出口运动](../research/data/fsi-rcr-2026-11-24/planar-outlets.md) · [分叉](../research/data/fsi-rcr-2026-11-24/branched.md)
3. **并行规模。** 在至少两台物理节点上补充网格、迭代、最大进程内存和 I/O 随并行度的变化，核验跨分区续算。单机进程数、通信条件与各算例的规模已分开记录。[路线图](FSI_PRODUCTION_ROADMAP.md) · [求解器与预条件实测](../research/data/fsi-phase-costs-2026-11-24/pc-recipes.csv)
4. **线性求解与并行退出。** 对 20 mm 两套随附网格，在更大分区上复核真实线性残量、每秩归约和实际进程退出状态，并继续定位多作业并发时的秩内信号。粗网格的 64 次线性修正与同网格直接解可逐步对照。[真实残量与求解选项](../research/data/fsi-linear-transient-2026-11-24/arterial-solvers.md)

## 2026-11-24 · 弹性管加载瞬态

已完成逐端面静压、法向应力、流量和功率输出，以及阶跃条件下 0.5/0.25/0.125 s 的同网格 EONSim–svFSI 对照。1 s 的最大截面差未随步长减小。下一项可独立验收的对照是让两程序施加相同的光滑升载，核对每一步实际施加的阶段压力并分别记录首步运动学、管腔体积和截面位移，再比较其余耦合离散。性能分项计时仍在队列中。[源码和结果](../research/data/fsi-pressure-faces-2026-11-24/README.md)

## 2026-11-24 · 网站内容审阅

优先核对[本次选编目录](../../website/drafts/README.md)中的四份编辑稿，以及学习栏目的 50 项源码表。请核查两套圆管计算的时间格式、移动域各误差的时间层、端到端计时范围与 P2 测试命令。其余 25 份草稿按同一目录中的合编方向接续。

## 2026-11-24 · HPC 调研与 Tet4 黏性核

- 本地已验证：基于 main `89a1a3d` 的数值提交 `4095e4b`，9 个定向 Release 检查。独立工作树内，PR #41 和 #42 的固定版本与此改动组合后，两项圆管回归通过。提交审阅时 #41 已合入主线。
- 下一项数值任务：固定 #42 网格和阶段语义，解释静压阶跃早期响应。同步记录面平均静压、法向牵引、位移、外载功和默认/固定稳定化的影响。
- 下一项性能任务：给当前弹性 FSI 分别报告流体及 ALE 切线、固体核、装配与 PC setup/apply 成本。候选 RCR 出口、Robin 支撑与多节点验收见[调研报告](../research/HPC_UPSTREAM_REVIEW_2026-11-24.md)。

## FSI-PROD-02B / review / 2026-11-20

Baseline `89a1a3d` includes the steady rigid-tube work from PR #38. This
increment targets the low-frequency, pressure-driven Womersley flow in a rigid
circular tube (R=1, L=2, rho=mu=1, alpha=2, sinusoidal pressure drop of
amplitude 0.02 and zero mean). Use the existing component-split end conditions.
Compare a full cycle of accepted endpoint fluxes against the complex analytical
solution after startup. Target amplitude error <2%, phase error <2 degrees,
waveform relative RMS error <3%, last-two-cycle maximum flow change <0.1% of
reference amplitude and maximum net outward flux <1e-10. Check the default
transient stabilization, time/mesh sensitivity, MPI and same-partition restart
separately. For a rigid-wall cross-code check, use svFSI 2022.09.26 at
`94a2ff5`, identical Tet4 connectivity, pressure waveform, end constraints,
time step and generalized-alpha spectral radius zero. Compare the complex
fundamental flow difference against 5% of the circular reference amplitude.
The companion elastic-wall comparison is tracked in
[PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42).

For a time-discretization control, hold the 48/8/12 mesh and BDF2 fixed and
compare successive first-harmonic differences on doubling the samples per
cycle. Repeat with one spatially uniform `fluid.stabilization_tau = 0.003`.
This value approximates the default coefficient at the mean cell volume, zero
velocity and 64 samples per cycle. It is fixed before the control solves.
Report the cycle-change floor alongside the differences. The default study
changes the stabilization operator along with the time step.

Local flow and rigid-wall svFSI gates passed on 48/8/12. The pressure trace,
uniform-coefficient control and spatial refinement are documented as separate
observations. The 48/12/18 mesh gives 0.7554% amplitude error and
0.2097° phase error. On that mesh the inter-code complex flow difference
is 1.3046%. The fixed-τ control gives phasor orders 1.960 and 1.991.
[PR #41](https://github.com/saitoasukakawaii/EONSim-new/pull/41) ·
[Inputs, measurements and replay](../research/data/womersley-2026-11-20/README.md)

## CI-DEBUG-ON-DEMAND / 2026-11-13

- 执行范围：默认 Release 增量数值验证、手动 Debug、Release-only 收据及自动合并四项检查。
- 验收：`python tests/test_ci_selection.py`、`python tests/test_agent_auto_merge.py`、`python tests/test_cloud_evidence.py` 和 PR Release 最小算例；实际状态由 Actions 证明。
- 管理员待办：main 必需检查移除旧 Debug、保留四项；当前连接无法访问保护规则管理 API。

## FSI-PROD-02C / review / 2026-11-20

Check the isolated linear elastic wall against the plane-strain Lamé solution
for a pressurized quarter annulus. Use a=1, b=1.2, L=2, E=100, ν=0.3,
internal pressure 0.02, zero exterior pressure and axial end rollers. Preserve
the existing default one-layer FSI mesh. Before solving, set targets of <2%
relative error in inner radius displacement and linearized bore area change,
<3% displacement L² error and <1% change in area compliance at the last
two refined resolutions. Check a second pressure and 1/2/4-rank invariance
(maximum displacement difference <1e−10 m). This structural constitutive
reference will support a subsequent coupled pressure–area comparison.

For a bounded monolithic hydrostatic check, apply the same positive pressure
on both fluid end faces, leave the outside of the solid traction-free, and
keep the quarter-domain symmetries and axial rollers. After a smooth startup
and relaxation, require <3% worst-section linearized area error against Lamé,
<0.1% last-step area change relative to the exact expansion, final fluid
speed <1e−6 m/s, pressure RMS error <1% of the applied pressure and interface
velocity/displacement differences <1e−9. Compare two step sizes to the same
physical endpoint. A dynamic pulse and an external coupled solution are separate.

For the external equilibrium check, run both codes from rest with a constant
0.02 Pa end pressure, dt=0.5 and generalized-alpha spectral radius zero.
Compare the worst-section difference in linearized area strain to 2% of the
analytic expansion. Require each solution to settle and check its area against
the 3% circular target. Retain any rejected external inputs or solves.

The first svFSI run encountered nonfinite arithmetic in its predictor at
spectral radius zero. A floating-point trap identified the division in
`PICP` where this FSI equation has γ=1. For the next paired runs use 0.5
in both programs, as in the upstream 3D pipe example. The wall, pressure,
time step and quantitative criteria are unchanged.

Observed 0.1894% worst-section area error for the finest isolated wall,
0.5684% for the fine coupled BE case and 0.0000227% maximum inter-code
difference relative to analytical expansion for the 48-sector paired case.
The 24-sector cross-code pair misses the analytical gate. The next physical
question is the dynamic pressure–area response. At fixed 48-sector resolution,
complete pressure-step histories on Δt = 0.5 and 0.25 s have peak inter-code
differences of 9.947% and 8.444% of the static expansion.
[PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) · [Measurements and replay](../research/data/lame-wall-2026-11-20/README.md)

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


## FSI-PROD-02A / review / 2026-11-06

PR #36、#37 已合入，当前基线 `dc378529538259567a78cea9820a202a6187809c`。
分支 `codex/fsi-tube-qualification` 领取生产路线的刚性稳态管首个独立增量：
同一端面按互斥分量组合压强/速度条件；充分发展 Poiseuille 压降—流量基线；
固定多边形的场加密与圆截面几何误差分开记录。预设验收：最细状态圆管解析流量误差 <2%，
场加密流量差递减且末档 <1%；1/2 rank 场差 <2e-9；端面通量平衡 <1e-10；
解析混合边界、重启签名和非法重叠拒绝通过。Debug/Release 使用仓库入口，最小相关回归。
本增量不代表整个 PROD-02 完成；Womersley、弹性管、默认瞬态稳定化和固定版本 svFSI 对照仍待验收。
实现 `a0d228764850fa838229acb6a6e613933070490f`，本地验收、自审和证据完成。
48边形流量误差1.264676%；12/48边形末档变化0.410813%/0.024769%；MPI场差2.78e-17。
最初level-2不通过，按原门槛加密后通过。Release新增/扩充两项、Debug三项通过；
Release未变regions复用首轮通过，Python网格/重算3项与CI选择26项通过。
48边形压强误差仍3.993089%，不能宣称全场定量资格。
[证据](../research/data/rigid-tube-2026-11-06/README.md)。
[PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38) 已创建，状态review，未合并。
云端Debug/Release各26/26、Python35项、网站/增量证据检查通过；数值测试零失败/零跳过。
最后仅补记文档与云端收据，复用这些通过证据，不重跑已完成数值研究。

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

本轮领取质量预算有效性修复，基线 `815755e`，实现 `80571b102e31dd2e7664a64a39a92efc8402045c`。本地验收完成：拒绝NaN初始状态、非正体积/接受步长、算术溢出；有效非零时间续算保持可用；26项Python检查与9组22400行归档重算通过。仅后处理修改，无新增数值求解或性能结论，等待分支合并。

FSI-NEXT-03 已由 PR #35 合并为 `815755eb15ffb63299487e8f9163ddc9d242a2f2`，状态done（固定τ限定范围）；以下review描述为历史。下一项数值研究仍是默认dt相关稳定化的误差分离资格，未在本轮实施。


## FSI-NEXT-03 / review / PR #35检查通过

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。

用户已明确授权上传代码与数值证据，并在验收后创建PR。下列旧in_progress记录为历史。


## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

本队列用于跨 Codex Goal / Cloud Task 接续研发。每个 Goal 只领取一个有明确验收条件的里程碑任务。

## FSI-NEXT-02 / done

2026-11-03 用户授权，20 小时为预算而非验收证据。基线 main `b2755b671ebffc4ad858d560214d4a7377eaf05e`；独立分支 `codex/fsi-next-02-periodic-flow`。
实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`；本地功能、验收、自审及记录完成；[PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 已合入 main，合并提交 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`。PETSc 3.23.7 Debug/Release CI 各29/29与网站/草稿隔离检查通过；[证据](../research/data/fsi-flow-2026-11-03/README.md)。周期体积流量驱动、无滑移弹性顶壁通道、移动域质量验证。

本次落实的验收：离散入口流量与独立波形计算误差 <1e-12；刚性壁零速度与界面速度/位移相容 <1e-12；阶段全局通量残差 <1e-9（基准流量 .01）；表面积分与体散度相符 <1e-12；BE/BDF2/generalized-alpha、1/2 rank 与同分区恢复字段差 <2e-9；正阶段/终点几何；周期参数签名和非法输入拒绝；整体 Jv、真实缩步重放；至少六个驱动周期、时间步和空间网格研究，报告体积累计误差及周期响应，不能把 secant 与 stage 时间层差异误判为连续性残差。Debug/Release 使用仓库编译脚本，受影响旧入口/压力回归，证据和草稿已完成；无空间渐近收敛或严格周期稳态声明。未检索到此前20小时计划原文，以上为本次按用户目标制定的可执行验收，非历史计划引用。

## FSI-NEXT-01 / done

基线 `06b05c4`；分支 `codex/fsi-inlet-reliability`，生产实现 `0d93d41`/`69692ee`，研究脚本 `32783a5`。速度入口与弹性壁通道、面积/几何诊断、精度与性能实验已完成本地验收：Debug/Release 各 5 项（4 项主检查 + 1 项旧弹性体补验）；分场时间阶、时间污染 9.51% 的空间研究、1/2/4 rank 的 30 个正式性能样本通过。用户授权全部完成后创建 PR，20 小时是估计，允许必要超时。已核对 PR #32 由远端合并为 `b2755b6`；本次未执行其合并，下面原记录保留历史验收来源。见 [证据](../research/data/fsi-next-2026-11-03/README.md)。

## FSI-LOAD-01 / done

用户授权：平滑周期压力驱动的单体 FSI、响应 CSV、流固时间序列及针对性验证。基线 `417e6f9`，分支 `codex/fsi-periodic-pressure`；验收及记录完成后才创建 PR。10 小时为工程量估计。实现 `a6c6761`；Debug/Release 针对性检查与双 rank 示例已通过，已创建 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31)，云端 Debug/Release 各 24/24 与网站检查通过；已由远端合并为 `06b05c4`。证据见 [验收记录](../research/data/fsi-pressure-2026-11-03/README.md)。

## 状态定义

- ready：依赖满足，可以开始。
- in_progress：当前有一个 Goal/Task 正在执行。
- blocked：存在明确阻塞，必须记录原因。
- review：已有可审查变更，等待审核或剩余验收；注明本地、PR 或合入状态，合并不自动代表全部测试通过。
- done：验收证据已记录且已合入 main；通常走 PR，本次按用户明确授权直接整合。
- deferred：暂缓，需由需求或性能证据重新触发。

## 当前队列

| ID | 优先级 | 状态 | 任务 | 交付与验收 |
|---|---:|---|---|---|
| FEM-G2C | P2 | done | P2 瞬态扩散闭环 | 基线 1bc87a7；实现 d19a032；BE/BDF2/alpha、同分区重启、接受步输出及本地 1/2 rank 验收完成，Release 5/5、历史故障 8/8；[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 云端 Debug/Release 各 15/15 通过，已由远端合入 main（dff9116）；最终证据补记另提纯文档 PR |
| FEM-G2B | P2 | done | P2 Robin 与纯 Neumann 边界 | [PR #28](https://github.com/saitoasukakawaii/EONSim-new/pull/28)；1/2 rank patch、物理零均值、用户输入与不相容载荷拒绝通过；云端 Debug/Release 各 10/10 相关检查通过，已合入 main（1bc87a7）；复用历史证据，本次未运行 |
| FEM-G2A | P2 | done | 直边三角形 P2 稳态 Poisson，D/N，1/2 rank | edfc73c 已接入分区/装配/输出，本地 Debug 1/2 rank patch、空间收敛和失败检查通过；[PR #27](https://github.com/saitoasukakawaii/EONSim-new/pull/27) 云端 Debug/Release 各 19 项相关检查通过；2026-11-01 已合入 main（c0745ea），复用既有验收证据 |
| CI-INCREMENTAL-01 | P1 | done | PR 增量 CI、精确执行与同 PR 成功证据复用 | [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 已合入 main（35bf1a1）；首次主锁 Debug/Release 各仅 Poisson 1/1 通过，文档后续提交实际零构建/零数值测试并继承原证据；保留手动全量，PR #26 已合并 |
| TEST-POLICY-01 | P1 | done | 固化增量验证与历史通过证据复用约束 | 基线 3df1c31；仅文档，ef20e03 随 PR #26 合入 main（35bf1a1）；检查文档差异及链接，该阶段不开发、不编译、不跑数值测试；自动 CI 改造由 CI-INCREMENTAL-01 承接 |
| FEM-INTEGRATION | P1 | done | G0B → G0 → G5 → G1 连续主线交付 | 基线及每阶段真实数值/MPI验证、独立审查、最终CI/PR与允许时合并；PR #23已合入main；本地与云端60/60/13通过，见集成验证记录 |
| DOCS-01 | P1 | done | 全仓 Markdown 进度与链接审查 | 88 份既有 Markdown 已审查，修订及静态验证见 [审查记录](MARKDOWN_AUDIT_2026-10-31.md)；[PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 已合入 be21882；本地静态检查、远程 Debug/Release 各60/60及网站/草稿隔离通过 |
| DEV-PROCESS-POLICY | P1 | done | 固化 PETSc 主力 CI 策略与持续知识积累要求 | [PR #24](https://github.com/saitoasukakawaii/EONSim-new/pull/24)；3.23.7 Debug/Release 为日常矩阵，3.19.6 手动专项；AGENTS、进度、队列、会话日志与知识索引同步更新；已合入 main（a508e3d），本次未复查远程 Checks |
| FEM-G0B | P1 | done | 旧存储上的语义与 physics/quantity/hybrid PC 接入 | 依赖基线；独立验收字段、父编号、唯一界面代表、刚体、空本地块及真实求解 |
| BRANCH-02 | P1 | done | 合入新增 G0A 并清理全部 7 个非主分支 | [源提交与检查](BRANCH_CLEANUP_2026-10-31.md)；保留 main，无生产求解器改动 |
| BRANCH-01 | P1 | done | 清理 18 个已合并分支并整合其余 6 个 | [源提交、取舍和检查](BRANCH_INTEGRATION_2026-10-30.md)；不编译，数值验收不随合并自动完成 |
| HPC-02 | P2 | done | 独立流体固定图 COO Jacobian 装配（PR #21 合并） | 证据见 FLUID_COO_ASSEMBLY_2026-10-30；保留默认路径，Release 既有超时等局限按报告记录 |
| FEM-G0A | P1 | done | DoF 语义、存储排列与 FSI 分块预条件详细设计及独立代数参考验证 | [专题与迁移切片](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)；20 项标准库测试通过，设计分支已审查合入；无 C++/MPI/PETSc 数值验收，G0已按后续授权实施验收 |
| FEM-G0 | P1 | done | DoF 语义、排列与物理场/物理量/混合 PC 树 | 现有 Tet4 结果与置换等价、叶子覆盖互斥、空本地块；依赖 G0B 及真实 1/2/4 rank 验收 |
| FEM-G1 | P2 | done | 规范化 reader、Gmsh4.1、Tri3/Quad4 二维标量闭环 | G0/G5 后；方向/标签/边界/MMS，禁止将读入等同求解 |
| FEM-G2 | P2 | deferred | entity DoF、不同阶空间与通用 Dirichlet/Neumann/Robin | G0/G1 后；trace、lifting、纯 Neumann、modal/nodal 与混合稳定性 |
| FEM-G3 | P2 | deferred | Hex8 及相容混合体网格 | G1/G2 后；过渡面、真实混合 patch、MPI 与几何验证 |
| FEM-G4 | P2 | deferred | form/约束驱动稀疏图与通用并行 VTU | 随 G2/G3 增量交付；远程/面项连接、字段采样、失败不发布 |
| FEM-G5 | P2 | done | BE 映射、变步长 BDF2、两类 generalized-α | BE/BDF2及共同stage alpha已接入独立场/ALE/单体FSI；最终本地与云端60/60/13通过，PR #23主线交付 |
| FEM-G6 | P3 | deferred | 非一致界面投影/mortar 到移动单体 FSI | G2/G4/G5 后；重现、力/功、搜索覆盖、Jv 与分布式对照 |
| FEM-G7 | P3 | deferred | 高阶批次、partial assembly/matrix-free 与预条件 | 目标业务触发；同精度算子对照、总耗时/内存，不只测 kernel |
| FEM-G8 | P3 | deferred | 配置 schema、inspect、recipe；按需 Python/DSL | 易用性随每阶段交付，native 热循环；暂不建设完整编译器 |
| INFRA-01 | P1 | done | 可复现云端构建、MPI 故障修复与核心数值 CI | 原分支 3 个 CI job 成功；合并时修正 ABI 检查范围与证据解析；72a3356 本次主环境 Debug/Release 35/35、旧版针对性7/7通过；最终PR #23主锁60/60及旧锁13/13云端通过，完成集成验收 |
| HUB-01 | P0 | done | 持续研发状态文件、文章模板和知识采集 Skill | 本 PR；文件可用、链接有效、网站构建通过 |
| SOLVER-01 | P1 | done | PETSc NonlinearSession 对象生命周期审计 | 源码调用链、对象生命周期表、setup/assemble/solve 计时方案、复用风险和是否实施的建议；本任务不改求解器 |
| SOLVER-01B | P1 | done | 固定 transient 案例的诊断开销基线（依赖 SOLVER-01 已合并） | 1/2 rank、每组至少 3 次、保存命令与原始日志；固定 rank 输出一致；明确计时边界，不将差异当作持久化收益 |
| SOLVER-02 | P1 | done | 多时间步 solver setup 性能基线 | fluid/elastic、各3次、逐步数据和首步/后续步统计；仅测量分析，不改求解器 |
| SOLVER-05 | P1 | done | 修复重复线性求解 KSP 所有权（依赖 SOLVER-01 审计） | 成功/失败/恢复调用均释放 PC；1/2 rank 回归和 Poisson 验证通过；独立 PR |
| SOLVER-03 | P2 | done | Newton 变量/方程一致缩放审查与规格 | 推导缩放后的未知量、残量、Jacobian、约束、线搜索和预条件器变换；先形成规格再实现 |
| SOLVER-03B | P2 | deferred | 按 SOLVER-03 规格实现可选一致缩放 | 由具体算例需求及规格审核触发；单位/非均匀尺度、物理验收、约束/反力、1/2 rank 和失败恢复验证 |
| SOLVER-04 | P2 | done | Schur/GAMG 网格规模行为分析 | 记录网格、DOF、块迭代数、粗层、内存和耗时；不预设网格无关性 |
| SOLVER-04B | P2 | done | 补齐求解器层级算子尺寸（依赖 SOLVER-04） | 只读已有算子；报告 global/local 行列；Schur 1/2/4 rank 与失败/初态收敛回归通过 |
| HPC-01A | P2 | done | 非线性装配阶段计时（HPC-01 的首个增量） | 分别报告 callback/错误同步/最终装配/约束；明确计时边界；Schur 与失败恢复回归通过 |
| HPC-01B | P2 | done | 稳态流体装配阶段基线（依赖 HPC-01A） | 三网格、1/2 rank、各 3 次；阶段范围/原始证据/直接解对照；不将回调等同纯 kernel |
| HPC-01C | P2 | done | transient fluid/FSI 装配阶段测量（用户同意继续建议任务） | 1/2/4 rank、每组 3 次；首步/后续步统计；物理解对照及原始证据 |
| HPC-01D | P2 | done | 独立流体 kernel/插入计时（用户要求继续上一轮建议） | 显式开关；逐rank/逐步计数；steady/transient/tagged 1/2 rank 开关对照通过 |
| HPC-01E | P2 | done | 流体单元计时开关扰动与基线（继续用户已提出候选） | 1/2/4 rank、交替顺序配对重复、warmup；物理解/迭代不变；原始数据和范围 |
| QA-01 | P2 | done | profiling 日志验收加固（PR #20 已合并） | 真实归档日志可解析；非有限/非整数原因与计数、缺失指标/根节点、重复层级及错序步被拒绝；加入 CTest |
| HPC-01 | P2 | deferred | MPI 稀疏装配与通信 profiling | 分离本地 kernel、远程插入、MatAssembly、halo exchange 和 KSP 时间 |
| HUB-02 | P3 | deferred | 将 PETSc 生命周期审计整理成正式教学文章 | 结合性能数据更新草稿；人工审核后发布 |

新增 FEM-G0–G8 的详细设计、依赖与验收唯一入口是 [通用 FEM 规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) §13。ARCH-01 的规划文档已随 BRANCH-01 集成，不能解释为 G0–G8 实现完成。FEM-G0A 设计与参考验证已按用户后续授权审查合入，子任务 done；该分支整合记录为历史；当前已按用户授权执行G0B/G0/G5/G1。


## DEV-PROCESS-POLICY / 2026-10-31

用户要求将 PETSc 3.23.7 设为日常主力 CI，PETSc 3.19.6 仅保留手动兼容验证；并将跨 Codex Task 的持续知识积累固化为根目录 `AGENTS.md` 规则。PR #24 同时承载 CI 和开发流程规则，已合入 main（a508e3d）。普通开发任务不因此增加多版本测试；无复用技术成果时不创建知识文章。本次仅从 Git 历史和工作流核对合并及策略，未读取远程 Checks，也未重跑数值测试。


## 历史任务规格与检查点

以下保留任务领取时的规格、预算和阶段状态；最新结果以上方队列表及 [集成验收](FEM_INTEGRATION_VALIDATION.md) 为准，不将历史 in_progress/review/deferred 当作当前待办。

## HPC-01C：多时间步装配阶段测量（已完成）

### 目标

使用 PR #13 新增的阶段计时字段，建立可复现的 MPI 装配测量基线。此任务只运行测量、解析日志和分析，不修改求解器代码。

### 执行要求

1. 读取 L2 离散算子计时契约及 PR #13 的实现，准确解释 callback_seconds、failure_sync_seconds、assembly_finalize_seconds、constraint_seconds、assembly_seconds、ghost_seconds 和 linear_seconds。
2. 从现有案例中选择至少一个装配成本足够稳定的代表算例；如资源允许，再增加 transient fluid 或 FSI。
3. 固定 main commit、Release 构建、CPU/内存、编译器、PETSc/MPI 版本、网格、DOF、容差和 PETSc options。
4. 在可用资源范围内运行 1/2/4 rank；每个配置至少 3 次重复，保存原始日志。
5. 报告每步与每次运行的中位数、离散程度和 rank-max 口径；区分首步与稳定步骤。
6. 阶段时间有包含关系且 rank 最大值可能来自不同 rank，不得直接相加或将 callback/assembly_finalize 解释为纯 kernel/纯网络时间。
7. 同时检查 SNES/KSP 迭代数、最终残量和物理解差；不放宽容差。
8. 不将单节点多 rank 结果写成多节点强扩展结论。若 Cloud VM 资源不足，记录阻塞并提供在 HPC 上复现的命令。

### 完成标准

提交可复现命令、环境信息、逐 rank 原始日志、统计表、阶段边界解释和瓶颈结论；明确下一步是优化、需要更细计时，还是暂缓。知识草稿保留在 website/drafts/。

## HPC-02 历史任务范围

HPC-02 基线：24eae624ee93b3e1989312e1b1b273217571310f。预计工程工作量 7–9 小时：接口与失败语义 1–1.5h，固定图缓存及流体接线 2h，数值/MPI/恢复回归 2–2.5h，Release 配对测量和文档/复核 2–3h。此为工作量估计，不作为实际耗时或完成证据。
范围为独立固定网格 Tet4 流体的 Jacobian COO；残量仍使用原 Vec 插入，FSI/ALE/固体、方程、停止容差和默认装配算法不改变。验收包括空贡献 rank、重复索引、远程行、重复更新清零、非零约束与原始反力、单 rank 局部拒绝后的共同失败和同对象恢复；真实案例覆盖 steady/transient/tagged、压力归一化和同分区重启。性能只报告实测配对数据，不预设加速门槛。

## 任务领取规则

1. 一个 Goal 对应一个主要任务和一个验收终点。
2. 开始时将任务标记为 in_progress；结束时标记为 review 或 done，并按 AGENTS.md 完成实质任务的进度、队列、会话日志和知识索引更新。
3. 任务受阻时记录阻塞与解锁条件，不要无限重试。
4. PR 合并后才能标记 done。
5. 下一 Goal 必须重新读取 main 的最新进度和任务队列。

SOLVER-02 测量已完成，见 docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md；结论为暂缓持久化原型，已由 PR #8 合并。后续优化需由业务规模或新增性能证据触发。

SOLVER-03 本轮因用户要求继续研发而领取，仅完成审查、规格及独立代数验证；实际求解器缩放实现仍需后续独立任务，不引入配置键。

SOLVER-03 规格及精确代数验证见 [审查报告](../research/NEWTON_SCALING_SPEC_2026-10-30.md)，已由 PR #10 合并；未实现求解器坐标缩放。

SOLVER-04 本轮范围：稳态流体单位立方体，2/4/6 subdivisions，1/2 rank；各组直接解参考及 3 次 Schur 重复，保存原始日志、字段差、层级、内存与计时，不外推大规模性能。

SOLVER-04 已完成本轮有界测量，见 [报告](../research/SCHUR_MESH_PROFILE_2026-10-30.md)；已由 PR #11 合并。后续大网格/FSI 或粗层成本测量需明确目标，不根据小样本直接调参。

HPC-01A 实现成功评价的阶段计时，已由 PR #13 合并；HPC-01 尚缺纯 kernel/插入分离与目标规模证据，保持 deferred，不把诊断接线当作完整 profiling 结论。

HPC-01B 已完成稳态三网格装配阶段重复测量，见 [报告](../research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md)，已由 PR #16 合并。未据此改求解器或作纯通信成本归因。

HPC-01C 已完成 fluid/elastic、1/2/4 rank、18次运行及180步测量，见 [报告](../research/TRANSIENT_ASSEMBLY_PROFILE_2026-10-30.md)，已由 PR #17 合并。没有新增 ready 任务；后续仍由用户选择。

HPC-01D 已实现独立流体显式单元计时，并通过 Release/Debug 三案例1/2 rank开关对照，已由 PR #18 合并。FSI/ALE、owned/remote插入分离与计时扰动测量未完成；无新增ready任务。

HPC-01E 已完成1/2/4 rank、每配置5对测量及6次预热，见 [报告](../research/FLUID_ELEMENT_OVERHEAD_2026-10-30.md)，已由 PR #19 合并。观测范围不足以支持固定开销或优化结论；无新增ready任务。

## INFRA-01 阶段记录

基线为 PR #21 合并后的 38a5e51。原分支 d3f69d1 的 [GitHub Actions run 41060786421](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41060786421) 已完成且成功：PETSc 3.23.7 Debug / Release 与 3.19.6 Release 三个 job。本轮只读取历史结果，不重新触发工作流。

源分支后续至 787372e 的恢复说明、精简证据、资源检测、包缓存隔离与单机 MPI 传输适配也已纳入。5745fd3 的 CI 41063030121 三个 job 成功；来源分支已创建 PR #22，本次按用户要求整合。原分支完整记录见 [INFRA-01](../research/INFRA_01_REPRODUCIBLE_MPI_CI_2026-10-30.md)；其云端执行属于先前开发会话。

依赖锁、恢复脚本、MPI 失败处理和测试已随分支集成；合并审查额外把 OpenMPI/int32 检查限定为云端显式启用，并使 JUnit 解析拒绝重复、缺失与错误结果。6 项纯 Python 解析器回归通过。

按用户要求，本次不编译，不运行 CMake 配置、CTest、MPI、性能或网站构建。最终集成提交的 Debug/Release 数值回归与环境恢复没有重新验证；原分支成功记录不能替代这些检查。该任务保留 review，后续按用户安排完成集成验收，不自动开启下一轮构建。


## FEM-G0A 历史范围与交付

10 小时是工程量预算，不是实测耗时。以 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424` 为源码事实基线，开始时最新 main 一致且开放 PR 查询为空。
任务从 in_progress 转为 review；2026-10-30 先按要求本地交付，2026-10-31 用户追加授权提交并推送 `docs/fem-g0a-dof-design`，不创建 PR、不合并、不触发 CI。三种分组、固定 K/W 与 lifting/置换、父块分布式编号、所有权/失效/成本和后续切片见专题。
20 项 Python 标准库参考测试只证明合成代数与分区索引逻辑；不构成真实 MPI/PETSc、FSI 稳定性、性能或 INFRA-01 最终集成验收。FEM-G0 整体不标 done。


## BRANCH-02 / 2026-10-31

用户追加授权合并并清理远程分支，替代上面 FEM-G0A 原交付阶段的“不合并”限制。已审查 G0A 源提交并复验 20 项参考测试；检查工具的 UTF-8/CRLF 修复通过正反例。FEM-G0A 为设计子任务完成，FEM-G0 整体及 G0B/G5/G1 的生产开发尚未执行，INFRA-01 的最终集成数值验收仍 review。分支及提交清单见合并清理记录。

## FEM-INTEGRATION：2026-10-31 历史授权与检查点（已完成）

接续检查点：`47b5bd4` 已合入G0，主线数值CI成功；新分支 `codex/fem-time-mesh`。
整体任务 in_progress。G0B已有实现；G0完整验收补强 in_progress；G5、G1仍为已授权待依赖完成。
本轮剩余工程量估计（非实测耗时）：基线复核3–5h，G0补验4–8h，G5 35–55h，G1 25–40h，最终集成6–10h。
用户明确允许当前WSL2验证，并要求CI云端复验。前序4CPU/32GiB云机记录不用于描述当前执行器。

用户已明确授权 G0B/G0/G5/G1 实现、依赖恢复、真实构建/MPI验证、阶段提交推送、审查后PR和受保护规则约束的主线合并。其它 deferred 阶段仅实施本闭环必需子集。ready 表示已授权，仍须遵守行内依赖，不代表可并行跳过前置验收。

- 基线 main：`72a335604a50c1ae27516b8bde15e05564b5748b`；开始时无未合并 PR。分支 `codex/fem-g0-g5-g1`。G0A 已合入，复用现有20项参考验证，不重复开发。
- 快照旧未提交 G0A 文件已保护至 git stash（`preserve restored FEM-G0A work before integrated implementation`）及 `/workspace/recovery/fem-g0a-20261031/`，不混入本实现。
- 工程量估计（不是实际耗时）：基线3–5h，G0B/G0 16–24h，G5 35–55h，G1 25–40h，最终集成6–10h。
- 资源：cgroup 4 CPU、32 GiB；使用仓库锁恢复 PETSc3.23.7 于 `/workspace/eonsim-cloud`，命令退出0。基线首次配置发现快照旧缓存引用已消失的 `/tmp/infra-pristine` Ninja；旧目录移至证据区保留，正在从空构建目录重跑。
- 当前没有新增生产能力或完成数值验收；INFRA-01 保持 review。证据临时目录 `/workspace/engineering-evidence/`，完成后提交精简可复现结论。
- 后续顺序：主环境 Debug/Release all → 3.19.6 failure/state → G0B生产适配及G0验收 → G5 → G1 → 完整回归与审查/CI/主线交付。

### 基线验收更新

锁定主环境从新的依赖前缀恢复，清空（移走保护）快照中的旧构建产物后运行 Debug/Release `all`，实际各35项全部通过。3.19.6 Debug `mpi-failure` 7项全部通过。运行时链接及2/4 rank主环境预检通过；恢复命令再次执行成功。精简机器可读清单见 [baseline.json](../research/data/fem-integration-2026-10-31/baseline.json)。Release/legacy 的 dirty 标记包括任务文档及尚未接入构建的新头文件；当时生产代码仍为72a3356。

G0B/G0当前生产实现、独立审查与主环境43/43各模式通过；兼容环境10项失败状态、7项分组重启、最新4项补验通过。状态review，待整体CI/PR/main；G5/G1尚未实现。
