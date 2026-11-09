# EONSim Codex Session Log

> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

用户最新选择：取消全量上传，先推送单独快照分支 `codex/fsi-progress-snapshot-20261109`。完整本地分支和工作区未改写；不创建PR、不合并、不自动恢复计算。

## 2026-11-09 02:35 UTC / user-requested stop and current-progress upload

用户先停用eonsim-new-48定时任务，随后要求停止后台计算，再明确要求将当前进度提交远程。
该新指令授权在物理验收未完成时上传当前分支，未授权合并；本次不创建PR、不恢复计算。
stop-all-prod48-user-20261109.py先核验PID/start_ticks，再通过pidfd向等待器/归档器和生产父进程
依次SIGINT，让原有清理逻辑处理自有scope；20控制器、36初始相关进程、9scope全部退出/空。
02:38另次只读检查无活动数值进程。没有共享scope信号、删除结果或覆盖原失败。

[停止与报告快照](../research/data/prod48-user-stop-2026-11-09/README.md)逐字保存147小文件/3218279B，
来源SHA独立列出。包含成熟FSI完成证明及rawreview、N800实际计划/采用/周期收据、α1 N400解析报告。
α1 N400的2400数值及解析已完成，U1.0163191685%FAIL1%；后续middle/time/space预算中断。
其它停止前步数由原日志进度记录保留：四参考7660/9319/4464/2426，α2N8003099，L24新增314，
新FSIN800粗7807/细999。所有原完整测试、成本与物理失败边界不变。
原进度器在终态缺失cycle时显示N800 step0只是读取缺省，不意味着数据清零；README明确标注。
中断L24轨迹103包、重放证明42包、成熟FSI证明19包均无完整archives.json，不暂存、不冒充封存。
新计划大档尚未开始；其小型冻结证据本次另存。未重跑任何数值测试，全部原数据和检查点保留本地。

## 2026-11-09 02:23 UTC / mature FSI proof and actual uniform N800 adoption

47675完成满载6200端点六模式：五组32态耗时146.110702/149.286529/61.422504/75.718240/
149.515772s，16态重放34.651153s；MatLUFactorNum32/32/1/4/32/1。
176场对与144native对1584datasets全部通过，最大node6.2241878e-15、P1mass2.3668619e-12、
history1.5312621e-14，legacyclock0且new/new v4精确。47710在新目录重读622raw文件、全部指标
精确重算；使用同一比较器，不声称外部或独立算法审查。原report SHA1c86c9ce66b360a6ed970d31364bc9da01782f6553ac41d9d9ca0a8428ad9dc4，
rawreview SHA67dfd443e33b4f42d4ea669d8b908600546be65e26fd956aeb63e0fc09bb3f4b；全部2Gswap0、零事件/空scope。
47776捕获1308完整原始文件及来源，仍增长；后继完整L24延长捕获同控制器排队。

随后实际运行run-fsi-s24-n800-lu32-family.py prepare；review-fsi-s24-n800-execution.py于02:16:27
在独立2Gscope核查21构建源、64数值命令、两域实际红加密嵌套、全部原物理/容差和预算算术。
新definition c6c5e5d9c9a23d0eafeb479439c83633fd72df8bbbfe5b526f0105bd97309540。
准备自审期间纠正了未运行草稿的最终snapshot命名：main输出config.output，只有历史PVD带restart后缀；
冻结和数值启动前已修正，未运行错误路径。各周期同grid/v4续算，初始零残量不要求不存在的KSP正原因，
任何实际启动的线性求解仍必须全部完成且正收敛。

冻结controller的run --role fine于02:16:57由47914/session25412采用，run --role coarse于02:17:21
由47944/session35201采用；budget由47952/session93166于02:17:38锁外等待。候选6993/LU32、
native1rank，fineCPU22/coarseCPU19 nice19、各2Gswap0、12G入场/8G底线，原其它进程未signal。
新两组均从零统一N800，32周期25600步/原16周期ramp，末三周期2400态及实际前端点完整审计。
新空间差取N800粗/细，时间差取完整旧N400细/新N800细；原kernel8c53a404仅改网格常量/标签，
预算尾部算术逐字不变，不除三、不改变稳定化、不相位拟合。原N400压力/两种速度时间失败继续有效。
47990/session37012排队保存实际计划和各终态完整证据；只完成后归档/暂存，未push或PR。

## 2026-11-09 01:50 UTC / optional FSI LU checks and mature screen

46060使用锁定3.23.7 run.sh explicit完成Debug/Release各fsi_lu_reuse、fsi_pressure_state、
fluid_lu_reuse三项，CI-selection26项通过。新路径1/2/4rank恒步10态LU10→2；window4、event、
variable各4次。全五场、新旧执行和重启对照通过，独立3696HDF最大9.7317987e-15，v4时钟精确。
全部resource return0/零事件/空scope。Release213.853s/513843200B、Debug207.916s/369856512B
是共享CPU验证时间，不作生产成本。21源文件冻结，Release6993d7f/Debug2123b716；旧2692/60eb不改。
[8950文件完整验证档](../research/data/fsi-retained-lu-validation-2026-11-09/README.md)
已01:45:23封存并全Git回读1433180B。新缓存真实终点几何拒绝未单独触发。

满载S24N200原6200seed f7efeb96筛查只增加逐步checkpoint，物理/容差/步长不变。
定义b3dc8ca587eb32a6d52437ec01a8cdc6060154e89c0024f646100ee1285a351b，计划自审b3c8f529
核对21源、11dataset种子、六模式命令与2Gswap0，01:46:24通过。47675/session9565于01:46:46
开始CPU19nice19/analysis锁，每模式1800秒：old-first/new-default/window32/window8/old-last各32态，
然后6216→6232重放16态。须176场对/144native对1584datasets及window32对四baseline成本≤.9，
不自动采用。旧v3clock仍1e-12，新v4精确；原预算失败/原c32失败继续保留。无push/PR。

## 2026-11-09 01:35 UTC / complete S24 time-budget failure and bounded follow-up

40042按原kernel完成EON三组预算；执行return0、2536.857888903s、峰值165564416B、2Gswap0、
零事件/空scope。三项time/space（压力.9133408342、流体速度.3861397581、固体速度.1905876075）
FAIL .1；全部tail/sampling通过，不能将周期/质量/Lamé通过升级为完整资格。
45992完成[57文件失败档](../research/data/elastic-s24-eonsim-time-budget-failure-2026-11-09/README.md)，
原budget SHA834f6ac81b59a85240b6fde9c7e3f19bff36c46004904eb265865f83c763140a，
普通Git单包1449600B已实际回读一致。未加Richardson因子、拟合相位或更改稳定化。

为后续时间加密准备默认关闭的-fsi_lu_pc_reuse_window，仅限线性周期压力双网格generalized-alpha。
沿已有NonlinearSystem保留预条件LU，当前Jacobian/真残量继续验证，三种有效积分系数变化和
几何拒绝重试会刷新。五个运行时/测试文件尚未验收；46060于01:31:48在CPU19/2Gswap0开始
Release/Debug fsi_lu_reuse、fsi_pressure_state、fluid_lu_reuse及全HDF检查，不改任何旧生产冻结程序。
未声称成本收益或新时间加密采用。L24全部210/11重放复核通过后已prepare具体800步计划，
实际计划自审01:34:01通过，46800/session29291于01:35:56开始延长，原2692/2Gswap0/CPU14nice19。
Release三项相关测试现均通过，Debug/全HDF待完成。第一次本地暂存因新档位于稀疏路径而仅暂存
已有文档，未提交；核验索引后使用明确--sparse添加完整metadata，原大包仍逐字回读。无push/PR。

## 2026-11-09 01:12 UTC / current execution-policy documentation

从03b3bfc核对当前study参数及NonlinearSystem生命周期，修正FLUID_PRESSURE_TIME.md中
过时的chord仅限Schur和“三步实验仍待运行”表述。当前chord支持显式Schur或MUMPS，
跨步LU缓存另行显式选择；fresh SNES与保留独立PC并不矛盾。引用已提交的真实入口、完整
历史和系数刷新证据，原cfa5d3c准备档不重写。源码未改、无新构建或数值测试。
知识及既有未发布Womersley草稿同步；局部审查不等于全项目验收。六主计算、完整EON预算、
L24重放对照与归档继续；无push/PR。

## 2026-11-09 01:00 UTC / full-load reference prefixes and completed replay numerics

ada59feff保存25文件的N200完整报告和原长度对照，18源哈希/6份Markdown/索引字节通过。
只读检查确认六主计算继续，L24 replay200在00:51:15完成2134.290635794s，replay10在
00:53:11完成115.962032540s；峰值1132482560/1127305216B，2Gswap0、零事件/空scope。
44437随后实际比较全部210场对和11native边界，44493独立raw复核仍等待。没有延长采用。

新的只读前缀核验排除最高可能写入的native及整个后续日志，保存原字节并前后校验。
ν.3fine4001..6800、ν0fine5001..8300、ν.3time1101..3600、ν0time601..1500全部最终FS/MS
行相对收敛通过；前三者分别包含400/1900/400满幅步，最后仍ramp。最大最终迭代数3，
各组最差FS/MS见[完整94文件证据](../research/data/reference-full-load-prefix-20261109t005527z/README.md)。
44808/session7776于00:57:38封存6包7656276B，包含60份实际冻结export输入；全包普通
Git字节回读完成。输入、原生状态、运行进程不改；仍不能称全程/周期/物理资格。

具体延长执行reviewer只准备并inspect ready=false，真实计划仍不存在。源码及v5只读
进度器已随前缀档保存。PowerShell首个生成helper命令发生解析错误、未写文件，改用
直接patch后正常执行；不是数值失败。未改运行时、未重跑未受影响测试，未上传或建PR。

## 2026-11-09 00:42 UTC / completed N200 field audit and finite-length comparison

本地98ee0f93已保存α1N200完整79包和L24原审计/证明计划，8份Markdown链接及所有新
索引字节通过，无push/PR。00:31:54，40040实际完成600态有界审计，五场周期max
2.4941457484e-7通过，kin0/mass1.1058862e-17/div1.0733491e-17/J正，Lamé1.23763990%
通过；audit1506.15625213s/89669632B/2Gswap0/零事件/空scope。40042随后已00:32:08
开始自己的EON空间/时间/尾项/采样预算，未宣称全部完成。

42097在复核原始SHA后00:36:47完成原长度kernel：L24均值Lamé1.55968%通过但周期失败，
平均位移差仅Lamé尺度.32204%，径向幅值和相位却有明显动态差异。保存全部harmonics/
原始input audit SHA，不能将分布式流体/固体惯性变化解释为纯端部误差。43422仍按原序
捕获原L24、完成的L12和长度对照，不重跑数值或恢复旧父。

只准备未启用的extend-length24-native6400.py；真实只读检查ready=false、没有新目录/
状态，缺少完整证明时evidence入口拒绝。总steps6400→7200是唯一case参数变化，输出1/
checkpoint200及原物理/容差保留。先实际proof44437及rawreview44493完成，再prepare具体
计划、自审execution-review，才可run。代码/检查尚不证明续算数值通过。
新增44619/session32219自00:39:07锁外等待两证明作业终态；CPU18原队列锁释放且所有scope
空后捕获原始字段/历史/输入/控制与复核，失败也保留。没有新延长采用。
[小报告包](../research/data/elastic-n200-audit-and-length-summary-2026-11-09/README.md)仅完整报告和静态后继，
不冒充仍在写的大轨迹。知识补入已有未发布压力历史草稿；不重跑未受影响的测试。

## 2026-11-09 00:26 UTC / completed L24 audit and bounded native-extension proof

从4f5f26d继续，实际读取状态确认EONN200已00:06:48完成6400并做600态审计。原L24
600态审计00:00:47完成，3086.610570493s/159633408B/2Gswap0、零事件、空自有scope，
原始输入SHA不变。两次固体速度周期差1.0924530e-5/1.0567924e-5仍超1e-5；其余四场及
运动学/守恒/J通过，Lamé均值误差1.55967748%通过2%。完整失败结论保留，未宣称资格。

读取真实6200/6400原生状态，确认各11数据集、完整历史和v3时间信息。只准备新的独立
200步重放及10步再重放；固定原binary2692、原MUMPS/chord和所有物理参数，只延长final
step至7200并增加证据输出。416份原始文件已逐字核验，具体计划/资源/范围经执行agent
自审。44437/session22841在00:15:38开始，CPU14共享nice19、2Gswap0、10G准入/8G底线。
证明要求210五场对和11个完整native边界对；旧v3时钟沿用1e-12，不称v4精确。原native
每200步才保存，未虚构原200步全部历史对。44493/session37385于00:23:14锁外排队，
待完整证明后重读并重算全部结果；无自动6400→7200采用。两份冻结controller不得编辑。
[审计及不可变计划证据](../research/data/length24-periodic-audit-and-native-proof-plan-2026-11-09/README.md)
包含原审计和计划/复核等待器源码，不包含增长的重放输出。43422完整原轨迹档另行捕获。

42447已00:09:07封存α1N200完整4116files/79parts1920613192B，随后等N400。所有79包
已完整Git回读；第一存储批次b002c068保存48包1228569372B，剩余31包692043820B及
metadata本次本地保存。受限首调用不能写D对象库，确认index未变后显式D写入成功；
原失败收据保留，不是数值失败。速度1.0164445542%FAIL1%及所有前期失败继续保留。
没有新C++修改/编译/无关测试，没有上传、PR或合并。按知识沉淀要求更新原有两篇草稿，
均未发布。局部重放验证不能替代后续周期、跨程序、空间/时间/采样预算和最终自审。

## 2026-11-08 23:54 UTC / unlaunched alpha1 fine execution preparation

在adddc7e继续已授权长程工作，没有新PDE进程。为实际S96α1筛查完成后的后续执行准备
run-alpha1-s96-fine-family.py；当前只读inspect确认40998仍运行、43221/43241仍等待，
因此未创建alpha1-s96-fine-family-plan-b0fd881或alpha1-s96-fine-family-current状态。
独立保留此前冻结准备器，不改任何活动控制器、源码、参数或阈值。

实际WSL /usr/bin/python3 check-alpha1-s96-fine-controller.py通过22项：两种真实准备器
命令生成分支与执行器匹配，20项物理/资源/顺序错误拒绝；路径前后均不存在。随后
capture-alpha1-execution-preparation.py核对六份冻结源与完成粗算例相同，逐字保存五份
源/检查文件。[静态证据](../research/data/alpha1-s96-execution-preparation-2026-11-09/README.md)
不包含新数值、性能或物理验证。将来仍须实际1440数据集raw复核eligible、具体计划review
和完整资源准入后才能run。粗Q幅值1.447028% FAIL1%继续明确保留。

按既有知识沉淀要求补充Womersley草稿的准备/采用/资格区分，未发布。未重跑无关C++或
数值测试。23:50七组生产正常推进，L24完整600态审计和alpha1N200捕获仍在进行；无上传。

## 2026-11-08 23:34 UTC / retained-factor and accepted-clock source review

在7ed5a5d（完整S96 N40084包已提交）检查NonlinearSystem的PC所有权、任意rank刷新、
失效/失败回收、当前矩阵与最终物理验收，以及fluid有效积分系数和v4时间补偿保存/恢复。
未发现本范围内新的运行时缺陷；发现L2状态文档仍无条件声称不保留因子，改为默认关闭、
独立流体显式MUMPS/FGMRES缓存的准确范围，并补DOF契约的后续系数刷新证据。

实际执行Python3.13 -Xutf8 review-solver-clock-source.py，十五份源/测试SHA与已有
lu-time-coefficient-refresh及checkpoint-clock-v4验证快照精确匹配，保存
[局部复核记录](../research/data/solver-clock-source-review-2026-11-09/README.md)。复用历史
Debug/Release和完整历史检查，本次无编译/数值重跑；不是独立外部审查或最终交付通过。
按既有知识沉淀技能更新Womersley草稿，未发布。

23:31真实进度已回读：EONN2005894/6400正式采样，L24全6400数值完成但末600态审计仍进行；
原父7713/子42141已退休，不恢复。四组参考与两组Womersley长程继续，alpha1N200捕获仍增长。
没有新增数值进程、物理/门槛变化或上传。原完整失败证据与所有未完成资格保留。

## 2026-11-08 23:25 UTC / complete S96 archive retains failed sampling

2026-11-08 23:25 UTC 完整S96档案更新：39748已23:03:10完成3323files/84parts/3591041640B，
全部84普通Gitblob整档回读通过。前两本地存储批次c17ece3（1–29）和
357ff49（30–58）已保存；最后26包及完整metadata现在最终本地提交，无push/PR。
[完整S96 N400轨迹](../research/data/womersley-s96-n400-complete-family-2026-11-09/README.md)
保留原N200目标velocitysampling/space.115648790529>.1 FAIL，另5budget项通过；N200/
N400解析和周期指标全通过也不能覆盖该失败。N400 U.471077545%、p.336758859%、
Qamp.181696731%；新N400目标仍等待独立41187 N8004800步及全部预算，不能提前替换原结论。

39748不得再等待/重启。后继42447已23:03:40真正开始alpha1 N200完整捕获，增长中不可stage；
其N400档仅40998全家族完成后才捕获。43808独立N800证据等待器仍按完整producer/预算/
cleanresources及前捕获释放条件执行。L24已23:08:12进入600态有界审计，原7713/42141
退休事实不变；43422仍按完整审计→实际L12→原kernel长度比较保存三个独立档案。
此轮没有新增生产代码、物理参数或阈值变化，未重跑未受影响测试。整体验收仍in_progress。

## 2026-11-08 /23:10 / complete coarse evidence and natural L24 boundary

UTC23:10覆盖：本地HEADab0d107f8f73ae2512669d72f3237d8db14b21c0，已保存实际nu0N200
600交接和三份完整只读前缀，共207files/4parts10251392B；34项变更11042753B、7份MD检查。
新43314/43315续算与消费者保持，旧41283族全部退休；没有push/PR。

[完整S96α1粗N400](../research/data/womersley-alpha1-s96-coarse-n400-complete-2026-11-09/README.md)
已23:02:36封存3279files/12parts219475928B，全部普通Gitblob整档回读通过。2400步六周期
U.7059441352%、p.8709598692%通过，Q幅值1.4470282864%仍FAIL1%；其它解析/周期项通过。
43573已completed，不再等待。匹配细网格和各项误差预算尚未完成；43221/43241仍排队，
没有新的S96α1细长程生产。仅粗诊断不能代替最细物理资格。

L24原数值子42141已自然6400并退出。42097于23:02:27核实所有数值后代退出和完整接受步
后，仅退休原等待父7713；旧状态cancelled_after_numerics_before_postprocessing。禁止
恢复7713/42141。完整输入哈希冻结后23:08:12实际开始bounded-l24-audit，CPU14nice19/
2Gswap0，末600态尚待完整审计；随后仍等实际L12的40040完成才做原算术长度比较。
[10文件真实退休与N800静态归档计划](../research/data/n800-capture-and-l24-retirement-2026-11-09/README.md)
1part9572B已整档Git回读；不把这份小收据当完整L24轨迹/审计。v4只读进度器用真实退休
和PID/start身份覆盖旧phase文本，不再误报原父仍暂停；原v1-v3仍保留。

新增43808/session78900，capture-s96-n800-complete-family.py，只等待现有41187完成4800
及全部N400目标预算、干净资源、先前CPU15捕获42447结束和完整N400档案入库。未来档案
womersley-s96-n800-n400-target-budget-2026-11-09；没有重跑/新数值采用/当前完整捕获。
status s96-n800-complete-capture-current；work/s96-n800-complete-capture-ab0d107。
43422仍等L24审计后捕获，再等L12及长度比较；39748 S96全档在写，42447α1档等待。

23:10完整步：EONN2005574/6400；nu.3fine6155/12800、nu0fine7434/12800、nu.3time2999/6400、
nu0time729/6400；S48α1N400611/2400、S96α2N8001378/4800。全项目保持in_progress。
只执行了既有计算、所需证据校验和新只读归档排队；未改物理/门槛或重跑无关测试。

## 2026-11-08 /22:59 / actual native600 handoff and complete-prefix evidence

UTC22:59覆盖：本地HEAD4f9bf6f3927cb47620f99383dc2994142cf85042，完整nu0N200后端证明
561files/11parts/283180048B及alpha1静态筛查18files/1part2103340B已提交；没有push/PR。

43314于22:51:40实际采用原生600→6400接续。原41283/41284及41954/41955/41957/41958
全部退出或Z，禁止恢复。旧数值自然STOP600、return0、2Gswap0/零事件/空scope；旧控制器
随后缺失6400文件及旧消费者失败如实保留。完整1..600的1200条FS/MS最终行通过，max
5.6e-11/9.3e-11；新43668/43669在CPU10/12、121678ILUT、2Gswap0运行，22:59已655/6400。
新43315预算消费者锁外等待；原39157 N400未动，未来仅认可明确的已存在coarse目录守卫。
[实际600交接](../research/data/reference-nu0-n200-native600-handoff-2026-11-09/README.md)
183files/3parts7868104B已捕获并完整Git回读，不含增长的新续算输出。

43106 S96α1粗N400已22:51:35完成2400+analysis+tail：U.7059441352%、p.8709598692%
通过1%，Q幅值1.4470282864%仍FAIL1%；phase.0596533544度、net7.97e-18及周期项通过。
43573/session51792正CPU13共享nice19捕获完整粗轨迹，未完成不能暂存。新细筛查43221
仍等原40998完整家族释放资源，43241随后独立raw复核；没有S96α1细长程自动采用。

[只读参考前缀](../research/data/reference-live-prefix-20261108t224736z/README.md)
24files/1part2383288B已完整Git回读。nu.3fine4001..5900、nu0fine5001..7100、nu.3time
1101..2700全部最终方程行收敛通过，原始字节前后不变；不是完整轨迹/周期/物理资格。
同档保存43422 L24/L12与长度比较捕获、43573粗算例捕获的静态控制器，不把排队当完成。

22:59实际完整步：L24=6378/6400，子42141继续计算、父7713仅有意T；42097等自然6400
后才退休旧父并做低内存全场审计，禁止手动恢复或signal数值子。43422/session99528
等其audit后捕获L24，再等40040完成捕获L12N200（排除增长budget.log），最后保存长度比较。
EONN2005436/6400，nu.3fine6088/12800，nu0fine7351/12800，nu.3time2933/6400；
S48α1N400517/2400，S96α2N8001287/4800。39748的S96完整档仍捕获，42447α1档仍等待。
所有已有失败和原门槛保留；本轮仅保存证据及执行已复核方案，没有重跑无关构建或测试。

## 2026-11-08 /22:38 / complete N200 backend proof and static alpha1 screen

UTC22:38归档更新：本地HEAD20d9f255cb54029434ac3ab9e6c5576449af77f9，已保存完整S24
4995files/143parts/1420132176B及6份Markdown检查；162项变更、1424128693B，未上传。
[nu0N200完整后端证明](../research/data/reference-nu0-n200-ilut-backend-proof-2026-11-09/README.md)
561files/11parts/283180048B已整档普通Git回读。100态对照/10态重放及独立raw复核通过，
只是早期ramp局部资格；22:24启动的43314仍等原生600，不把证明中的adoptedfalse改写。

43375/session27225，capture-alpha1-plan-and-nu0-time600.py，自22:36:06运行；status
alpha1-plan-nu0-time600-capture-current，work/alpha1-plan-nu0-time600-capture-20d9f25。
第一档[alpha1静态筛查准备](../research/data/alpha1-s96-execution-screen-preparation-2026-11-09/README.md)
已22:36:13完成18files/1part2103340B；不含新细数值结果。第二档等待实际43314adoption，
随后捕获封存旧600轨迹、旧producer/consumer失败及新不可变输入/独立方案自审，排除增长输出。
两新档文档/字节验证后本地提交；不得重启已完成42564或重复启动43375。未提前push/PR。

## 2026-11-08 /22:30 / sealed S24 sample and reviewed native600 continuation

UTC22:30覆盖：本地HEAD a341bc6；没有push/PR。S24细N400 EONSim全部12800步及末1200态
有界审计已完成，39984完整捕获4995files/143parts/1420132176B，原始OOM/失败消费者均保留。
五场周期最大2.4729777e-7、kin0、mass9.541e-18、div9.388e-18、J正、Lamé1.237613%通过；
参考轨迹与各自误差预算仍不齐。全量普通Gitblob回读与本地提交随后执行，非项目资格。
[完整采样档案](../research/data/elastic-s24-fine-eonsim-complete-sample-2026-11-09/README.md)。

42340的nu0N200完整110态独立raw复核已22:13:37通过，42564原始证明完整归档22:22:13结束。
43290对实际600接续方案的单独自审通过，核验真实双rank STOP重放、全部后端证明、原预算kernel。
43314/session48356于22:24:47真实启动，status reference-nu0-n200-native600-family-current，
work/reference-nu0-n200-native600-family-fcc2956；当前waiting_for_native600/adoptedfalse。
只向原time结果目录写原生STOP_SIM600；原41283/41957/41958继续自然推进（22:30=506）。
新43315消费者ready_for_idle_replacement，不持分析锁；不能把等待写成后端已采用。
自然600后原旧6400检查的预期FileNotFoundError和旧消费者失败必须保留；新控制器核实所有
旧身份已退出、600完整链和干净资源后才可创建新的121678ILUT600→6400，原fine39157不变。
实际definitionSHA f9ed1bd4b30a17ec5a1d9f10c55774797d803313fd48eaa9a5a9b1593cc0dd15。

43106的S96α1粗N400于22:22:19真正开始2400步，CPU14共享nice19/2Gswap0。
新增43221/session85867只锁外等待40998完整家族和43106完成，之后独立S96α1细N400启动32态
four8/native32/four32，5/2/2实际LU，三对全部1440HDF数据集/节点/P1mass/v4exact，6Gswap0。
必须候选比另外两模式均节时≥10%；无长程自动采用。43241/session72328只等待其完整原始复核。
两个状态alpha1-s96-fine-execution-screen-current和alpha1-s96-fine-execution-review-current；
新S96α1细长程生产尚未创建。α1 S48 N200 U1.0164446%FAIL1%保留。

22:30实际完整步：S48α1N400286/2400，S96α2N8001105/4800，EONN2005052/6400，
nu.3fine5914/12800，nu0fine7126/12800，nu.3time2763/6400，nu0time506/6400。
L24子42141=6233/6400，父7713仍有意T；42097等自然6400，禁止手动恢复父或signal数值子。
39748的S96完整档仍在捕获，42447的α1完整档仍等待；未完成档案不能暂存。全部门槛保持。

## 2026-11-08 /22:12 / complete alpha1 N200 diagnostic and next-grid preparation

UTC22:12更新：本地HEAD fcc2956；S48完整153包已全部提交，无push/PR。
alpha140998已完成N2001200及六周期分析，U1.0164445542%仍FAIL1%；压力.216089%、
Q幅值.640241%、phase.0404516度、net1.59311e-17及周期项通过。21:52:50真正开始
同S48α1N4002400步，4rCPU0–7；不得重跑已完成N200或称整体已通过。

新43106/session12134，run-alpha1-s96-coarse-n400.py，status alpha1-s96-coarse-n400-current，
work/alpha1-s96-coarse-n400-fcc2956，D/womersley-a1-s96-r8-a8-l0-n400-native32-fcc2956。
22:09:49只waiting_for_existing_proof_capture；等待42564终态后2Gswap0/CPU14 shared nice19，
14GiB可用入场/8GiB运行底线，fresh2400/c6/400phases/60eb/native1/window32/chord。
只粗网格解析和tail，不称新性能对照或fine资格；S48失败保留。静态源码SHA
be9b652c21cbd88ceb09076227a5843569ed9f1fa3a1ac277c39c428053b4d65，不编辑冻结源。
43147已22:11:43完成22file/1part32272B准备档并实际Git回读；含已完成N200分析和
30秒只读CPU采样，不包含增长轨迹，也不从guest利用率推断宿主核隔离或因果加速。

42290独立nu0N200后端screen已22:05:46 completed/eligible/adoptedfalse。old1001501.603722845s，
ILUT100902.451790098s，ratio.6009919770；replay10为98.278060453s。100态node/P1/history
1.76183e-19/5.22227e-17/2.75116e-17、norms0/timeexact，重放全部0/算法字节精确。
42340仍在独立原始数据复核；42564等其结束完整归档，主41283仍原f3运行。
新continue-nu0-n200-native600.py和review-nu0-n200-native600.py仅写出并语法检查，
尚未prepare/run、没有新状态/目录/STOP_SIM/后端采用；必须先复核与42564完整捕获，再
准备并独立审查具体600方案。保留旧6400检查预期失败和原预算kernel，不信任预先声明。

22:00实际完整步：N800860/4800，L246082/6400，EONN2004637/6400，nu.3fine5729/12800，
nu0fine6884/12800，nu.3time2581/6400，nu0time363/6400。L24父7713仍有意T，
42097等数值子42141自然6400，不得恢复父或signal数值子/sharedscope。
39748的S96完整档、39984的S24完整档仍增长；只有completed档案可暂存。全部门槛不变。


## 2026-11-08 /21:34 / sealed S48 family and independent N200 backend screen

UTC21:34执行快照；S48完整N400档案随后完成全量Git回读（精确时刻见index-staging.json）。
本地HEAD fc4c272，前两批1–100包已独立提交，最后53包及完整metadata准备最终本地提交；无push/PR。
S48 α2 N400完整2400步、六周期及N200-target预算已封存8162files/153parts/3774516920B。
N400 U1.0459910557%与N200 U1.0468222496%仍FAIL1%；其余解析/周期项和六个budgetterm通过。
完整档womersley-s48-n400-complete-family-2026-11-09含全部保留current/history；旧N200/middle完整档SHA链接。
不把N200-target预算误写为N400独立空间资格；S96 N400目标仍需新N800时间对照。

新增nu0细N200专属后端screen42290/session98395已21:20:49实际old100开始，
status reference-nu0-n200-ilut-screen-current，work/reference-nu0-n200-ilut-screen-af41681；
真实100→200原f3必须复现实际原200所有rank算法字节，随后121678ILUT100及190→200重放10。
2rank CPU14/16 shared nice19、2Gswap0、各3600秒，完整五场/全native历史与norms/时间/收敛/成本≤.9。
早期ramp证明，不称满载；不暂停41283，不自动交接。冻结controllerSHA
d804b3089021a7736ab9cf1cc9785c8ee478d3bc6165a8829c9607e49a623f41。
独立raw reviewer42340/session45123在reference-nu0-n200-ilut-review-current等待，CPU15nice19/2Gswap0。
首次静态case比较漏checkpoint_interval差异在任何数值screen前拒绝，保留preflight-history；
只明确移除dt/steps/checkpoint_interval后比较全部其它物理参数，未改变实际N200输入。

alpha1完整capture42447/session5601已21:33:03排队，status alpha1-complete-family-capture-current，
work/alpha1-complete-family-capture-af41681，先等39748归档和42340review终态退出再入场。
旧759-file handoff与1563-file middle的26个普通Git包已全量回读；早期middle直接实体包没有
index-staging.json，首次静态假设错误已保留，尚未运行任何capture。新capture仅在N2001200+
分析资源全空后捕获sealed N200，在40998全completed后捕获N400+全部预算，不混入增长日志。

21:34实际完整步：alpha140998=1111/1200，S96N80041187=696/4800，EONN20040040=4310/6400；
nu.3fine38880=5586/12800，nu0fine39157=6698/12800，nu.3N20039392=2441/6400，
nu0N20041283=252/6400。L24子42141=5963/6400，父7713仍有意T，42097等自然6400；
不要手动恢复父或signal数值子/sharedscope。39984完整S24与39748的S96档仍增长，不能暂存。
全部长程物理与误差预算尚未齐；原失败均保留，48小时到点不是完成。


## 2026-11-08 /21:01 / sealed nu0 coarse and L24 postprocessing boundary

UTC21:01最高优先：本地HEAD e771355；新两档1456files5parts110252568B已实际Git回读，待本地提交；无push/PR。
独立nu0粗41283已完成12800、完整收敛及1200态audit（20:44:35）。FS/MS最大3.7e-11/9.6e-11；
五场周期最大6.611520782e-6、kin0/mass5.85469e-18/div5.78545e-18/J正通过。20:44:37接着
同原规划细N200，41957/41958双rankCPU10/12/f3，20:56=72/6400；原39157细N400仍继续。

41996/session74410已20:54:47完成同源6f、同400phase粗网格跨程序比较与完整归档：
comparison_eligible=true，但中p幅值差3.112768487% FAIL2%；径向/面积3.026038%、flow
1.838383/1.854909%及各相位门槛通过；Lamé均值EON3.195039047%/ref3.195043167%均FAIL2。
全场P1相对RMS U/p/ALE/solidV/solidD=.00709477/.01318861/.11738335/.01103094/.01102916，
只记录差异，不另造全场门槛或因果归因。所有raw SHA前后不变，原nu.3失败保留。
档elastic-s24-coarse-n400-nu0-reference-pair-2026-11-09含1408files/4parts/109627948B；
已finalized普通Gitblob。参考完整raw/全部native历史/commands/source在档，已存EON全档逐项SHA链接。

