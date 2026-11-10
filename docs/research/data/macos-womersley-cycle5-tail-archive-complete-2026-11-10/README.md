# Womersley cycle5 tail archive and reader verified

基线808576a。82051归档exit0；51712执行verify-womersley-n1600-cycle5-tail7999-archives.py exit0，20块799状态完整解码SHA/长度与原库存一致、manifest不变。移除分配2591981568B，归档917769083B，净回收1674212485B。收据gzip读回一致。

分析包装器增加20尾段收据，恢复范围6401..7999，其余原9600完成要求/四阶积分/原分析器均未改。`build/analysis-venv/bin/python build/recompute-20261109/check-womersley-cycle5-tail-reader.py`，69287 exit0，7201/7600/7999三个归档状态及8000保留端点数组与原读取器完全一致，恢复副本清理通过。完整解析审计仍未运行。

总目录新增799状态子集；29406执行review-current-archive-catalog.py exit0，16完整库存及11子集，日志随附。未变归档复用历史解码证据，不称全局重解码。τ和Wom继续，物理/预算验收仍待完成。复用既有方法，无新算法文章，无push/PR。
