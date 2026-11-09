# EONSim Codex Development Progress

> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

用户最新选择：取消全量上传，先推送单独快照分支 `codex/fsi-progress-snapshot-20261109`。完整本地分支和工作区未改写；不创建PR、不合并、不自动恢复计算。

2026-11-09 02:35 UTC / 10:35 CST：**用户已停止定时任务及全部后台计算，以下为最高优先状态。**
20个控制器和数值、分析、归档、等待子进程已退出，9个专用scope空；02:38复查无活动数值进程。
[停止收据与当前进度](../research/data/prod48-user-stop-2026-11-09/README.md)保存实际信号、完整状态及小型报告。
用户随后明确要求提交远程，替代此前“全部验收后才push”的上传时点限制；本次只上传当前开发分支，
不创建PR或合并。不要自动恢复旧控制器或重新启用定时任务；原始数据、日志、检查点及未封存档均保留。

停止前确认：α1 S48 N4002400/2400且解析完成，U1.0163191685%仍FAIL1%，家族预算未完成；
α2 S96 N8003099/4800；四参考分别7660/12800、9319/12800、4464/6400、2426/6400；
L24新增314/800；新N800粗7807/25600、细999/25600。步数不等于资格通过。
本次保存成熟FSI完整小报告/raw复核、N800冻结计划/采用/周期收据与停止记录；原始大轨迹的中断归档
没有完整manifest，继续仅保留本地，不冒充完整证据。原全部物理失败和未完成预算保持。

2026-11-09 02:23 UTC：本地HEAD3b08e4f已保存可选FSI LU代码及完整验证，没有push/PR。
47675成熟筛查02:05:45完成，47710全部raw重读02:14:48通过；176五场对、144native对1584datasets，
node6.22419e-15、P1mass2.36686e-12、history1.53126e-14，旧clock差0、新v4精确。
old-first/new-default/window32/window8/old-last各32态耗时146.111/149.287/61.423/75.718/149.516s，
实际LU32/32/1/4/32；16态重放34.651s/1LU。四成本比全部≤.9，只是共享CPU上的局部成本。
47776/session18158正在捕获完整成熟证明，之后等46800完整L24延长再归档；增长中不stage。

新独立S24 N800家族已通过实际计划自审并启动：fine47914/session25412、coarse47944/session35201，
budget47952/session93166锁外等待两组完成。control fsi-s24-n800-lu32-family-3b08e4f，
definition c6c5e5d9c9a23d0eafeb479439c83633fd72df8bbbfe5b526f0105bd97309540；候选6993/LU32，
原生1rank，fineCPU22/coarseCPU19 nice19共享、各2Gswap0、12G入场/8G底线。
从零统一dt=2pi/800，32周期25600步，原16周期ramp；末三周期全部2400态及实际23200端点审计。
空间对照为同N800粗/细网格，时间对照为完整旧fineN400；预算仅明确替换网格常量，算术和.1不变。
原N400三项时间失败不覆盖，未创建N1600或新参考时间族。47990/session37012等待归档锁，先存
不可变采用计划，之后各自完整粗/细/预算终态归档。02:21粗2131/25600、细249/25600；不是资格通过。
原α1N4002374/2400、α2N8002977/4800，四参考7570/9204/4376/2323继续，L24新增243/800。

2026-11-09 01:50 UTC：b8d1c76已本地保存S24时间预算失败，三项时间差超.1保持。
[可选FSI LU验证](../research/data/fsi-retained-lu-validation-2026-11-09/README.md)已01:42:32完成：
Debug/Release各3/3、CI26/26、3696完整HDF最大9.7318e-15、v4时钟精确；2Gswap0、零事件/空scope。
Release6993d7f/Debug2123b716已冻结，8950files1part1433180B已完整Git回读。
47675/session9565于01:46:46运行满载6200检查点32态筛查，status fsi-retained-lu-mature-screen-current；
CPU19nice19/2Gswap0/analysis锁，五种32态模式及16态重放，完整176场对/144native对与成本待完成。
46800 L24独立6400→7200继续，43422/44619原始档仍捕获，六主研究保持。未采用新时间族，无push/PR。

2026-11-09 01:35 UTC：完整[S24 EON预算](../research/data/elastic-s24-eonsim-time-budget-failure-2026-11-09/README.md)
已结束但未通过：压力、流体速度、固体速度time/space分别.9133408342/.3861397581/.1905876075，
均超过.1；ALE/固体位移通过，全部tail/sampling通过。40042现等参考程序，不重复EON分析。
57文件1包1449600B已完整Git回读；原失败保留，不采用Richardson缩放或调整物理门槛。

44437及44493的210五场/11native重放与独立复核已通过，01:29:44 rawreview完成。
具体L24 6400→7200计划现已prepare，definition a91c5770add90857b8a4e3316030db4d89359c7e673e7743e754779adae0d2cb；
执行自审01:34:01通过；46800/session29291于01:35:56实际启动6400→7200，CPU14nice19/2Gswap0。
原c32周期失败不覆盖，完整证明档44619正在捕获。
新增46060/session33301于01:31:48开始Release可选FSI LU验证，随后Debug及完整HDF；
CPU19/2Gswap0/原analysis锁。Release3/3已通过，Debug及全HDF尚待完成；代码未提交/采用，旧冻结生产继续。无push/PR。

2026-11-09 01:12 UTC：03b3bfc已本地保存94文件四参考前缀。当前源码复核仅修正
[执行策略说明](FLUID_PRESSURE_TIME.md)：chord支持显式Schur/MUMPS，保留LU与fresh SNES
属于不同生命周期；早期准备证据与后续实际检查分开引用。未改运行时或重跑数值测试。
01:08实际完成步：ν.3fine7045/12800、ν0fine8540/12800、ν.3time3864/6400、ν0time1726/6400；
S48α1N4001699/2400、S96α2N8002390/4800。L24已比较160/210场对，尚待完整raw复核；
40042继续EON完整预算，43422完整L24档增长中，不能提前stage。未采用延长、未push/PR。

2026-11-09 01:00 UTC：ada59feff已本地保存完整N200/原L12-L24报告，25files1967275B、
18源哈希和6份MD检查通过，无push/PR。L24原生200步及10步数值重放已00:53:11全部
return0，2134.290635794/115.962032540s、各2Gswap0、零事件、空scope；44437现在比较
210五场对及11原生状态，44493等完整证明后重算。尚无6400→7200采用。

[四组参考前缀](../research/data/reference-full-load-prefix-20261109t005527z/README.md)已00:55完成，
分别至6800/8300/3600/1500，续算段2800/3300/2500/900步所有FS/MS行严格<1e-10；
前三组分别有400/1900/400满载步，ν0N200仍在ramp。最大最终迭代数均3，最差比4.2e-11。
44808已00:57:38捕获94files/6parts7656276B并整档Git回读；不再等待，不等于完整资格。
同时保存未执行的review-length24-extension-execution.py及只读v5状态器，不创建新生产。
40042仍分析EON预算，43422原L24完整轨迹还在捕获。六组长程继续，失败阈值不变。

2026-11-09 00:42 UTC：HEAD98ee0f93已完整保存α1N200全部79包及L24审计/证明计划，
84files695038377B、8份MD校验通过，未push/PR。40040已00:31:54 completed6400+600态
审计：五场末两周期max2.49414575e-7、kin0、mass1.1058862e-17、div1.0733491e-17、
J正均通过，Lamé均值1.23763990%通过2%；40042自00:32:08分析EON自己的完整误差预算。

42097已00:36:47完成原L12/L24长度kernel，旧父/数值子仍退休。两者Lamé均值通过，
但L24周期仍FAIL；动态径向幅值3.71209e-5/9.57156e-6、相位差-73.41246度，是有限长度
响应差异，不能只解释为端部离散误差。[完整报告与静态后继](../research/data/elastic-n200-audit-and-length-summary-2026-11-09/README.md)
保存两份完整600态报告、资源收据、原kernel和未启用延长脚本；原始大轨迹仍由43422捕获。

44437原生重放仍运行；44493完整raw复核等待。新增44619/session32219于00:39:07
排队捕获其终态完整证据，成功或失败均保留，等待阶段无锁；之后CPU18nice19/原队列锁，
必须全部自有scope空。未来档length24-native-extension-proof-2026-11-09尚未开始。
extend-length24-native6400.py仅inspect/static检查：ready=false，工作/输出/status均不存在，
SHA469f78e7ca3d7bb58a3042e2d95ee759a14c2c6160011d0fdfa98dfc28fe094c；不得提前prepare/run。
仍须完整证明+复核，再准备具体6400→7200计划并自审；原c32失败和原长度对照不覆盖。

2026-11-09 00:26 UTC：S24 EON N200已00:06:48完成6400数值并进入末600态审计，
不是整体资格完成。L24末600态审计已00:00:47完成：固体速度两次周期max
1.092453015494461e-5/1.0567924362696135e-5，仍FAIL1e-5；其它四场及kin/mass/div/J通过。
Lamé均值误差1.5596774818%通过2%，不能覆盖周期失败。42097仍等待实际L12审计后
执行原长度比较；43422正在捕获完整L24档，旧7713/42141继续退休，不恢复。

[L24审计与独立重放计划](../research/data/length24-periodic-audit-and-native-proof-plan-2026-11-09/README.md)
保存完整审计、416个原始文件哈希、两个原生端点核验和具体计划自审。新44437/session22841
于00:15:38启动6200→6400重放，原2692/MUMPS/chord、CPU14nice19共享、2Gswap0，
只将最终步改7200并每步保存。随后6390→6400重放；需要210场对及11个原生边界完整比较。
新44493/session37385锁外等待完整证明后再重读全部对照，没有自动延长生产/新物理通过。
proof status length24-native-extension-proof-current；review status length24-native-proof-review-current。

[完整S48α1 N200档](../research/data/womersley-alpha1-n200-lu32-complete-2026-11-09/README.md)
已00:09封存4116files/79parts1920613192B，整档普通Gitblob回读已完成。
b002c068已本地保存前48包，剩31包及完整metadata本次保存；速度1.0164445542%仍FAIL1%。
原首个受限调用无法写D对象库、未改索引，记录保留；明确D写入后同helper/同字节成功。
42447现等40998 N400全家族完成；未push/PR。00:24完整步：ν.3fine6709/12800、
ν0fine8123/12800、ν.3time3537/6400、ν0time1352/6400；S48α1N4001289/2400、
S96α2N8001995/4800。所有未通过物理门槛及未完成预算保留，不以存储完成代替验收。

2026-11-08 23:54 UTC：本地HEADadddc7e已保存LU/时钟局部源码复核与契约修正，未push/PR。
[S96α1后续执行静态准备](../research/data/alpha1-s96-execution-preparation-2026-11-09/README.md)
保存未启用的准备器/执行器与22项实际检查：两种rank策略的命令逐字对应原准备器，20项错误
配置被拒绝；真实只读预检ready=false，计划目录/执行状态均不存在。六份冻结分析/研究源与
已完成粗算例一致。没有新细长程采用；43221/43241仍等待40998完整家族和实际筛查/复核。

23:50完整步：EONN2006164/6400正式采样；nu.3fine6454/12800、nu0fine7806/12800、
nu.3time3289/6400、nu0time1065/6400；S48α1N400980/2400、S96α2N8001721/4800。
L24数值6400已完成、600态有界审计仍进行；42447的alpha1N200完整档仍增长。
所有原物理失败、未完成预算与最终交付自审要求保持，不重跑未受影响的数值测试。

2026-11-08 23:34 UTC：本地HEAD7ed5a5ddda43b7d3af4a51d35c3a054062f0ab54已完成整个
S96 N400的84包和metadata提交，工作树此前干净，无push/PR。所有对应stager/finalizer已结束。
[LU与时钟源码复核](../research/data/solver-clock-source-review-2026-11-09/README.md)确认十五份
相关源码/测试与已执行验证逐字一致；本次仅修正架构文档的默认/显式缓存区别和系数刷新说明，
未改运行时、未重跑无关测试，完整交付审查仍待物理证据齐备。