L24新后处理接续42097/session14695从20:55:44运行，status elastic-length24-bounded-postprocess-current，
work/length24-bounded-postprocess-handoff-e771355。20:58:38原warmup5800结束，原sample子42141
（start10928062/CPU19/2692原binary）继续5801→6400；20:58:39仅等待父7713/start2801171被
有意SIGSTOP。7713状态T是计划行为，不得恢复或重启；数值子未signal，尚未6400/未采用分析。
新controller监控所有真实后代自然gone/zombie，完整原accepted1..6400/finalcheckpoint后才
TERM+CONT退休精确父；旧shared init.scope绝不signal。原父将记录cancelled_after_numerics_before_postprocessing，
原状态/日志/轨迹保留；不会运行旧dense audit或已退休L12路径。若新控制异常且未退休，它先恢复
同身份父并记失败；若新controller突然死亡，应先核实definition/pause/自有分析资源，不能盲目恢复。

准备definitionSHA aa767dcbd75b5f059d44cad3ac1f7fee6d08faddb39997f5cf6f352005358d40；
独立控制fixture及20:55:18执行者单独源审查通过，reviewerSHA955dcd5532b812ca790d3d8a94a1083e454a04933c24f222b003ae75f5f33fda。
未来D/elastic-s24-l1-n200-L24-bounded-postprocess-e771355只建立原场PVD索引并2Gswap0/CPU14
做bounded6f审计，之后锁外等真正L12producer40040completed；原长度比较kernel逐字抽取，
门槛不变。48files1part624620B静态准备档已Git回读，不包含增长轨迹、pause或未来分析，不能算完成证据。

20:56其他真实步：alpha140998=850/1200；S96N80041187=452/4800；nu.3fine38880=5375/12800；
nu0fine39157=6421/12800；EONN20040040=3826/6400；refN20039392=2235/6400。39984/39748仍捕获大档，
不可stage增长part。全部物理与误差预算未齐，继续工作；不要恢复任何已退休旧族。


## 2026-11-08 /20:38 / exact serialized reference review

UTC20:38最高优先：HEADd2c24ee；新增两档145files2parts3290384B已完整Git回读，待本地提交，无push/PR。
41583的封存参考1200态读取已完成335.850544s/81088512B，但内存int周期键与JSON string键
直接比较导致exit1；原failure/资源/41673失败capture保留。41802独立序列化报告复核20:33:45
完成，物理/质量/1200行及所有旧收敛值精确一致，新增仅完整区间元数据和分析SHA；全raw
输入SHA不变，不重算字段/数值。原ALE周期2.211333152e-5仍FAIL。完整证明122files376324B。
新有效静态预案work/reference-postprocessing-contingencies-v2-d2c24ee，definitionSHA
c9f3046f308a344e68c9fa36f400372446ec1d092975ed43831bda43783cbd8d；只prepare，未执行恢复。
旧三个参考38880/39157/39392正常运行，不signal/不改冻结源；仅实际audit OOM且完整数值/
native链后才可能另立恢复，nu0未来预期directory guard失败不是该触发条件。
41833 capture-v2已20:34:53 completed；41583/41673均已failed，不恢复。原旧预案保留。

20:29:36只读prefix原始快照23files2914060B：nu.3fine4001..5100、nu0fine5001..6000、
nu.3time1101..1900、nu0coarse1..9400全部最终FS/MS行<1e-10，最多3iteration；各全程仍未完。
首次归档名含大写T/Z在任何part前拒绝，独立小写retry保留失败后完成，无数值重算。

20:36真实步：alpha140998=695/1200；S96N80041187=301/4800；nu0coarse41283=11804/12800，
其time尚queued；nu.3refN4005247/12800、nu0fine6255/12800、EONN2003543/6400、
refN2002109/6400、L245678/6400。原coarse/time所有权和预算41284不变；39984/39748大档仍增长。
核心clock/LU/referencechain/物理指标已针对性只读自审，无新增核心修改或旧数值测试重跑。
全项目资格未通过；所有剩余完整周期、误差预算、最终自审和全档仍需完成。


## 2026-11-08 /20:10 / N400 refinement and explicit pending-reference ownership

UTC20:10最高优先：HEADa3e1c87；本地三档873files23parts378561156B完整Git回读，待本地提交，无push/PR。
alpha1五模式/旧轨迹/失败/实际交接档759files21parts377840384B已完成；41020不再等待。
新alpha1仍40998，20:08:56已464/1200；旧身份全部gone，不恢复。

原S96家族29270已19:48:31 completed/passed=false，唯一失败是N200速度sampling/space
.115648790529>.1；U/P时间比.073911407822/.079631443096和其余项PASS。新41187/session32029
已采用独立N400-target家族，status s96-n400-qualified-family-current，work/s96-n400-qualified-family-a3e1c87；
D/womersley-a2-s96-r8-a8-l1-n800-native-serial32-a3e1c87从零4800/六周期，20:08为89步。
CPU21/原60eb/window32/native1/6GiBswap0，14GiB入场8GiB底线；源码/物理/阈值不变。
新N400同相位空间差U.001823100329/P.005360697553；N400速度sampling8.7096e-5占新space
约4.78%，仅此项PASS，N800时间/完整预算待完成。原body只分辨率200→400、400→800，
逆变换字节/AST完全同原，不将原N200失败改判。45files33876B证明已完整保存。

独立nu0新41283/session39260已20:03:35真正接管尚未启动coarse/time，CPU10/12、原f3
双rank/原逐字export、2GiBswap0/10GiB入场8GiB底线，coarse-solve20:03:37开始。
family work/reference-nu0-early-companion-family-a3e1c87；handoff work/nu0-early-companion-handoff-a3e1c87；
status reference-nu0-early-companion-family-current。明确接管原规划D/reference-s24-l0-n400-meshnu0-native5000-fce909d
与D/reference-s24-l1-n200-meshnu0-native5000-fce909d两个尚未产生reference输出的目录，
有early-execution-claim及ownership收据。20:08 coarse1983/12800，time尚未启动。
原39157 fine-solve继续，未signal/未改冻结源。原fine数值+convergence+audit结束后，原
assert not reference.exists()将阻止重复coarse；真实抽取循环fixture在任何export/数值调用
前拒绝，独立review已通过。未来原预期guard失败须保留；若不是该准确原因或fine资源/
全报告不完整，新家族必须失败，不能伪造原completed。该未来边界目前尚未发生。
新预算41284在reference-nu0-early-companion-budgets-current等待新完整家族；旧40214已
cancelled_before_analysis，唯一signal针对已核实无子/无锁idle40214，不恢复。新consumer
仅6个路径/decision变换，逆变换字节/AST相同，原budget kernel逐字保留。69files686896B
不可变接管/输入证明完整Git回读；无新nu0物理资格。

20:08其余真实步：nu.3refN4005064/12800、nu0fine6018/12800、EONN2003134/6400、
refN2001931/6400、L245514/6400。39984 S24全轨迹与39748 S48/S96全档仍增长，不stage。
首次新计划归档因repo helper不在声明证据根，在任何part前拒绝；保留失败与空目录。
新retry2复制逐字helper到work后完成，41384已20:07:32 completed，不重跑任何数值。


## 2026-11-08 /19:45 / alpha1 actual reviewed recovery

UTC19:45最高优先：HEADa3e1c87保存115文件完整细审计/控制fixture，无push/PR。
31707真实200seed五模式19:27:56完成，38449独立回读19:29:19通过：5pairs1280HDF，
old/new最大history2.6123471e-12、P1mass9.6319535e-11；newcache最大history2.9880612e-16、
mass2.2887646e-13，legacyclock0/newv4exact。new32对old8/default8/long8成本比分别
.087324840987/.249570660821/.667585831991。原解析/物理门槛不变。

真正alpha1现为40998/session88668，19:39:22已采用并实际接受217/1200（19:41:50）。
status alpha1-native200-lu32-recovery-current，work/alpha1-native200-lu32-recovery-a3e1c87；
D/womersley-a1-s48-l2-n200-lu32-native200-retry2-a3e1c87，后N400同lu32-paired-retry2后缀。
同60eb/window32/chord、4rCPU0–7/14GiBswap0/22GiB入场8GiB底线；200→1200再fresh2400，
最后采样cycles4–6全新策略。预算算术aae1723...逐字保留。原middle是200步/100存储相位，
space按原100共同相位算法，细N200/N400仍200/400全相位，不补造原始数据。

旧20806/21493/20825/34663/34666–9全gone，不恢复。首次prepare错误要求middle200phases，
写目录前拒绝；修正真实输入后，首次run又因sha(__file__)字符串类型错误在signal前拒绝。
独立retry2改成Path后通过审查，确实退休driver/MPI/idlewaiter；但旧owner写failed后自然
退出超过40秒，retry2在19:34:44正确failed/adoptedfalse。所有旧数值子进程当时已退出。
拟定清理helper读取owner身份时它已自然gone，未发额外signal，也未创建cleanup目录。
保留两份失败计划；新恢复controller不含任何os.kill，只在全部原身份/会话为空和完整
seed再次核对后运行。19:39:05独立review通过，definitionSHA
4c78fed3d5a2d594e3dbb33b02eda435439bbc64bc327107108a3495d49aa6c9；命令只迁移控制/分析路径。

41020/session4111从19:40:36捕获完整五模式证明、旧alpha1部分轨迹、两份失败、实际新交接
不可变证据，status alpha1-checkpoint-handoff-capture-current，档womersley-alpha1-native200-lu32-handoff-2026-11-09。
排除新增长日志/receipt/attempt/currentpointer；尚未completed，不stage。
S96N400已2400，19:44仍tail-n400/budget，六解析/周期门槛已PASS：U.4710775447%、
p.3367588593%、Qamp.1816967312%、phase.0563039771deg、net1.24204e-17，不能代替最终预算。
19:41其余步：nu.3refN4004864、nu0refN4005766、EONN2002706、refN2001734、L245351。
S24细完整审计已过周期/守恒/Lamé，参考及各自预算继续；两个大档39984/39748仍增长。


## 2026-11-08 /19:27 / full fine audit and guarded retirement fixtures

UTC19:27覆盖：HEADdba2dd8；39865已19:11:27完成S24细N400全部1200态补审计，
12800数值未重跑，原始输入SHA不变。五场末两周期max2.4729777216e-7<1e-5；kin0、
stage mass9.5409791e-18、divtheorem9.3876277e-18、两域J正。Lamé均值相对误差
1.2376125755%满足2%；原粗网格失败保留。3313.361s/90243072B/2GiBswap0/零事件/
空scope。参考配对和独立误差预算尚待完成，不能写成总体合格。
[完整审计报告档](../research/data/elastic-s24-fine-bounded-audit-report-2026-11-09/README.md)34files360280B已实际Git回读；
39984自19:11:40捕获全数值样本与旧OOM/失败，不暂存增长文件。

31707真实alpha1检查点筛查已完成old8/default8/new32short8/new8long32，耗时分别
1261.797791/441.503384/110.186291/434.130110s；new32long32及38449完整独立回读仍待完成。
old20806/21493与N400waiter20825保持，未采用。仅准备新的native200 LU32 N200/N400
完整家族及reviewer，未prepare/run、未创建其目标目录；原预算算术逐字保留。
40637交接模拟5场景均PASS，8.655826s/85270528B/2GiBswap0/零事件/空scope，
[完整81文件控制验证](../research/data/alpha1-retirement-control-validation-2026-11-09/README.md)20304B已Git回读。
未对正式进程发送信号，后续prepare必须绑定此验证函数和完整数值证明。

19:18真实步：S96N4002260/2400；alpha1旧369/1200；EONN2002385/6400；refN2001587/6400；
nu.3refN4004712/12800、nu0refN4005578/12800、L245225/6400。S48N400已完整但U仍FAIL。
39748完整S48归档增长中；115文件两新小档合计380584B是报告/控制验证，不是这些长程全档。
首次默认工具权限不能写D对象库、随后经批准的同命令写入及完整回读成功；无数据移动、
删除、push/PR或门槛变更。


## 2026-11-08 /18:53 / complete S48 budget and preserve archive storage headroom

S48N400 completed2400 and all budgets18:44:12. All six time/tail/sampling
terms are below.1 of the last spatial field difference, but the velocity
analytic gates still fail; overall passed=false.31707 began the actual200-seed
alpha1 screen18:44:21 without stopping old alpha1.39748 captures the sealed S48
family; growing archives are not staged. Fine S24 bounded audit remains running.

With C free about9.1GB and complete N400 evidence still pending, validated
append-only D Git objects in an isolated fixture. A complete249028B archive is
an ordinary blob; default Windows/WSL reads and fsck pass. An independent
--no-local clone contains complete objects with no alternates. Initial broad
environment preflight rejected app Git config/pager variables before any write;
preserve that failure and restrict the guard to actual storage overrides.

After separate raw-object/clone review, added only a new D store, relative
alternate and junction to the checkout. No existing objects moved/deleted,
Git config/ref changed or upload occurred. A unique real-index ordinary blob
stored only in D reads exactly on both platforms. New bounded-batch stager
prechecks all source hashes and whole-batch space, checks each Git payload,
and requires explicit whole-archive finalization. Actual55-file/265116B proof
passed staging and finalization. Existing articles extended; no C++/numerics
rerun for storage. Future final remote delivery remains gated on full acceptance.

## 2026-11-08 /18:35 / replace idle nu0 consumer and preserve N400 velocity failure

New40214 replaced only idle39162 after independent40183 review of unchanged
plans/kernel, exact old identity/no-child/no-lock and four actual function routing
fixtures. Fine reference uses explicit restart-chain; original companions use
family coarse/time solve logs. No numerical producer was signalled. Old waiter
has explicit cancellation and receipt, not a fake numerical failure.86 files/
73816 bytes fully captured and Git-readback verified. Root9d9 code tests reused;
no new C++ or unrelated tests run.

S48alpha2N400 completed analytic diagnostics: U1.0459910557% remains above1%;
all other five preliminary gates pass. N200/N400 relative field RMS velocity
.0001445713146 and pressure.0001901804033; denominator/tail/sampling remain
under evaluation. Preserve failure; no acceptance inferred from2400 steps.
Fine S24 bounded audit39865 remains active on immutable existing output.

## 2026-11-08 /18:22 / bounded audit validated and native1600 adopted

The new reader passed Windows9/WSL9, reproduced old full-cycle retention, and
recomputed all1200 coarse states exactly except analyzerSHA (566.535979s,
36995072-byte peak, clean2GiB scope). Fine39865 began analysis18:14:31 on unchanged
sealed12800 output. Preserve original OOM and failed39197/39393, no numerical rerun.

Actual1600 screen39567 and independent39575 passed24 pairs/264 datasets/fiveP1
fields, v3 clocks exact, cost ratios.3703195674/.3454892791. Revised unexecuted
handoff sources bind the validated analyzer and recovered N400 path. Three actual
function routing fixtures prove explicit restart-chain use for resumed references;
all budget arithmetic and worker bodies remain unchanged.40013 reviewed242 raw
hashes and actual identities in24.110960s/10334208B/zeroevents/empty scope.

40040 adopted18:17:35 after planned SIGINT only33829 and all33828 family exited.
Keep original accepted1601..1647 as excluded tail; restart from complete1600.
New40042 consumes exact new routes.40067 sealed75 immutable files, excludes
all growing new logs. Nu05000 actual handoff307 files is also fully sealed.
39984 completed bounded-memory56 files and1600-proof331 files, now waits repaired
fine audit to capture the full S24 sample. S48N400 reached2400 and began analysis;
alpha1 screen still waits its complete budget. No physical pass or push/PR implied.

## 2026-11-08 /18:06 / preserve complete numerics and repair audit memory

S24 N400 EON completed12800 and all1200 stored sample states. Audit37886 was OOM
killed17:55:43:2GiB peak, memory.events max36/oom1/oom_kill1, return-9,
876.028295 seconds, empty scope. Its sample solve has return0/zero events. Preserve
the failure and failed downstream39197/39393. No numerical rerun or status rewrite.

The analyzer retained one complete phase cycle of nodal dictionaries. Replace
those retained frames with immutable paths and reread exactly the prior phase;
all integral arithmetic/order remains unchanged. A live-object regression plus
nonzero per-cycle pressure drift checks bounded frame count and exact phase/RMS
norms. Windows9 and frozen WSL9 pass; running the regression against committed
old source reproduces retention failure.39845 now compares the complete1200-state
coarse audit to its original report, excluding only analyzer SHA.39865 awaits that
validation before a new same2GiB full fine audit, with portable indices into old
immutable VTUs and before/after hashes. Both root changes remain uncommitted.

Prepared-but-unexecuted EON1600 handoff helpers are stale after39393/37886 failed;
do not execute them. Future consumers need the recovered fine audit route and
explicit reference restart-chain handling when matching a changed analyzer.
Actual1600 same-state screen39567 began18:04:11; original EON stays running.
Nu0 family39157 adopted native5000 at17:59:41 without original solver signals;
old20277/38384 failures preserved.39231 actual handoff capture finished18:03:03.
39748 queues only completed S48/S96 N400 families, not growing outputs. No push/PR.

## 2026-11-08 /17:51 / actual reference1100 and bounded EON execution proof

Reference39392 adopted the exact1100 native seed at17:49:23 after the original
29899/29901 family exited naturally. All2200 final equation rows through1100
passed, FS/MS maxima5.7e-11/9.4e-11. Original full6400 audit and old39174 budget
failed as expected and remain preserved. New39393 consumes the reviewed route.
Capture39401 finished135 files/10488872 bytes; a separate39661 seven-file3204-byte
supplement preserves convergence-svfsi command/log, which the frozen capture's
svfsi/export/audit prefix selection did not include. No active capture was edited.

EON1400 same-state screen39418 completed all24 pairs/264 HDF datasets/five P1
fields and4+4 restart. Old-first/candidate/old-last8-step times170.780458337,
50.510200381,161.065220538 seconds; ratios.2957610073/.3136009140. History/node/
normalized-mass maxima5.0923282e-16/7.4593109e-17/3.3598051e-14; legacy v3 clocks
identical. Reviewer39468 initially demanded MatLUFactorNum for both backends;
SuperLU_DIST actually reports MatLUFactor16, while MUMPS reports numerical8.
Retain its2.029150-second failure/zero events/empty scope. Fresh39531 completed
independent readback17:40:52 in78.776539 seconds, peak89337856 bytes, clean2GiB
scope. Capture39559 completed356 files/six64292392-byte parts17:48:56.

New39567/39575 wait for actual1600 and repeat the bounded same-state proof/readback
without signalling33828/33829. Future native1600 continuation/reviewer/budget
sources were prepared but not executed. Kernel file SHA8c53a40420c0dcd41615863745c6f89a16e0dbd4cf631150387d6bb75bfc01f5
is distinct from the preserved extracted arithmetic-tail SHAead574f634cb6713581244325d3f71690796bb17b5b74b56e5422187c1dfa078;
check both exact identities rather than equating these different byte ranges.
S24 EON N400 reached12800 and started the full1200-state audit17:41:06; no
complete/physical qualification inferred. No push/PR and no new C++ build/tests.

## 2026-11-08 /17:29 / reviewed N200 backend and natural1100 request

Reference100-step baseline/candidate and10-step replay took3004.393521160,
1590.483061353 and167.676861234 seconds. Independent38676 completed17:09:38
after236.938041 seconds of raw readback; nodal/P1/history maxima1.84314e-17,
4.48271e-15/2.95572e-15, saved norms zero and physical time exact. Replay algorithm
bytes match except diagnostic elapsed/nonstate padding. The original successful
baseline is imported byte-for-byte, with its earlier diagnostic failure retained.
Capture39299 finished556 files/ten279699816-byte parts17:23:44; actual Git checks
precede local commit. This remains bounded execution evidence, not physical qualification.

Independent native1100 handoff39364 passed17:19:58. Initial39331 failed only on
a Python bytecode cache comparison,1.530293 seconds, zero memory events/empty scope;
all real source checks remain strict. New39392 requested STOP_SIM1100 at17:21:06.
Original29899/29901 still run; no candidate adoption yet. New39393 waits for the
actual handoff with unchanged budget worker/arithmetic and the actual4000 N400
route. Original39174 will fail naturally at the original N200 audit boundary.
Capture39401 waits for actual adoption and excludes active EON files in the shared
directory. No original numerical process was signalled.

New independent EON screen39418 started17:26:15 from sealed1400 using the same2692
binary. Two default8-step arms bracket MUMPS/chord8 and4+4 replay, CPU16 shared/
nice19/2GiBswap0. All24 pair-states/full history/P1/v3 clock and at least20 percent
cost reduction against both baselines are required; no automatic handoff. All
formal production and original physical gates continue. No upload or PR.

## 2026-11-08 /17:08 / actual native4000 adoption and nu0 boundary request

The original nu.3 N400 solver ended naturally at4000. Original full-study audit,
old handoff37988, consumer37989 and capture38175 failures remain unchanged.
New38880 adopted at17:00:01 after all original processes exited and the complete
1..4000 prefix passed8000 final equation rows, maxFS5e-11/MS9.8e-11. Its exact
native seed, source, reviewed backend transition and manifests bind the new
4001..12800 chain;39174 waits for full producers with unchanged budget arithmetic.
Capture38891 completed218 files/five32434744-byte parts at17:02:09; native Git
readback passed17:06:38. Growing continuation output is excluded. No upload/PR.

Nu0 successor39157 requested STOP_SIM5000 at16:59:28 only after independent
review39073 passed126.408616s/169283584B/2GiBswap0, zero events and empty scope.
The original20277 family still runs and no nu0 adoption occurred. New39162 waits
without the analysis lock;39231 captures only after actual adoption. The later
coarse/time cases retain original two-rank binary and input export. No original
numerical process was signalled. Capture39197 waits for all S24 EON sample/audit
requirements. N200 screen38663 completed17:05:41 with eligible=true/adopted=false;
independent38676 review remains active. All physical failures and gates remain.

## 2026-11-08 /16:45 / reviewed midnight successor queued

38854 retry3 independently passed16:41:21,69.066164s/177700864B/2GiBswap0,
zero events and empty scope. Existing failed cache comparison retained.
38880/session80017 now waits outside locks for predecessor37988's sealed4000
boundary and parser rejection. No adoption, new stop request or signal.
38891/session19819 will capture actual adoption only, including failed old
controllers and both reviews. Future consumer is elastic-s24-midnight2-budgets;
it is not running yet. Capture38827 completed344 files/four134713104-byte parts
at16:44:20; real Git byte verification precedes local commit. No upload or PR.

## 2026-11-08 /16:40 / diagnostic midnight wrap, preserved failures

N200 screen37691 completed its original100 numerical steps600→700 with exit0,
3004.393521s, zero memory events and an empty scope. Its frozen auditor rejected
negative diagnostic elapsed after local midnight;37700 correctly failed too.
Pinned UTIL.f CPUT() omits the date and OUTPUT.f writes CPUT()-timeP(1) into
both printed diagnostics and native records. Physical time and algorithm state
did not regress: the resumed700 matches original700 algorithm bytes exactly
except the diagnostic elapsed field.

Four-file parser/test change allows finite signed elapsed only. Physical time,
equation norms, residuals, complete histories and provenance remain strict.
Windows6 convergence+16 restart tests and26 CI-selection tests passed; WSL28
reference+8 pressure tests passed, along with actual100-step convergence and
serial/two-rank native records. Final38611 validation4.083539s/33239040B,
2GiBswap0, zero events, empty scope. Initial validation mistakenly required
every MPI rank timer to wrap; preserved failure, since only master has that
timer origin. Initial Windows ownership refusal retained with successful
per-process safe-directory retry, no Git configuration change.

Fresh38663/session63590 imports every closed old100 byte and original resource
receipt, then runs only candidate100/replay10 from16:32:36. Fresh38676/session75952
independently awaits it. Original failed screen/reviewer never restored.
Capture38827/session80874 archives closed failed baseline and validation only.

Existing37988 still waits original4000 natural boundary, with its frozen parser.
Fresh midnight2 preparation binds corrected source and unchanged physical input,
candidate and numerical budget; no new stop or process signal. Preparation-only
name collision and subsequent absent-directory review preserved. Second review
rejected comparison of generated Python cache bytes; retry38854 uses a separate
review directory and still checks every actual source/input/proof. No adoption
yet. Later original N200/nu0 frozen auditors also need explicit corrected routes.
HEADa0a4675; no upload, PR or physical qualification claim.

## 2026-11-08 /16:11 / reviewed nu0 consumer replacement

Local73a8c4f stores complete S96 fine N200:57 changed files,1,821,244,349
indexed blob bytes, largest44,682,612; six Markdown checks and exact metadata
byte checks passed. No upload or PR.

New definition0e275a5a6e9d7574f8180b85c8a664b909d2457f466bb7a297b9c42b834bd9d2
preserves all three nu0 plans and the exact budget tail
ead574f634cb6713581244325d3f71690796bb17b5b74b56e5422187c1dfa078.
Independent38359 verified sealed coarse equivalence, unchanged input hashes,
source functions and meaningful changed-report rejection. Review1.023214s,
16,138,240B,2GiBswap0 had zero events and an empty scope.

At16:09:15 new38384/session46596 published readiness then retired only idle
20925/start3575499 after checking no children or held locks. Original status,
source and provenance remain; old process is absent and explicitly cancelled.
New reference-nu0-recovered-budgets-current waits outside the lock for unchanged
family20277. The later EON comparison now uses its reviewed11600 recovery.
All numerical plans/formulas/limits and the separate nu.3 budget are unchanged.

38413 captured the immutable handoff16:11:04:57 files/one431,780-byte part;
actual Git readback passed. Active numerical/future analysis files excluded.
37988 still waits native4000;38175 waits actual adoption;37691 remains old100.

## 2026-11-08 /16:01 / complete S96 N200 capture and live status

Local ad31460 stores the two sealed stop/recovery archives. Capture36172
completed15:56:24:1,672 files,44 parts,1,820,122,244 bytes for the full native
S96 fine N200 trajectory and retained history. Its six preliminary gates
pass; matched fine N400 and all original error-budget gates remain pending.
Stage this large archive in a separate commit with the existing full-byte
Git readback and whole-batch disk reserve. No upload or PR.

Read-only16:01 progress confirms nine active formal producers. S24 recovered
EON sample11844/12800, original reference3815/12800, independentnu0 reference
4323/12800; S24 N200 EON1225/reference871 of6400, L24 4376/6400;
S48/S96alpha2N4001864/1088 of2400,alpha1N200293/1200.
New38175/session15667 waits for actual native4000 adoption before capturing
the sealed original trajectory and immutable handoff. It excludes growing
new continuation results. Reference37988 is still adopted=false.

The old independentnu0 budget20925 is idle with no children, still waiting
for unchanged family20277. Inspection found its later cross-code comparison
points at the failed original EON path. A fresh consumer is being prepared;
no old process or frozen source has been changed. Its own numerical budget
and all nu0 producer inputs must remain unchanged.

## 2026-11-08 /15:52 / sealed recovery evidence

37566 and38013 are complete. Their two archives contain540 verified files,
11 parts,90162492 bytes. Actual Git index readbacks passed at15:42:39 and
15:50:55; every part is an ordinary100644 blob with the D original retained.
README files distinguish the initially unexecuted preparation, actual sample
adoption and reference4000 request that still awaits its boundary. The active
S96 N200 capture36172 and growing sample/reference outputs are excluded.
At15:49 actual sample11725/12800, original reference3782/12800, independentnu0
4270/12800; S48/S96alpha2N4001819/1025 of2400,alpha1N200290/1200. Preserved
all physics failures; no push/PR. The same-chat heartbeat was updated through
the app with the revised producer/consumer identities and original cutoff.

## 2026-11-08 /15:43 / sample recovery and revised reference handoff

At15:18:34 the old S24 EON controller7140 failed its obsolete exclusive22/23
guard after successfully completing warmup11600. Actual nu0 reference21426
already occupied logical23, while22 was free. No nonlinear failure occurred;
the complete v3 seed and success log remain unchanged. Its old budget7593
exited failed at15:18:40. The previously prepared reference handoff was never
run because its idle7593 precondition was no longer true.

Fresh37886/session33816 froze the11600 seed, original2692 binary and exact
MUMPS/chord options, then ran11600→11602 and11600→11601→11602. Independent
37909 reread both states:22 HDF datasets total, all history, legacy clock,
five nodal fields and normalized P1 differences are zero. Resource scopes
were clean; the original failed data were untouched. Actual1200-step sample
began15:35:34 on logical22/2GiBswap0 with shared guest sibling23 explicitly
declared. The new path is elastic-s24-l1-n400-sample11600-recovery-abec003.
Only the new producer state may eventually authorize its new budget consumer.

37533 completed the exact-source coarse EON/reference re-audits15:25:45 with
every physical value unchanged. The257-file8-part62478896B stop-proof archive
completed15:28:04. Fresh reference preparation binds the new EON path and the
already failed old budget; its definition SHA is
603227c6604d182f070ca20afe1d7141cf37b2255e75507edf3b8efeb61878b5.
37948 independent review finished15:39:01 after rechecking the stop proof,
bounded backend binding, sealed prior matched reports and unchanged budget
arithmetic:41.434666s,182452224B,zero events,empty scope. A subsequent compact
display requested an absent optional summary key; this read-only formatting
error did not alter any proof. The passed definition and receipt were reread.

37988/session90386 actually started15:39:59 and first launched new idle budget
37989. At15:40:00 it wrote original reference/results/STOP_SIM=4000, preserving
the native stop proof and5055/6701 identity. No signal was sent to the old
failed7593 or either live reference process. Current adopted=false, waiting
for natural4000; never signal the shared init.scope. Only after original
prefix/native checkpoint validation and family exit may candidate121678 run
4001..12800. Original full12800 audit failure at the planned short boundary
must remain visible. The independent nu0 family and all N200 producers are
unchanged. No push/PR or physical qualification.

37691 began the independent N200 old100 proof15:28:06;37700 still waits.
38013/session39658 now captures the sealed old warmup/failures, complete
split-restart proof and immutable revised handoff/consumer records, excluding
the growing1200-state sample and future reference continuation.36172 remains
capturing the complete S96 fine N200 trajectory. Only completed archives may
be staged as verified ordinary Git blobs.

## 2026-11-08 /15:22 / live steps and separate N200 backend proof

Refreshed the nine formal producers at15:17UTC without counting a partially
iterated reference step. Fine S24 EON N400 reached11595/12800, close to the
11600 sampling boundary; original nu.3/nu0 reference reached3684/4112.
No full-run or physical gate is inferred from these progress counters.
The independent handoff review completed the coarse EON report regeneration:
all physical report values are exactly unchanged; coarse reference is still
being audited. No production STOP_SIM or backend adoption has occurred.

Prepared and queued an independent N200 fine reference proof37691/session93901
from sealed original600/700 native records; original100 must reproduce actual
700 before candidate100 and candidate690→700 replay10. It waits outside the
probe lock until37566 completes the native-stop evidence capture. CPU16,
nice19,2GiB/swap0, strict fields/P1/all native histories/norms/exact time and
at least10% measured cost improvement remain required. The N200 source case
is exact; the normalization comparison allows only dt/steps/checkpoint cadence
to differ from the same-physics coarse N400 case, with physical dimensions
and all other inputs checked identical. This is early-ramp proof, not mature
or full-load validation. Independent reviewer37700/session32509 waits for
the complete screen; it adds immutable case/mesh/scale bindings and actual
empty-scope checks. Neither helper can hand off a production run.
Frozen screen SHA7e70a403dca5093ab59711cfe2e413dc4e0508d975ea2ba348c8cb2bc244d401;
review SHAe002c033a397d6ef535ecb18d55bf5bba0da8e5c22fee179ac0e4b36ad7331a4.
Original29899/29901 and all other formal producers remain untouched. No push/PR.

## 2026-11-08 /15:07 / restore the authorized chat wakeup

The prior id again returned nonexistent on update. Local automation inventory
contained only an unrelated paused task in another chat; it was not changed.
Using the app's heartbeat tool under the existing48h authorization created
eonsim-new-48 ACTIVE in the current chat. Actual automation.toml readback binds
01a1abd8-e4e7-7603-b1fb-c9c9767ba76a,30-minute cadence and original UTC11-09
12:59:10 cutoff. The saved prompt reads the latest repository state first,
preserves all acceptance/upload boundaries and requests meaningful-change-only
notifications. This supersedes the earlier failed-update state, not the fact
that the long studies and physical qualification remain incomplete.

## 2026-11-08 /15:00 / native stop boundary and prepared consumer

