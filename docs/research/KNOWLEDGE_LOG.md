# EONSim Knowledge Log

> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

用户最新选择：取消全量上传，先推送单独快照分支 `codex/fsi-progress-snapshot-20261109`。完整本地分支和工作区未改写；不创建PR、不合并、不自动恢复计算。

2026-11-09 10:35 CST：用户停止全部后台工作并授权上传当前进度。
[停止快照](data/prod48-user-stop-2026-11-09/README.md)区分用户取消、原数值失败、已完成局部验证和
未完成资格；保留原中断记录，不将控制器failed改写为通过。α1 N400解析U1.0163191685%仍失败。
成熟FSI成本/rawreview报告与N800冻结采用计划已补存小型证据；大轨迹归档中断，尚未完整提交。
已有压力历史草稿补入停止边界，保持draft；无数值重跑、PR合并或文章发布。

2026-11-09 10:23 CST：3b08e4f的可选FSI LU已通过真实满载32态成本及完整raw复核，
旧两次baseline146.111/149.516s、新默认149.287s、新window32为61.423s；字段/全历史/v4时钟
均通过，实际分解32→1。另存window8和重放，明确共享CPU与局部窗口，不推广为全程或扩展性。
新N800粗细家族经过具体计划核对后采用，从零统一细步保留16周期加载和32周期总时长；
空间、时间、尾项、采样仍用原P1算术和.1门槛。已有压力历史草稿补入真实采用与证据边界，
新计算仍未完成，原N400三项预算失败保留；完整成熟证明与执行计划归档尚在进行，未发布。

2026-11-09 09:50 CST：[可选FSI LU验证](data/fsi-retained-lu-validation-2026-11-09/README.md)
接入线性周期压力双网格generalized-alpha，默认关闭。流体/固体/位移映射有不同有效系数，
全部参与失效判断；非线性通过后的几何拒绝也不能留下可误用缓存。Debug/Release、1/2/4rank、
事件/变步/重启及3696HDF通过，缓存几何拒绝未单独触发。分解次数不代表生产加速，满载成本
与长程另验；更新已有压力历史草稿及契约，不发布。

2026-11-09 09:35 CST：[完整S24时间预算](data/elastic-s24-eonsim-time-budget-failure-2026-11-09/README.md)
显示周期/守恒/Lamé通过仍可能留下占空间差91.33%的压力时间差；三项时间预算失败，全部
尾项和采样通过。按实际数值分开记录执行成功与数值门槛失败，不用二阶假设缩小预算。
默认稳定化含有效时间系数，现有两级差不能独自确定误差来源或阶数。补入既有压力历史草稿，
未发布。后续可选FSI LU仅开发/验证中，需完整状态、收敛及真实成本证明后才采用。

2026-11-09 09:12 CST：源码复核修正[压力研究执行说明](../development/FLUID_PRESSURE_TIME.md)中的
过时Schur-only限制。步内Jacobian复用、跨步LU预条件因子和accepted积分历史是三个不同
对象：每次solve仍创建新SNES，只有已接受的显式MUMPS因子先detach后保留；有效积分系数
改变时集体刷新，重启重建执行缓存。链接实际MUMPS入口、系数刷新和成本档，保留原cfa5d3c
“仅准备”的历史边界。同步已有Womersley草稿；本次仅文档，不改运行时或重跑无关测试。

2026-11-09 09:00 CST：[四组参考前缀](data/reference-full-load-prefix-20261109t005527z/README.md)
区分“输出步数”“方程收敛”“满幅步覆盖”和“完整周期资格”。仅封存低于最高native的
完整边界及对应日志前缀；前三组已有400/1900/400满幅步，第四组仍在ramp，全部严格
相对收敛也不证明周期稳定。94源文件/6普通Git包保留原日志、native和60份冻结输入。
既有参考程序草稿补入这一证据边界，不新建文章、不发布。

2026-11-09 08:42 CST：[N200完整审计与原长度对照](data/elastic-n200-audit-and-length-summary-2026-11-09/README.md)
证明L12五场周期2.49415e-7及质量/J/均值门槛通过，L24仍周期失败。两者平均位移差只有
Lamé尺度.32204%，动态径向幅值3.71209e-5与9.57156e-6，相位差-73.41246度。
均值接近不能推断动态响应相同，改变长度还改变分布式惯性；原长度kernel结果只作响应
敏感性记录。完整跨程序预算仍待完成。未启用扩展只改总步数、须完整重放证明后才能采用。
原压力历史草稿补入实际值，未发布；原始大轨迹和小报告包分别保存，不互相冒充。

2026-11-09 08:26 CST：[L24完整审计与原生重放计划](data/length24-periodic-audit-and-native-proof-plan-2026-11-09/README.md)
显示平均径向Lamé误差1.55968%通过，固体速度周期1.09245e-5/1.05679e-5仍失败。
均值准确、瞬时方程收敛和周期稳定是不同条件；延长周期前先用实际原生6200→6400与
6390→6400重放证明历史连续性。原检查点每200步保存，证据数量必须按真实可用状态列出，
不能把210输出场对写成210原native历史对。现仅证明在跑、复核排队，没有延长生产采用。
已有压力历史草稿补充，原c32失败保留，未发布。

[α1N200完整档](data/womersley-alpha1-n200-lu32-complete-2026-11-09/README.md)4116files/79parts
整档Git回读后仍保留速度1.01644%FAIL1%；归档数量和周期稳定不能代替细网格解析及预算。
Womersley草稿同步保存这一边界。两批本地提交只管理真实证据，没有提前上传或资格声明。

2026-11-09 07:54 CST：[S96α1执行准备](data/alpha1-s96-execution-preparation-2026-11-09/README.md)
把模板检查、真实测量、具体计划审查和长程采用分开：22项静态检查可证明错误配置被拒绝，
但不能代替尚未运行的三模式成本与1440数据集raw复核。只读检查明确ready=false且未创建
生产状态；六份粗细分析源相同，原粗Q幅值FAIL保持。已有Womersley草稿补充，未发布。

2026-11-09 07:34 CST：[LU与时钟源码复核](data/solver-clock-source-review-2026-11-09/README.md)
在7ed5a5d确认十五份相关源码/测试与实际验证快照逐字一致，复用未受影响的历史检查。
执行缓存与accepted算法历史的持久化职责不同：因子在失败/重启后重建，v4补偿余量必须恢复。
修正L2状态文档的过时无缓存描述，补齐有效积分系数刷新契约；既有Womersley草稿更新。
没有新增运行时修改、构建或测试，不把局部源码审查称为整体验收或独立外部审查。

2026-11-08 23:25 UTC：完整原始轨迹归档后仍保留原采样失败。
[3323文件S96 N400完整档](data/womersley-s96-n400-complete-family-2026-11-09/README.md)
显示N200/N400解析与周期指标通过，但N200速度采样项为其空间差11.5648791%，超过10%。
新N400目标必须用自身空间分母和独立N800时间控制，不能重新解释旧budget。84个普通Git
包分三次有界提交、整档回读后才保存完整manifest；只是存储完成，不是物理资格。既有草稿同步。

