# 原物理审计读取器的有界体场恢复

基线ccd11b1。

## 2026-11-10：完整物理审计的原读取器恢复验证

[证据](../research/data/macos-streaming-physical-reader-2026-11-10/README.md)：51265实际geometry48的23200端点及23201/24000/25600三相位、两域全部字段，先展开与按帧恢复调用原eonsim_frame完全一致；创建副本全部回收。early端点与dense使用独立归档游标，避免同归档内early排序在dense之后引起回退漏读。新audit-pressure-streaming.py仍调用原analyze并保留原所有相位/前一端点/公式/门槛；长管未完成的真实前置拒绝通过，未创建报告或proof。此测试不是完整物理审计，长管体场仍未归档，后续实际完整审计和恢复覆盖仍必须执行。65569预算继续，无push/PR。

实际验证：OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/test-streaming-physical-reader.py。同时运行audit-pressure-streaming.py对尚未完成的真实length24入口，确认完整轨迹凭据缺失时拒绝且不输出报告。

新wrapper仅替换原模块eonsim_frame外侧I/O恢复，原analyze的拓扑、物理、时间、完整PVD相位与指标计算均保持。每次恢复验证原manifest/收据/archive和成员SHA，原读取器继续校验实际拓扑并映射坐标。非归档输入继续由原读取器处理。early与dense分别保持单调游标，避免初始端点先读使最后dense帧不可达。未修改正在运行的完整预算/生产程序。未来消费者必须保留proof并验证完整覆盖；退出0不能代替数值门槛。
