# EONSim Codex Task Queue

> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

用户最新选择：取消全量上传，先推送单独快照分支 `codex/fsi-progress-snapshot-20261109`。完整本地分支和工作区未改写；不创建PR、不合并、不自动恢复计算。

2026-11-09 02:35 UTC：**用户要求停止，全部后台队列已停止；定时任务PAUSED。**
禁止按下方历史队列自动恢复任何计算、审计、归档或筛查。20控制器/9scope已核验退出，
原`failed`中断记录保留，[停止快照](../research/data/prod48-user-stop-2026-11-09/README.md)解释用户取消原因。
用户追加要求“将当前进度提交远程”：允许现在将已提交完整历史和停止进度上传
`codex/fsi-production-48h-20261107`，不要求先完成物理资格；不创建PR、不合并。
未封存的103/42/19个大档部分只留本地，不能stage为完整归档。后续恢复必须等待用户新指示，
再核对真实检查点与半写尾部，不能直接重启旧冻结控制器。FSI-PROD-02仍未完成验收。

2026-11-09 02:23 UTC：47675成熟FSI筛查和47710完整raw复核均通过并退出，不重复执行。
新S24 N800细47914、粗47944已真正采用，47952只等完整两组后分析原算术预算；不得重跑prepare/run
或修改冻结controller。目标25600步/32周期/末2400态，统一从零细时间步，没有warmup捷径。
fine持elastic-geometry-long.lock/CPU22，coarse持elastic-budget-analysis.lock/CPU19；各2Gswap0，
CPU22的guest sibling23有原参考，明确共享而非独占性能。全部原计算和N400失败继续保留。
47776当前捕获成熟证明，之后等完整L24延长；47990当前等同归档锁，先存采用计划再等粗/细/预算。
43422/44619原轨迹和重放证明仍增长，只stage实际完成档。α1N400接近数值结束但仍须完整分析，
43221/43241继续等其整个family完成后筛查新的S96策略。无push/PR，时间窗口到点不降低门槛。

2026-11-09 01:50 UTC：46060已completed，Debug/Release三项及完整3696HDF通过，不重跑。
47624验证捕获已completed8950files1part1433180B且Git回读完成。47675真实满载32态筛查正运行，
必须全收敛/字段/历史/实际LU计数/四个成本比≤.9，再单独rawreview后才允许新FSI时间加密。
原三项time预算FAIL保持，40042等参考。L24实际延长46800用原2692运行，原c32失败保留。
所有活动冻结源不修改；43422/44619增长中的档不stage；最终完整资格前不push/PR。

2026-11-09 01:35 UTC：40042的EON预算已完成且三项time/space失败，现锁外等svFSI；
不要重跑已完成预算或放宽.1门槛。[失败完整证据](../research/data/elastic-s24-eonsim-time-budget-failure-2026-11-09/README.md)
已整档Git回读。46060正做显式默认关闭的FSI LU增量验证（Release/Debug三个相关测试及全HDF），
实际通过后还须成熟真实checkpoint成本/历史证明才能采用新时间加密，未完成前不得改冻结生产。
44437/44493全部重放复核已完成；实际L24 extension自审已01:34:01通过，46800于01:35:56实际run。
44619保存完整证明，43422继续原L24/N200轨迹捕获；只stage完整档。全部资格前不push/PR。

2026-11-09 01:12 UTC：继续六长程及40042完整EON预算；44437已核对160/210场对，
44493仍须完成后的全部raw复核，之后才可prepare具体L24延长计划。43422仍增长不可stage。
本轮仅修正当前执行策略文档，与历史准备/实际验证证据分别绑定；运行时和冻结控制器未改。
全部验收与完整自审前不push/PR，局部源码审查不作为项目通过。

2026-11-09 01:00 UTC：L24 proof44437已完成200+10数值，现在全210五场/11native比较；
44493继续等它完整通过后逐项重算，44619等两个终态后完整归档。不要提前prepare或run
extend-length24-native6400.py。review-length24-extension-execution.py仅inspect ready=false；
未来实际prepare完成后才review具体计划，记录匹配definition/proof/raw SHA，再run。

44808 reference-full-load-prefix-capture-current已completed94files/6parts7656276B，已整档
Git回读，不重复捕获/暂存。四前缀的满载覆盖400/1900/400/0步，全部方程收敛通过只是
前缀证明；[证据边界](../research/data/reference-full-load-prefix-20261109t005527z/README.md)保留。
40042完整EON预算、43422原L24及后继N200/长度大档仍运行；六长程计算不变。未push/PR。

2026-11-09 00:42 UTC：40040 EONN200已completed6400及600态周期/守恒/J/均值审计；
42097原L12/L24长度比较也completed，不再等待/恢复二者。40042现真正analyzing eonsim
完整预算，参考半部仍待各自生产；不能把前述局部门槛通过当预算或跨程序通过。
43422仍捕获原L24完整轨迹，随后已完成的L12和原长度对照，增长中不stage。

[新小报告包](../research/data/elastic-n200-audit-and-length-summary-2026-11-09/README.md)保留L24周期失败
及明显动态长度差异。44437 proof→44493 rawreview→具体延长plan审查的顺序不变。
新44619/session32219，capture-length24-native-proof.py，statuslength24-native-proof-capture-current，
等待两个proof/review终态与自有scope清空后保存全原始证明；failed也如实归档，不自动采用。
未启用extend-length24-native6400.py（469f78e7）仅只读检查，当前prepare/输出/status不存在；
只有完整证明和复核真正passed后才prepare，然后另写匹配definition/proof/review SHA的
execution-review.json才可run。CPU14nice19/2Gswap0、6400→7200、末600审计，不改物理门槛。
HEAD98ee0f93之后只准备这些独立后继和证据，原六组长程继续，无push/PR。

2026-11-09 00:26 UTC：继续六组原长程数值和新的有界L24原生重放44437，EONN200已
6400并在完整审计。L24 c32审计完成但solid_velocity周期1.09245e-5/1.05679e-5 FAIL；
原42097长度比较仍等待实际L12，43422完整L24档增长不可stage。mean Lamé1.55968%PASS
不能替代周期门槛。不得恢复原7713/42141。

[新重放计划](../research/data/length24-periodic-audit-and-native-proof-plan-2026-11-09/README.md)
只证明原6200→6400在7200最终步下的200场轨迹及10步再重放；原native只每200步保存，
因此真实可用的是210五场对、原6400一个完整native对和新10个native对。CPU14nice19/
2Gswap0，持独立length24-extension.lock。44493已排队，完整证明后同锁重算全部指标；
不得把静态计划、局部进度或单次证明当6400→7200长程采用。还需具体扩展计划与实际自审。
两新status分别length24-native-extension-proof-current和length24-native-proof-review-current。

α1N200完整4116files/79parts已整档Git回读，首48包b002c068；最后31包/metadata本地保存。
42447现只等N400全家族，不再等待N200捕获。新S96α1screen43221/raw43241仍等40998完成，
未启用的prepare/execution helpers不要提前执行。N80041187仍为N400目标时间控制。
所有原门槛、失败保留及完成后才push/PR规则不变。

2026-11-08 23:54 UTC：继续七组实际数值生产与L24有界审计；EONN200已6164/6400。
[S96α1执行器静态准备](../research/data/alpha1-s96-execution-preparation-2026-11-09/README.md)
22项配置/命令检查通过，但真实前置仍未完成：43221筛查、43241完整raw复核必须实际eligible，
才可运行prepare-alpha1-s96-fine-family.py prepare，随后review具体计划再run；此时没有
计划目录、新执行状态或新生产。未启用脚本不能记为新算例已排队或采用。
等待L24审计和EONN200完整审计；43422只按真实完成条件捕获，42447增长档不可stage。
当前本地HEADadddc7e；未push/PR，原全部资格门槛不变。

2026-11-08 23:34 UTC：7ed5a5d已保存完整S96 N40084包，所有对应Git暂存/回读完成。
继续现有七组数值生产、L24有界审计及其后的实际L12长度比较；EONN200已进入正式采样。
[LU与时钟局部源码复核](../research/data/solver-clock-source-review-2026-11-09/README.md)完成，
十五份源/测试哈希与历史验证相同；只修正文档，没有新数值测试或新运行时修改。
42447的alpha1 N200档仍增长；43422/43808等待完整前置条件。43221/43241仍等原alpha1家族，
新的S96α1细长程准备器只做过ready=false的只读预检，没有prepare/adoption/新生产。
物理失败和待完成预算保持，尚未push/PR，最终交付自审未完成。

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



## FSI-PROD-02 / 48h continuous / in_progress / 2026-11-07

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

UTC18:06最高优先：37886完成12800数值后，完整audit因整周期节点缓存触发2GiB OOM。
39197/39393已failed，不恢复、不重跑sample。39845验证根代码按需重读修正：旧缺陷
复现、Windows/WSL各9项通过，完整粗1200态数值逐项等价仍在跑；39865仅等待验证后
做新完整细审计。新根代码两文件未提交，当前HEAD6bce127。

未执行的EON1600正式handoff/reviewer/budget源仍指向旧失败消费者/细审计，禁止直接
运行；先更新新分析器/新路由，参考匹配审计必须使用显式restart-chain，再独立审查。
39567实际1600边界screen和39575reader继续；原33828/33829不动。nu0已5000实际采用，
39231捕获completed待Git验证，39162后续消费者也需新的EON审计路由。39748仅等待
S48/S96 N400完整预算再捕获，无新的物理资格。

UTC17:51：39392已实际native1100采用，39393为有效nu.3预算消费者；旧29899/29901/
39174自然退出及失败保留，不恢复。39401实际交接135文件与39661失败审计补档7文件
均completed。39559完成EON1400同态选项356文件；三档合计498文件9包74784468B，
实际Git回读后本地提交，不上传。初次39468性能事件名误判保留，retry39531独立通过。

39567/39575只排队1600 EON边界证明/独立审查；原33828/33829继续。新1600正式接续、
独立handoff review及budget helper只有源文件，尚未prepare或运行，不能宣称采用。
S24 EON N400已12800但1200态audit仍运行；39197仍等完整审计。39157nu0自然5000、
S48N400后alpha1筛查/独立review和全部空间/时间/尾项/采样预算继续。门槛不变。

UTC17:29：39299完整N200后端556文件10包279699816B已捕获，实际Git回读后本地提交。
38663/38676均completed，不再等待或重跑。新39392只请求1100自然停点，原29899仍算；
39393为未来有效nu.3预算消费者，39401只等实际N200采用才归档，不混入增长EON输出。
39364独立交接审查PASS，首39331缓存比较失败保留；尚无N200正式采用。旧39174到边界
将自然failed，后继路径和原算术已核验，不能恢复旧等待器。

39418 N200 EON选项筛查只跑小规模真实1400同态对照，等待完整字段/历史/重放和两次
默认成本；至少20%节时才eligible，仍需独立回读才考虑后续交接，原33828/33829不动。
39157nu0自然5000、39197S24EON完整采样捕获和31707/38449alpha1队列继续，无push/PR。

UTC17:08：新38880已真实采用原生4000接续，39174为有效nu.3预算消费者。旧5055/6701、
37988/37989/38175全部退出且失败保留，不得恢复。38891完整218文件5包32434744B已
实际Git回读，补README/知识/本地commit；不要再等待此capture。后续必须完整12800链、
1200态场审计及各误差预算，不把prefix通过当全程合格。

39157独立nu0家族仅请求5000自然边界，原20277仍运行；39162等待新家族，39231只在
实际采用后捕获不可变交接。39073独立准备审查通过，未启动任何新nu0数值。旧38384
将随原家族自然终结，不能强改状态或signal原数值程序。39197等待37886全部采样/审计。
38663 N200 screen已completed/eligible但未采用；38676仍独立回读，结束后保存全证据并
决定新N200自然边界交接及预算路由。31707/38449继续锁外等待。HEADfce909d，无push/PR。

