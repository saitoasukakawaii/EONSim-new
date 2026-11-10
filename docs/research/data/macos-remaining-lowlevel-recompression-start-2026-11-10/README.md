# Re-encode only confirmed lower-level archives

基线8c6708b。原生ps只读检查确认三个reference诊断目录无活动求解；只读VTU盘点648文件，仅2组单链接重复、688128B潜在收益，不执行该低收益变更。

原执行脚本证实boundary014-015/016-017/018-019/prefix均zstd9，native dual-path为zstd3；先前无收益009-013确为zstd19，本次明确排除，N400参考已zstd19亦排除。显式五集合共120块，选择清单随附。

复用逐块旧/新完整tar SHA、可恢复收据事务、每块总目录核对后才删除旧备份的实现，20GiB加单块临时空间保护。AST通过，`python3 build/recompute-20261109/recompress-remaining-lowlevel-archives.py`已启动47691；完整后验及回收统计尚未完成。所有生产求解仍保持原进程容量暂停，未降低恢复门槛。复用既有方法，无新算法文章，无push/PR。