2026-11-09 07:10 CST：S96α1粗N400的速度/压力和周期项通过，但流量幅值1.44703%
仍FAIL1%；[完整3279文件证据](data/womersley-alpha1-s96-coarse-n400-complete-2026-11-09/README.md)
保留不同观测量的不同结论，不用周期稳定或某个场误差通过替代整组资格。
[实际L24自然边界](data/n800-capture-and-l24-retirement-2026-11-09/README.md)把数值完成、
等待父退休与后续完整审计分开；进度读取器必须优先使用真实收据和身份，避免沿用滞后的
phase标签。同档的N800归档等待器只是静态准备。既有Womersley草稿补充，未发布。

2026-11-09 06:59 CST：[实际原生600交接](data/reference-nu0-n200-native600-handoff-2026-11-09/README.md)
将局部后端证明与真实采用明确分开：旧数值自然停止且所有旧身份退出后，保存完整前缀、
原生seed和旧6400后置条件失败，再开始新续算。旧失败不改写，新增长输出不提前归档。
[三个运行中参考前缀](data/reference-live-prefix-20261108t224736z/README.md)逐字冻结后检查
方程收敛，只证明指定完成区间，不覆盖末期周期或误差预算。既有参考草稿同步，未发布。

2026-11-09 06:38 CST：[nu0N200完整后端证明](data/reference-nu0-n200-ilut-backend-proof-2026-11-09/README.md)
保存真实100态与10态重放、全部rank原生算法历史及独立原始数据复核。局部40%左右节时仅用于
明确范围的执行策略选择；早期ramp一致不等于满载/长期物理通过。独立实际600交接另行留证。
[alpha1筛查静态准备](data/alpha1-s96-execution-screen-preparation-2026-11-09/README.md)
把已排队方案与尚不存在的数值结论区分，继续已有参考草稿而不新增空泛文章。

2026-11-09 06:30 CST：[完整S24细采样档案](data/elastic-s24-fine-eonsim-complete-sample-2026-11-09/README.md)
将已通过的有界审计与全部1200态current/history绑定，并保留原OOM和失败消费者。
五场周期、Lamé均值及质量门槛通过只证明本算例指标，不能覆盖未完成的跨程序与时间/空间预算。
前期只有精简报告时的“完整轨迹仍封存中”现已由4995文件/143包完整档案补齐；不重算PDE。
继续补充既有参考草稿，未发布。

2026-11-09 06:12 CST：α1 N200六周期稳定不等于解析速度通过。
[完整诊断与S96下一组静态准备](data/alpha1-next-grid-preparation-2026-11-09/README.md)
保留1.0164446% FAIL1%及全部其它原始指标。30秒资源快照只观察guest利用率，不推导
宿主物理核隔离或因果成本改善。补充既有Womersley草稿，未发布。


2026-11-09 05:34 CST：误差预算小于空间差10%，仍不能覆盖解析误差超标。
S48 N200/N400时间、尾项、采样六项均通过，但速度误差分别1.04682%/1.04599%仍FAIL1%。
[8162文件完整轨迹与预算](data/womersley-s48-n400-complete-family-2026-11-09/README.md)
保留该结论。大档案以完整普通Git包分批提交，每批有字节回读，整份manifest等全部153包
全量验证后才提交，避免把中间存储检查点称为完整证据。沿既有Womersley草稿补充，未发布。


2026-11-09 05:01 CST：周期场通过只是跨程序比较的前提。独立mesh-nu0粗N400的全部
12800步和1200态完成后，ALE周期6.61e-6通过，但中部压力幅值差3.11277%及两程序Lamé
均值误差3.19504%仍超原门槛。[1408文件完整证据](data/elastic-s24-coarse-n400-nu0-reference-pair-2026-11-09/README.md)
保留全部原始状态和400相位P1差异，不用周期通过替代物理一致性或空间/时间预算。
长管数值仍在运行，旧后处理依赖已退休的L12路径，预先规划仅后处理的自然边界接续；
[48文件准备证明](data/length24-postprocessing-preparation-2026-11-09/README.md)包含真实临时父子
进程控制fixture和逐字原分析kernel，不等同真实6400轨迹/后处理通过。既有参考草稿已补充，未发布。


2026-11-09 04:38 CST：比较内存对象与序列化报告之前，必须明确JSON会把整数键变为字符串。
参考1200态复核完整输出后由该键类型差异失败，单独读取两份JSON并逐值核对后，所有
物理/质量指标和旧收敛值精确一致；原failed仍保留，不重算数值或偷偷放宽浮点容差。
[122文件完整证据](data/reference-bounded-reader-and-preparation-retry2-2026-11-09/README.md)
同时保留新旧静态恢复预案，正常producer不能因此被恢复/替换。
[23文件只读前缀](data/reference-live-prefix-20261108t202936z/README.md)只证明选定完成区间，
不提升为整条轨迹或物理资格。既有参考草稿同步，未发布。


2026-11-09 04:10 CST：解析和时间误差通过仍可能被采样预算拒绝。S96 N200速度采样
占最后空间差11.5649%，保留FAIL；新N400必须用同N400粗细网格重新算分母，并独立做N800
时间控制，不能只换更有利的采样项。[45文件细化证据](data/womersley-s96-n400-budget-refinement-retry2-2026-11-09/README.md)
记录原失败、精确分辨率替换及尚未完成的N800。未启动数值任务的提前调度也须显式输出
所有权与消费者路由，原冻结目录guard拒绝重复运行的实际fixture已通过；当前细参考未
signal，[69文件接管证据](data/reference-nu0-early-companion-ownership-2026-11-09/README.md)不声称未来旧队列已退出。
[759文件alpha1完整交接档](data/womersley-alpha1-native200-lu32-handoff-2026-11-09/README.md)已封存并Git逐字回读。
沿既有两篇草稿更新，没有新建或发布文章；原长程物理资格仍需完整证明。


2026-11-09 03:45 CST：真实进程收尾可能长于模拟进程fixture。alpha1的数值进程与
driver已退出，但原owner虽已写failed仍晚于40秒退出，交接器应保留失败而不是强改成功。
它随后自然退出；新控制器只重核既有完整种子/数值命令和资源，迁移控制/分析目录后继续。
5种fixture证明的控制函数不等于所有实际运行时收尾都受同一时限保障。完整旧轨迹和两份
失败正在同实际交接一起封存；新长期资格仍需全周期和误差预算，短程成本收益不能替代。
沿既有Womersley草稿记录这一限制，未发布。


