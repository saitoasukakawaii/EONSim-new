# Cycle6 prefix archive started; catalog consumer conflict preserved

基线c911444。Wom62758正常exit0按容量暂停，完整日志8850；6194仍存活。单HDF透明压缩实际无分配收益，候选已删除、原文件不变。18514前置清单核对exit0，8001..8800共800不可变已接受检查点；15785执行archive-womersley-n1600-cycle6-prefix8800-chunks.py运行中，保留周期端点/当前代，zstd19逐成员完整解码后移除原payload。

错误：启动新集合前未先停止旧总目录消费者47691。新tar出现但尚未登记时，47691在第14块（016-017/0000）的总目录全覆盖检查失败，exit1。随后试图暂停旧组时ps已经显示进程终态，没有发送信号。事务published-awaiting-catalog；实际当前新包SHA/收据一致、旧备份SHA对应旧包，均保留，尚未删除旧备份，无数据丢失。旧进度/失败日志及事务已保存。

必须完成15785并独立全解码，接入cycle6子集总目录后，再核验该事务并完成提交，随后以新续接入口跳过已完成块继续剩余集合，不盲目重跑原控制器。分析wrapper及预算wrapper尚未加入cycle6前缀，须适配并实际验证再运行完整分析。无完整数值验收，无push/PR。
