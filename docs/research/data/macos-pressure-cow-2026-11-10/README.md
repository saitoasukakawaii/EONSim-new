# 闲置压力输入写时复制去重

基线 b3ae49d，macOS arm64，本地 APFS。实际执行 `build/analysis-venv/bin/python build/recompute-20261109/probe-pressure-cow-clone.py` 与 `build/analysis-venv/bin/python build/recompute-20261109/deduplicate-idle-pressure-cow.py`，后者会话28802退出0。

独立试验对压缩输入实际调用 clonefile，副本修改后源SHA不变，inode不同，临时副本删除。批量操作排除运行中的参考N800目录，并通过进程列表检查所选目录闲置；100输入只有8种内容，92副本使用无回退clonefile。替换前后及最终100文件全部SHA验证通过，路径与字节保留，独立inode可单独修改。共享文件系统可用空间23596630016→25148731392B，观测增加1552101376B；不是隔离测量，不使用逐文件st_blocks之和推断共享块节省。

核对原PID68300/PGID/命令/暂停状态后恢复N1600；保留607.286784秒。新容量监测会话5078启动，原20GiB控制器和21.25GiB监测阈值不变。无求解器修改；无新数值验收结论；尚未push/PR。其余容量保留任务仍待恢复。