2026-11-09 03:27 CST：有界内存分析器已实际完成细网格1200态：五场周期性、运动学、
阶段守恒与正Jacobian通过，Lamé均值误差1.237613%通过2%；完整参考/预算仍需单列。
[34文件完整审计记录](data/elastic-s24-fine-bounded-audit-report-2026-11-09/README.md)不冒充尚在捕获的全数值轨迹。
交接时即使当前子计算很慢，也可能恰好跨过分段边界。5种实际模拟进程验证“短暂持有
driver、核对身份、退休旧队列、先挂终止信号再恢复driver”的顺序；提前失败必须恢复
同一driver，其他进程保持运行。[81文件验证](data/alpha1-retirement-control-validation-2026-11-09/README.md)只证明控制流程，
不能替代真实数值/成本筛查。沿既有参考草稿补充，未发布。


2026-11-09 02:53 CST：S48N400完整六项误差预算PASS，但解析速度1.045991%仍FAIL；
不能把时间误差已受控解释为几何/空间精度已合格。原alpha1真实200seed筛查现已开始。
完整轨迹归档需同时预算原件与Git对象空间。[55文件存储证明](data/git-cross-drive-storage-proof-2026-11-09/README.md)
验证普通blob在D、默认Windows/WSL读取以及不依赖alternates的独立clone；实际采用仅新增
对象存储，没有移动/删除既有证据或改变Gitconfig。分批暂存与整个档案完成分别留证。
沿[既有Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)补充，未发布。

2026-11-09 02:35 CST：已将独立nu0预算切换到有界内存分析器与恢复后的EON结果。
日志路由必须按真实生产者区分：fine为完整续算链，coarse/time为family目录完整日志。
86文件[交接证据](data/reference-nu0-bounded-budget-consumer-2026-11-09/README.md)保存
4路径检查、独立审查和仅退休空闲等待器的收据，数值生产者不变。
S48 N400 U1.045991%仍FAIL1%，不能将时间步减半误报为速度已合格；其余预算继续。

2026-11-09 02:22 CST：完整周期审计的缓存规模应按“相位数×网格状态”核算。S24细1200态
审计触及2GiB，数值12800已成功；保留路径重读上一相位即可保持积分顺序和全部指标，
完整粗1200态逐值等价且峰值约35MiB。弱引用回归在旧代码失败、新代码通过，Windows/WSL
各9项。细补审计仍进行，不能把粗等价当细物理资格。
[完整修复证据](data/pressure-audit-bounded-memory-validation-2026-11-09/README.md)。
更新[既有参考审计草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)：
区分已完成数值、后处理资源失败与恢复分析；新预算重审续算轨迹必须保留显式完整链。
实际1600交接和独立nu05000交接均封存，所有旧失败保留，文章未发布。

18:06调查记录（验证未完）：完整细N400数值成功后，审计缓存整400相位的节点字典
触及2GiB。路径级缓存可保留相同积分顺序，代价是重读前一周期数据；不能将分析资源
失败误称数值不收敛或降低采样数。旧缺陷复现及9项回归通过，完整粗1200态逐项等价
仍在验证，暂不宣称完整细审计通过。原OOM和下游失败保留，沿既有草稿后续补证据。

17:51补充：PETSc直接分解的事件名称随后端调用路径变化。原SuperLU_DIST以
MatLUFactor记16次，新MUMPS以MatLUFactorNum记8次；同一读取器强制同名会产生假失败。
独立复核应保留事件种类、实际次数和原始profile，不能把“没有该事件”解释成没有分解。
[完整1400同态证据](data/elastic-n200-mumps-chord-option-proof-2026-11-09/README.md)保留首次
失败、修正后独立回读、全部24对字段/历史及两次包围基线。约69–70%局部收益不能替代
满载/末周期资格，继续等1600边界证明。参考native1100已实际接续，补档覆盖原审计
命令/失败日志；原轨迹与新的待验计算仍分开记录。沿既有参考草稿补充，未发布。

17:29补充：N200参考候选的真实100态后端对照和10态原生重放经独立回读通过，成本由
3004.39s降至1590.48s；只说明该有界对照中的收益，不外推为整个生产段提速。原成功
基线逐字复用，同时保留旧诊断审计失败；[556文件完整证据](data/reference-n200-midnight-backend-proof-2026-11-09/README.md)
包含全部字段/原生历史和资源。新1100自然边界仅已请求，未采用。沿既有参考草稿
补充证据适用范围；全长收敛、周期和误差预算继续独立验收，未发布文章。

17:08补充：原参考自然结束4000后，原完整12800审计失败和旧冻结解析器的跨午夜拒绝
分别保留。接续必须绑定真实检查点、完整前段收敛、已审查的后端变化及全部输入来源；
不能将失败日志改成成功，也不能仅凭新进程运行宣称全程通过。218文件原生4000
[不可变交接证据](data/reference-fine-native4000-handoff-2026-11-09/README.md)已实际Git回读。
新轨迹、完整周期与预算另行验收；沿既有参考草稿补充，未发布。

16:40补充：固定svFSI诊断计时只取当天秒数，跨午夜可出现负elapsed；物理时间和
完整算法状态并未倒退。解析器应分别约束诊断字段与算法状态，不能将残差、范数或
来源校验一起放宽。真实100态与单/双rank记录、Windows22项、WSL28+8项及CI26通过；
原误拒绝、错误“所有rank计时都相同”断言与准备审查失败保留，见
[344文件完整证据](data/reference-midnight-diagnostic-audit-2026-11-09/README.md)。沿既有
[参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)补充，未发布。

16:11补充：恢复生产者后须检查所有下游，独立nu0预算的最终比较也曾指向旧EON失败
路径。新消费者保留同一数值族、逐字预算tail和同版报告约束，通过实际输入与封存
报告回读后才退休无子任务的旧等待器；没有向数值程序发信号。见[57文件交接证据](data/reference-nu0-budget-consumer-handoff-2026-11-08/README.md)。
沿既有参考草稿补充，未发布；替换等待器不等于数值预算或物理资格通过。

16:01补充：完整S96细N200六周期的速度/压力/流量幅值误差为0.475826%/0.360074%/
0.234326%，六项初步门槛通过；同网格N400与空间/时间/尾项/采样预算仍未完成。
[完整1672文件证据](data/womersley-s96-fine-n200-complete-2026-11-08/README.md)保留全部
实际存储历史，不把初步解析通过当作完整资格，也不覆盖原S48速度失败。沿既有
[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)补记，未发布。

15:43补充：旧S24细EON在11600预热成功后被22/23独占检查拒绝采样，原因是已有参考
程序使用CPU23；预算等待器随之退出。分别保存数值成功与调度失败，不修改旧日志。
新目录用同一二进制和原11600状态做两态整段/分段重放，22个HDF数据集、五场节点/P1
质量及旧v3clock差全0后才采样。逻辑CPU22与guest sibling23共享须如实标注，不能写成
物理核独占。新预算消费者显式连接恢复后的路径，避免原状态失败后下游悄然失联。
原生停止与同版报告审查已完成，见[完整停止证据](data/reference-native-stop-and-handoff-preparation-2026-11-08/README.md)；
修订后参考交接目前只请求4000自然停点，尚未真实采用候选。沿既有参考草稿记录，未发表。

