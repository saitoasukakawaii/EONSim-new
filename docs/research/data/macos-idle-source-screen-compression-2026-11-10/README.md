# 闲置源码及已完成筛选输出压缩

基线3709283，macOS arm64。实际运行 `build/analysis-venv/bin/python build/recompute-20261109/compress-idle-dependency-source.py`，27555退出0；选择闲置Trilinos源码6123文件，排除.git/符号链接/多硬链接/小文件，5967替换，回收360546304B，事后SHA全部通过。安装库、构建产物和运行中的生产程序未修改。

实际运行 `build/analysis-venv/bin/python build/recompute-20261109/compress-idle-alpha1-screen.py` 退出0；已完成alpha1启动筛选raw-review通过，进程预检无使用该目录，10个VTU透明压缩回收107442176B，全部替换事后SHA通过。二者总回收467988480B，无原始内容删除，无未来恢复前置条件。不能把源码压缩当作新数值验证。

39359归档与38893参考继续，N1600仍保留原92463，未恢复；主计算最终验收尚未完成。复用既有透明压缩方法，无新文章；未push/PR。
