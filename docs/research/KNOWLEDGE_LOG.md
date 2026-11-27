# EONSim Knowledge Log

2026-11-27 核对：主线已合入 #65（`2463f717`）；以下历史记录保留实际执行日期、源码、失败与验收边界。当前能力与开放目标见 [当前能力矩阵](../development/CURRENT_STATUS.md)。历史 review/Draft 不代表当前 PR 状态，历史证据不计为本次执行。

## 2026-11-27 · FSI-SADDLE-01：兼容性、复用失效与实际工作量

[未发布草稿](../../website/drafts/fsi-saddle-point-multigrid.md)、
[机制说明](../development/FSI_SADDLE_POINT_MULTIGRID.md)和
[原件/失败索引](data/fsi-saddle-01-2026-11-27/README.md)对应
[PR #65](https://github.com/saitoasukakawaii/EONSim-new/pull/65)。最终生产/驱动源码
`ccf1bd7b3727a6b3ddd3a85954a3a78c51a652ba`；实现与有界验收完成，最终检查和锁定head合并状态由PR记录确认。

Galerkin定义不等于粗细散度交换；实际压力像空间闭包可以保证交换，但在本轮n8保留全部
729个压力自由度，增加建层和存储成本。兼容transfer的复用应审实际B变化：固定缩放及typed
transfer下B不变可安全保持粗层B，变化且压力未满维必须重建。真实重建guard不能被当作复用
失败，也不能被记作复用已经执行；生命周期reason计数与配置开关分开。

分布式ASM局部LU需要适合鞍点的数值主元，不能用shift或降低零主元阈值处理错误。Braess
实体块逆的alpha影响实际平滑稳定性；由同源单因子诊断确认alpha=2修复n8失效，并由独立
块oracle核对默认值。两个修复都保持原方程和残量/字段接受门槛。逐次投影/提升的deflated
FGMRES与一次warm start不同，但有限QR/SVD谱选择不等于完整harmonic-Ritz GCRO-DR。

有效集合48条物理/18条网格全通过，分源复用明确；原始失败保留。colored在本次n8实测总
求解时间减少34.46%，all反增69.97%；最优网格增长比1.7037>1.3，目标OPEN。单host、最大
本轮5367DoF的证据不支持百万DoF、多节点、普遍inf-sup或稳定加速结论。文章仍在drafts。

[最终源码 CI 45931896224](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896224)
实际新执行 **83/83 Release、54/54 Python**，没有复用数值记录。合并预览
`75bb86a0c5e668d497d0e95eb5ed0be4df824550` 与 `ccf1bd7` 的完整 tree 均为
`014a1de3199b7e476aec00aa63078a13adb60610`，dirty=false；
[源码网站检查 45931896258](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896258)
通过。远端检查与本地分源轨迹分别计数；最终文档 head 的四项检查及合并以 PR #65 为准。


## 2026-11-27 · FSI-SCALE-01：精确作用、预条件近似与性能证据的边界

北京时间记录，任务起始于 2026-11-26。[未发布草稿](../../website/drafts/fsi-scalable-matrix-free.md)、
[运行与数学说明](../development/FSI_SCALABLE_MATRIX_FREE.md)和
[完整原件/失败索引](data/fsi-scale-01-2026-11-26/README.md)对应
[PR #64](https://github.com/saitoasukakawaii/EONSim-new/pull/64)，最终生产/驱动为
`50b41ae19067bd8853a482ab853805e23c096ec5`。实现与有界验证完成；最终文档 head 的检查和
锁定 head 合并结果由 PR #64 记录确认。文章仍在 drafts，未公开发布。

可复用结论：精确 Jv 与 reduced assembled P 的图/值/刷新必须分开；部分装配缓存绑定
每次真实线性化，SIMD 和方向通信重叠不能复用过期状态。物理左右缩放应配合保持原
Galerkin 测试空间的限制，候选再现本身不保证鞍点稳定性。压力 supremizer 以实际离散
耦合生成局部响应，消耗原 spectral 名额；局部最小奇异值与 FP64 setup 配对保持既不是
全局 inf-sup 下界，也不证明 native FP32 量化后同样精确。K-cycle 的每次粗访问最多两方向
并不限制整个递归周期只有两次粗工作，必须报告实际计数而非只报外层迭代。

故障教训：约束投影的零残余可能被线搜索放大；KSP 正 reason 过早发布会使公开
BuildSolution 读取旧 restart 近似，真实残差 guard 必须在当前迭代状态取得解。不同 RSS
采样口径须分别保存；系数变 float 不能抵消两个 generation 同驻、稠密 patch 或 halo
容器剩余容量的开销。`116836b` RSS 增加约35%的负例及 `30e2941` 生命周期/存储修复
后的单次同源 pair（最大 rank 归一化峰值 −4.0557%）均保留；不据此宣称总内存或带宽减半。
缺 telemetry、Python 负例异常类型及人工中断也与真正的物理失败分别记录，拒绝门槛未放宽。

最终 `50b41ae` 本地 **3/3 MG、19/19 Python、9/9 网格和15/15物理求解**通过；后两批
独立重读 72 接受步、171 条线性记录，保留原字段/约束、严格或当次 forcing 真残量门槛。
`30e2941` **9/9 MG/patch/smoother**、K-cycle 网格和 native pair 仅按原源引用；
`6378f4c` 的三次配对方向成本测量也只支持共享节点上的局部观察。原件没有 J/b/dx，
日志标量复核不等于离线重算 Jdx−b。

703/2299/5367 DoF 的最终 supremizer V 迭代 92/138/199，平均最大/最小 **2.1630**，
未达到预声明 **≤1.3**；优化 V 2.3402、历史 K 2.0612 同样未达。近似网格无关仍 **OPEN**。
实测最高 **10,387 DoF / 单 host**，百万 DoF、多节点与扩展效率 **OPEN / 未运行**。
局部配对有效、有限窗口物理通过与目标完成是不同结论，不能互相替代。

[源码 CI 45853312807](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312807)
实际 **4/4 Release、19/19 Python**，复用 62 项 Release、总覆盖 66；合并预览
`3ca62ae4c0c037ca59c255fc8cd1754f1101f7ea` 与源码的 tree 均为
`7f66c8b02d62ed67606f7bf5f94fd5af34915f6e`。
[源码网站检查 45853312823](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45853312823)
成功；这不替代最终文档 head 的检查和合并记录，也不计作该 head 新执行数值测试。

## 2026-11-26 · FSI-MF-02：先收缩方向，再形成节点力

[未发布草稿](../../website/drafts/fsi-direct-solid-action.md)、
[原始证据](data/fsi-mf-02-2026-11-26/README.md)对应 [PR #62](https://github.com/saitoasukakawaii/EONSim-new/pull/62)
及生产/测试源码b7d727b。从已有能量函数推导直接δP，不构造材料或单元完整切线；
一致质量与位移/惯性链系数分别保留，零方向也不跳过NH构形验证。
MG省去的是每层已知零初值的一次残量乘，不能靠rank-local零判断改变collective路径。

4项定向CTest与11次物理求解通过；14组固体/12组支撑的完整切线与残量差分双参考成立。
局部核4配置每种7对测量中位降低75.75%–82.08%；旧/新二进制3对小例MF阶段中位降低
23.27%，wall范围跨零且中位+1.44%。该例说明局部作用成本下降不能直接解释为整程序
加速。理论、实现、数值和性能证据分开；草稿未公开发布，完整P与规模目标仍开放。

## 2026-11-26 · FSI-MG-01：完整混合粗空间与流水线失败协议

[未发布算法草稿](../../website/drafts/fsi-monolithic-multigrid-matrix-free.md)、
[操作与数学说明](../development/FSI_MONOLITHIC_MULTIGRID.md)、
[原始证据与性能数据](data/fsi-monolithic-mg-2026-11-26/README.md)对应 PR#61、最终生产
3b5cbddb928dfa789dc1f3f424dba451f33107e6。理论、实现、验证和有限性能证据分别陈述。

可复用算法：完整约束后混合 Galerkin 保留跨场耦合；受候选约束的缩放正规能量下降与局部
谱增强须保持基的秩；粗层 patch 应围绕完整聚合体基定义，不能随稠密图任意扩张；结构
顺应性 Schur 保留实际非对称耦合及完整 D。PCD Robin 使用当前 ALE 相对通量三次积分，
速度质量增强明确为离散 Laplace 混合，零输运极限含原 D；不声称标准加性 PCDR。

故障教训：重复 PtAP 的舍入变化会使精确数值缓存失效；错误提前退出可能分别遗留向量锁
与流水线归约状态，二者不能仅靠替换同一个向量解决。错误粘滞后有限临时作用排空通信，
通过原收敛回调契约退出并无条件抛原错误，才能保持 MPI 与状态接受契约。四类失败及对应
最小修复、1/2/4-rank复验原件完整保留，未修改PETSc私有结构或放宽通过门槛。

本地22项有效CTest区分最终12新跑/10复用；最终28次FSI、84步、177真残量通过原门槛，
累计64成功及4早期已修复setup失败分列。独立审计重读XML/CSV/log而非调用项目校验器；
无J/b/dx离线乘积证据。源码CI45819157827实际95/95 Release、54/54 Python，成功receipt
与merge-preview完整tree已核实；文档head的证据复用不算新的数值运行。

703/2299/5367 DoF的MG迭代104/151/206，FP32相同但更慢；小例直接解更快。LU值数组
减半而5367的最大rank RSS由198.668升至214.629MiB；MF的P装配6→3但完整P仍保留。
局部谱不是全局残量学习，候选可表达不证明一般inf-sup或网格无关，没有多节点或普遍
端到端收益声明。文章仍在drafts，后续需人工审查数学范围与更大规模性能证据才可发布。

## 2026-11-26 · FSI-PC-05：物理粗空间、PCD 边界尺度与空 owner 集体调用

[未发布算法草稿](../../website/drafts/fsi-field-amg-pressure-interface.md)、
[实现与选项](../development/FSI_ADVANCED_PRECONDITIONERS.md)及
[完整证据](data/fsi-advanced-2026-11-26/README.md)对应PR#59、最终生产19cd26f。
理论、实现、数值验证和有限性能证据分开记录；没有公开发布或新增无关架构规则。

可复用推导：LSC/BFBt保留完整D但明确是当前缩放变体；PCD只给Laplace校正施加辅助边界，
保留物理Mp及mu质量逆，稳态模型极限为(Mp/mu+D)^-1；逐层候选投影与完整Galerkin
保证所选模态可表达，但不保证一般网格无关；FP32仅作用于局部因子并受FP64残量约束。

两条重要故障闭环：空owner的MatIncreaseOverlap局部n=0返回导致集体错序，采用临时空IS
补位并实际通过1/2/4rank；PCD全单位边界破坏质量极限，新测试链接旧库明确失败，修复后
独立6个作用oracle、4代积分与2项SELF/WORLD检查通过。旧失败原件不被后来的成功覆盖。

20/60/38次真实求解分别独立审计，最终38次108步225修正，field3.19152e-11、history
5.68434e-14、true residual/gate0.00927309；26对分区HDF5容器字节不同而完整语义相同，
差异与比较方法都保留。2rank PCD网格迭代825/1199/1731→144/166/225，仍比nodal/BFBt多；
BFBt加patch在六条件下降2.44%–11.96%迭代，PCD小例则增加。局部因子数组减半不等于
总内存/带宽/耗时减半。没有网格无关、多节点、普遍加速或完整入口Robin/PCDR能力声明。

最终源码CI [45787454655](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45787454655)
实际85/85 Release选测、54/54 Python通过，0数值失败/跳过/复用；合并预览121e54bb与
19cd源码tree相同，成功增量receipt及官方artifact摘要均已核实。后续文档检查复用此来源。

## 2026-11-26 · RCR-PC-01：端口 Schur 的低秩响应与失败恢复

[未发布草稿](../../website/drafts/rcr-port-schur-low-rank.md)、[使用与推导](../development/RCR_PORT_PRECONDITIONER.md)
及[原始证据](data/rcr-port-2026-11-26/README.md)对应PR#58、生产28e6d54、驱动ad08887。
理论区分固定线性H的Woodbury恒等式与含内层求解的近似响应；移动出口及行约束不保证
V=-Uᵀ。实现逐代缓存HU和D-VHU，端口层内积合并归约，基础GAMG/BoomerAMG保持可选。

1/2/4rank独立代数、奇异/NaN拒绝与恢复及13真实FSI运行已验证；独立原件回放确认
43接受步、96真残差、798无失败内层记录，adaptive12新鲜J/8刷新/4复用。
114Newton总数另含没有线性诊断的18直接参考迭代；不混淆观测范围。
保留PCApply失败路径向量读锁与变步长名义终点的两次失败、对应修复及定向复验。

GAMG单/双出口迭代145→144和53→53，单次短样本不支持普遍加速或网格扩展结论。
文章仅保留在drafts，未发布。最终源码CI实际65/65 Release、54/54 Python通过，
0数值跳过/复用；成功receipt与CI原件见证据页，后续文档不算新的数值执行。

## 2026-11-26 · HPC-07：固定结构复用与对照器完整性

[草稿](../../website/drafts/hpc-fixed-structure-refresh.md)及
[证据](data/hpc-followup-2026-11-26/README.md)对应源4c7edc6、PR#57。
保留新鲜节点逆但复用完整COO图，owned/halo各展开一次物理槽位，并验证输出oracle
自身的长度、身份、索引和绑定。理论关系、实现、数值/故障验证及性能证据分开陈述。

远程MPI日志的半行前缀还触发一次解析误报；保留失败原件并独立回放，测试驱动
8e6c013只容忍前缀而保持完整记录/唯一标记/行尾/线程和批次门槛。先同步后定向复验
8项Python和1项双线程FSI通过，数值生产路径保持。
最终8e6c013源码CI实际43/43 Release和44/44 Python，0跳过/复用；两组绿色CI原件
与首次误报原件分开归档，文档head不算新的数值执行。

4项本地Release和30项Python通过，37次FSI正常/预期失败语义与83接受步已独立复核，
14次历史HDF5精确回放通过。配对16runs/80步/160修正的场与历史差0；独立861摘要断言。
线程批次58→29、清零少9次；总MatAssembly未少，wall范围跨零。2rank线性时间中位
−4.49%不能推广为普遍整程序收益；RSS中位+1.08%一并保留。
没有多节点、百万DoF或网格无关AMG证据。草稿未公开发布，无新增架构规则。

## 2026-11-26 · HPC-06：库级重启不能重置应用级求解预算

[未发布草稿](../../website/drafts/adaptive-pc-retry-budgets.md)记录自适应 PC 的一次恢复
为何必须扣除已接受 Newton 步和 PETSc 计数的函数评价，并恢复下一次 solve 的原上限。
实现与回归源 `bce292a1870c38686e44514e2879009ebb9a736a`，交付 PR#56。
旧 main 加新测试准确失败；新代码本地5项、源码CI17项Release通过；6次真实动脉的
24步/48修正满足原门槛，最大五场差4.68297e-13。独立原始日志/owner-VTU/哈希审计已归档。

理论/API、实际代码、负对照与正确性证据分开陈述；没有新增性能结论。实际动脉未触发
重建重试，预算证明来自有意构造的晚发生KSP失败。函数预算仅指PETSc计数，不包括
已有显式初始/重试起点与最终物理验收组装。[完整证据](data/adaptive-retry-budget-2026-11-26/README.md)。

## 2026-11-26 · HPC-05：聚合粗空间、通信、SIMD、自适应与共享输出

[未发布草稿](../../website/drafts/hpc-five-track-optimization.md)及
[完整证据](data/hpc-five-track-2026-11-26/README.md)对应生产2788970、驱动ceaa680、交付PR#55。
理论/API、源码实现、正确性与性能分别列明；草稿未晋升公开页面。

可复用结论包括：缩减语义节点聚合须局部去秩退化并保留完整Galerkin交叉项；ghost pending
期间只能读owned依赖，失败先完成通信；缩放平方和可与约束max组合为一次稳定归约；AD SIMD
必须验证标量提升的IEEE/别名语义；实际PC数值复用需与J组装分开计数；HDF5发布入口必须晚于
集体数据关闭，不能把requested collective当作actual collective。

15 项定向检查通过；37 次真实 FSI 运行均符合预期（含 3 次预期失败）；SIMD20配对中位下降
30.99%～34.58%，MPI字段归约6→3。
112次网格系列独立核验实际USER10→2–3、J10，n8/2rank配对线性−27.85%、wall−13.35%；
fresh aggregate本身不保证更快。HDF5相对ASCII输出−73.22%/−44.73%，却慢于现有binary。

保留首轮缺诊断的元数据失败和一次真实FGMRES残差间隙；公共外层请求收紧到1e-11后，原严格
真实残差门槛下最终动脉36runs/312步/624修正通过，worst ratio.8439101351、场差7.5813e-12。
动脉实际USER64→61/62，四步计时没有统一优势。估计残差reason不能替代显式Jdx-rhs；
四步样本不能冒充32步轨迹性能；新证据提交不代表重新执行既有检查。

所有计时限定共享主机1/2rank，部分代数验证到4rank。迭代随网格增长，没有mesh-independent、
多节点、GPU、并行文件系统或高阶HDF结果输出结论。待人工公开发表审查的问题是不同平台的
收益能否复现，而不是已授权PR合并的额外审批门槛。

## 2026-11-26 · FSI-PC-04：参考旋转模式与联合速度 GAMG

[未发布算法草稿](../../website/drafts/fsi-reference-modes-and-gamg.md)记录缩减语义行的参考
位置、约束零模态、局部/全局粗空间区别及插值复用的数值刷新。最终源码/驱动 `88e6c335`，
基线 main `858f021`，交付 [PR #54](https://github.com/saitoasukakawaii/EONSim-new/pull/54)。
所有实现/修复先推送后验证，合并状态以 GitHub 为准。
固定 PETSc 3.23.7 为依据；scalar aggregate 的多向量局部秩风险使 `rigid` 仅支持 twolevel，
不把 near-nullspace 宣称为动态 FSI 精确零空间，也不声称完整向量弹性 AMG 已实现。

本地 a7e0 的 7/7 定向、两种 1/2-rank 真实缩步/重启通过；88e6 报错刷新改动只补受影响
COO 1/1，9/9 计时/取消控制通过，其余复用此前证据而未重复运行。
最终 88e6 源码 CI 实际 56/56 Release、10/10 Python 与四项必需检查成功，来源收据已归档。
最终 78/78 动脉 runs、656 步、1,282 次修正独立重放通过；最大场差 `2.6171e-9`，门槛不变。
细网格 rigid 迭代 `5445→5050`，wall 配对中位变化 `−10.79%`，三次范围跨零；
粗网格及 GAMG 无时间优势，两项均保留可选。没有多节点/GPU/生产规模结论。

可复用错误包括 GAMG 创建层级前调用 PCMG setter、fatal 前未刷新的 stdout 与 MPI stderr
交错，以及 `subprocess.run(timeout)` 对短命令外部计时的轮询影响。
失败原件、两个 binary 来源、逐项命令、统计定义与独立审计均见
[完整证据](data/fsi-block-multilevel-2026-11-26/README.md)，知识草稿保持未发布。

## 2026-11-26 · FSI-PERF-03：实际工作计数、成本分区与输出语义

[未发布开发草稿](../../website/drafts/fsi-runtime-cost-and-output.md)与
[完整原始证据/独立审计](data/fsi-runtime-2026-11-26/README.md)已补齐实测。
生产实现/二进制为 `7e8868e`，带权驱动 `3e366c8`、输出校验修复 `7d86f38`，均先推送后运行。
已完成压力解析列/24 方向 AD、紧凑 AIJ、持久批次团队、最终新残量共用、起点切线一次消费/延后、
稳定分区与显式权重/指纹、紧凑边界与可选 binary。开发与验收完成；
[PR #53](https://github.com/saitoasukakawaii/EONSim-new/pull/53) 最近核验为 open Draft/head `7d86f38`，
最终证据检查及已授权保护合并由其权威状态记录，草稿不发布。

本地 Release **17/17**；源码 CI **48 新执行 + 24 Python**，驱动 CI **1 新执行 + 47 复用、21 Python**，
IO 修复 CI **0 新数值执行 + 48 复用**，来源见证据索引。四组性能 **88 runs / 880 步 / 1,760 次线性修正**
经独立 raw/字段/历史审计，8,502 条哈希收据全部匹配；最大场差 `4.440892098500626e-16`。

可复用结论是用真正的工作量解释收益：同二进制/twolevel 初始切线开关使每次完整 J/USER **30→20**，
callbacks 仍为 20，场/历史精确一致，wall 中位数 **−12.060%～−25.594%**。
对象复用、首矩阵一次性数值消费和后续起点延后须分别记录；任何试探评价后不能沿用消费资格。
显式 `10:5,20:1` 仅在本例 n=8/2 rank 得到 wall **−10.585%**；默认收益混合，
COO 双线程单 rank wall **+3.900%**，没有把局部机制组合拆成未经消融的独立加速结论。

IO **32 runs** 的数组/方向拓扑精确对照通过。Binary 相对同紧凑 ASCII 的 output 时间在 1/2 rank
分别 **−81.338% / −82.010%**，字节却 **+0.815% / +3.060%**；编码与边界裁剪的效果须分开比较。
**24 次 prepare / 168 对 HDF5** 只覆盖 P1 的 2/8/32 分片，空 dataset 以尺寸和类型单独核实。
原 driver 的 `KeyError('reason')` 来自只解析数字字段，求解实际 exit 0、`CONVERGED_RTOL`；
失败原件保留，7d 推送后仅重跑 output。前两组缺少历史分区 shard 哈希收据的边界也明确保留。

性能仅共享主机 1/2 rank、三个测量配对；部分正确性路径覆盖 4 rank。
phase 最大 rank 时间不可相加为 wall，写出未包含 fsync；这些数据不支持多节点、GPU、P2 分区或
通用物理标签成本比的性能主张。理论、实现、验证和性能来源在草稿中分别列明，未公开发布。

## 2026-11-25–26 · FSI-PERF-02：精确图、局部贡献去重与 collective 会话

[算法草稿](../../website/drafts/fsi-performance-completion.md)和
[完整证据](data/fsi-performance-2026-11-25/README.md)记录默认精确图、残量 COO、局部 K→U、
有界线程批次与合资格 SNES/KSP/PC 复用。源码 7f3d12e / 2b0b30b 均先推送后验证。
局部图必须区分 test/trial 投影；移动 RCR 面积导数须显式保留。会话只保存稳定 callback holder，
每次绑定新的借用 Context，并且所有 rank 共同保留/析构；复用对象仍刷新数值 Jacobian/PC。

本轮有实测回退再修复：K 项全局间接排序使细网格单 rank COO 初始化 +23.03%，
改成局部行分桶、短列排序和提前释放临时行数组后，同后端基线配对为 −39.90%。
原始贡献→slot 与数值相加顺序保持，既保留内存收益，也检查 setup 成本。
默认 assembly 中位数下降 9.47%–20.34%；最终 COO 初始化下降 20.17%–47.72%，RSS 下降 2.13%–8.89%。
默认细网格单 rank RSS 增加 4.01%，一些整次 wall 范围跨零；没有将阶段收益或组合优化拆成未经消融的独立因果结论。

本地首轮 13/13 与修复受影响 1/1 通过；远端首轮 51/51，修复 28/28 新执行 + 23 项复用原通过证据。
最终 80 次 / 1,600 步、3,200 次线性修正经独立原始数据复核，13,787 份文件哈希、5,040 份体 VTU 核验通过；最大字段差 6.661338147750939e-16。
中间32次COO与两次审计助手失败原样保留。审计修正分别来自日志显示精度和 Python3.12 sum 的浮点累加语义，未放宽物理或统计门槛。

长期契约已同步[离散算子](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md)和
[并行内存](../architecture/L2_PARALLEL_MEMORY_AND_BACKENDS.md)。
BAIJ 的块布局不适配、halo 双阶段回调收益空间过小均给出当前编号/历史测量依据，而非未经实测的速度断言。
草稿未公开发布，性能适用范围仅本次共享单机1/2 rank和小网格；GPU/多节点不在已验证范围。

## 2026-11-25 · FSI-ASSEMBLY-01：保留稀疏图、固定装配计划与可选 COO

[算法草稿](../../website/drafts/fsi-sparse-assembly-plan.md)说明最终 AIJ 所有权转移、
分别缓存 test/trial 映射、逐次刷新时间权重、融合残量/AD 切线与按物理依赖压缩 COO 的边界。
[源码、实际命令与验证索引](data/fsi-assembly-2026-11-25/README.md)区分
基线二进制 c4fb266、生产实现及候选 df6e9ac、最终驱动 b2ccd964，均先推送后执行。
物理方程、时间历史和接受门槛不变，默认仍为 MatSetValues。

clean df6e9ac 的 PETSc 3.23.7 Release 本地 **8/8 定向检查通过**，覆盖远程图产生和矩阵所有权、
融合单元、1/2-rank FSI、RCR、变步长、retry/restart，及共享代数层的 1/2/4-rank 独立流体路径。
最终两组性能 campaign 共 **64 次运行、320 个接受步、640 次线性修正**，含 16 次预热。
每步 SNES/KSP 次数一致；默认场及历史差为零，COO 最大场差 `2.220446049250313e-16`。
[独立证据重放](data/fsi-assembly-2026-11-25/independent-audit.json)核对全部轨迹、
3,328 份运行文件哈希、1,152 份 VTU 与配对统计，未发现不一致；
[最终归档校验](data/fsi-assembly-2026-11-25/archive.json)已补齐并核对实际二进制、全部内容对象及清单，关闭初审的待打包状态。

默认 assembly 配对中位数下降 **2.72%–11.81%**，COO 下降 **30.16%–43.37%**；
COO 四组整次 wall 变化范围都跨过零，细网格单 rank 峰值 RSS 配对中位数增加 **27.81%**，保持显式选项。
COO 的唯一 nnz 降低 25.70%/28.69%，但贡献值缓冲及 PETSc 内部计划占用额外内存。
可复用经验是将唯一 nnz、单元贡献数、额外容量和 RSS 分开记录，并在同输入、同迭代、同接受轨迹下报告成对成本；
装配核的下降不能直接解释为整次加速。旧基线缺少新的初始化细分，也不能从通用 solver setup 推导图初始化收益。

首轮 pilot 暴露外部 wall 的约 50 ms 量化：根因是 `Popen.wait(timeout=...)` 轮询。
b2ccd 改为阻塞 wait 与独立超时 watchdog，推送后重新运行两个正式 campaign；原 pilot 保留，墙钟不进入最终结论。
配对百分比中位数必须逐对重算，不能用双方独立中位数之比替代；rank 最大分项不能简单相加为整次 wall。

b2ccd 对应 PR merge SHA `ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0` 的 CI
实际执行 **55/55 项 Release 选测**通过，无历史复用、失败或跳过，另有 **65 项 Python 检查**及网站构建通过。
[CI 来源](data/fsi-assembly-2026-11-25/ci-source-b2.json) ·
[数值 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206852) ·
[网站 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206859)。
本地未运行全套、Debug 或 PETSc 3.19.6；CI Debug/3.19.6 手动 job 跳过，选测不等同于全量。
[PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51) 保持 Draft，待用户 review/merge；草稿未发布。

## 2026-11-25 · FSI-PC-03：节点流体反馈和嵌套响应成本

[算法草稿](../../website/drafts/fsi-schur-response-cost.md)解释混合单位节点逆、
结构 USER 矩阵 `K−G H_F E`、实际近似流体响应及其嵌套成本。
[固定源码与验证索引](data/fsi-block-efficiency-2026-11-25/README.md)区分
664a623 比较二进制、66b0a62 驱动和 c4fb266 最终默认源码，全部先推送后执行。

主要结果：节点结构近似通过独立矩阵及物理检查，但此次筛选没有显示有用时间收益，
因此保持实验选项。完整 72 次对照支持将 added_mass 流体和 twolevel 速度默认改为单次 PC 应用，
细网格线性中位数分别由 44.477524/3.931200 s 降至 6.506006/0.609956 s，外层次数反而增加。
直接法在两套小网格上仍更快，不据此声称一般加速或多节点扩展性。

c4fb266 的 clean PETSc 3.23.7 Release 本地 9/9 通过；独立归档重放核对了 1,248 次真实残量和
全部保存场。早期错误类型被最后快照掩盖的检查器缺陷有保留失败记录，修复后 25/25 正负对照符合预期。
可复用经验是：逐次核对实际 solver 观测；分开报告二进制与驱动；区分完整根 Jacobian、
近似隐式 Schur 作用和 P 矩阵；PREONLY 内有容差粗解时仍不能假定固定线性逆；
真实线性残量报告本身不等于新增运行时接受门槛。c4fb266 的四项源码 CI 均通过，
15 项新数值运行、39 项历史复用及其来源详见验证索引。

交付 [PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50) 按本轮授权在四项保护检查通过后合并；
草稿仍待网站人工审阅，未发布。

## 2026-11-25 · FSI-PC-02 嵌套 Schur 与两层校正（本地及源码 CI 通过）

[算法草稿](../../website/drafts/fsi-nested-schur-twolevel.md)区分完整流体消元与
压力 Schur，说明三个 A00 求解器的 PETSc 语义、共享压力 Pmat 的刷新，以及不依赖连续 xyz 行号的
分区常数粗空间。[配置指南](../development/FSI_BLOCK_PRECONDITIONER.md)记录选项及适用边界；
[实际证据与复现](data/fsi-block-2026-11-25/README.md)保留源码、原失败、诊断和最终收据。

本地按来源复用生产修复 `b8ac03a` 的 1/2/4-rank 代数 oracle 3/3 及 restart 收据；
推送后的最终 head `b52281d7585ead08e545f29f8d83eca9177e7eac` 在 clean PETSc 3.23.7 Release
下通过 8/8 项物理/恢复选测，Python 辅助检查 58 项通过。
动脉管 60 次运行通过，12 条 32 步轨迹含 768 次完整系统真实残量检查；
最大残量/目标比 `0.5600385064`，最大相对场峰值差 `1.0712628633e-11`。

可复用经验包括：GAMG 创建后切换 PC 类型可能遗留 `useAmat`；MPI 隐式 Schur 的 PC 应明确使用已装配 P；
全局 KSP 停止容差可能仍高于某个有量纲缩放字段的接受限值；计时超时不能替代数值结论。
两套网格仍以直接法更快，不从有限 rank 或较少外层迭代推断普遍提速、网格无关收敛或完整多层 AMG。
b522 源码远端 53 项 Release 数值选测、58 项 Python 检查、选测/证据收据和网站构建均通过。
[CI 元数据](data/fsi-block-2026-11-25/ci-source-b522.json) ·
[数值 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963270) ·
[网站 run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963330)。
PR #49 仍待用户审核并由用户合并，保持禁止自动合并；草稿未发布。

## 2026-11-24 · 如何解读同网格 FSI 与独立空间参考

| 提问 | 控制与结果 |
|---|---|
| 为什么人工管的相对差能到两位数？ | 1 s 时两程序的端面积增加相差 0.008910 个百分点。相对 svFSI 的小瞬态为 13.82%，相对静态 Lamé 膨胀为 4.0975%。按相同稳定化度量计算，两个非线性程序的端面差缩到 0.00000283 个百分点。[稳定化与四面体编号](data/fsi-linear-transient-2026-11-24/tet-order.md) |
| 换为 20 mm 管是否重现？ | 在同一 80 Pa 缓升压力下，两程序粗网格端部面积增加均约 0.18680%，独立圆形参考为 0.20300%。网格误差大于同网格程序差。[尺度变换与空间参考](data/fsi-linear-transient-2026-11-24/scaled-tubes.md) |
| 流量入口接 RCR 时，哪项影响出口相位？ | 32 步/周期时，仅在 svFSI 离散牵引中对齐阶段，粗网格两程序的复流量差从入口振幅的 1.270% 降为 0.0343%。轴向从 6 层加到 48 层另行改变传递振幅。全周期正向灌流的平均端压遵循总阻力乘平均流量。[流量、相位、压力和储量](data/fsi-linear-transient-2026-11-24/perfusion.md) |
| 两个出口能否只用末端阻力比分流？ | T 形管内腔本身有压损。独立的差压 Stokes 实验预测了同网格恒流分叉结果。充盈阶段还要核对净流量、壁面储量和起始时刻。[分叉验证与储量](data/fsi-rcr-2026-11-24/branched.md) |
| 如何验证端口历史跨拒绝步和重启？ | 用独立解析或分段精确的电容压力、从 VTU 重积的实际端口通量、静默 checkpoint 后的下一步和人工改变曲线的负例分别检验。[压力驱动及采样数据](data/fsi-rcr-2026-11-24/reservoir-pressure.md) |
| Krylov 输出收敛时解实际满足什么？ | 在每次修正后代回相应程序的矩阵。svFSILS 的内外绝对容差与外层投影影响真实残量。EONSim 提供分块和正交化对照，收敛标记、全场误差和进程退出逐项记录。[BIPN](data/fsi-linear-transient-2026-11-24/bipn-residual.md) · [PETSc 场分块](data/fsi-linear-transient-2026-11-24/arterial-solvers.md) |
| 分叉双端流量为何也会相差一半？ | 关闭父支并固定几何，对同一网格改变 PSPG 系数，两个空间算子各自与匹配的独立解一致，终端振幅之间却相差 52.31%。[同网格双端导纳](data/fsi-rcr-2026-11-24/junction-harmonic.md) |

## 2026-11-24 · 压力端面功率与弹性管启动

[技术草稿](../../website/drafts/fsi-pressure-face-work.md)从外压功、有限元压强迹和黏性法向应力解释输出。基于 `3697204` 的 48 扇区圆管区分端点时间求积与两程序真实的位移差，附 EONSim 12 工况与三个步长的固定版本 svFSI 阶跃算例。[数据与验证](data/fsi-pressure-faces-2026-11-24/README.md)

## 2026-11-24 · 网站知识选编

[草稿目录](../../website/drafts/README.md)逐篇登记了 34 份材料。九篇进入四个专题或教程的选稿范围；另从现有调研编成[上游源码阅读指南](../../website/learning/open-source-hpc.md)。主线归档为数值依据，编辑稿用原始波形、节点力、时间步数据和 P2 制造解说明读数。待人工审阅的栏目入口见[知识专题](../../website/knowledge/index.md)和[实践教程](../../website/tutorials/index.md)。

## 2026-11-24 · 仿射 Tet4 黏性核及 50 个上游项目复查

在 `4095e4b` 保留 ALE 几何导数，将单元内恒定的黏性应力及速度切线精确积分一次。局部公式和有限差分、1/2-rank 成对实测、#41/#42 集成证据见[调研报告](HPC_UPSTREAM_REVIEW_2026-11-24.md)。[教学草稿](../../website/drafts/tet4-viscous-work-and-ale-tangents.md)的审阅重点是常黏度仿射假设，以及单元核与全 FSI 计时边界。

## 2026-11-20 / 振荡刚性管的相位与压力迹

Womersley 的圆管解提供复数流量参照。新增末周期投影、三相位全场积分与同网格
svFSI 核验。实现 `62c0b2f`，比较工具 `bef75bd`。已核验 48/8/12
上的流量门槛，计算端面压力仍比施加幅值低 7.58%。草稿待审问题包括
端面压力和内部压力的适用指标，以及时间加密同时改变默认稳定化系数的影响。
刚性管在固定 48 扇区上的细化将端流幅值误差降到 0.7554%，在 24 扇区上仅看端流则会低估域内速度误差。弹性壁的独立平衡试验见 [PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42)。稿件保留在草稿目录。
[基准草稿](../../website/drafts/womersley-flow-and-pressure-traces.md) · [原始证据](data/womersley-2026-11-20/README.md)

## 2026-11-13 / Release 验收与 Debug 故障定位分离

PR 日常正确性依靠 Release 增量 CTest 和复用证据；Debug/GDB/LLDB/sanitizer 仅用于定位实际故障。删除默认 Debug 前必须同步更新 receipt 来源校验和自动合并保护检查，保持 fail-closed；此流程经验已纳入工程规范，不新建知识文章。

## 2026-11-20 / 厚壁管的压力、半径与面积

线弹性厚壁管的 Lamé 平面应变解给出了独立的压力–面积基准。多边形面积对节点位移求导可直接衡量变形，并能与沿边长加权的径向位移交叉核对。两个求解器在同一粗网格上给出了接近的截面响应，同时都超过了解析解的误差门槛。复核时应分别查看几何细化、两程序之差和移动流体体积收支。[文章草稿](../../website/drafts/pressure-area-and-lame-wall.md) · [验证数据](data/lame-wall-2026-11-20/README.md)

## 2026-11-07 / 全场误差与局部质量审计

新增[算法草稿](../../website/drafts/tube-field-errors-and-local-mass.md)，实现
`4113ab8300410459dbfb057db5d4978e7d106aa7`。理论为单纯形多项式矩及散度积分；
验证包含6项解析检查、5组真实稳态网格、1/2/4 rank与归档字段审计。无性能结论，
不宣称完整FSI资格。初始测试预期的手算错误、MPI root启动拒绝均保留。
[证据](data/rigid-tube-seeds-2026-11-07/README.md)。待审：压力迹与域内压力误差
的不同收敛行为、几何误差抵消和剩余局部质量误差。稿件未发布。


## 2026-11-06 / 刚性管混合端面与几何误差分离

新增[数值基准草稿](../../website/drafts/rigid-tube-geometry-and-mixed-boundaries.md)，
实现a0d228764850fa838229acb6a6e613933070490f。理论：充分发展端面应力相容性、
Poisson域单调性给出的cos^4几何界；实现：互斥分量条件、保持多边形的red细分；验证：
11状态/1–2rank、固定门槛加密、Debug/Release与重算；无性能证据。首轮误差抵消及不通过记录保留。
流量误差1.264676%通过，压力仍3.993089%，不扩张为全场/瞬态FSI资格。待审问题是端面定义、
几何界适用对象及剩余局部质量误差；稿件未发布。[证据](data/rigid-tube-2026-11-06/README.md)。
[PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38) 云端Debug/Release各26/26与网站检查通过，
仍待人工审查；完整11状态研究是本地证据，不把CI小回归误报为完整研究重跑。

## 2026-11-06 / 质量预算的非有限值拒绝

源码 `80571b102e31dd2e7664a64a39a92efc8402045c`；`max(0., abs(NaN))`可保留0，故初始状态和累积量必须在最大值归约前验证。时间差容差不能替代接受步长严格为正的检查。扩充[既有周期FSI草稿](../../website/drafts/fsi-periodic-state-and-error-separation.md)，未发布。26项Python检查通过，9组归档22400行重算与原36个预算值一致；无新PETSc/MPI或性能证据。命令与复现详见[会话日志](../development/CODEX_SESSION_LOG.md)。PR #35已合并为815755e，下方未合入描述为历史。


## 2026-11-05 / 固定算子周期误差分离与可恢复证据

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](data/fsi-next-03/local-recovery-2026-11-05/README.md)。

[知识草稿](../../website/drafts/fsi-periodic-state-and-error-separation.md)区分理论、实现与实际验证；无性能结论。
人工审查重点：固定τ解释、经验尾项收缩假设、50/100采样含义与非均匀观测阶。草稿未发布。


## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 自审中的复用知识

连续历史仍可能缺失尾部，必须同时核对声明终点；原时间矩阵在校验配置、CSV SHA和可执行文件后重新分析通过。归档明确区分完整标量历史、最后四周期场和可恢复checkpoint，逐文件SHA回读核对。正式场差使用100实际相位，50/100统计差检验相位积分；20相位重建误差另列。相关说明补入原草稿，完整空间/时间污染预算仍未验收，不发布。

## FSI-NEXT-03 误差分离补充

草稿 [周期状态与误差分离](../../website/drafts/fsi-periodic-state-and-error-separation.md) 补充已验证的三格式时间阶和质量预算阶，以及尚在验证的等长追加周期衰减估计、实际密集采样oracle。时间证据 `data/fsi-next-03/time-accuracy-final/`；默认稳定化空间序列仍在运行。经验几何尾项估计必须注明衰减持续的条件，不能写成严格渐近误差界。未发布，无PR。

## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

2026-10-31 状态同步：G0B/G0/G5/G1 与 INFRA-01 已完成 PR #23 集成，PR #24 已合入。以下按任务保留原证据；历史“待验收”只适用于对应检查点。全部 drafts 仍未发布。

2026-11-03 状态同步：当前 main 为 `4f3a995de45d`。FSI-LOAD-01、FSI-NEXT-01、FSI-NEXT-02 已分别通过 PR #31/#32/#33 合入；FEM-G2A/B/C 已通过 PR #27/#28/#29 合入。下列文章均仍是 drafts，源码合入不自动等于知识文章发布；历史检查点保留其当时状态和原始证据。

本文件是知识资产索引，不代替文章正文、文献阅读笔记或实验原始数据。

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。

## FSI-NEXT-02 / 2026-11-03

[周期流量入口与移动域质量预算草稿](../../website/drafts/fsi-periodic-flow-mass-budget.md)：实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，已通过 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33) 合入 main，合并提交 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`。离散P1入口归一化、无滑移、阶段与secant区别、独立积分和同分区恢复均有实现及验证证据。PR 云端 Debug/Release 各29/29，网站/草稿隔离通过；六周期原始CSV/日志见[验收](data/fsi-flow-2026-11-03/README.md)和 `delivery-ci.json`。无性能证据；空间渐近收敛、严格周期稳态、大规模及高Re均未证明。文章仍待人工审核，未发布。

## G5 独立场generalized-alpha / 2026-10-31

[stage与物理输出草稿](../../website/drafts/generalized-alpha-stage-and-physical-output.md)：
新时刻权重、分离惯性/位移链、算法加速度与端点物理加速度、压力stage及启动。
来源[alpha-standalone.json](data/fem-integration-2026-10-31/alpha-standalone.json)，
理论/实现/真实数值分开，无性能声明。待审核：输出时间语义、启动压力与质量恢复的卸载模型限定；保持draft。

## G5 独立场BDF2 / 2026-10-31

[时间误差与稳定化草稿](../../website/drafts/bdf2-time-error-and-stabilization.md)：
不等距BDF2公式、结构速度未知量重建、固定tau的真实速度/压力时间阶，
卸载结构高频模态进入渐近区的验证。理论、实现、数值证据分开；没有性能结论。
源码与测试来源为[bdf-standalone.json](data/fem-integration-2026-10-31/bdf-standalone.json)。
待审核：稳定化限定、非线性结构/跳跃载荷的未验证边界；保持draft。
后续补充ALE/单体FSI BDF2的压力时间阶、移动网格保持与接口离散功率，
来源[bdf-coupled.json](data/fem-integration-2026-10-31/bdf-coupled.json)，已更新同一草稿；
不将接口功率平衡声称为总能量守恒，非线性材料仅验证状态恢复而非时间阶。

## ARCH-01 / 2026-10-30

[通用 FEM / DoF 分层草稿](../../website/drafts/general-fem-dof-architecture.md)：源码阅读基线
`38a5e516ffe129d1b70c7c1bd8365deb5ded101a`。证据类别为理论/设计与静态实现对应；
没有新数值验证或性能实验，lastVerifiedCommit 留空。配套
[架构规划](../architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md) 与
[20 组上游学习矩阵](FEM_FRAMEWORK_LEARNING_2026-10-30.md)。
待审核非匹配接口的稳定性选择、时间 stage 相容性、DoF 语义与 PC 分组边界；保持未发布。

## HPC-02 / 2026-10-30

[固定 COO 装配草稿](../../website/drafts/fluid-coo-assembly.md)：实现/测量提交 `ceea57d`，
区分局部贡献求和、实际错误同步、1/2/4 rank 验证和 36 次配对性能测量。
保留准备/内存成本、WSL 环境和既有 MPI 故障测试超时限制；仅独立流体 Jacobian。
待人工审查，未发布。

## 状态定义

- idea：值得研究的主题，尚无完整内容。
- draft：已有草稿，尚未审核。
- review：正在人工审核。
- published：已合并到 main 并出现在公开网站。
- superseded：被更新版本替代，保留历史链接。

## 已发布知识

| Topic | 状态 | 主题 | 文章 |
|---|---|---|---|
| HUB-K001 | published | CFD 求解器学习路径 | [CFD](../../website/learning/cfd.md) |
| HUB-K002 | published | 有限元与固体力学 | [FEM](../../website/learning/fem.md) |
| HUB-K003 | published | HPC 与并行计算 | [HPC](../../website/learning/hpc.md) |
| HUB-K004 | published | EONSim 并行稀疏矩阵装配 | [Parallel Sparse Assembly](../../website/knowledge/parallel-sparse-assembly.md) |
| HUB-K005 | published | EONSim 单体 FSI 架构 | [Monolithic FSI](../../website/knowledge/monolithic-fsi.md) |
| HUB-K006 | published | EONSim 构建与运行 | [Build and Run](../../website/tutorials/build-and-run.md) |

## 候选知识主题

| Topic | 状态 | 主题 | 文章/预期证据 |
|---|---|---|---|
| HUB-K007 | draft | PETSc 非线性求解器对象生命周期 | [PETSc object lifetime](../../website/drafts/petsc-object-lifetime.md)；源码审计已完成，后续 setup 测量见 HUB-K011 |
| HUB-K008 | draft | Newton 变量/残量一致缩放 | [缩放规格草稿](../../website/drafts/newton-scaling.md)；独立代数验证，生产缩放仍 deferred |
| HUB-K009 | draft | Schur/GAMG 网格规模行为 | [网格测量](../../website/drafts/schur-mesh-profile.md)；小规模重复数据 |
| HUB-K010 | draft | MPIAIJ 预分配和装配成本 | [阶段测量](../../website/drafts/assembly-phase-baseline.md)、[单元计时扰动](../../website/drafts/fluid-element-overhead.md)；纯通信归因仍未完成 |
| HUB-K011 | draft | PETSc SNES/KSP/PC setup profiling | [多步测量](../../website/drafts/multistep-setup-profile.md)；未证明持久化收益 |

## 登记规则

- 只有形成可复用知识的任务才登记；普通 typo、纯格式变更不登记。
- 每个条目关联文章路径、源码 commit、参考来源和验证证据（如有）。
- 没有运行数据时不得填写性能数值；没有测试时不得标记为已验证。
- 草稿位于公开仓库，不能存放私密研究笔记、凭据、受限数据或未授权论文全文。
- 发布状态只有在文章进入正式栏目并合并到 main 后才改为 published。

## SOLVER-01 / 2026-10-30

草稿：[PETSc 对象生命周期](../../website/drafts/petsc-object-lifetime.md)。证据：固定提交源码审计；无新增数值/性能实测。待人工核对上下文生命周期与计时边界，未发布。

## SOLVER-01B / 2026-10-30

[诊断开销测量草稿](../../website/drafts/nonlinear-setup-baseline.md)：已运行1/2 rank重复测量，具有源码/输出一致性/性能样本证据；无持久化优化收益证据。待人工审核。

## SOLVER-02 / 2026-10-30

[多时间步setup草稿](../../website/drafts/multistep-setup-profile.md)：源码/重复输出/性能证据已归档；无持久化收益证据，等待人工审核。

## SOLVER-05 / 2026-10-30

[重复线性求解的 KSP 所有权](../../website/drafts/linear-solve-ksp-lifetime.md)：代码提交 c47f00d；PETSc 官方生命周期资料、旧实现失败及修复后 1/2 rank 创建/销毁计数与数值验证。无性能数据，未发布；待审核作用域销毁和测试边界。

## SOLVER-03 / 2026-10-30

[Newton 缩放算法草稿](../../website/drafts/newton-scaling.md)：审查基线 717b25b，规格与精确代数脚本 6dc2baf。理论推导、当前代码和独立代数验证分开列示；无 PETSc 集成及性能证据。待审核尺度配置、约束变换及停止准则，未发布。

## SOLVER-04 / 2026-10-30

[Schur 网格测量草稿](../../website/drafts/schur-mesh-profile.md)：脚本/源码提交 79eb826，6 个直接参考、18 个 Schur 样本及原始证据入 Git。包含理论、实现、数值对照与性能证据；仅 108–1372 DoF、1/2 rank，不支持网格无关性或跨节点扩展结论。待人工审核计时与误差口径，未发布。

## SOLVER-04B / 2026-10-30

[求解器层级算子尺寸草稿](../../website/drafts/solver-level-dimensions.md)：提交 124bed3，记录元数据/communicator 语义、实际代码与 Release 1/2/4 rank 验证。无性能收益证据；未设置算子的哨兵分支未单独触发。待人工审核，未发布。

## HPC-01A / 2026-10-30

[装配阶段计时草稿](../../website/drafts/assembly-phase-timers.md)：提交 fff4895，记录时间规约数学、阶段实现与 Release/Debug 针对性验证；无性能收益或纯 kernel/通信归因证据。待人工审核边界及失败路径，未发布。

## HPC-01B / 2026-10-30

[装配阶段测量草稿](../../website/drafts/assembly-phase-baseline.md)：脚本提交 d1708e1，6 个参考和 18 个 Schur 样本、30 份日志及 JSON 入 Git；包含理论/代码/数值与性能证据，未拆分纯 kernel/插入或纯通信。待审核计时与归因边界，未发布。

## HPC-01C / 2026-10-30

[瞬态装配草稿](../../website/drafts/transient-assembly-profile.md)：测量82081d5，独立固体验证0f90585，统计f92e57b；18次运行180步，1/2/4 rank，最终物理解对照和逐步分布入Git。理论、实现、数值与性能证据分开；无纯kernel归因或多节点结论，待人工审核。

## HPC-01D / 2026-10-30

[流体单元计时草稿](../../website/drafts/fluid-element-timing.md)：源码1722265，解释kernel/插入边界与有/无切线计数；Release/Debug各通过steady/transient/tagged 1/2 rank开关对照。没有性能收益或计时扰动证据；仅独立流体，待人工审核，未发布。

## HPC-01E / 2026-10-30

[流体单元计时扰动草稿](../../website/drafts/fluid-element-overhead.md)：脚本1423b99，30个计量样本/15对及6次预热，逐rank数据和39份日志入Git；理论、实现、数值一致性及性能观测分开。范围不支持固定开销或加速结论，待人工审核，未发布。


## QA-01 / 2026-10-30

[profiling日志校验草稿](../../website/drafts/profile-log-validation.md)：实现7b91030，11项回归覆盖72份归档日志与损坏日志负对照；说明NaN比较、整数原因码与根节点完整性。没有新增数值或性能测量；待人工审查协议范围，未发布。


## INFRA-01 / 2026-10-30

[MPI失败与云端恢复草稿](../../website/drafts/mpi-failure-cloud-reproducibility.md)：d3f69d1实现、旧版最小复现和两环境针对性回归；分开控制流理论、源代码、数值/状态与性能未测量。完整套件和CI以INFRA-01报告为准，尚未发布。


## BRANCH-01 / 2026-10-30

本次按 eonsim-knowledge-capture 更新 [MPI 失败与云端恢复草稿](../../website/drafts/mpi-failure-cloud-reproducibility.md)，补充合并验证边界；沿用原开发记录模板，不另建同题文章。新知识为固定 ABI 探针应按环境启用，以及测试结果不能用条数替代名称完整性。6 项合成 XML 回归只证明解析器行为；没有本次编译、MPI 数值或性能证据。原 INFRA-01 数据保留其原提交出处，最终集成验收未运行；草稿仍未发布。取舍见 [整合记录](../development/BRANCH_INTEGRATION_2026-10-30.md)。


## FEM-G0A / 2026-10-30

按 eonsim-knowledge-capture 的 algorithm-note 模板新增 [DoF 身份与嵌套 FSI 分块草稿](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)。固定源码 SHA `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`；理论为固定 K/W、非零 lifting、置换与父编号推导，当前实现为该 SHA 的源码审计，验证仅为标准库 Fraction 合成代数及 1/2/4 模拟分区索引逻辑。没有性能实测、新 C++ 接口或真实 PETSc/MPI 验证，INFRA-01 保持 review。草稿未发布；待人工审查结构速度语义、界面唯一代表、父编号、验收不变性与证据边界。实施契约只在 [FEM-G0A 专题](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md) 维护。

2026-10-31 合并补记：FEM-G0A 源提交 b674d5a 已完成本次设计/参考验证审查，20 项测试复验通过；检查工具修正 UTF-8 与 CRLF 兼容。设计子任务已合入，知识草稿仍为 draft，生产 C++/PETSc/MPI 验收范围不变。详见 BRANCH-02 合并清理记录。

- 2026-10-31，FEM-G0B：[语义DoF与父编号](../../website/drafts/semantic-blocks-and-parent-numbering.md)，draft。理论/工作区实现/实际小rank检查分级；后续集成与兼容证据已在 PR #23 补齐，不自动发布。

## G0 补强 / 2026-10-31

[真实装配置换与PC验收草稿](../../website/drafts/assembled-permutation-and-pc-verification.md)，按benchmark-report模板。区分置换理论、工作分支实现、主锁Debug/Release 43项与兼容补验、72个受控测量样本。该提交 CI 及最终 PR #23 交付已完成；草稿未发布。

- 2026-10-31，G5耦合alpha：更新[stage与算法历史草稿](../../website/drafts/generalized-alpha-stage-and-physical-output.md)，记录共同stage/独立历史、极小步消减误差与端点集体验收；真实数值与源码审查分级，草稿未发布。

- 2026-10-31，G1：[规范化网格与双线性标量单元](../../website/drafts/normalized-mesh-and-bilinear-scalar-elements.md)，benchmark-report草稿。记录文件/拓扑/空间分离、原生Q1、独立矩阵与收敛、零空间和restart数据文件身份；源码/PETSc-MPI/审查分级，无性能测量，未发布。

## DEV-PROCESS-POLICY / 2026-10-31

项目级持续知识积累规则已写入根目录 [AGENTS.md](../../AGENTS.md)，并同步到 [进度](../development/CODEX_PROGRESS.md)、[任务队列](../development/CODEX_TASK_QUEUE.md) 与 [会话日志](../development/CODEX_SESSION_LOG.md)。要求实质任务保存真实过程与测试证据，维护跨 Task 状态；有复用价值的技术成果才形成 `website/drafts/` 文章，且必须经人工审核后才能发布。该条目记录的是研发流程规则，不是算法或数值结果，因此不另建技术文章。源码/规则变更通过 PR #24 追踪；本任务未运行 C++ 编译、CTest、MPI 或性能测试，CI 结果以 PR Checks 的实际状态为准。


## DOCS-01 / 2026-10-31

基线 `a508e3d`，本地分支 `codex/markdown-progress-audit`。全仓 [Markdown 审查](../development/MARKDOWN_AUDIT_2026-10-31.md) 同步现行状态与历史证据边界，并按 eonsim-knowledge-capture 更新已有 DoF、BDF2、alpha、COO、生命周期草稿；原模板与理论/实现/验证/性能分级保留，没有新数值或性能数据。静态检查命令和未验证项见审查记录。没有新技术成果需要独立文章，所有草稿仍为 draft，未发布。

DOCS-01 交付补记：已通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合入 main（be21882）；远程主锁 Debug/Release 各60/60、网站构建及草稿隔离通过，旧锁专项 skipped。命令与运行链接见 [审查补记](../development/MARKDOWN_AUDIT_2026-10-31.md#远程交付补记)。仍无新算法/性能文章，草稿未发布。


## TEST-POLICY-01 / 2026-10-31

验证约束更新的原始检查点：基线 `3df1c31`，由本地分支 `codex/incremental-validation-policy` 交付；该分支当时未推送、未合入 main。约束内容随后由 CI-INCREMENTAL-01 的提交 `ef20e03` 随 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26) 合入 main（`35bf1a1`）。规则见[增量验证与历史证据复用](../development/BUILD_AND_VALIDATION.md)：仅检查新增或受影响行为，已通过且未受影响的测试不重跑，全量仅在用户明确要求时运行。原始文档检查未运行编译或数值测试；无新算法/性能结论。


## CI-INCREMENTAL-01 / 2026-10-31

[PR 增量 CI 与证据复用草稿](../../website/drafts/incremental-ci-and-evidence-reuse.md)：基线 ef20e03，开发分支 codex/pr-incremental-ci。说明路径映射、精确测试清单、同 PR 成功证据与必需检查状态的边界；PR #26 已合入 main（`35bf1a1`）；本地脚本检查、云端 Debug/Release 各一项 Poisson 和后续文档提交的零构建/零数值运行复用均已验证，见 [initial.json](data/ci-incremental-2026-10-31/initial.json)及[reuse.json](data/ci-incremental-2026-10-31/reuse.json)。无性能结论，不发布。


### FEM-G2A 局部检查点

P2 参考三角形六节点插值、六个多项式的值/梯度重现及反向边迹已通过直接 C++17 编译验证。源码为本条所属提交；命令与范围见 CODEX_SESSION_LOG 的 FEM-G2A 记录。尚无生产求解、MPI 或收敛证据，完整知识草稿待闭环完成后形成。


### 2026-11-01 — FEM-G2A 共享边空间

[草稿](../../website/drafts/p2-edge-space-poisson.md)：源码 edfc73c，参考基函数、离线实体空间与 P2 稳态 Poisson 已实现；本地 Debug PETSc 3.23.7、1/2 rank patch/收敛/失败证据见 data/p2-2026-11-01。理论、实现与实际验证分列，未测性能，PR #27 云端 Debug/Release 各 19 项相关检查通过，实际 merge preview 60ee8e26；证据 data/p2-2026-11-01/cloud.json。PR #27 已合入 main（`c0745ea`）；文章不发布。


### 2026-11-01 — FEM-G2B 边界与物理均值

更新[现有 P2 草稿](../../website/drafts/p2-edge-space-poisson.md)：源码 d6ec424，新增 Robin 边迹矩阵及纯 Neumann 相容性/零空间/体积均值解释。本地 Debug、PETSc 3.23.7、1/2 rank 相关数值及拒绝检查通过；命令见会话日志，证据 data/p2-boundaries-2026-11-01。PR #28 云端 run 41287626201 的 Debug/Release 各 10 项相关检查通过；PR #28 已合入 main（`1bc87a7`），文章仍未发布。


### FEM-G2C 启动检查点（2026-11-02）

基线 `1bc87a7`，当前未提交改动增加 P2 解析一致质量矩阵 oracle；独立 C++17 检查通过，命令与边界见 [会话日志](../development/CODEX_SESSION_LOG.md)。生产瞬态功能、MPI、checkpoint 尚未实现或验证。本检查点不生成文章，不构成功能交付或性能证据。


### FEM-G2C P2 瞬态历史（2026-11-03）

- 草稿：[P2 瞬态扩散：一致质量、时间层和完整历史](../../website/drafts/p2-transient-history.md)，未审核、未发布。
- 实现 `d19a03268577b33ddfb41177037d9bbc1f76d273`；BE/BDF2/一阶 alpha、P2 空间签名及同分区完整历史恢复、接受步输出。
- 理论证据：一致质量的重心坐标积分、统一时间方程和 alpha 边界时刻；实现与验证分开标记。
- 本地 Debug 分项与 Release 五项 P2 检查通过，真实 1/2 rank；8/8 HDF5 历史/空间补验通过；命令及失败尝试见会话日志，原始摘要见 [源码与证据](data/p2-transient-2026-11-03/source.json)。
- 无全量、旧锁、超过 2 rank 新验证或性能结论；PR 云端结果后续登记，不把本地结果称为云端通过。


FEM-G2C 云端补验：[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29)，run 41582475827，PETSc 3.23.7 Debug/Release 各 15/15 相关项通过；网站 run 41582475766 通过。源码仍为 d19a032，merge preview b8c1642；详见 [云端证据](data/p2-transient-2026-11-03/cloud.json)。PR #29 已合入 main（`dff9116`）；草稿未发布。


2026-11-03 合并状态核对：PR #29 已在远端合并为 dff911648e54507e9cca80ad1880c20b867a0c75，本 agent 没有执行合并。最终云端证据补记提交晚于合并，作为纯文档后续 PR 提交；知识文章仍保持 draft。


## 2026-11-03 / FSI-LOAD-01

- 草稿：[单体 FSI 的时变载荷与接受步历史](../../website/drafts/fsi-periodic-pressure-history.md)，未发布。
- 实现：`a6c6761084f2003c72593107c6aa5cbc351d75bb`；理论为项目阶段时间约定与 smoothstep 多项式，代码为候选步压力及集体输出阶段。
- 验证：[PETSc 3.23.7 Debug/Release 本地证据](data/fsi-pressure-2026-11-03/README.md)，含 1/2 rank、时间精度、恢复、实际缩步、I/O 失败及完整装配切线。
- 复用教训：评价时间与终点量不能混记；双域节点 owner 与本地域单元存在性不同；粗步未进渐近区不能放宽精度门槛。无性能或生产规模结论。

FSI-LOAD-01 补充：PR #31 已合入 main（`06b05c4`）；云端主锁 Debug/Release 各 24/24 与网站检查通过；[CI 摘要](data/fsi-pressure-2026-11-03/ci.json)。草稿仍未发布。

## 2026-11-03 / FSI-NEXT-01

- 草稿：[单体 FSI：非零入口、终点有效性与可解释的加密研究](../../website/drafts/fsi-inlet-endpoint-and-resolution.md)，未审核、未发布。
- 实现 `0d93d41`/`69692ee`，研究脚本 `32783a5`。理论证据为本质边界的线性阶段关系、三角面插值积分；实现与实际验证、性能分开描述。
- [本地验收与数据](data/fsi-next-2026-11-03/README.md)：PETSc 3.23.7 Debug/Release 各 4/4，真实 1/2 rank 拒绝/恢复和切线；分场时间阶、时间污染受控的空间轨迹；Release 30 正式性能样本，最多 4 rank。
- 可复用教训：阶段有效不代表终点有效；界面节点集不等于界面面片；加速度放大位移误差，非线性与线性停止条件须相容；时间污染未控制前不解释空间阶。
- 小网格直接法更快，较大网格分块内存较低，但不证明大规模加速；无非匹配界面、重网格或生产规模结论。详细未验证边界和人工审查问题留在草稿中。

FSI-NEXT-01 补验：旧镜像弹性体几何路径 Debug/Release 各 1/1；本地两模式各累计 5 项独立检查通过，详见同一验收目录。PR #32 已合入 main（`b2755b6`）；知识草稿仍未发布。

## 2026-11-06 — Circular FSI inlet and conforming tube (draft)

[Discrete inlet flux normalization](../../website/drafts/fsi-circular-inlet-discrete-flux.md).
Implementation `718b7a6bb97fbb5eed09829a0bb7225d3963ee5f`; mathematical derivation,
MPI implementation and small-case verification are distinguished. Evidence in
[data/fsi-tube-2026-11-06](data/fsi-tube-2026-11-06/README.md). No performance or
physiological accuracy conclusion. Review required; article remains draft.