15:00补充：固定svFSI可通过results/STOP_SIM在完整状态写出后正常退出；首次把触发
文件放cwd的独立试验未生效，已保留失败并受控清理。正确单/双rank各10态实际验证
与不中断oracle五场及原生算法状态一致。长期交接仍待独立审查，不能把源码存在或
退出值0视为证明；沿现有参考草稿记录，未发布。

14:17补充：S12同版分析器恢复已完成，所有报告值除SHA外一致；S12/S24完整比较仍保留
Lamé/ALE失败。新增显式v2执行切换来源契约，保持v1默认拒绝后端变化，要求真实全场/
原生历史/重放证明与准确物理输入绑定。Linux23+8、Windows受影响4项、两真实proof绑定
及原S12完整链均通过；没有后端交接或物理合格声明。Windows短路径别名误判和归档
root拒绝均保留，见[验证档](data/reference-backend-transition-contract-validation-2026-11-08/README.md)。
沿[参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)补充，不发表。

12:06补充：S12两份审计因分析器SHA不一致被交叉比较正确拒绝，采用同一冻结版本
重算EON后处理并要求其它报告值完全不变；不删除来源门槛，也不重跑数值轨迹。
参考800态结果显示ALE周期2.625e-5仍FAIL。双rank100+100+10筛查完成、成本比
.765242，独立审查仍待；mesh-IC数值通过但成本比1.420609，已拒绝。沿同一
[参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)记录，原始失败和
[淘汰选项证据](data/reference-rejected-mesh-ic-and-placement-2026-11-08/README.md)均保留。

11:45补充：S12真实6400数值结束后，launcher返回0但辅助MPI进程尚在资源组，控制器
按原规则failed并清空自有scope。保留该失败、801场文件和最终原生状态，再在独立目录
补做原定审计，不把退出值当收敛证明、不自动重跑整段计算。完整6400收敛链已PASS；
全场物理审计仍进行中。执行收尾、数值输出完整性、收敛与物理资格是不同证据层。
沿[参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)记录；未发表。

10:57补充：固定svFSI双rank文件使用最大rank payload作为共同直接记录长度，较小rank
有105000B尾部padding；它不属于Yn/An/Dn。新审计显式绑定每rank布局、step/time/范数，
保持serial契约；19参考+8压力测试和五份真实文件解码通过，实际双rank恢复仍在试验。
沿[参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)记录，不发表。
基线1374b625，变更及冻结SHA见[原生记录证据](data/native-two-rank-record-audit-2026-11-08/README.md)。

固定原码内置ILUT的启动与实际满载6000步续算，五场/完整历史/保存范数/时间经独立
回读通过；20步265.064→127.284秒，10步重放除elapsed逐字一致。证据只支持有限串行
执行筛查，不支持长期物理资格或自动交接。第一次双rank试验因共享CPU位置竞争取消，
保留失败和空scope收据，新位置重试；不通过提高优先级挤占主计算来制造性能收益。
S24粗EON虽然周期与守恒通过，Lamé3.195039%仍FAIL2%；S96粗N400初步通过也不能
代替细层预算。执行证据和物理门槛继续分开。

10:06尺度复核：冻结alpha1执行读取器采用0.02/(4*12)归一化速度差，实际L=2的
Poiseuille中心速度尺度为0.02/(4*2)。原筛查尺度更小六倍、门槛更严，不能把此量
误写为生产解析速度RMS；README与草稿已明确。原代码、排队任务和物理预算不变。

09:58补充：Alpha1读取器在已完成启动证据上新增完整当前/上一时间层P1质量检查，
320数据集通过；实际200态执行交接仍待筛查，不能把读取器验证当作交接验证。
新S96粗N400只是同网格时间对照，原细层空间分母与预算不变。沿
[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)补记，未发表。
参考Trilinos后端仍处独立构建试探：其原生ILUT含零对角替换，不能由选项名推断
离散方程等价。保留原二进制，待全字段、原生历史及成熟checkpoint对照，不提前采用。

09:12补充：S24粗N400原网格nu.3参考也已完成，31/32周期ALE位移差均约2.2113e-5，
未过1e-5；其余四场、收敛及质量通过。与既有网格闭路机制诊断相容，但不能仅由此
推断具体因果或宣称独立nu0细系列合格。保留完整原失败，沿
[参考求解器草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)补记；未发表。
新原生续算证明及CI检查已归档；物理验收与执行/审计正确性继续分开。

08:58补充：上述S12原生证明现已通过。20态全场与原始结果相同，10态重放的全部
序列化历史除elapsed外逐字相同。真实日志的两段及三段链也通过，原失败尾部明确
排除。完整字段审计强制完整链而不接受一个晚期日志，并绑定原始边界场文件字节。
16项参考与8项压力审计测试通过；新6400恢复已启动，仍不代表完整物理资格。

## 2026-11-08 / 原生续算必须保留原失败与分段收敛证据

S12参考计算在原定12小时限时后止于5641完整步，5600原生重启状态仍在。有限续算
筛查在新目录进行，先比原有20态，再从5610重放10态，检查全部序列化历史和保存时间。
此时尚未验证通过；原来只接受Continue0的收敛审计不能直接套用或修改日志规避，
需显式验证输入、二进制种子、连续步区间与各段最终迭代。初次资源组创建竞态失败也保留。
已通过的S96粗层802保留态MPI核验是独立成果，不替代细层或参考续算验收。

## 2026-11-08 / 完成状态与资源锁、周期性与精度分别验收

08:14补充：同一CPU21、同6GiB边界和S96细网格，四rank窗口32为632.061秒，原生
单rank为394.727秒；三执行路径960数据集独立回读、节点/历史及P1质量范数、精确
v4均通过。这是给定资源布局下的实测成本，不能概括成并行扩展性。特别区分分区
MPI单rank与原生串行驱动：两条路径都测量并比场后，才采用匹配的长期启动方式。
新粗/细/时间研究已启动，完整误差预算仍待运行完成。沿既有Womersley草稿补充，
完整筛查原始档案正在捕获；没有发表或推送。

`a6643c8`后的完整S48细alpha2虽已稳定，U1.046822%仍FAIL1%；新S96粗层虽U/p
低于1%，Q幅值1.058047%仍FAIL。S12细弹性EON末两周期五场和阶段质量通过，
无限长平面应变Lamé均值差4.802660%仍FAIL2%。不能以周期、守恒或轨迹完整性
替代最终精度和独立误差预算；沿[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)
补记，未发表。

