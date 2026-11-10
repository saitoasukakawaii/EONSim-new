# 按相位恢复原始体场的有界读取

基线a4bcd62，macOS arm64/PETSc3.25.6产生的实际单rank轨迹，分析OMP/OpenBLAS/VECLIB单线程。完整N1600物理审计94137仍运行，不修改正在运行的审计或冻结比较kernel。

新增restorer绑定恢复收据、原manifest与整个archive SHA；每次按单调相位顺序解码请求成员，在原路径恢复字节并校验，调用原Study.frame后仅回收本次创建且SHA未改的展开副本。原已存在文件仅验证、不删除。每成员保留20GiB+文件大小+64MiB容量检查；重复请求/缺失成员/非单调顺序拒绝。未请求archive尾部可终止读取，不宣称该次重新全解码；完整archive SHA及此前完整解码证据保留。

72751运行 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/test-streaming-volume-materialization.py` 退出0。真实粗N1600/细N800四个共同相位，先全部展开后使用原比较器，与每相位恢复后使用同一比较器，完整报告逐项完全一致。两侧各恢复8成员，单相位新增展开峰值597101/4477007B；异常消费者清理通过。重复收据、成员与manifest不符、错误manifest、冲突共享manifest、错误archive SHA共5类拒绝通过。测试后全部原缺失路径仍缺失，完整字节保留在归档。不是完整预算或性能加速证明。

新增analyze-elastic-n1600-budget-streaming.py仅用子类frame包裹恢复；原compare-pressure-fields.py、原kernel、所有1600/800相位、P1范数、tail/sampling与10%门槛未改，源码SHA绑定。实际不完整输入前置检查按预期退出1，未创建分析输出目录。完整运行须等待fine审计终态；尚未执行完整预算。

此前“预算前恢复体场”的要求可由此按相位恢复逐一满足，不能跳过任何被原预算读取的帧；完整恢复入口仍保留供其他消费者使用。完整预算必须另行验证逐成员哈希、覆盖与报告，四相位测试不能替代最终验收。未push/PR。

## 2026-11-10：修复完整预算入口漏接恢复组件

复核39e3139的实际wrapper发现，原study仍直接构造Study，且finally使用未定义stores；此前四相位测试只覆盖独立组件，前置检查因缺少fine审计提前退出，均未覆盖完整入口接线。因此此前“新增wrapper已用子类frame包裹”的描述不成立。现以make_streaming_study明确接入实际恢复子类和stores，保留原kernel/相位/范数/门槛。15319实际执行test-streaming-volume-budget-wrapper.py退出0：直接提取并执行生产wrapper的factory，真实粗N1600/细N800四相位报告与全部展开读取完全一致，两侧各8成员、峰值597101/4477007B，清理及5类拒绝通过。完整预算仍待94137审计完成，未把四相位验证算作完整验收。wrapper SHA8860800cb01e8e3ecbc60a5156b2b28852c72d18278d0493cedc808b0dcbf766。无push/PR。
