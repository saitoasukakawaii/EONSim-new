# 细网格 N400 跨求解器观测比较

基线dbedcc7。EONSim与已采用补丁的svFSI均完成12800步，同物理输入/网格/时间网格/窗口11601..12800；比较入口重新由实际末周期400相位计算谐波、核对审计源码和所有先决门槛。保留原幅值分母（svFSI）和绝对相位，不拟合时间偏移。冻结比较程序SHA与快照一致。

执行：`build/analysis-venv/bin/python build/recompute-20261109/compare-pressure-audits.py --eonsim build/recompute-20261109/elastic-s24-l1-n400-audit.json --svfsi build/recompute-20261109/reference-kinematic-elastic-s24-l1-n400-nu0/audit.json --output build/recompute-20261109/elastic-fine-n400-cross-observables.json`。命令退出0仅表示报告生成，observable_gates_passed=false。

中部压力幅值差2.769315779%超过2%，相位差1.411537097度超过1度，均失败。径向位移和投影面积幅值差2.7212704%/2.7212711%，通过5%；两端流量幅值差2.0061353%/2.1257494%，相位差0.8238831/0.8975643度，通过各自5%/2度。两求解器Lamé均值约1.2376%，局部物理/周期/参考严格收敛先决门槛均通过。

这仅是N400同网格诊断，不能代替N800目标比较或独立时间/空间误差预算；不能由幅相差直接归因于某项稳定化或ALE算子。旧粗网格压力失败与时间预算失败保留。本次未比较完整节点场，未恢复已归档体场。两输入审计压缩读回逐字节一致，完整原始场分别由既有存储清单/本地目录保留。无整体验收或48小时完成声明，未push/PR。