23:31完整步：EONN2005894/6400已正式采样（新子43983）；nu.3fine6308/12800、nu0fine
7627/12800、nu.3time3149/6400、nu0time904/6400；S48α1N400800/2400（新段44029–32）、
S96α2N8001561/4800。L24数值6400已完成，42097仍做600态有界审计，旧7713/42141禁止恢复。
42447捕获alpha1 N200增长中，43422/43808按原完成条件等待；没有新细alpha1长程采用。

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



## 48小时连续研发启动 / 2026-11-07

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


UTC18:53覆盖：HEAD224aad5；S48alpha2N400在18:44:12完成全部2400和完整预算。
时间/尾项/采样六个相对空间项均PASS：U时间.0161463、采样.0387633；P时间.0210419、
采样.0386377，均小于.1；但N200/N400速度解析门槛仍FAIL1%，总体passed=false。
25665已退出不恢复；31707于18:44:21开始真实200seed的old-vector8筛查，未采用/未暂停old。
39748于18:44:43开始完整S48归档，增长中不stage。39865细1200态补审计仍在运行。

完成[跨盘Git证明](../research/data/git-cross-drive-storage-proof-2026-11-09/README.md)与
[只追加对象存储](../research/data/git-external-object-storage-2026-11-09/README.md)：完整249028B
样本Windows/WSL读回及独立--no-local clone一致、无alternates依赖，strict fsck通过。
实际checkout仅新增D对象库和relativealternate/junction，未移动或删除既有对象、未改
Gitconfig/ref；storage-probe普通blob仅存D且双平台实际索引回读通过。新分批stager保持
D4GiB+全batch+64MiB、C4GiB+64MiB预留，已有暂存+新batch限1.5GB，每part全SHA回读。
完整55files265116B已捕获/实际Git回读；首次过宽GIT环境preflight拒绝保留。
无push/PR，物理门槛不变。

UTC18:35覆盖：HEAD9d9ce99保存有界审计修正和769文件四档，无push/PR。
40213交接已18:32:22完成，当前独立nu0预算为40214，status
reference-nu0-native5000-bounded-budgets-current，work/reference-nu0-native5000-bounded-budgets-9d9ce99。
原39162已cancelled_before_analysis，不恢复；仅此无子任务/无锁等待器收到SIGTERM，
39157及所有数值生产者未signal。独立40183 review通过.612646s/10969088B/2GiBswap0。
四个实际函数路由检查覆盖EON、fine完整restart-chain、coarse/time实际family日志；
nu0 kernel逐字不变，最终EON连接39865新有界审计。完整86文件73816B已40219捕获并
实际Git回读，见[分析消费者交接](../research/data/reference-nu0-bounded-budget-consumer-2026-11-09/README.md)。

S48 alpha2 N400完整解析分析已完成：U1.0459910557%仍FAIL1%，p.1907398426%、
Qamp.5183525706%、phase.1019895043deg、net1.32554e-17、末周期U/p6.49e-15/6.15e-15。
N200→N400时间场差relativeRMS U.0001445713146/P.0001901804033；还需最后空间差分母、
tail/sampling才能判预算。25665在继续tail，未completed；31707仍等待，不能跳过。
39865细1200态补审计仍运行；39984只等待它完整后捕获，S24物理资格尚无新结论。

UTC18:22最高优先：HEAD6bce127尚无push/PR。39845完整1200态粗审计验证已18:11:49
PASS，除分析器SHA外所有值精确一致；566.535979s/峰值36995072B/2GiBswap0/零事件/
空scope。Windows/WSL各9项，旧缓存缺陷复现。两根源码已验证、待本地提交；证据见
[有界内存验证](../research/data/pressure-audit-bounded-memory-validation-2026-11-09/README.md)。
39865于18:14:31开始新S24细1200态audit，无数值重跑，原OOM/39197/39393失败仍保留。

39567边界1600已18:12:10完成，39575独立回读通过。24对态264HDF和五P1、legacyclock0，
候选成本对前后baseline比.3703195674/.3454892791；完整证据见[331文件证明](../research/data/elastic-n200-native1600-boundary-proof-2026-11-09/README.md)。
未执行helpers已修正新分析器/新N400路径/旧消费者已失败事实；3种实际函数命令路由
检查通过，参考续算使用显式restart-chain，worker/误差预算kernel逐字不变。
40013独立handoff review已18:16:34 PASS，242原始文件SHA、24.110960s/10334208B/零事件。

40040/session50611真正18:17:35采用native1600，原33828/33829已按计划SIGINT退出；仅
原求解器收到信号，无额外cleanup。原1601..1647接受尾段保留并排除，不能恢复旧族。
status elastic-n200-native1600-current，work/elastic-n200-native1600-handoff-32fb313，
D/elastic-s24-l1-n200-mumps-chord-native1600-32fb313。同2692/MUMPS/chord/CPU18/2GiBswap0，
1600→5800+600samples→6400。当前有效nu.3预算40042，status elastic-s24-native1600-budgets-current。
[实际交接75文件](../research/data/elastic-n200-native1600-handoff-2026-11-09/README.md)由40067完成，排除增长结果。

独立nu0实际5000交接307文件6包66801540B已Git回读，见[完整封存](../research/data/reference-nu0-native5000-handoff-2026-11-09/README.md)。
39157新细研究仍运行，39162旧消费者最终EON路径尚需另行路由，不改其冻结源。
39984/session44417先完成验证56文件249028B、1600证明331文件64272852B，目前只等39865
完整后捕获S24全部sample/旧OOM及失败消费者/新审计；status bounded-audit-boundary-capture-current。
39748仍等两Womersley N400完整分析/预算后归档。S48已2400，18:17:05转n400-analysis，
不是completed；31707/38449继续等它全完。18:20其余步：S96N4001895/2400、alpha1340/1200、
nu.3N4004366/12800、nu0N4005144/12800、EONN200新1637/6400、refN2001246/6400、L244936/6400。
所有物理失败及门槛保持，不将优化/归档或步数完成当项目验收。

UTC18:06最高优先：HEAD6bce127已保存498文件三档，无push/PR。S24 EON N400确已
12800，但37886的1200态审计17:55:43触及2GiB上限，memory.events max36/oom1/
oom_kill1、return-9、876.028295s、scope空；数值sample资源return0/零事件。原失败
保留，不重算数值、不恢复37886。39197捕获与39393预算均已正确failed，不能恢复。

根因是audit_pressure_tube.py保存整400相位的节点字典，内存随网格×相位增长。根代码
改为保留路径并按原顺序重读上一周期状态，公式/阈值不变；测试新增弱引用跟踪并以
非零周期漂移检验相位/RMS，Windows9项PASS。39845/session44114冻结验证在运行，
status pressure-audit-bounded-validation-current，work/pressure-audit-bounded-validation-6bce127；
旧版本同测试确实失败，新版本WSL9项通过，目前coarse全1200态与既有报告逐项比较。
两源文件scripts/audit_pressure_tube.py、tests/test_pressure_tube_audit.py尚未提交。
39865/session60206新finish-s24-bounded-audit.py仅等验证成功后重做审计，status
elastic-s24-bounded-audit-recovery-current，work/elastic-s24-bounded-audit-recovery-6bce127，
未来D/elastic-s24-l1-n400-bounded-audit-6bce127；新PVD索引引用不变旧VTU，输入前后SHA。
尚无新审计结果。既有参考运行源仍冻结；后续消费者必须连接新审计状态/路径。

先前未执行的EON1600正式handoff/reviewer/budget helpers现已过时：它们仍要求已失败的
39393活着、仍指向失败的37886，不得prepare/run。需改为新分析来源/路由并重新审查；
消费者重审参考报告时还须保留restart-chain路径，不能把续算日志当全程日志。
39567边界1600筛查已18:04:11实际old-first，39575独立审查等待；原33828/33829继续。
这两个冻结筛查器不改，仍没有正式EON采用或原进程signal。

39157独立nu0已17:59:41真实5000→12800，原20277家族与38384自然退出，原失败保留；
新seed1419728B/time78.5398163397418/SHAbfc1a4cb2e75145dce204edc09b4b7c98d663a6974d63000a6d1dafde9750e91。
CPU9+23、2GiBswap0、ILUT仅细N400；39162仍等待完整family，未来EON比较也须新审计路由。
39231实际交接捕获已18:03:03 completed，尚未Git暂存。旧族不得恢复。
39748/session42018新capture-alpha2-n400-final-families.py自17:57:04等S48完整预算后
串行捕获S48/S96 N400全轨迹，status alpha2-n400-final-capture-current，work/
alpha2-n400-final-capture-6bce127。增长中不stage；后续大档须按实际体积分批本地提交。

UTC17:51覆盖：HEAD32fb313保存前一完整N200参考后端证明，无push/PR。新39392已
17:49:23真正采用原生1100→6400，status reference-n200-native1100-current，原29899/
29901及旧39174均已自然退出，不能恢复。全1..1100共2200最终FS/MS行通过，最大比
5.7e-11/9.4e-11；seedSHA d97860c924c3995b426521bffff79937eda3d1eb6477c7b3ef5367a20ba37100。
39393现为有效nu.3预算消费者；CPU20、2GiBswap0和全部物理/时间/输出/容差保持。
39401完成135文件2包10488872B；旧convergence-svfsi命令/日志前缀另由39661补存7文件
3204B，未修改冻结捕获器。见[实际1100交接](../research/data/reference-n200-native1100-handoff-2026-11-09/README.md)
与[失败审计补档](../research/data/reference-n200-native1100-audit-tail-2026-11-09/README.md)。

39418真实1400 EON选项筛查17:34:58完成。old-first/MUMPS-chord/old-last8态分别
170.780458337/50.510200381/161.065220538s；候选成本比.295761/.313601。全部24对态
264HDF数据集及五场P1最大history5.0923282e-16、node7.4593109e-17、mass3.3598051e-14，
legacyclock差0，4+4重放通过。首次39468复核错误地对SuperLU_DIST也要求MatLUFactorNum
而失败；真实旧事件MatLUFactor16，新MUMPS数值分解8，原失败2.029150s/零事件/空scope
保留。新39531/session76071于17:40:52独立回读通过78.776539s/89337856B/2GiBswap0。
39559已17:48:56完成356文件6包64292392B，见[完整选项证明](../research/data/elastic-n200-mumps-chord-option-proof-2026-11-09/README.md)。
这只是中段ramp局部成本，不是满载或物理资格；未采用到正式EON。

新39567/session57096等待原生1600，helper screen-elastic-n200-boundary1600.py，status
elastic-n200-mumps-chord-boundary1600-current，work及D/elastic-n200-mumps-chord-boundary1600-32fb313。
独立39575/session15721等待完整筛查，status elastic-n200-boundary1600-review-current。
原33828/33829继续。continue-elastic-n200-native1600.py、独立handoff reviewer和只换
EON N200路径的budget helper仅已写好/语法检查，没有prepare、发信号或正式采用。
必须完整边界证明、原进程身份/完整前段/资源/预算算术审查后才允许具体交接。

S24 N400 EON于17:41:06已12800并转1200态audit，37886仍运行审计，尚非completed；
39197继续等完整审计才归档。17:49其余完整步：nu.3N400参考4214、nu0参考4904；
N200 EON1558/reference1099（随后实际1100接续）；L24 4804；S48/S96alpha2 N400
2288/1695；alpha1 328。39157仍等nu0自然5000，31707/38449仍等S48N400完整完成。

UTC17:29覆盖：HEADb8b3a78已保存实际4000交接218文件档，无push/PR。38663 N200参考
对照17:05:41 completed，38676独立复核17:09:38 PASS。原100/候选100/重放10成本分别
3004.393521160/1590.483061353/167.676861234s，候选约减少47.1%；node1.84314369e-17、
P1mass4.48271050e-15、nativehistory2.95572486e-15、保存范数0、物理时间exact，候选
重放算法字节除诊断elapsed/padding完全一致。独立复核236.938041s，原基线逐字导入、
原失败保留。39299/session11348已17:23:44完成556文件10包279699816B，正在实际Git
回读，见[完整N200后端证据](../research/data/reference-n200-midnight-backend-proof-2026-11-09/README.md)。

