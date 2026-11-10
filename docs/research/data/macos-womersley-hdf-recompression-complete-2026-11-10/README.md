# Womersley 历史 HDF 无损重编码完整验证

源码基线 81e4ca4；Mac arm64，本次仅归档处理，生产二进制与数值模型未修改。

cycle3/4 控制器 17139/15092 均 exit0。分别执行 `python3 build/recompute-20261109/verify-womersley-n1600-cycle3-archives.py` 与 cycle4 对应命令，43315/33110 均 exit0；每组39块、1599成员，逐成员完整解码 SHA/长度与原库存一致，检查点 manifest 未变、已归档原状态路径不存在。独立核对78个当前压缩包 SHA/长度、提交事务/收据一致、旧备份不存在，97606 exit0。

cycle3：3994510980→1835531473B，回收2158979507B；cycle4：3994600326→1835532968B，回收2159067358B；合计4318046865B。事务证据 gzip 已读回一致。

`python3 build/recompute-20261109/review-current-archive-catalog.py`，40679 exit0，输出见 catalog.log。总目录引用历史未改动归档的解码证据，并非全局重新解码；本次两个集合已完整重新解码。复用既有压缩/恢复方法，无新数值或算法结论。

Womersley 完整9600步及预算仍待完成，FSI τ 全程恢复、长管周期延长和主锁平台验证仍未完成；没有 push/PR。