UTC16:45：38854独立review-retry3通过，38880/session80017已排队新midnight2接续，
adopted=false，原37988仍自然等4000。38891/session19819等新实际采用再捕获；未来
budget status elastic-s24-midnight2-budgets-current，当前未spawn。38827完整344文件
4包134713104B已completed，实际Git回读/本地commit进行中；不再等待该capture。

UTC16:40优先：跨午夜诊断elapsed误拒绝已修正并以Windows6+16/CI26、WSL28+8和真实
old100/双rank4400验证。代码尚未提交。37691/37700已failed不可恢复；新38663/session63590
仅复用已成功old100并跑剩余ILUT100/replay10，38676/session75952独立审查等待。
38827/session80874捕获完整失败/验证证据，完成后才实际Git回读、文档及本地commit。

37988原生4000仍按原请求自然推进。新midnight2接续只prepare，独立review-retry3
38854/session80612运行；通过后才启动新等待器，必须等旧37988实际失败和全部原族
自然退出、严格prefix/seed核验才接续。原预算37989和捕获38175届时会正确失败，保留
并使用新独立后继，不能改失败状态。首变量名/缓存比较准备审查失败均保留。
38384消费者和20277/29899家族的旧冻结解析器须另做后续路由修正；不编辑活动源。
38449 alpha1独立审查排队，31707仍等25665完整结束；无新alpha1采用。无push/PR。

UTC16:11覆盖：HEAD73a8c4f保存完整S96细N200；不再等待36172。新nu0预算38384/
session46596已采用，reference-nu0-recovered-budgets-current；原20925已计划退休且
无进程，不恢复。原20277未改，三组输入及预算算术逐字不变，未来EON比较连接已审核
的恢复路径。独立审查与57文件431780B捕获均已完成，保存本地commit。37988仍等
原参考4000自然停点，38175等实际采用；37691/37700筛查与审查继续。原alpha1筛查
31707仍等S48 N400完整结束/真实200/22GiB资源。不得提前push/PR。

UTC16:01：HEADad31460；36172完整S96细N200已completed，1672文件44包1820122244B，
单独实际Git回读/本地提交，不再等其写入。38175/session15667只等37988真实4000采用
再捕获封存前缀/交接，不能提前归档增长结果。37988仍未采用，37691仍old100，37700等。
9组正式生产正常推进。独立nu0预算20925仍等待原20277全部三组，后续EON路径已经过时；
准备新消费者、精确保留预算算术/同版审计并审核后才退休空闲旧等待器。此刻尚未交接，
不动20277及其后续coarse/time计算。无push/PR。

UTC15:52：37566与38013两完整档案540文件/11包/90162492B已实际Git回读并补README，
保存本地检查点；不再等待这两个capture。36172仍捕获S96全N200，增长档不能stage。
37886继续sample，37988继续等原参考真实4000，37989等采用；37691仍old100，37700等待。

UTC15:43最高优先：旧7140/7209已完成11600预热但在下一阶段的22/23独占guard失败，
7593随之failed退出，均不可恢复。实际EON采样是37886/session33816，状态
elastic-s24-sample11600-recovery-current，D/elastic-s24-l1-n400-sample11600-recovery-abec003；
独立两态全11datasets/五场/P1/legacyclock差0已审核，CPU22共享guest sibling/2GiBswap0。
旧reference-fine-ilut-handoff-abec003只prepared，从未执行；新37988/session90386
reference-fine-ilut-continuation-recovery-current已15:40请求原reference/results/STOP_SIM=4000。
此时5055/6701仍运行、adopted=false，等自然退出/完整prefix/native4000核验才新ILUT。
新budget37989 elastic-s24-recovered-budgets-current已等待采用，并绑定新EON路径和新参考
路径；原预算数值尾段不变。不能重启7593或向init.scope发信号。新review37948已PASS。
37566旧停止证明完整捕获已结束；38013/session39658捕获恢复/交接不可变证据，36172
捕获S96完整N200，两增长档不stage。37691 N200 screen已old100运行，37700独立review等待。

UTC15:22最高优先：37533的粗EON匹配审计已完成且所有物理报告值完全一致，粗参考
审计仍在运行；未发原参考4000停止。N200独立screen37691/session93901只等37566
完成，status reference-trilinos-fine-n200-screen-current；37700/session32509的
reference-trilinos-fine-n200-review-current只等该screen完成。两者都是新独立控制器，
禁止与旧fine-serial N400已完成证明混淆，也不得恢复旧失败trial。
N200600→700 old/candidate各100态、690→700 replay10，全字段/原生history/时钟/
成本门槛维持；CPU16共享nice19/2GiBswap0，尚未计算，更未交接正式N200。
完成后保存全部raw与独立review，另行决定是否准备长程交接；原9组生产继续。

UTC15:07调度覆盖：应用已成功重建当前聊天eonsim-new-48 ACTIVE，每30分钟至原窗口
终点；实际本地配置已回读。另一聊天的旧暂停任务未改动。37533审查和36172归档继续，
37566/session51341等待审查完成后捕获完整停止试验与不可变准备；尚无正式交接。

UTC15:00最高优先：HEADabec003，无push/PR。37309原生停止retry2已完成，37533独立审查
仍在运行；36325错误路径小试已受控取消并清空自有scope，不恢复。36172完整S96细N200
仍增长，不能stage。原9组生产者继续，原alpha1真实200已存在但31707仍等S48 N400资源。

- 新handoff仅prepare：reference-fine-ilut-handoff-abec003；独立review通过前不能执行run。
  未发正式stop、未取消7593、未启动新budget。run才会先启动新空闲消费者，校验原7593
  无子任务后退休它，写原reference/results/STOP_SIM=4000，等待5055/6701自然退出；
  核对完整prefix与真实seed后在CPU8接续。原nu0族20277和20925不在此交接范围。
- 新预算analyze-elastic-s24-ilut-budgets.py只替换fine参考路径，原数值预算tail逐字保留；
  37533正在实际重算已结束coarse两报告验证同版匹配，不能删除分析器身份检查。
- 完成停止与交接审查后，保存首次错误路径试验、正确两组10态、独立review和不可变
  准备/交接证据。正在写入的正式接续结果与日志不能混入完整档案。

UTC14:25最高优先：16aa5db已提交审计/三档；36093已完成，两后端证明26包565348664B
实际Git回读PASS，保存本地检查点。36172现在捕获完整S96细N200，尚未完成，不stage。
原5055(start2090032)/6701(start2254886)及7593(start2731595)仍活跃；原20277与
20925也仍活跃。这些老进程属于init.scope，不能用整个scope发信号。暂无新的交接
controller或采取动作，仅只读核对；必须把后续消费者及原失败尾段处理做完整再交接。

UTC14:17最高优先：HEAD27f5c82，无push/PR。35377、35431、33659、34564、34585、
36113和36128均已completed；不恢复30063/34488/34839/34864或已结束的筛查。

- S12完整参考链与S24粗EON配对28包440929264B已Git逐字回读；补齐README及进度，
  保存本地检查点。两侧Lamé和参考ALE失败保留，中p粗幅值3.112885%亦FAIL。
- v2后端切换审计/四组负例已通过Linux23+8、Windows受影响4项和两真实proof绑定，
  原S12 v1完整链12800最终方程行仍PASS。验证档1包63840B已实际入索引；没有C++变更。
  继续审查/保存，准备具体长期交接时必须核对原PID/start、真实边界seed、scope清空、
  新消费者和全部原始失败尾段；当前原5055/20277等全部未动，不能宣称已采用。
- 36093/session37552：native-reference-backend-capture-current，捕获两完整真实
  后端证明；增长中不得stage。36172/session61118：contract-s96-fine-n200-capture-retry2-current，
  小验证档已完成，正在等待36093结束后捕获S96细N200全部1200轨迹，排除活跃N400。
  首次36164因Windows路径不在helper许可root而failed，保留；retry先逐字复制至work，
  不修改冻结helper或复用失败目标目录。
- 新S96细N200六项初步门槛全PASS；29270现细N400，完整预算未完成。
  原S48alpha2N40025665约1440/2400；alpha1真实200已存在，31707仍锁外等原N400完成
  和资源，没有自动暂停/交接；20825仍等原alpha1。
- 原自动唤醒id13:54返回不存在，未重建。当前聊天继续执行，后台任务不等于交付。

UTC12:06最高优先：34839与34864现为failed，保留，不能恢复或改成完成。
已完成的参考800态审计可复用，ALE周期FAIL2.625e-5；失败原因是跨报告分析器身份
不一致。35377/session72761在独立s12-matched-analysis-recovery-243c9d0以参考同版
脚本重算EON报告，严格要求除来源SHA外全部值不变，再完成交叉比较。原完整收敛链
及参考审计不重跑；全部原始字节与失败日志须保持。后续capture-v3仅等新完整完成。

- 双rank34291全试验passed/eligible但不自动采用；34564独立审查中。原100/候选100
  耗时1839.648800/1407.776664秒，重放10步逐字一致，尚无后端切换全链契约。
- 34452细nu.3串行已12:00:38运行原100步；34585继续等待，原生产者不动。
- 34967 mesh-IC已完整结束，numerical PASS/cost FAIL1.420609，停止该方案；35283
  已捕获293文件/6包56,537,864B及先前取消的位置试验，12:07:04 Git逐字回读PASS。
- 35431/session46144：capture-s12-completed-reference-chain-v3.py，status
  s12-complete-reference-capture-v3-current；只等35377完成，保留全部旧失败和同版EON审计。
- S12 EON47包402,206,344B已Git回读PASS；33659 S24粗配对完成分析、正在capture。

UTC11:45最高优先更正：30063已6400数值返回0，但singleton辅助30077晚退出导致
controller failed；清理完成且scope空，原失败不改。34488等待器也已failed，不恢复。

- 34839/session47501：finish-s12-native-audits.py，work/s12-native-audit-recovery-243c9d0，
  status reference-s12-native-audit-recovery-current。CPU13nice19/2GiBswap0；全801原始
  场/最终6400种子/字节哈希已核验，无数值重跑。原本应做的完整链12800最终方程行已PASS，
  现800态audit，随后observables/200phasefields；最后再次核对全部原始字节不变。
- 34864/session5970：capture-s12-completed-reference-chain-v2.py，work/
  s12-complete-reference-capture-v2-243c9d0，status s12-complete-reference-capture-v2-current。
  只等待新34839完整completed，保留原12h失败、收尾失败、34488失败和所有完整证据；未开始capture。
- 34967/session69921：screen-reference-mesh-ic.py，work/reference-mesh-ic-screen-243c9d0，
  status reference-mesh-ic-screen-current；CPU15nice19/2GiBswap0，各1200秒，持独立review锁。
  相同candidate121678/FSI-ILUT的20态基线与仅mesh改Trilinos-IC的20态，再候选10态重放。
  保留mesh CG、组装选项0、原物理/容差，真实满载6000种子；全场/历史/时间/收敛/成本≤.9
  才eligible，仍无自动handoff。固定源码READFILES.f和LS.f提供此选项，未改上游。
- 34291原100态已逐字重现实际2700（1839.648800s）；候选约2668/2700。原生产者未动。

UTC11:28最高优先：HEAD243c9d0784b18d55d8b267fa0554767f20ca7554，无push/PR。

- 34291双rankretry仍做原100态；review34564/session70457等待它完整结束，helper
  review-reference-native-backend.py two-rank，work/reference-trilinos-two-rank-review-243c9d0。
- 34452/session86261：screen-reference-trilinos-fine-serial.py，work/
  reference-trilinos-fine-serial-screen-243c9d0，status reference-trilinos-fine-serial-screen-current。
  等probe锁，原nu.3细网格实际2800→2900原100/候选100与2890→2900重放10；CPU16nice19/
  2GiBswap0，每模式3600秒。原实际2900算法字节必须重现，生产5055不变；没有自动交接。
  review34585/session81384随后等待，helper同上fine-serial模式，独立分析锁/CPU15/2GiB。
- 两个review目录已有11:21:58 static-input-check.json：实际case、geometry、两网格、
  export manifest及P1归一化独立核对PASS。只支持输入不变，不是数值或完整review通过。