新39392/session61477已17:21:06请求原N200参考在1100自然停点，当前仍adopted=false；
helper continue-reference-n200-native1100.py，status reference-n200-native1100-current，
work/reference-n200-native1100-handoff-b8b3a78，未来D/reference-s24-l1-n200-ilut-native1100-b8b3a78。
原29899/29901仍正常算至1100；全前段及原生seed核验、全部原进程退出后才同CPU20/
2GiBswap0采用候选继续6400，物理/dt/容差/输出不变。独立39364已17:19:58通过；首
39331仅缓存文件比较失败1.530293s/零事件/空scope，保留，真实源码比较不放宽。
新39393预算elastic-s24-native1100-budgets-current只等采用，N400路径仍为38880；
worker/匹配报告与预算算术逐字不变。旧39174届时自然failed，不能恢复或改冻结源。
39401/session68252只等实际采用后捕获参考封存证据，明确排除同目录仍运行的EON输出。

39418/session27399新elastic-n200-mumps-chord-screen-current已17:26:15运行old-first。
work及D/elastic-n200-mumps-chord-screen-b8b3a78，真实1400seed、原2692binary，CPU16
共享nice19、2GiBswap0/10GiB入场/8GiB底线。前后两次默认8态包围MUMPS/chord8态与
4+4重放；全24对态current/history/五场P1、legacyclock及相对两基线均至少20%节时才
eligible，无自动采用、不暂停原33828/33829。它只是中段ramp筛查，不是满载物理资格。
17:28正式步数S24 N400 EON12661、nu.3ref4122、nu0ref4777（各12800）；S24N200
EON1489/ref1051（各6400）；L24 4722/6400；S48/S96alpha2 N4002208/1567（各2400）；
alpha1 321/1200。39157仍等原nu0自然5000，39197仍等完整EON采样及审计。门槛不变。

UTC17:08覆盖：HEADfce909d已保存跨午夜诊断修正与344文件完整证据；无push/PR。
原nu.3细N400于16:59自然完成4000，5055/6701均退出；旧完整12800审计、37988交接、
37989预算和38175捕获按旧冻结规则failed，全部保留且不得恢复。新38880/session80017
已17:00:01真正采用4000→12800，status reference-fine-ilut-continuation-midnight2-current，
work/reference-fine-ilut-handoff-midnight2-a0a4675，D/reference-s24-l1-n400-ilut-m4000-midnight2-a0a4675。
完整1..4000共8000最终方程行通过，maxFS5e-11/MS9.8e-11；seedSHA edbb57065220bbfe9e8e5e4c8c977e888344ecd4aeb8e5b4a74ee34e85ca5bdd。
新39174消费者elastic-s24-midnight2-budgets-current等待正式生产，预算算术不变。
38891已17:02:09完成218文件5包32434744B；17:06:38实际Git回读通过，见
[原生4000交接证据](../research/data/reference-fine-native4000-handoff-2026-11-09/README.md)。
不包含增长中的新计算输出，采用不是完整物理资格。

独立nu0新39157/session4177已16:59:28请求原生5000自然停点，尚adopted=false；
status reference-nu0-native5000-family-current，work/reference-nu0-native5000-family-fce909d。
原20277/21425/21426继续计算；新39162消费者等待，不持分析锁，39231/session83817
只等实际采用才捕获。独立39073已126.408616s/169283584B/2GiBswap0/零事件/空scope
完成原生停止、后端、输入、源码及原nu0预算算术回读。后续细N400用已验证ILUT，
未运行的粗N400/细N200仍用原binary/原两rank/原导出输入；固体nu.3不变。

17:06完整步：S24细N400 EON12454/12800、新nu.3参考4027/12800、nu0参考4657/12800；
细N200 EON1420/6400、参考1004/6400；L24 4634/6400；S48/S96alpha2 N4002120/1442
（目标各2400）；alpha1 314/1200，九组正式数值进程均实际运行。39197/session64613
等待37886完整1200采样及审计后才捕获S24细EON。38663的N200候选100+重放10已17:05:41
screen通过且eligible，38676独立回读仍进行，尚未采用N200后端。原alpha1筛查31707及
独立审查38449继续等25665完整结束和资源，不暂停原alpha1。全部物理及预算门槛不变。

UTC16:45：跨午夜完整证据38827已16:44:20 completed，344文件4包134713104B，正在
实际Git回读，旧失败与基线全保留。新4000接续独立38854已16:41:21 PASS，69.066164s/
177700864B/2GiBswap0零事件空scope；新的38880/session80017自16:42:23在锁外等旧37988
自然边界及诊断审计失败，status reference-fine-ilut-continuation-midnight2-current，
work/reference-fine-ilut-handoff-midnight2-a0a4675，仍adopted=false。候选目标
D/reference-s24-l1-n400-ilut-m4000-midnight2-a0a4675。未来新budget是
elastic-s24-midnight2-budgets-current（尚未spawn）。38891/session19819只等真实采用
再捕获，status reference-native4000-midnight-capture-current；原38175届时的失败也保留。
后来的成功审查/接续证据由新38891捕获，不混入先完成的344文件验证档。无push/PR。

UTC16:40覆盖：HEADa0a4675，九组正式生产继续，无push/PR。16:33完整步为S24细N400
EON12159/12800、原nu.3参考3911/12800、nu0参考4478/12800；细N200 EON1326/6400、
参考932/6400；L24 4508/6400；S48/S96alpha2 N4001993/1262（目标2400），alpha1
304/1200。步数不等于资格。38449/session74060独立alpha1审查已锁外排队，仍先等31707
真实筛查及25665释放资源，没有采用或暂停原alpha1。

新发现：N200后端筛查37691的old100在16:18:10数值return0、3004.393521s、零内存事件
且scope空，但旧解析器拒绝跨北京时间午夜后的负诊断elapsed，控制器与37700审查
均failed，保留且不恢复。固定svFSI UTIL.f只取当天秒数，OUTPUT.f将此差写入日志和
native记录；物理时间未倒退。当前4文件修正仅接受有限带符号诊断elapsed，物理时间、
保存范数、残差、全历史与SHA要求不变。Windows相关6+16、CI26测试及WSL28+8通过；
真实old100严格收敛通过，700算法字节除elapsed完全重现原700，双rank4400已真实解码。
WSL最终验证38611耗4.083539s/33239040B/2GiBswap0/零事件/空scope。首次“所有rank均
应负耗时”的验证断言失败保留；只有master计时起点相同，非master可仍为正。

38663/session63590新screen-reference-trilinos-fine-n200-midnight.py已16:32:36运行ILUT100。
status reference-trilinos-fine-n200-screen-midnight-current，work/reference-trilinos-fine-n200-screen-midnight-a0a4675。
原成功old100完整逐字复制，资源成本仍取实际3004.393521s，不重跑或更改原失败；随后
690→700重放10态与完整比较。38676/session75952独立review-midnight等待；无正式采用。
38827/session80874正在捕获reference-midnight-diagnostic-audit-2026-11-09，包含原失败
old100、两次验证、固定上游源码和CI失败/成功；增长档不能暂存。

原37988仍等待自然4000，冻结旧解析器预计会拒绝跨午夜prefix，不能修改其源。
新reference-fine-ilut-handoff-midnight2-a0a4675已prepare，definitionSHA
5e75f2d05071e3dfe8cf8072dc922f37082d17c1def3aa256c5f3df31961e730，尚未run或采用。
首prepare在创建目录前变量名冲突、首review因无目录退出；第二review38803仅在比较
Python缓存而非源码时失败32.650046s/零事件/空scope。38854/session80612独立retry3
只区分缓存与真实源码，继续全proof回读，不能提前声称通过。新控制器只允许旧37988
自然失败、所有原进程退出且完整4000收据通过后接续，不重写STOP_SIM，不signal init.scope。
原nu0消费者38384及原N200/nu0家族的冻结旧审计也需要后续显式修正路由，尚未完成。

UTC16:11最高优先：HEAD73a8c4f保存完整S96细N2001672文件44包1820122244B；
57变更文件/1821244349索引blob字节/最大44682612B，6份MD链接及元数据字节检查通过。
旧nu0预算20925已16:09:15经PID/start3575499、无子任务/无锁核验后退休，不得恢复；
新38384/session46596，reference-nu0-recovered-budgets-current，work/
reference-nu0-recovered-budgets-ad31460，waiting_for_reference_family，不持分析锁。
原20277三组数值队列未改。独立38359审查通过，预算tail SHAead574f634cb6713581244325d3f71690796bb17b5b74b56e5422187c1dfa078
逐字不变；后续EON比较连接已审核的11600恢复，同版物理报告一致性要求保留。
审查1.023214s/16138240B/2GiBswap0/零事件/空scope。38413已16:11:04完成57文件
1包431780B捕获，实际Git回读通过，保存本地检查点。原参考37988仍等4000，38175
只等真实采用再捕获。N200筛查37691仍old100（16:10约682/700），没有采用候选。
无push/PR，所有物理门槛及待验预算不变。

UTC16:01覆盖：HEADad31460已保存两份停止/恢复交接档案540文件11包90162492B，
工作树已核对。36172的S96细N200完整捕获15:56:24 completed：1672文件44包
1820122244B；准备独立本地提交，避免与其它大档案合计超过单次对象预算。六项初步
解析/周期门槛通过，最细N400和全部误差预算仍待完成；原S48速度1.046822%失败保留。
实际9组正式生产仍运行：S24恢复sample11844/12800、原参考3815/12800、nu0参考
4323/12800、S24 N200 EON1225/6400/参考871/6400、L24 4376/6400；S48/S96alpha2
N400为1864/1088（各目标2400），alpha1N200293/1200。步数不是物理验收结果。

新38175/session15667自15:56:23等待37988真实native4000采用，状态
reference-native4000-handoff-capture-current，work/reference-native4000-handoff-capture-ad31460；
仅实际采用后捕获封存原轨迹/原失败/新seed及不可变交接，排除增长中的新结果。
当前37988仍waiting_for_native4000_boundary/adopted=false，37691仍N200old100。
只读发现nu0预算20925的最终跨程序比较仍连接旧EON失败路径，正准备独立新消费者；
尚未更换20925、未修改20277冻结数值队列。无push/PR，全部门槛不变。

UTC15:52归档覆盖：38013已15:49:04 completed，恢复/修订交接283文件3包27683596B
已15:50:55实际Git回读PASS；停止证明257文件8包62478896B亦15:42:39回读PASS。
两份完整档案共540文件11包90162492B，README和原失败说明已补，准备保存本地commit。
36172的S96完整N200仍增长，不包含在此提交。15:49实际S24恢复采样11725/12800、
原参考3782/12800（仍等4000，未采用）、nu0参考4270/12800；S48alpha2N4001819/2400、
S96alpha2N4001025/2400、alpha1N200290/1200。全门槛不变，无push/PR。

UTC15:43最高优先覆盖：7140/7209已在15:18:34退出。400→11600预热全部成功、
完整v3检查点11600有限且封存；随后旧guard要求22/23皆空闲，撞上已授权nu0参考21426
的CPU23而失败，尚未运行sample。7593预算等待器15:18:40因此failed并退出。两原状态
和全部轨迹保留，不恢复旧PID，不改旧guard。此前“9组原生产继续”不再适用。

新37886/session33816（work/elastic-s24-sample11600-recovery-abec003，状态
elastic-s24-sample11600-recovery-current）已15:35:34实际从11600继续1200步sample，
D/elastic-s24-l1-n400-sample11600-recovery-abec003。原2692二进制/MUMPS/chord、
原case/dt/容差，CPU22、2GiBswap0、10GiB入场/8GiB底线；明确与CPU23 guest sibling
共享，不宣称宿主物理核隔离。独立37909已审查11601/11602：每态11个HDF数据集、
全部历史/旧v3clock与五场节点/P1mass差全0。新采样未完成，不等于物理验收。

