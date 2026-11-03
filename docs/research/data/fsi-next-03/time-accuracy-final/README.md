# 三格式瞬态时间精度与累计质量预算

源码基础：96f232fdcf597aaeb1f6813cf88fb4b1953682d5。PETSc 3.23.7 锁定环境，Release，2 MPI rank，每rank一个线程；单元为n=2生成的Tet4周期无滑移弹性壁通道，固定tau=.05。用更细BDF2参考比较第二个完整驱动周期20个实际相位，参考体积lumped L2场差；不声明该周期为稳态。

实际命令（在已记录的隔离运行环境中）：

```bash
python scripts/study_fsi_time_accuracy.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec /workspace/scratch/b8438b07bb94/eonsim-cloud/petsc-3.23.7/bin/mpiexec \
  --work build/fsi-next-03/time-accuracy
```

最终BE每周期1280/2560/5120步；BDF2及alpha为160/320/640步；BDF2参考10240步，再与5120步参考比较。受检速度/位移阶门槛BE≥.85、另两格式≥1.7；压力阶单列。所有最终门槛通过；参考再加密差为最小候选误差的3.17%–3.21%。早先粗矩阵失败并不抹除，见上层full-field记录。

`summary.json`为场误差/阶原始结果，`reference-contamination.json`为独立参考精度比。`mass-convergence.json`由各完整接受历史用`fsi_cycle_metrics.volume_budget`再积分得到；最大累计预算误差阶BE约1.000，BDF2约2.000，alpha为2.062/2.016。CSV是求解器原始输出，未删列或抽样；gzip解压后SHA-256与manifest核对。日志同样无删节压缩。网格/配置保留原文。

`second-cycle-fields.tar.gz`保存用于比较的第二周期实际VTU/PVTU及所有引用的rank片段，`phase-files.json`保存物理时间与原文件名。归档不含第一周期场；不能拿不完整场序列重新计算从零开始的周期判据。配置内绝对输出路径仅是当时工作目录，复算时由Runner重定位。

此处manifest为成功计算后的归档记录，在更换可执行文件前记录SHA，并非伪称运行前已有该清单。后续脚本已增加运行前固定可执行文件定义；对缺少该定义的旧目录会拒绝自动复用，需要新目录。旧数值结果仍有效，新增防误复用逻辑未改变其数值计算。
