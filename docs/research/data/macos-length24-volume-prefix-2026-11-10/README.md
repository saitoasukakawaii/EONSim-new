# 长管已接受体场前缀的可恢复归档

基线8a8f305。

## 2026-11-10：长管体场前缀归档及第五次容量监测

[证据](../research/data/macos-length24-volume-prefix-2026-11-10/README.md)：80755清单2826成员完成，25165归档退出0，73967独立全解码98块SHA通过；实际长管23201两域经生产恢复reader与先展开读取完全一致、创建副本清理通过。净回收2253260272B。39869在原PID73679身份/停止状态核实且free=26024480768B>23GiB时恢复，保留614.215359秒，新的tail压缩只处理24585以后字段；原20/22/23GiB条件保持。

后续完整审计使用audit-pressure-streaming.py和volume-through24584-chunks收据，前一端点及末2400相位不变；capture新增独立归档核验并要求实际恢复2770所需成员。冻结旧控制器的最终索引收集要求体场已展开，预计会因归档路径报错；保留原记录，数值全部完成后使用finalize-length24-archived-series.py经完整归档核验重建原PVD并写completion-postflight。当前未完成前置拒绝实际通过，最终收尾/完整审计路径尚未执行，不能提前认定成功。catalog v13准备但未运行/未采用，需预算恢复副本清理后验证；65569预算继续，无push/PR。

实际依次运行prepare-length24-volume-prefix.py、archive-length24-volume-prefix.py、verify-length24-volume-prefix.py、test-length24-restored-reader.py、resume-length24-fifth.py（均在build/recompute-20261109）。前缀选择early29帧及dense23201..24584的双域体场，绑定停止进程身份、连续接受日志与原冻结output-before-log证明。每块先解码全校验再回收原文件；独立复核再完整解码。后续读取仍需原路径恢复，不能把归档视为省略相位的许可。

未来完成后顺序：核实10563与数值进程终态及两阶段receipt；运行finalize-length24-archived-series.py --work build/recompute-20261109/elastic-s24-l1-n800-length24；运行audit-pressure-streaming.py --case .../case.json --work ... --first-step 23201 --output build/recompute-20261109/elastic-s24-l1-n800-length24-audit.json --receipts build/recompute-20261109/archives/elastic-s24-l1-n800-length24-volume-through24584-chunks；完整审计结束后运行capture-elastic-length24-n800.py与长度对照。所有这些最终路径尚未执行；原控制器失败须原样保留。