已实际出现一次控制时序失败：生产者释放资源锁后才发布completed，后继即使拿到锁
也可能仍读到running。失败发生在任何数值工作前，保留原始记录；新控制器在锁外等待
终态，入场后复查，独立路径绑定消费者。资源可用与证据就绪是两项不同条件。
新32态筛查尚在运行，不能把成功启动当作筛查或长研究通过。

固定参考版本的NS/BIPN和RCS两试探均在600秒限时内未完成全部20态，未采用；实际
编译参数早已有-O3/-march=native。保留超时、警告、未完成状态和已清空的资源记录，
不把选项存在或编译缓存中的简写当作可用性/性能结论。完整原始档案正在串行构建。

## 2026-11-08 / 复用策略必须识别时间系数，失败门槛也保留完整轨迹

06:49补充：[完整成本档案](data/lu-refresh-startup-cost-2026-11-08/README.md)独立回读2560
数据集、真实分解事件和空scope后，只有新32窗口对前后两baseline均达到10%收益。
新8虽比前baseline快20.18%，却只比后baseline快5.70%，仍不采用。新32局部57.494秒
允许新粗层长研究，不等于物理资格；实际运行波动、错误checker和未采用模式均保留。

[S96启动筛查](data/rounder-mesh-startup-screen-2026-11-08/README.md)表明实际分解4→1
仍可慢33.66%：BE首步因子在BDF2阶段产生11–12次线性迭代。依据有效时间系数变化
[主动集体刷新](data/lu-time-coefficient-refresh-2026-11-08/README.md)后，Debug/Release
各6项、各1005完整HDF数据集通过，实际事件计数覆盖空owner、变步、事件及alpha；
这只是正确性，独立成本筛查仍需完成。默认PREONLY被筛查脚本误当FGMRES的失败
保留，新控制器重查已有成功状态后续算，不修改失败记录或数值门槛。

[完整中层轨迹](data/womersley-alpha2-middle-lu8-complete-2026-11-08/README.md)周期通过
而U1.851116%仍FAIL；[细单周期诊断](data/womersley-cycle4-diagnostic-2026-11-08/README.md)
U1.046822%仍FAIL。均保存全部原始状态而非只留汇总，细长期和空间/时间/尾项/
采样预算另行验收。沿既有[生命周期草稿](../../website/drafts/petsc-object-lifetime.md)
及[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)补充，不发布。

## 2026-11-08 / 接续来源和存储完整性分别留证

[中层八步及交接](data/womersley-middle-lu8-2026-11-08/README.md)把连续原轨迹、重启旧
配置、新默认、新缓存四组比较分开记录；成本达标后独立回读再采用。后继空间分母
必须显式绑定新中层，不能只改细网格。原暂停恢复与最终退休是不同时间事件，
[完整fine600交接](data/womersley-lu600-handoff-2026-11-08/README.md)保留旧部分轨迹及
计划中断原状态。沿既有[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)
和[对象生命周期草稿](../../website/drafts/petsc-object-lifetime.md)补充证据，未发布。

[存储验证](data/archive-storage-validation-2026-11-08/README.md)证明同16个HDF只改变
tar成员次序能在本样本减少35.64%字节，且逐字可还原；不能推广为所有轨迹节省率。
隔离Git fixture及实际39,834,848B索引回读证明外置本地包仍可进入完整普通Git blob，
省去稀疏工作树重复副本。归档完成与实际索引完整性必须分别核验，不使用路径指针
冒充公开结果；原件未移除，无物理/并行资格新结论。

## 2026-11-08 / 实际分解减少之后仍核验完整成本与轨迹

[细LU八步证据](data/womersley-fine-lu-screen-2026-11-08/README.md)保留相同600种子下
旧默认/新默认/新缓存三组：实际分解8/8/1，474.624→116.530秒，完整160个HDF数据集
max1.03433e-16、v4时钟exact。独立回读后才另行采用；窗口8只改变预条件器执行策略，
长期解析场和时间/尾项/采样预算不能由这组性能筛查推导。核组标签按WSL guest解释。
更新[生命周期草稿](../../website/drafts/petsc-object-lifetime.md)与
[脉动流预算草稿](../../website/drafts/womersley-field-and-error-budgets.md)，不发布。
同一档案中的参考前缀检查剔除整条最高在写步，全部前缀通过只用于提前发现问题，
不替代完整reference audit。

## 2026-11-08 / 输出文件、成本门槛和虚拟机拓扑分别核验

[参考资源筛查](data/reference-allocation-screens-2026-11-08/README.md)保留四rank首步
停滞、GMRES200变体输出5但MS第5步未收敛、双rank20态正确但9.68%收益未达10%的
三个不同结论。未放宽门槛或采用新长期策略。沿
[参考对照草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)补充此证据。

[Windows/WSL拓扑](data/execution-topology-2026-11-08/README.md)显示16宿主核与12个
guest核组不能混用；更正可读说明中的“物理核”，原始哈希档案保留。虚拟CPU亲和性
是实现证据，不能单独证明宿主物理核隔离或扩展性。草稿未发布。

## 2026-11-08 / 筛查、采用和长期验收保留独立证据

补齐[76文件细资源筛查](data/womersley-cgroup-screen-2026-11-08/README.md)、
[157文件执行预检](data/production-followup-preflights-2026-11-08/README.md)与
[77文件接受态交接](data/womersley-mumps460-handoff-2026-11-08/README.md)。前者只给
eligible，随后460→原连续463完整历史复核才触发采用；增长中的长程输出不混入完成
档案。这些证据不表示新LU缓存细筛查已通过。沿既有Womersley草稿的资源策略解释，
没有另造算法结论、修改门槛或发布文章。

## 2026-11-08 / 暂停等待者，让大数值状态自然释放

e435524后的[126份控制前置证据](data/lu-cache-screen-startup-2026-11-08/README.md)验证
只暂停研究parent、数值child自然结束再恢复的机制，以及真实四rank分解次数日志读取。
当前细网格控制器仍等待600；启动证据不能当作性能通过。资源所有权与恢复责任补充到
[生命周期草稿](../../website/drafts/petsc-object-lifetime.md)。
[原r4完整24246文件](data/pressure-production-rank4-2026-11-08/README.md)归档完成，
保持1/4rank五场一致性与legacy时钟失败分开解释。没有发布或PR。

## 2026-11-08 / 保留PC对象不等于保留LU因子

d0f9bb3后的可选LU缓存用独立`MatLUFactorNum`事件发现SNESReset会清掉共享PC因子；
必须先解绑旧KSP、清除DM/应用上下文，再提交缓存。当前Jacobian和原字段接受保持，
旧因子只作FGMRES预条件。默认关闭，失败/窗口/options变化及重启失效。
[2859份原始证据](data/lu-preconditioner-reuse-2026-11-08/README.md)含两次失败、Debug10项、
明确来源的Release10项、真实1/2/4rank完整历史、1/2rank研究入口及26项CI规则检查。
尚无细网格成本或长期采用结论。补充到[对象生命周期草稿](../../website/drafts/petsc-object-lifetime.md)，
仅将已验证的所有权规则写入并行内存契约；未发布。

