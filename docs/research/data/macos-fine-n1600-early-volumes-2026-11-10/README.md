# 已完成N1600早期体场的可恢复归档

基线0d4f275；物理审计与完整raw capture均已完成，当前独立预算读取范围经原kernel/比较器逐项核对。

## 2026-11-10：N1600早期体场归档并恢复长管原进程

[证据](../research/data/macos-fine-n1600-early-volumes-2026-11-10/README.md)：85035归档退出0，69337独立重新解码56块3258成员SHA通过，2成员真实恢复通过；净回收1269433837B。仅选择fine步<=48000；绑定当前运行预算wrapper/kernel/比较源码SHA，原预算只读取fine48001..51200（sampling端点49600），该窗口全部保留。物理审计及全raw capture已终态；未来早期场消费者/完整物理重放仍须恢复。catalog v12已准备但**未运行/未采用**，需预算暂时展开副本清理完成后统一复核；当前v11不覆盖新增56块。

43413在free=25046220800B>23GiB且原PID73679命令/停止状态一致后恢复，保留时长13116.359909秒；已看到24460完整接受步。原20GiB硬下限、22GiB监测保护、23GiB恢复条件未变。新增tail压缩仅处理24454以后输出，避免误要求已归档的旧边界前缀；监测失败会保留原进程。65569完整预算仍live，未修改运行源码；无push/PR。

实际执行archive-fine-n1600-volumes-through48000.py、verify-fine-n1600-volumes-through48000.py、restore-womersley-materialization.py（2成员probe）和resume-length24-fourth.py，均位于build/recompute-20261109。归档逐块完整解码后才回收原文件；独立复核再次完整解码。原manifest位于docs/research/data/macos-elastic-fine-n1600-2026-11-10/raw-manifest.json。完整预算未结束，不能写作通过；后续完整catalog必须使用v12并实际验证成功后才采用。