37533已15:25:45完成两粗网格同版审计，所有物理指标完全一致；37566停止证明捕获
15:28:04 completed，257文件8包62478896B，正在实际Git回读。旧abec003交接prepare
因旧预算先失败而未执行，保留原定义/审查，不修改。新37948已15:39:01完成修订审查，
复用字节核验的同版粗报告并重读停止/后端证明；41.435s/182452224B、零事件/空scope。

37988/session90386已15:40:00真正请求原nu.3参考在4000正常停点，状态
reference-fine-ilut-continuation-recovery-current，control/reference-fine-ilut-handoff-recovery-abec003，
future D/reference-s24-l1-n400-ilut-m4000-recovery-abec003。新定义SHA
603227c6604d182f070ca20afe1d7141cf37b2255e75507edf3b8efeb61878b5；新预算37989
elastic-s24-recovered-budgets-current只waiting_for_handoff_adoption，绑定新EON采样路径。
旧7593已经自然失败，无信号；5055/6701继续算到4000，没有被暂停/kill，也绝不signal
init.scope。当前adopted=false，尚无真实4000接续。20277/20925和原N200参考不在交接内。

37691的N200600→700独立screen已15:28:06开始old100；37700仍等待完整screen。
38013/session39658自15:41:56捕获封存预热、旧失败、重启证明和不可变新交接，目标
elastic-s24-sample-recovery-handoff-2026-11-08；排除增长中的sample/参考结果，未完成
不得stage。36172完整S96细N200仍增长，15:28约33包1.422GB含正在写包。HEAD仍abec003，
无push/PR，所有物理失败及完整误差预算门槛不变。

UTC15:22覆盖：原9组正式生产继续。15:17完整步为S24细N400 EON11595/12800、
原nu.3参考3684/12800、nu0参考4112/12800；细N200 EON1087/6400、参考786/6400；
L24动态4193/6400；S48alpha2N4001689/2400、新S96alpha2N400848/2400、
S48alpha1N200279/1200。此处只报已完成步，不代表完整审计或物理资格。
37533已完成粗EON的同版重审计，所有物理报告值逐项完全一致；粗参考重审计仍在运行，
尚未写交接review，也未请求正式4000停止。36172与37566的归档状态未提前改变。

新增37691/session93901独立N200后端screen已15:21:19排队，状态
reference-trilinos-fine-n200-screen-current，work/reference-trilinos-fine-n200-screen-abec003。
真实原600/700检查点已逐字复制；原生1rank/CPU16nice19/2GiBswap0，先等37566捕获
完成再取probe锁，原100步必须逐字重现原700，然后候选100步及690→700重放10步。
节点/全部原生history/norm<2e-9、P1mass<1e-8、native时间exact、成本比≤.9不变。
这属于N200早期ramp，不能用N400或S12结果代替，也不自动采用。归一化使用完全相同
物理量/几何尺寸的既有尺度，N200原case本身及dt保持不变。37700/session32509独立
review已排队等screen完成；现无新数值结果，未暂停或切换29899/29901。

UTC15:07调度覆盖：旧eonsim-new-48再次update仍返回不存在；本地只找到另一聊天的
旧暂停任务eonsim-5-4，未改动。按本次已授权的剩余48h窗口，用应用工具创建当前聊天
heartbeat成功返回id=eonsim-new-48/statusACTIVE；实际automation.toml回读确认当前
thread01a1abd8-e4e7-7603-b1fb-c9c9767ba76a、每30分钟、截止UTC11-09 12:59:10。
提示要求先读仓库最新记录，只在重要变化时通知。此记录覆盖此前“唤醒未生效”，
但定时器存在不代表全部研发完成，也不保证机器或应用离线时运行。

UTC15:00覆盖：HEAD abec003e4df8a8444285ced8974db20ba8173862 已保存完整两后端证明
1104文件/26包565348664B；43变更文件/566446184索引blob字节，5份Markdown链接通过。
无push/PR。36172仍捕获完整S96细N200，14:58约22包/936MB（含增长包），尚无完成索引。

原生正常停止小试37309/session18693已14:57:40 completed：单rank2800→2810、双rank
2600→2610，固定原二进制/原100步输入未变，仅各自results/STOP_SIM指定提前正常退出。
两组各10态的五场、全部原生算法历史/保存范数/时间与既有不中断oracle一致，排除的
只有elapsed与双rank padding。零事件/空scope；不据此宣称长期后端采用或物理合格。
首次36325错误地把STOP_SIM放在输入cwd，未按2810停止；14:49:12只取消此独立小试，
失败、部分状态、原生控制器和清理收据均保留，没有信号发送给正式生产者。

已准备但未执行continue-reference-fine-ilut.py：work/reference-fine-ilut-handoff-abec003，
definition SHA2bf29d18b40a928595b7e4177b51f46abc9ae1310610ae55156efacb4503e8a2。
计划在原nu.3细N400真实4000边界正常退出后，原生1rank/CPU8/2GiBswap0以已审查ILUT
继续至12800；新消费者保留原预算算术，所有报告须同版分析器且物理值不变。
独立37533/session3878正重读停止证明/后端绑定并重算已完成粗配对的匹配报告。
尚无handoff-review、正式STOP_SIM、adoption或新长程进程；5055/6701/7593与20277/20925
都未改变，不得把准备状态当作交接。控制器只允许向身份校验后的旧空闲预算PID发信号，
不能向共享init.scope发信号。原程序提前结束后的完整12800审计失败须原样保留。

UTC14:25归档覆盖：HEAD16aa5db761b2b06ce2192082a203e36e6711cc41已保存v2审计修改
与三档6079文件/29包440993104B，72变更文件/446251072索引blob字节，9份Markdown
链接通过。36093现已14:15:03 completed，两完整后端证明1104文件/26包565348664B
已14:21:09实际Git回读PASS，待本地提交；不再等待36093。36172正在capturing_fine_n200，
该新S96完整轨迹仍增长，不stage。原参考生产和预算等待器均未切换；无push/PR。

UTC14:17最新覆盖（本地HEAD27f5c82，尚无push/PR）：S12参考完整6400链、800态审计及
同版分析器的200相位对照已12:34:16完成；原timeout、MPI收尾失败和分析器身份拒绝
均保留。S12两程序Lamé约4.8026%FAIL2%，参考ALE末两周期约2.625e-5FAIL1e-5。
S24粗网格两侧12800步及400相位对照也完成，Lamé约3.1950%FAIL、参考ALE约2.2113e-5
FAIL，中p幅值差3.112885%FAIL2%；不能将完整比较记作物理资格。
两份完整档案共6001文件/28包/440929264B，实际Git回读已PASS；README已补。

新S96原生串行alpha2细N200完成1200和analysis，U/p/Q幅值误差分别0.475826%/
0.360074%/0.234326%，phase0.060445度、net1.0872e-17，六项初步门槛全PASS。
原S48细N200速度1.046822%FAIL保持。新S96 N400已启动，空间/时间/尾项/采样预算
仍待完成；新N200完整捕获36172/session61118排队，不把六项初筛作为全部验收。

14:10只读实际完整步约：S48alpha2N4001440/2400，新S96alpha2N400491/2400，
原alpha1N200254/1200；后者真实200checkpoint已存在。alpha1筛查31707仍在锁外等
S48 N40025665全部完成和22GiB资源，原20806/20825未改。弹性S24细EON N40010974/
12800、原nu.3参考3479/12800、独立nu0参考3789/12800；细N200参考655/6400，
EON仍运行（13:49为842），L24动态3948/6400。9组生产者继续，无活动暂停。

参考Trilinos细serial100+100+10及双rank100+100+10已分别13:10:22/12:04:48独立
复核PASS；成本比0.729680/0.765242，完整场/历史/原生时间和候选重放通过，未交接。
36093/session37552正在完整捕获两证明，仍增长，不暂存。新增显式v2全链审计仅允许
绑定同物理输入/真实rank布局/二进制/独立raw proof后的FSI-ILUT切换；旧v1仍拒绝
隐式切换。36128于14:09:48通过23参考+8压力测试、两真实proof绑定及原S12完整v1链；
Windows四个受影响测试通过。首次Windows短路径身份误判和首次捕获根目录拒绝均
保留。验证档78文件/1包63840B已14:16:36 Git回读PASS，核心修改尚未本地提交。

调度事实：13:54尝试更新原eonsim-new-48时，应用返回该automation不存在；没有
重建或宣称更新成功。当前聊天继续主动执行，全部生产进程独立运行；不得把本地
保存的待用prompt当作已生效的自动唤醒配置。原48h窗口和全部验收后才上传的约束不变。

UTC12:06覆盖：S12 EON完整3309文件/47包/402,206,344B已11:56:07完成实际Git
逐字回读，物理结论仍为周期/守恒PASS、Lamé4.80266%FAIL。mesh-IC完整50态数值
PASS，但20步105.186→149.428秒、成本比1.420609 FAIL≤.9，拒绝采用；与取消的
首个双rank位置试验共293文件/6包/56,537,864B已12:07:04完成Git逐字回读。

双rank34291于12:00:25完成：原100步1839.648800秒，ILUT100步1407.776664秒，
比值.765242074；节点/P1质量/native历史最大2.012e-16/3.164e-14/6.614e-14，
保存范数差0、时间exact，10步重放除elapsed/padding逐字一致。eligible=true但
adopted=false；独立34564正在复核，细串行34452已接锁运行原100步。

S12参考800态审计已PASS执行检查，但ALE末两周期2.624921e-5/2.624848e-5，
FAIL1e-5；其余四场周期、守恒与正Jacobian通过。34839在交叉比较因两报告
analysis_script_sha256不同而failed，34864随后正确拒绝归档。没有删除身份检查。
新35377/session72761（finish-s12-matched-source-comparison.py，status
reference-s12-matched-analysis-current）12:03:39以相同冻结分析器重算EON报告，
要求除脚本哈希外所有报告值完全相同，再比较观测量/200相位字段；不重跑数值。
35431/session46144 capture-v3在独立目录等待新完整审计，保留全部旧失败及同版EON报告。
33659 S24粗配对已12:04:04完成400相位字段分析并开始捕获，尚未完成归档。

UTC11:45覆盖：S12数值程序已6400且返回0，但30063于11:33:09因资源组残留MPI辅助
30077而failed。清理只SIGINT该辅助进程，scope已空、所有内存事件0；801场文件与最终
6400原生状态齐全。不得将原controller改成completed，也不重跑已结束的数值轨迹。
新34839/session47501（finish-s12-native-audits.py，status reference-s12-native-audit-recovery-current）
已冻结全部输出哈希并补审计：完整6400链/12800最终方程行PASS，FS/MS最大比
5.6e-11/9.8e-11，现审计800态。原34488归档等待器正确failed并保留；新34864/session5970
等待补审计完成，再归档原12h失败、收尾失败、完整原生链与全部输出，尚未捕获。

双rank34291原100态已11:29:21通过：全算法字节除elapsed/padding外与实际2700逐字
相同，history/norm差0、time exact；原段1839.648800秒，候选尚在2668/2700，重放及
独立review仍待。新34967/session69921在CPU15nice19/2GiBswap0做S12满载20态mesh-IC
内置选项小试；两臂均固定candidate/FSI-ILUT，只候选mesh从FSILS改Trilinos-IC，保留CG、
mesh物理和所有容差。占独立review锁，无主计算交接；不能提前宣布成本或数值通过。

UTC11:28覆盖：检查点`243c9d0784b18d55d8b267fa0554767f20ca7554`已本地提交61文件，
包含三档、审计代码与原始测试；没有push/PR。S12恢复约6376/6400，S96细N200实际保存点
已800。34291双rank原100态接近2700，独立review34564等完整试验；原nu.3细网格串行
34452排在同一probe锁后，实际2800→2900原100/候选100/重放10，review34585随后。
两试验的原网格、case、geometry、manifest和P1尺度已11:21:58独立静态回读通过；
数值与交接仍待完整验收。34488等待S12全部审计结束后归档原失败及完整恢复链。

