# FSI-NEXT-03：实施中的检查点

## 最新进展（历史段落保留）

时间精度和累计质量预算已通过，完整原始输入/接受历史/日志与第二周期场见 [time-accuracy-final](time-accuracy-final/README.md)。checkpoint保存间隔的Debug受影响回归7/7通过，日志见 `cadence-debug/`；默认稳定化n=2周期86通过，n=8仍在推进。等长追加周期估计及100相位实际采样检查正在实施。完整空间收敛、10%误差分离、最新脚本回归和最终审查仍未完成，无PR。以下“未实施”均是对应历史检查点状态。

基线 main 4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e，分支 codex/fsi-next-03-periodic-convergence。
48小时是预算，当前未完成整体验收，不能创建PR。

## 已执行

- `python tests/test_fsi_cycle_metrics.py`：四项通过。标量相位对齐、均值漂移及坏历史拒绝；不代表完整场周期性。
- 使用 `scripts/cloud/run.sh 3.23.7 release explicit /workspace/scratch/b8438b07bb94/eonsim-cloud build/fsi-next-03/selection.json`，selection 为 `{"tests":["fsi_flow"]}`。
- 首次编译成功，但测试遇 LLVM OpenMP `z_Linux_util.cpp(2125)` 启动断言；日志保留 failures/。不是数值失败或非法输入正确拒绝。
- 复用上一轮有记录的PID隔离方法：同一命令内启动回收 `/bin/true`，直至PID超过 `/dev/shm/__KMP_REGISTERED_LIB_*` 中的现存最大PID，再调用同一编译脚本。未删除共享对象、未修改依赖、未调松容差。Release fsi_flow 1/1通过；精确底层断言根因仍未调试确认。
- previous-cycle-audit.json 是旧六周期数据的重新后处理，不是新的求解。尺度固定为位移1e-4，128个相位点，末周期比较终点t=.6。

## 正在实施及未验收

30周期固定tau/default tau对照为探索实验。标量检测尚未接入完整场、连续三周期停止、checkpoint续算及正式收敛驱动；线性插值的相位采样误差还需独立检查。
三格式时间收敛、三网格空间收敛、10%污染界限、独立移动几何、1/2/4 rank恢复、Debug验证、CI映射、知识草稿及最终审查均未完成。没有新的PR或合并。

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。
