# τ recovered series finalizer preparation

基线2e87ca7。入口 `python3 build/recompute-20261109/finalize-tau-recovered-series.py --work build/recompute-20261109/elastic-s24-l1-n800-tautime-n400`。

沿已验证finalize-elastic-series入口适配恢复目录：验证early1..23200和dense-recovery23201..25600完整成功日志/收据，重新核对二进制、输入、原checkpoint及失败记录哈希，重新读取439步878对重叠体场，检查两域PVD完整有序且真实文件存在，之后发布合并索引与completion-postflight。保留原dense失败分支；不修改分析器、物理或误差门槛。

AST通过。在实际仍运行的恢复工作区执行上述入口，exit1按预期拒绝Incomplete trajectory，两个索引和完成记录均未生成。完整成功路径尚未运行，不能称已完成审计接入。后续必须先等待75128终态和receipt，再执行此入口及原audit_pressure_tube.py（first-step23201），随后才能运行τ分解。

复用既有完成后索引汇总方法，无新算法文章，无push/PR。
