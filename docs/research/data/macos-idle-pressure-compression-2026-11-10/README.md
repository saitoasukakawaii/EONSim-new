# 静态参考压力输入透明压缩

基线8b31238。70225监测在dense-011第49097步容量保留原65916并正常退出；当前检查点48960，34110仍live。94435完成0，仅选择dense-011至49096，不再枚举已归档的early边界；544文件事后SHA全通过，回收457019392B，求解器/控制器未改。

1540完成0，命令 `build/analysis-venv/bin/python build/recompute-20261109/compress-idle-reference-pressure-inputs.py`，扩展执行权限。预检枚举100个静态pressure输入，明确排除当前运行的reference-kinematic-elastic-s24-l1-n800-nu0；断言无实际进程命令引用被选工作根。每文件检查源大小/mtime稳定、源SHA与候选SHA完全一致后，仅有分配空间收益才替换。100文件实际替换，回收1509425152B；全部替换文件事后重读SHA通过。无收益文件保留原件，没有删除输入、改路径、改输入逻辑SHA或改变恢复收据。此结论只验证字节保持，不重新证明诊断数值结果。

第十一段命令 `build/analysis-venv/bin/python build/recompute-20261109/compress-logged-fine-n1600-eleventh-segment.py --work build/recompute-20261109/elastic-s24-l1-n1600 --through 49096`，扩展执行权限。所有压缩证据保留并gzip读回一致。下一步按实际余量核对原65916后恢复并用新监测收据；旧70225已终态。参考继续，尚无新物理验收，未push/PR。复用已有方法，无新文章。

更新（cb542fb之后）：空间超过23GiB，核对原65916完整命令/PGID/T状态后恢复，保留193.779895秒计入墙钟；同执行链进入新监测88526，实际live。原34110及参考38893也确认live，其余保留任务未恢复。监测入口monitor-fine-n1600-capacity-seventh.py沿用同一身份guard和21.25GiB门槛。
