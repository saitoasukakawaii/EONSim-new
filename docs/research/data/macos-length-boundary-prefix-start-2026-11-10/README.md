# 长管不可变边界前缀归档启动

基线a47ee04。实际ps确认长管73679同命令/Ts；已完成密集日志连续23201..24454，选严格早于末接受步的边界前缀：早期29步和密集23201..24453，每步流/固两文件，共2564文件。全部核对不被PVD引用、源文件大小/mtime稳定并建立SHA清单。原分配4385742848B、逻辑8393514513B，不等于预计释放容量。

清单命令 `build/analysis-venv/bin/python build/recompute-20261109/prepare-length-boundary-prefix.py`，79581完成0。归档命令 `build/analysis-venv/bin/python build/recompute-20261109/archive-length24-boundary-prefix-chunks.py`，18670实际live，已完成前21批840成员；每批最多128MiB逻辑字节、zstd9单线程，解压逐成员SHA通过后发布恢复收据并回收展开副本，体场/检查点/当前及未来边界未动。不是完成研究全目录清单。

准备了终态逐块完整解码校验器verify-length-boundary-prefix.py及更新后的非运行中capture-elastic-length24-n800.py：最终capture合并保留文件与归档成员，显式记录恢复收据，不能因文件缺失而静默缩小原始清单。两入口仅通过语法检查，完整归档验证/最终capture尚未运行。终态还需恢复样本和统一归档清单新增这一未完成研究的前缀；已有v2只扩展粗N1600，尚不足覆盖本前缀。

同时41843监测完成0，细N1600在dense-002第46787步保留原47882；原34110控制器仍live，检查点为46656，未恢复。第二次保留收据已保存。粗边界74185与参考38893继续。无新物理结论、无push/PR，复用现有归档方法，无新文章。
