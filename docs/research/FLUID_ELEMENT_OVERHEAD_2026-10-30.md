# HPC-01E：流体单元计时开关扰动与基线

日期：2026-10-30（Asia/Shanghai）。基线 main f232b07（PR #18 合并），脚本提交1423b99。本轮按用户要求继续上一轮开关测量建议，未修改 C++、案例、容差或 CMake。

## 研究问题与测量协议

评估启用 `-fluid_element_report` 后的观测耗时变化，并建立独立流体 kernel/体单元插入的初始计时数据。不是优化前后加速实验，也不将差值全解释为时钟调用的因果成本。

使用 cases/fluid/transient.yaml：单位通道、Tet4/P1 稳定化、500 DoF、384四面体，rho=mu=1、pressure_drop=1，BE dt=0.05、10步、ramp_time=0.1；边界和压力定标保持既有配置。
SNES rtol=1e-10、atol=1e-12、max_it=30；默认 PREONLY/LU（SuperLU_DIST）。两种模式均开启 solver_report，仅切换 fluid_element_report，不启用 linear_report/Schur。

Release、GCC15.3、PETSc3.23.7、已验证的OpenMPI5.0.8工具链；Xeon Platinum8573C、cgroup4 CPU/32GiB；每rank OMP/OpenBLAS/MKL单线程。
1/2/4 rank，每配置先各模式预热一次，再做5组配对，交替开关顺序（奇数配对数导致一组顺序多一次）。共36次物理运行，其中30次进入统计、6次预热排除；3次预处理另计。未独占VM或随机化全局配置顺序。

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim --parallel 4
python3 scripts/benchmark_fluid_element_report.py --executable build/release/eonsim \
  --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec \
  --work /tmp/eonsim-element-overhead --repeats 5
```

work 必须不存在。[数据目录](data/fluid-element-overhead-2026-10-30)含39份原始日志（含预热/准备）及results/environment JSON。输入原文、SHA256、commit、可执行文件哈希、命令与资源限制保存在JSON。网格为固定Git案例；VTU/分区可按脚本重建。

## 指标定义

- solve：将一次运行10步的 solver_report.solve_seconds 相加；每步已是rank最大值。这不是整个时间区间的单一rank累计最大值。
- wall：外层进程墙钟时间，包含MPI启动、读入、两类报告输出和场输出。
- 配对相对变化：每对 `T_on/T_off - 1`，再取5对的中位数及min/max。**配对比值的中位数不等于两个耗时中位数之比**。
- kernel/insert：开启时先对每rank累计10步，再取rank最大值，随后对5次统计中位数。包含最终验收/原始反力回调，排除面载荷与最终装配等，具体见[计时契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。

## 实测结果

solve及kernel/insert单位为ms，wall为s。耗时列为off/on的各自中位数，变化列为配对中位数[min,max]。

| rank | solve off/on ms | solve配对变化 | wall off/on s | wall配对变化 | kernel rank-max ms | insert rank-max ms |
|---|---|---|---|---|---:|---:|
| 1 | 99.024 / 111.130 | +3.56% [-0.10%, +27.68%] | 1.317 / 1.322 | +3.62% [+0.04%, +3.98%] | 20.956 | 23.230 |
| 2 | 92.356 / 90.128 | +0.60% [-6.25%, +5.64%] | 1.268 / 1.267 | -0.02% [-3.77%, +0.03%] | 8.918 | 9.536 |
| 4 | 94.914 / 95.287 | -0.64% [-7.15%, +12.74%] | 1.320 / 1.318 | -0.05% [-0.42%, +0.02%] | 8.072 | 7.198 |

每次逐步、逐rank单元时间/计数、每对变化，以及各模式耗时min/max均在 [results.json](data/fluid-element-overhead-2026-10-30/results.json)。计时值本身已受测量扰动，kernel/insert不是无仪器的纯净成本，也不是全部装配时间。

## 数值与数据有效性

30个计量样本、6个预热样本全部完成。每步SNES/KSP原因为正，无拒绝评价；同rank开关/重复物理字段最大差3.3307e-16，跨rank最大差4.4409e-16。各模式逐步SNES/KSP迭代轨迹一致；开启时单元计数在重复之间一致。
所有rank/step报告齐全且无重复，计时有限非负，计数是当地单元数的正整数倍。主字段按owner/原始节点ID对齐，包含速度、压力、动量残量；只比较最终输出，未保存逐步物理场。
有效报告与缺rank/step、重复报告、NaN时间、错误单元计数、关闭模式却输出报告五个负对照通过。Release构建退出0（no work to do），没有额外运行全套CTest。

## 结论与限制

单rank配对solve变化中位数+3.56%，范围约-0.10%至+27.68%；2/4 rank范围均跨越零。此次小样本不支持固定开销百分比，也不能以负变化声称开启诊断加速。
端到端wall受到启动及输出等影响；单元计时报告在solve之外输出，因而两种时间的变化不等价。没有分别隔离时钟、日志I/O、调度和缓存扰动；无置信区间或显著性结论。

建议保持单元计时默认关闭，只在专门调查时开启。需要更精确开销或优化依据时，应在独占资源/更大代表规模上扩展重复与控制实验；本轮不改装配算法。
本结果仅覆盖独立流体小案例、单节点1/2/4 rank，不覆盖FSI/ALE、owned/remote插入分离或大规模扩展。完整HPC-01仍未验收完成。

## 参考资料

- [单元计时实现草稿](../../website/drafts/fluid-element-timing.md)
- [PETSc performance manual](https://petsc.org/release/manual/performance/)
