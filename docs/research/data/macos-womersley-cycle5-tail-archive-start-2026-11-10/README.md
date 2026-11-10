# Womersley 第五周期尾段归档启动

基线02b012c。AST通过，`python3 build/recompute-20261109/prepare-womersley-n1600-cycle5-tail-archive.py`，96494 exit0；实际第五周期完整接受日志到8000、原/当前fluid源码写checkpoint早于接受日志一致、799个7201..7999状态的稳定长度/mtime/SHA及manifest逐一核对。第8000周期端点和当前代不在选择范围。

`python3 build/recompute-20261109/archive-womersley-n1600-cycle5-tail7999-chunks.py`，82051运行，128MiB分块zstd19单线程，20GiB加临时空间保护；每块完整解码逐成员校验后才移除原payload，manifest与全部五个周期端点保留。实际清单gzip读回一致。

完整后验、回收统计、总目录接入未完成。**现有analyze-womersley-n1600-streaming.py还未接入此尾段；必须在归档完整终态后加入20块收据、扩展6401..7999恢复区间并做实际读取对照，再运行完整分析。** Womersley预算亦需正确恢复这批状态，不允许直接忽略缺失。τ75128和Wom6194仍运行。复用既有方法，无新算法文章，无push/PR。
