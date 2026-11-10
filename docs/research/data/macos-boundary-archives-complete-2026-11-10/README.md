# 两组边界归档终态验证

基线0e5f867。74185、18670均退出0。粗N1600归档18块9658成员，净回收666281116B；长管前缀65块2564成员，净回收1784970580B。每批编码后完整解码/SHA核对，发布收据后删除展开副本；终态40401重新核对全部83归档SHA/大小和所列缺失路径。净收益已逐批释放，不能再加到当前空闲空间。

长管独立校验命令 `build/analysis-venv/bin/python build/recompute-20261109/verify-length-boundary-prefix.py`，9543退出0，再次完整解码2564成员。两组各2个流/固边界成员通过现有restore-womersley-materialization.py实际恢复到独立probe目录并重读SHA，证据随附。完整receipt及清单gzip逐字节读回通过。

统一清单命令 `build/analysis-venv/bin/python build/recompute-20261109/review-current-archive-catalog-v3.py`，64610退出0：13个完整研究与2个未完成研究不可变子集，共279归档；缺失文件与恢复收据精确对应。该检查没有重新解码其余历史归档，复用原证据。已将完全相同的验证源码采用到原入口review-current-archive-catalog.py，避免以后沿用旧193计数。长管最终capture使用新的前缀完整解码验证，但最终数值capture尚未运行，不能声明最终物理通过。

细N1600仍在46787容量保留，长管仍24454容量保留；参考计算继续。可以依据实际余量恢复原进程，需单独记录。无push/PR，无新文章。

更新（82bd3c6之后）：核对原47882同命令/T状态，余量24826957824B时恢复N1600，保留403.351138秒计入原墙钟；第三次容量监测30651已启动并实际live，命令 `build/analysis-venv/bin/python build/recompute-20261109/monitor-fine-n1600-capacity-third.py`。原34110及参考38893同时核对live。长管仍保留，未恢复。