只读核对当前40个提交的新对象：6,338,031,777B raw、最大单提交1,785,544,813B、
最大blob86,012,108B；可按1.9GB保守上限分五次后续快进上传。它不是实际网络pack测量，
也没有执行上传；全部验收后仍须复核远程实际引用与最终新增对象。记录在ignored
build/prod48-20261107/push-sizing-243c9d0.json，无凭据。

UTC11:05证据覆盖：双rank记录审计、串行Trilinos证明、S96 native粗时间对三档均已完成，
分别28/973/4953文件、1/5/17包，共465,596,100B。11:04:22至11:05:12全部实际Git
普通blob逐字回读PASS；代码、测试与相关记录一起保存本地检查点，尚无上传。
S12 EON档案28745仍增长，不能混入这次提交；双rank34291仍在原算法100步验证中。

UTC10:57覆盖：本地HEAD`1374b625b829f03c1d37fbc167cf390bc3aa8bb4`，没有push/PR。
S24 EON粗N400已完成12800及1200态审计：五场周期、运动学、阶段质量和正Jacobian
通过，Lamé均值3.195039%仍FAIL2%；原参考ALE周期FAIL不变。EON实际继任33828
在CPU18计算细N200，参考继任29899在CPU20。S12原生恢复30063约6212/6400；
S24 EON细N400约9038、原参考细N400约2893、细N200约268、独立nu0细N400约2847，
L24约3181/6400。各进行中结果不作为物理资格。

S96粗N40031784已10:22:34完成六周期2400步，六项初步门槛通过：U0.615600%、
p0.542559%、Q幅值0.518270%、phase0.074227度、net1.05e-17；末两周期场差约6.14e-15。
同粗N200/N400的U/P时间RMS差为0.001636009/0.004225703，仍需细层空间分母与完整预算。
29270细N200已经过600进入第四段；原S48细N40025665及alpha1原20806/20825继续，
实际200态筛查31707仍在锁外等待，未交接。

固定原码Trilinos启动及真实满载S12续算均已通过独立回读。启动20步588.202→340.256秒；
实际6000→6020的20步265.064→127.284秒，候选节点/P1质量/历史差分别1.839e-16、
4.546e-14、3.186e-14，保存范数差0、原生时间exact。6010→6020重放10态除elapsed外
逐字一致，10:53:00独立review通过。仅有有限串行证明，尚未采用新参考后端。

新双rank记录审计保持serial格式，显式核对各rank实际payload与固定RECL/padding；
19参考+8压力测试以及五份真实原生记录解码通过。它不等于实际双rank恢复证明。
首次双rank试验34174因CPU12与S12恢复/alpha1共享位置冲突，于10:56:09取消并清空
自有scope，保留全部失败证据。独立retry34291/session52411改用CPU10/16nice19共享，
先2600→2700 original100逐字匹配实际2700，再候选100和10态重放；主生产者不变。

证据捕获：28745仍写S12 EON完整档案；33919写S96 native粗时间对；34227已完成
28文件/2781956B的双rank格式验证档案，现写串行Trilinos完整证明；33659等28745结束后
做S24粗两程序比较并归档EON侧。增长档案不得提前暂存。仍未全部验收，继续计算与审查。

UTC09:58覆盖：本地`8297a417bbb405b5c44d93149c9a2aa6fa50af60`已保存原生重启审计、
针对性验证与四份完整档案；尚无push/PR。S12原生恢复30063约5918/6400，S12 EON
完整归档28745仍增长。S24粗N400原参考的1377文件/3包/109,010,096B已完成实际Git
回读，ALE周期失败不变；其EON侧约11545/12800。原参考细N400约2734、细N200约158，
独立nu0细N400约2597；不能将这些进行中结果写成验收完成。

Alpha1完整当前/上一时间层读取器在已归档启动样本上复核320数据集：节点/历史最大
5.4277761e-12、归一化P1质量最大1.9164191e-10，均通过；旧v3只按其已有时间契约，
新v4互比exact。实际200步checkpoint筛查31707仍锁外等待原N400完成、真实200态和
22GiB可用内存，未暂停原20806或替换20825。新S96粗N400伴随31784已运行至约892/2400，
CPU15共享nice19/2GiB，原细N200预算不变；29270细N200已进入400之后第三段。

独立参考后端试探31946/session95993于09:53:57开始，现构建固定svFSI原码自带的
Trilinos路径，使用本机已安装库、新目录、CPU16nice19/2GiB/swap0。原二进制和全部
原生产者不变。构建后仅20态FSILS/ILUT对照，完整字段、原生历史、收敛及成本均待验；
ILUT源码含零对角替换，不能假设只是等价预条件。没有采用或长期资格结论。

UTC09:12覆盖：本地`0029a7ea6ecaadea36d36a67781dbebb3e4b12fd`已保存三组Womersley
完整档案，未上传。S12原生恢复仍30063运行；有限重启证明443文件/4包/56,165,088B
已捕获并实际Git回读。新增审计CI映射亦完成：26项选择、6项证据检查，以及锁定
PETSc3.23.7 Release/Debug各1项Poisson均PASS，两程序二进制与既有60eb/c2c6完全相同。
该70文件/65,144B验证档案也已回读；16参考+8压力测试详见独立原生证明。

新失败指标必须保留：S24粗N400原nu.3参考6673已08:45:10完成12800及全场审计，
全步相对收敛、运动学和质量PASS，但31/32周期ALE位移差2.211333e-5/2.211283e-5
超过1e-5，因此periodic=false、不可用于通过预算。实际CPU20继任为29899，08:45:14
开始S24细N200；独立nu0系列20277照常运行，不混合两种网格运动方案。31614/session43442
已捕获新审计验证，现捕获完成的S24粗参考一侧，排除其仍运行的EON一侧；28745仍捕获
S12 EON完整输出。总体资格未通过、没有PR。

UTC08:58覆盖：S12原生20态续算、10态重放已PASS，五场节点/P1质量差均0，完整
序列化历史（除耗时）逐字一致、保存时间exact；不称为EON v4时钟。独立最终审查
08:50:55通过16项参考测试、8项压力审计测试及真实两段/三段收敛链；原1..5600
FS/MS最大最终比5.6e-11/9.8e-11，均严格低于1e-10。审计现在显式验证连续区间、
原生种子、全部输入哈希和被排除的原失败尾部；完整场审计不接受单个晚期续算日志。

实际恢复30063/session65771于08:52:59开始，work/s12-native-recovery-a6643c8，
D/reference-s12-native-recovery-a6643c8，status reference-s12-native-recovery-current；
CPU13nice19/2GiB/swap0/18000秒，原5600种子到6400，物理及容差不变。完成后自动
审查全收敛链、800保存态及同算例交叉对照；仍非完整资格通过。初次冻结审查缺测试目录
的准备失败、第一次资源竞态和原12小时失败均保留。30090/session51962正在捕获这些
已结束证据及恢复任务不可变定义，排除增长中的恢复结果。

三组已完成档案（S48细alpha2完整、alpha1启动、S96细执行路径）共3878文件、76包、
1,783,550,240B，实际Git索引逐字回读已PASS。28663两组捕获已08:43:53完成；28745
正在捕获S12 EON完整轨迹。继续本地检查点，尚无push/PR。

UTC08:39最高优先更正：原S12参考程序3224/3226在07:35:13触及原定43200秒限时，
最后完整5641步、5642仅部分迭代，**并未完成6400**。原失败、日志、5600原生重启文件
全部保留；CPU20锁释放后6673已07:35:17开始S24粗N400参考，不能恢复或覆盖旧任务。
新原生续算筛查仅验证5600→5620及5610→5620；首次29610在资源限制建立时检查过早，
未启动求解、范围已清空。修正仅等待最多5秒让限制建立，仍由子进程在执行前验证
2GiB/swap0，重试29691/session20654已08:36:58运行，CPU13共享低优先级。
状态reference-s12-restart-screen-retry2-current；数值、全历史及显式续算收敛链均待验收，
尚未采用完整6400续算，不能拼接日志冒充未中断计算。

新S96原生粗N200已完成1200；802保留态、20050数据集对既有四rank粗层全部通过，
节点/历史max1.0408341e-17，归一化P1质量max1.4500918e-16，v4时钟exact。
29270已08:30:27进入细N200。原S48细alpha2完整归档28315于08:34:09完成：
3094文件、59包、1,432,871,592B；alpha1启动档案189文件、7包、106,014,248B亦完成。
两者正在实际Git字节回读后保存本地检查点；28663现捕获S96粗层，29287捕获S96筛查，
28745仍等前序。物理门槛及推送条件不变，尚无push/PR。

UTC08:14最高优先覆盖：新S96细筛查已完成并选择**原生单rank**。同CPU21的32态
四rank窗口8/32分别943.454/632.061秒，分区单rank397.683秒，原生单rank394.727秒；
最后者对四rank窗口32减少37.55%，峰3,553,603,584B。独立回读960数据集通过：对
四rank节点/历史max1.550409e-16、归一化质量max2.382260e-16，对分区单rank
max6.938894e-18，v4时钟exact。仅为这个网格/CPU配置的启动成本证据。

四rank筛查后的28580空闲待审控制器已07:50:31安全退休，状态cancelled_before_long_work；
全部筛查、退出handler和退休记录保留，不得恢复。实际新长研究是29270/session91679，
08:08:57启动，status `rounder-native-serial-a2-family-current.json`，控制目录
work/rounder-native-serial-a2-family-a6643c8。新匹配粗N200/细N200/细N400均从零开始，
CPU21/1rank/6GiB/swap0/候选60eb/窗口32；粗层已完成200，先核对全部802个保留态
与既有四rank粗层的完整场/历史，再推进细层及原时间/尾项/采样预算。尚无新细物理资格。

Alpha1短筛查已07:47:37完成；独立480数据集回读07:53:29通过，缓存184.668秒对
原1358.554秒/新默认499.213秒均达成本门槛，仍只eligible，原alpha1长研究继续。
原S48 alpha2的匹配N400已07:52:01真正进入2400步计算。S12 EON完整审计、各原
弹性/参考任务状态沿下文；整体未通过。29287/session89907用低优先CPU15捕获
alpha1筛查后再捕获S96四组完整筛查及不可变采用定义；28315仍捕获完整S48细轨迹，
28663/28745排队。当前完成筛查与运行中长轨迹分开归档，尚无push/PR。

UTC07:46执行计划覆盖：28580的四rank窗口8已完成32态，943.454472秒、峰4,346,318,848B，
零内存事件、作业范围已空；窗口32仍运行。先完成独立原始回读，但暂不写会自动启动
长研究的review.json。准备在完整筛查结束后退休其空闲待审控制器，再以正常资源锁
运行单rank32态对照；同CPU21/6GiB、同网格/物理/时间，比较两组全部当前/历史场、
精确v4、节点2e-9与归一化P1质量范数1e-8，要求相对两种四rank窗口均至少10%收益。
目前仅准备，未运行或采用；原S48长研究不受影响。
25408已完成old-vector1358.554秒和new-default499.213秒，07:44:19进入new-cached；
三组完整字段与成本判据尚待结束后审查，不能从两组耗时提前认定采用。

UTC07:32最新覆盖（本地代码检查点`a6643c8`，尚无push/PR）：原S48 alpha2细层25368
已于07:13:21完成1200步、完整场分析和5–6周期尾项。末周期场差通过，速度误差
**1.046822%仍FAIL1%**；压力0.196569%、流量幅值0.506865%通过各自1%门槛。
完整原始轨迹由28315归档中，不能把增长中的包当作完成证据。匹配N400仍为25665，
alpha1短筛查25408已先取得原细层资源，正在8步old-vector；原alpha1长研究继续。

