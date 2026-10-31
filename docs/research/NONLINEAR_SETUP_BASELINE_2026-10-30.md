# SOLVER-01B：非线性诊断开销基线

后续状态：SOLVER-02 已完成 [多步 setup 测量](MULTISTEP_SETUP_PROFILE_2026-10-30.md)，持久化继续暂缓。下文“等待细分测量”保留原检查点语境，构造/析构及独立 PC 成本仍未完全分离。

日期：2026-10-30；源码基线 c1c7508。任务边界：实际测量既有路径，不改求解器，不宣称持久化优化完成。

## 方法

固定 cases/fluid/transient.yaml：单位立方体 125 节点、384 Tet4、500 全局 DoF；10 步，dt=0.05，density/viscosity/pressure_drop=1，ramp_time=0.1；SNES 相对容差 1e-10、绝对容差 1e-12、最多 30 次迭代。默认 preonly/LU 路径。

Release，GCC 15.3、PETSc 3.23.7 real-double/32-bit、OpenMPI 5.0.8、OpenBLAS 0.3.34；云端 CPU 配额 4 核、内存 32 GiB；每 rank 单线程。每 rank 先执行一次不计入样本的报告关闭预热，再交替执行关闭/开启报告，各 3 次。开启项为 -solver_report -linear_report -log_view，因此差异包含三项诊断的综合影响，不是单个选项成本。

端到端 wall 使用 Python perf_counter 包围 mpiexec 子进程，包含启动、计算、VTU 写盘和退出；预处理不计入。不存在重构后的对照，不得计算优化加速比。磁盘/调度噪声未隔离，报告开启顺序固定在每对后面。

## 结果

| rank | 报告开启 | wall 中位数（秒） | 最小–最大（秒） |
| --- | --- | --- | --- |
| 1 | False | 1.316755 | 1.267418–1.319629 |
| 1 | True | 1.318050 | 1.310359–1.318453 |
| 2 | False | 1.316658 | 1.266784–1.317011 |
| 2 | True | 1.317176 | 1.316780–1.319864 |

固定 rank 的全部输出 PointData 在重复运行及诊断开关之间最大差为 0，阈值为 1e-10*(1+abs(reference))；这是同 rank 输出一致性，不是跨 rank 场映射比较。全部 12 个测量运行、2 个预热与2个预处理退出 0。开启报告的每次运行均验证有 10 条 solver_report。

单次样本 r1-n0-report1 的 PETSc 日志中 PCSetUp 为 17 次、时间约 0.059262 秒；它包含预条件器数值工作，不能全算作 SNES 对象分配开销。该样本不代表三次平均。

## 结论与边界

端到端中位数差异远小于部分组内波动，无法从该小规模实验得出诊断显著拖慢或持久化将显著加速的结论。当前结果建立了可复现基线与 PETSc 事件证据，尚未独立计时构造和析构，也未覆盖 FSI、块预条件器及 AMG。SOLVER-02 继续等待细分测量；下一步应分离对象创建/销毁、PC 数值 setup 和进程启动成本，并在至少一个更大问题上复测。

## 重现与证据

```bash
source /workspace/.eonsim-tools/activate.sh
python3 scripts/benchmark_nonlinear_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-nonlinear-baseline-new
```

work 必须不存在以阻止旧产物污染；每次输出使用独立文件。完整命令、可执行文件与案例 SHA256、每步计时、重复样本及原始日志保存在 [data/nonlinear-setup-2026-10-30](data/nonlinear-setup-2026-10-30/)。输入源码固定为结果 JSON 中的完整 commit。

相关 Release 回归 solver_failures、solver_failures_mpi、nonlinear_acceptance、nonlinear_acceptance_mpi：4/4 通过；无失败/跳过。没有运行全部 CTest。
