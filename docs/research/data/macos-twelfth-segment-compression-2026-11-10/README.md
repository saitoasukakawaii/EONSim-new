# 第十二段压缩与参考场文件低收益记录

基线9a78ed4。88526监测退出0，在49416步容量保留原68300；原34110仍live，检查点49216。7511完成0，命令 `build/analysis-venv/bin/python build/recompute-20261109/compress-logged-fine-n1600-twelfth-segment.py --work build/recompute-20261109/elastic-s24-l1-n1600 --through 49415`，扩展执行权限；796文件透明压缩回收713482240B，事后SHA全通过。只选择严格早于末完整接受日志的本段四类输出。

90359完成0，命令 `build/analysis-venv/bin/python build/recompute-20261109/compress-idle-reference-vtu.py`，扩展执行权限。扫描11238个静态参考VTU，活动N800参考目录排除，并预检实际ps无进程引用选定根；只在大小/mtime稳定且候选/源SHA相同、有分配空间收益时替换。实际替换64文件，仅回收1835008B，事后SHA全部通过，无收益候选删除、原件保留。抽查参考VTU头含vtkZLib压缩器；此实测表明本次进一步透明压缩收益小，不将扫描输入体积记为释放容量，也不声称对所有格式均无收益。

当前N1600仍保持原进程，未恢复；参考继续。后续需要更有效容量回收才能持续输出。无物理验收变化，未push/PR，复用已有方法，无新文章。