新S96r8a8粗层27906于07:14:29完成六周期及分析：U0.691816%、p0.679231%通过1%，
Q幅值1.058047%仍FAIL1%，周期场差通过。原新细层控制器27988在任何数值工作前
失败：粗层释放锁与写completed之间存在间隙；完整失败记录保留。新28580/session92098
于07:22:35启动独立retry2，先在锁外等completed再入场。状态为
`rounder-fine-refresh32-retry2-current.json`；输出为D下
`rounder-fine-refresh32-screen-retry2-a6643c8`。仍先32态窗口8/32筛查，独立回读后
才可采用；CPU21四rank、6GiB/swap0和原物理/误差预算门槛不变，尚无细层采用。

弹性S12细层3212于07:25:39完成6400步及5601–6400全部800态审计：末两周期五场
最大归一化差1.013074e-6<1e-5，界面运动学0、阶段质量6.72205e-18、散度定理
7.17573e-18均通过，正Jacobian。径向均值相对无限长平面应变Lamé差4.802660%，
仍超2%，不把周期通过解释为整体通过。6659已接续S24粗层N400，参考及交叉程序/
空间/时间预算继续等待；完成的EON侧全轨迹由28745排队归档，排除增长中的参考文件。

参考程序两项独立20态试探均未采用：NS/BIPN于07:14:01、RCS于07:24:02触发预设
600秒限时；前者仅约9态完成且反复警告，后者没有完成态。实际2GiB/swap0作业范围
已清空，内存事件为0。原固定版本已使用-O3/-march=native；未另建“优化版”。
28663在完整细档案之后串行归档新粗层/交接失败和两项试探，不改任何参考生产者。

UTC06:49最新覆盖：新[启动成本筛查](../research/data/lu-refresh-startup-cost-2026-11-08/README.md)
已完成并独立回读2560数据集/实际LU事件/资源，全部数值与v4时钟通过。
原window8前后103.181/87.337秒，新默认160.047、新8为82.359、新32为57.494秒；
新8对后baseline收益仅5.70%不采用，新32对两baseline及默认均超过10%门槛，局部eligible。
原checker对默认PREONLY误判的失败全部保留；1296文件/3包35863880B完成并索引核验。
其余四归档也完成：cycle4/middle/rejected-screen/code-validation共8173文件；无增长中归档待提交。

独立审查后27906/session22160于06:41:24启动新S96r8a8粗层N200，window32/候选60eb，
六周期1200、4rank CPU21、2GiB/swap0，已完成第一周期200。状态rounder-coarse-refresh32-current.json，
work/rounder-coarse-refresh32-d844e40。27988/session59577为新细层筛查等待器，尚未数值工作：
状态rounder-fine-refresh32-current.json，D/rounder-fine-refresh32-screen-d844e40。
它等待粗层完成且周期通过，独立CPU21/6GiB/swap0、14GiB可用入场/8GiB下限；
先32态window8/32全历史与成本对照，匹配内部review才跑新细N200/N400，预算算术逐字保留。
原25368细S48最近1112/1200，25665原匹配N400、25408原alpha1筛查及所有弹性/参考不变。
新粗层采用不代表最细或项目资格；完整物理预算仍未通过，无push/PR。

UTC06:31最新覆盖：middle25664已05:56:47完成1200及原分析/对照；末两周期通过，
速度误差1.851116%仍FAIL1%。[完整3713文件](../research/data/womersley-alpha2-middle-lu8-complete-2026-11-08/README.md)
十包214,006,344B已实际索引回读。细25368最近1056/1200，继续原f7/window8；
[单cycle4诊断](../research/data/womersley-cycle4-diagnostic-2026-11-08/README.md)的U1.046822%
仍FAIL1%，1023文件/20包474,290,060B完整保存，不代替最后三周期及误差预算。
新S96插值网格筛查仅作离线诊断；旧f7窗口32启动筛查比窗口8慢33.66%，未采用，
依赖的26278细等待器已在任何数值工作前取消，**不得恢复**。

d844e40之后的五文件修正：显式LU复用遇有效时间系数变化即集体刷新，覆盖BE→BDF2、
变步长、事件和generalized-alpha启动，默认关闭策略不变。26487于06:22:09完成
PETSc3.23.7 Debug/Release各6项；每配置1005个完整HDF数据集，最大差分别
1.4650607116362124e-14/1.465017343549313e-14，v4时钟/元数据exact。实际LU事件
核对及空owner请求刷新通过；尚无性能或长程采用结论。27575独立成本筛查因脚本
误要求默认PREONLY也为FGMRES而中断，数值两组均成功，原失败保留。27732的新
retry2控制器复核这两组后仅继续剩余三组，state lu-time-refresh-startup-screen-retry2-current.json。
26332完整中层归档已结束；27539串行捕获拒绝的S96筛查，27620随后归档已完成验证。
所有原生产及参考继续，alpha1筛查25408/匹配alpha2 N400等待器25665仍有效。
没有活动暂停，全部物理预算尚未完成；无push/PR。

UTC05:30最新覆盖：中层八步三模式已完成，原vector/new-default/cache分别500.678/
101.536/45.120秒，完整连续轨迹/历史对照最大4.60101e-12，v4对照时钟exact；
独立回读后25664于04:59:26从480采用window8至1200。旧7509/7603/24479/24482–24485
全部退出，**不得恢复**。当前有效alpha2 N400等待器为25665；旧25369已在计算前取消。
它等待fine25368完成和新middle25664匹配，预算必须完整middle1200；原算法/门槛不变。
[中层833文件](../research/data/womersley-middle-lu8-2026-11-08/README.md)与
[细600交接855文件](../research/data/womersley-lu600-handoff-2026-11-08/README.md)
已完整归档；不包含增长中的新轨迹。05:28两层均有800完整周期收据；S12细EON已过
5600预热进入采样，原参考及其余长程继续。alpha1筛查25408仍排队，无暂停原alpha1。
[归档存储验证](../research/data/archive-storage-validation-2026-11-08/README.md)：同16个
HDF仅改成员顺序，样本17.41→11.21MB，逐字一致；39,834,848B完整归档已实际回读Git
索引为普通100644 blob，本地D原件保留、稀疏工作树不重复物化；没有移动/删除数据。
完整物理及预算尚未验收，所有变更仅本地保存，仍不push/PR。

UTC04:40:12，细LU筛查完整[330文件/7包](../research/data/womersley-fine-lu-screen-2026-11-08/README.md)
已归档。600→608 old/new-default/cache耗时494.556/474.624/116.530秒，实际分解8/8/1；
新默认/cache完整160数据集max1.03433e-16，v4时钟exact。独立回读通过，局部收益75.4479%。
04:28:40，新25368/会话80268从600采用window8续算至1200，状态womersley-lu8-boundary-current.json；
旧21873/22001/21907已全部退出，**不得恢复**。新25369等待匹配N400，不持锁。
25408/36908为alpha1独立八步筛查排队，原alpha1继续运行；25496/74833等待中层完整488，
随后在CPU21/2GiB独立短对照，原六进程只在筛查期间暂停、结束恢复，尚未采用中层策略。
25460/32984正在接续归档已封存的旧MUMPS部分轨迹和新交接不可变收据，增长中的新轨迹不归档。
新队列等待中层时释放资源，数值预算尾段未改。三组参考前缀收敛检查通过仅作提前诊断。
所有长期物理/预算门槛仍待完成；当前无push/PR。

UTC04:03：d1ad62b保存先前三组完整交接证据；新增参考资源筛查也已全部结束并
[归档162文件](../research/data/reference-allocation-screens-2026-11-08/README.md)。四rank
原GMRES100首步停滞，200变体第5步MS迭代30仍2.51e-9>1e-10并超时；两者不采用。
双rank原100在CPU10/12的20态数值通过，但236.232/261.554秒仅9.68%收益，未达到
预设10%，仍不采用。24930已于03:57:42恢复alpha1六进程；没有额外活动参考筛查。

[资源元数据更正](../research/data/execution-topology-2026-11-08/README.md)：Windows报告
16核/24逻辑处理器，WSL报告12个双线程核组。既有“物理核”标签应理解为WSL核组，
未证明宿主物理核绑定；README/草稿已更正，原始JSON/归档哈希和数值结果保持原样。
24147仍只暂停alpha2 driver22001等600，其数值子进程继续；原21873/21907未替换。
alpha1 LU筛查仅准备，未启动；全部原资格门槛不变，尚未push/PR。

UTC03:12：21979的三组后续原始档案全部完成：
[完整细MUMPS/Schur筛查76文件](../research/data/womersley-cgroup-screen-2026-11-08/README.md)、
[alpha1及nu0参考预检157文件](../research/data/production-followup-preflights-2026-11-08/README.md)、
[460接受态交接77文件](../research/data/womersley-mumps460-handoff-2026-11-08/README.md)。
这些是先前完成的独立筛查/交接，不是当前LU缓存细筛查或长期资格的新通过。
24147仍等原MPI到600，最近主流体537；22001继续有意暂停等待，数值子进程正常。
已准备但未启动`handoff-womersley-lu8-m600.py`和匹配N400新控制器；必须先读取完成的
细筛查报告并保存匹配报告哈希的内部自审记录，才可交接。N400预算尾段逐字复用原算法。
原21873/21907仍保留；没有推送或PR。

UTC02:57：本地e435524已保存可选LU实现及完整验证，未push/PR。细筛查24147/
会话86102已启动，**仅driver22001有意暂停**；原22002/22005–22008继续到600自然
结束。状态`lu-reuse-fine-screen-current.json`，D/lu-reuse-fine-screen-e435524。
它等原数值子进程退出释放因子后再串行8步old/new/cached对照，结束确认新scope为空
才恢复driver；不自动采用。独立暂停/恢复与实际四rank profile计数8/1均通过，
[126份启动证据](../research/data/lu-cache-screen-startup-2026-11-08/README.md)已完整归档。
现阶段不得恢复22001或启动重复主MPI。

原r4[24246文件/14包](../research/data/pressure-production-rank4-2026-11-08/README.md)
归档于02:50:39完成；1200共态的五场max节点8.6042e-16、质量范数7.7286e-14。
21979已开始完整cgroup筛查归档；它写入中的目录不暂存。其余长程继续，物理资格未完成。

UTC02:37：可选LU复用小验证已完成。Debug10/10；Release复用首次6项默认路径和
retry2三项实际LU计数通过证据，隔离目录后重跑流体项通过。两配置各455个HDF数据集
最大差1.0402e-12、时钟/时间元数据精确。显式`--mumps --lu-reuse-window`入口真实
1/2rank各13态最大差1.1720e-14、时钟精确；更改策略恢复被拒绝、完成态恢复无重算。
[完整验证及两次失败](../research/data/lu-preconditioner-reuse-2026-11-08/README.md)已归档。
细网格成本/长程采用尚未做；21873仍正常计算至约508，原冻结研究不变。无push/PR。

UTC02:27：已补齐[修复后生产时钟重放](../research/data/pressure-clock-replay-2026-11-08/README.md)
19302文件/15包、[原有界直接解失败](../research/data/womersley-direct-bounded-failure-2026-11-08/README.md)
16文件/1包及[alpha1中层N200](../research/data/womersley-alpha1-middle-n200-2026-11-08/README.md)
1563文件/5包的完整档案说明。重放400步时钟精确通过，不覆盖原v3失败；中层速度
1.66366%仍失败。r4档案仍由21376写入，21979继续等待，不暂存未完成档案。

可选LU缓存尚未提交/采用：首次Release独立实际分解计数失败，查明SNES析构会重置
共享PC。解绑再保留后1/2/4rank实际分解次数1/0/0/1通过；小流体复跑目录混入旧态
使额外HDF审计中断，已改为每次独立目录。23025/会话56958正在Debug10项；修正后
Release的455个HDF数据集最大场/历史差1.0402e-12，时钟/元数据精确通过。26项CI
选择检查通过。未做细网格成本试验，长程继续使用原冻结二进制，无push/PR。

