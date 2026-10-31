# HPC-01C：瞬态流体与弹性 FSI 装配阶段测量

后续状态：独立流体的 kernel/插入计时及开关扰动已在 [HPC-01E](FLUID_ELEMENT_OVERHEAD_2026-10-30.md) 补充；FSI 的同类细分及纯通信归因仍未完成。下文原始测量不因此扩大范围。

2026-10-30（Asia/Shanghai）。基线 main `28c60da`；按用户在候选任务提出后要求继续的指示执行。
本轮不修改 C++、案例、容差或构建配置。完成已有装配测量要求中的 transient、1/2/4 rank 和首步/后续步增量，完整 HPC-01 的纯 kernel/插入分离仍未完成。

## 设置与复现

- 使用仓库 `cases/fluid/transient.yaml` 与 `cases/fsi/elastic.yaml`，输入原文及 SHA256 在结果 JSON。
- fluid：单位立方体、500 DoF、rho=mu=1、pressure_drop=1、BE dt=0.05、10 步、ramp_time=0.1；既有抛物速度边界和压力定标。
- elastic：102 个有效 DoF，共形弹性 FSI，BE dt=0.02、10 步，压力 1、rho=mu=1、Young=100、Poisson=0.3、solid_density=1、thickness=0.25；沿用既有边界/接口消元，不把该小模型当作通用三维验证。
- 两例 SNES rtol=1e-10、atol=1e-12，最大迭代分别 30/20；默认 PREONLY/LU（SuperLU_DIST）。仅启用 `-solver_report`，没有启用 Schur 或 linear_report。
- Release；GCC 15.3.0、PETSc 3.23.7、已有 Open MPI 5.0.8 工具链；Intel Xeon Platinum 8573C，cgroup 4 CPU/32 GiB；每 rank OMP/OpenBLAS/MKL 单线程。
- 每例在 1/2/4 rank 各重复三次；同一节点，无预热或随机化，不保证共享 VM 无外部扰动。

```sh
source /workspace/.eonsim-tools/activate.sh
cmake --build --preset release --target eonsim --parallel 4
python3 scripts/profile_multistep_setup.py --executable build/release/eonsim \
  --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec \
  --work /tmp/eonsim-transient-phases --ranks 1 2 4
```

[数据目录](data/transient-assembly-2026-10-30) 保存 24 份原始日志、environment.json 和 results.json。日志中 solver_node 含 rank，阶段计时仍为 rank-max；没有伪称取得每 rank 独立阶段时间。
JSON 保留输入、命令、可执行文件哈希、180 个逐步报告、60 个逐步统计和18个逐次运行统计。网格来自固定 Git 案例；VTU/分区为可重建临时产物。
测量启动脚本为 82081d5；独立固体场验证在测量完成后用 0f90585 执行，统计补充用 f92e57b 执行。对应提交号独立记录，未为分析脚本调整重复运行物理求解；最新脚本已集成这些检查。

## 时间口径及结果

首步：每次运行第 1 步的三个样本；后续：每次运行第 2–10 步的均值，再对三个运行样本统计。
下表是中位数，单位 ms。每项 min/max 和逐步/逐次分布见 [results.json](data/transient-assembly-2026-10-30/results.json)，不将同一次运行的九个后续步当成九次独立重复。
“后续”不保证物理状态或计算负荷已稳定，尤其 fluid ramp 尚影响第2步；原始逐步数据保留这种变化。

| case | rank | phase | solve | assembly | callback | assembly_finalize | failure_sync | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| fluid | 1 | first | 18.341 | 5.938 | 5.656 | 0.077 | 0.003 | 0.035 |
| fluid | 1 | later | 8.696 | 3.232 | 3.156 | 0.033 | 0.002 | 0.017 |
| fluid | 2 | first | 18.984 | 6.328 | 3.072 | 3.024 | 0.291 | 0.428 |
| fluid | 2 | later | 8.106 | 3.029 | 1.584 | 1.327 | 0.160 | 0.289 |
| fluid | 4 | first | 20.309 | 6.396 | 2.429 | 3.474 | 1.162 | 0.434 |
| fluid | 4 | later | 8.446 | 2.895 | 1.254 | 1.512 | 0.646 | 0.324 |
| elastic | 1 | first | 4.412 | 2.384 | 2.306 | 0.038 | 0.002 | 0.012 |
| elastic | 1 | later | 4.033 | 2.680 | 2.621 | 0.024 | 0.002 | 0.007 |
| elastic | 2 | first | 8.735 | 5.127 | 2.588 | 1.990 | 1.677 | 0.193 |
| elastic | 2 | later | 4.258 | 2.758 | 1.223 | 1.423 | 0.333 | 0.222 |
| elastic | 4 | first | 6.689 | 2.687 | 0.800 | 1.458 | 0.280 | 0.239 |
| elastic | 4 | later | 3.932 | 2.156 | 0.762 | 1.276 | 0.330 | 0.270 |

各计时字段的唯一语义见 [L2 契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。只累计正常完成评价，并在 SNESSolve 后冻结；不含最终验收/反力重装配。所有样本拒绝次数为零。
callback 含物理计算与插入，assembly_finalize 含本地整理/通信。ghost 是 assembly 内的子集；linear 与 assembly 可处于 solve 内不同路径。独立 rank 最大值不能直接相加或解释为严格百分比。

## 数值与数据验证

18 次运行、180 个接受步成功。每步 SNES/KSP reason 为正，残量有限，阶段时间非负且不越过 assembly 边界。
fluid 残量范围 3.2771e-17–1.6769e-11，elastic 为 7.1209e-14–4.9250e-12；字段验收仍由既有求解器执行。
主输出按 owner/原始节点 ID 对齐的跨 rank 最大差为 6.6614e-16；独立固体场为 2.4287e-17；同 rank 主输出重复差最大 5.5512e-16。
比较阈值沿用脚本的主输出重复检查及跨 rank 2e-8 绝对差检查；混合单位的最大绝对差仅作回归指标，不代表无量纲物理误差。仅比较最终输出场，没有逐步场文件对照。
有效日志及缺 phase、NaN、非零拒绝计数、超外层时间四种错误输入检查均通过。Release 构建返回 no work to do。

## 结论与边界

fluid 首步 solve 明显高于后续均值，不能以首步成本外推所有时间步；小型 elastic 首步随 rank 的变化也不能直接作为稳健加速比。
fluid 后续 callback 从单 rank 3.156 ms 降到四 rank 1.254 ms，但最终装配从 0.033 ms 增至 1.512 ms，solve 中位数仅从 8.696 ms 变为 8.446 ms。多个成本相互影响，不据此宣布并行优化完成。

下一步结论为**暂缓重构，必要时按目标规模补更细事件测量**。本轮不是多节点强扩展、物理模型 validation 或计时开销实验；未跑全套 CTest，未修改求解器。纯 kernel/插入分离、拒绝评价成本和更大 FSI 模型仍需独立任务与需求。

## 参考资料

- [既有多时间步 setup 测量](MULTISTEP_SETUP_PROFILE_2026-10-30.md)
- [稳态装配阶段基线](ASSEMBLY_PHASE_BASELINE_2026-10-30.md)
- [PETSc performance manual](https://petsc.org/release/manual/performance/)