## 2026-11-08 / 完整重放与未通过的中层结果分别归档

[生产时钟重放19302文件](data/pressure-clock-replay-2026-11-08/README.md)补齐v4修复的
真实双rank400步精确时钟、完整历史及五场对照。它不追溯恢复旧格式丢失的补偿。
[有界直接解16文件](data/womersley-direct-bounded-failure-2026-11-08/README.md)保留
地址空间分配失败；[alpha1中层1563文件](data/womersley-alpha1-middle-n200-2026-11-08/README.md)
保留速度1.66366%未过1%的结果。capture5091b68与数值源/二进制身份分开记录。
结论补充到既有[时间历史草稿](../../website/drafts/fsi-periodic-pressure-history.md)和
[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)，没有发布。

## 2026-11-08 / 资源策略变化必须另立证据，不能改写原失败

3.5GiB/rank虚拟地址空间限制下的直接解失败仍保留。另行预声明的整作业14GiB、
swap0限制，经实际内存失败/MPI继承检查后完成细网格同态筛查：候选181.986秒，
原配置353.400秒，max字段5.2965e-12，历史过门槛，但采用仍须独立交接。
显式MUMPS入口及嵌套会话整作业清理的[331份证据](data/womersley-mumps-entry-2026-11-08/README.md)
已核验；原连续计算已恢复，长程资格尚未完成。补入既有
[Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)，未发布。

## 2026-11-08 / MPI进程组不是完整作业边界

真实OpenMPI5把rank放入不同进程组；启动器先退出时，rank仍可存活在原新会话中。
Linux研究入口按完整自有会话与PID启动身份清理，保留原失败及清理收据，不影响旁侧
会话。[24份验证](data/linux-study-session-cleanup-2026-11-08/README.md)包含超时、中断、
提前成功、真实MPI和原等待器明确替换。补入既有MPI故障草稿，未发布。

[原时钟失败24550文件](data/pressure-mpi-original-clock-failure-2026-11-08/README.md)与
[完整nu0参考1783文件](data/reference-mesh-nu0-2026-11-08/README.md)已回读核验。
[指标图](data/reference-mesh-nu0-comparison-2026-11-08/README.md)明确：周期漂移改善不等于
压力幅值或Lamé均值合格，独立变体仍需自身细化预算。补入既有参考求解器草稿。

## 2026-11-08 / 筛查先约束资源，变体各自保留预算

细网格直接解筛查应预声明内存、时间和自有进程清理边界，同态比较后才讨论采用；
启动不等于字段或成本通过。内部网格运动参数的独立变体也必须建立自己的空间/时间
配对，不能借用原变体的预算。[30份启动记录](data/bounded-followup-startup-2026-11-08/README.md)
保存待执行筛查与独立nu0预算等待器，复用的预算函数经结构相等核验。补充原Womersley
草稿；实际筛查/预算仍未执行，原研究和失败不变。

## 2026-11-08 / 分段入口与运行交接分开验收

新入口通过并不意味着已冻结控制器自动采用它。[114份替换证据](data/segmented-queue-handoff-2026-11-08/README.md)
记录等待器身份核验、数值工作前取消、原`finally`恢复外层父进程以及新等待器接手。
当前数值子进程身份未变。主alpha2完整600/连续603三步复核只是已安排的未来交接，
不能写成已经完成。补充既有Womersley草稿，原始失败、执行成本与物理资格仍分开。

## 2026-11-08 / 合法时限还需要有界计算段

入口接受86400秒，不等于细网格的多周期调用一定能在该时限内完成。显式自然周期
分段保持总物理终止时间、保存频率和问题定义，通过完整checkpoint衔接各段。
[604份真实验证](data/womersley-segmented-execution-2026-11-08/README.md)区分v4精确时钟
与旧v3近似恢复契约；两版本各1/2rank所有13存储态及历史通过。补入既有Womersley
草稿。尚未更换已运行控制器，不把新入口通过写成长期研究已采用或物理合格。

## 2026-11-08 / 时间补偿也是恢复状态

生产长轨迹揭示：物理场通过容差检查，并不保证恢复后的时钟逐位相同。原v3未保存
补偿求和余量，使400步中183步时钟不同，最终差1ULP；旧文档未承诺逐位时钟。
v4显式保存该accepted算法状态，旧v3保留带诊断的近似回放，不猜测丢失历史。
[10464份验证文件](data/checkpoint-clock-v4-2026-11-08/README.md)保存精确源码、
Debug/Release各8项通过，以及真实四rank快照双格式读取/4项损坏输入拒绝。
真实生产400步精确时钟、完整历史及周期/质量审计已通过，大归档仍在捕获。
补入[既有时间草稿](../../website/drafts/bdf2-time-error-and-stabilization.md)，未发布。

## 2026-11-08 / 网格运动路径与待执行参数检查

[34份闭路诊断](data/reference-mesh-loop-2026-11-08/README.md)复现既有基准，并在严格相同
边界路径下细化回放：200→800段仍有约1.93e-5漂移，单形状往复降至约2.05e-7。
首谐波与原闭路近乎相同，支持路径依赖解释；内部网格参数扫描仍只属反事实。
新nu0完整耦合对照已启动但未验收，原nu.3失败不变。补入既有参考草稿。

[70份队列修正](data/womersley-time-queue-recovery-2026-11-08/README.md)记录自审发现
超出真实CLI限制的运行时限、执行前取消、自然周期边界分段和8项实际入口守卫检查。
参数入口通过与数值成功明确分开，未改运行冻结源或放宽任何数值门槛。

## 2026-11-08 / 独立截面参考与配对定义

[106份P2截面证据](data/womersley-polygon-reference-2026-11-08/README.md)把S48/S96几何差
与三维离散误差分开。制造解、真残量、积分和相邻细化通过；S48速度差约.45%–.50%，
S96约.11%–.12%。保留双精度残量停滞和校验器精度混用的失败，经扩展精度修正满足原门槛。
观察到的细化增量不是严格误差界，误差范数也不能直接相减。科学图及输入哈希一并保存。
更新[既有Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)。

[L24的66份预检](data/pressure-length-preflight-2026-11-08/README.md)证明中段局部网格完全
匹配，仍需完整动态结果；长度还改变惯性，不能把所有变化归为夹持端误差。
[37份时间后继证据](data/womersley-time-queue-2026-11-08/README.md)保留等待时不持主锁、
补控制量资格前提的自审和旧等待器取消。更新原参考草稿，均保持未发布。

## 2026-11-08 / 启动失败与冻结控制器交接

