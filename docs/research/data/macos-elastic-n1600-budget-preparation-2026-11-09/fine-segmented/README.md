# 默认细FSI N1600分段输出启动

基线fe927b1。原N800预算失败后需默认加密；为限制输出峰值，前29周期正常稀疏输出，最后3周期按最多256步划分求解段，段结束且进程成功退出后透明压缩所有VTU。所有51200步与末4800逐步场保留，无删除、插值或周期缩短。每段读取真实checkpoint，按实际restart前缀合并PVD。

实际加载probe：python3 build/recompute-20261109/run-elastic-fine-n1600-segments.py --work build/recompute-20261109/elastic-segment-probe --probe；随后build/analysis-venv/bin/python build/recompute-20261109/check-elastic-segment-probe.py。34866与比较均退出0。四段16步、最大压力0.0697261；全部32个流体/固体相位对照连续运行最大差3.95517e-16<原2e-9容差，80个压缩尝试文件重新SHA通过。测试轨迹完整归档逐成员解码核验。tested-controller.py保留测试源码；生产入口仅另加了probe成功和binary绑定要求。

实际生产命令：python3 build/recompute-20261109/run-elastic-fine-n1600-segments.py --work build/recompute-20261109/elastic-s24-l1-n1600。34110启动后再次确认live。原冻结生产binary不变；实际输入仅dt、steps、checkpoint_interval改变，两域网格/几何SHA一致，材料、时间格式、加载和容差不变。重启会重新建立LU预条件器，小算例对照已覆盖该路径，不声称长期逐位相同或性能提升。

启动free>38GiB，运行20GiB磁盘底线、3GiB RSS与每段24h保护仍保留。分段压缩降低未压缩批次峰值，但总容量仍取决于实际压缩率和其他并发输出；必须继续监控，不能当作容量已无限保障。长程物理审计、完整N1600预算以及细参考/跨程序等原任务未完成；未push/PR。