- 34488/session29052：capture-s12-completed-reference-chain.py，状态
  s12-complete-reference-capture-current；等30063全6400/800态/链/交叉分析completed，
  才捕获elastic-s12-reference-complete-native-chain-2026-11-08，保留原12h失败和原始尾部。
- 当前40提交对象只读分批检查PASS，raw6.338GB可分五次≤1.9GB快进上传；全部验收后
  复核最终远程/对象，不提前推送。原生链用户文档补齐1/2rank边界，仍拒绝隐式后端变化。

UTC11:05证据覆盖：34227和33919已completed。三档23包/465596100B的实际Git回读
全部PASS；新增双rank解析器/19+8测试证据及相关九份代码/文档准备保存本地检查点。
28745仍增长，33659仍等待；34291在原算法100步阶段。没有push/PR或后端交接。

UTC10:57最高优先：HEAD1374b625，本地推进、无push/PR。Trilinos启动及S12真实满载
串行20态/10态重放均已独立通过；未采用，完整链的后端身份仍严格检查。

- 34291/session52411：`screen-reference-trilinos-two-rank-retry1.py`，work/
  reference-trilinos-two-rank-retry1-1374b6，status reference-trilinos-two-rank-retry1-current。
  CPU10/16共享nice19/2GiBswap0，各模式3600秒，实际2600→2700原100态必须与原实际
  2700每rank算法状态逐字相同（只排除elapsed和padding）；然后候选100/重放10及五场、
  全native历史、收敛、成本≤0.9。不得自动交接。34174旧试验因CPU12/13竞争已取消，
  自有scope清空、原失败和部分结果保留；不得恢复。原20277正常继续。
- 34227/session23031：`capture-reference-backend-and-parallel-audit.py`，status
  reference-backend-audit-capture-current。第一档native-two-rank-record-audit已完成28文件/
  1包/2781956B；第二档reference-trilinos-serial-proof仍增长，完成后才逐字Git回读/暂存。
  包含固定上游源码、编译参数、原始oracle/全输出与两个独立review；排除活跃双rank。
- 33919/session92673：捕获完成的native S96粗N200/N400时间对，status
  s96-native-coarse-time-capture-current；六项N400初步门槛通过不代表完整细层预算。
  29270细N200已过600；原25665/20806/20825和实际200筛查31707依赖不变。
- 30063 S12恢复约6212/6400，日志work/s12-native-recovery-a6643c8/svfsi.log；完成后
  自动全链/800态/同算例比较。28745完整EON捕获仍增长，33659等它结束后比较S24粗两边。
  S24 EON粗6659已完成，Lamé3.195039%FAIL；实际继任33828/33829细N200，参考29899/29901。
- 新19参考+8压力测试、真实5份原生文件解码均PASS，新增代码只涉及审计/测试，无C++变化。
  复用8297的CI选择/Debug/Release针对性检查，不为文档或提交重跑无关数值测试。

UTC09:58最高优先：HEAD8297a417已提交原生审计及四档，未push/PR。S24粗参考完整档案
1377文件/3包/109010096B已索引回读，README明确ALE周期FAIL；S12 EON归档28745仍活跃，
不得提前索引。30063恢复约5918/6400，完成后自动全链/全场/同算例交叉对照。

- 31707/session73476：实际alpha1第200步筛查仍在锁外等待；status
  alpha1-checkpoint-lu32-screen-current，D/alpha1-checkpoint-lu32-screen-8297a4。
  原20806约172/1200、20825仍等待原生产者，未退休/改绑。读取器在旧启动样本320
  数据集已PASS（work/alpha1-full-history-reader-check-8297a4），不是实际200态筛查通过。
- 31784/session24813：新粗N400 companion，status s96-coarse-n400-companion-current，
  work/s96-coarse-n400-companion-8297a4，D/womersley-a2-s96-r8-a8-l0-n400-native-serial32-8297a4。
  原生1rank/60eb/window32/CPU15nice19/2GiBswap0，fresh2400/六周期/400相位，末尾比较
  同粗N200时间/尾项；原fine-N200预算算术不变。当前约892/2400，尚无完成指标。
- 31946/session95993：独立参考Trilinos构建/20态试探；status reference-trilinos-screen-current，
  work/reference-trilinos-screen-8297a4，helper screen-reference-trilinos.py。
  同上游PIN原码复制、已有系统库、CPU16nice19/2GiBswap0；构建2400秒，FSILS/ILUT各1200秒。
  只改FSI后端，mesh仍FSILS；全物理/容差不变，restart每步供全历史比较。即使eligible，
  成熟真实checkpoint及独立审查仍须完成后才能改消费者。不得覆盖原build或原生产者。
- 33204/session33072已09:58:26完成已验证读取器及两项任务不可变定义的捕获：35文件/
  1包/222784B，引用已归档同SHA网格，排除增长结果和未获得的200态。状态
  handoff-preparation-capture-current；10:00:53实际Git字节回读PASS。

UTC09:12最高优先：`0029a7e`已本地保存三组Womersley档案。新续算审计及CI映射完成
针对性验证（16参考+8压力，另26选择+6证据、Debug/Release各1Poisson），未重跑全套。
S12原生证明、S96粗完整、拒绝参考筛查、新审计验证四档共4824文件/13包/185,520,052B
均已实际Git回读，代码/文档检查点待提交。30063的S12恢复仍运行，不宣称6400完成。

6673已08:45:10完成S24粗N400参考12800，但ALE周期差约2.2113e-5 FAIL1e-5；其余
五场中的四场、收敛、质量通过也不替代这个失败。实际继任29899/CPU20运行细N200。
独立nu0系列20277和各原生产者继续；31614/session43442已捕获新验证、正捕获S24粗
参考完整一侧，EON增长路径排除。28745仍捕获S12 EON完整一侧。未push/PR。

UTC08:58最高优先：原生S12有限续算及独立真实收敛链已PASS；最终review在
work/s12-native-restart-review-final-a6643c8（16+8测试、20态五场差0、10态完整历史
除elapsed逐字一致）。实际全6400恢复30063/session65771于08:52:59运行，状态
reference-s12-native-recovery-current，控制work/s12-native-recovery-a6643c8，结果
D/reference-s12-native-recovery-a6643c8；CPU13共享nice19/2GiB/swap0，timeout18000。
不得恢复原3224/3226；原失败保留。完成后自动全链/800态/同算例交叉审计，物理门槛不变。
新source审计代码与针对性测试已实现，原生证据30090/session51962正在归档；不收活跃结果。
已结束的三个Womersley档案76包/1,783,550,240B已实际Git字节回读，保存本地检查点。
28663两档捕获完成、尚未索引；28745已开始S12 EON完整捕获。未push/PR。

UTC08:39最高优先：S12参考3224/3226已原定12小时timeout失败（5641完整、5642部分），
不再运行；6673已07:35:17接CPU20开始S24粗N400。保留原失败及stFile_5600.bin。
有限续算第一次29610在内存限制刚建立时失败、无求解；独立retry2的29691/session20654
08:36:58在CPU13nice19/2GiB/swap0运行20态续算及10态原生重放。新status
reference-s12-restart-screen-retry2-current；结果在D/reference-s12-restart-screen-retry2-a6643c8。
先全场/完整序列化历史/原生时间验证，再实现并测试显式分段收敛链；未允许完整恢复采用，
不得把旧失败抹去或把续算输入改写为Continue0。实际运行证据通过后才能新路径恢复至6400。

29270粗层1200与802保留态MPI/历史核验已PASS：20050数据集，node/history1.0408341e-17，
P1质量1.4500918e-16，exactv4；08:30:27开始fine-n200。28315完整细轨迹与29287第一组
alpha1启动档案已完成，正在Git回读；28663捕获S96粗，29287捕获S96筛查，28745排队。
仅完成的档案才能索引；每次本地检查点保持未来单次上传低于GitHub2GiB边界，不提前推送。

UTC08:14最高优先（覆盖下文所有“准备/等待采用”）：

- 28580已在完成640数据集原始回读后、没有子进程和任何长计算时退休；状态为
  cancelled_before_long_work，完整筛查/cancellation/handler failure保留，不得恢复。
  分区单rank29062和原生单rank29167均已32态completed；原生方案394.727331581秒，
  对四rank8/32成本比0.418385/0.624509。08:08:07独立960数据集审查通过；native
  report SHA d312e87a41dd38d379b72e5b5fe8ef29467d04e8488097ef278fe705ad2557a9。
- 实际采用的新生产者29270/session91679，状态rounder-native-serial-a2-family-current，
  控制work/rounder-native-serial-a2-family-a6643c8；helper run-native-serial-a2-family.py
  SHA39f10545d54a7a23ca4d249748f7b10d3686c86d7f32791e2d56bced7c5d76df。
  CPU21单rank6GiB/swap0/14GiB入场/8GiB下限，native全局网格路径与既有driver一致。
  新D/womersley-a2-s96-r8-a8-l0-n200-native-serial32-a6643c8，然后l1-n200及l1-n400。
  粗1200后先全802保留态MPI/历史/clock对照，预期20050数据集、节点2e-9/质量1e-8；
  该worker已冻结SHA bde0e60fc5a778147df3f2e217dd8d03914c9198a27c56983f3d9f4ef69f2a70。
  原budget算术SHAaae1723...不变；目前粗层已200，不能报告粗MPI或细资格通过。
- 25408已completed且480数据集独立review通过，只alpha1启动eligible；没有退休20806。
  原alpha2N400实际25665已07:52:01开始fine-n400-c6，目标/预算仍原匹配S48系列。
- 新29287/session89907、execution-screen-capture-current，用CPU15nice19顺序捕获
  womersley-alpha1-lu8-startup-2026-11-08及womersley-s96-fine-execution-screen-2026-11-08。
  后者仅纳入已结束筛查与新family不可变定义/源码，排除其增长中日志/结果。
  28315/28663/28745仍按下文顺序在CPU17归档。只索引完成并逐字回读的档案。
