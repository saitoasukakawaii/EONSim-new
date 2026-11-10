# N1600 原进程恢复与边界归档恢复样本

基线bd4e991。粗N1600边界首块0000的流体/固体各一个成员，以现有restore-womersley-materialization.py实际恢复到独立probe目录，工具核对归档SHA并解压扫描、逐成员SHA/大小验证；再次读取恢复文件校验通过。probe-receipt和verification保留，原归档及缺失路径未变。仅两样本恢复结论，不替代剩余归档终态审计。

74185已完成6批3360成员，当前继续。空间超过22.25GiB后实际ps核对45495同PGID/完整命令/T状态，SIGCONT原进程；保留170.033041秒计入原墙钟。恢复瞬间可用24063045632B。新监测41843启动且实际live，仍21.25GiB提前保留；第二次使用独立收据名，原54503不重启。原求解/控制器未改，检查点/相位未删。命令：`build/analysis-venv/bin/python build/recompute-20261109/monitor-fine-n1600-capacity-second.py`。

独立预算及细N1600最终物理审计仍待完成。旧数值失败保留，无push/PR；复用已有方法，不新增文章。