UTC01:51：21873的460→463与原连续463完整历史最大差4.4264e-12、时钟差0，通过
后已于01:50:05明确采用MUMPS续算。旧7542及20170/20171/20174–20177全部退出，
旧等待器20754/20817已取消，不得恢复。新D/womersley-a2-s48-l2-n200-mumps-m460
正在14GiB/swap0整作业限制下运行，21907等待其完整结束后做N400。已完成
[交接收据](../research/data/womersley-mumps-entry-2026-11-08/later-handoff-receipts.json)
另有源哈希；21979/会话79950排完整screen、预检与不可变交接数据，等21376归档后
串行执行，不捕获增长中的长日志。全部数值资格仍待验收；不push/PR。

UTC01:44：显式MUMPS入口及完整作业资源控制已通过
[331份小检查证据](../research/data/womersley-mumps-entry-2026-11-08/README.md)。
真实1/2rank各13态，默认直接解对照最大5.204e-18，分段chord最大1.614e-14；
v4时钟精确相同，改变配置resume及非法组合正确拒绝。默认行为和数值核不变。
细网格独立三步screen在14GiB/swap0下181.986→353.400秒（候选/原配置），
字段最大5.2965e-12、全部历史过门槛；原六进程已于01:28:58恢复。
较早3.5GiB/rank地址空间下的失败保留；不同内存策略不能混为一次试验。
21873正在等待完整460/连续463，随后独立复核后才交接；21907只等待其完整N200，
不持计算锁。此时旧20754/20817仍等待，尚未取消，新长程策略尚未采用。

原r4已经完成12800和1200相位五场比较，最大节点差8.604e-16、归一化质量范数差
7.729e-14；原旧时钟失败不变。alpha1中层N200完成，速度误差1.66366%仍失败；
细预检804.988→426.417秒、最大差3.814e-12通过，20806已启动细网格，1180已退出。
独立nu0 S24串行/双rank20步差1.665e-16、2.456e-14，通过后20277采用双rank
CPU9/23运行细参考。大归档20351于01:43:40完成修复后重放；21376继续失败筛查/中层/r4。
[400步交接68文件](../research/data/womersley-vector400-transfer-2026-11-08/README.md)
已完整核验。完整PROD-02尚未验收，继续本地工作，不push/PR。

UTC00:55：研究入口修复Linux MPI残留进程风险；真实rank各自建组，清理改为核对自有
完整会话和启动身份。7项Python检查及真实2rank成功/4rank超时通过，
[24份证据](../research/data/linux-study-session-cleanup-2026-11-08/README.md)已核验。
旧直接解等待器20915在零数值运行时取消，新21129/会话23593等待同一中层自然结束，
时间/内存/字段/成本门槛不变。当前长研究的冻结源码没有改变，未重跑PDE或全套测试。

原重启失败[24550文件/26包](../research/data/pressure-mpi-original-clock-failure-2026-11-08/README.md)
和完整nu0粗参考[1783文件/2包](../research/data/reference-mesh-nu0-2026-11-08/README.md)
已回读核验。[对照图](../research/data/reference-mesh-nu0-comparison-2026-11-08/README.md)
显示网格周期过门槛，但压力幅值及Lamé均值仍失败。r4已完成12800步，正在五场审计；
alpha1中层接近1000，直接解筛查尚未开始。归档队列已转400交接，修复后生产重放随后。
独立nu0 S24及其预算等待器仍待原r4释放资源。完整PROD-02未验收，无push/PR。

UTC00:34：新增两个独立等待器，[30份启动证据](../research/data/bounded-followup-startup-2026-11-08/README.md)
已回读核验。20915等alpha1中层自然结束/分析后，用释放的四核做有界MUMPS与Schur
同400步种子三步对照；每配置900秒、每rank3.5GiB，仅评估候选，不自动改变生产方案。
它持选项预检锁，使20806之后的fine预检等待，现有中层仍继续。20925等待独立nu0
S24三组完整结果，再沿原算法核算预算和细网格跨程序对照，不持分析锁。两者尚无
数值通过结论。r4到10000、alpha1中层914；原始大归档仍在进行，未推送或创建PR。

UTC00:17后：已完成等待控制器的明确替换，[114文件](../research/data/segmented-queue-handoff-2026-11-08/README.md)
保存身份、取消、原始/新冻结源与研究输入。旧15446/15457/7639在任何细/N400数值工作前
取消；当前中层5422身份和命令未变，1180由新20806重新暂缓。alpha2新20754等待完整
600步及连续603步，之后才验证三步重启并交接；当前7542及其求解进程仍正常运行。
N400新20817/20825均不持锁等待新收据，参考S24 nu0队列20277仍等待原r4。
所有具体数值预检和长期资格仍按各自状态推进，不把队列替换写成计算通过。

继本地86bbdac后，补充显式`--cycles-per-solve`自然周期分段，保持总物理终止时间和
默认行为。新v4与旧v3可选Schur路径各做真实1/2rank检查：13个存储态及完整历史通过，
v4差0，旧v3双rank最大6.939e-18；非法0/-1和完成后resume无重复尝试通过。
[604份原始证据](../research/data/womersley-segmented-execution-2026-11-08/README.md)已核验。
这处理长solve段可能超过合法86400秒时限的执行风险，不代表物理资格；当前所有已冻结
长控制器仍未更换，下一步在等待/完整接受态边界准备明确交接，禁止改活源码。

UTC23:54：定位并修复生产重启的时间补偿量丢失。原r2五场400相位通过，但183步时钟
不同、最终差1ULP，原失败保留，精确时钟门槛不放宽。checkpoint v4保存该accepted状态；
旧v3显式提示缺失，不声称补回历史。Debug/Release各8项通过，真实快照读取器双格式及
4项拒绝通过，[10464份原始验证](../research/data/checkpoint-clock-v4-2026-11-08/README.md)已核验。
新生产重放400步精确时钟/全部HDF历史/五场及周期/质量均通过，较大原始归档收尾中；
原冻结b072的r4全长已启动。完整PROD-02资格未通过，未上传或创建PR。

主alpha2第400步四核三步复核通过：488.690→339.692秒、最大场差5.087e-12，已显式
派生六周期续算；原调度507/631按计划退出，不得恢复。nu0完整粗参考周期通过，末周期
网格漂移5.87244e-6，但中部压力幅值2.58247%、Lamé均值8.31525%仍失败。新增独立
S24 nu0细化队列20277，等r4/时钟工作释放CPU9/23后做20步串行/双进程预检，再计算
三组同物理空间/时间配对；原nu.3研究不变。还需审查长流体段是否可能超过单次24小时
入口时限，不能把控制器超时写成物理失败；当前数值进程继续，未改冻结源码。

UTC23:11：新增证据已本地保存a7a177e，未上传。后继自审再发现运行时限172800超过真实
CLI上限86400；两个旧等待器在执行前计划取消，另冻合法时限、自然cycle5→6分段版本。
真实入口8项守卫检查通过，新等待器15446/15457不持主锁，70文件已核验。主计算未中断。
参考网格闭路机制诊断34文件完成：相同路径200→800段后漂移仍约1.93e-5，单形状往复
控制约2.05e-7；内部网格nu0回放约5.85e-6，仅为反事实，不能替代原完整耦合失败。
另启动同物理输入、原固定二进制的完整nu0对照，12800步仍在计算。生产MPI二rank完整
12800已结束并审计中，尚待五场对照/重启/四rank。所有原门槛继续有效，无push/PR。

UTC22:53：本地fa9646d后，L24动态长度诊断已启动；中段局部网格与L12逐单元匹配，
三步末态差2.844e-25通过，完整32周期尚未完成。alpha1/2细N400后继已冻结，等待时不持
数值队列锁；自审补中层/控制量周期与质量前提，旧等待器的计划取消保留。新增66/37文件
归档核验完成。生产MPI的r1完整轨迹与原默认配置1200相位最大场差8.674e-16通过，r2继续。
独立P2多边形参考四次尝试后通过原门槛：S48速度几何差约.45%–.50%，S96约.11%–.12%。
双精度残量下限、校验器精度错误与修正均保留，106文件/科学图已核验；观察到的网格增量
不是严格误差界或三维资格。主alpha2到386、alpha1中层到569；全部原资格门槛不变，无push/PR。

UTC22:18：本地f0422d0已保存，未上传。S12/N400的1/2/4rank五步预检通过，完整32周期、
末三周期五场与二rank末周期重启对照在CPU9推进。首次漏冻结生成器的导入失败保留。
alpha2中层N200新旧三步末态差1.717e-12通过，CPU21已进入六周期独立研究。首次零保存
间隔拒绝保留；同项错误在主流体400步probe执行前被发现，已另冻新等待控制器，原数值
进程未中断。alpha1仅外层父调度暂缓，当前中层求解继续，结束后再预检细网格候选。
S24只读预算控制器等完整收据；390文件已核验归档。长程/精度/预算资格仍未完成。

UTC21:56：S24第400步完整检查点复核完成，标准/MUMPS+chord三步21.886→14.335秒，
末态场差7.454e-20、最大归一化质量范数差1.122e-17；满足预声明门槛。已显式派生D盘
新研究，从400步续至12800，原日志至402的额外两步在新研究重算；原始记录完整保留。
参考仍沿原目录计算，主流体400步自然边界仍在等待。执行快照116文件、alpha1后续3126、
直接解筛查103文件均已回读核验。长程资格与预算仍未完成，不推送或创建PR。

UTC21:42：N400原始8289文件与vector967文件核验完成。单核弹性直接解新短对照保持同一
1400步状态：MUMPS+chord三步末态场差3.47e-17、五场归一化范数差最大1.21e-14，局部
耗时17.956→6.633秒；串行SuperLU反而更慢。没有修改运行研究，S24第400步完整状态处的
独立复核/显式续算控制器已启动等待，原参考继续。归档另发现svFSI最后状态硬链接；保留
原断言失败并仅重试归档，79文件通过。所有门槛不变，完整资格尚未完成，无push/PR。

UTC21:14：可选block3细网格三步通过2e-9字段门槛，最大差5.08531e-12；单物理核心局部
成本下降26.392%。明确保留可选实现，但尚未改长期研究。第400步自然边界交接控制器已启动，
仅暂停Python调度子，现有四个求解进程继续；须再通过同态四核复核才派生六周期续算。
实际研究定义拒绝静默换选项的6项检查和26项选测检查通过。N400时间/尾项/采样分析完成，
参考ALE周期最大1.91055e-5仍失败；空间分母未完成，不声称预算合格。S24两侧长计算继续。
原始证据正顺序归档，具体进程/储存安排见最新队列；没有push或PR。

UTC21:00：N400参考12800步全部相对收敛，正几何和质量通过，但网格周期仍失败；
EON周期通过。中部压力幅值差2.58266%未过2%，减半时间步尚未消除此差异。
N200→N400完整场时间/尾项/实际采样分析正在进行。CPU8已进入D盘S24/level1/N400参考长算；
另两组S24空间/时间预算配对已冻结并排在CPU18/20原研究之后。计算安排详见最新队列。
所有长期计算继续使用冻结b072，门槛不变，尚未push或创建PR。

UTC20:41：证据已本地提交054b64a，未上传。N400 EON12800步完成且全场周期通过，参考继续。
S24/level1/N400短程两边通过，长期两侧已分别在CPU22/8现有锁后排队，原始数据改用D盘空间；
保存最后三周期，具体状态见队列。alpha1 level1/N100周期/压力/流量通过，速度1.66523%仍失败。
可选速度三分量PC元数据完成最小Debug6项、Release5项+同源码失败补验1项，真实小管1/2/4rank
对LU最大差1.012e-13；一物理核心默认MPI空等的超时及恢复保留，未放宽测试时限。
细网格有界对照正在CPU22/23进行，仅为局部观察；没有采用新策略、整体资格或push/PR。

UTC20:17：N200/时间预算/独立网格回放4298文件和静态Lamé108文件已逐份回读核验。
增量网格实际场回放差约1e-15；边界严格闭合仍有约1.93e-5漂移，固定几何约1e-16。
时间差、尾项和实际100→200采样已分场记录；空间分母未完成，不声称10%预算通过。
另十组全环夹持静态L12/L24诊断完成，匹配局部网格，中部位移变化约.30%–.39% Lamé尺度；
S24/level1的L12中部均值误差1.2501%，这只是静态候选筛选，不替代动态耦合资格。
主计算和临时GAMG探测继续，保留全部失败与原门槛；尚无push/PR。