- 本地只读object-budget-a6643c8.json统计36个新提交、3,786,182,556B新对象，最大单提交
  770,519,369B、单blob86,012,108B。[GitHub单次push上限2GiB](https://docs.github.com/en/get-started/using-git/troubleshooting-the-2-gb-push-limit)
  已核实；后续单提交保留余量，全部资格通过后再分批fast-forward推同分支，最终才PR。
  当前没有上传；不要force-push、重写历史或把分批传输当成提前发布授权。

UTC07:46优先覆盖新S96细层选择：暂不执行会写adoption token的
`review-rounder-fine-refresh32-retry2.py`。先等28580完整结束32态两组；执行只写
startup-only-review.json的`review-rounder-fine-startup-only.py`（SHA
f44ffdaf033369efe554afa707b56800f25eb04893d3bf1c646e0bcc6384ccc4）独立回读。
如果状态awaiting_independent_review，准备的`retire-rounder-fine-review-waiter.py`
必须核验28580/start_ticks6031536、controller哈希、无子进程、两个资源锁归属、原始
回读和空scope、无长研究路径，再只退休此空闲等待器并记录cancelled_before_long_work。
若成本未过而已completed_screen_only则无需信号。完整筛查轨迹及任何退出handler记录保留。
然后才能运行已准备但未执行的`screen-rounder-fine-serial.py`：正常取得small-direct/middle
锁，单rank/CPU21/6GiB/swap0，32态、1200秒限时，所有当前/历史场按mesh_node_id与
唯一owner拼接，精确v4、节点2e-9、归一化P1质量1e-8、实际2LU，以及对两四rank模式
均≥10%成本收益。只写候选报告，不自动采用。后继长研究控制器需在选择后显式另建；
当前N200/N400未来路径尚未开始，不能把准备脚本记为已运行。原S48/弹性/参考继续。

UTC07:32最高优先接续（`a6643c8`已本地提交，未push/PR）：

- 27988/session59577已在任何数值工作前failed，不得恢复。原因是粗层释放资源锁后才
  写completed，后继在间隙断言失败。原D/rounder-fine-refresh32-screen-d844e40完整保留。
- 实际新细层为28580/session92098，helper `run-rounder-fine-refresh32-retry2.py`，SHA
  a4488deb891ba693b970c02b0bd2a1116e7fcdcf1360104122763bad4f02e814。
  status `rounder-fine-refresh32-retry2-current.json`；D/rounder-fine-refresh32-screen-retry2-a6643c8。
  先锁外等粗层completed，再获取原small-direct/middle锁并复查；07:22:44起window8筛查。
  6GiB/swap0/CPU21四rank、14GiB入场/8GiB下限；实际5/2LU、640数据集、v4exact、
  成本比≤.9保持不变。只有awaiting_independent_review时，检查report后运行已准备的
  `review-rounder-fine-refresh32-retry2.py`重读原始字段/事件/资源；decision必须是
  `run_rounder_fine_refresh32_retry2`且哈希吻合。尚未采用长研究。
  未来细N200/N400明确改绑D/womersley-a2-s96-r8-a8-l1-n200/n400-refresh32-retry2-a6643c8；
  粗分母仍D/womersley-a2-s96-r8-a8-l0-n200-refresh32-d844e40，预算算术不变。
- 27906/session22160已07:14:29完成1200+analysis/tail。周期通过，Q幅值1.058047%FAIL1%。
  25368/session80268已07:13:21完成原S48细1200+分析，U1.046822%FAIL1%；实际匹配
  原N400仍25665，25408短筛查先占细层资源，原20806 alpha1继续。不能恢复25369。
- 3212的S12 EON已07:25:39完整6400+800态审计完成，周期/质量通过，Lamé均值4.802660%
  FAIL2%。6659/28651已同刻启动S24粗N400；参考3224、6673及其它系列不变。
- 28212 NS与28423 RCS均600秒timeout，scope空、零内存事件，均未采用；原参考继续。
- 28315/session91538捕获完整原S48细轨迹；28663/session17747等其结束后串行捕获
  新S96粗层+首细启动失败，再捕获两参考试探。28745/session10669再等28663完成，
  捕获已结束S12 EON侧，明确排除仍增长的reference目录及svfsi日志。
  状态分别alpha2-fine-complete-capture、coarse-reference-capture、s12-eonsim-complete-capture
  加-current.json。四档案名分别womersley-alpha2-fine-lu8-complete-2026-11-08、
  womersley-s96-coarse-refresh32-complete-2026-11-08、reference-native-solver-probes-2026-11-08、
  elastic-s12-fine-eonsim-complete-2026-11-08。只在完成后按既有普通blob方式逐包索引回读。

UTC06:49最高优先：27539/27620/27930以及之前全部归档均completed，五新档案实际blob
已索引回读，共9469文件/36包744408996B。需完成本地review/commit，仍不得push/PR。
27732成本retry2于06:35:28结束；独立回读2560datasets和事件/资源后review允许新粗层。
新32耗时57.494s，相对old8前后103.181/87.337s均达10%；新8对后baseline仅5.70%不采用。
原27575检查脚本默认PREONLY误判失败保留在完整1296-file成本档案。

27906/session22160新coarse已于06:41:24采用候选60eb/window32、S96r8a8level0、alpha2
N200、warmup2/cycles6/phases200、每周期分段，CPU21四rank idle-yield、2GiB/swap0。
status rounder-coarse-refresh32-current.json；work/rounder-coarse-refresh32-d844e40；
D/womersley-a2-s96-r8-a8-l0-n200-refresh32-d844e40，已完成200周期收据，后续analysis/tail。
新27988/session59577仅waiting_for_resources，冻结run-rounder-fine-refresh32.py SHA
38b8ae8630f0d93261bd21a1a4338b296cc92bc7ed307b1f8a136ea76bc9ce07。
它使用同small-direct/middle锁串行等粗层完成，不占原global fine队列；CPU21/6GiB/swap0，
14GiB可用入场、8GiB全局下限。先fine32态窗口8/32，要求实际5/2LU、640datasets/v4exact、
cost≤.9才eligible；等待独立review.json最多1800秒，decision=run_rounder_fine_refresh32，
report/definition/candidate哈希必须匹配才采用。status rounder-fine-refresh32-current.json；
D/rounder-fine-refresh32-screen-d844e40；未来study/target分别womersley-a2-s96-r8-a8-l1-n200/n400-refresh32-d844e40。
Fine N200/N400、原门槛及middle/space/tail/sampling预算自动接续；算术SHAaae1723d5c1148f31c13c0ff88e50e4df6bd049e877f8eb3e6abd8607ef6b49c未变。
当前未完成fine筛查、无fine采用。原S48fine25368、N40025665、alpha1screen25408及其它长程均不变。

UTC06:31最高优先接续：middle25664已完整1200及分析完成，U1.851116%FAIL1%，
末两周期通过；3713文件/10包214006344B已索引核验。fine25368原f7/window8最近1056，
继续到1200；唯一有效alpha2 N400等待器仍25665。alpha1八步筛查25408继续等待，
原alpha1和弹性/参考任务不变。不得恢复旧fine/middle或取消的25369/26278。

单cycle4诊断U1.046822%FAIL1%，1023文件20包474290060B完整归档并实际Gitblob回读；
它不是三周期或预算资格。新S96窗口32旧f7启动32态成本127.681/95.526=1.3366，
数值640dataset通过但成本失败，不采用；其fine等待器26278已无数值工作地取消。
归档等待器26664因两份report.json复制重名在捕获前取消；新27539/session34461
capture-rounder-startup-screen-v2.py在06:27:28开始捕获，status rounder-startup-capture-v2-current.json，
原两个报告均保留，副本取不同名称。27620/session98154验证归档排其后。

有效时间系数刷新五文件代码已完成26487/session6231验证：Debug/Release各6项和
各1005HDF数据集通过，最大1.46506e-14、v4exact，候选Release SHA60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07。
work/lu-time-refresh-validation-d844e40冻结源/报告不改。默认0不变、缓存仅PC执行态。
旧27575/session24899成本筛查失败是checker误要求默认PREONLY为FGMRES；两组原始
成功输出和failure.json都保留。新27732/session83462、screen-lu-time-refresh-startup-retry2.py
在D/lu-time-refresh-startup-screen-retry2-d844e40复核旧两组，再执行new8/new32/old8-last。
禁止把未完成筛查当性能通过或采用；接下来独立回读报告/因子事件/完整历史，再决定新几何研究。
继续完整48h目标、证据/草稿及审查，全部真正验收前不push/PR、不合并。

UTC05:30最高优先接续：25368细alpha2和25664中层alpha2均运行f7/window8，分别
从600/480续至1200，当前都有800完整收据。中层scope2GiB/swap0、CPU21；细scope14GiB/
swap0、CPU0–7不变。中层status womersley-middle-lu8-boundary-current.json，work控制目录
womersley-middle-lu8-boundary-2367903，D/womersley-a2-s48-l1-n200-lu8-m480。
**旧7509/7603/24479/24482–24485及21873/22001/21907均gone，不得恢复**；下文pause为历史。
原25369等待器已取消且无计算；当前25665状态womersley-time400-a2-lu8-middle-current.json，
冻结queue SHA1ccca6dffe4ab3887657e5fa6c320a3ae317923ec9050583270081ea834e50a9。
预算必须等新middle1200完成；等待释放资源，五种admission实际检查/AST/未改预算尾通过。
25408 alpha1筛查继续等待fine完成，原20806及20825不变。没有活动暂停者。
25460/25725均完成：[855文件细handoff](../research/data/womersley-lu600-handoff-2026-11-08/README.md)、
[833文件middle](../research/data/womersley-middle-lu8-2026-11-08/README.md)。25785存储捕获也完成；
其39,834,848B包实际加入索引并逐字回读，保留D原件为稀疏工作树节省一份重复文件。
后续大归档可用已验证rank-order/external helper，但**每个part必须实际索引为完整Git blob
并核对后才能提交**，不能只提交外部路径。所有长物理资格/预算继续，不push/PR。

最新接续覆盖：细screen24147已完成并恢复原driver后，由内部独立review批准单独交接。
25368/80268于04:28:40实际采用window8，从600续算到1200，scope eonsim-lu8-continuation-25368.scope；
work/womersley-lu8-boundary-e435524，D/womersley-a2-s48-l2-n200-lu8-m600。旧21873/22001/21907
已gone，旧scope空，**不得按下文历史pause记录恢复**。25369是新N400等待器，状态
womersley-time400-a2-lu8-current.json；新queue sha122b82754868b29023901809099d82fc0bc9e30fe905fc14fbc99deeb0de074e。
其等待中层阶段释放资源、分析前重新取锁，数值算法不变。
25408/36908运行alpha1 LU筛查等待器，未暂停alpha1；须25368完成后持全局资源锁入场。
25496/74833运行screen-alpha2-middle-lu8.py（sha faa6d713dc6f113de6ba70e11b8c93743d4dbee95b9556f6f8d68123488fe11f），
等原中层完整488，取480种子/连续481–488对照，再暂缓7603/24479/24482–24485；owner7509保持。
新scope仅2GiB/swap0，10GiB可用内存入场、8GiB运行下限，CPU21四rank闲等让出，900秒/模式；
三模式完整历史/连续轨迹/真实分解/双baseline≥10%成本都通过才eligible，始终先清空scope再恢复原六进程。
不得抢先恢复正在借用CPU21的原中层进程，不改变细25368或原alpha1。中层尚未采用。
25416细归档已04:40:12完成330文件/7包155,598,764B；25460后续交接归档仍写入，不暂存其目录。
完整证据见[细screen](../research/data/womersley-fine-lu-screen-2026-11-08/README.md)；长期资格未通过，不push/PR。

UTC04:03最新：参考筛查24508/24851/24930均已结束，三次自有scope都为空；
alpha1的21493/21499/21502–21505全部已恢复，最后恢复03:57:42。两次四rank失败，
双rank20态通过但成本收益9.68%未达10%，没有采用/更改20277长期参考策略。
25048归档于04:00:51完成，162文件1包17,790,032B；旧失败和MS未收敛输出5保留。
CPU资源标签统一按[WSL/Windows实测](../research/data/execution-topology-2026-11-08/README.md)
解读，不能把WSL12个核组说成宿主12物理核，也没有宿主绑核证据。

24147/86102继续等600；22001仍是它有意暂停的alpha2 driver，**不得恢复**。
准备的`screen-alpha1-lu8.py`尚未启动，须alpha2细cache完成、独立review且已采用，
然后等待其完整新N200结束并取得全局内存/CPU锁，才运行alpha1八步三配置对照。
该准备不构成采用、性能或长期通过；21873/21907仍是当前生产/等待器。

UTC03:12：21979已completed，三组原始证据README已补齐。24147仍在等自然600边界；
22001保持有意暂停、原数值子进程运行。准备但**未启动**：`handoff-womersley-lu8-m600.py`
（sha130e9c77f515d283b7c9718dc340a1fbc5878122246ffc7b9950b543752b4dfa）及
`queue-womersley-time400-lu8.py`（sha38b47f1af4ffe1beda8189a0dec4e769fc5645774bac0bbab47dece45680dc61）。
前者须完成筛查eligible、原driver已恢复及与report哈希匹配的内部handoff-review.json；
先准备新研究/新等待器，再取消原21907并通过原21873正常清理整个scope。尚未执行。
新N400预算尾段与旧控制器逐字一致，sha5746119ef3c503b74a458828a6f90a47f8fbc18c942762e904dbfd35c063f067。
这些预备文件不构成性能或采用结论；全部原物理门槛继续适用。

UTC02:57最新安全接续：e435524本地提交完成，24147/会话86102运行
`screen-lu-reuse-cycle600.py`，状态`lu-reuse-fine-screen-current.json`。
**22001是有意暂停的研究driver**；原21873监控/锁继续，22002/22005–22008数值子进程
正常推进到600。不要SIGCONT22001或重启主MPI；三种新probe scope都结束后24147会
自行恢复它。若24147崩溃，先按D/lu-reuse-fine-screen-e435524的definition/pause核对
start身份、清理仅属24147的新scope，确认为空才恢复原driver。筛查1200秒/模式、
14GiB/swap0、八步完整场/历史/时钟/实际分解计数/至少10%局部收益，只有eligible，
不自动采用。原21907未取消、仍等待。126份不可变启动证据已归档。
21376的r4归档已完成；21979转whole-job-fine-screen，不暂存其增长目录。

UTC02:37最新：LU数值入口小验证和归档完成（23025、23773、23974均completed），
Debug10项通过，Release三次尝试合并明确来源覆盖10项；两次失败保留。每配置455个
HDF数据集max1.0402e-12，真实CLI1/2rank各13态max1.1720e-14且时钟exact。
下一步是同态细网格有界成本与独立采用审查，尚未暂停21873/22001或替换21907。
必须等待原MUMPS自然段结束释放大因子，不能暂停全部原MPI后再并发第二个大MUMPS。
原长程继续，所有物理门槛不变，无push/PR。

继d0f9bb3，领取可独立验收的可选LU预条件器复用：当前细直接解每步约60秒主要耗在
重新分解。只复用MUMPS因子作FGMRES预条件，当前Jacobian/残量/物理容差不变，默认关闭。
必须验证1/2/4rank、改变算子/步长、完整历史/恢复、窗口重建、异常失效及不支持配置拒绝，
再做同态细网格有界成本对照（字段2e-9、至少10%收益）；未验证前不采用、不改冻结长任务。

UTC02:27：LU首次22152失败已保留；共享PC仍被SNESReset清因子。修正后22647的
Release4项通过，但HDF审计发现重复测试目录含两代同一步记录而中断。新23025/
会话56958，`lu-reuse-validation-retry3-current.json`，每次独立测试目录；Release
完整455数据集通过，最大1.0402e-12，时钟/元数据精确。Debug10项进行中，尚未
做细网格成本或生产交接。26项CI选择规则检查通过。冻结检查期间不编辑相关源码。
修复后clock/direct原失败/alpha1中层三档案已完整，r4仍写入；21979等其完成。

UTC01:51覆盖下文等待状态：21873已通过实际460→463/原连续463对照，完整历史max
4.4264e-12、时钟差0。01:50:05起adopted=true，旧7542/20170/20171/20174–20177及
20754/20817均已退出，不得恢复。新target已开始continuation，实际scope为
`eonsim-mumps460-continuation-21873.scope`，包括研究driver及嵌套MPI会话；14GiB/swap0。
21907继续只等完整N200。新21979/会话79950，direct-policy-capture-current.json，
`capture-direct-policy-followups.py`，等21376完成后串行归档完整screen、alpha1/nu0
已完成预检及交接不可变输入。控制源码都已冻结，正在写的归档目录不暂存。

UTC01:44最新覆盖（下文保留历史）：

- cgroup筛查21516已完成并恢复20170/20171/20174–20177，当前原主流体正常运行。
  D/womersley-cgroup-screen-5091b68，181.986/353.400秒，max5.2965e-12；仅eligible，
  未直接采用。21129的3.5GiB/rank地址空间失败已结束，不能写成此新资源策略失败。
- 新21873/会话53697，`handoff-womersley-mumps460.py`，状态womersley-mumps-boundary-current.json，
  控制work/womersley-mumps-boundary-5091b68，目标D/womersley-a2-s48-l2-n200-mumps-m460。
  不持锁等待460/连续463；随后暂缓已核验六进程，在同态三步/历史通过后才取消旧等待器
  20754/20817、停止旧7542家族并显式派生。未采用前失败须恢复原进程；不能手工抢先恢复
  正在probe时有意暂缓的进程。14GiB整作业/swap0、启动可用>16GiB、运行低于8GiB停止；
  整个作业包含嵌套会话并已验证清理。源码与检查收据均已冻结；禁止改活控制器。
- 新21907/会话42811，`queue-womersley-time400-mumps.py --alpha 2`，状态womersley-time400-a2-mumps-current.json，
  控制work/womersley-time400-a2-mumps-5091b68，未来D/womersley-a2-s48-l2-n400-mumps-paired-5091b68。
  等新N200完成，不持计算锁；同binary/MUMPS/chord、同网格、总六周期始终固定，单次1周期。
  沿用原预算完整实现（逐字相同已核验），全局direct-memory锁限制同时一个直接细作业。
  旧alpha1 N400等待器20825不变。此时旧20754/20817尚在等待，取消以新控制器收据为准。
- 小检查21659完成，331文件已归档；cap runner21835正常/强制清理通过。生产C++未改变，
  未重复全套/旧PETSc。新CLI源SHA a84c28bc…，运行控制器均匹配此已测源码。
- r4完成并通过，16987已退出。20806细vector已于01:19:38启动；1180已经退出，不得恢复。
  20277已采用双rank在CPU9/23计算独立nu0细S24；20925继续等三组预算。20351已于01:43:40
  完成repaired；21376继续原直接解失败、中层、r4，01:51:24已转rank4；正在写的目录不能暂存。

UTC00:55优先状态：

- 旧直接解等待器20915在runs=[]时计划取消，不得重启。实际MPI每rank独立进程组，
  新helper `screen-womersley-fine-direct-session.py`按完整新会话/启动身份清理。
  新21129/会话23593，womersley-fine-direct-screen-retry2-current.json，D盘
  womersley-fine-direct-screen-30828c5-attempt2；持option锁等20806的middle分析，
  中层5422继续。900秒/3.5GiB/2e-9/10%门槛不变，筛查仍未执行/未采用。
- work/womersley-direct-session-cleanup-30828c5的真实4rank orphan清理检查通过；
  work/womersley-direct-screen-replacement-30828c5保存取消身份/收据。项目Linux
  study.run同类修复的7项Python与真实2/4rank检查在study-session-cleanup-validation-30828c5，
  24文件已核验；原所有长控制器仍旧冻结源，不能声称已自动升级。
- 原7370失败24550文件26包与nu0完整参考1783文件2包已完成归档，可提交这两个目录；
  20351归档队列00:54:39转boundary，之后repaired。仍在写的目录不可暂存。
- r4已到12800并进行audit/1200态比较，尚无完成收据。20277及20925依旧等待；
  alpha1中层接近1000。当前源码修复及新证据需完成文档/自审后本地保存，不push/PR。

UTC00:34补充（原队列不变）：

- 20915/会话60954，womersley-fine-direct-screen-current.json，
  `screen-womersley-fine-direct.py`，D盘womersley-fine-direct-screen-c509af0。
  持mpi-option-probe.lock等20806的middle-analysis-completion；不占数值主锁、不中断
  中层5422。然后CPU10–17同400种子/同candidate162 binary三步MUMPS/chord与
  Schur/vector/chord对照。每配置900秒、每rank3.5GiB地址空间，起始可用内存>16GiB、
  运行中低于8GiB则停止自有组。候选失败保留并跳过重复baseline；字段<2e-9、正收敛
  和局部成本至少降低10%才进入独立采用评估，不会自动交接。释放选项锁后20806继续
  既有预检与方案；禁止改这两个冻结控制器或抢先恢复1180。
- 20925/会话50721，reference-nu0-s24-budgets-current.json，
  `analyze-reference-nu0-s24-budgets.py`，work/reference-nu0-s24-budgets-c509af0。
  等20277的独立nu0三组结果，不持分析锁；原study/analyze算法逐AST相同，物理输入
  哈希和nu0变体身份另验，再持elastic-budget-analysis.lock/CPU19审计全部五场预算。
  最后等原EON S24 fine完成做同网格跨程序观测量比较。原nu.3失败和原7593预算不变。
- 30份冻结源/身份/启动状态已归档bounded-followup-startup-2026-11-08；仅启动通过。
  原大归档20351/20352继续，未完成目录不要暂存。原r4约10000、中层约914步。

UTC00:17最新控制器（替代下文旧等待器，不替代其历史证据）：

- 旧15446/15457/7639已计划取消，均未启动细/N400数值工作。取消收据在
  work/segment-controller-replacement-08718b9；不得重启旧控制器。
- 主alpha2新增20754/会话73777，womersley-segment-boundary-current.json，
  `handoff-womersley-segment600.py`，work/womersley-segment-boundary-08718b9。
  当前不持锁、只等待。原7542/20170/20171及20174–20177仍运行。完整600与603
  检查点确认后，保存种子/连续参考并停止仅已核验的20170进程组，等原父释放锁，再做
  同binary三步重启对照；字段/历史<2e-9、legacy时钟<1e-12且正收敛才派生D盘
  womersley-a2-s48-l2-n200-segmented-m600，按每周期分段完成4–6周期。清理失败则
  不启动新解算，保留失败等待处理。新旧研究不能混淆，旧数据完整保留。
- alpha1新20806/会话39670，alpha1-fine-vector-segmented-current.json，
  `handoff-alpha1-fine-segmented.py`，work/alpha1-fine-vector-segmented-08718b9。
  1180已重新被它有意暂停，当前子5422仍运行；不能手动恢复1180。中层自然1000步后
  仍做原四核三步字段/成本预检，通过才运行D盘womersley-a1-s48-l2-n200-vector-segmented。
- N400新alpha2 20817/会话56569、alpha1 20825/会话47942，
  womersley-time400-a{2,1}-retry4-current.json，`queue-womersley-time400-segmented.py`。
  控制目录womersley-time400-a{alpha}-08718b9-attempt4，目标D盘
  womersley-a{alpha}-s48-l2-n400-paired-08718b9。均等待新N200状态，不持主锁。
  每次数值调用最多1周期，CLI时限86400；5→6周期计划、同binary/选项和预算前提不变。
- 上述114份替换证据已核验归档。参考nu0 S24队列20277和原始大归档20351继续；
  不得修改其冻结源码，原r4和全部其余长研究继续。

自然周期分段增量（86bbdac后，尚未交接现有长控制器）：

- `study_womersley.py --cycles-per-solve N`保持总终止时间和相位保存频率，单个数值
  调用最多N个完整周期；未指定仍原两段方式。`--timeout`仍最多86400，不绕过入口限制。
- 新v4验证20389/会话20157和旧v3验证20559/会话91173均完成。各真实1/2rank、
  16接受步、13存储态、65/130数据集全部通过；旧v3只沿用近似时钟契约。604文件已归档。
- 7542/7639/15446/15457仍原冻结版本，不能把新脚本当作已被它们使用。下一步先准备
  新控制器并核对身份；等待器可在任何数值工作前明确取消/替换。运行的alpha2必要时
  在完整周期检查点派生续算，保留原始数据和计划中断收据。原资格/预算门槛均不变。

UTC23:54最新（优先于下方历史状态）：

- 原7370生产MPI已失败退出，错误rank0/clock；r1/r2各12800物理审计通过，1200相位
  rank对照及400相位重启字段通过，但完整HDF比较在时钟停止，不能说全历史通过。
  原失败不得重跑或覆盖。新v4保存补偿求和余量，旧v3兼容仅承诺容差级时钟。
- 修复验证15868完成，clock-checkpoint-validation-current.json；PETSc3.23.7
  Debug/Release各8项通过，10464文件已归档。新二rank生产复核18205，
  elastic-clock-restart-current.json，D盘elastic-clock-restart-6f202a1，CPU23持
  reference-diagnostic.lock。共同legacy11600起步、新v4在12400分叉，400精确时钟/
  全HDF历史/五场及周期/质量已于23:53:06完成通过；不声称恢复legacy丢失补偿。
- 原冻结b072缺少的r4后继16987/会话33542已运行，elastic-mpi-r4-current.json，
  D盘elastic-mpi-r4-continuation-6f202a1；CPU9持elastic-mpi-restart.lock。
- 7542四核复核通过并完成显式交接：488.690→339.692秒，字段5.087e-12。
  507/631已计划退出，不得恢复；目标D盘womersley-a2-s48-l2-n200-vector-m400
  正在六周期续算。7639继续等alpha1中层自然结束，1180仍有意暂停。
- 15488完整nu0粗参考已完成；周期/质量/逐方程收敛通过，中部压力和Lamé门槛仍失败。
  新20277/会话39236，reference-nu0-s24-series-current.json，
  `queue-reference-nu0-s24.py`，控制目录reference-nu0-s24-series-6f202a1。
  当前不持锁等待r4与时钟工作。先持两原锁，在CPU23串行与CPU9/23双进程做20步
  全载荷预检（ramp0仅为执行筛查，不作周期证据），五场须通过2e-9/1e-8，双进程
  局部耗时须降低至少10%才选择；否则保留串行并释放CPU9锁。随后独立S24fineN400、
  coarseN400、fineN200原物理32周期，目标D盘reference-s24-l{1,0,1}-n{400,400,200}
  -meshnu0-6f202a1。只改新export网格nu，物理case逐字节相同；原nu.3仍运行。
- 证据队列20351/会话48477，clock-reference-capture-current.json，顺序保存原MPI失败、
  nu0参考、400交接及修复生产重放；不持数值锁，低优先级CPU17，不能重复启动。
- 后续需审查N200/N400每个实际solve段的预计耗时。合法CLI时限86400仍可能不足以
  覆盖长段；不得直接改运行冻结源或等待超时后误判为物理失败。必要时另冻自然周期
  分段入口并先做小算例真实验证，再有证据交接。所有原预算与资格门槛不变。

UTC23:11最新（替代旧N400等待器PID/目标目录）：

- 旧7843/7849在23:02:53计划取消，尚未数值工作或持主锁；原超限timeout172800在自审发现。
  新alpha2父15446/会话2429、alpha1父15457/会话23940，
  womersley-time400-a2-retry3-current.json / womersley-time400-a1-retry3-current.json，
  `queue-womersley-time400-bounded.py --alpha 2/1`。
  控制目录womersley-time400-a{alpha}-a7a177e-attempt3；D目标改为
  womersley-a{alpha}-s48-l2-n400-paired-a7a177e。均等待N200生产者，不持主锁。
  真实CLI8项验证通过，单段时限86400，N400先5周期2000步再resume至6周期2400步。
  预算/前提门槛不变；禁止重跑7822/7843/7849及其旧源码。
- 网格闭路诊断15252/会话90447已完成，reference-mesh-loop-current.json，
  work/reference-mesh-loop-a7a177e，34文件已归档；未改原参考或物理输入。
- 新完整nu0参考父15488/会话59371，CPU23，reference-mesh-nu0-current.json，
  `run-reference-mesh-nu0.py`，D盘reference-s12-l0-n400-meshnu0-a7a177e。
  持reference-diagnostic.lock，23:07:34启动原7bdb74c二进制12800步/从11200保存。
  与原S12/N400 case逐字节一致，只在新export中将mesh方程nu.3改0；固体nu.3保持。
  原export与原失败方案完整保留，完成后做全部方程收敛/五场周期/质量与原EON对照。
  这不是原方案通过，也不能代替细化预算；CPU23与22共享核心，不作性能比较。
- 生产MPI7370已完成二rank12800，23:04:02进入audit；未完成五场比较和二rank重启。
  主alpha2到393，原父631/1180仍由7542/7639有意暂缓，保持自然边界计划。

UTC22:53最新补充（原主计算和自然边界控制器继续）：

- L24父7713/会话43109，CPU19，elastic-length24-current.json，
  `run-pressure-length24.py`，D盘elastic-s24-l1-n200-L24-ramp16-c32。
  b072/MUMPS/chord，N200共6400步/预热5800/末三周期；22:26:14开始长算。
  持elastic-budget-analysis.lock至本研究审计结束，再释放并等L12，故7593须等待此锁。
  与CPU18共享物理核心，局部网格严格匹配已证明，三步预检已通过；没有完整动态长度结论。
- 细N400后继alpha2父7843/会话35263、alpha1父7849/会话73997；
  womersley-time400-a2-retry2-current.json和womersley-time400-a1-retry2-current.json。
  `queue-womersley-time400-reviewed.py --alpha 2/1`，当前均等待且不持主数值队列锁。
  只有N200新生产者或核验的旧fallback完成后才接原CPU0–7/10–17及原锁。
  D目标womersley-a{alpha}-s48-l2-n400-paired-fa9646d；同网格/二进制/选项六周期。
  原alpha2等待器7822已计划取消，补中层与控制量周期/质量前提后另冻新版本，禁止重启旧者。
  N400只是N200时间预算控制量；没有独立N400空间资格。
- 独立截面P2参考已完成，CPU23释放。状态womersley-polygon-reference-retry4-current.json，
  结果work/womersley-polygon-reference-fa9646d-attempt4；原7868、7917、7955三个失败保留。
  7968通过制造解/真残量/积分/观察到的细化标准，106文件归档完成；无三维资格声明。
- 生产MPI7370的r1完整12800及末1200相位对原默认配置通过，r2预热仍在运行。
  主alpha2当前386、alpha1中层569；7542/7639仍各持原Python631/1180有意暂停。
  不要手工恢复父调度、重启旧控制器或重复排队。

UTC22:18最新（取代下方空闲CPU/旧等待PID）：

- 生产MPI父7370/会话95515，CPU9，elastic-mpi-restart-current.json，
  `run-pressure-mpi-restart.py`，D盘elastic-mpi-s12-l0-n400-f0422d0-attempt2。
  同b072/MUMPS/lag=-2，1/2/4rank各从零12800步，保存11600端点及末三周期；
  二rank再从12400完整代重算末周期，比较400相位及全部HDF历史。五步预检通过，
  当前r1预热。CPU9与参考8共享物理核心，不作性能声明。首次缺生成器的导入失败保留。
- alpha2中层父7509/会话51902，CPU21，womersley-alpha2-middle-retry2-current.json，
  控制目录womersley-alpha2-middle-f0422d0-attempt2，D盘womersley-a2-s48-l1-n200-vector。
  新旧三步末态差1.717e-12通过2e-9，22:13:09进入六周期N200/200相位；
  候选162059c0、显式chord/block3、默认tau。CPU21与参考20共享物理核心。
  原7476因checkpoint_interval=0被输入校验拒绝，旧目录与状态保留，不得重跑旧启动器。
- 主流体旧等待6906已计划取消，finally恢复同一631，五个数值进程保持原身份。
  待执行probe也有非法零间隔，已在执行前另冻间隔3版本，未改活跃冻结源码。
  新父7542/会话30329，womersley-vector-boundary-retry2-current.json，
  `handoff-womersley-vector400-retry2.py`，控制目录womersley-vector-boundary-f0422d0。
  它再次仅持Python631暂停，MPI632/635..638继续自然至400；旧状态cancelled_before_probe。
  四物理核心字段/10%成本双门槛及显式续算计划不变，勿手工恢复631。
- alpha1新父7639/会话60480，alpha1-fine-vector-current.json，
  `handoff-alpha1-fine-vector.py`，控制目录alpha1-fine-vector-f0422d0。
  仅SIGSTOP外层父1180，子5422及当前MPI正常至中层1000步；不得误判失联或恢复1180。
  完成后分析中层，再在CPU10-17做alpha1细网格新旧三步预检；字段<2e-9且成本降低
  至少10%才取消旧父并另起D盘womersley-a1-s48-l2-n200-vector六周期。
  不通过/异常finally恢复同一旧父。原未来细目录仍空，未静默改定义。
- S24预算父7593/会话13613，elastic-s24-budgets-current.json，
  `analyze-elastic-s24-budgets.py`，等两程序coarseN400/fineN200/fineN400完整收据。
  只读计算空间/时间/31→32尾项/实际200→400采样及逐场10%比值，前提失败则资格失败。
  届时CPU19/elastic-budget-analysis.lock，当前仅等待，没有数值求解。

CPU18/20原S12细网格及S24后继队列、CPU22新S24续算、CPU8原S24参考继续。
新启动失败、完成预检及冻结控制器390文件已核验；运行快照不是长期完成证据。

UTC21:56最新：S24交接已完成。原6429/6802在21:47:32计划中断退出，其failed状态是
该执行交接收据，不能自动重跑。完整checkpoint400核验通过；原日志401/402另保留并重算。
同一CPU22两模式三步21.886264/14.335186秒，末态场差7.454e-20、归一化范数1.122e-17，
通过两场门槛及20%局部成本收益条件。父7140/会话27432持原geometry锁，21:48:12开始
`/mnt/d/EONSim-prod48-20261107/elastic-s24-l1-n400-ramp16-c32-mumps_chord-m400`，
数值7209，状态elastic-execution-s24-current.json；仍用冻结b072，仅显式MUMPS及lag=-2。
日志在work/elastic-execution-s24-400-054b64a/continued-warmup.log，目标11600后采样至12800。
参考父5055/数值6701保持原D盘路径；最终比较必须读取新EON与原参考的审计。
执行快照116文件已归档；alpha1后续3126、直接解103文件也完成，归档父7159已退出。
CPU9/21目前无数值作业。主流体父6906仍等待自然400步，只持原Python631暂停；
不要手工恢复或重复启动。其余CPU18/20研究及后继预算队列保持不变。

UTC21:42最新：CPU21有界弹性直接解筛查已完成并释放，不占后续计算资源。S12/level1/N200
同一1400步接受态后三步，标准/MUMPS/串行SuperLU/MUMPS+chord末态场差均通过；
总17.956/11.194/60.128/6.633秒，最大差3.47e-17、五场归一化质量范数差最大1.21e-14。
CPU21与参考CPU20共享物理核心，属于局部选项筛查，不能外推通用性能。
为S24单核长计算准备同态复核：父7140/会话27432，elastic-execution-s24-current.json，
脚本handoff-elastic-s24-400.py。现仅等待原6429/6802在CPU22发布完整第400步，尚未发信号。
届时核验全部耦合/时间历史后计划SIGINT数值子，原父自然记录计划中断并释放geometry锁；
新父取得同一锁后，使用原b072做标准/MUMPS+chord三步复核。两场门槛及20%局部成本收益
均满足才派生D盘elastic-s24-l1-n400-ramp16-c32-mumps_chord-m400，否则派生standard-m400。
两种分支均从原完整400步续至12800并保存三周期。参考5055继续原D盘目录；以后交叉比较
须用新EON目标与原参考审计，不把原EON计划中断状态误作数值失败或重跑旧控制器。

N400归档8289文件/16包179991408字节、vector967文件/7包104651260字节已完成核验。
S24短预检首次归档因参考硬链接被普通成员断言拒绝；失败原包/源码完整保留在failed目录。
修正归档dereference后79文件核验，未重算PDE。后续归档重试父7159/会话94458，状态
followup-capture-retry-current.json，CPU9，继续alpha1已完成两项及直接解短探测；旧6901已失败退出。
两份新交接控制器独立：主流体父6906仍仅持有原调度631的暂停；S24父7140当前未暂停父进程。

UTC21:14最新交接：单物理核心block3三步完成并通过，标准733.265秒/候选539.742秒，
最大场差5.08531e-12（门槛2e-9），局部成本下降26.392%，默认不变。
新交接控制器PID6906/会话59413，状态womersley-vector-boundary-current.json，
脚本handoff-womersley-vector400.py。它仅SIGSTOP主研究的Python调度子631，主父507仍持
mpi-queue.lock，MPI632和数值635..638在CPU0-7正常继续至预设400步，不能误判为失联。
自然完成后核验四rank完整历史，再在原四物理核心做同态旧/新二进制三步复核。
场差与至少10%成本收益同时满足才显式派生D盘womersley-a2-s48-l2-n200-vector-m400，
并计算至第六周期，保存5→6尾项；否则恢复同一原调度子。冻结源码在
work/womersley-vector-boundary-054b64a/source。原结果/尝试完整保留；不得重复启动或手动
恢复631与探测重叠。任何失败先读状态及original-resume.json，残留探测进程需清理后再恢复。

S24/level1/N400 EON已21:02:01在CPU22接续，参考CPU8继续。alpha1原队列仍未改数值选项；
其未来level2/N200空输出目录已显式映射到D盘，收据alpha1-fine-storage-054b64a.json，
没有移动已有原始场或修改冻结控制器。N400时间分析已完成，参考网格末周期最大1.91055e-5仍失败。
归档CPU9：N400 PID6801/会话94134；后续父6901/会话29620等待前者结束，再顺序处理
vector/短预检/alpha1已完成数据，状态followup-capture-current.json。归档未完成前不提交半成品。
新增研究选项的6项实际旧研究只读/拒绝检查与26项选测检查通过，C++通过证据复用，不重复数值测试。

UTC21:00最新安排：粗S12/N400两侧及审计已完成；EON周期通过，参考仍失败，中部压力
幅值差2.58266%仍未过2%。CPU8已20:53:07接续D盘S24/level1/N400参考长算，父5055、
数值进程6701，原锁和状态不变。N200→N400只读时间/尾项/200→400实际采样分析在CPU9，
状态elastic-time400-fields-current.json（会话1235），不改变原始场或参考收敛标准。
S24/level1/N400 EON父6429仍在geometry锁后等待；细网格可选PC对照已进入block3模式，
当前标准三步已完成，报告仍未完成。不能在仅有单组耗时或未核验场差时采用。

新增S24预算配对队列已冻结输入到D盘：elastic-s24-l0-n400-ramp16-c32与
elastic-s24-l1-n200-ramp16-c32，分别只改变同多边形空间层级和细网格时间步；
各保存最后三完整周期及真实前态。EON父6658/子6659/会话16789在CPU18的
elastic-ramp-queue.lock等待原S12空间研究；参考父6672/子6673/会话35782在CPU20的
elastic-space-reference.lock等待。状态elastic-budget-{eonsim,svfsi}-queue-current.json；
子状态elastic-budget-s24-l0-n400-{eonsim,svfsi}-current.json，之后依次进入s24-l1-n200。
准备与队列脚本run-elastic-budget-companion.py/queue-elastic-budget-companions.py已冻结；
不要重跑prepare或重复启动。原始输出在/mnt/d/EONSim-prod48-20261107，不能为归档复制回C盘。

UTC20:41最新安排：旧alpha1临时窗口已20:22:49正常恢复，原父1180继续执行，现为level1/N200。
GAMG粗化三组场差通过，384.06/375.52/386.77秒，未达到采用收益，不改变原研究。
候选S24/level1/N400/ramp16五步已通过，EON34.98秒、参考31.63秒（仅短程局部观察）。
为避免C盘不足，长期输入/原始输出使用已创建的D盘目录
`/mnt/d/EONSim-prod48-20261107/elastic-s24-l1-n400-ramp16-c32`；控制状态和锁仍在原work。
总12800步，保存11600..12800三个完整周期及真实前态。参考PID5055/会话8395在CPU8原
elastic-serial-queue.lock等待粗N400参考完成；状态elastic-geometry-svfsi-current.json。
EON PID6429/会话40636在CPU22的elastic-geometry-long.lock等待短对照结束，状态
elastic-geometry-eonsim-current.json。不要重复启动，两者冻结b072及准备时Python源码。

可选独立流体`-schur_velocity_block3`在054b64a后实现；元数据/空owner/集体拒绝/恢复、
真实三步1/2/4rank与LU场差及旧Schur/失败回归：Debug6项通过；Release5项通过，旧Schur
在一物理核心默认MPI空等下100秒超时。只重试该失败项，启用mpi_yield_when_idle后16.70秒
通过原时限；源码逐文件完全相同，combined-release-evidence.json证明复用。初次清单格式
错误和超时证据保留。新Release二进制sha162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c。
CPU22/23现为四rank单物理核心的有界细网格候选对照（会话7389），报告
schur-vector-probe-fine-054b64a/report.json，持上述geometry锁与mpi-option-probe.lock。
源200步历史及旧b072场基准已核验，单项1200秒上限；没有采用新策略或更改运行中研究。
后续先完成/保存该对照与实际成本证据，再决定是否保留或显式派生研究。C++改动尚未本地提交。

UTC20:20补充：时间/网格回放4298、静态Lamé108、全环夹持L12/L24诊断109文件均已核验。
十组夹持静态结果仅作为下一网格选择依据；S24/level1/N400/ramp16五步两程序预检
在CPU22运行，PID4948/会话47970，elastic-geometry-probe.lock，
状态elastic-geometry-probe-current.json，目录elastic-s24-l1-n400-probe-6093f01。
尚未启动该网格长期研究。CPU0-7、8、10-17、18、20安排保持，临时窗口仍按下方收据恢复。

最新调度补充：alpha1-option-window.py（PID3654/会话82204）仅SIGSTOP调度父进程1180，
其当前N100求解子进程继续正常完成500步；完整收据确认且数值进程退出后，在CPU10-17
执行有界GAMG粗化选项三步对照，报告gamg-probe-fine-6093f01/report.json。
状态alpha1-option-window-current.json；结束/异常finally对同一已核验父进程SIGCONT。
这是短时计算资源调度，其他研究继续；不要重启alpha1或把父进程T状态误判为失联。
新的网格回放reference-mesh-replay-6093f01已完成：N100/N200实际场重现最大归一化节点差
2.70e-15/4.79e-15；闭合边界仍有1.946e-5/1.932e-5增量网格漂移，固定几何对照约1e-16。
该诊断没有重做流固耦合、修改参考二进制或改变门槛。CPU22现无数值作业。

UTC19:48最新：CPU8的N200两边已完成；EON周期通过，参考mesh周期最大1.93514e-5仍失败。
中部压力幅值差2.48284%未过2%，相位.51230度通过；所有参考方程步相对收敛。
CPU8现转入elastic-s12-l0-n400-ramp16-c32，PID3524/会话72742，状态elastic-n400-current.json，
原elastic-serial-queue.lock。同设置N400五步实际参考预检通过，11200预热后保存至12800。
两组MPI和CPU18/20的空间研究保持运行。CPU22的九组静态Lamé诊断已完成（非耦合资格）；
该CPU现在只读分析N100/N200完整场、尾项和采样，状态elastic-time-fields-current.json。
原N200控制器不得重启；新的N400是明确的独立研究，不替代已有失败结论。

UTC19:36最新资源：新增的两个单进程空间研究已实际启动，替代下方“尚未启动”状态。
共同输入elastic-s12-l1-n200-ramp16-c32，EON PID3212/会话3286，CPU18，elastic-ramp-queue.lock，
状态elastic-space-eonsim-current.json；参考PID3224/会话9823，CPU20，elastic-space-reference.lock，
状态elastic-space-svfsi-current.json。不与CPU0-7、8、10-17重叠，启动检查内存及C盘空间。
EON5600步预热后保存至6400，参考保存5600..6400；两侧源码/输入已冻结。短程预检
123文件和PC选项94文件核验完成。CPU8的EON N200周期/质量通过；同项参考仍在运行。
先查全部五份状态和实际进程，不重复提交。更新既有48h续接提示，不新增重复自动任务。

UTC19:30资源更新：pc-probe-fine-c49c69c已结束（会话43255关闭），CPU18-23不再有MPI探测。
S12/level1/N200五步两求解器预检也完成，状态elastic-space-probe-current.json，CPU18已释放。
CPU20在elastic-space-reference.lock下运行reference-space-startup-c49c69c的ramp16参考五步检查，
会话87181；尚未启动细化网格长研究。主CPU0-7、alpha1 CPU10-17和N200 CPU8保持运行。
6846份启动数据归档核验完成；不得将归档中的N200控制器副本当作已完成的N200结果。

UTC19:15最新操作点：CPU8已转入elastic-s12-l0-n200-ramp16-c32，PID2808/会话71064，
状态elastic-n200-current.json；6400步，5600预热后保存四周期。显式减半dt、默认tau，
参考线性绝对容差收紧到1e-26，非线性1e-10不变；同N200五步实际预检通过。不要重复启动。
CPU18-23为有界PC选项探测，持elastic-ramp-queue.lock和mpi-option-probe.lock，
会话43255，报告pc-probe-fine-c49c69c/report.json；已实际四rank验证亲和性不与其他求解重叠。
原主CPU0-7和alpha1 CPU10-17保持运行。CPU9只做已完成数据的只读审计，已完成。

新的参考日志审计通过13200步全部26400方程步；ramp2/c12全2400终行达到上限，其中1215
未达相对标准，明确不合格。初次1e-22短探测在ramp16首mesh步仍失败，1e-26的N100/N200
五步均通过；原失败保留。导出6/日志4/场审计7/CI选测26及制造绑定4项通过，181文件核验。
日志绑定输入清单后才算参考收敛证据，缺日志不得进入比较资格。

ramp16/c32两边均完成且新参考全程收敛。EON全场周期通过，与原132周期同求解器场差
最大1.891e-6<事前1e-5，允许EON后续采用该预热。参考内部网格周期差仍1.95e-5>1e-5，
不同启动的mesh场差.002170>1e-5，故该缩短预热结论不外推参考侧。中部压力4.90%/2.66度
差仍未过；N200正在独立研究。旧ramp16控制器在3200步完成后的只读审计阶段计划交接，
终止控制器也结束了审计子进程；只重做无报告的只读审计，未重算EON或运行已知坏参考设置。
所有历史状态保留，按本段最新状态行动。没有push/PR，完整PROD-02尚未通过。

UTC18:48补充优先：ramp2/c12两边均已输出并审计，但参考日志有1999条迭代上限行。
固定PIC.f会把maxItr当作ok，故这些场不能作为收敛资格；正几何/输出存在不够。
正核对更严格线性绝对容差的最小短算例并增加日志收敛审计，不放宽非线性1e-10。
ramp16队列已于18:46:45转为EON预热，PID1800；撤回“等待任务”的尝试因状态核对发现
已经启动而未执行任何信号/文件修改。下一步仅对其参考阶段做有证据的交接，保留已算EON。
132周期原无ramp参考当前未见迭代上限行，仍须完整日志检查后才可认定通过。

UTC18:40最新操作点：主alpha2与alpha1队列继续。alpha1首个level0/N100六周期已完成，
周期门槛通过，但u/p/Q幅值2.4358%/1.7679%/3.1368%均未过1%；2071文件核验归档。
独立CPU8的EONSim132周期完成；最后两周期全场差最大3.73e-6<1e-5、运动学和阶段质量通过。
参考程序初次启动因OpenMPI5的sm选项遗留到系统OpenMPI4而在MPI_Init失败，无数值输出。
已保留失败与完整EON结果，单独复制不变输入到reference-attempt2，清除运行时选项后重试。
控制器PID1540/会话83316；仍看elastic-window-current.json，不重复整个长预热。

General压力输入的两个真实100步精确检查、导出5项、审计7项、制造启动比较6项通过。
288文件核验，未改参考源码或物理门槛。CPU18经实际不重叠检查后用于有界启动研究，
锁elastic-ramp-queue.lock。ramp2/c12 EON周期差仍3.69e-3，未过；其参考初始化同样失败，
正在reference-attempt2单独重试，PID1707/会话46033，状态elastic-ramp-current.json。
第一次恢复器曾在原控制器释放锁、外层异常处理尚未更新状态的间隙误判；保存失败，
改为等待旧进程退出并核对MPI_Init日志及无结果目录后重试，未重算EON。
下一项ramp16/c32已在同CPU18锁上等待，PID1800/会话65764，状态elastic-ramp16-current.json。
只改变明确记录的启动函数；候选必须通过周期检查并与长预热同求解器场对照后才可采用。
以上四个实际CPU集合及全部状态文件均先核对再行动。没有push/PR，原截止及验收条件不变。

UTC18:17资源/队列补充：无数值求解的实际四rank亲和性预检已证明CPU10-17与主CPU0-7、
弹性CPU8均不重叠。在该集合启动独立alpha1队列，锁womersley-alpha1-queue.lock，
状态work/womersley-alpha1-current.json，控制器PID1180（会话73417），输出womersley-alpha1-0b9e980。
顺序为level0/N100六周期、level1/N100五周期、level0/N200五周期、level1/N200五周期、
level2/N200六周期/200相位；每项结束分析，随后做同N200空间差和5→6尾项等比较。
均为四rank、冻结b072、标准Schur，无chord参数外推。每项新研究前检查>=5GiB空余内存、
>=8GiB主机C盘空间及其他求解进程亲和性；驱动/分析源码已冻结。预检不是性能结论。
现有三份状态先读后行动，不再为这些研究启动重复控制器。alpha1实际精度仍待计算。

**当前操作点UTC18:04优先于下方历史**：选项探测与粗网格固定时间尺度研究均已完成。
主控制器PID507（会话81684）持有mpi-queue.lock，状态work/womersley-continuation-2eabb47.json，
运行womersley-a2-s48-l2-n200-chord-m200，先400再1000步。lag=-2细网格三步差1.03e-14，
本次耗时降低5.42%，显式接受态派生/200相位已发生；不要重启旧研究或另开主MPI队列。

资源安排有实测变更：24逻辑核心/32GiB，主rank亲和性0-1/2-3/4-5/6-7、约28GiB空余。
另允许一个**单进程**弹性作业固定CPU8、独立elastic-serial-queue.lock，不作并发性能结论。
控制器PID994（会话23544）状态work/elastic-window-current.json，输出elastic-s12-l0-n100-c132-window。
它从600步完整接受态续至12800预热，保存真实12800终点和12801..13200，审计后从零运行
同定义132周期的固定svFSI。分析/导出源码已冻结，启动前检查CPU不重叠及可用内存>=2GiB。
先检查这两份状态/进程，不重复启动。heartbeat已同步资源安排；截止时间及PR门槛未变。

严格窗口读取11项制造检查、导出4项通过，551文件核验；首次弹性3423文件、选项139文件、
受控时间尺度1574文件均已回读核验。旧制造检查的JSON键类型错误和旧坐标审计失败均保留。
真实长暂态、细网格最终场、alpha1与剩余误差预算仍待完成，无push/PR。

当前操作点（UTC17:36，优先于下方历史状态）：第200步交接已完成。
`scheduled-handoff-200.json`为checkpoint_handoff_complete；2189验收控制器结束，
最终failed仅指旧SV读取器坐标核对失败。Debug/Release时间尺度与stage-pressure已通过，
两边600步物理求解完成；修复精确Float32映射后`elastic-reaudit-float32-865b101`
两边审计与比较完成，均未周期稳定，尚不具备物理比较验收资格。原始失败完整保留。
当前唯一数值作业是`option-probe-fine-lag2-865b101`（标准与lag=-2各3步），
探测辅助程序自己持有mpi-queue.lock。先前COO细网格没有端到端收益且更占内存，不采用。
旧lag=-1的两份粗网格失败保留；PETSc命令行不接受该值，runner已改为受支持的-2。
细网格lag=-2若通过且值得采用，则由fork助手在新同级目录从200步派生、--phases200，
显式--chord --resume；否则使用standard派生保存更密相位。新旧研究都不能重复启动。
弹性下一步须消除启动暂态并完成各自时间/空间/采样/尾项预算；不放宽周期门槛。

用户明确要求连续推进48小时，全部完成再推送PR。窗口：北京时间2026-11-07 20:59:10至
2026-11-09 20:59:10。基线main `c218c18c7b11396ed177d91c631a278bdf0cb2a9` 已合并PR #38，
包含4113ab8的场审计/种子网格补充；下方PR未合并与旧在研分支为历史。
工作分支 `codex/fsi-production-48h-20261107`；期间仅本地提交、保存可恢复状态，
本轮全部验收/自审/证据/知识草稿齐备后才push并创建PR，不能用窗口到期代替完成。
本对话heartbeat `eonsim-new-48` 每30分钟续接至窗口结束，不启动重复MPI队列。

按依赖连续完成PROD-02：稳态刚性场/端面与局部质量资格 → Womersley及时间/空间/周期预算 →
弹性管与固定版本svFSI对照 → 完整审查；有剩余时间再按生产路线推进下一项边界能力。
不为等待而空转，不把单项通过或48小时到期等同整个生产项目完成。

首先领取稳态资格子项，沿用R=1/L=2/rho=mu=1/Delta p=.02及原求解停止准则。
事前门槛：最细状态Q误差<1%、速度相对L2<1%、压强RMS/Delta p<1%、端面压降误差<2%、
div RMS/(Umean/R)<1%；全局通量<1e-10、1/2/4rank与参考直接解场差<2e-9。
几何误差与场加密分别记录，原始失败必须保留；不修改稳定化公式或容差换取通过。
先核对现有Schur/GAMG与LU一致性，再评估可控内存下的细网格。其他子项在计算前固定自己的门槛。

稳态进展：96/48/96四rank六项场门槛通过，447073节点；小网格MPI/LU对照已通过。
证据78文件核验见rigid-tube-schur-2026-11-07；不外推最大网格MPI/LU验证。

Womersley子项预设（门槛在运行前确定）：R=1、L=2、rho=mu=1，压力差 .02*sin(2*pi*t/T)，
alpha=1、2（T=2*pi/alpha^2），无滑移侧壁、端面切向零速度/轴向压力牵引。
先以滑移侧壁的均匀加速流核对BE/BDF2/alpha的精确离散递推、1/2/4rank、保存频率和续算。
定量研究使用BDF2；每种网格至少三周期，最后两周期同相位场差<1e-6（速度/压力分别按解析周期RMS归一化），
追加周期确认尾项。最细状态周期速度L2误差<1%、压力RMS/压差幅值<1%、流量谐波幅值误差<1%、
相位差<1度；全局通量<1e-10。固定多边形场加密与几何误差分开；时间步减半、尾项和相位采样加密
对各场指标的影响分别<末档空间场差的10%。默认随dt变化的tau必须单独辨明，不把固定tau结果当默认资格。

实际进展：alpha2粗/level1在N100达到周期稳定，但速度误差2.3667%/1.86191%未通过。
粗N100→N200的时间/参数变化约为首档空间场差的54–56%，不满足预算；粗网格第六周期尾项约1e-14。
唯一运行作业womersley-a2-s48-l2-n200，四rank冻结b072，warmup400/总1000步；不得重复提交。
UTC16:16安排一次**接受态交接**：watcher读取并验证第200步完整四rank checkpoint/BDF2历史后，
向原mpiexec发送SIGINT，保留未完成attempt和原日志；这不是数值不收敛。状态文件
`work/scheduled-handoff-200.json`，watcher PID1431（会话56874）；不启动第二个watcher。
随后已有2189a8c验收控制器获取同一锁，先做短验收/首轮耦合。再针对同一完整接受态
检查既有COO/步内固定Jacobian选项，只有真实字段/残差一致后才考虑采用；最后显式续算细网格。
在交接与验收期间不要自动启动原研究的重复resume。当前源码和正在运行的数学问题未改变。
已有三组周期场的轴向定位与六组网格的解析插值筛选已归档；只用于下一轮诊断设计。
49137节点候选的alpha2插值误差约.2744%，不是PDE误差或运行时间预测；尚未采用替代网格。
选项探测辅助脚本已准备，仍未执行。先检查队列空闲，再从明确的完整checkpoint做短探测，
保留原容差和失败记录，不能默默改变旧研究定义或把3步一致性扩展成长期精度证明。
源码cfa5d3c已提供--fluid-coo/--chord（后者仅Schur），非默认选项进入definition。
旧研究默认空续算和改变选项拒绝共4项纯元数据检查通过；没有数值探测或真实fork。
准备的fork-womersley-execution.py要求完整匹配且通过的探测收据，再复制明确的接受态到
新的同级研究目录；原研究不改。probe辅助程序自己持有队列锁，不能再套run-python.sh锁。
fork仅支持不晚于warmup终点的接受态，避免遗漏分析器所需的周期历史。拟对细网格显式
使用--phases200保存全部N200步，以实际数据检查100→200采样；尚未派生。已完成的
50→100相位重建诊断与正弦/线性参考只验证分析链，不替代该预算。
可选fluid.stabilization_time_scale只用于分离tau时间参数的影响，默认算法未改；新代码数值验收待队列。
实际旧场系数重建已归档：粗/level1 N100时间平方项占比.66249/.12466，同场减半dt的
平均tau比.58293/.85711。仍需默认N100→固定时间尺度N200→默认N200的真实场对照；
不能将系数占比当作误差占比。两个N100历史共200次前一步独立对照差0，N200该项未做。
管端压力迹与重建法向应力诊断已补入现有Womersley证据；后续细化结果保留同类诊断，
不混称压力值和自然牵引，也不将有限网格强应力偏差自动判为实现错误。
接下来完成stage-pressure参考输入实际核验、时间尺度Debug/Release最小检查，再继续误差预算及弹性对照。
源码检查点d280e7f仅本地提交；新诊断已编译但未做数值验收。等待队列状态在
work目录next-acceptance-current.json，先检查该进程，禁止重复提交。若当前大网格因
原21600秒单次时限退出，保留失败并在队列释放后用同一冻结二进制、同定义、
`--resume --timeout 86400`接续完整checkpoint；不得把超时归因为物理不收敛。
静态审查发现新压力管固体区域标签丢失，b9075f0已修正，Python针对性3+3通过。
原未运行输入保留；实际待算例改用elastic-s12-l0-region20。等待控制器已在执行前撤回并
重新排队，源码基准b9075f0，输出工作目录acceptance-b9075f0；仍不得重复提交。

后续静态审查：svFSI两方程默认同名Displacement，导出已改为两个显式Alias；新增
[完整场审计](PRESSURE_TUBE_FIELD_AUDIT.md)。Python审计5项、导出3项、选测26项通过，
实际耦合读取待验。旧b907等待控制器在执行前撤回（取消记录保留），将使用新源码重新排队并
在两次耦合运行后实际执行审计。当前冻结Womersley作业继续，不能重复启动。
替代控制器已在UTC15:47:37排队，源码2189a8c9589add9376c060ef4e4c2e871fdb0c60，
输出acceptance-2189a8c，状态仍在next-acceptance-current.json；前两份取消记录不是数值失败。
独立制造场的VTK/双域映射及48快照完整审计通过，185文件核验归档；这不构成真实耦合结果。
已准备build/prod48-20261107下的compare-pressure-audits.py和compare-pressure-fields.py，
独立5+3项分析检查通过、28文件归档；控制器完成后用它们读取真实审计/场。
参考内部ALE为增量伪弹性，EONSim为参考Laplace；记录此差异，不能把跨程序内部
网格位移一致作为物理等价假设。原响应、质量、周期及误差预算门槛不变。

弹性子项预设（尚未执行耦合求解）：选择可与固定svFSI源码精确对应的参考构形小应变线弹性lElas，
E=1000、nu=.3、两域rho=1、mu=1、R=1、外半径1.2、L=12；两流体端面均施加
`.02+.01*sin(t)`（T=2*pi，无启动ramp），固体两端与ALE端面全分量固定，外壁零牵引。
两程序从零场开始，各自generalized-alpha rho_infinity=.5；不得假设其离散时间/压力表示相同，
先用零速度、空间均匀的时变压力检查参考程序的输入与输出时刻约定。
同周期场差<1e-5后比较：中部壁平均径向位移/面积谐波幅值差<5%、压力幅值差<2%/相位差<1度、
两端通量幅值差<5%/相位差<2度；各程序时间/尾项/采样影响<末档空间场差10%。
圆管长筒平面应变Lamé均值响应只用于独立近似对照（有限夹持端效应需检查），目标中部均值差<2%。
几何与场加密分开；EONSim正几何、界面相容、质量预算和MPI/续算检查沿用既有门槛。
Neo-Hookean同名但公式不同，不能以同参数替代本材料匹配；完整非线性血管资格不由本子项推出。

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
