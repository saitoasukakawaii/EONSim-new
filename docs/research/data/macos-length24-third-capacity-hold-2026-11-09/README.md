# 长管第三次容量保留

基线 cbabd7c。51629监测器完成0，在完整接受24454步、可用23576424448B时保留原进程组73679，实际ps确认同命令及Ts。原20GiB控制器未退出，最终25600步和物理验收尚未完成。

`python3 build/recompute-20261109/compress-logged-elastic-frames.py --work build/recompute-20261109/elastic-s24-l1-n800-length24 --through 24453` 首次受限执行退出1：ditto返回后临时文件0B，大小/SHA断言阻止替换，verified_replacements为空。确认原文件5606446B存在后仅清理0B临时文件；扩展执行权限重试15325完成0，200个文件无损压缩，回收376279040B，并事后逐文件重读SHA全部通过。确切空临时文件成因未独立定位，不能仅据重试成功推定权限根因。失败记录保留。

恢复需核实原PID/命令/T状态，使用新的监测收据名；第三次监测器不可直接重跑。其余三组计算继续。未push/PR。
