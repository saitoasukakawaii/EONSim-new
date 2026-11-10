# 已归档检查点的临时容量回收

基线d610fa4。30651完成0，N1600 dense-004在47330步保留原52782；原控制器34110未终止，检查点47168。78925完成0，命令 `build/analysis-venv/bin/python build/recompute-20261109/compress-logged-fine-n1600-fourth-segment.py --work build/recompute-20261109/elastic-s24-l1-n1600 --through 47329`，扩展执行权限；644文件透明压缩回收581193728B，事后SHA全通过。

另对已完成4800步的Womersley α2精细N800，回收完整归档中已有的3201..4799内部检查点HDF（保留4000及所有周期端点），共1598文件5183963136分配字节。命令 `build/analysis-venv/bin/python build/recompute-20261109/evict-alpha2-n800-late-capacity.py`，24282完成0。删除前重新检查原归档及清单SHA，逐文件与原清单一致，再从完整归档重新解码全部1598成员并核对SHA，发布恢复收据后才回收副本；不减少原始数据或改变时间相位。

这些文件仍是未来N800/N1600预算的必需输入：执行预算/重放前必须先运行 `python3 build/recompute-20261109/restore-womersley-materialization.py build/recompute-20261109/archives/alpha2-s96-l1-n800-late-capacity-materialization.json`。若其他历史收据中的文件也被消费者使用，也必须恢复。当前只暂时回收展开副本，不能沿用旧“第5/6周期仍展开”描述。预算尚未运行，原失败未改；存储调度后必须完成原预算。

原归档首/末所选检查点3201、4799已实际恢复到独立probe目录并重新SHA核对，83008完成0。32557统一279归档清单重新通过，所有新增缺失文件恰好对应新收据。证据gzip读回逐字节一致。无最终物理资格，未push/PR。

更新（9418026之后）：空间超过26GiB，核对原52782同命令/T状态后恢复，容量保留192.297742秒计入墙钟。新监测48131实际live，原34110及参考38893均live；命令 `build/analysis-venv/bin/python build/recompute-20261109/monitor-fine-n1600-capacity-fourth.py`。其余保留计算未恢复。
