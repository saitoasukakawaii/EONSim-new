# Completed Womersley archive adoption preparation

基线9b272d6。候选38852仍编码中。沿既有采用事务适配alpha1-s96-l1-n400：verified-staged前置、旧/新压缩SHA和长度、原完整清单SHA、候选全部成员独立解码SHA/长度、全部五个原有引用记录精确集合检查；保留旧包/旧收据后更新新包与全部记录，总目录检查、两成员实际恢复SHA通过之后才删除旧备份。

AST通过。实际执行`python3 build/recompute-20261109/adopt-wom-alpha1-n400-recompression.py`对仍encoding的候选exit1按预期拒绝，未创建采用事务目录。完整成功路径尚未运行，未修改任何原归档或恢复记录。后续必须等待38852 exit0及verified-staged，再执行采用器；不能把准备工作记作回收。

复用既有事务及解码校验方法，无新算法文章，无push/PR。
