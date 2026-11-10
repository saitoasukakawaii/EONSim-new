# Womersley N1600第四周期可恢复归档

基线4459f23，未修改冻结求解器/控制器。

## 2026-11-10：Womersley N1600第四周期内部状态归档

[证据](../research/data/macos-womersley-n1600-cycle4-archive-2026-11-10/README.md)：84597完成0，62994独立完整解码39块1599成员SHA通过，2成员真实恢复通过；净回收1192606842B。75078统一481归档/14完整清单/8不可变子集通过并采用v11。四个周期端点、当前检查点和第5/6周期保留，capture已加入cycle4归档核验。**任何读取cycle4内部HDF的分析/全轨迹重放必须先恢复对应收据；不得省略这些相位或放宽门槛。** 当前约22.23GiB，未达到此前23GiB恢复条件；保留原暂停进程，94137完整FSI审计继续。尚无新物理验收，无push/PR。

实际依次运行prepare-womersley-n1600-cycle4-archive.py、archive-womersley-n1600-cycle4-chunks.py、verify-womersley-n1600-cycle4-archives.py与review-current-archive-catalog-v11.py（均位于build/recompute-20261109）。预检绑定完整attempt-004的4801..6400成功日志，当前检查点晚于6400，选择4801..6399原始HDF并保存每个manifest和字节SHA。每块先解码全验再回收原文件；随后独立全解码再次校验。恢复使用restore-womersley-materialization.py RECEIPT。最终capture可直接验证归档而无需展开；需要这些内部帧的数值消费者仍必须展开后读取。