UTC19:48：已本地提交6093f01，未上传。N200两侧完成：中部压力幅值差2.483%仍未过2%，
相位.512度通过；参考内部网格周期差1.935e-5未过且相比N100几乎不变。全部参考方程步
相对收敛，不能将未周期稳定等同于求解失败。N400预检通过并开始完整研究，空间细化继续。
独立静态厚壁管九组诊断完成；积分4/6比较曾失败，改用6/8并复用成功求解，未降低1e-9
积分检查阈值。该诊断采用对称/仅轴向端约束，与实际径向夹持FSI分开解释，尚无新增耦合资格。

UTC19:36最新：细化一层的长期弹性研究已分别在CPU18（EON，PID3212/会话3286）及CPU20
（参考，PID3224/会话9823）启动，6400步，锁和状态见队列；两组短预检123文件已核验。
PC探测94文件已核验，不改当前主研究选项。CPU8粗网格N200已完成EON6400步，周期/质量
均通过（末周期最大1.92e-6）；参考正在计算，尚不具备时间预算或跨程序通过结论。

UTC19:30补充：6846份启动研究文件已逐文件回读核验；日志解析器自审补拒绝损坏迭代行，
4项相关检查通过，4份真实日志重审结论不变。细网格PC探测完成：仅压力HYPRE三步场差
3.32e-12、局部耗时366.70→292.45秒；两场HYPRE更慢，均未更改运行中主研究。
CPU18五步S12/level1/N200空间预检两边已完成；CPU20正在检查同细化网格ramp16的参考收敛。
其余三组研究继续；没有push/PR。

UTC19:15：参考日志全步审计已接入比较资格，缺日志保持未验证。13200步参考全部相对
收敛，但ALE网格位移周期差1.95e-5仍未过；ramp2/c12另有1215方程步未收敛，保留失败。
收紧线性绝对容差到1e-26的短程N100/N200通过，非线性及物理门槛不变。相关最小检查和
181证据文件核验完成。ramp16/c32 EON与132周期全场差最大1.891e-6，预声明1e-5门槛通过；
参考mesh场差.002170不通过，不能共用这项启动结论。N200双求解器32周期已在CPU8运行，
细网格有界预条件器探测在CPU18-23，原两MPI队列继续。原始结果/失败/知识记录均保留，未push/PR。

UTC18:48补充：参考ramp2/c12完成但日志暴露迭代上限仍标ok的行为；1999条上限行不得
当收敛资格。正在补实际日志审计及更严格线性绝对容差短程检查，非线性门槛不变。
ramp16已转入EON预热；参考阶段须处理这一已知问题后才接续。

UTC18:40：EONSim132周期长预热已通过最后两周期全场门槛（最大3.73e-6）、阶段质量及
运动学；参考运行在清除MPI版本间遗留选项后单独重试，不重做已完成EON。详见最新队列。
显式General压力表已通过普通正弦/平滑启动各100步精确离散检查，最大递推误差4.19e-13；
5项导出、7项审计、6项制造启动比较通过，288文件核验。默认Fourier仍拒绝静默近似启动。
两周期ramp后的12周期真实EON场仍未周期稳定，保留失败结论；更长ramp候选排在CPU18。
alpha1首个六周期场周期稳定但u/p/Q幅值仍未达1%，2071文件核验。无完整资格、无push/PR。

UTC18:17补充：alpha1也已在独立CPU10-17四rank队列启动；实际四进程亲和性预检无重叠。
低/中网格N100/N200后进入细网格N200六周期，具体状态/锁见队列。并发只用于完成数值
研究，不作为性能比较。主alpha2和单核弹性继续；截至此处新alpha1尚无精度通过结论。

当前检查点（UTC18:04，优先于下方历史）：细网格lag=-2三步差1.03e-14通过，本次
156.54→148.06秒。已显式派生womersley-a2-s48-l2-n200-chord-m200，从200步恢复、
保存相位200；原研究不变。首次弹性/通过项3423文件和选项成功/失败139文件均已核验归档。
受控粗网格N200完成1000步；固定BDF2时间尺度后N100→N200场差.000551646/8.41201e-6，
同N200改变tau时间尺度则为.00409246/.00823032（速度/压力归一化RMS），1574文件核验。
这是参数影响分离，固定参数结果不替代默认资格，粗网格精度仍未过。

后期弹性窗口必须读取真实前一步、至少三完整周期；11项制造窗口及4项导出检查通过，
551文件核验，物理门槛不变。资源检查证实24逻辑核心/32GiB内存，主四rank绑定CPU0-7，
另设独立单进程弹性队列固定CPU8（实际约28GiB空余）。EONSim从600步续至12800预热，
随后分析四周期至13200，再运行同定义svFSI。两份控制器与锁见队列，严禁重复启动。
真实长暂态结果仍在计算；没有push/PR。

最新接续（UTC17:36）：第200步完整四rank接受态已核验，计划交接成功；原细网格
attempt保留为计划中断。2189a8c时间尺度Debug/Release各1/1通过，阶段压力参考
100步通过。两边首次弹性600步完成；实际参考输出坐标为Float32使旧审计失败。
已按精确binary32序列化匹配修复，6项单位检查和实际VTK双精度类型读取通过，
两边重审均通过运动学/阶段质量/正几何，但全场周期门槛未过；中部压力对照也未过。
详见[审计说明](PRESSURE_TUBE_FIELD_AUDIT.md)。六周期结果不是弹性资格。
COO三步对照粗/细最大场差8.7e-19/1.35e-17；细网格总时间未降低、峰值内存增加，
暂不采用。旧chord lag=-1在PETSc选项入口被拒绝；改为首次Newton重建的lag=-2，
粗网格3步差2.60e-15通过，细网格对照正在执行。尚未续算原细网格，无push/PR。

PR #38已合并为c218c18；接续其中新增的完整场审计及96/12/24种子网格证据，
不重做未受影响历史检查。工作分支codex/fsi-production-48h-20261107；用户授权窗口至
北京时间11月9日20:59:10，全部验收/自审/证据完成后再push和PR。
当前推进PROD-02剩余资格，先处理端面压力与局部散度，再做Womersley、弹性管和固定版本svFSI。
已建立本对话定时续接；执行前核对唯一计算队列、记录accepted状态和失败，防止重复启动。
WSL Ubuntu24.04的原锁定依赖可用，启动检查无遗留eonsim/MPI作业。具体门槛与顺序见任务队列。

21:24检查点：Schur小网格1/2/4rank与哈希核验的历史LU逐点差最大5.66e-13。
96/24/48（112945节点）默认500次Krylov失败；保留失败，restart=120/max_it=2000后以539+86次收敛，
原rtol/atol未改。Q/速度L2/压力RMS误差0.133114%/0.189354%/0.218287%；端面3.087918%、
归一化div 1.467790%仍未达标。96/48/96四rank在唯一队列运行，使用冻结的旧二进制。
瞬态压力边界与checkpoint采样频率已实现；仓库入口Release四项全部通过（fluid_pressure_time、
tagged_fluid_verification、fsi_element_jacobian、fsi_pressure_state）。离散解析误差最大1.98e-16。
这仅是脉动边界实现验收，Womersley定量研究尚未开始；本轮未push或创建PR。

22:20后续检查点：96/48/96稳态447073节点、2626560单元四rank完成，六项预设场门槛通过。
Q/速度L2/压力RMS/端面压降/div误差分别为.048834%/.164996%/.101786%/1.899080%/.733242%。
[六份原始归档](../research/data/rigid-tube-schur-2026-11-07/README.md)78文件哈希核验通过；
MPI/直接解对照仍仅在1737节点，不能扩张范围。Womersley alpha2粗网格已周期稳定，但速度2.3667%、
压力1.15345%、Q幅值1.47233%未达标；level1、时间减半、追加周期在唯一队列依次进行。
固定svFSI构建及压力管网格/Fourier导出三项检查通过，均匀时变压力输入检查等待队列。
弹性耦合对照、Debug最小回归、误差预算和整体自审尚未完成；不push/PR。

后续检查点：b072压力增量Debug最小两项2/2通过，280原始文件已核验归档。
Womersley level1/N100压力、流量幅值/相位和周期门槛通过，但速度L2仍1.86191%；
粗网格N100→N200的速度/压力场差为首档空间场差的56.10%/53.96%，不满足10%预算。
追加第六周期的场差约1e-14，粗网格周期尾项很小；不能代替细网格尾项证明。
唯一运行作业为womersley-a2-s48-l2-n200（四rank、冻结b072二进制），总目标1000步，
warmup目标400步。后续需检查其实际完成/超时状态；禁止重复启动。
固定svFSI均匀压力100步已通过精确离散核验：速度2.51e-15、压力递推4.61e-13。
ASCII/未压缩导出的失败均保留，原生zlib网格通过标准VTK与参考程序读取。
显式stage-pressure输入选项已实现，但该选项实际参考运行及弹性对照仍待执行。
默认tau的可选时间尺度诊断实现/测试已准备，正在仅编译；实际数值检查等待同一队列，尚未通过。

静态审查补充：b9075f0修复通用网格写出固定region10导致新压力管固体标签错误的问题。
显式传入流/固region，几何导出3项与原刚性网格3项通过。旧未运行输入保留在归档；
新输入为elastic-s12-l0-region20。旧等待项在执行前撤回，新等待项以b9075f0为源码基准；
状态仍在next-acceptance-current.json。时间尺度实现已编译完成，数值验收仍待执行。

48h窗口后续：3934131本地保存已核验的稳态/初期Womersley/参考导入/Debug证据，无push/PR。
首次弹性计算前补充结构位移和ALE位移的不同参考输出名，以及完整物理场审计；
五项独立审计检查、三项导出检查、26项选测检查通过。实际耦合审计仍pending。
详见[压力管审计定义](PRESSURE_TUBE_FIELD_AUDIT.md)，不将准备工作记为弹性资格通过。
源码2189a8c已本地提交并绑定新等待控制器。独立VTK实际证实旧同名位移丢失一份；
新映射物理值完全保留，参考坐标差1.11e-16。制造的48快照历史两条审计路径均恢复已知谐波，
[185文件](../research/data/pressure-tube-audit-2026-11-07/README.md)核验归档；没有新的耦合求解通过结论。
11月8日00:16（UTC16:16）针对约50秒/步的细网格安排第200接受步交接：验证完整checkpoint
后才中断原MPI，让既有验收队列先执行，再核验加速选项并续算。尚未实际发生交接；
状态与后续操作见任务队列，不能把计划中断写成物理失败或整个算例完成。

离线误差定位确认level1速度偏差并不局限端部；节点插值与场误差分别记录，根因仍待辨明。
六组网格的解析插值筛选已完成，34原始文件核验归档；无新增PDE精度或性能结论。
见[网格筛选](../research/data/tube-mesh-screen-2026-11-08/README.md)及现有Womersley证据补充。
弹性观测量与嵌套双域场比较准备完成，独立5+3项检查通过、28原始文件核验；
全部为分析/制造数据。参考内部网格方程差异已明确记录，真实耦合结果仍pending。
已有BDF2历史的tau系数重建已完成，200次独立前一步对照完全一致；系数对dt敏感，
但尚无新的受控周期求解或场误差归因结论，时间尺度数值验收仍在原队列等待。
源码cfa5d3c把可选COO/步内chord策略写入不可变研究定义；旧研究空续算及三类拒绝
共4项检查通过，7文件核验归档。没有实际采用新选项，数值探测和显式派生续算仍待交接后执行。
已有场补充压力迹/法向应力分离诊断，仿射积分检查最大1.164e-13；不是新PDE结果或新增验收门槛。
采样重建工具通过正弦/线性独立参考；已有50→100相位差已记录，不能冒充100→200预算。
准备的新研究只允许从warmup接受态派生，可明确加密保存相位；尚未执行真实派生或加速探测。

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