冻结脚本遗漏间接生成器导入、流体保存间隔0被正确拒绝，两种启动失败都保留并在
独立attempt2修复。中层三步末态差1.717e-12通过。待执行细网格probe的同项错误在
试算前修正：取消旧等待控制器，经finally恢复原调度，再由新冻结控制器接手，原
数值进程身份未变。[390文件](data/production-queues-2026-11-08/README.md)区分完成预检与
运行快照。补入既有Womersley草稿，不将计划取消/导入失败写成物理不收敛。

## 2026-11-08 / 速度块语义与成本证据

显式速度三分量元数据先验证 owned 语义和所有权，保留根AIJ矩阵和压力子块。
Debug六项、Release五项加同源码失败补验一项通过；真实1/2/4rank小管第三步与LU差
最大1.012e-13。细网格三步末态差5.08531e-12，局部耗时减少26.392%，峰值内存却增加。
保留单物理核心MPI空等超时、恢复与源码相等复用记录，见[967文件](data/womersley-vector-metadata-2026-11-08/README.md)。
扩充[既有Womersley草稿](../../website/drafts/womersley-field-and-error-budgets.md)和DoF使用契约；
没有把局部收益或插值常数候选写成通用性能、精确零空间或长期资格。

N400两边求解收敛，但参考内部ALE周期和中部压力幅值仍失败；
[8289文件](data/pressure-tube-n400-2026-11-08/README.md)分别保存时间/尾项/实际采样，空间分母未完成。
诊断图显示相位改善不等于所有门槛通过。另保留S24归档硬链接断言失败，解引用后的
[79文件](data/pressure-s24-preflight-2026-11-08/README.md)通过字节核验，无PDE重算。
扩充[原参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)，均未发布。

同态弹性直接解另有[103文件](data/elastic-direct-options-2026-11-08/README.md)：MUMPS加步内复用
局部三步17.956→6.633秒且末态差3.47e-17，串行SuperLU却更慢；这里只允许进入细网格
确认，不能直接改运行研究。[3126份alpha1后续文件](data/womersley-alpha1-followup-2026-11-08/README.md)
保留两项仍未完全通过的真实周期结果，不将同时改变空间和时间的两列当作单项误差分离。

独立S24第400步复核随后通过：21.886→14.335秒、末态差7.454e-20；
[116文件的交接证据](data/execution-continuations-2026-11-08/README.md)将已完成的短复核与
尚未完成的长续算分开记录。原日志多出的401/402步保留，从完整400步重算，参考目录
保持原路径。扩充同一草稿，不把检查点交接、短程一致和长期验收合并成一项声明。

## 2026-11-08 / 闭合边界并不保证增量内部网格闭合

实际N100/N200参考网格被独立回放重现到约1e-15；严格闭合的边界历史仍留下约1.93e-5
内部网格漂移，而固定几何的同一伪弹性控制回到约1e-16。保留元素体积归一化及真实
历史，才足以把该粗网格路径效应与未结束暂态区分。原参考未修改，周期门槛未放宽。
[4298文件](data/pressure-tube-time-2026-11-08/README.md)同时保留时间/尾项/实际采样差和N200失败门槛；
空间分母未完成，不作预算通过声明。静态[108文件](data/lame-static-2026-11-08/README.md)另展示
壁面均值改善与非单调全场差并存，支持条件不能与夹持FSI混用。
[109文件的夹持端部配对](data/clamped-static-2026-11-08/README.md)另外比较同局部网格下L12/L24，
静态中环变化约.30%–.39%，仍不作为动态误差界。扩充
[既有参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)，未发布。

## 2026-11-08 / 迭代减少不代表成本降低

同一完整接受态的三步粗/细网格PC对照通过字段门槛，但两场HYPRE只在粗网格更快，
细网格总时间反增。仅压力HYPRE有局部收益，未改变运行研究的策略。
[94文件](data/womersley-schur-options-2026-11-08/README.md)保留真实命令、层级、成本与限制，
扩充既有Womersley草稿，不外推通用性能。弹性同多边形细化五步检查和微小启动参考检查
通过，[123文件](data/pressure-tube-space-preflight-2026-11-08/README.md)核验；长研究尚未验收。

## 2026-11-08 / 输出、收敛、周期态是三个独立条件

固定参考PIC.f可在迭代上限后继续写场；ramp2/c12的1215个方程步未达相对标准。
新日志审计按全部步骤/方程核对相对值并绑定导出清单，缺证据不得进入比较资格。
收紧线性绝对容差的真实短程检查与失败均保留，非线性1e-10不变；
[181文件](data/svfsi-convergence-2026-11-08/README.md)核验，相关最小检查通过。
原132周期参考全部求解收敛，但内部ALE位移未周期稳定；EON缩短启动后的全场对照通过，
参考同项失败。不能把求解完成、物理场稳定和内部网格稳定相互替代，也不能把一个程序
的预热结论外推另一个。扩充原参考草稿，N200仍在计算，无完整资格或发布声明。

## 2026-11-08 / General载荷符号、回卷和启动证据

固定参考的General输入不自动加Fourier路径的压力负号，IGBC又对表末时间取模；必须
显式负压力并在运行终点后增加一个结点。两个实际100步均匀压力检查通过精确离散递推，
5项导出、7项审计和6项制造启动比较通过；[288文件核验](data/pressure-general-input-2026-11-08/README.md)。
长预热EON已周期通过，短ramp2/c12仍失败，不能以启动函数较光滑替代场证据。
参考启动另暴露OpenMPI5/4的MCA选项隔离问题，清除库路径还不够；无求解的初始化失败
单独保存和重试。恢复器的锁释放/外层状态更新竞态也保存并修复。扩充原参考草稿。
alpha1首个周期场仍未达精度，见[2071文件](data/womersley-alpha1-first-2026-11-08/README.md)；没有新增资格声明。

## 2026-11-08 / 稳定化参数分离与窗口真实初态

[受控N200研究](data/womersley-fixed-time-2026-11-08/README.md)完成1000步并核验1574文件；
默认减半dt同时改变tau时间项，两种影响必须分别表达，场差模长不可相加。固定参数的
粗网格精度仍未过，不能替代默认资格。细网格步内Jacobian复用三步一致性通过后显式派生续算。
[窗口审计](data/pressure-tube-window-2026-11-08/README.md)必须读取真实前一接受态，不能把
预热后的体积当作零状态。11项制造检查和4项导出检查通过；故意违反端约束的制造场仍不合格。
551文件核验且保留失败；扩充现有Womersley与参考对照草稿，没有新增重复文章或物理完成声明。

## 2026-11-08 / 真实参考输出的精度契约与首次弹性结果