At abec003, answered the user's live status request with actual nine producers
at14:34UTC, distinguishing timestep completion from physics and error budgets.
The native reference remains the dominant long-running work. Pinned MAIN.f
checks stopTrigName after coupled solution/TXT, writes a full native checkpoint
when cTS reaches it, emits the output row, then exits and finalizes MPI.
READFILES.f prefixes this filename with the result folder.

The first isolated36325 trial mistakenly placed STOP_SIM at the input cwd;
the solver passed2810. Guarded cancellation14:49:12 signaled only this trial
controller after PID/start/source identity checks; its scope cleanup, partial
states and failure are retained. No production process was signaled.
Fresh37309 at14:49:48 used results/STOP_SIM. It completed14:57:40: serial ten
states2801..2810 and two-rank2601..2610 normally exit, exactly reproduce all
five fields and native Yn/An/Dn/norms/time of the existing uninterrupted proof
(algorithm bytes exclude only elapsed/padding). Both scopes empty, no events.

Prepared continue-reference-fine-ilut.py and a new budget consumer in separate
directories, definition2bf29d18b40a928595b7e4177b51f46abc9ae1310610ae55156efacb4503e8a2.
They are not running or adopted. The proposed normal stop is original nu.3
fineN400 at4000, then same12800 target/physical input/output grid with ILUT,
CPU8/native one-rank equivalent via explicit MPI1/2GiBswap0. Only the idle old
budget7593 would be retired, after its replacement waiter is alive; original
5055/6701 stop naturally, and their full-target audit failure remains visible.
No shared init.scope signal is allowed. The nu0 family is unaffected.

Independent37533/session3878 waits for complete stop proof then reopens raw
states, rebinds the candidate to unchanged production input, checks the exact
old budget function/tail, and actually regenerates the completed coarse pair
with the matched frozen analyzer. Every physical report value and old strict
convergence criterion must stay identical. It is still running; no review
decision, production STOP_SIM, retirement or long continuation has occurred.
The prepared work is execution provenance, not new numerical qualification.

The full native backend proof archive was committed as abec003 (43 files,
566446184 indexed bytes, five Markdown link checks). S96fineN200 capture36172
continues and is not staged. No C++ changes or unrelated test reruns.

## 2026-11-08 /14:25 / sealed native backend proofs

Local16aa5db records the validated v2 change and three complete archives:
6079files/29parts440993104B,72 changed files/446251072 indexed blob bytes,
nine Markdown link checks passed. No push/PR.

Native backend capture36093 completed14:15:03:1104files/26parts565348664B;
actual Git byte verification passed14:21:09. README and proof links now bind the
full raw records, independent reviews and execution-provenance tests. These
late-ramp results remain adopted=false. Capture36172 began complete S96 fineN200
at14:15:24; its growing output is not staged.

Read-only preparation confirms old reference5055/6701 and original budget7593
remain alive, as do nu0 family20277 and budget20925. They belong to init.scope,
so that shared group must never be signaled as if task-owned. No handoff script,
process pause, signal, new continuation or consumer replacement was performed.

## 2026-11-08 /14:17 / completed pairs and explicit execution provenance

At local27f5c82, resumed the status inspection after the earlier usage-limit
interruption. Fresh WSL calls succeeded; nine actual producers remained active.
The detailed13:48 user update distinguishes completed steps from acceptance.
S96 native fineN200 has completed1200+analysis: U/p/Qamp.475826/.360074/.234326%,
phase.060445deg/net1.0872e-17, all six preliminary gates pass; itsN400 and budgets
continue. Original S48 U1.046822% failure remains. Alpha1 actualcheckpoint200
now exists; its queued screen still waits outside locks for25665 and resources.

S12 matched-source recovery35377 completed12:34:16 with every EON report value
except source digest identical, no numerical rerun, and all raw SHA unchanged.
Capture35431 completed1070files/8parts287476596B, native Git readback13:52:27.
S24 coarse pair33659 completed400-phase comparison and4931files/20parts153452668B
at13:43:03; Git readback13:55:51. S12/S24 Lamé errors remain4.8026/3.1950%,
reference ALE remains2.625e-5/2.2113e-5, and S24 midp amplitude3.112885% fails2%.
See their archive READMEs; completion does not override comparison eligibility.

Fine serial reference screen34452 completed13:06:18 and independent34585 review
13:10:22. Original/candidate100 costs2035.326083/1485.136532s (ratio.729679899),
replay10 costs148.146062s. Node/mass/history maxima1.683e-16/3.818e-14/5.304e-14,
norm difference0, native time exact; replay algorithm bytes exact except elapsed.
The two-rank34564 review completed12:04:48 with ratio.765242074 and exact replay
except elapsed/padding. Both remain bounded late-ramp evidence, adopted=false.
Their full raw capture36093 is active and cannot yet enter Git.

Added opt-in svfsi-native-restart-chain-v2 to svfsi_restart_evidence.py. The
original v1 input-equality contract stays intact. A v2 transition identifies both
binary digests and binds a matching100-state backend/10-state replay proof,
exact physical input and native layout, immutable independent review/source/raw
hashes, strict per-equation convergence, clean resource receipts and10% cost
reduction. Production output grid cannot change. Original seed hashes and
excluded tails remain explicit; no full physical qualification is inferred.

Initial Linux36113 passed23 reference+8 pressure tests, both actual proof
bindings and the original S12 full v1 chain. Windows23 had one new positive-test
failure: tempfile used TFBLAB~1 whereas resolve expanded tfblab633. Canonical
evidence paths now accept that same file and reject repeated aliases. Final
Linux36128 repeated23+8/real bindings/v1 chain successfully14:09:48; affected
Windows four tests passed14:09:59. Both source revisions and the first Windows
tool-output summary are preserved. No C++ build or unrelated tests repeated.

Capture36164 correctly rejected Windows-root files outside declared work/D
origins before archiving. Fresh36172 copies those small records byte-for-byte
to its own work directory and preserves the failed controller; no helper or
scope relaxation.78-file/63840B validation archive completed14:14:04 and Git
readback14:16:36. It next waits36093 before capturing complete S96 fineN200;
growing N400 output is explicitly excluded.

The attempt to update eonsim-new-48 at13:54 returned Automation does not exist.
No replacement was created and no successful scheduled continuity is claimed.
The current chat continues active work; the original48h/acceptance/upload limits
remain. This is not a numerical failure or a reason to stop background studies.

## 2026-11-08 /12:06 / explicit analyzer identity and completed bounded screens

At243c9d0, `screen-reference-trilinos-two-rank-retry1.py`34291 completed the
actual2600→2700 original/candidate100-state comparison and2690→2700 replay.
The original final algorithm bytes reproduce the actual production2700 record
except elapsed/padding. Node/mass/history differences are2.012e-16/3.164e-14/
6.614e-14; saved norms and native time match. Replay is bitwise exact except
elapsed/padding. Wall1839.648800/1407.776664/175.832042 seconds, ratio.765242074;
CPU10/16 nice19,2GiB/swap0,zero events/empty scopes. Independent34564 review is
running; original production remains untouched. Fine serial34452 started next.

`screen-reference-mesh-ic.py`34967 completed11:51:16. Same candidate FSI-ILUT
in both arms, only mesh FSILS→Trilinos-IC changes. Numerical20+20+10 passes,
but wall105.185993/149.428208/71.768049 and ratio1.420609 reject the option.
`capture-rejected-reference-options.py`35283 completed11:58:16:293 files/six
parts/56,537,864bytes, including the earlier cancelled placement probe. No
independent adoption review or production change is needed for a rejected option.

S12 reference800-state audit completed with quality/positive geometry passing,
but ALE cycles31/32 maxima2.624921365896e-5/2.624848369670e-5 fail1e-5. The next
observable comparison correctly rejected differing analysis_script_sha256:
old EON90834063 versus reference db4d0e7e. Both34839 and its capture waiter34864
remain failed. `finish-s12-matched-source-comparison.py`35377/session72761 uses
the exact frozen reference analyzer to regenerate only the EON audit and requires
all other report values to be identical. No input-identity relaxation or numerical
rerun. It reuses the completed6400 convergence and800-state reference audit,
then performs the missing observable/200-phase comparison and raw SHA readback.

S12 EON archive47 parts/402,206,344bytes passed actual native-Git byte readback
at11:56:07. The stager now reserves4GiB plus the entire incoming batch and64MiB
before writing, retaining the per-part check. No upload or PR occurred. No new
C++ or numerical regression tests were run: this slice is evidence capture and
necessary re-analysis of existing outputs. Results remain physically unqualified.

## 2026-11-08 / completed S12 solve, preserved cleanup failure, separate audits

At11:33:09, native S12 recovery30063 was marked failed after the numerical
process returned0 at6400. The only leftover scope member was30077, previously
observed as the singleton MPI helper; the controller's own SIGINT cleanup
removed it. Memory events were all0 and the scope was empty. Wall9610.144591s,
peak42418176bytes, original2GiB/swap0. All801 actual fields5600..6400 and the
finite6400 native record exist. No assertion of nonlinear/physical success
was made from exit0 alone, and the original controller failure remains intact.

The first capture waiter34488 correctly refused to call this completed.
`finish-s12-native-audits.py`34839/session47501 created a separate frozen
analysis control, verified original input/binary/endpoint and SHA-hashed every
numeric output before proceeding. It reuses the original required audit commands,
not another numerical solve. The original1..5600 plus resumed5601..6400 chain
passes12800 final equation rows, maximum FS5.6e-11/MS9.8e-11 below1e-10.
The800-state field audit and cross-program comparisons are still running at11:45.
The final action rechecks every numeric byte. New34864/session5970 capture-v2
waits for those audits, retaining both earlier failures and the original12h
timeout/excluded tail. No frozen controller or original status was overwritten.

The two-rank original100 test now exactly reproduces actual2700: history0,
saved norms0, native time exact, all algorithm bytes except elapsed/padding
equal. Candidate100, replay10 and independent review are still pending.
In parallel, the pinned upstream READFILES.f/LS.f were checked for mesh
Trilinos-IC support. `screen-reference-mesh-ic.py`34967 starts a bounded
actual S12 full-load6000 test with the same candidate/FSI-ILUT in both arms;
only candidate mesh preconditioning changes from FSILS to built-in IC.
Original CG, physical mesh equation, assembly0 and all tolerances remain.
20+20+10 states, CPU15nice19/2GiBswap0/1200s per mode, independent-review lock;
this is exploratory execution evidence only, without adoption or qualification.

## 2026-11-08 / native parallel records and bounded reference backend proof

11:28 follow-up: local243c9d0784b18d55d8b267fa0554767f20ca7554 contains61files,
467685384 indexed blob bytes. All23 archive parts were actually read back from
Git before committing. Local staging validation corrected Windows GBK versus
UTF8 text reading and sparse historical file/directory link handling; these
were pre-commit checks, not numerical failures. No upload/ref change occurred.

Queued original mesh-nu0.3 fine serial actual2800→2900 screen34452, preserving
original5055. It uses6625-node native1113064-byte records and requires exact
original100 recovery before candidate100/replay10. Both this and two-rank34291
have independent readback waiters34585/34564; no production handoff. Independent
static input checks11:21:58 confirm original case/geometry/meshes/manifest and
the exact P1 normalization; actual numerical completion is still pending.
34488 waits for full S12 recovery and audits before capturing original timeout,
full native chain, fields/history and comparisons. S12 had6376/6400 observed,
S96 native fine N200 had an actual800 checkpoint at this snapshot.

`inspect-final-push-sizing.py` read actual Git objects across40 commits from
c218c18 to243c9d0:6338031777 raw bytes, largest commit1785544813, largest blob
86012108. Five conservative≤1900000000-byte groups are possible at the current
head. This is a read-only raw sizing proxy, not an actual transport pack; final
remote refs and later objects must be rechecked after acceptance. No push.
Added native-chain CLI/provenance boundaries to PRESSURE_TUBE_FIELD_AUDIT.md;
the new text does not permit unverified backend changes or claim parallel
restoration has passed. No unrelated C++ or numerical tests rerun.

Base1374b625; no push/PR. Extended only `scripts/svfsi_restart_evidence.py`
and its tests: pinned two-rank direct records have a shared709864-byte RECL,
local nodes4225/3600, and105000 trailing non-state bytes in rank1. Decode
finite Yn/An/Dn and exact common step/time/equation norms, bind all rank
layouts to provenance, and preserve the existing serial return shape.
Never compare padding as numerical state or silently accept a serial label.
Full-chain input identity still rejects a backend change; that was not relaxed.

Actually ran `python -m unittest discover -s tests -p 'test_svfsi*.py'`
(19) and `-p test_pressure_tube_audit.py` (8), on Windows and frozen WSL
source. `validate-native-two-rank-audit.py` also read immutable actual
two-rank20/2600/2700 and serial5600/6000 files. All pass; actual parallel
restoration remains unproven. Evidence: work/native-two-rank-audit-validation-1374b6;
[record audit](../research/data/native-two-rank-record-audit-2026-11-08/README.md).
No C++/CI selection change; unaffected8297 Debug/Release checks not rerun.

`screen-reference-trilinos.py` built the pinned upstream source without
patches using installed Trilinos13.2. Candidate SHA121678f9b7a84e2ae07e5061468fbeffb39cd0468d1141517bb5dd2d816a34e3;
original SHA f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf
is unchanged. Explicit FSILS20 reproduces original startup fields/history
exactly; ILUT20 takes340.256496s versus588.202296s, ratio0.5784684942.
Independent `review-reference-trilinos-startup.py` additionally checks
saved equation norms. Both reviews exclude only elapsed from algorithm state.

`screen-reference-trilinos-mature.py` used the actual S12 full-load6000 seed:
original20=265.064113s, candidate20=127.283612s, replay10=63.782413s. All five
fields and P1 mass pass; candidate maximum nodal1.8388069e-16, normalized
mass4.5457445e-14, native history3.1856462e-14, saved norm difference0 and
native time exact. Candidate6010→6020 replay is bitwise identical except
elapsed. Independent `review-reference-trilinos-mature.py` passes10:53:00,
90.446409s/98,418,688B peak, 2GiB/swap0, all memory events0 and empty scope.
[Serial proof](../research/data/reference-trilinos-serial-proof-2026-11-08/README.md)
retains build/source, inputs/oracles, raw outputs and both reviews. These are
shared-CPU bounded timings, not scalability or long-cycle qualification.

First actual two-rank screen34174 used CPUs12/16. CPU12 shares alpha1's
12/13 pair while S12 recovery occupies13; this placement serialized work.
Cancelled only that new controller10:56:06, its cap cleaned its own three
members with SIGINT, and empty scope confirmed10:56:09 (342.258706s).
Partial outputs/failure/cancellation receipt remain. Retry34291/session52411
uses CPUs10/16, unchanged2GiB/swap0/3600s and original numerical controls;
original100 must reproduce actual2700 before candidate100/replay10 proceed.
Neither a producer nor a consumer was switched. No short check authorizes
silently dropping backend identity from full-run convergence evidence.

S24 EON coarse N400 completed10:21:54: five-field periodicity and quality
pass, Lamé mean3.195039% fails2%. Its reference still fails ALE periodicity.
S96 native coarse N400 completed10:22:34: U0.615600%, p0.542559%, Q0.518270%,
phase0.074227deg and net1.047e-17; all preliminary gates pass, fine budgets
still pending. Frozen alpha1 execution-reader normalization clarification
does not change its stricter threshold or any production analytic RMS.
Updated the existing reference/Womersley drafts; neither is published.

## 2026-11-08 / actual-checkpoint preparation and independent coarse time pair

Local8297a417 contains the native restart audit and its validated evidence.
The completed original S24 coarse N400 reference is now fully captured:
1377files/3parts/109010096B, all ordinary Git blob bytes independently read
back. Its ALE periodicity still fails1e-5. The active EON side is excluded.
No push or PR; no unchanged solver tests rerun.

Ran the frozen alpha1 history reader against the already completed startup
archive: `python3 reader.py --plan plan.json --output report.json`, at
work/alpha1-full-history-reader-check-8297a4.320datasets pass; maximum nodal/
history difference5.427776067143397e-12 and normalized P1 mass1.9164190834e-10.
This includes current and time_previous fields, mesh ownership and ghost
agreement. Legacy v3 time remains approximate-contract evidence, while the
new-v4 pair is exact. Source hashes were checked against8297a417 after reading;
the definition records this order. No new numerical solve was made for this check.

`screen-alpha1-checkpoint-lu32.py`31707 queued09:31:22 outside resource locks.
It requires original checkpoint200, original N400 completion and22GiB free
before five paired4rank modes; no producer pause, adoption or consumer change.
`run-s96-coarse-n400-companion.py`31784 started09:39:28: same coarse S96 mesh,
fresh N400six cycles, native1rank/60eb/window32, shared CPU15nice19/2GiBswap0.
It adds a coarse time/tail pair without changing original fine budget arithmetic.
Definitions and completed reader proof are being archived separately from live outputs.

The preparation archive completed09:58:26 with35files/222784B, and actual Git
byte readback passed10:00:53. Original input hashes link to the already stored
alpha1 startup archive; no incomplete simulation outputs are included.

Pinned svFSI already has an optional Trilinos implementation and system13.2
libraries are present. Source inspection found native ILUT modifies zero matrix
diagonals, so backend equivalence is explicitly unproven. Independent
`screen-reference-trilinos.py`31946 started09:53:57 in a copied source/build
tree under2GiBswap0 and shared CPU16nice19. The unchanged original binary remains
in use. Build is followed only by two20-state explicit-FSILS/FSI-ILUT trials,
full-field/native-history/convergence checks and a bounded cost screen.
No package installation, upstream patch, mature-checkpoint proof or adoption occurred.

## 2026-11-08 / audit mapping checks and coarse reference ALE failure

09:12 snapshot: local0029a7e stores the three completed Womersley archives.
Four further completed archives (S96coarse, rejected NS/RCS, native S12 restart
proof, audit-selection validation) total4824files/13parts/185,520,052B and
pass actual Git readback. New code maps shared restart evidence into affected
CI tests.26 selection and6 evidence tests plus one Poisson test per locked
Release/Debug configuration pass09:07:14. No solver rebuild occurred and
both binary hashes remain unchanged.16 reference/8 pressure tests and actual
native chain checks remain separately frozen in the restart proof.

Original S24level0 N400 nu.3 reference6673 completes12800 and field audit
08:45:10, but periodic=false: ALE displacement maximum phase differences
2.211333152e-5 and2.211282780e-5 exceed1e-5 at cycles31/32. Other four fields,
printed relative convergence and quality pass; this is not budget eligibility.
CPU20 successor29899 starts fineN20008:45:14. Independent nu0 family continues.
Capture31614/session43442 saves validation then this completed reference half,
excluding the still-growing EON side. S12 recovery30063 and EON capture28745
remain active. No push/PR or altered physical gate.

## 2026-11-08 / verified native S12 recovery begins

08:58: retry29691 completes numerical proof08:43:12:20 resumed physical
states match the original exactly;10 replay states have byte-identical
serialized history except elapsed execution time. Saved native times match
exactly without claiming an EON v4 clock. Final independent review08:50:55
passes16 reference and8 pressure-audit tests, plus actual two/three-segment
convergence chains. Original1..5600 worst FS/MS ratios5.6e-11/9.8e-11 stay
strictly below1e-10. The first review preparation lacked source/tests;
its partial directory remains. Later reviews use independent directories.

New audited support binds local binary stamps/finite full history, exact seed
hashes, unchanged physical inputs and contiguous log ranges. Excluded old
tail steps stay explicit. Full pressure audits require a complete chain,
not a late restart log, and verify original boundary output bytes. Native
recovery30063/session65771 starts08:52:59 from5600 toward6400 with original
binary/physics/tolerances, CPU13nice19/2GiB/swap0,18000s. Full convergence,
800-state field audit and same-case observable/P1 comparisons follow; no
full physical qualification is inferred. Proof capture30090 is running.

Three completed Womersley archives total3878files/76parts/1,783,550,240B;
all actual Git blob bytes pass readback. Local checkpoint only. Coarse and
rejected-reference-probe captures finish08:43:53; S12EON capture is active.
No push/PR, source solver rebuild or relaxed acceptance threshold.

## 2026-11-08 / S12 reference timeout and explicit restart evidence

08:39 correction: original S12 reference3224/3226 timed out07:35:13 at its
predeclared43200s limit. Complete step5641 and partial5642 remain;6400 is
not complete. CPU20 companion6673 began coarseS24N400 at07:35:17. Original
source, logs, inputs and step5600 native direct-record binary are unchanged.
The pinned binary matches original provenance. New bounded20-state resume
and10-state replay preserve all serialized Yn/An/Dn and saved time. First
attempt29610 failed before solver exec because its parent observed a newly
created scope before MemoryMax was installed; empty scope and blank log are
retained. Retry29691/session20654 starts08:36:58 in a new directory, with
at most5s setup polling and unchanged2GiB/swap0 child validation. No full
recovery adoption yet; printed convergence needs an explicit validated chain.

Native S96 coarse completes1200 and independently compares802 retained
states/20050datasets to four-rank coarse: absolute node/history1.0408341e-17,
normalized P1 mass1.4500918e-16, exactv4 clocks.29270 begins fineN20008:30:27.
Full S48alpha2fine capture completes08:34:09:3094files/59parts/1,432,871,592B;
alpha1 startup capture189files/7parts/106,014,248B also completes. Git staging
and byte readback are running; no push/PR or new physical qualification.

## 2026-11-08 / complete field endpoints and a resource-handoff race

08:14 authoritative outcome: four-rank fine32-state window8/32 completes
943.454471935/632.060752033s,5/2LU,640datasetsmax1.8908485888e-16/exactv4.
Raw-only review finishes07:50:09. A guarded SIGTERM retires only idle waiter
28580 at07:50:31 after verifying fixed start6031536, no child, both held locks,
empty completed scopes, no adoption or long directory. Its handler failure,
complete screen and separate retirement receipt remain; final lifecycle status
is cancelled_before_long_work. No original long producer is stopped.

`screen-rounder-fine-serial.py` completes07:58:04:32states,397.682864605s,
2LU,peak3,539,881,984B. The existing study driver uses native rank1 without
mpiexec/partition, so a separate `screen-rounder-fine-native-serial.py` checks
that actual path:394.727331581s,2LU,peak3,553,603,584B. Both share CPU21 and
the original6GiB/swap0/field/cost limits. Native node/history max vs four-rank
is1.5504091067e-16, normalized P1 mass2.3822602589e-16, clocks exact;
native vs partitioned serial max6.9388939039e-18. Independent960-dataset
review finishes08:08:07 and permits only the fresh matched serial family.
Native report SHA d312e87a41dd38d379b72e5b5fe8ef29467d04e8488097ef278fe705ad2557a9.

`run-native-serial-a2-family.py` starts29270/session91679 at08:08:57, on
CPU21/native rank1/6GiBswap0, unchanged60eb/window32/driver/physical gates.
Fresh S96 coarse N200 precedes fine N200/N400; before fine work, all802
retained coarse current/history states and exactv4 are compared to the completed
four-rank coarse (20050 datasets). Original numerical-budget arithmetic remains
byte-identical. Coarse has reached200; later MPI/fine/budget results are pending.

Alpha1screen25408 completes07:47:37:cached184.667509988s vs oldvector
1358.554362344s/newdefault499.212951618s, with8/1 actual default/cacheLU.
Independent480-dataset review finishes07:53:29; max field/history5.4277765e-12,
legacy clocks differ0 and newv4 are exact. Eligibility is not a handoff;
originalalpha1 continues. Original S48 alpha2N40025665 begins its actual
2400-step solve07:52:01. CPU15nice19 capture29287 now preserves both complete
startup families while CPU17 full-fine capture28315 and its queues continue.

