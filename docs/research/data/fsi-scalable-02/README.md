# 复跑和收据

运行根目录下的原生输出按作业独立保存。`paired-summary.json` 与 `runs.csv` 对应小网格 EONSim 直接法 / 原版 svFSI。`arterial-asm.json` 与 `ablation.json` 保存首次 ASM 实测，当时 ASM 命令还带 `-linear_report -solver_report`，相关数据包含这些额外诊断。当前驱动将额外线性残量与步时诊断移到独立重放。报告中的 `T_job` 比值使用双方同口径墙钟；将共同输入转换和分区费用计入时请使用 `T_total`。对于同网格多次复跑，已存在的离线准备卷只计一次。

以仓库根目录为起点，`dir` 指向本目录，`case_dir` 是保存 `case.json`、`fluid.msh`、`solid.msh` 的原始 SI 血管目录。`eon`、`native` 和 `mpi` 指向已经校验的原生可执行文件，`root` 是新的运行目录，`python` 环境包含 NumPy、SciPy 及 VTK。运行前导出 `PYTHONPATH` 以包含仓库的 `cases/fsi` 和 `tests`。Slurm 单核作业直接执行命令；多核作业用 `--ranks`、`--mpiexec` 让驱动在分配中启动相同 rank 数的两个程序。

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$PWD/cases/fsi:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
dir="$PWD/docs/research/data/fsi-scalable-02"
for steps in 20 32 100; do
  python "$dir/paired_tube.py" --case "$case_dir" --root "$root/formal-$steps" \
    --steps "$steps" --gate "$root/formal-20/summary.json" \
    --eon "$eon" --svfsi "$native" --eon-linear asm --svfsi-linear moderate || exit 1
done
```

直接法与原版严格容差对照分别使用 `--eon-linear direct`、`--svfsi-linear reference`，每组配置另设根目录，重新取得其 20 步收据。`native_timing.py` 可在原生 CMake 构建旁单独重链步时版本；`internal_tube.py` 在同一分配下做直接法/ASM 交错试跑和原生时间循环重放。以 `--help` 查看路径参数。所有窗口使用同一 `dt=1/32 s`。

合成五步测试使用 `scripts/benchmark_fsi_block_scaling.py` 的 `--campaign strong --steps 5 --timing-repeats 3 --reference-mode mono_pressure_auto --modes mono_braess_tentative`，每个 MPI rank 分配 `OMP_NUM_THREADS` 个核，OpenMPI 使用 `--bind-to core --map-by slot:PE=N --report-bindings`。十万级 `--subdivisions 22`，五十万及百万级分别取 37、47。作业 `395` 固定可执行文件 `eonsim-610eadd`，独立输出 `large-t2`、`large-t4`、`large-t1`。`collect_scaling.py` 汇总每次尝试和源收据哈希。

`level-events.json` 中每个字典分别给出 PETSc 事件的 rank 0 与跨 rank 统计。`ablation.json` 中 PETSc 事件的数组顺序见各自 `column_order`。`host-environment.txt` 保留实际动态库与运行时版本，私有路径用 `$HOME` 表示。