首轮两边600步完成后，实际svFSI坐标的Float32存储暴露了此前Float64制造输入未覆盖的
读取问题。精确模拟输入节点的binary32序列化、拒绝碰撞并核对拓扑后，恢复原输入几何
用于积分；没有扩大物理容差。6项单位检查与真实VTK双精度类型制造读取通过，原场重审
通过运动学和阶段质量，但周期及中部压力比较未过。更新[原参考草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)
及[审计契约](../development/PRESSURE_TUBE_FIELD_AUDIT.md)，无弹性完成声明。
新增时间尺度Debug/Release各1/1及显式阶段压力输入已实际通过；未复跑无关测试。
步内固定Jacobian还发现PETSc API与命令行lag=-1的区别；原失败保留、受支持-2先做实际探测。

## 2026-11-08 / 弹性观测量与嵌套双域场比较

比较辅助工具在源码检查点7a344a9上通过5项观测量/拒绝检查与3项嵌套场/双读取器检查；
全部是已知信号、仿射场和制造历史，无新PDE求解。28原始文件回读核验，
见[证据](data/pressure-tube-comparison-2026-11-08/README.md)。零振幅相位不可判为通过，
只在实际嵌套拓扑上使用精确P1质量范数。固定参考源码还确认增量伪弹性与本项目
固定参考Laplace网格扩展不同，跨代码参考坐标场差不作Eulerian同点误差解释。
扩充[原参考对照草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)，门槛不变，真实耦合仍待运行。
已有Womersley定位数据另生成PNG/SVG并检查版面，原数据哈希未变。文章均留在drafts。

## 2026-11-08 / 脉动流误差定位与解析插值筛选

采样补充：0eb4544上用已有100相位历史检查50相位线性重建；正弦RMS参考差1.6e-17，
线性参考差8.89e-16，3文件核验归档。该差不能外推为100→200预算，原草稿已说明。

管端补充：5cd0c2b上读取已有场，分别积分压力迹和重建`p-2mu*du_x/dx`，
仿射参考积分最大误差1.164e-13。两份诊断文件复制核验；弱牵引与重建强应力的区别
已补入原草稿，无新PDE结果、不增减精度门槛、不作公式缺陷归因。

执行策略补充：cfa5d3c将COO/步内chord选项固化入研究身份，4项不启动MPI的续算/拒绝
检查通过，7文件核验。新选项数值一致性和计时尚未运行；显式接受态来源与新研究目录
用于避免覆盖旧定义。[准备证据](data/womersley-execution-2026-11-08/README.md)与原草稿已同步。

补充实际BDF2历史中的tau系数分项与同状态减半dt的敏感性；200次前一步逐文件交叉
检查完全一致，稀疏N200未做该项。两份原始分析文件核验归档，系数变化不作场误差
归因或界限。源码检查点f7a32f6，结果与方法已补入下述证据和原草稿。

冻结b072已有三组周期场在2189a8c分析实现上重新定位；速度误差仍遍布中部，
非第一谐波分量很小，但没有证明具体根因。节点插值、数值场误差和两者差分别保留，
不以范数相减归因。[定位补充](data/womersley-first-2026-11-07/README.md)有独立哈希清单。
另对六组网格仅做解析插值/形状检查，34原始文件逐一回读核验；
[网格筛选证据](data/tube-mesh-screen-2026-11-08/README.md)不代表PDE精度或性能验收。
扩充原[周期场草稿](../../website/drafts/womersley-field-and-error-budgets.md)，没有另建重复文章。
源码检查点4fc5002；全部仍在本地，草稿未发布，未push/PR。

## 2026-11-07 / 双域输出身份与阶段质量审计

静态阅读固定svFSI发现两方程同名Displacement；显式Alias分别保存结构位移和网格位移，
避免读取器同名覆盖。新审计按实际参考坐标和四面体拓扑映射两域，排除未被域使用的输出点；
区分材料中截面、投影面积、组装阶段质量和终点体积积分。算法、事前归一化与待验范围见
[定义](../development/PRESSURE_TUBE_FIELD_AUDIT.md)，并扩充[参考对照草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)。
仿射积分/精确质量/谐波/拒绝/输出映射五项检查通过，导出3项与选测26项通过；实际耦合仍待执行。
源码2189a8c，独立VTK实际丢弃旧同名数组之一；不同名数据的物理值完全读回，参考坐标差1.11e-16。
两条完整48快照制造历史恢复已知谐波/阶段时间；[185原始文件](data/pressure-tube-audit-2026-11-07/README.md)
已核验。制造数据明确不作真实弹性计算证据。
未发布文章，未创建PR。

## 2026-11-07 / 周期场误差与参考输入的离散检查

源码检查点d280e7f；新增[Womersley误差草稿](../../website/drafts/womersley-field-and-error-budgets.md)
和[参考压力时刻草稿](../../website/drafts/reference-solver-discrete-pressure-check.md)。
冻结b072的前三个Womersley状态均未通过速度门槛，时间预算也未通过；周期稳定不等于精度达标。
[5169原始文件](data/womersley-first-2026-11-07/README.md)全部归档回读核验。
svFSI固定7bdb74c均匀压力100步通过精确离散递推；旧ASCII、未压缩与填充失败均保留，
原生zlib导入通过双读取器；[213原始文件](data/svfsi-import-2026-11-07/README.md)已核验。
可选tau时间尺度已编译、尚待数值检查；显式阶段压力转换尚待真实参考运行。
两篇均区分理论、实现、实测与未完成部分，没有性能结论，保留drafts。
静态复核后b9075f0补充固体区域标签保持：几何正确不代表材料/区域语义正确；
新压力管实际标签与配置一致的3项检查及原网格3项通过。旧准备输入保留，首次耦合仍未运行。

## 2026-11-07 / 稳态细网格的压力迹与局部质量门槛

扩充[现有全场审计草稿](../../website/drafts/tube-field-errors-and-local-mass.md)，
求解器c218c18、研究入口b072cc8。447073节点四rank六项预设场门槛通过；
较粗状态端压/散度未通过，默认Krylov预算失败也完整保留。只增加迭代预算，未改容差。
1/2/4rank与LU对照限定1737节点；不外推最大网格直接法验证或均匀h阶数。
[原始归档](data/rigid-tube-schur-2026-11-07/README.md)共78文件已逐一核验哈希。
无性能、瞬态或弹性资格结论，文章继续留在drafts。

## 2026-11-07 / 脉动压力的阶段取值与离散参考

新增[算法草稿](../../website/drafts/pressure-stage-and-discrete-flow-oracle.md)，源码b072cc8。
理论为均匀加速流的直接代入和三种时间格式的离散递推；实现包括零均值压力、阶段载荷及接受态采样。
Release四项相关检查、三格式1/2/4rank、续算/拒绝通过；最大离散参考误差1.98e-16。
Debug和Womersley定量资格在该证据点未运行，无性能结论。
[证据与原始数据](data/fluid-pressure-time-2026-11-07/README.md)。待审为阶段/端点压力解释与旧重启签名保持。
稿件仍在drafts，不发布；48小时整体任务继续，尚未push/PR。

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
