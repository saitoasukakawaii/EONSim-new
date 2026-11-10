# N1600默认FSI预算入口

基线d03270d。原N800内核不修改；新副本只把目标索引、半步索引、采样数量标签和报告字符串参数化。source check将这些明确改动反向还原后，要求其余源码逐字节等于原内核。P1范数、周期31/32尾项、第32周期、每隔一步线性重建、五场分别10%space和全部前提均不变。

实际执行python3 build/recompute-20261109/check-elastic-refined-budget.py退出0。另从已有真实N800的space/time/tail/sampling报告重新计算全部判定，仍保留流体速度/压力/结构速度三项时间失败；这不是重新读取所有原始场。实际未完成N1600入口调用退出1且未创建输出目录。具体命令、报错、SHA见check报告。

正式入口：build/analysis-venv/bin/python build/recompute-20261109/analyze-elastic-n1600-budget.py --solver eonsim --output build/recompute-20261109/elastic-n1600-budgets。需先完成粗N1600、细N800、细N1600的全部数值receipt和最后三周期物理审计。新细成员使用分段controller完成记录，原细N800使用已保留postflight记录。

N1600完整数值预算尚未运行；预备检查不构成新精度结果。全部十个长程handle本次确认live，剩余磁盘约38.57GiB，未push/PR。