Read-only Git object planning finds36 new commits totaling3,786,182,556B;
largest incremental commit770,519,369B and blob86,012,108B. These are object
byte sums, not transmitted-pack measurements. [Official2GiB push guidance](https://docs.github.com/en/get-started/using-git/troubleshooting-the-2-gb-push-limit)
supports bounded commit batches for eventual delivery after all acceptance.
No network mutation, history rewrite, push or PR was performed by this audit.

07:46 execution update: the four-rank fine window8 completes32 states in
943.454471935s, observed peak4,346,318,848B, no memory events and empty scope.
Window32 remains active. Prepare a raw-only review that cannot trigger long
adoption; after completion, a guarded retirement may release only the idle
review waiter (fixed PID/start identity, no children/adoption, both lock owners,
complete raw review). A separate, normally locked one-rank32-state trial is
prepared with the sameCPU21/6GiB/physics/clock and all current/history fields,
nodal2e-9/mass1e-8 and10%cost gates against both four-rank observations.
No serial trial or retirement has run yet. Alpha1screen25408 has completed
old-vector1358.554362344s and new-default499.212951618s; cached mode starts
07:44:19. Full comparison and any production selection remain pending.

At local code checkpoint`a6643c8`, original S48 alpha2 fine25368 completes1200
and both analytic/periodic/tail analyses at07:13:21 UTC. Velocity1.046822%
still fails1%; p0.196569% and flow-amplitude0.506865% pass. Last two periods
pass, but the matching N400/space/time/sampling budget remains pending.
Fresh S96 coarse27906 completes1200 at07:14:29: velocity0.691816% and
pressure0.679231% pass1%, flow amplitude1.058047% fails. No fine qualification.

The first fresh fine controller27988 fails before partitioning or any solve:
its predecessor released resource locks before writing its completed status.
The assertion sees the earlier state. Original failure/controller/definition
and empty completed_runs remain untouched. Separate retry28580 starts07:22:35,
waiting for completion outside both locks, then reacquiring and checking it.
`wsl.exe -d Ubuntu-24.04 -- python3 <repo>/build/prod48-20261107/run-rounder-fine-refresh32-retry2.py`
uses frozen60eb,4rank guestCPU21/idle-yield,6GiB/swap0; hard limits and original
budget arithmetic remain unchanged. Its controller SHA is
a4488deb891ba693b970c02b0bd2a1116e7fcdcf1360104122763bad4f02e814.
Separate paths bind the future fine N200/N400 consumer pair to the completed
new coarse study. The32-state cost/field screen is running; a prepared raw
reviewer must verify the evidence before matching review permits long work.

S12 fine EON3212 finishes6400 and the800-state audit at07:25:39. The largest
last-two-period five-field normalized difference is1.0130742766e-6<1e-5;
kinematics0,stage mass6.7220534694e-18,divergence theorem7.1757322569e-18
pass, with positive fluid/solid Jacobians. Infinite-plane-strain mean radial
displacement differs4.8026596733% and fails2%; period/quality is not full
qualification. The frozen audit command is `source/scripts/audit_pressure_tube.py
--case case.json --work <S12-study> --first-step5601 --output eonsim-audit.json`.
S24 coarse N400 companion6659 starts immediately on releasedCPU18; reference,
space/time/tail/sampling and cross-code evidence remain pending.

Two separate native reference-option trials use pinned upstream7bdb74c and
unchanged physical/time/tolerance input: `screen-reference-ns-feasibility.py`
only changes FSI GMRES to NS/BIPN; `screen-reference-rcs-feasibility.py` only
changes its preconditioner FSILS to RCS. Both fail their predeclared600second
limit,07:14:01 and07:24:02 respectively. NS emits repeated warnings and only
about9 completed states; RCS completes none. Both2GiB/swap0 scope receipts
show no remaining process or memory-limit event. Neither establishes full
20-state equality/convergence or comparable speed, and neither is adopted.
Actual existing Fortran flags already contain-O3/-march=native; no alternate
native build is created. Full failures are retained alongside successful data.

Full fine capture28315 runs on low-priorityCPU17;28663 waits to capture the
completed new coarse/failed fine startup and the two reference trials;
28745 then captures only completed S12 EON inputs/fields/checkpoints/logs.
Its shared reference directory/logs remain live and are explicitly excluded.
These captures are still in progress at07:32; no growing archive is staged.
No push, PR, merge, publication or lowered numerical gate.

## 2026-11-08 / coefficient-aware LU refresh and complete failed-gate evidence

UTC06:49 completion update: all five archives are complete, with9,469 files
in36 parts totaling744,408,996 bytes; full ordinary-blob index readbacks pass.
Startup retry2 finishes06:35:28; independent2560-dataset/log/event/resource
review passes. New32 costs57.494194266s against old8 first/last103.181454243/
87.337229434s and new default160.046561114s. New8 costs82.359251955s and
fails the10% criterion against the later baseline. The1296-file complete
[cost archive](../research/data/lu-refresh-startup-cost-2026-11-08/README.md)
includes the original checker failure. Only new32 is eligible.

`run-rounder-coarse-refresh32.py` starts a fresh matched S96 coarse six-cycle
N200 study at06:41:24 after independent review, retaining the original S48
producers. A separate `run-rounder-fine-refresh32.py` waits for that coarse
completion/periodicity, then screens32 states before any long fine study.
It uses the same CPU21 serialization, a private6GiB/swap0 scope,14GiB
available-memory admission and8GiB running floor; the parent cap code is
frozen with exactly those resource-constant changes. The rank guard verifies
the actual hard limits. Separate matching raw review remains required.
The fine numerical-budget arithmetic is byte-identical to the existing queue;
SHAaae1723d5c1148f31c13c0ff88e50e4df6bd049e877f8eb3e6abd8607ef6b49c.
Neither a fine-memory fit nor full accuracy/budget success is yet established.

Afterd844e40, the existing alpha2 middle continuation completes1200 states
and original analyses at05:56:47. Periodicity passes; velocity1.851116%
still fails1%. Its3713-file full trajectory archive has10 parts214006344B.
The independent fine cycle4 diagnostic has velocity1.046822% above1%; its
1023-file snapshot archive has20 parts474290060B. Both complete byte/index
readbacks pass. These are not substitutes for full fine-cycle/error budgets.

An independent S96/r8/a8 mesh screen retains all three generated meshes.
Its32-step level0 old-f7 window8/window32 comparison passes640 datasets
(max2.36929e-12, v4exact) but window32 is33.66% slower. The level1 waiter is
cancelled before any numerical work. All436 original files, two archives,
19,683,352B are preserved. A capture waiter with two copied report basenames
is retired before writing any archive; a new controller preserves uniquely
named copies and both originals. No running producer source was modified.

The rejected startup shows11–12 linear iterations after the first BE factor
is retained into BDF2. The five-file patch adds collective explicit LU refresh
and invokes it on effective-time-coefficient changes. Defaults and current
operator/true-residual acceptance remain unchanged; no checkpointed execution
cache. Actual factor-event tests cover an empty-owner rank request, variable
steps, constant startup, events, generalized-alpha startup and recovery.
`validate-lu-time-refresh.py` freezes source hashes and executes six selected
PETSc3.23.7 tests in each build. Debug/Release6/6 pass; each1005-dataset audit
passes, maxima1.4650607116362124e-14/1.465017343549313e-14 with exact v4
clocks/time metadata. The3001-file archive is565360B. Exact commands and
source/binary hashes are in its [README](../research/data/lu-time-coefficient-refresh-2026-11-08/README.md).

The following independent startup cost screen initially rejects the successful
new default run because its checker incorrectly requires FGMRES even when
reuse is disabled; the unchanged default is PREONLY with fresh factors.
The failed controller, assertion, logs and full states remain in place.
`screen-lu-time-refresh-startup-retry2.py` independently rechecks both completed
observations (including default32 actual factors), byte-verifies imported
states, then runs only the remaining new8/new32/old8-last comparisons. At
06:33 it is still running; no performance or adoption claim. Original fine
25368 continues, and alpha1/elastic/reference work is unchanged. No push/PR.

## 2026-11-08 / middle cache adoption and byte-preserving archive storage

At2367903, middle480→488 screen completed with vector/default/cache costs
500.678313912/101.535775972/45.120052223s; actual MUMPS LU counts8/1. All
four160-dataset comparisons pass, including the original continuous trajectory;
maximum4.6010070753332855e-12 and new/new v4 clocks/time metadata exact.
All2GiB scopes are empty and original processes resumed before independent
review. Controller25664 then explicitly adopted from480 at04:59:26. Old
middle processes were retired, as was still-waiting25369;25665 is the matching
fine N400 consumer. Five source-extracted admission cases and wait/algorithm
checks pass. No physical threshold changed. The full833-file archive and
the855-file fine600 handoff archive completed05:19:11/05:15:07 respectively.
Their READMEs contain source hashes, actual commands, limitations and links.

Measured archive ordering on16 completed fine HDF files: the same24,191,616
raw bytes produce17,411,816 bytes generation-first or11,205,436 rank-first.
Every original member matches by hash; observed timings82.019/62.349s are a
single concurrent run, not a general performance claim. A native-Git isolated
fixture then verifies external-file regular blobs, skip-worktree and full tree
readback. The frozen new capture helper stores large parts on D and small
metadata in C without moving/deleting original data. Its26-file real validation
completed05:21:03, followed by actual project-index full-byte readback05:30:28:
39,834,848 bytes, mode100644, blob858cd6ab83181cb68e75012521ae81767d022d42.
The D original remains; no Git ref/config changes or upload occurred.

Commands and exact evidence are in the
[middle archive](../research/data/womersley-middle-lu8-2026-11-08/README.md),
[fine handoff](../research/data/womersley-lu600-handoff-2026-11-08/README.md), and
[storage validation](../research/data/archive-storage-validation-2026-11-08/README.md).
Existing numerical regression evidence is reused; these record/capture changes
do not trigger another PDE or full test run. Long studies and all physical
acceptance gates remain incomplete; no push/PR.
All three archive manifests/copied hashes and nine Markdown link sets pass.
Default staged whitespace checking reports native Windows CRLF in raw JSON;
preserve those hashed original bytes and check with `core.whitespace=cr-at-eol`,
which passes without changing repository configuration or evidence content.

## 2026-11-08 / measured fine LU reuse and explicit accepted600 adoption

Completed old/new-default/cached eight-step fine alpha2 screen at UTC04:26:39.
Whole-job times494.556161080/474.623760231/116.530105585s, actual LU counts8/8/1;
new-default/cache ratio0.2455210112706628. All160 paired HDF datasets passed,
maximum1.0343288725511712e-16 and exact v4 clocks/time metadata. Independently
reread the complete states, profiles and resource receipts before the matching
report-hash internal review at04:28:19. This is a local guest-CPU cost result,
not host physical-core isolation or long-cycle qualification.

At04:28:40 controller25368 adopted the explicit window8 fork from600, after
preparing its target and successor25369, cancelling the unused old waiter and
verifying the entire original scope empty. Old21873/22001/21907 are gone.
The raw original interrupted status remains, with planned-transfer receipts.
The new N400 queue releases CPU/memory locks while waiting for middle results;
its numerical budget tail is unchanged. Alpha1 screen25408 now waits for the
new fine N200 completion without pausing the original alpha1 calculation.

The full fine-screen330-file/7-part/155,598,764-byte archive finished04:40:12.
It also includes immutable reference-prefix diagnostics:4518/1758/1030 steps
all pass their printed relative convergence, excluding the entire highest
in-progress step. These do not replace the eventual full-run audit.
25460 is separately capturing the sealed original trajectory and immutable
new handoff records. New middle screen25496 waits for original488, then tests
same-seed480→488 on CPU21 in a2GiB/swap0 scope;10GiB admission retains8GiB
headroom. This is only an independent screen, not middle adoption. All ongoing
physical and budget gates remain open. No push, PR or publication.

## 2026-11-08 / reference allocation failures and guest topology correction

After d1ad62b, independently screened the unchanged pinned reference on the
existing20-step full-load mesh-nu0 S24 fine problem. Each attempt borrowed
alpha1 CPUs by stopping its six identified processes; a private2GiB/swap0
scope contained the diagnostic, and all six resumed only after that scope
was empty. No reference source or long-study input was changed.

Four ranks with original GMRES100 remained in the first step. GDB stacks
showed GMRES activity; the mechanism was not proved. Cancelled at643.680s
because even the first step already exceeded the complete261.554s two-rank
baseline and could no longer pass the10% cost gate. This duration includes
diagnostic debugger attachment, not a clean performance sample.
The explicit space200 retry retained every tolerance but reached its300s
limit. Five outputs exist; a separate partial log inspection found step5
mesh equation iteration30, relative-to-initial2.51e-9>1e-10. It is a failure.

Two ranks with original GMRES100 and guest CPUs10/12 completed20 states:
max node1.6653345369377348e-16, mass2.4558182111500794e-14; all40 final
equation rows passed. Cost236.232313604s improves the prior261.554205039s
by9.68%, below10%, so this allocation is not selected. Last alpha1 resume
UTC03:57:42. The162-file/17,790,032-byte archive completed04:00:51.

Windows CIM reports16 host cores/24 logical processors for i9-12900K;
WSL lscpu/sysfs reports24 guest CPUs arranged in12 two-thread core groups.
Linux affinity does not establish host-core pinning. Corrected README/draft
labels and recorded both raw observations, retaining immutable prior JSON,
archive hashes and numerical outcomes. No numerical tests were repeated for
these documentation corrections. Prepared alpha1 LU screening remains
unexecuted;24147 still owns the intentionally stopped22001 until its natural
600 boundary screen finishes. No push or PR.

## 2026-11-08 / completed execution evidence and prepared conditional successors

The serial follow-up capture21979 completed at UTC03:09:28. It contains the
earlier whole-job fine screen76 files/3 parts/58,674,092 bytes; alpha1 and
nu0-reference preflights157 files/3 parts/58,980,120 bytes; and completed460
handoff77 files/2 parts/29,916,128 bytes. Each archive was read back and
file-hash verified. Capture identities e435524/977b130 remain separate from
frozen numerical source. No old numerical run was repeated for this capture.

The453 screen's maximum complete-history difference is5.810796288585607e-12,
distinct from its5.296499350215811e-12 current-field maximum. Its local
181.986/353.400 second ratio and original6-process resume are preserved.
The460 handoff independently compared original uninterrupted463; its
4.42640715747622e-12 maximum history difference passed before actual adoption.
The original virtual-address failure and all old outputs remain separate.

While24147 waits for the current natural600 boundary, prepared but did not
start a reviewed600 LU-window8 fork and matched N400 successor. The first
requires a completed eligible screen, confirmed original-driver resumption
and an internal review record matching the exact report/binary hashes.
It prepares the new input/queue before any old cancellation. The N400
numerical budget tail is byte-identical to the existing controller
(SHA2565746119ef3c503b74a458828a6f90a47f8fbc18c942762e904dbfd35c063f067).
AST checks passed; runtime handoff remains untested and unexecuted. Original
21873 and21907 remain active. No push, PR, model change or relaxed threshold.

## 2026-11-08 / naturally drain a segment before another large factorization

After local e435524, an actual parent/child fixture stopped only the parent,
allowed its new-session child to finish, verified the parent had not advanced,
then resumed it successfully. Actual four-rank tiny PDE runs also verified
the exact production `-log_view` parser: numeric LU counts8/default and1/
window8. No performance inference is made from this shared-CPU fixture.

Controller24147 started at UTC02:50:32, with only study driver22001 stopped.
The old MPI launcher22002 and ranks22005–22008 continue to their existing
step600 stopping point. Original controller21873 keeps monitoring and its
resource admission locks. New scopes may start only after all old numeric
children exit and the complete600 checkpoint passes inspection. Three serial
eight-step runs separate old/new executable differences from new/new cache
behavior; the stated field, clock, factor-count, memory, time and10% local
cost gates must pass. Even success only marks eligibility. The driver resumes
after all probe scopes are empty; it must remain stopped if cleanup fails.
[126 startup files](../research/data/lu-cache-screen-startup-2026-11-08/README.md)
preserve source, identity, tested control proof and a dated observation,
not the future numerical result. No producer/waiter was cancelled.

The prior r4 raw capture completed at UTC02:50:39:24,246 files in14 parts,
89,811,864 compressed bytes, capture e435524. The original b072 four-rank
12800-step run and its1200 common-state five-field comparison are complete;
nodal/mass maxima8.60423e-16/7.72856e-14 pass their original limits. This
does not replace the original legacy-clock failure or fine-grid qualification.
The next serial capture21979 has begun the earlier whole-job screen archive.
All numerical trajectories remain separately frozen. No push or PR.

## 2026-11-08 / optional LU preconditioner lifetime and verified factor reuse

Afterd0f9bb3, added a default-off MUMPS factor cache to `NonlinearSystem`,
exposed only for standalone fixed-mesh transient fluid. Fresh SNES/KSP
objects still own per-call callbacks. Current operators and original final
field acceptance remain active; only FGMRES may use the retained factor.
Window, options changes, errors and restart invalidate the cache. Explicit
`study_womersley.py --mumps --lu-reuse-window` freezes this execution policy.

The first attempt preserved a PC reference but SNESDestroy called SNESReset,
which reset the PC factors despite their additional reference. Independent
PETSc numeric-factorization events caught it on1/2/4 ranks although the
small PDE outputs agreed. The fix detaches the PC before SNES teardown and
clears DM/application references before committing the retained owner.
SNES preconditioner-lag APIs also prevent Jacobian assembly from resetting
the reuse flag. These observations were checked against fixed PETScv3.23.7
source, not inferred from a newer manual or pointer identity.

Debug10/10 passed in36.64 seconds. Release evidence combines six unaffected
checks from attempt1, the three LU-count checks from attempt2 and the
isolated fluid rerun from attempt3. Actual AIJ/COO factor counts are1/0/0/1
for window3. Failure recovery includes a Jacobian callback exception on an
empty-owner rank. Eight-step variable-BDF2 direct/cache and five resumed
states on1/2/4 ranks compare455 HDF datasets per configuration: max
1.0401913569857077e-12, exact clocks and time metadata. The second attempt's
separate audit failed because repeat invocations shared old checkpoint
generations; fresh per-run directories fixed that without deleting evidence.

The actual small study-entry check completed at UTC02:32:05: one/two ranks,
13 states each,65/130 HDF datasets, max1.1719791803699309e-14, exact clocks,
immutable resume policy and completed no-op resume. Three invalid option
combinations were rejected before creating a study. CI selection26/26 passed.
Release executable SHA256 is
`f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`.
All sources, commands, raw histories, two failures and reused-test origins
are in the [verification archive](../research/data/lu-preconditioner-reuse-2026-11-08/README.md).
CPU17 was shared: these timings are not performance evidence. No old-PETSc,
full-suite, fine-grid cost or long-run adoption claim. The existing lifecycle
draft and parallel-memory contract record the now-confirmed ownership rule.

## 2026-11-08 / complete clock replay and middle-grid archives

Afterd0f9bb3, documented three completed raw captures: repaired production
clock replay19,302 files/15 parts/106,899,680 bytes; original bounded direct
failure16 files/one part/4,603,812 bytes; alpha1 middle N200 study1,563
files/five parts/171,588,648 bytes. Each capture had archive readback and
per-file hashing. Their capture5091b68 identity is distinct from each
frozen numerical source/executable. Exact commands, meshes, histories and
logs remain in the archives. Documentation work did not rerun those PDEs.

The repaired v4 replay has400 exact logged clocks and400 common final-cycle
five-field comparisons within2e-9 nodal/1e-8 normalized mass-norm limits.
The old v3 clock failure remains. The original3.5GiB per-rank virtual-space
direct attempt failed during allocation, before any accepted step, with
no valid timing ratio. The separate whole-job14GiB policy does not erase it.
Alpha1 middle velocity remains1.6636599947%, failing1%, despite periodicity
and its other analytic diagnostics passing. Full production qualification
is still pending. The r4 capture is still writing and is not included here.

An optional LU-cache implementation is being verified separately, not
adopted. First Release7/10 passed; independent numeric-factorization counts
failed on1/2/4 ranks because SNES destruction reset a shared PC. Detaching
the retained PC before destruction fixed actual counts to1/0/0/1. The
second Release4/4 passed; its separate HDF audit rejected duplicate old/new
generations from repeated test-directory use. A fresh per-invocation test
directory preserves old evidence and removes that ambiguity. Third Release
fluid check and455 HDF datasets passed (max1.0402e-12, exact clocks and time
metadata). Debug10 checks are running at UTC02:27; no performance conclusion.
`/usr/bin/python3 tests/test_ci_selection.py` passed26 checks in0.401s.
Unchanged Release checks reuse the first attempt's passing evidence.
All failed attempts remain; long numerical controllers/binaries are frozen.
No push, PR or publication.

## 2026-11-08 / explicit direct policy and bounded complete-job control

After5091b68, added explicit `--mumps` to the Womersley study, excluding
Schur and allowing chord only with an explicit audited path. Solver options
remain immutable across resume. Actual1/2-rank checks compared13 saved
states and65/130 datasets each: MUMPS versus reused unchanged default
evidence differed by at most5.20417e-18; chord/segmentation by1.61364e-14.
V4 clocks were exact. Rejected policy changes preserved all existing file
hashes, completed resumes were no-ops, and three invalid combinations were
rejected. No numerical-kernel/build/full-suite or historical PETSc rerun.
[331 raw files](../research/data/womersley-mumps-entry-2026-11-08/README.md)
include exact sources, commands, output and resource-control tests.

The earlier fine direct attempt failed under3.5GiB per-rank virtual address
limits. Preserve that failure. A separately declared14GiB whole-job cgroup
cap with swap0 was first tested by actual64MiB allocation failure and real
MPI inheritance. At accepted453, a reversible pause of the original six
processes allowed a same-state four-core screen. MUMPS/chord took181.986s
versus353.400s for Schur/vector/chord, final field difference5.29650e-12,
all histories below their limits and old clocks within1e-12. The observed
cgroup peak was10821701632 bytes. Originals resumed at UTC01:28:58.
The screen did not itself adopt the policy. Full fine outputs are retained
and await their serial archive; the completed report is already captured.

For the subsequent long job, a private cgroup encloses the study driver
and its nested MPI sessions. A real nested-session timeout fixture required
SIGKILL for a child ignoring earlier signals; the complete owned scope
emptied, original timeout propagated and unrelated neighbour survived.
Normal completion also passed. The frozen460/463 handoff21873 and matched
N400 waiter21907 started, initially holding no numerical queue locks.
At UTC01:44 adoption and cancellation of old20754/20817 were still pending.
The old originals continue until the explicit same-state handoff succeeds.

At UTC01:50:05 that handoff passed: all histories differed by at most
4.42640715747622e-12 against the uninterrupted463 reference; clocks happened
to match exactly but retain the legacy tolerance contract. The old7542
family and unused20754/20817 waiters exited completely. The explicit
MUMPS continuation started under the whole-job14GiB/swap0 scope, while
21907 waits for its full completion. Completed handoff receipts were copied
with separate hashes; full raw fields remain queued behind existing captures.

Other completed results: original r4 finished12800, with1200 common stored
states giving max nodal8.60423e-16 and normalized mass7.72856e-14. Alpha1
middle finished1000, velocity error1.66366% still above1%; its fine-vector
preflight804.988→426.417s and3.81381e-12 passed, and fine started01:19:38.
Original parent1180 exited. The separate nu0 S24 reference preflight
396.942→261.554s passed its five-field1/2-rank checks (1.66533e-16 and
2.45582e-14 maxima), selecting two ranks for the ongoing fine run.
The verified400-step transfer archive contains68 files/four parts,
48934952 bytes. All physical gates remain unchanged; no push or PR.
The reusable resource-policy distinction is added to the existing
Womersley draft, which remains unpublished.

## 2026-11-08 / real MPI group topology and complete-session cleanup

Read-only `/proc` inspection showed OpenMPI5 ranks in separate process
groups but the same new session. A real four-rank fixture killed its
launcher while ranks ignored SIGINT/SIGTERM; the surviving ranks proved
that checking only the launcher's process group was insufficient. The
old waiting diagnostic20915 was cancelled with zero numerical runs.
Replacement21129 uses session/start identities and remains bounded by the
same resource and numerical criteria. Original sources and cancellation
receipts were preserved; no running numerical producer was interrupted.

The shared Linux study invocation now starts a new session, lets MPI relay
cancellation, rechecks and cleans all remaining members, retains a cleanup
receipt and propagates timeout/interruption. A successful launcher with
live children is rejected. Seven Python checks passed in9.065s, including
unrelated-session survival. Real2-rank success and4-rank timeout also
passed through the changed runner. No physical kernels, solver options,
non-Linux runner or frozen long-study source changed; no PDE/full-suite
repetition was needed. [24 raw verification files](../research/data/linux-study-session-cleanup-2026-11-08/README.md)
include the exact tested hashes, commands and logs.

The original MPI clock failure archive finished:24550 files,26 parts,
194715212 bytes. The separate full coarse nu0 reference finished1783
files,two parts,73984384 bytes. A hash-linked PNG/SVG comparison was
visually checked; mesh periodicity improved but pressure amplitude and
Lamé mean remain over their gates. The400-transfer and repaired replay
raw archives continue. Rank4 reached12800 and entered audit; full
production acceptance, push and PR remain pending.

## 2026-11-08 / bounded fine-solver screen and independent reference budgets

Atc509af0, the main fine-fluid cost motivated a separately frozen direct
MUMPS diagnostic. It waits for the alpha1 middle solver and analysis to
exit naturally, using the option-probe lock to defer the next fine screen.
The same400 seed, candidate binary, mesh and three steps are used for both
modes on four physical cores. Per-mode900s, per-rank3.5GiB address space
and an8GiB available-memory floor bound the experiment. It adopts nothing;
positive convergence,2e-9 fields and10% local cost reduction only permit
later review. Current numerical producers were not signalled or modified.

A separate mesh-nu0 budget watcher was prepared because the original S24
auditor intentionally targets the unchanged nu.3 family. Its existing
`study`/`analyze` function ASTs are identical; added checks bind physical
inputs and the separate reference export identity. Both watchers passed
syntax/startup checks and remain waiting. No numerical success is claimed.
[30 verified files](../research/data/bounded-followup-startup-2026-11-08/README.md)
preserve frozen sources, identities, inputs and bounds. The original large
archive continues; no full-suite rerun, push or PR occurred.

## 2026-11-08 / immutable successors replace waiting schedulers

At08718b9, separately prepared successors were syntax-checked and tied to
the tested segmented study source. Exact PID/start/command and waiting
states were checked before signalling15446/15457/7639 individually.
Their original sources and cancellation receipts are preserved. Child5422
remained alive with the same command; old `finally` resumed1180 and the
new watcher20806 then held that outer parent again. No numerical solver
was stopped during this replacement.

The new alpha2 watcher20754 waits without a numerical lock for a complete
600 seed and uninterrupted603 reference. It will verify copied inputs,
stop only the identified owned group, wait for cleanup, and validate the
three-step restart before a separate segmented continuation. It has not
yet performed that future handoff. N400 successors20817/20825 follow the
new statuses and wait without holding the producers' locks. The alpha1
fine screen and all scientific gates remain mandatory.

[114 verified files](../research/data/segmented-queue-handoff-2026-11-08/README.md)
contain both generations of controllers, snapshots and prepared S24 nu0
inputs. That reference queue also remains pending. The original large
MPI/clock/reference captures continue independently. No push/PR occurred.

## 2026-11-08 / cycle boundaries bound individual solver calls

After86bbdac, review distinguished a legal CLI timeout from a sufficiently
short numerical segment. Fine-mesh timings can make an existing multi-cycle
invocation exceed86400s. The optional `--cycles-per-solve` bounds individual
invocations at whole-cycle checkpoints while keeping every attempt's
physical final time fixed. Default invocation structure is unchanged;
receipts expose the explicit execution choice.

[604 verified files](../research/data/womersley-segmented-execution-2026-11-08/README.md)
record real1/2-rank checks with both the validated v4 binary and the frozen
v3 Schur/chord/block3 candidate. Default versus4/8/12/16 stopping points
agree across all13 saved states and full HDF datasets: v4 differences are0,
legacy maximum6.939e-18. Legacy exact clocks in this small fixture do not
override the known long-trajectory v3 failure. Invalid0/-1 counts are
rejected and resuming a completed study creates no additional attempt.
No rebuild/full-suite repetition was performed. Existing long controllers
were still unchanged; separately frozen handoffs remained the next step.

## 2026-11-08 / checkpoint compensation and the original production failure

The original b072 rank2 production replay passed400 field states, but the
exact HDF clock gate failed:183/400 accepted clocks differed and the final
difference was2.842170943040401e-14. Rank1/rank2 full trajectories and their
1200-state comparison passed separately. The original failure is retained;
the history checker stopped at `rank0/clock`, so its later checks cannot be
reported as passed. The prior contract promised tolerance-level replay.

At base6f202a1 the correction used by compensated clock summation was
identified as missing accepted algorithm state. Checkpoint v4 now stores
it in the manifest and all HDF rank clocks; all six physics drivers pass
it into restore. V3 remains readable with an explicit zero fallback and
approximate-clock diagnostic. Nonfinite or rank-dependent corrections
are rejected without replacing the previous published state.

[10464 archived files](../research/data/checkpoint-clock-v4-2026-11-08/README.md)
contain exact modified sources, repository build commands, Debug/Release
8/8 checks each, and a real four-rank Womersley v3/v4 reader comparison
with four corruption rejections. Raw test paths were resolved from actual
CTest commands, including differently named P2/restart directories. Only
the low-priority archive worker was moved after CPU starvation; no solver
affinity changed. No full suite or old-PETSc repetition was performed.

The corrected binary's real rank2 continuation starts from a common
legacy11600 seed, then splits at a new v4 checkpoint12400. All400 logged
time/accepted_dt/evaluation_time values and final HDF history clocks are
exact;400 restart fields differ by at most6.45318e-16 and normalized mass
RMS7.18431e-14. Its1200-state comparison against the original trajectory
also passes. The final periodic/quality audit passed at23:53:06UTC, with
exact follow-up receipts copied separately; the larger raw archive is
still being captured. The rank4 original-binary continuation
is running. This does not recover any correction already lost in v3.

Separately, the four-core alpha2 checkpoint400 screen passed5.087e-12 with
488.690→339.692s local cost, selecting the explicit vector continuation.
The mesh-nu0 full coarse reference has passed its original periodic and
quality gates, but pressure amplitude2.58247% and Lamé mean8.31525% still
fail. An independent matched S24 family waits behind existing work, with
a20-step1/2-rank execution screen before its32-cycle solves. The original
nu.3 family is unchanged. No push, PR, merge or draft publication occurred.

## 2026-11-08 / path-dependent mesh diagnostic and pending CLI correction

Ata7a177e, code review found a pending-controller defect:172800-second
timeout exceeded the actual study CLI's86400 maximum. Both waiting jobs
were cancelled before lock acquisition/numerical work, retaining their
identities and receipts. Independent replacements split N400 at natural
cycle5 then resume to6. Eight actual CLI checks reach the intended input
guards for legal commands and reproduce rejection of the old timeout;
none launches a solver. [70 verified files](../research/data/womersley-time-queue-recovery-2026-11-08/README.md)
preserve the full correction. No active producer or numerical gate changed.

The [34-file mesh-loop diagnostic](../research/data/reference-mesh-loop-2026-11-08/README.md)
exactly reproduces the prior closed-boundary drift. Subdividing the same
piecewise-linear path200→400→800 changes normalized drift1.93212e-5→
1.92857e-5→1.92681e-5. A first harmonic gives the same drift, while a rank-one
shape path gives2.05308e-7. The two harmonic boundary directions have nodal
singular-value ratio.353202. These observations support path dependence,
not a claim that all coupled temporal errors have been explained.

Counterfactual mesh nu0/.45/.49 produce5.85007e-6/5.10700e-5/5.78988e-5
drifts; physical solid normalization remainsnu.3. All true linear residuals
are below2.769e-15. A separate original-binary S12/N400 coupled nu0 run was
started onCPU23 at23:07:34UTC; only its new mesh-equation input differs,
and the original export is retained. Full12800-step convergence, original
periodic/quality gates and cross-solver results remain pending. This does
not relabel the original failednu.3 trajectory. MPIr2 has finished12800
and is being audited; restart and rank4 remain. No push/PR occurred.

## 2026-11-08 / polygon reference and matched follow-up definitions

Atfa9646d, L24's central fluid/solid tetrahedron coordinate sets exactly
match the translated L12 mesh. Same-b072 startup fields agree within
2.844e-25 using default SuperLU_DIST versus MUMPS/chord; the long6400-step
study is running. [66 verified files](../research/data/pressure-length-preflight-2026-11-08/README.md)
preserve inputs, three-step results and a dated incomplete long-run scope.
Changing length also changes inertia; no pure dynamic end-error claim follows.

Fine N400 successors for both Womersley frequencies wait without the
producer's numerical lock. Self-review found missing middle/control
periodicity and mass prerequisites in the first waiting controller. It was
cancelled before numerical work; independently frozen replacements preserve
the original gates. [37 files](../research/data/womersley-time-queue-2026-11-08/README.md)
record this change. N400 controls target the fine N200 budget, not an
independent N400 spatial qualification. Production MPI's completedr1 long
trajectory matches the previous default backend over1200 phases; r2 continues.

The independent P2 complex cross-section reference isolates fixed-polygon
geometry. The initial S96/level3 attempt failed without an informative
exception; attempt2 reproduced true-residual stagnation above1e-11. Attempt3
introduced extended accumulation but incorrectly checked it against a
double oracle at an extended-precision bound. Attempt4 uses an80-digit
decimal summation oracle and extended state/residual correction, retaining
all original1e-11 gates. One correction achieves9.081e-15/7.788e-15 on the
finest S96 systems. Complex quadratic manufacture errors stay below2.630e-13.
All failures, sources, twelve completed final-attempt complex fields and
the observed-refinement evidence are in [106 verified files](../research/data/womersley-polygon-reference-2026-11-08/README.md).

S48 velocity geometry differences are.497830%/.454478% foralpha1/2; S96
gives.123803%/.112978%. Successive reference changes are below1e-4, an
observed-resolution criterion rather than a rigorous error estimate. The
hashed PNG/SVG figure was visually checked. No production binary changed,
no full or historical test suite reran, and no push/PR occurred.

## 2026-11-08 / production-clock MPI and immutable queue recovery

Atf0422d0, the new S12/N400 MPI/restart study freezes b072 and identical
MUMPS/chord options for1/2/4ranks. Initial import failed before solver launch:
the frozen source omitted the indirect mesh-generator dependency. Independent
attempt2 adds it, retaining the original failure. Five-step final-state checks
pass; full32-cycle trajectories and rank2 restart from12400 remain running.

The alpha2 middle N200 screen first specified zero fluid checkpoint cadence.
Input validation rejected it before solving. Independent attempt2 uses3;
three-step final nodal difference1.71695e-12 passes2e-9. CPU21 shares its
physical core with reference20;124.325/105.634s are local observations only.
The explicit six-cycle study starts22:13:09UTC, default tau and200 phases.

The same invalid cadence was found in the pending alpha2 fine400 probe.
Waiting controller6906 alone received SIGINT; finally resumed the same631,
with all numerical process identities untouched. Separately frozen controller
7542 then held631 again, preserving the natural400 endpoint. Old source,
planned replacement and dated snapshots remain; no pending frozen source was
patched in place. Alpha1 watcher7639 holds only outer parent1180, while child
5422 completes its existing middle study. Fine adoption requires a later
same-four-core screen passing2e-9 and10% cost reduction; otherwise parent
resumes. S24 budget controller7593 waits for complete producer receipts and
preserves all convergence/periodic prerequisites, using a bounded sampling
cache. [390 verified files](../research/data/production-queues-2026-11-08/README.md)
cover completed startup checks and frozen queue snapshots, not long-run
qualification. No push or PR.

## 2026-11-08 / optional velocity metadata, N400 evidence and explicit boundary queues

After054b64a, the opt-in standalone Tet4/P1 Schur velocity block-size3 path
collectively checks semantic triples and extracted ownership. Root operator,
pressure block and stopping criteria remain unchanged. Debug six selected
checks pass. Release five checks passed in attempt2; legacy Schur timed out
under four ranks on one physical core. With identical sources, idle-yield
enabled and the unchanged limit, the one failed check passes16.7033s; the
five successful checks are reused with exact source hashes. Initial malformed
selection input and timeout artifacts are retained. Real small-tube1/2/4rank
third-step LU comparison has maximum difference1.01170e-13. Six completed-study
CLI preservation/rejection checks and26 selection checks pass after the
Python-only runner/mapping changes. No unrelated or old-PETSc suite rerun.

Fine checkpoint200, steps201–203: candidate default metadata733.265s versus
block3 539.742s on one physical core with four MPI ranks. Final field difference
5.08531e-12 passes2e-9; default candidate versus retained b072 field differs
5.63786e-18. All accepted clocks and convergence reasons pass. Peak rank RSS
increases992313344→1063612416bytes. These are local observations, not scaling.
[967 files](../research/data/womersley-vector-metadata-2026-11-08/README.md) verified.
At21:13:58UTC, watcher6906 holds only Python scheduler631; numerical ranks
continue normally to400. Exact checkpoint verification and a separate original
four-core comparison must precede any new block3 continuation. Old state remains
preserved, with failure recovery controlled by watcher receipts.

Coarse S12 N400 completes12800steps in both programs. EON periodicity/quality
pass; reference all-equation convergence/quality pass but final mesh period
maximum1.91055e-5 fails1e-5. Mid-pressure amplitude2.58266% fails2%, phase
.183517degree passes1degree. Actual N200→N400 fields,31→32 tail and200→400
sampling are separate observations, with no spatial-denominator budget pass.
[8289 files/16 archives](../research/data/pressure-tube-n400-2026-11-08/README.md)
verified; the derived PNG/SVG has exact input hashes and a visual layout check.

The S24 five-step preflight archive first rejected a valid last-state hard link.
Original failed archive/source/status were retained; dereference mode retries
only capture and verifies[79 files](../research/data/pressure-s24-preflight-2026-11-08/README.md).
Previously completed N400/vector archives were not recomputed. The resumed
capture queue finishes at21:45:44UTC: [3126 alpha1 files](../research/data/womersley-alpha1-followup-2026-11-08/README.md)
and [103 direct-screen files](../research/data/elastic-direct-options-2026-11-08/README.md)
are verified. Alpha1 level1/N100 velocity1.66523% still fails1%; level0/N200
velocity/pressure/flow amplitude2.29153%/1.58464%/2.46513% also fail. These two
studies differ in both mesh and time step and cannot themselves isolate either.

That S12 level1/N200 checkpoint1400 direct screen has three-step final
differences below3.47e-17 and normalized mass norms below1.21e-14. Standard,
MUMPS, serial SuperLU and MUMPS+chord local times17.956/11.194/60.128/6.633s;
CPU21 shares a physical core with ongoing reference CPU20, so only option
screening is claimed. It has completed and released CPU21. S24 watcher7140
subsequently verified the complete400-step checkpoint and deliberately
interrupted the old numerical process at21:47:32UTC. The old log includes
steps401/402, which are recomputed from durable400. Its independent CPU22
three-step confirmation takes21.886264/14.335186s; final nodal difference
7.45389e-20 and largest normalized mass norm1.12140e-17 pass both limits.
At21:48:12UTC the explicit MUMPS+chord continuation starts, retaining b072,
the physical inputs and tolerances. [116 verified files](../research/data/execution-continuations-2026-11-08/README.md)
preserve completed confirmation and dated in-progress execution snapshots;
the long continuation is not yet qualified. Other long studies/paired budget queues
continue; alpha1's future fine output directory was mapped to empty D storage
without moving raw files or editing its frozen controller. See the latest task
queue for precise process/lock paths. No push or PR; fullPROD-02 remains open.

## 2026-11-08 / N200 budgets and independent mesh-path replay

At6093f01, both coarse N200/ramp16/c32 runs completed6400 steps. Reference
equation logs all pass, but its mesh period maximum1.93514e-5 fails1e-5;
EON periodic/quality gates pass. Mid-pressure amplitude2.48284% still fails2%,
phase.51230degrees passes1degree. N400 five-step reference startup passes at
the unchanged nonlinear threshold and explicit1e-26 linear floor; its full
12800-step study is running onCPU8. Same-polygon space runs continue on18/20.

Read-only same-source N100/N200 fields, tail and actual100→200 phase sampling
are now available. Five manufactured sampling oracles pass1e-14. Spatial
denominators remain pending; no10% budget pass. The independent mesh replay
reproduces actual N100/N200 reference fields at max normalized nodal differences
2.70e-15/4.79e-15 (predeclared limit1e-8). Closed-boundary incremental paths
retain1.946e-5/1.932e-5 mesh RMS drift; fixed-geometry pseudoelastic controls
return near1e-16. No coupled rerun, altered accepted field or reference patch.
[4298 verified files](../research/data/pressure-tube-time-2026-11-08/README.md).

Nine quarter-annulus static Lamé cases are complete, [108 files](../research/data/lame-static-2026-11-08/README.md)
verified. The original4/6 quadrature check failed; its successful solve was
reused hash-identically for6/8 analysis, then eight further solves completed.
All6/8 changes below1e-9; energy/pressure-work agreement within4.45e-14.
Volume-field errors are not all monotone. These axial-only/symmetry supports
are distinct from fully clamped FSI. The PNG/SVG preserves both mean and full
field behavior, with visual layout checked. Ten separate full-annulus clamped
L12/L24 solves subsequently completed onCPU22; matched local mesh sizes give
.30%–.39% mid-wall change on the Lamé scale; [109 files](../research/data/clamped-static-2026-11-08/README.md)
verified. These are static observations, not dynamic end budgets. A five-step
S24/level1/N400/ramp16 coupled preflight started onCPU22 atUTC20:19:37;
long-study selection remains pending its result. No C++ rebuild or unrelated
regression rerun.

The alpha1 parent alone is temporarily held for a bounded GAMG option screen;
its existing numerical child completed500 steps normally. The same-parent
finally-resume receipt controls recovery. No numerical state was discarded.
Local-only checkpoint, no push/PR; overallPROD-02 remains in progress.

## 2026-11-08 / bounded PC screen and elastic spatial continuation

Frozen b072/PETSc3.23.7, exact probes at c49c69c. Three-step coarse/fine
Schur GAMG, pressure-HYPRE and all-HYPRE checks all pass2e-9 physical fields.
Fine pressure-only difference3.3132e-12, wall366.70→292.45s; all-HYPRE has fewer
iterations but takes575.01s. Six logical CPUs18-23 are three physical cores;
other jobs ran on disjoint cores. These are local observations, not general
performance/scaling claims. No running study option was changed.
[94 files](../research/data/womersley-schur-options-2026-11-08/README.md) verified.

S12 level1 N200 no-ramp five-step EON/reference solves completed on CPU18;
15877 EON DoFs, positive geometry/convergence,23.95/26.22s. Separate ramp16
reference five-step check onCPU20 passed, maxFS9.9e-13/MS9.8e-12, no caps.
[123 files](../research/data/pressure-tube-space-preflight-2026-11-08/README.md) verified.
Prepared immutable6400-step common input and source snapshots; independently
locked EONCPU18 and referenceCPU20 startedUTC19:34:53/19:35:09. Available memory,
host disk and actual solver affinity checked. Five numerical jobs are now
active, not five MPI jobs; maximum MPI size remains4. Long spatial acceptance
is pending, and the short preflight is not substituted for it.

Coarse N200 EON6400 steps completed, periodic and quality gates pass; maxlast
cycle1.9194e-6. Its reference remains running. A provenance label in the original
N200 controller inherited0b9e980 although the base wasc49c69c plus exact copied
changes. Added a separate correction receipt; preserved original controller,
record and source hashes. This corrects metadata, not numerical results.

## 2026-11-08 / convergence guard, startup comparison and N200 continuation

Follow-up: malformed iteration rows now fail explicitly, so an unreadable
later row cannot leave an earlier converged-looking value as final evidence.
Four affected unit checks passed (.043s); four actual logs reaudited without
new solves or changed conclusions. Eight exact review files verified.
The [6846-file startup archive](../research/data/pressure-tube-startup-2026-11-08/README.md)
is complete, including failed initialization, recovery and handoff attempts.

Sourcec49c69c plus the captured Python changes: pinned PIC.f marks the iteration
cap as ok. Added strict all-equation/all-step log checking, bound by export
manifest to the field report. Either printed relative criterion must be below
1e-10; rounded equality stays unproven. Missing logs cannot qualify reference
comparison. Actual13200-step log passes26400 final equation rows; ramp2/c12 has
2400 cap rows and1215 relative failures. Both raw histories remain available.

Explicit tighter reference linear floors do not change nonlinear/physical
gates. Five coupled steps with1e-22 passed for ramp2, failed ramp16 first mesh
step at1.1e-10. At1e-26, ramp16 N100/N200 passed with at most2/3 iterations.
Exporter6, log auditor4, field auditor7, selection26 and manufactured binding4
checks passed. Initial synthetic log whitespace caused a missing-row rejection;
preserved that attempt, accepted harmless bracket whitespace and reran only
the affected checks. [181 verified files](../research/data/svfsi-convergence-2026-11-08/README.md).

The queued ramp16 driver had already started when a waiting-job cancellation
was checked; no signal was sent then. At accepted3200, a planned handoff stopped
the driver during its read-only audit to prevent the known inadequate reference
floor. Its audit child also ended without a report. Repeat only that failed
read, then use a separately frozen tightened export/driver; all EON states were
preserved, no PDE rerun. Reference3200 steps now pass the full relative audit.

Four completed histories were reaudited with the same current implementation
and matching log evidence. Before comparing startup, declared1e-5 for all five
maximum-phase normalized P1 fields. EON132 vs ramp16/32 passes, max1.8903e-6.
Reference fails: internal mesh difference.00217017; both reference histories
also retain about1.95e-5 per-cycle mesh drift. The short-startup result therefore
applies only to EON. No geometry/period gate was removed. Mid-pressure amplitude
and phase differences remain about4.90%/2.66degrees, so no elastic qualification.

AtUTC19:08:54, PID2808/session71064 began explicit N200,32-cycle ramp16 study on
CPU8, retaining default tau and frozen b072 binary. It uses1e-26 only for the
reference linear floor, then checks every relative solve before field analysis.
Separately, a bounded existing-PC screen on verified CPUs18-23 owns the former
CPU18 lock and a probe lock. Coarse3-step GAMG/HYPRE pressure/both variants pass
field differences below2.3e-12; same-mesh fine probes remain running. These
concurrent timings are local option observations, not general performance.

## 2026-11-08 / General pressure, long-tail result and runtime isolation

Follow-up UTC18:48: ramp2 reference completed but has1999 cap-iteration rows.
Pinned PIC.f explicitly marks maxItr as ok; this is not a convergence proof.
Its small startup load exposes the linear absolute floor1e-14. Inspecting a
tighter linear solve and an independent log-convergence guard is the next task;
nonlinear1e-10 is unchanged. The ramp16 EON warmup already started at18:46:45;
the attempted cancellation of a waiting job failed its read-only state check
before any signal or mutation, so its existing computation continues.

At0b9e980 plus the archived Python changes, inspected pinned svFSI READFILES.f,
FFT.f:IGBC and SETBC.f:SETBCNEUL. General inputs need scalar negative pressure,
exact mesh-local face node IDs, endpoint-time knots, and a final knot beyond
the simulated end to avoid periodic wrap. --general-pressure is explicit;
default Fourier behavior is unchanged. The C2 startup law and alpha_f offset
are evaluated at the fixed-step reads, with no fitted pressure/phase parameter.
Actual zero-ramp and half-period-ramp100-step inputs passed1e-9; maximum endpoint
recurrence errors4.188e-13/4.050e-13. Exporter5 and auditor7 unit checks and6
manufactured startup comparison checks passed. [288 verified files](../research/data/pressure-general-input-2026-11-08/README.md).
Only Python input/analysis paths changed; no new C++ build or unrelated rerun.

The long EONSim continuation reached13200 steps with positive accepted endpoint
geometry and passed its stored129-132cycle audit: last two cycle maxima below
3.73e-6, kinematics0, maximum stage flux3.25e-18. The initial reference launch
failed in MPI_Init: its system OpenMPI4 cannot use the inherited OpenMPI5 sm
component. Preserve original inputs/logs; copy hash-identical inputs to
reference-attempt2 and clear all OMPI/PMIX/PRTE settings and runtime library
paths. PID1540/session83316 runs only this reference recovery on CPU8.

Bounded CPU18 startup probes used actual affinity checks, separate from0-7,
8 and10-17. The ramp2/c12 EON result is not periodic (last-two solid-velocity
maximum.003693). Its initially frozen controller had the same reference MPI
environment error. A queued recovery first hit a status race: the numerical
lock is released before the original controller's outer exception handler
updates its status. This preparation failed before any new solve. Preserve
that script/status receipt, then wait for the previous process to exit and
validate the actual MPI_Init log/no-output state. PID1707/session46033 now
runs only its reference on CPU18. A ramp16/c32 candidate PID1800/session65764
waits on the same lock. Different startup is explicit and still needs actual
periodicity and same-solver comparison with the long unmodified startup.

Alpha1 level0/N100600steps finished; u/p/Q amplitude errors2.4358%/1.7679%/
3.1368% fail while periodicity passes. [2071 verified files](../research/data/womersley-alpha1-first-2026-11-08/README.md).
The sequential alpha1 controller continues level1. No concurrent-performance
claim, physical tolerance change, public upload or PR.

## 2026-11-08 / disjoint alpha1 queue

At0b9e980, a real four-process affinity check (no solver) verified CPUs10-17
for every rank, disjoint from primary0-7 and serial8. Started the frozen-source
alpha1 controller atUTC18:17:07, PID1180/session73417, with its own queue lock.
It retains standard Schur and b072 binary, runs paired N100/N200 small/medium
meshes, then six fine cycles with200phases, including actual same-grid time,
same-N200 space and5→6tail comparisons. Before each new study it requires
5GiB available memory,8GiB host-drive space and no overlapping solver affinity.
Preflight/controller provenance is in work/womersley-alpha1-0b9e980. No
alpha1 physical acceptance or concurrent performance claim at startup.

## 2026-11-08 / continuation, controlled tau time and late elastic windows

Source2eabb47 fine lag=-2 screen passed with field difference1.03e-14<2e-9,
observed156.54→148.06s. Explicitly forked immutable step200 into
womersley-a2-s48-l2-n200-chord-m200 with200phases, same binary/mesh/dt; actual
continuation started UTC17:47:12. First coupled/check evidence3423files and
all option evidence139files were read back and verified, failures included.

The accepted2189a8c binary completed coarse alpha2/N2001000steps with
tau-time2*(T/100)/3. Last-cycle differences8.09e-13/1.24e-14. At common BDF2
tau-time, N100→N200 RMS field differences are.000551646/8.41201e-6; at common
N200, changing tau-time gives.00409246/.00823032. Norms are not additive error
budgets; N100's first BE startup tau-time differs. Coarse analytic gates still
fail. [1574 verified files](../research/data/womersley-fixed-time-2026-11-08/README.md).

Added explicit --first-step audit windows and reference output-start-step.
At least three full cycles plus a real preceding endpoint are required. Stage
and volume-budget initialization use that state, and quality claims name the
stored window. Four exporter checks and11 manufacturing/window/full-history,
gap/duplicate/phase/count/field-range checks passed. A1% static dilation has
nonzero initial volume and deliberately violates caps; that gate remains failed.
The first harness passed integer-key dicts to a JSON comparator and raised
KeyError3; preserved it, then read its serialized reports in a new attempt.
No PDE was rerun for that test error. [551 files](../research/data/pressure-tube-window-2026-11-08/README.md).

Resource inspection showed24logical CPUs,32GiB RAM, about28GiB free and primary
rank affinity0-1/2-3/4-5/6-7. Updated the earlier single-job scheduling choice
to one primary four-rank queue plus one separately locked serial job pinned
toCPU8. This is not a timing benchmark. AtUTC18:01:41 the serial controller
resumed the original600-step elastic state toward128warmup+4sample cycles,
then the pinned reference. It freezes analysis/adapter code and checks affinity/
memory. Both active jobs and the heartbeat are recorded in the task queue.
No long-tail physical result has completed at this checkpoint; no push/PR.

## 2026-11-08 / actual checkpoint handoff and first coupled audit

AtUTC17:24:14 the watcher verified all four step200 HDF5 states and BDF2
histories, hashed the complete generation and interrupted only the recorded
MPI process. Its planned interruption and original attempt are preserved.
The queued2189a8c checks then ran: fluid_stabilization_time Release1/1 in2.78s,
Debug1/1 in3.31s. Unchanged-derivative oracle maximum2.12e-16; MPI/restart
differences2.78e-17. Explicit svFSI stage-pressure100-step recurrence/stage
errors5.45e-13/1.45e-13 passed. No unrelated numerical tests were rerun.

Both first coupled calculations reached600steps, but the reference audit
failed on reference coordinates. The real pinned writer uses Float32 positions
and Float64 physical arrays; the previous manufactured fixture used Float64.
Fixed exact binary32 input-node matching, with collision/one-ULP/topology
rejections and original input geometry for integrals. Six standard-library
tests and independent VTK fixtures passed. Reanalysis of both unchanged
histories passed kinematics/stage mass/positive geometry but not periodicity;
mid-pressure difference4.9021%/2.6578degrees also fails the prespecified gates.
No physical qualification is claimed. See[output contract](PRESSURE_TUBE_FIELD_AUDIT.md).

Short execution probes preserved all failures: COO passed field comparisons
on coarse/fine meshes but fine wall time158.80→159.75s and peak rank RSS
1.186→1.784GB do not justify adopting it. These are bounded3-step observations,
not scaling results. lag=-1 failed at SNESSetFromOptions; pinned PETSc source
explicitly rejects that command-line value despite its separate API meaning.
Runner/probe now use-2 (build first Newton Jacobian, reuse within that step).
Coarse3-step field difference2.60e-15 passed; fine check pending. No push/PR.

## 2026-11-08 / phase-sampling analysis preparation

At0eb4544, ran `build/prod48-20261107/check-womersley-phase-sampling.py` on
the three existing100-phase cycle5 histories. Their own50-phase linear
reconstruction differs by about.00139 in normalized cycle-RMS fields.
This is not a100→200 sampling budget. The independent sinusoid interpolation
RMS matches `(1-cos(pi/50))/2` within1.6e-17; linear signal error8.89e-16 and
invalid-grid rejection also passed. All3 helper/report files were read back
and verified; no PDE solve or new dependency.

Restricted the unexecuted fork helper to warmup checkpoints, since a later
single-generation fork would omit required phase history. Added explicit
new-study phase cadence as preparation for actual200-phase data at unchanged
N200; no real fork occurred. Existing prepared-file hash/status updated;
original metadata-check archive stays unchanged. AtUTC17:18 the active fine
job had accepted step193. [Sampling evidence](../research/data/womersley-first-2026-11-07/README.md).

## 2026-11-08 / end pressure and reconstructed stress

At5cd0c2b, ran `build/prod48-20261107/audit-womersley-end-stress.py` on the
existing three cycle5 histories. It finds each end triangle's unique parent
and integrates P1 pressure and reconstructed `p-2mu*du_x/dx` harmonics.
The independent affine oracle's maximum error is1.164e-13. Level1/N100 drop
complex-amplitude errors are5.80515%/3.42207%, respectively; these are not the
volume pressure RMS and do not establish a discrete-formula defect. No new
PDE solve or acceptance criterion. Both helper/report copies were SHA256
verified; [evidence](../research/data/womersley-first-2026-11-07/README.md).
AtUTC17:13 the active fine solve had accepted step186; handoff still awaited200.

## 2026-11-08 / immutable execution-policy preparation

Sourcecfa5d3cd4d4c81ee56cec895a53678e9a6973b96 adds optional COO/within-step
chord arguments to the Womersley runner. Default definition construction is
unchanged; nondefault solver options participate in resume identity. Chord
requires the inspected Schur preassembly path. No C++ change or option adoption.
Ran `check-womersley-execution-metadata.py` with system Python and MPI replaced
by /bin/false: legacy completed-study no-op passed, both policy changes were
rejected on old-study resume, and unsupported chord was rejected before input
loading. All original study files/attempts stayed unchanged (4/4 checks).
Syntax/CLI loading also passed; unrelated analytical tests were not rerun.

Seven raw files were read back and verified. Bounded same-state probe and
explicit-origin fork helpers are separately marked prepared/unexecuted in
[the evidence](../research/data/womersley-execution-2026-11-08/README.md).
Static review corrected the fork's expected command tail to include MPI
partition arguments after the options, before any actual fork was attempted.
The original fine solve reached step178 atUTC17:06; handoff/acceptance still
waited. No extra numerical job, source-study mutation, push or PR.

## 2026-11-08 / actual BDF2 tau-term reconstruction

Executed system-Python `build/prod48-20261107/audit-womersley-tau-terms.py`
at source checkpointf7a32f6, reading existing cycle5 b072 checkpoints only.
For coarse/level1 N100, mean squared temporal fractions are.662492/.124660;
same-state half-dt mean tau ratios are.582931/.857109. Maximum advection
fractions are1.058e-8/5.020e-9. These are coefficient diagnostics, not physical
error bounds or causal attribution. Their200 stored previous fields match
independent predecessor checkpoints exactly. N200 sparse saving has zero
direct preceding-file checks, explicitly distinguished from a zero error.
Both raw helper/report files were read back and SHA256-verified in a61000-byte
archive; [full evidence](../research/data/womersley-first-2026-11-07/README.md).

Also reviewed the C++ delta from c218c18 and the pending diagnostic tests;
no new defect identified. The waiting controller's entire guarded source
diff against2189a8c returned0 in Ubuntu-24.04. No solver reruns for this
analysis. At UTC16:52 the fine solve had accepted step159 and the handoff
was still waiting. C: had25.1GB free; D: has946.7GB available if later large
archives need another local location. No files were moved or deleted.

## 2026-11-08 / prepared elastic comparison and ALE interpretation

At checkpoint7a344a9, executed `check-pressure-comparison.py` (5/5) and
`check-pressure-field-comparison.py` (3/3), under build/prod48-20261107 with
system Python3.12/NumPy1.26.4/SciPy1.17.1/VTK9.6.1. Independent known harmonics,
phase wrapping, undefined amplitudes, invalid/stale acceptance, nested affine
patches, exact constant mass norms and actual manufactured dual-reader files
were checked. These are not solver outputs. All28 raw files were archived
and read-back SHA256-verified. The four helpers remain research tools with
explicit original-path assumptions; production solver/auditor paths and the
waiting controller's guarded inputs are unchanged. Actual commands and
comparison definitions are in the
[evidence](../research/data/pressure-tube-comparison-2026-11-08/README.md).

Read pinned svFSI MESH.f/LELAS.f: mesh extension uses previous geometry and
incremental displacement through the elasticity kernel; its quadrature weight
differs from physical elasticity's Jacobian-weighted integral. EONSim uses
fixed-reference vector Laplace. Recorded source hashes and the limitation
that cross-code reference fields are not Eulerian point matches. No claim
about the effect on the not-yet-run periodic response; no gates relaxed.

Generated a three-panel plot from the existing Womersley localization JSON
using Matplotlib3.6.3. Moved an overlapping legend after visual inspection;
final PNG/SVG and input/output hashes retained, with no numerical-data change.
Expanded the two existing drafts and knowledge index; no public push/PR.

## 2026-11-08 / offline Womersley localization and mesh screen

No additional PDE solve. Executed system-Python helpers
`build/prod48-20261107/localize-womersley-error.py` and
`screen-tube-interpolation.py` using NumPy1.26.4/SciPy1.17.1/h5py3.14.0.
The former reads cycle5 of the three existing b072 studies with quadrature6:
level1 first-harmonic velocity error remains about1.71–1.96% across the eight
mesh-aligned axial bands, so it is not restricted to the ends. Non-first-
harmonic relative norm is at most2.546e-7. Pressure-gradient localization is
recorded without causal attribution. Supplemental helper/report hashes are
separate from the already frozen Womersley archive manifest.

The latter creates/screens six mesh definitions with quadrature4. It records
analytical nodal interpolation, tetrahedron mean ratio and the zero-advection
tau temporal-term fraction. These are not numerical solution errors, best
approximations, runtime predictions or new qualification. All34 raw files
were read back and SHA256-verified in a5597956-byte archive. Sources are
unchanged from2189a8c; repository checkpoint4fc5002. Exact commands, helper
path assumptions and evidence are in the
[mesh screen](../research/data/tube-mesh-screen-2026-11-08/README.md) and
[localization supplement](../research/data/womersley-first-2026-11-07/README.md).
The existing draft was expanded; no additional numerical tests were needed.

At UTC16:25 the original fine solve had accepted step126; the single
checkpoint200 watcher and acceptance controller were still waiting. A first
status query used the unrelated Ubuntu distribution and found no paths; the
correct active runtime is Ubuntu-24.04. No process there was changed by that
read-only query. Prepared option-probe helper passes Linux CLI loading; no
option probe or alternative-mesh solve has run. No push/PR.
Changed-Markdown check passed7 files; 20 historical file/directory targets
were verified in Git despite sparse exclusion. Its first draft did not
recognize sparse directories, which was corrected before recording the pass.
Tracked diff whitespace check passed; no solver tests were rerun for capture.

## 2026-11-08 / planned accepted-state queue handoff

The active fine Womersley job advances at roughly 50 seconds per accepted
step; no formal performance estimate is inferred from this observation.
To get the first coupled checks earlier, a single watcher was started
UTC2026-11-07T16:16:02Z. It waits for step200, validates the atomic pointer,
all four HDF5 rank states and BDF2 history, hashes them, then sends SIGINT only
to the original prterun PID419 after checking its command/start identity.
It verifies original ranks exit; it never sends an additional forced kill.
Record: work/scheduled-handoff-200.json. Watcher PID1431/session56874.
At this checkpoint it is still waiting; no accepted state was discarded.

The already waiting acceptance-2189a8c controller will acquire the same lock.
After its checks, inspect controlled probes of existing fluid_coo and PETSc
within-step Jacobian reuse, before explicitly resuming the fine study. No
option has been adopted and no tolerance changed. The original incomplete
attempt and interruption must remain recorded. This is an intentional
scheduling interruption, not a solver-convergence failure. Do not automatically
restart the fine case while the short acceptance or an option probe is active.

## 2026-11-07 / 2189a8c reader evidence and replacement queue

Local source commit 2189a8c9589add9376c060ef4e4c2e871fdb0c60 is complete as an
implementation checkpoint, not physical qualification. The replacement
queued-next-acceptance controller started UTC15:47:37 and waits on the same
MPI lock; output acceptance-2189a8c. It will run the minimal time-scale tests,
stage-load check, both coupled cases and their actual field audits. Current
Womersley remains frozen at b072 and was not interrupted.

Ran the retained reader and pipeline helpers with /usr/bin/python3 and VTK9.6.1
on manufactured data only. VTK actually ignored one of two legacy identically
named displacement arrays. The aliased data preserved physical fields exactly,
with reference-coordinate difference 1.11e-16 and the deliberately imposed .004
interface defect recovered. Both complete 48-snapshot manufactured histories
recovered their prescribed pressure harmonic and distinct first-stage clocks.
These are not solver outputs or physical acceptance. Reopened both archives
and verified all 185 files; [commands and raw fixtures](../research/data/pressure-tube-audit-2026-11-07/README.md).
No change to production code after 2189a8c for this evidence capture; no extra
numerical tests, public upload or PR.

## 2026-11-07 / coupled output aliases and physical field audit

Read pinned svFSI READOUTPUTS/WRITEVTUS before its first coupled run. Both FSI
and mesh equations default to the name Displacement, while their physical
meanings differ. The exporter now uses the supported Output: Alias syntax to
preserve Solid_displacement and Mesh_displacement separately. Uniform-pressure
fluid-only historical evidence is unaffected. Actual coupled alias reading is
pending, not claimed from the text/geometry tests.

Added audit_pressure_tube.py with strict reference coordinate/topology mapping,
exact P1 mass norms, material mid-ring/section observations, positive deformed
geometry, stage mass reconstruction, interface/end constraints and harmonic
observations. Frozen normalization and phase definitions are documented in
[the audit contract](PRESSURE_TUBE_FIELD_AUDIT.md) before the first coupled
outputs. Endpoint net flux is not an alpha-stage residual, and trapezoidal
volume change is an independent time-quadrature diagnostic.

Actual commands: python tests/test_pressure_tube_audit.py (5/5),
python tests/test_svfsi_export.py (3/3), and python tests/test_ci_selection.py
(26/26, with process-local safe.directory). No solver was rerun for these
analysis/input changes. The waiting b907 controller was cancelled while queued,
with no children/jobs started; its receipt is acceptance-b9075f0/queue-cancelled.json.
The frozen Womersley MPI run continued. The replacement controller will run the
same bounded acceptance sequence plus actual coupled field audits. All numerical
and physical acceptance still pending remains explicitly pending.

## 2026-11-07 / local evidence checkpoint and sparse link check

The steady/Womersley/reference/Debug evidence above is retained locally; no push
or PR. All new individual archives are below 100 MiB (largest 86,012,108 bytes).
`git diff --check` passed for the then-tracked edits. After staging, the full
check reported whitespace in preserved raw logs and CRLF JSON sidecars; those
evidence bytes were not rewritten. `git show --format= --check HEAD -- '*.md'`
passed on local checkpoint 3934131. A structure/link check of the 11 changed Markdown
files found no missing repository targets. Twenty historical link targets are
tracked but excluded by this checkout's existing sparse data rule; their paths
were verified against `git ls-files`. The ordinary
`node website/scripts/check-content.mjs --source-only` returned failure because
it checks only the filesystem and cannot see those excluded historical files.
This is not reported as a passing full website check, and no numerical test was
rerun for this documentation/evidence commit. The active fine Womersley solve
and the single waiting acceptance process remain unchanged.

## 2026-11-07 / pressure tube region correction before coupled execution

静态检查发现study_rigid_tube.write_mesh把体单元标签固定为10，而新压力管固体配置为20。
FSI读取器会拒绝Unexpected independent FSI volume tag；不能用只检查几何的VTK导出测试证明
EONSim可读。b9075f0fa19b11ecf8ac8ed1a89e9366aa7c3a09为写出函数新增显式region参数，
新压力管按配置传入10/20，并在几何测试中独立读取实际Gmsh体标签。Python导出3项与原网格3项通过。
未执行耦合求解的旧输入已归档保留；生成全新elastic-s12-l0-region20，不覆写旧网格。
仅撤回等待锁的旧验收进程（尚未执行任何验证），取消记录在acceptance-d280e7f/queue-cancelled.json；
当前Womersley求解未中断。新等待进程以b9075f0为源码基准，输出acceptance-b9075f0。
当前数值验收仍pending，不把这个准备阶段修复或仅编译当作通过。

## 2026-11-07 / 48h continuous / d280e7f research checkpoint

本地提交d280e7fdd84a8bf3c2e63185623afb2907faba7c，未push或PR。前三个Womersley状态
及同相位完整场比较完成；速度门槛仍失败，时间/参数变化为首档空间差54–56%，尾项很小。
具体参数和三份归档5169文件哈希核验见[初期研究](../research/data/womersley-first-2026-11-07/README.md)。
只有alpha2与4rank，alpha1/更细预算/几何/MPI物理对照仍待完成，未把流量达标当全场完成。

b072压力边界Debug最小检查2/2通过，原始280文件已核验保存；数值代码在该构建时未变。
d280后新增fluid.stabilization_time_scale，只替换默认tau估计中的有效时间尺度，互斥固定tau，
瞬态专用且写入重启签名。真实粗网格时间变化触发此诊断；默认算法、导数及容差不改。
新代码已仅编译通过，三时间格式离散oracle、无滑移算子变化、1/2rank、续算/拒绝测试待实际执行。
纯Python源码语法检查及更新后的CI选择26项通过。一次Windows CI选择调用因仓库所有权校验失败；
仅用该进程的safe.directory环境配置重跑后通过，没有改全局Git配置。

固定svFSI原生压力输入100步的速度/压力递推误差2.51e-15/4.61e-13。紧凑ASCII标签、
逐行ASCII连接表、多分量连接表、raw二进制及填充尝试均失败或在通用读取器前被拒绝；
采用其原生zlib格式后标准VTK与svFSI均通过，全部失败文件和213原始文件已核验归档。
详见[参考输入检查](../research/data/svfsi-import-2026-11-07/README.md)。发现参考程序按终点读取载荷、
按alpha_f组装；新增显式阶段转换，按公式而非结果拟合，实际运行仍待执行。

当前唯一数值作业：womersley-a2-s48-l2-n200，冻结b072、四rank、目标1000步，warmup400。
每次子命令timeout21600秒；较细网格推进慢，若超时须保留失败并从完整checkpoint续算，不能标通过。
后续唯一等待进程queued-next-acceptance.py（work/next-acceptance-current.json）持相同锁，
按顺序执行d280的Release/Debug各一项最小检查、显式stage-pressure参考检查、两程序首个600步弹性管。
完成进程仅表示有输出，弹性物理资格仍需审计。新建两篇知识草稿，不发布。

## 2026-11-07 / 48h continuous / steady field checkpoint

冻结c218c18求解器及b072cc8研究入口完成96/48/96四rank，447073节点/2626560单元，
Krylov restart120/max4000，1012+187次线性迭代，残量9.93658e-14。
六项事前门槛全部通过，原始失败和较粗未达标结果保留；详见
[证据及实际命令](../research/data/rigid-tube-schur-2026-11-07/README.md)。
六份压缩包78个原始文件全部回读核验SHA256；没有重跑无关数值测试。
1737节点1/2/4rank Schur/LU差最大5.66e-13，不是最细网格并行/直接法证据。
扩充现有全场误差草稿；继续本地工作，未上传或创建PR。

alpha2、48/4/8、100步/周期的Womersley首轮五周期完成。最后两周期场差已低于1e-6，
但速度L2 2.36670%、压力RMS 1.15345%、Q幅值1.47233%未达到1%门槛。
q4与q6分析速度指标差1.662e-7；同一原始场后处理加密，不是重复求解。
首次分析因NumPy布尔值无法JSON序列化而失败，改为标量float后仅重跑分析；未改场或门槛。
level1、粗网格N200和追加第六周期依次排队。svFSI均匀时变压力输入检查也在同一锁后等待。

## 2026-11-07 / 48h continuous / pressure boundary checkpoint

用户要求连续48小时，全部验收后才push/PR。窗口北京时间11月7日20:59:10至11月9日20:59:10。
发现PR #38已由远端合并，取主线c218c18建立本地codex/fsi-production-48h-20261107。
本地源码检查点b072cc81e29160488e5c08044d8aee3b0245078f，未上传。定时续接eonsim-new-48已建立；
WSL目录/home/tfblab633/EONSim-prod48-20261107使用mpi-queue.lock，禁止重复数值作业。

先复用95文件哈希核验的历史LU原始场，Schur在48/4/8种子1/2/4rank的最大逐点差5.66e-13。
96/24/48默认Krylov 500次失败（DIVERGED_ITS，残差2.446e-8），完整日志保留在steady-schur-refined；
新的独立目录以restart=120/max_it=2000求解，539+86次线性迭代收敛；rtol/atol未改。
112945节点的Q、速度L2、压力RMS误差为0.133114%、0.189354%、0.218287%；
端面压降3.087918%、归一化散度1.467790%未过事前门槛。96/48/96四rank继续计算，
冻结二进制SHA256 f7e694748f37dbaaed15096f7b140c96eddaadac66d5bc78eac38e2677c82613。

新增瞬态压力边界复用FSI正弦律，按积分阶段施加载荷；零均值用单位牵引缓存，不除以均值。
checkpoint保存频率沿用现有格式，保持接受态/重启签名约定。仓库入口PETSc3.23.7 Release四项
通过：fluid_pressure_time、tagged_fluid_verification、fsi_element_jacobian、fsi_pressure_state。
精确离散均匀加速流覆盖三时间格式及1/2/4rank，误差1.98e-16；续算、频率和拒绝检查通过。
Python刚性管9项通过。CI选择首轮因新增规则缺python列表出现KeyError，修正后26项通过。
原始280文件归档、日志、哈希及初次失败说明见[证据](../research/data/fluid-pressure-time-2026-11-07/README.md)。

Womersley研究门槛已事前写入队列；解析Bessel参考三项检查通过，独立SciPy结果差1.22e-18；
正权Gauss/Duffy规则的五次单纯形矩误差4.44e-16，直接时空积分与谐波/质量矩阵误差积分差3.2e-15。
数值研究与HDF5审计脚本仍待实际算例验收。首个alpha=2、48/4/8、100步/周期、四rank任务
已排在稳态细网格之后，不能重复提交；等待的flock进程也属于唯一数值队列。

从本机只读svFSI仓库固定提交7bdb74cdd517310d6bf32c0bb7d42072aeac8658导出独立源码快照，
系统GCC/GFortran/OpenMPI/OpenBLAS构建成功，未改动原仓库。参考程序在reference/build/bin/svFSI；
选项与日志在reference/，尚未执行物理对照。确认该版本FSI允许lElas域，可与EONSim线弹性材料匹配；
不把两套不同Neo-Hookean公式仅按同名视为相同材料。

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


Execution notes: original EONSim workspace connector returned internal errors twice.
A fresh checkout of the existing branch was used; old uncommitted work could not be
inspected. Git HTTPS push dry-run lacked credentials; repository objects are uploaded
through the connected GitHub API, with tree equality checked. No auto-merge.
The new numerical solves use unchanged source at 92d63f1; postprocessing source is
4113ab8. Commands, initial failures and raw inputs/fields are in the evidence link.


## 2026-11-06 / FSI-PROD-02A 刚性管稳态流量基线

- 恢复：远端已合并PR #36/#37，基线dc378529538259567a78cea9820a202a6187809c。
  复用当前checkout，未修改旧WSL工作区。Windows Git报告295个M但diff空；逐文件确认原始blob
  与索引一致后刷新这些路径的索引，确认暂存diff为空，才建立独立分支；没有reset或丢弃用户修改。
- 实现：a0d228764850fa838229acb6a6e613933070490f。原接口每tag单一条件不能表达相容的
  Poiseuille端面：只允许按互斥笛卡尔分量组合流体条件，压力可选分量；规范检查移至实际法向
  trace，唯一标签诊断避免重复计数，签名涵盖全部条目。固体仍要求tag唯一。
- 验证设计：R=1/L=2/rho=mu=1/Delta p=.02，Re=.0025/alpha=0；充分发展稳态解，
  red细分保持多边形边界；几何变化单列。事前设定流量2%、末档变化1%、MPI2e-9、净通量1e-10。
- 首轮七个串行状态和MPI完成，但level-2场变化5.670926%/2.479559%失败；继续12边形到level4、
  48边形到level3、补24边形level3，不重复原状态。最终流量1.264676%、末档变化
  0.410813%/0.024769%、MPI2.78e-17、净通量4.12e-17通过；压力3.993089%仍未资格化。
- 实际构建与检查：仓库run.sh、PETSc3.23.7、WSL2、单线程/单MPI队列；首轮Release
  tagged_fluid/regions 2/2；扩充重启分量/规范检查后Release tagged_fluid/rigid_tube 2/2；
  Debug三项3/3。网格与重算3项、CI选择26项。此前CI选择在Windows遇到Git所有权保护，
  仅为当前进程设置该checkout safe.directory后通过；无全局配置修改。无数值求解失败。
- 证据：[原始数据、命令、校验和及迁移重算](../research/data/rigid-tube-2026-11-06/README.md)。
  构建原SHA/dirty字段保留，以实际数值源码哈希与二进制身份关联实现提交。未做性能测量。
- 自审：流量通过不能掩盖压强和局部散度误差；几何界适用于连续多边形解，不是FE约束。
  没有独立审查者。未重跑无关FSI/时间研究；PROD-02的Womersley、弹性管、瞬态tau、svFSI待后续。
- 知识沉淀：按eonsim-knowledge-capture生成[草稿](../../website/drafts/rigid-tube-geometry-and-mixed-boundaries.md)，
  区分理论、实现、实际验证和未测性能，保持draft；本地验收完成，已创建
  [PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38)，未合并。
- 云端最终验收：[run 42236840428](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42236840428)
  PETSc3.23.7 Debug/Release各26/26，零失败/零跳过；Python26+6+3=35项与增量receipt通过。
  网站run42236840526通过。测试合并预览3f4625c394cb487a17b00a400ea98d2b9eb53375的tree
  2802d32421aa6c6c9ec49ac0146862b3de0d7853与已审查head d1c4be0完全一致。
  Debug运行较久，期间日志尚未发布，结束后读取实际成功计数；没有假定提前通过。
  最终补记仅文档/证据，后续CI应复用同PR成功收据。完整11状态研究仍是本地证据，CI只做小回归。

## 2026-11-06 / FSI-QA-01 质量预算有效性修复

- 基线：main `815755eb15ffb63299487e8f9163ddc9d242a2f2`，PR #35已合并。工作区连接两次内部错误，改从GitHub核对后克隆主线；未修改原连接工作区。
- 源码：`80571b102e31dd2e7664a64a39a92efc8402045c`，分支 `codex/fsi-mass-history-validation`。
- 复现：一条t=.1、dt=.1、进出流均0、体积1的历史，传入`initial_volume=NaN`，旧函数返回`final_defect=NaN`而`max_absolute_defect=0`。t=1e-12、accepted_dt=-1e-12也通过旧绝对容差检查。
- 根因：初始质量状态未验证；NaN在max归约中可被掩盖；时间一致性容差没有单独约束接受步长符号。有限输入也可在积分中溢出。
- 修复：验证初始三标量有限/体积正值，接受体积和步长正值、时间差有限；积分和缺陷在归约前验证有限性。梯形积分公式和既有时间一致性容差不变。
- 实际测试：`python tests/test_fsi_cycle_metrics.py` 10/10；`python tests/test_fsi_archive.py` 2/2；`python tests/test_fsi_field_cycles.py` 8/8；`python tests/test_fsi_space_metrics.py` 6/6。均为系统Python、无MPI/无PETSc依赖、无C++构建配置。`git diff --check`通过。
- 归档重算：以下命令实际执行，9组22400行、36个质量预算值精确一致；这是旧求解输出的新后处理验证，不是新的数值求解。C++/PETSc 3.23.7 Debug/Release、MPI以及3.19.6均未运行。
- 自审：volume_budget所有调用者共享修复；正常非零起始时间/非零初始通量续算通过；归档和原收据未改写。无独立审查，不推断既有数值证据曾含异常状态。
- 文档生成曾因嵌套here-document结束标记冲突失败，确认无文件变更后改用结构化补丁。代码修复没有失败尝试。
- 知识：补入既有周期FSI草稿，保持draft，无新架构决策。

```sh
python - <<'PY'
import csv,gzip,json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
from fsi_cycle_metrics import volume_budget
root=Path('docs/research/data/fsi-next-03/time-accuracy-final')
count=0
for expected in json.loads((root/'mass-convergence.json').read_text()):
    name=f"{expected['scheme']}-{round(.1/expected['dt'])}"
    with gzip.open(root/name/'flow.csv.gz','rt') as stream:
        rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    result=volume_budget(rows)
    assert all(result[k]==expected[k] for k in result),(name,result,expected)
    count+=len(rows)
    print(name,len(rows),'rows: exact match')
print('PASS: 9 archived histories,',count,'accepted rows; all 36 budget values unchanged')
PY
```


## 2026-11-05 / FSI-NEXT-03 验收与PR #35交付

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。

新执行命令及阶段退出码见证据matrix-status.json；归档重算见relocation-audit.json及relocated-budget.json。
原始失败未删除，冻结的生产输入74份逐字节匹配Git，二进制SHA保持不变。
n=8尾项交付包明确只保留每个区间末周期实际场；全部标量历史保留，迁移后从这些场重算验证。
本轮自审没有未解决阻塞项；不声称独立外部审查。按eonsim-knowledge-capture收敛既有草稿，未发布。

## 2026-11-05 / FSI-NEXT-03 本地接续与归档迁移修正

- 恢复最新分支`1b33db8`，核对main仍为`4f3a995`；保留已有Linux旧项目的未提交修改，复用其锁定PETSc依赖。
- 仓库完整下载无有效进度，按需取源码/相关归档；Windows换行导致首轮shell入口失败，恢复LF后用仓库run.sh成功编译。
  Release只执行`fsi_periodic`，1/1通过；构建dirty标志原样保留，74份生产输入逐字节匹配Git。
- 固定τ粗网格归档878文件、7700行接受历史和研究指纹核对通过；本地二进制完整周期重放最大场差2.21e-15。
  n=2半步长从初态计算88周期收敛；n=4两步长39/49周期收敛；n=8原步长31周期收敛；五状态尾项和100相位采样完成，n=8半步长继续。
- 发现原误差估计仅用绝对目录名和generation绑定，导致完整数据换机器后不能审计。
  `e4bda86`改为generation、完整检查点SHA、网格SHA和研究定义校验；`python tests/test_fsi_space_metrics.py`6/6通过。
  不改原receipt，不允许用路径迁移跳过不同构建的重放验收。
- 原固定n2续算包仅含30份索引/日志，没有实际场片段；本轮真实重算尾项/密集采样，并归档全部引用文件和SHA。
  归档辅助脚本最终打印的st_size调用错误已修正，重新生成并回读验证；未涉及求解。
- [本轮命令、日志及数据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。
  五状态15个归档迁移后45833文件SHA匹配，三个区间场差和尾项全部重算一致；10组续算的22400行接受历史质量/几何检查通过。
  n=8尾项包保存各区间最后周期的实际场及全部标量历史；大采样包4 MiB分片后重组SHA匹配。完整原件保留本机。
  无新Debug或全量检查；其余历史证据在未改数学/输入路径的前提下复用。整体尚未完成，无PR。
  使用eonsim-knowledge-capture更新既有误差分离草稿，未发布。

## 2026-11-04 恢复与串行补验

2026-11-04 已从远端 a67f329 恢复同一分支，核对 main 仍为 4f3a995。默认三网格归档逐文件校验通过（923/743/678 个文件），重新审计 8600/5000/3700 条接受步。使用仓库 restore.sh 和 run.sh 恢复 PETSc 3.23.7 Release，所得可执行文件 SHA-256 为 b4de28ffc6481701b533ec4772f4f0f604cfc18bc15bc63c858ebebae38352da。单一 MPI 队列的 fsi_periodic、fsi_flow、fsi_inlet、fsi_pressure_state 均通过。旧固定 τ 算例缺少原始场和 checkpoint，固定 τ=.05 的三网格与两步长研究从初态重算。完整误差预算、证据审查及 PR/CI 仍待完成。 原始日志、JUnit、构建摘要及归档复核见 docs/research/data/fsi-next-03/recovery-release/。

## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 自审修正与实测尾项

阶段检查点已推送 `4119d8622a708997d25b66453957f33d178fdb6b`，与本地对应tree一致，无PR。随后自审修复连续但末尾截断历史可能被误复用的问题：原因是仅验证相邻时间连续性，没有验证达到声明终点；新增终点/步数/精确相位校验，并排入截断历史负例。时间矩阵原始数据在SHA和配置核对后显式迁移定义并重新分析，全部门槛仍通过，无重算/补造数据。

n=2在原86周期状态之后追加三个十周期块，完整场块间收缩率约0.54–0.57；得到经验尾项估计，非严格误差界。n=4追加周期与n=8周期检测继续。审查同时区分了波形重建与相位积分误差：正式空间/时间场差采用真实100相位，50/100统计差作为采样误差；20相位插值诊断另列。用户要求的时间/剩余瞬态10%阈值未改变。

## FSI-NEXT-03 时间精度与质量预算已验证，空间研究继续

本地基础提交 `96f232f`，后续改动尚在同一分支实施。三格式完整第二周期的时间精度矩阵已通过：BE 最小受检阶0.864，BDF2 1.882，generalized-alpha 1.981；参考加密差占最小候选误差3.17%–3.21%。累计质量预算的最大误差阶分别约1、2、2。它们是固定tau、n=2的瞬态验证，不替代稳态空间研究。原始配置、压缩CSV/日志和第二周期场已归档 `docs/research/data/fsi-next-03/time-accuracy-final/`。

新增可选 `fsi.checkpoint_interval`，默认仍每个接受步保存，指定停止点/最终接受步必保存；周期研究仅需每周期保存。仓库编译脚本完成 Debug 7/7 受影响回归，证据 `cadence-debug/`；后续纯Python相位采样/压降检查仍继续针对性验证。默认稳定化n=2已在第86周期通过，n=8仍在运行；从已收敛状态追加周期的瞬态估计和真实100相位输出复核正在实施。没有创建PR，也未声称48小时预算耗尽。


## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

本文件记录有实质代码、算法、验证或知识产出的开发会话。只记录事实，不写无法复现的“已优化”“性能显著提升”等结论。

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。

## 2026-11-03 / FSI-NEXT-02 — 周期流量、无滑移与移动域质量预算

- 用户授权20小时预算、同一独立分支持续实施、阶段检查点；全部本地验收/审查之前不创建PR，完成后唯一汇总PR且不自动合并。基线main `b2755b6`，分支 `codex/fsi-next-02-periodic-flow`，实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`。
- 首先读取 main/仓库契约；此前20小时计划原文未检索到，未以其它仓库历史计划替代。按本次明确目标在队列落实可执行验收。
- 现有仿射入口不能表达四边为零的非零截面形状；新增P1矩形形状的离散通量归一化与平滑周期波形，复用既有整体求解、端点/stage映射和签名机制。
- 新诊断独立积分当前表面通量与体散度，分开stage预算、secant体积变化及后处理累计预算。无滑移通道用真实弹性顶壁和夹持边界，非预设运动。
- 使用 `scripts/cloud/restore.sh` 和 `scripts/cloud/run.sh` 编译；Debug/Release 新增1项、旧入口/压力2项均通过；三格式/1和2rank/恢复/Jv/9次真实缩步重放。六周期研究完成三网格和三步长，原始数据与局限见[验收](../research/data/fsi-flow-2026-11-03/README.md)。没有全量和3.19.6编译，也没有性能研究。
- 重要失败：空环境恢复；MPI root拒绝；LLVM OpenMP启动断言在串行重试仍复现，保留失败且不冒充正确非法参数拒绝；避开残留注册PID名字后完整复验通过，底层断言精确原因仍未回溯确认。Git push无凭据，使用GitHub API保存相同tree后同步本地。详细命令、失败尝试、解决范围见验收，不将环境规避写成数值修复。
- 本 agent 完成源码diff自审、26项CI选择器测试；无外部独立审查。知识稿 `website/drafts/fsi-periodic-flow-mass-budget.md` 保持草稿；长期架构未变，不改架构契约。
- 本地验收/证据/自审后仅创建 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33)。[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) Debug/Release各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。 增量证据job也成功；不需要代码修复。合并预览tree与本地/PR head完全相同，精简证据见 `delivery-ci.json`。PR #33 随后于 2026-11-03 合入 main，合并提交 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`；任务状态更新为 done。后续纯文档更新不重新运行未受影响的数值测试，保留并引用原 CI 来源。
- 同时核对前置 FSI-NEXT-01 已由 PR #32 合并为基线 `b2755b6`，纠正队列旧 in_progress，历史记录明确标注。

## 2026-10-31 / DOCS-01 — 全仓 Markdown 进度同步

- 用户要求审查全部 Markdown 并按当前进度更新；基线 `a508e3d`，在 `codex/markdown-progress-audit` 工作。本次只修改文档，未推送、合并或部署。
- 清点 88 份既有项目 Markdown，覆盖根入口、架构、研发/研究、Skill、环境、网站正式页面/草稿/模板；逐文件处理清单见 [审查记录](MARKDOWN_AUDIT_2026-10-31.md)。依赖包、构建产物与 Git 内部文件不属于项目文档。
- 根因：多个文档保留不同检查点的“当前”描述。同步 PR #24 已合并、G0/G5/G1 已交付、旧 PETSc 手动专项、Doxygen 实际输入和平台范围；明确 G2/G4 子集及历史 BE/测试计数。
- 按源码确认 checkpoint 容器仍 v3、二维分区 v3/三维 v2，并补充二维标量 LinearSolveFailure 的重试边界，未改数学模型。
- 用 eonsim-knowledge-capture 修订既有草稿和知识索引，补后续验收来源；没有新增数值/算法成果，不另造教学文章，不将草稿转为发布。
- 静态检查脚本首次把数据目录误判为网站页面、把首页 layout: home 判为缺标题；修正检查器的路径/页面分类后复查。旧研究中不可移植的 Windows 链接改为原工程相对路径与行号，保留来源提交。
- 实际执行 `python3 /tmp/eonsim_md_audit.py` 检查全文结构、本地链接/锚点和固定 Git 源码目标，`git diff --check` 检查空白；最终结果见审查记录。`command -v node` 未找到 Node，本次未执行网站构建或产物隔离检查。
- 未运行 CMake、编译、CTest、MPI、数值或性能实验；未访问外部文献链接或远程 PR Checks。PR #23 测试数字引用已归档证据，不是本次新结果。

## 2026-10-31 / G5 — generalized-alpha ALE与单体FSI

- 以25e0945为基线，独立alpha云端CI三环境成功。共同af、一阶流体/二阶运动学、各自算法历史接入单体残量和checkpoint；明确stage力/功率输出。
- 新增提交前端点几何检查，rank局部失效先allreduce再共同拒绝。
- 主锁Debug10项针对性CTest全部通过（324.63秒），rho=0/0.5/1的速度/压力/位移趋二阶，整体J差分约1.8e-9；1/2/4rank完整历史、事件重启、接口运动与功率通过。
- 首次极小步重试对照因时间戳相减及接口位移消减而算法网格加速度不一致；改为17位实际步长重放、接口直接共享stage速度，保持原容差后通过。
- ALE rho0.5粗步启动误差抵消，改用更细同问题网格时间步进入渐近区；未改阶数阈值。
- ALE补充实测stage有效/endpoint反转，坏单元rank分布3/1/2/0；缩步恢复与失败checkpoint哈希不变通过。FSI独立端点反转分支仅审查，未直接触发。
- 独立审查两轮无剩余源码阻塞项；更新知识草稿，未发布。证据alpha-coupled.json。继续G1，G5最终集成验收与整体主线交付仍待完成。

## 2026-10-31 / G5 — 独立场generalized-alpha

- BDF2耦合检查点`bab4fda`云端CI三环境成功（run41192856614）。
- 核对PETSc3.23.7 alpha1/alpha2版本源码、一阶原始预印本§3–4与压力评价论文。Chung1993出版社全文403，仅核实出版信息，不声称读过全文。
- 新时刻权重参数分别实现一阶流体与二阶结构；独立stage速度/压力、端点恢复、完整算法历史及rho checkpoint。接受一个BE启动步的策略明确不同于PETSc探测启动。
- 结构惯性q与位移beta*h/gamma分离；局部线弹性/Neo-Hookean方向导数通过。物理端点加速度由卸载模型一致质量方程恢复，算法加速度独立输出/保存。
- 独立审查发现stage残量与端点输出混用风险，已将流体字段命名stage_momentum_residual，结构保留stage字段但端点反力/残量使用质量恢复方程，日志标记evaluation_time。
- 主锁Debug7项针对性CTest全部通过，26.82秒CTest墙钟；包括rho=0/0.5/1的真实流体早期/终点速度与压力阶、结构位移/速度/物理加速度阶、rho=1启动后能量保持、阻尼、1/2/4rank、事件checkpoint、算法历史和真实拒绝。
- [alpha-standalone.json](../research/data/fem-integration-2026-10-31/alpha-standalone.json)保留实际源码/二进制、命令、退出码和结果。alpha ALE/FSI尚未接入并明确拒绝；G5不关闭，继续下一增量。

## 2026-10-31 / G5 — BDF2 ALE与单体FSI

- 独立场提交`c923387`的云端CI三环境成功（run41181938354）。
- FSI流体惯性、结构/刚体位置与加速度、ALE网格速度、reduced.slot位移试探列和lifting统一使用当前BDF2映射；各层历史只在共同接受后提交。
- ALE新增同分区checkpoint，保存当前与前一流体/网格状态及步长；重试重建trial几何不污染accepted。
- 独立审查指出测试遗漏压力MPI/重启与非均匀接口功率，已补齐。接口功率按全分量离散残量与共享速度内积计算，不声称总能量守恒。
- 主锁Debug6项针对性CTest全部通过，138.35秒CTest墙钟；包括3个新验收和旧motion/刚体FSI/弹性FSI回归。整体Jacobian差分相对误差约1.4e-9，MPI最多4rank。
- 弹性FSI压力阶1.86/1.97、刚体压力阶2.00/2.02，速度与网格位移趋近2；粗时间步压力未达门槛后保持物理问题和容差继续细化。ALE网格速度BE阶0.95/0.98、BDF2阶2.02/2.01，均匀/剪切流保持及重启通过。
- 高压超弹性真实拒绝压力测试：从两步accepted检查点限制Newton为2次，15次缩步后以原容差接受下一BDF2步，并与无拒绝相同轨迹一致。测试显式允许16次重试，只推进一个恢复步；不作为实用步长建议。原8次上限耗尽的结果不是生产回归；3次Newton上限没有触发拒绝，未拿它替代恢复证据。
- [bdf-coupled.json](../research/data/fem-integration-2026-10-31/bdf-coupled.json)保存实际源码/二进制/日志哈希、命令、退出码和数值结果。G5仍未关闭，继续generalized-alpha；G1未实施。

## 2026-10-31 / G5 — 独立流体和固体BDF2增量

- 从`e9e4d30`继续；该G0补强提交云端三环境CI成功（run41180022722）。
- 统一BE/BDF2导数映射、实际历史步长、比率上限2、事件后启动、两层accepted checkpoint；独立固体位移重建同步使用当前格式。
- 真实流体首次320步测试暴露累计舍入制造极短末步，时间控制器补偿求和修复，320/10000步oracle通过。
- 独立审查指出步长相关tau使时间加密同时改变空间离散；新增显式固定tau并保持旧BE默认。压力驱动实测速度/压力BDF2阶约2；不是Python参考替代生产验证。
- 固体粗步未进入渐近区，保持问题和门槛继续细化，位移/速度/加速度BDF2阶接近2。没有声称非线性材料阶数或BDF2逐步物理能量单调。
- 主锁Debug编译退出0；针对性CTest9项全部通过，42.23秒CTest墙钟。选择包含time_integration、fluid/solid_time_verification、fluid/solid_element_jacobian、time_retry_verification、restart_block_verification、fluid/solid_verification。
- 新测试覆盖变步长、1/2/4rank、事件处重启、最后短步、BDF2启动后的真实Newton拒绝与同轨迹对照；签名拒绝更换积分器/候选步计划。独立审查公式与状态无阻塞缺陷，建议的schedule签名已补齐。
- [证据清单](../research/data/fem-integration-2026-10-31/bdf-standalone.json)记录实际dirty源码哈希、基线SHA、二进制哈希、命令、退出码及结果；不是把新结果归给旧提交。新增知识草稿保持draft。
- G5未关闭，后续继续ALE/FSI及两类generalized-alpha，G1尚未实施；此处只记录可复现增量。

## 2026-10-31 / FEM-INTEGRATION — 从已合入的G0检查点接续

- fetch核实main为47b5bd46c992fcf64cf163361053ceb0091fa5a5，工作区起始干净，无开放PR；建立codex/fem-time-mesh。
- 读取主线CI作业日志，主锁Debug/Release各43项、旧锁Release 10项均成功；独立审查核对原g0.json的100份源码哈希全部匹配。
- 本轮明确追加授权WSL2开发验证、CI云端复验。两套仓库依赖锁成功恢复；主锁Debug编译与链接检查通过。首次MPI预检被沙箱socket策略拒绝，沙箱外同命令预检与完整43项通过。
- G0补强真实J/R跨rank置换、已知离散解与真实Newton右端检查，三recipe物理量及压力规范对照；独立审查发现辅助PREONLY失败分叉并修复为共同拒绝。
- 当前Release/兼容检查、受控性能、新提交CI尚待完成。整体任务继续，未将G5/G1标记完成。

## 2026-10-30 — ARCH-01 — 通用 FEM 架构与上游学习规划

- 用户要求审查 EONSim-new，并进一步规划多网格/空间、边界、非一致界面、DoF/预条件、时间格式与高性能执行；明确暂不开发、不编译。本轮遵守此范围。
- 独立本地 checkout 从旧审查基线同步 main 至 `38a5e516ffe129d1b70c7c1bd8365deb5ded101a`，确认 PR #21 已合并；建立 `docs/general-fem-architecture-plan`。未修改只读 sources/。
- 静态阅读当前拓扑、Gmsh、DoF、FSI、COO、VTU 及 L1/L2；确认 Tri3 只是 Tet4 边界、体域仅 Tet4，BE/共形接口仍为实现边界；现有独立流体 COO 与分片 VTU 不重复安排为全新功能。
- 新增 `docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md`：明确拓扑/几何/空间分离、一般 BC、K/W 与非匹配传递、三类 DoF/PC 排列、约束后图、两类 generalized-α 与变步长 BDF2、输出和 native 批次执行；提供 G0–G8 依赖和验收候选。
- 新增 `docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md`：访问官方文档和作者论文，覆盖用户列出的 20 组项目（Elmer 与 oomph-lib 分列）；给出具体迁移产物和不照搬部分，没有逐库源码全审或性能横评。
- 同步 L0/L1/L2、下一阶段设计、README、ROADMAP、进度与任务队列；纠正旧文档中持久 SNES/PC 的优先级，保留根据已有测量暂缓的决定。HPC-02 按 PR #21 标 done；所有新增实现任务 deferred，无新增 ready。
- 使用仓库 eonsim-knowledge-capture 技能，新增未发布草稿 `website/drafts/general-fem-dof-architecture.md` 与知识登记。证据为理论/设计和静态实现对应；lastVerifiedCommit 留空。非匹配稳定性、stage 相容性及 PC 语义为后续审阅重点。
- 文档检查：`git diff --check`；以 Python 标准库检查所有变更/新增文件仅为 Markdown、UTF-8、围栏闭合、相对文件/站点路径存在及新文件尾空白；通过。此为文档结构检查，未构建网站或声称渲染验证。
- 未运行 CMake、编译、CTest、MPI、求解器、性能实验、上游原型或网站发布。没有修改 src/include/tests/cases/scripts/CMake 等实现；历史数值与性能记录保持原有证据范围。
- 初次交付为本地文档草案，当时未创建 PR、未推送、未发布。下一步开发需用户另行启动；本轮不擅自领取候选。
- 用户后续明确要求将上述 16 份 Markdown 文档推送远程；交付目标为 origin 的 `docs/general-fem-architecture-plan` 分支，提交范围仍限这 16 份文档。保持不编译、不创建 PR、不合并 main、不发布网站；提交标识及交付结果以 Git 远程引用为准。

## 记录模板

~~~markdown
## YYYY-MM-DD — TASK-ID — 简短标题

- Branch / PR:
- Base commit:
- Objective:
- Changed files:
- Implementation:
- Commands executed:
- Tests and results:
- Performance evidence (if applicable):
- Knowledge draft:
- Limitations / unresolved issues:
- Next task:
~~~

## 2026-10-30 — HUB-01 — 持续研发与知识生产基础设施

- Branch / PR: feat/codex-continuous-development-workflow；[PR #3](https://github.com/saitoasukakawaii/EONSim-new/pull/3)。
- Objective: 为 EONSim 建立跨 Codex Task 的进度恢复、任务队列、会话记录和公开知识草稿模板。
- Changed files: CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、website/templates/ 下的文章模板、知识采集 Skill，以及 AGENTS.md 入口。
- Implementation: 定义状态语义、任务领取规则、SOLVER-01 下一任务边界和知识文章证据分级。
- Commands executed: 通过 GitHub 仓库接口创建/更新文档；未在 Codex Cloud 本机执行命令。
- Tests and results: GitHub Actions Website Build Check 在 PR #3 分支上成功；执行了依赖安装和 VitePress 生产构建。未运行 EONSim C++/PETSc/MPI 测试（本次未修改求解器）。
- Performance evidence: 无，本次未进行性能实验。
- Knowledge draft: 本次新增的是模板和工作流，不将其伪装成已验证的数值研究文章。
- Limitations / unresolved issues: 尚未实现自动从测试日志提取数据或自动发布；Codex 需按 Skill 和 AGENTS 规则执行草稿生成。
- Next task: SOLVER-01 PETSc NonlinearSession 生命周期审计。

## 2026-10-30 / SOLVER-01

- 基线：0828f41（PR #3 已合并）；分支 docs/solver-baseline-audit。
- 变更：新增 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md、website/drafts/petsc-object-lifetime.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG。
- 审计：读取 linear_system/nonlinear_system/schur_solver、PetscOwner 及 fluid/solid/fsi 调用链；主 Vec/Mat 跨步保留，SNES 每次 solve 创建；Context 为借用栈引用；计时不完整覆盖构造析构。结论为需要额外测量，SOLVER-02 保持阻塞。
- 实际验证：仓库根目录 `git diff --check` 通过；`git diff origin/main -- src include CMakeLists.txt CMakePresets.json` 为空；website 目录 `npm run docs:build` 成功；仓库根目录 `test ! -d website/.vitepress/dist/drafts` 成功。
- 数值测试/性能实验：未运行；本任务为静态审计，不能据此声明性能收益。
- 知识沉淀：有，已按 eonsim-knowledge-capture 形成草稿并登记；证据为源码分析，数值与性能仍待测量。
- 下一步：人工审核审计报告，再开展固定 transient case 的重复 profiling。

## 2026-10-30 / SOLVER-01B

- 基线 c1c7508，PR #4 已合并；分支 perf/nonlinear-setup-baseline。
- 新增 scripts/benchmark_nonlinear_setup.py、docs/research/NONLINEAR_SETUP_BASELINE_2026-10-30.md、data/nonlinear-setup-2026-10-30 的结果 JSON/原始日志及 website/drafts/nonlinear-setup-baseline.md；更新进度、队列与知识日志。
- 仓库根目录激活 /workspace/.eonsim-tools/activate.sh；`cmake --preset release -DBUILD_TESTING=ON -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" -DMPIEXEC_EXECUTABLE="$CONDA_PREFIX/bin/mpiexec" -DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS` 和 `cmake --build --preset release --parallel 4` 退出0。
- `python3 scripts/benchmark_nonlinear_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-nonlinear-baseline` 退出0：12个样本、2个预热、2个预处理成功；同rank输出差0。raw日志已入Git，不依赖临时目录恢复。
- `ctest --preset release -R '^(solver_failures|solver_failures_mpi|nonlinear_acceptance|nonlinear_acceptance_mpi)$' --output-on-failure`：4/4通过，耗时4.57秒；未运行全套。
- website目录 `npm run docs:build` 成功；草稿目录未进入dist。求解器及CMake未改。
- 知识沉淀：已生成测量边界草稿并登记。构造析构独立计时仍未完成，无持久化优化收益结论；SOLVER-02保持blocked。
- PR：https://github.com/saitoasukakawaii/EONSim-new/pull/7，等待人工审核。文档末尾空行已修正。

## 2026-10-30 / SOLVER-02

- 同步基线8c8a4af，PR #7已合并；分支perf/multistep-setup-profile。按最新队列将旧SOLVER-02“设计原型”表格描述统一为正文规定的测量任务。
- 新增scripts/profile_multistep_setup.py、docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md、data/multistep-setup-2026-10-30的JSON及16份原始日志、website/drafts/multistep-setup-profile.md；更新进度/队列/知识日志。
- 仓库根目录激活已有环境后 `cmake --build --preset release --parallel 4` 退出0（no work to do，求解器相对前一基线无变更）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-solver02` 退出0：fluid与elastic、1/2rank、各3次，共120接受步，同rank重复输出差0。
- 对实际日志的解析检查：有效10步通过；删除一条报告、负SNES reason、NaN三个错误输入均被拒绝。website目录 `npm run docs:build` 通过；草稿未进入dist。未运行全套CTest，未改求解器/容差。
- 使用eonsim-knowledge-capture流程形成测量草稿；原始证据入Git。结论为暂缓持久化原型，首步成本不可外推后续；独立构造析构成本仍未知。
- 下一步：人工审核；未来只有业务需求或更大规模测量支持时重新打开优化任务。

## 2026-10-30 / SOLVER-05

- 同步 origin/main 至 a48de95，确认 PR #8 已合并；分支 fix/linear-solve-ksp-lifetime。SOLVER-02 标记 done。
- 修改 src/algebra/linear_system.cpp、include/eonsim/linear_system.hpp，将 KSP owner 从成员移到单次 solve 作用域；新增 tests/verify_linear_lifetime.cpp 和两项 CTest 注册。代码提交 c47f00d。
- 更新进度、队列、本日志、KNOWLEDGE_LOG；使用 eonsim-knowledge-capture 生成 website/drafts/linear-solve-ksp-lifetime.md，记录理论、实现、数值/生命周期验证及性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target verify_linear_lifetime --parallel 4` 成功。旧实现 `ctest --preset release -R '^linear_lifetime$' --output-on-failure` 预期失败，提示 solve 返回后 PC 未释放。
- 修复后 `cmake --build --preset release --target eonsim verify_linear_lifetime --parallel 4` 成功；`ctest --preset release -R '^(linear_lifetime|linear_lifetime_mpi|poisson_verification|poisson_parallel)$' --output-on-failure` 4/4 通过（14.05 秒）。
- `cmake --build --preset debug --target verify_linear_lifetime --parallel 4` 成功；`ctest --preset debug -R '^linear_lifetime(_mpi)?$' --output-on-failure` 2/2 通过。每 rank 四次 PC 创建/销毁，覆盖成功、失败、恢复和 owned/ghost 解。
- 未运行全套 CTest；未测量内存字节数、耗时收益或大规模并行。下一步人工审核本修复；持久化优化保持延期。
- 文档验证：`git diff --check`、五份 Markdown 的解析/围栏配对检查通过；`npm run docs:build --prefix website` 成功；`test ! -d website/.vitepress/dist/drafts` 成功，草稿未进入生产构建。
- Markdown 检查最初直接导入 markdown-it 失败（非顶层依赖）；改用已安装 VitePress 的 createMarkdownRenderer 后五份文件解析及围栏检查通过，无新增依赖。

## 2026-10-30 / SOLVER-03

- `git fetch origin` 同步 main 至 717b25b；`gh pr view 9 --json state,mergedAt,url` 确认已合并；SOLVER-05 标记 done。新分支 docs/newton-scaling-spec。
- 领取原队列 SOLVER-03 的审查/规格任务；审查 FieldAcceptance、Context、convergence、NonlinearSystem::solve、Schur 配置和非线性验收测试。现有字段尺度仅用于验收，未实现完整 Newton 坐标变换。
- 新增 docs/research/NEWTON_SCALING_SPEC_2026-10-30.md、scripts/verify_newton_scaling.py、website/drafts/newton-scaling.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志及 KNOWLEDGE_LOG。
- `python3 scripts/verify_newton_scaling.py` 通过：两组尺度，Newton/Jv、非零约束、试探点/加权 merit、逆预条件作用和 Schur 恒等式；两个错误公式负对照均被识别。规格/脚本提交 6dc2baf。
- 使用 eonsim-knowledge-capture 形成算法草稿，明确当前实现、候选理论、独立验证及性能证据缺失。未修改 C++、CMake、case 或容差；未运行 C++ 构建/CTest、MPI 或性能实验。
- SOLVER-03 标记 review，新增 deferred 的 SOLVER-03B 并列明实现验收条件与触发需求；不将候选规格描述为已实现能力。
- `python3 -O scripts/verify_newton_scaling.py` 同样通过；`git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿目录未进入 dist。核对 src/include/CMake/cases 相对 origin/main 无差异。
- 相对链接检查最初误将既有 `/learning/cfd` 网站路由视为本地文件；限定为相对文件链接后通过，未修改已有网站路由。

## 2026-10-30 / SOLVER-04

- `git fetch origin` 同步至 a4957e0；`gh pr view 10 --json state,mergedAt,url` 确认合并，SOLVER-03 标记 done。分支 perf/schur-mesh-profile。
- 新增 scripts/profile_schur_mesh.py（79eb826）、docs/research/SCHUR_MESH_PROFILE_2026-10-30.md、data/schur-mesh-2026-10-30 的 38 个证据文件、website/drafts/schur-mesh-profile.md；更新进度/队列/会话/知识日志。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-schur-mesh` 退出 0：2/4/6 subdivisions、1/2 rank、6 个直接参考及 18 个 Schur 重复；最大字段差 4.0834e-12。
- 对实际日志解析的有效输入、缺报告/NaN/负 SNES reason 三种变异，以及节点集合/非有限值/超阈值差三个负对照检查均通过。
- 版本采集中的非提升权限 mpiexec --version 输出 pmix socket 警告但返回版本；实际 MPI 测量在允许本地通信的执行权限下全部成功。
- 使用 eonsim-knowledge-capture 形成 benchmark 草稿；完整计时范围与限制见报告。未修改求解器、CMake、既有案例或容差；未运行全套 CTest、FSI 或跨节点测试。下一步人工审核；大网格/粗层进一步测量需明确需求。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / SOLVER-04B

- `git fetch origin` 同步至 f1e9594；`gh pr view 11 --json state,mergedAt,url` 确认已合并。SOLVER-04 标记 done，新分支 feat/solver-level-dimensions。
- 修改 src/algebra/nonlinear_system.cpp，使用 KSPGetOperatorsSet 后读取已有 A 的全局/本地行列；修改 tests/verify_schur.py 验证各层尺寸及顶层分布总行数；更新 L2 离散诊断契约。实现提交 124bed3。
- 更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG；按 eonsim-knowledge-capture 生成 website/drafts/solver-level-dimensions.md，区分元数据理论、实现、数值验证与性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh` 后，`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（36.97 秒）。Schur 含四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.36 秒），包含初态收敛和故障路径。
- 未跑全套 CTest、性能基准；不宣称诊断零开销。尚无 P 尺寸/逐层非零元或累计成本；未设置 A 的哨兵分支未单独构造测试。下一步人工审核，本次不调参。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。CMake 和 case 未更改。

## 2026-10-30 / HPC-01A

- 同步 origin/main 至 615af36，确认 PR #12 已合并，SOLVER-04B 标记 done；分支 feat/assembly-phase-timers。
- 修改 src/algebra/nonlinear_system.cpp：累计正常完成评价的 callback/failure_sync/assembly_finalize/constraint 时间；在 SNESSolve 后冻结，沿用原有报告规约。修改 tests/verify_schur.py 检查有限非负及外层时间界；更新 L2 计时契约。实现提交 fff4895。
- 更新进度/队列/本日志/知识登记；按 eonsim-knowledge-capture 生成 website/drafts/assembly-phase-timers.md。HPC-01A 是有界实现增量，HPC-01 的纯 kernel/插入分离与重复测量仍未完成。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（37.19 秒），含 Schur 四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.28 秒）。
- 未修改物理方程/容差/CMake/案例；未跑全套 CTest 或性能实验；新增时钟读取开销未知。失败评价的细分成本未纳入，详见契约。下一步人工审核，不能将计时接线报告为完整瓶颈结论。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。

## 2026-10-30 / HPC-01B

- 同步 origin/main 至 7f2bc51，`gh pr view 13 --json state,mergedAt,url` 确认合并；HPC-01A 标记 done；分支 perf/assembly-phase-baseline。
- 修改 scripts/profile_schur_mesh.py，新增四阶段及 assembly/ghost 汇总、缺字段/阶段越界/拒绝计数检查；脚本提交 d1708e1。
- 新增 docs/research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md、data/assembly-phase-2026-10-30 的 32 个日志/JSON 文件、website/drafts/assembly-phase-baseline.md；更新进度、队列、会话与知识日志。按 eonsim-knowledge-capture 整理证据边界。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-assembly-baseline` 退出 0：6 个直接参考、18 个 Schur 样本，无拒绝评价；最大节点字段差 4.0834e-12。
- 有效日志解析及缺 callback/NaN/阶段越界/非零 domain_rejections 四个负对照均通过。本轮未修改 src/include/CMake/cases，未跑全套 CTest 或时钟开销 A/B。
- n=6 callback 中位数由单 rank 25.487 ms 降至双 rank 13.779 ms，最终装配由 0.138 ms 增至 9.609 ms；不把最终装配全解释为网络时间。完整设置与范围见报告。下一步人工审核，HPC-01 未完成的分离与规模测量仍延期。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；已核对 src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / HPC-01C

- 同步 main 至28c60da，PR #16已合并。用户在上一轮提出 transient fluid/FSI 1/2/4 rank 候选后要求继续，本轮执行该有界任务；分支perf/transient-assembly-profile。
- 修改scripts/profile_multistep_setup.py：新阶段校验/统计、1/2/4 rank参数、主输出按owner/原始节点ID跨rank对照、独立固体输出检查及逐步/逐次分布。新增研究报告、26份日志/JSON证据、知识草稿；更新进度/队列/本日志/知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-transient-phases --ranks 1 2 4` 成功：18次运行、180接受步，主输出跨rank最大差6.6614e-16，同rank重复差5.5512e-16。
- 运行启动版本82081d5；确认FSI单独输出固体场后，用0f90585的verify_solid_outputs对全部已生成输出补验，最大跨rank差2.4287e-17。f92e57b的detailed_statistics补充18个逐次和60个逐步统计。无需重新运行物理求解；版本来源分别记录在JSON。
- 有效日志与缺phase/NaN/非零拒绝计数/超外层时间四个负对照通过。采用eonsim-knowledge-capture整理草稿，保留统计与计时边界。未修改C++/CMake/案例，未跑全套CTest；未测量时钟开销。
- 下一步人工审核，性能结论为暂缓重构，必要时按目标规模补更细事件；没有擅自激活其他deferred任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。

## 2026-10-30 / HPC-01D

- 同步origin/main至2e7e9a9，PR #17已合并，HPC-01C标记done。用户在上一轮提出独立流体kernel/插入分离建议后要求继续，本轮执行该有界任务，分支feat/fluid-element-timers。
- 修改src/physics/fluid.cpp，新增显式-fluid_element_report开关、单元kernel/Vec+Mat插入时间、逐rank/逐步单元计数；关闭时无单元时钟读取。新增tests/verify_fluid_element_report.py及CMake注册，更新README和L2契约。实现提交1722265。
- 新增website/drafts/fluid-element-timing.md；按eonsim-knowledge-capture区分理论/代码/验证与性能证据缺失；更新进度、队列、会话和知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4`及Debug同命令成功。
- `ctest --preset release -R '^fluid_element_report$' --output-on-failure` 1/1通过（21.34秒）；Debug同测试1/1通过（22.73秒）。每个构建覆盖三案例、1/2 rank、开关共12次求解；主物理字段/动量残量保持、计时有限非负、报告和单元计数有效。
- 本轮不跑全套CTest或性能基准；未修改方程、容差或PC策略。计时包含最终验收/原始反力回调，不可与callback_seconds直接相减；整个失败solve不输出，拒绝评价的专门计时路径未新增测试。FSI/ALE与owned/remote插入仍未分离。
- 下一步人工审核，无新增ready任务；如继续测量需明确目标规模并考虑计时扰动。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；README新增选项说明及契约链接已核对。

## 2026-10-30 / HPC-01E

- 同步main至f232b07，PR #18已合并；HPC-01D标记done。用户在上一轮提出计时开关扰动测量后要求继续，本轮执行该候选；分支perf/fluid-element-overhead。
- 新增scripts/benchmark_fluid_element_report.py（1423b99）：每配置预热两模式，5对交替顺序，固定solver_report，仅切换fluid_element_report；检查字段、逐步迭代轨迹、单元计数及报告完整性。
- 新增研究报告、data/fluid-element-overhead-2026-10-30的41份日志/JSON、website/drafts/fluid-element-overhead.md；更新进度/队列/会话/知识登记。使用eonsim-knowledge-capture标注证据及局限。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/benchmark_fluid_element_report.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-element-overhead --repeats 5` 成功：1/2/4 rank，共30个计量样本/15对，另6次预热。最终字段同rank差3.3307e-16、跨rank差4.4409e-16，逐步迭代轨迹及计数一致。
- 有效报告及缺报告、重复报告、NaN、错误单元计数、关闭模式出现报告五个负对照通过。
- 单rank配对solve变化中位数+3.56%，范围-0.10%至+27.68%；2/4rank范围跨零。详细耗时/统计口径见报告；不将负值称为加速，不作纯时钟成本归因。
- 未修改C++/CMake/案例，未跑全套CTest；仅小规模独立流体，完整HPC-01未完成。下一步人工审核，无新增ready任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。


## 2026-10-30 / QA-01

- 同步origin/main至25e49af，PR #19已合并；HPC-01E标记done。用户继续上一轮日志校验候选，分支fix/profile-log-validation。
- 实现7b91030修改scripts/profile_multistep_setup.py、scripts/profile_schur_mesh.py，新增tests/test_profile_validation.py与CMake注册。原因/计数严格整数校验、计时和残量有限非负、报告/步顺序配对、稳态必需统计字段及逐rank根节点/重复层级校验。
- 修复前负对照发现NaN原因、非法迭代计数及缺失根节点等误接受；修复后 `python3 tests/test_profile_validation.py` 与 `python3 -O tests/test_profile_validation.py` 均11项通过。真实数据覆盖18份瞬态、18份稳态、36份开关测量/预热日志，共72份。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4` 与Debug同命令均成功；CMake重新生成，C++无需重编译。
- `ctest --preset release -R '^profile_log_validation$' --output-on-failure` 与Debug同命令均1/1通过（各0.09秒）。未执行全套CTest或新MPI/性能实验，测试读取已提交证据，不重新证明数值正确性。
- 更新进度/队列/本日志/知识登记；使用eonsim-knowledge-capture新增website/drafts/profile-log-validation.md，区分浮点语义、实际实现、解析器验证与性能未测量。
- 待人工审核；无新增ready任务。此解析协议限于现有固定十步、零拒绝评价的测量，不作为任意PETSc运行的通用成功判据。
- `git diff --check`、五份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功（3.37秒），dist未包含草稿或模板；未修改src/include/cases。

## 2026-10-30 / HPC-02

- 用户要求依据规划设计并完成预计 5 小时以上任务，然后创建 PR。核对指定 EONSim-new 与旧 EONSim 是不同仓库，在独立 checkout 从 `24eae62`（PR #20）建立 `codex/fluid-cached-coo`；旧工作区及未提交修改未改动。
- 任务队列登记 7–9 小时工程工作量估计及具体验收；实现 `ceea57d` 增加独立固定网格流体 `-fluid_coo`，一次准备图、复用数值缓冲，在错误同步后调用 collective COO 更新。默认装配、物理公式、停止条件、残量/反力与 FSI 路径保留。
- WSL Ubuntu24.04/GCC13.3/PETSc3.19.6/OpenMPI4.1.6 下 Release 和 Debug 完整构建成功。新增 COO 代数测试 1/2/4 rank 通过；真实流体每构建 87 个命令，最大字段差 5.190625707029994e-12。
- Debug 6/6 通过；Release 首轮 7/8 通过，`solver_failures_mpi` 60 秒超时在独立未修改基线构建中相同复现。共享求解器的 Schur/FSI、真实缩步、计时及日志回归额外 4/4 通过。不宣称整个 CTest 通过。
- `benchmark_fluid_coo.py` 完成两档网格、1/2/4 rank、36 次计量及12次预热；所有18对迭代轨迹一致，字段最大差 6.661338147750939e-16。装配中位变化约 -45% 至 -62%，solve 约 -8% 至 -44%，wall 约 -11% 至 0%；多组 wall 范围跨零，明确记录准备和内存成本。
- 原始测量使用 `ceea57d`；后续仅修正跨 Windows/WSL Git status 的 CRLF 元数据噪声。58 个编译源文件归一化哈希与提交相符，可执行哈希与测量一致；原始 JSON 未改写。
- 独立 deep review 对 `ceea57d` 为 PASS，无阻塞发现。报告、原始日志、字段证据、审查记录及 source provenance 已归档；按 eonsim-knowledge-capture 添加 website/drafts/fluid-coo-assembly.md 并登记知识日志，未发布网站。
- 代码、验证、性能测量和评审完成后创建 [PR #21](https://github.com/saitoasukakawaii/EONSim-new/pull/21)，人工决定是否合并；无新增 ready 任务。创建后的提交仅登记 PR 链接与 review 状态。此任务不提供 FSI/ALE/残量 COO、GPU、多节点或大规模扩展证明。
- 交付前代码/文档的 `git diff --check`（排除原样归档的日志）、8 份 Markdown 围栏/相对文件及站点路由链接检查、JSON 证据解析、测量脚本语法检查通过。两份构建日志保留 CMake 原始输出中 8 行尾空白，完整 diff 检查因此会报告这些空白；不改写原始证据。后续文档/元数据修改未改变已审查的 src/include/CMake/tests；未重复运行数值测试，未构建或发布网站。


## 2026-10-30 / INFRA-01

- 用户明确授权14–18小时估计工程量的云端基础设施任务；未将估计写实际耗时。仅远程Linux，main基线38a5e51，PR #21已核实合并，纠正HPC-02状态。独立分支codex/infra-reproducible-mpi-ci。
- 读取根AGENTS/L0、工程总纲/路线/构建/进度队列、并行/状态/求解契约及两份历史报告。用户指定architecture下L0路径不存在，实际入口在根目录。
- 新增environments两份SHA256显式锁及版本说明，scripts/cloud恢复/运行/证据入口、核心GitHub Actions、runtime探针；复用presets/provider和34项原测试（新增后35项），添加选择/rank标签。
- src/algebra/nonlinear_system.cpp修复旧PREONLY局部PC失败，在诊断前统一布尔失败标志，保留负枚举原因；本地失败树不额外collective。已共同传播的fatal callback早退后更换trial Vec，隔离PETSc残留读锁，COO图/矩阵保持。
- tests/verify_solver_failures.cpp覆盖三个诊断模式、fatal Jacobian、accepted不变及恢复；tests/verify_checkpoint.cpp补破坏指针前读者同步；tests/verify_runtime.cpp验证real/double/int32及实际MPI运行。
- 未改main隔离构建在PETSc3.19.6下原60秒超时（60.07秒），最小纯PETSc复现rank0 reason4、rank1 reason-11；上游3.20.0已加入归约。保留最小复现源码，详细归因见INFRA-01报告。
- 最终锁在/tmp/infra-pristine恢复；随后在/tmp/eonsim-cold-I3bOY2显式隔离所有包缓存、独立检出c07f94a，完成干净恢复/构建/7项故障回归，再重复restore与7项测试通过；云机4CPU/32GiB。旧hwloc CPUID启动问题及容器CMA限制分别适配，不混同应用死锁。
- 两套环境mpi-failure各7/7通过；主环境Debug全35/35通过474.17秒、Release全35/35通过409.08秒。d3f69d1分支CI三任务全部成功（41060786421），均上传诊断产物。最终入口/文档提交仍须head CI通过，尚无正式PR。
- 首轮主环境全套暴露COO Vec锁与checkpoint竞态并修复；CI四rank失败进一步定位OpenMPI5忽略旧映射变量，模拟两槽位前后验证后加入PRRTE设置及四rank预检。
- 独立审查指出负PC枚举、嵌套cgroup和超时残留，均修正并复核无源码阻塞；真实MPI超时清理与多层后代终止/reap通过。数值Python优化明确禁用。
- 使用eonsim-knowledge-capture新增未发布草稿，更新README/L2契约/BUILD_AND_VALIDATION/进度队列/知识登记。Markdown八文件解析及链接、网站构建3.94秒、草稿排除检查通过。精简机器证据见INFRA-01报告旁data目录；正式PR状态待验收后更新。


## 2026-10-30 / BRANCH-01 — 已合并分支清理与主线整合

- 用户明确授权删除已完全合并的 18 个远程分支，并审查剩余 6 个、优先架构与 CI、合入 main；明确禁止编译。以 38a5e51 为起点，在 integration/review-branches-2026-10-30 逐次整合。
- 18 个 tip 均为原 main 祖先，保存 SHA 后按精确旧值保护原子删除，复核只剩 main 与 6 个待整合分支；没有删除未审查引用或强制改写 main。
- 架构 16 份文档完整保留。CI 审查到 d3f69d1 后，推送前发现远程新增 c07f94a/5745fd3，继续审查并保留环境恢复与证据增量。其余旧分支按整合报告保留有效补充、维护主线状态，不复活过时任务。
- 新修正：锁定 ABI 的 runtime 探针改为云端显式启用；JUnit 解析按名称严格匹配并识别 error；文档检查支持 source-only 与 CRLF；网站 CI 增加模板哨兵；修正文档与真实 CMake target 的不一致。
- 工作目录为 EONSim-new checkout。执行 python -B tests/test_cloud_evidence.py（6 项通过）、node website/scripts/check-content.mjs --source-only（10 文件通过）、Python AST、bash -n、YAML/JSON/锁结构检查、Markdown 围栏和本地链接检查、git diff --check 及祖先关系核验。
- 本轮没有 CMake 配置/编译、CTest、MPI、数值/性能或网站构建；没有启动 GitHub 数值 CI。读取的历史成功状态只对应原分支 d3f69d1。最终推送含 [skip ci]，不把已有证据当作最终集成通过。
- 使用 eonsim-knowledge-capture 更新原 INFRA-01 草稿和知识登记，分开原分支执行记录与本次脚本验证；没有新性能证据，草稿未发布。
- 完整源提交、删除清单、冲突取舍和验证边界见 BRANCH_INTEGRATION_2026-10-30.md。INFRA-01 最终集成验收待执行，G0–G8 均 deferred；不自动开始新开发或构建。

- 推送前又检测到源 CI 分支新增 1497137/787372e：保留 PR #22 与 5745fd3 成功 CI 的证据、以及 ob1 单机传输适配。只读 GitHub 确认 CI 41063030121 三个 job 成功；核对 OpenMPI 官方 sm/vader 命名并检查脚本语法，未执行 MPI。最终整合范围以 branches.json 中的六个 tip 为准，INFRA-01 保留最终集成验收待完成。

- 第一次推送前置检查发现 main 已并发合入 PR #22（281699c2e86eb4eb0f9d0db7ca1bc891892c90dd），因此未执行推送；复核其唯一新增提交为已审查 CI tip 的 merge commit，纳入主线历史后树内容不变。继续采用正常快进推送与 [skip ci]，未覆盖并发提交。


## 2026-10-30 / FEM-G0A — DoF 与 FSI 分块详细设计（本地 review）

- 用户授权预计 10 小时工程量的有界设计/参考验证任务；预算不作实际耗时。开始 fetch origin/main 后 HEAD 与远程均为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，工作区干净；GitHub 开放 PR 查询为空。新建本地分支 `docs/fem-g0a-dof-design`，队列单独登记 in_progress。
- 阅读当前 AGENTS/L0、进度/队列/分支整合、通用 FEM 规划、L1/L2 离散/FSI/状态/并行、INFRA-01/HPC-02 证据边界；逐项审计 DoF/constraint/fields/嵌套 Schur、checkpoint/输出和既有测试源码，未执行既有数值检查。
- 新增 [专题设计](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)，固定提交源码映射、六项契约、三种配置/14 行示例、父编号公式、PETSc 3.19.6/3.23.7 官方 tag 静态核对、容量复杂度与 C++ 切片。总纲只加链接和 G0A 范围说明。
- 新增 docs/research/fem_g0a/ 下参考模型、unittest 与只读文档/语法检查器。模型没有求解器/进程调用，全部标准库；Fraction 手算 oracle 含非对称矩阵、非零 lifting、K/W 不同、置换与 dt 更新，另覆盖三树/刚体/1/2/4 模拟分区/空 local block/错误编号。
- 实际执行 `python3 -B docs/research/fem_g0a/test_reference_model.py`：首轮 18/18；交叉审查新增真实语义 alias 键、三层子矩阵元素 oracle 和单孩子拒绝后，最终 20/20 通过。原始输出及源码哈希见 [证据目录](../research/data/fem-g0a-2026-10-30)。这是分区索引逻辑验证，不能称 MPI 测试。
- 同一作者交叉核对源码/契约/手算/反例，修正普通保留行 Dirichlet 与 FSI 消元的区别、结构内部 BE 系数避免双乘、joined ID 和含 rank 的 fingerprint、checkpoint 缺失 reduced 排列版本、旧 PETSc prefix 长度与 Schur 内部 KSP 的接线范围；不冒称独立多人审查。
- 官方源码直接临时下载超时，改用浏览工具读取版本 tag 源码；未安装依赖。`check_artifacts.py` 首次把既有站点路由误当文件路径，补上源码路由解析后通过；没有修改旧文章链接来规避检查。
- 实际执行 `python3 -B docs/research/fem_g0a/check_artifacts.py`（Python AST、7 份 Markdown 围栏/本地文件与站点路由、固定 EONSim SHA/路径/行号、14 份审计源码哈希）、`git diff --check`，并检查新文件空白和生产路径零差异。最终输出见 [checks.txt](../research/data/fem-g0a-2026-10-30/checks.txt)。检查不证明远程链接存活或网站渲染。
- 使用 eonsim-knowledge-capture 的 algorithm-note 模板新增 [未发布草稿](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)，登记 KNOWLEDGE_LOG；分开理论、基线实现、独立参考验证与性能未测量。值得沉淀的知识是 K/W 区别、共享代表唯一归属与父编号空间，待人工审查。
- 未执行配置/编译器/编译、CTest、MPI、EONSim、性能基准或网站构建；未修改生产 C++、CMake、既有数值测试/算例、CI 或 sources/；未 commit、push、创建 PR、合并或发布。FEM-G0A 转 review（本地交付），FEM-G0 整体和其它阶段仍 deferred，INFRA-01 review 与其真实数值验收状态不变。
- 未解决事项为人工审查、真实 PETSc/MPI 接入及物理验收；下一最小候选 G0-B1 仅将现有语义适配到 IS、保持 root 编号与默认行为，未启动。

## 2026-10-31 / FEM-G0A — 后续提交推送授权

- 用户明确要求将改动推送到远程；提交目标为 `docs/fem-g0a-dof-design`，保持 FEM-G0A review、FEM-G0 deferred 和 INFRA-01 原验收状态。
- 提交前 fetch 确认 origin/main 仍为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，远程目标分支尚不存在；工作区仅含此前 FEM-G0A 交付文件。
- 核对两个工作流：数值工作流 push 仅匹配 main/codex/**，网站工作流 push 仅匹配 main，均不匹配本设计分支；提交另加 `[skip ci]`。不创建 PR、不合并、不运行或重跑构建。
- 更新当前状态中的“本地未提交”说明，保留 2026-10-30 的基线、检查证据与会话历史；不改变参考模型、生产代码或知识草稿的未发布状态。


## 2026-10-31 / BRANCH-02 — 合并 G0A 与清理远程分支

- 用户明确授权合并远程分支并清理多余分支。基线 f44c3e0；6 个历史分支已完全合并，新增 docs/fem-g0a-dof-design 的 b674d5a 多 1 个提交；远程无开放 PR。
- 在 integration/merge-cleanup-2026-10-31 审查合入 G0A 设计、标准库参考模型与历史证据，重跑 20 项参考测试通过；源码、CMake、数值测试、算例和 CI 未变化。
- 检查工具首次执行因 GBK 解码 UTF-8 失败，启用 UTF-8 后发现 14 份源码仅因 CRLF 检出被误判修改。显式 UTF-8 读取并仅归一化 CRLF 后全部基线哈希匹配；代码及其他空白变化的负例仍被识别。没有改写审计源码或旧证据。
- 更新 G0A 的设计交付状态和本轮合并清理清单；G0 生产实现及 G0B/G5/G1 未执行，INFRA-01 最终集成验收仍 review。此次是维护已有知识成果，不新增重复知识文章，原草稿未发布。
- 实际检查：20 项参考测试、AST/Markdown/固定源码引用/14 份哈希、LF/CRLF 与修改负例、Git 差异和祖先关系；结果见 BRANCH_CLEANUP_2026-10-31.md 与对应 checks.txt。
- 远程更新采用原子正常快进 main 加 7 个精确 SHA 保护的分支删除；推送前再次核对各 tip，保留 main 与完整可追溯历史。提交使用 [skip ci]，本轮未配置或编译项目、未运行 CTest/MPI/性能/网站构建。

## 2026-10-31 / FEM-INTEGRATION — 基线恢复与G0检查点

- 用户已明确解除纯设计限制，授权G0B→G0→G5→G1整体实现/测试/推送及按规则主线交付。main复核为72a3356，无开放PR；分支codex/fem-g0-g5-g1。旧快照未提交G0A工作已stash与归档保护。
- 在4CPU/32GiB云环境复用锁恢复3.23.7与3.19.6；移走引用失效临时路径的旧构建目录，从空产物重建。基线主环境35/35各模式、兼容7/7通过。
- 实际修改：DoF语义头、field/reduced布局、显式slot K/W映射、PC树与SNES接入、配置/CMake；新增pc_plan及pc_restart测试，复用schur/time_retry脚本；文档/队列/知识草稿同步。没有G5/G1能力。
- 当前G0主环境 `scripts/cloud/run.sh 3.23.7 {debug,release} all /workspace/eonsim-cloud` 分别43/43通过；兼容mpi-failure 10/10及三recipe/重启7项通过。最后补验状态见实施记录。精简结果、来源清单和原始日志位置见FEM_INTEGRATION_VALIDATION.md。
- quantity首次失败定位为原始压力块AMG粗层问题，固定使用Jacobi后通过；没有改变物理方程、精度门槛或超时。独立审查指出并修正rank局部输入错误、子KSP数组生命周期、Schur命名options漏检、零初态配置绕过与PC负例假通过条件。
- 权限：仓库API报告push可用，main保护规则读取403（integration缺少该端点权限）；尚未尝试合并或绕过规则。正式PR等待全部阶段完成。
- 下一步：保存并推送经验证G0检查点，检查CI，随后统一时间映射/accepted历史，从BE迁移进入G5。预计工程量不是实际耗时。

- 接续验证：主锁Release完整43项通过；旧锁三recipe补验3项通过。主锁Debug及旧锁Release新增奇异诊断失败/恢复10项均通过。性能两算例/1、2、4rank/四模式/三重复共72样本，最大场差3.307e-12，直接解在此小问题中solve中位数较低。证据入g0-supplement.json及pc-recipes-benchmark.json。
- 使用知识采集Skill生成真实装配置换与PC验收草稿并登记；尚未发布。当前准备提交推送检查点并进行新提交云端CI，之后进入G5。

## 2026-10-31 / FEM-INTEGRATION — G5与G1最终集成

- 用户明确授权WSL2真实构建/MPI，并由云端CI复验；继续使用两套Linux显式依赖锁、原presets与恢复入口，没有另建构建系统。实际资源24逻辑CPU、约32GiB，编译并发4、每rank数学库单线程。
- G5依次推送c923387（独立BDF2）、bab4fda（ALE/FSI BDF2）、25e0945（独立一阶/二阶alpha）、2fcd2fd（共同stage ALE/FSI alpha）；四个检查点云端三环境CI均成功。局部/整体切线、速度/压力/结构与网格时间阶、能量/阻尼、接口运动与功、事件/拒绝/完整历史重启见阶段JSON，不能将BE启动或参考ODE单独当作FSI精度证据。
- G1增加独立规范化导入层、Gmsh4.1 ASCII子集、Tri3/P1与Quad4/Q1相容混合二维标量Poisson/扩散；贯通命名材料和D/N/Robin、纯Neumann、METIS/owned/ghost/AIJ、G5时间与checkpoint、VTU/PVTU/PVD。二维分区版本3，三维保留版本2及旧Tet4读取。
- 独立审查发现并修复导入partition tags静默丢弃、名称维数检查、线性PC局部失败集体传播、不连通域零空间和restart输出时间片覆盖。新布局配置独立声明固定语义/存储策略；不把PC树变化或诊断MatPermute称为生产排列。
- 数值检查包括独立解析Q1质量/刚度、角点反转、外部编号/方向、三拓扑patch/MMS/畸变/边界法向通量、双材料、纯Neumann、空间与时间加密、1/2/4rank重启和真实失败恢复。对称矩阵成对计算消除极小步长舍入导致的假非对称；未降低rank、放宽容差或延长失败超时。
- 配置补充前主锁Debug/Release各59项及兼容13项通过；这份中间证据保留于build/pre-layout-policy-evidence。配置补充后的最终清单为主锁各60项、兼容13项，运行结束结果与源码哈希归档fem-final.json；不将中间结果冒充最终通过。
- 使用eonsim-knowledge-capture生成二维规范化/双线性单元草稿并登记，所有文章仍在website/drafts。当前环境没有node，本地网站命令未运行成功；网站构建及草稿隔离交由PR云端检查。Markdown本地链接检查通过。
- 最终主线与PR状态以后续交付记录为准；G2/G4仅实施必要子集，其余阶段不关闭。未测二维性能，也未把G0原检查点72样本性能结果归到新源码。

- 最终配置补充后Debug60/60、Release60/60、兼容13/13全通过；CTest墙钟574.87/213.11/18.50秒。fem-final.json保存109份源码哈希和实际清单，独立审查无确定源码阻塞；准备最终G1提交、PR及云端验证。


## 2026-10-31 / FEM-INTEGRATION — 主线交付完成

- 最终提交9e5a1ed经独立复核：109/109源码哈希一致，实际inventory/JUnit为60/60/13，所有命令退出0，无超时/失败/跳过，日志及二进制哈希匹配。
- PR #23云端三环境同样60/60/13通过（41199182613），push CI成功（41199162462），网站及草稿隔离成功（41199182529）。云端4CPU约16GiB，未混同WSL2资源。PR合并预览300a7544与功能提交tree一致。
- GitHub按expected_head_sha=9e5a1ed正常merge成功，main为9cc2e102e8e32f929de1c9a790c1ae527b931fa2。未绕过检查、未强推、未覆盖他人修改。
- 完成状态、队列、用户指南和交付JSON归档；G0B/G0/G5/G1及INFRA-01关闭，G2/G4只含必要子集，其余阶段保持deferred。知识文章仍为草稿。
- 完成状态归档为文档变更；生产源码及测试保持已验收版本，最终远程同步与main CI由交付时再次核对。

## 2026-10-31 / CI-DEPENDENCY-POLICY — 主力 PETSc 与按需兼容验证

- 按用户要求，将 PETSc 3.23.7 确定为日常主力构建版本；PETSc 3.19.6 不再参与每次 Push/PR 的自动编译和链接检查。
- 更新 `AGENTS.md`：规定第三方差异优先通过能力检测、官方版本宏和集中兼容层处理；需要 Patch 时必须版本限定、可追溯、可重复应用；仅在相关兼容路径变化时做针对性验证。
- 更新 `.github/workflows/core-numerics.yml`：日常矩阵保留 PETSc 3.23.7 Debug/Release；3.19.6 仅在手动触发并勾选 `run_legacy_petsc` 时执行 Release `mpi-failure` 专项检查。
- 更新 `docs/development/BUILD_AND_VALIDATION.md`，使构建说明与工作流一致。保留 3.19.6 锁文件和运行脚本，未删除历史环境。
- 在工作流文件完成调整前，首个内容提交曾短暂触发旧矩阵的一次过渡 Push CI，其中 PETSc 3.19.6 Release 专项 job 已通过；随后最终工作流改为独立可选 job，当前 PR CI 中 3.19.6 job 明确 skipped，不执行编译/链接。最终 3.23.7 Debug/Release CI 正在验收；不将过渡运行解释为未来日常策略。

## 2026-10-31 / DEV-PROCESS-POLICY — 长期知识积累规则

- 用户明确提供“EONSim 持续知识积累要求”，将其固化为根目录 `AGENTS.md` 的项目级规则；Codex 新 Task 应读取该文件执行，不要求用户每次重复粘贴。
- 规则要求每项实质任务记录重要错误与根因、真实测试证据，更新 `CODEX_SESSION_LOG.md`、`CODEX_PROGRESS.md`、`CODEX_TASK_QUEUE.md` 和 `KNOWLEDGE_LOG.md`；有复用价值的技术成果使用 `eonsim-knowledge-capture` Skill 形成 `website/drafts/` 草稿。
- 明确边界：普通 typo/纯格式/机械小改动不强制生成文章；没有复用技术成果时不制造草稿；文章未经人工审核和 PR 合并不得发布。
- 同步更新进度和任务队列，将本项记为 review，并更新知识索引。相关文档提交：AGENTS `54cba2e`、进度 `04b334a`、队列 `389fc5b`；后续会话日志和知识索引提交由本条记录的 Git 历史追溯。
- 验证范围：通过 GitHub 仓库内容接口复读并检查目标文件，确认规则文本和链接路径存在；本任务没有修改 C++/CMake/数值测试，没有运行编译、CTest、MPI 或性能测试。PR #24 的 GitHub Actions 结果以实时 Checks 为准；未完成项目不标记为通过。
- 未生成技术文章草稿：本次交付是研发流程规范，不是新的算法、数值方法或可复用技术错误分析；该决定已登记在 `KNOWLEDGE_LOG.md`。


## 2026-10-31 / DOCS-01 远程交付授权

用户追加要求推送并合并到远程。再次 fetch 后 origin/main 仍为 a508e3d；89 份 Markdown 的静态检查与 git diff --check 通过。准备提交并通过 PR 合并；远程检查结果待实际完成后记录，草稿不转正式栏目。

## 2026-10-31 / DOCS-01 远程交付完成

- 功能提交 `40f87c0989cde56d085f3b05eea31b90116dc9e9` 已推送，并通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合并为 `be21882b589735ff449b472e8efc76555cffb9fb`；没有强推。合并 tree 与功能提交一致，已用 `git diff --exit-code 40f87c0 be21882` 核对。
- [PR 数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324586) 实际日志确认：PETSc 3.23.7 Debug/Release 各 60 passed、0 failed、0 skipped；测试对象为合并预览 `8e835ecb5b9475e2e70f802b9944554e13f4e2cb`。PETSc 3.19.6 手动兼容 job 本次 skipped，不计为通过。
- [网站 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324560) 的生产构建与草稿/模板隔离均成功。此为远程补验，前序本地缺少 Node 的记录仍成立。没有新增性能结论，也没有将草稿转为正式栏目。
- 本地 main 已快进至合并提交；仅补记任务完成状态和上述证据链接。本补记不改源码/网站，静态复核后使用 `[skip ci]` 提交，避免重复数值套件；不把前述结果标记为补记提交的新运行。


## 2026-10-31 / TEST-POLICY-01 — 增量验证与历史证据复用

- 用户明确要求仅改约束，不开发和编译项目，并停止每次开发结束后的全量测试及无关历史测试重跑。源码基线 `3df1c31f8f3b6c995e00368782a94971a92371c3`；本次变更仅为 Markdown；用户随后授权本地提交，分支 `codex/incremental-validation-policy`，未推送。
- 静态检查发现旧规则虽写“最小验证”，仍在基础设施交付、公共接口和最终集成处要求 `all`，且“代码继续变化”重跑条件未限定影响范围。已统一 AGENTS、L0、构建与验证、路线及 Goal 流程：只检查新增/受影响行为，复用未受影响的历史通过证据，全量仅在用户明确要求时运行。
- 历史证据保留原提交、命令/环境/结果或归档链接；本次未运行须明确标注，不计作当前提交新通过。受影响路径不能仅用改动前的通过记录代替必要检查。
- `.github/workflows/core-numerics.yml` 仍配置 Push/PR 的主锁 Debug/Release `selection: all`；本次按“仅改约束”限定未修改工作流、测试或脚本，没有实现 CI 自动选测，也没有触发远程验证。
- 验证仅限文档阅读、`git diff --check`、改动 Markdown 本地链接目标检查和差异范围核对；没有运行 CMake 配置、编译、CTest、MPI、性能实验或网站构建。无数值结果或性能结论，未生成知识文章。
- 进度、队列及知识索引同步；任务为 review（本地分支交付，未推送、未合入 main），不改写历史交付记录。


## 2026-10-31 / CI-INCREMENTAL-01 — PR 增量执行（进行中）

- 用户选择并批准：仅 PR 自动增量检查，分支 Push/main 不重复数值 CI；脚本验证加一次小型云端验收；不改生产求解器、不跑全量、不自动合并。基线 ef20e03，分支 codex/pr-incremental-ci。
- 原入口只有 core/all/mpi-failure，先编译所有目标且重复做 2/4 rank 预检。新增显式路径/测试/目标映射、精确 JSON 清单执行、同 PR 成功 receipt；保留原必需检查名称与手动全量/旧锁专项。
- 复用前检查 workflow 成功、repo/PR/base/规则及依赖指纹、head 祖先关系、完整双模式来源；找不到有效证据只重新计算 PR 相关项，不能落回 all。artifact 下载跨域时去除 Authorization；ZIP 只读取单个有界 receipt.json，不解压到工作区。
- 首轮选测脚本测试发现 include/eonsim/fsi_element.hpp 未映射；补齐后 24 项 Python 测试通过。共享 reader、流体边界对固体的使用者及 profile 日志输入也纳入显式规则。
- 已执行 python3 tests/test_ci_selection.py（24 项通过）、python3 tests/test_cloud_evidence.py（6 项通过）、bash -n scripts/cloud/run.sh、actionlint 1.7.7 的 core-numerics.yml 语法检查及 git diff --check；尚未运行本次生产构建/数值测试，云端 smoke 待 PR 验收。旧数值记录不计为本次通过。
- 使用 eonsim-knowledge-capture 记录 CI 选测/证据复用草稿，不发布；后续补充真实云端证据及文档提交的复用结果。

### CI-INCREMENTAL-01：首轮云端精确清单验收

- 实现提交 `8f695cc6ed17fcbbd2736cceba38e7984de2b67e` 已推送并创建 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26)，未合并。主数值 [run 41214961025](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41214961025) 成功，实际测试 merge preview `9ce31f9f869770e5672b01a1dfa39b4788710c6f`，tree 与功能提交相同。
- PETSc 3.23.7、OpenMPI 5、GCC 15.3，云端 4 CPU/约 16 GiB；Debug/Release 仅运行 poisson_verification，各 1 passed、0 failed、0 skipped，rank=1。构建 targets 仅 eonsim、verify_runtime；锁定运行时探针 rank=1 另计，不冒充数值测试数。JUnit 与清单一致，receipt 已生成。
- 实际入口：`scripts/cloud/run.sh 3.23.7 <debug|release> explicit .cloud build/ci/plan.json`；CTest 使用 `-R '^(poisson_verification)$'`。完整命令、退出码及精简结果见 [initial.json](../research/data/ci-incremental-2026-10-31/initial.json)。本地未编译或运行求解器，主锁全量及旧锁未执行；旧锁 job 为 skipped。
- 网站 run 41214961032 成功，草稿隔离通过。GitHub runs 查询确认该提交只有两个 pull_request 事件，没有 Push run。
- 下一笔仅补记文档/证据，将用于实际验证同 PR receipt 复用；复用结果尚未计为完成。

### CI-INCREMENTAL-01：历史证据复用验收与交付

- 文档/证据提交 `00722958b64df7cb65821269a08e510c5214834b` 的 [run 41215264515](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41215264515) 全部成功；selection 明确 `tests=[]`、`python=[]`、`reused=[poisson_verification]`。Debug/Release 的依赖缓存、restore、checkout、build/test 和数值 artifact 上传步骤均 skipped，不是重新通过一次数值测试。
- 新 receipt 指向 previous_run_id=41214961025，每个模式的原始来源仍为首次 merge preview `9ce31f9f869770e5672b01a1dfa39b4788710c6f`。精简证据见 [reuse.json](../research/data/ci-incremental-2026-10-31/reuse.json)。网站 run 41215264596 也通过；旧锁专项未运行。
- 补充两个标准库测试验证手动 all/explicit 清单生成及 PR 禁止请求手动全量，执行 `python3 tests/test_ci_selection.py SelectionTests.test_manual_all_and_explicit_cli_only_plan_requested_names SelectionTests.test_pr_cannot_request_manual_full_suite`，2 项通过；没有执行任何全量数值测试。选测/receipt 测试文件现共 26 项。
- 本地直接查询 api.github.com 曾超时；改用已连接 GitHub 的只读 fetch/log/artifact 接口取得证据，没有修改网络策略或把查询失败计为测试失败。
- 交付为 PR #26 review，未自动合并。代码、规则、状态及知识索引同步，文章保持 draft。已验证范围为新 CI 路径；不扩大为现有 60 项套件的新通过记录。最后补记只涉及状态/证据及上述脚本测试，数值执行链与规则指纹保持不变。


## FEM-G2A — 局部 P2 检查点（未完成）

- 用户批准完整 P2 稳态 D/N、1/2 rank 闭环，本地开发及云端相关检查；10 小时为估计，闭环完成优先。
- 已将 main 快进至 PR #26 合并提交 `35bf1a1`，新分支 `codex/fem-g2a-p2`。
- 新增纯参考 P2 tabulation，节点顺序为顶点及 01/12/20 边中点；不修改网格几何、生产模型或依赖。
- 实际命令：`c++ -std=c++17 -Wall -Wextra -Wpedantic -Iinclude tests/verify_tri_p2.cpp -o build/p2-local/verify_tri_p2 && build/p2-local/verify_tri_p2`，退出 0；独立六个二次空间单项式的值/梯度重现、节点插值、反向边迹通过。无 MPI/PETSc；不是求解器验收。
- `python3 tests/test_ci_selection.py`：26 项通过；`git diff --check` 通过。新增 CMake 注册项尚未通过 CMake 构建执行，不将直接编译结果称为 CTest 通过。
- 未完成：实体边空间、分区存储、装配、D/N、输出、数值收敛和真实 1/2 rank、云端 CI、PR。任务继续 in_progress。源码检查点由本记录所在 Git 提交追溯。
- 暂不生成完整知识文章：只有局部基础函数证据，完成真实闭环后按知识采集 Skill 汇总，不能提前写成生产能力。


## 2026-11-01 / FEM-G2A — 分布式 P2 实现与本地验证

- 源码提交 edfc73c；基线 35bf1a1，分支 codex/fem-g2a-p2。新增独立 ScalarP2Space，以原始顶点 ID 对规范化边，在现有 METIS 单元分区之后建立 owned/ghost 和包含远程单元贡献的完整图。HDF5 可选组 version=1，原几何版本不变。
- P2 稳态统一系数 Poisson、非零 D/N、原生二次三角形 VTU/PVTU 已接入；geometry/space 分离。缺失空间、非法连接/owner、非有限坐标明确拒绝。未支持模型在配置/准备阶段报错。
- 本地命令 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/plan.json` 首次执行 p2_space_oracles、tri_p2_oracles，2/2 通过；随后 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json` 只执行 scalar_p2_verification，1/1 通过。空间身份/读取校验修改后，仅重跑受影响的 P2 求解项，通过。
- 真实 1/2 rank 畸变 patch L2 约 3e-12、H1 约 5e-11；n=4/8/16 正弦最细 L2/H1 阶 2.9699/1.9711；双 rank 使用节点/单元反排输入，场按实体身份对照。配置拒绝和强制 KSP 失败均通过。
- 直接 C++17 编译执行 verify_tri_p2 补充解析刚度/载荷矩阵 oracle，及 verify_p2_space 的实体/远程邻接验证，均通过；26 项 CI 选择脚本测试通过。未执行全量、旧锁或本地 Release。
- `python3 build/p2-local/check_corruption.py` 使用 h5py 3.14 修改 rank_1.h5，分别删除 P2 组、篡改连接和 owner；真实双 rank 明确失败且未生成索引。该额外本地检查脚本与结果已归档。新补入自动脚本的旧 P1 分区拒绝场景尚待云端执行。
- 编译发现 signedness 和 misleading-indentation 警告，已修正并重新编译，无新增警告。未降低数值门槛或放宽测试超时来隐藏失败。
- 证据 docs/research/data/p2-2026-11-01；摘要记录实际执行时的 dirty 状态，不能把后来新增测试标为此前已执行。云端验收及 PR 仍待完成，任务 in_progress。


### FEM-G2A 云端验收完成

- PR #27：功能提交 6327c189b9cd936159fb11c5f472934047fa2f0e，生产实现 edfc73c。run 41283957039 的实际 merge preview 为 60ee8e26a0ccf8f1b11aad8fe1906c17f67cd87c。
- PETSc 3.23.7 Debug/Release 各 19 passed、0 failed、0 skipped；selected checks 包含 P2 三项及共享配置/分区/语义入口的代表回归，未运行全量。最终新增的 missing-space 自动负例与解析刚度/载荷 oracle 已随此次 CI 验收。旧锁 job skipped。
- 云端 4 CPU、约 16 GiB，网站 run 41283957245 通过；草稿保持未发布。来源摘要 docs/research/data/p2-2026-11-01/cloud.json。
- 状态 review，未自动合并。文档收尾只复用上述通过证据，不将其记作新提交重新运行。Markdown 本地链接与 git diff --check 通过。


## 2026-11-01 / FEM-G2A 合并状态接续

用户要求继续推进。通过 GitHub PR 信息及 git ls-remote 确认 PR #27 已于 2026-11-01 合并，main 为 c0745ea88c89ab08bb5babbcae530ee2008a49cf；本地 main 已快进。审核时间线没有待处理的代码审查意见。任务改为 done，数值证据复用既有 run 41283957039，不重新编译或运行测试。后续新增范围正在确认。


## 2026-11-01 / FEM-G2B — P2 Robin 与纯 Neumann

- 用户要求继续推进；上一任务 PR #27 已合并。提出后续范围选择，在等待期间完成主线同步；未收到其他选择后按已说明的推荐项推进边界扩展。未自动合并 PR。
- 实现 d6ec4244a73adbcbfd839b93cc595260a0138447。Robin 复用三节点边迹，增加正系数边界矩阵和相应制造解载荷；纯 Neumann 复用现有 LinearSystem 常数零空间及载荷相容性检查。无新配置键、依赖、分区格式或主求解器后端。
- 非直观数学细节：P2 顶点基函数的体积积分为零，节点均值不是物理体积均值；归一化使用积分后的全局均值，并同步规范制造解的误差参考。
- 执行 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json`，清单仅 scalar_p2_verification：1/1 通过，真实 1/2 rank 全 Robin 与纯 Neumann patch、用户显式源项/Robin 数据、MPI 场值对照及不相容载荷拒绝均通过；相关已有 P2 路径随受影响测试复验。
- 双 rank 纯 Neumann L2=6.2481e-13、H1=9.2768e-12，物理积分=-9.9920e-16。没有放宽容差；编译无新增警告。没有执行全量、旧锁或本地 Release。精简数据与原摘要归档 docs/research/data/p2-boundaries-2026-11-01，原摘要保留实际 dirty 状态。
- 使用知识采集 Skill 更新现有 P2 草稿，不制造重复文章；云端相关验收待执行。


### FEM-G2B 云端交付

PR #28 的 run 41287626201 成功，实际 merge preview bbf494b84af62b904a7821355d75fab982831b16，功能提交 41547fa，生产源码 d6ec424。PETSc 3.23.7 Debug/Release 各 10 passed、0 failed、0 skipped；旧锁专项 skipped。网站 run 41287626208 成功。摘要 docs/research/data/p2-boundaries-2026-11-01/cloud.json；本次无全量测试。状态 review，未自动合并；收尾文档复用上述成功证据。


## 2026-11-02 / FEM-G2C — 启动检查点（未完成）

- 用户授权按约 10 小时规划实施，验收完成后才创建 PR。基线 `1bc87a7`，分支 `codex/p2-transient-diffusion`；当前改动未提交。
- 核对 P2 装配、P1/Q1 时间驱动及 checkpoint 接口。P2 空间身份尚未纳入 checkpoint，P2 输出局部 I/O 异常的集体传播需完善；这些是待实现事项。
- 增加独立解析 P2 一致质量矩阵 oracle（参考三角形面积 1/2，整数矩阵除以 360），同时保留刚度、载荷和二次重现检查。顶点行和为零，不采用行和集总质量。
- 实际执行 `c++ -std=c++17 -Wall -Wextra -Wpedantic -Iinclude tests/verify_tri_p2.cpp -o /tmp/eonsim-verify-tri-p2-g2c` 及 `/tmp/eonsim-verify-tri-p2-g2c`，均退出 0。独立 C++17 检查，无 PETSc/MPI，不计为 CTest 或瞬态生产验收。`git diff --check` 通过。
- 首次创建分支因沙箱中 .git 只读失败，按工具授权升级后创建成功；没有绕过文件系统权限。
- 尚未实现生产时间推进、恢复及时间序列，未构建求解器、未跑 Debug/Release 或 MPI 验收；未创建 PR。任务保持 in_progress。尚无完整可复用成果，不新增文章草稿。


## 2026-11-03 / FEM-G2C — P2 瞬态闭环本地验收

- 用户要求继续实施，完成后提交 PR；源码 `d19a03268577b33ddfb41177037d9bbc1f76d273`，基线 `1bc87a7`。上次只完成质量矩阵 oracle 后停止的检查点不代表完整交付；本轮继续实施，没有后台任务或绕过额度限制。
- 生产 P2 接入一致质量矩阵、BE/变步 BDF2/一阶 generalized-alpha、时变 D/N/Robin、事件、真实 KSP 失败后的有限缩步。历史只在求解成功后更新，瞬态 Neumann 保留均值。
- 复用 v3 checkpoint，附加 P2 实体整数身份、编号、owner、连接及边界标签签名；不能把大整数 ID 转 double 后散列。恢复时局部读取异常集体传播，校验跨 rank 时钟/历史元数据一致。P2 输出加入算法导数、接受步序列和 XML 转义，分片失败不发布全局索引。
- 初次沙箱 MPI 预检因 PMIx socket errno=1 失败，按工具授权在沙箱外重跑；不是数值失败。首次新增 time 测试误向 BE/BDF2 配置 rho_infinity，配置器正确拒绝；修正测试仅在 alpha 设置 rho，未改校验规则或放宽容差。其余 restart/failure/质量 oracle 已通过，未因该测试错误重复运行。
- 实际命令：`bash scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json`，原 P2 steady 检查通过；`... debug explicit .cloud build/p2-local/transient-plan.json` 首轮 3 passed/1 failed；随后 `... debug explicit .cloud build/p2-local/time-only-plan.json` 仅时间项通过。补充变步时间阶和用户边界后重跑该时间项通过；签名加入语义身份与标签后仅 `... debug explicit .cloud build/p2-local/restart-only-plan.json` 重启项通过。
- `bash scripts/cloud/run.sh 3.23.7 release explicit .cloud build/p2-local/release-plan.json`：scalar_p2_verification/time/restart/failure、tri_p2_oracles 共 5 passed/0 failed/0 skipped；应用 Release，锁 PETSc 3.23.7/OpenMPI，单 rank 单线程，数值 MPI 为 1/2 rank。环境为本地 WSL2，不能称云端运行。各步命令、依赖和结果保留于证据 JSON。
- 独立质量矩阵逐项对照解析值；恒定与交替步长时间加密、rho=0/0.5/1、时变端点 D 与自然 N/Robin、绝热积分、乱序输入 1/2 rank 对照通过。重启覆盖事件处和有效多步历史，输出原时间片/序列保持；真实 KSP 限制触发缩步，重放到相同实际步长结果一致，重试耗尽不改 checkpoint。
- `python3 build/p2-local/check_history.py`（系统 h5py 3.14.0 + 锁定 MPI/求解器）：双 rank 缺失 previous/rate、非法 time_metadata、非有限 scalar、改变边实体语义身份均拒绝，8/8 通过；该脚本作为本地补验归档，不新增日常 Python 依赖。
- `python3 tests/test_ci_selection.py` 26 项通过；`python3 tests/test_cloud_evidence.py` 6 项通过；新增文件路径分类无未知项，PR 预计选取 15 个相关 CTest（最终以实际 PR 差异为准）；`git diff --check` 通过。没有全量、旧锁、性能或超过 2 rank 的本轮运行。
- 测试执行时 HEAD 为基线且源码 dirty，随后提交为上述实现 SHA；原始摘要保留真实状态。Debug 时间/失败结果早于仅签名补充，复用未受影响路径；最终 restart/Release/故障补验覆盖完整签名。不因为后续文档提交重跑。
- 使用 eonsim-knowledge-capture 整理 P2 瞬态历史草稿，保持未发布；已更新状态、队列及知识索引。PR 与云端检查尚待后续记录。


### FEM-G2C — PR #29 云端验收与交付

- 实现 d19a032，交付 head e5900a169d079c82b4af8509d1aa4af4fd199a88；[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 已创建，未合并。实际 merge preview b8c1642f08ef5333f55e874fa5c83157e7ba2a59 的 tree 284e3497681e54af1949869fee3c963e597deca3 与本地 head 一致。
- [数值 run 41582475827](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41582475827) 的 Debug/Release 日志及 receipt 均确认：PETSc 3.23.7，各 15 passed、0 failed、0 skipped。清单包含 P2 新增三组及配置/CMake 影响入口代表回归；不是全量。P2 新验收为 1/2 rank；共享旧检查 scalar2d_space 等保留自身最多 4 rank，不扩展 P2 验证结论。
- 云端 4 CPU、约 16 GiB；每模式构建、运行时链接和 CTest 命令退出 0；receipt 核对测试清单与双模式来源后成功。3.19.6 手动专项 job skipped。选测脚本的合成 failure/error/skipped XML 是负例输入，26/6 项脚本测试均通过，不将日志里的负例文本误认为数值失败。
- [网站 run 41582475766](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41582475766) 构建和草稿/模板隔离成功；文章仍是 draft。
- 精简机器证据、15 项清单与每项原始来源见 docs/research/data/p2-transient-2026-11-03/cloud.json。收尾仅补状态和证据，复用同 PR 上述通过记录，本次不重新编译或运行数值测试，不使用 skip ci 绕过检查。


### FEM-G2C 远端合并与补记竞态

最终状态查询发现 PR #29 已在 2026-11-03T05:16:50Z 合并，merge commit 为 dff911648e54507e9cca80ad1880c20b867a0c75，实际合并 head 为 e5900a1；本 agent 未调用合并工具。补记 87f6df0 在该时间之后推送到原分支，没有进入已关闭 PR，因此查不到它对应的新 PR CI，不属于检查失败或绕过。修正队列为 done；最终证据与合并状态单独提交纯文档补记 PR，不修改数值源码，不重跑历史已通过检查。


## 2026-11-03 / FSI-LOAD-01：时变压力与接受步历史

用户批准计划后执行；先 fetch origin，基线 `417e6f9`，独立分支 `codex/fsi-periodic-pressure`。
实现提交 `a6c6761084f2003c72593107c6aa5cbc351d75bb`。
新增 smoothstep 启动正弦压力、共同阶段评价、缩步重算和波形签名；
抽取既有场重建实现接受步 CSV/流固 PVD，集体传播写出失败，保留最终场路径。

实际验收命令、配置、rank、误差和失败尝试见 [本地验收](../research/data/fsi-pressure-2026-11-03/README.md)。
Debug state/convergence 直接脚本通过，局部切线/刚体 CTest 2/2；Release convergence 直接脚本通过，state/局部切线/刚体 CTest 3/3。
Python CI 选择器 26/26。Release 双 rank 示例 100 步完成，并实际生成检查响应图。
BE 粗步未达门槛后细化，保持原阶数标准；其他初期失败为测试配置/比较器/错误字符串问题，具体根因已归档。
未执行全量、旧 PETSc、新 4 rank 或性能基准；10 小时是计划估计，不宣称实际运行 10 小时。

使用 eonsim-knowledge-capture，形成 [阶段载荷与接受历史草稿](../../website/drafts/fsi-periodic-pressure-history.md)，未发布。
进度/队列/知识索引同步，任务 review；所有本地验收及记录完成后才创建 PR，未自动合并。

本地验收与记录提交 `38a83c9` 后创建 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31)。自动增量 CI 数值 run `41589294783`，网站 run `41589294782`，开始时均 in_progress；最终结果另行记录。

云端数值 run `41589294783` 最终 success：PETSc 3.23.7 Debug/Release 各 24/24、零失败/跳过；3.19.6 按策略 skipped。网站 run `41589294782` success。数值检验提交为合并预览 `6bed816adfa8090d174c335da36b283b47d25f87`，PR head `38a83c9`，不是已合并 main。精简日志摘要见 [ci.json](../research/data/fsi-pressure-2026-11-03/ci.json)。仅补记录，不重跑本地检查。

## 2026-11-03 / FSI-NEXT-01：固定入口、可靠性与受控研究

- 用户要求实施下一步完整 FSI 任务，全部完成后才提交 PR；20 小时是工程量估计。fetch 确认 PR #31 已合并为 `06b05c4`，从该 main 创建 `codex/fsi-inlet-reliability`。未自动合并任何 PR。
- 生产实现 `0d93d41`，界面真实双域邻接补强 `69692ee`；最终性能脚本 `32783a5`。固定仿射三分量入口及 smoothstep 启动，BE/BDF2 终点规定值与 alpha 终点插值，冲突检查和 checkpoint 签名；新增共形弹性顶壁算例。
- 界面三角片按稳定节点 ID 分布式路由，只接受恰有一个流体与一个固体邻接单元的面。按参考面积积分位移/速度、另报当前面积；几何检查同时覆盖阶段和外推终点，失败必须早于历史提交。夹持反力不混入自由界面残量平衡。更新单体 FSI 长期契约。
- 实际本地 PETSc 3.23.7 Debug/Release 构建受影响目标，CTest 正则 `^(fsi_diagnostics|fsi_diagnostics_mpi|fsi_inlet|fsi_pressure_state)$` 各 4/4，零失败/跳过。含 1/2 rank、三时间格式终点、恢复、装配切线及真实拒绝重放；线性/Neo-Hookean Jacobian 最大差 1.54187e-8/1.54813e-8。
- 入口 Neo-Hookean 两格式各真实缩步 16 次；刚体 alpha 周期压力第四步阶段收敛而终点反转，失败 checkpoint SHA256 不变，失败步无历史发布。缩步 1 次后成功，与相同步长重放一致。
- `scripts/study_fsi_next.py --study inlet-time` Release 分场 RMS 比较：BE .905–1.056、BDF2 1.892–2.091、alpha 2.000–2.223。`--study accuracy` 最初时间污染为最后空间差 6.98 倍，统一细化后为 .09509；n=2/4/8 轨迹差减小，不宣称预定空间阶。旧进程超时不足，主动取消为退出 143；只复用已成功样本，以归档的 `finish_accuracy.py` 完成参考解，取消样本不计通过。
- `--study performance` 最终为 10 预热 + 30 正式样本，1/2/4 rank、n=4/8、625/5057 DoF。三次交替重复且同容差；最大场差 6.16e-11。直接法在小网格及 n=8 的 2/4 rank 更快，分块最大进程 RSS 更低；没有稳定加速证据，不改变默认求解器或引入推测性优化。
- 重要失败：BE/BDF2 误带 rho 参数；重复负例沿用输出前缀留下旧 PVD；粗 BE 固体位移阶 .844；仅按流体外表面计数缺少固体邻接。分别修正测试配置/前缀、细化时间、补强邻接及 oracle，未降低验收标准。性能首轮位移差 2.20e-14 经 dt^-2 放大为加速度差 1.027e-8；统一收紧非线性后旧 KSP atol 又导致 SNES -6，最终同时收紧所有 recipe 的线性容差，重新测量完整矩阵，失败数据单独保存。
- [验收 README](../research/data/fsi-next-2026-11-03/README.md) 记录完整命令、配置、依赖、rank、源码沿革、失败尝试及 JUnit/CSV/JSON/图。空间历史来自原方程提交，后续邻接修订不改变该平面共形算例，复用已有通过证据；没有全量或 PETSc 3.19.6 运行。
- Python 选测器 26/26；`git diff --check` 通过。使用 eonsim-knowledge-capture 形成 [知识草稿](../../website/drafts/fsi-inlet-endpoint-and-resolution.md)，未发布；更新进度、队列与知识索引。PR/云端结果另行记录。

FSI-NEXT-01 最终审查发现旧镜像弹性体使用单独参考几何分支，追加 Debug/Release `elastic_fsi_verification` 各 1/1（不重复前述已通过检查），并补 CI 映射；本地各累计 5 项。选测器 26/26、证据解析 6/6 通过，新文档链接检查通过。

## 2026-11-03 / WEBSITE-KNOWLEDGE-REFRESH — 网站与知识资产同步

- 基线 main `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`；在独立分支 `codex/website-knowledge-refresh-2026-11-03` 更新网站首页、研发总览、知识索引、单体 FSI 专题及 FEM 学习页。
- 根据已合入 PR #31/#32/#33 更新 FSI 能力说明；根据 PR #27/#28/#29 更新 P2 标量有限元范围。相关测试数量只按已归档证据记录，不将选测描述为全量测试。
- 补记 FSI 与 P2 技术文章草稿的合并状态、CI 来源和限制；所有文章继续留在 `website/drafts/`，未自动发布。
- 同步 `KNOWLEDGE_LOG.md`、`CODEX_PROGRESS.md` 和 `CODEX_TASK_QUEUE.md`，修正 FSI-NEXT-02 已合并后的状态。
- 本任务只改文档，不运行 CMake、编译、CTest、MPI、数值或性能实验；网站构建/草稿隔离检查待本 PR 的 GitHub Actions 结果确认。

## 2026-11-06 — FSI-PROD-01 circular inlet / solid-wall tube

User asked to advance toward production FSI. Rechecked/fetched main `dd27eef`
(PR #36 merged), isolated branch `codex/fsi-production-tube`. Read architecture,
state, build and knowledge contracts. Implementation local `31a04e6`, remote
`718b7a6bb97fbb5eed09829a0bb7225d3963ee5f`, identical tree
`8b0adc8bd3b206576cefd9a0e90e5314397d24ec` verified before branch creation.
CLI push failed for missing HTTPS credentials; uploaded code via GitHub API.

Implemented circle profile with discrete MPI flux normalization and geometry
checkpoint signature, preserving rectangle default/signature; deterministic
independent disk/annulus Tet4 meshes with matching interface triangulations;
actual coupled tube acceptance and independent mesh oracles. Review performed
by the implementing agent, no independent external review claimed.

Important failure: an enlarged inlet radius violates zero velocity on clamped
interface rim nodes before restart compatibility is checked. Initial negative
test expected the wrong failure category. Split geometry-conflict and waveform
signature tests without changing solver tolerances. The test script was edited
while the first Python process retained its old code, so traceback source lines
can show a newer label; preserve the failed log and rerun the entire corrected
tube test. No production fix was needed for this failure.

Validation commands, source hashes, metrics, first failure and final logs:
[FSI-PROD-01 evidence](../research/data/fsi-tube-2026-11-06/README.md).
Restored pinned PETSc 3.23.7 with `scripts/cloud/restore.sh`; compiled using
`scripts/cloud/run.sh`, explicit affected tests only. Release tube and old
rectangle flow checks passed. Independent mesh tests 2/2 and CI-selection
checks 26/26 passed. Debug tube first failed at a negative-test process startup (LLVM OpenMP
assertion/PMIx error), while rectangle flow passed. Retained the failure,
reused the historical bounded PID-isolation workaround and reran the complete
tube check: 1/1 passed, zero skips. Thus Debug/Release each accumulated two
distinct affected checks passed. No tolerance or equation changes.

Additional signed radial-field inspection shows both local contraction and
expansion on this coarse transient mesh. Do not describe response as physically
qualified; PROD-02 must separate spatial/geometric/time effects and compare
against analytical limits and a pinned svFSI case. No default-tau, production
scale, patient accuracy, RCR, external Robin or multi-node claim.

Reusable derivation and failure lesson captured in unpublished draft
`website/drafts/fsi-circular-inlet-discrete-flux.md`; roadmap and task queue
advance toward quantitative tube qualification, vascular boundaries, real
geometry and multi-node scaling. Do not auto-merge main or publish the draft.

PR #37 acceptance: remote head `29d8082`, merge preview `92a28b5`, identical
accepted tree `8ef42cd7e716aa995b03030fa7ed0617e7e2c449`. Core run
42170183765 Debug/Release each 31 passed, zero failed/skipped; website run
42170183717 and incremental receipt passed. Final update only records evidence
and PROD-02 dimensionless-scale scoping (Re .006366, alpha 12.533 for current
coarse case); no numerical rerun or new physical accuracy claim. PR remains
unmerged and the knowledge article unpublished.
