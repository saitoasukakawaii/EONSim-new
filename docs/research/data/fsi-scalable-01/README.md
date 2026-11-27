# FSI-SCALABLE-01 实验索引

实现和结果解读见[整体求解报告](../../../development/FSI_SCALABLE_SOLVER.md)。原始文件保存在实验服务器的 `$HOME/workspace/fsi-scalable-01-runs/`。每个基准批次有独立的 `results.json`、输入、分区、求解日志和最终场。仓库内的摘要省略了主机路径，原件相对路径和 SHA-256 可用于回查。

[结果与原件索引](summary.json) · [逐次运行数据](runs.csv) · [能量优化对照](energy-and-pressure.png) · [强扩展](strong-scaling.png) · [弱扩展](weak-scaling.png) · [混合并行](hybrid-scaling.png)

## 证据目录

| 远端相对路径 | 内容 |
|---|---|
| `environment.log` | CPU 拓扑、NUMA、主机内存、磁盘、依赖、绑定探针和用户级 perf 可用性 |
| `omp-binding.c` 与 `omp-binding.log` | 两个 NUMA 域的实际双线程绑定探针 |
| `baseline-source.txt` / `baseline-build.log` | 基线提交、树、可执行文件摘要和 Release 构建 |
| `baseline-ctest.log` | 基线 2 rank 通过与 4 rank 超时 |
| `smoke/*/results.json` | 703 自由度、2 rank 的直接参考与严格交换对照 |
| `baseline/*/results.json` | 10,387 自由度的 Vanka 和 Braess 基线 |
| `pressure-verify-{1,2,4}.log` | 有界压力像的制造解 |
| `pressure-timing/*/results.json` | 8 rank、三次交错的能量优化与压力像对照 |
| `pilot-n16/*/results.json` 与 `pilot-n22/*/results.json` | 41,959 与 108,379 自由度试跑 |
| `coarse-smoke/*/results.json` 与 `coarse-audit-smoke/*/results.json` | 初次粗层验收误判和按实际行数修正后的重跑 |
| `coarse-timing/*/results.json` 与 `hybrid-pilot/*/results.json` | 自适应粗层及 4 MPI × 2 OpenMP 试跑 |
| `petsc-profiles/*/petsc.txt` | 与正式计时分开的 PETSc 事件分析 |
| `memory-guard.json` | 低上限的受控终止，退出码 -15 |
| `scale-n22/*/results.json` | 108,379 自由度的五档强扩展正式收据 |
| `weak/*/results.json` | 4–128 rank、41,959–1,259,907 自由度六档弱扩展正式收据 |
| `hybrid-128/results.json` | 五种等 128 核配比的预热与交错三次测试 |
| `pilot-n37/*/results.json` 与 `pilot-n47/*/results.json` | 511,939 与 1,046,979 自由度的五步对照 |
| `joint-pressure/*/results.json` | 按 Galerkin 测试权重压缩压力、联合增强及 2/4 rank 直接参考 |
| `zero-lift-verify-{1,2,4}.log` 与 `zero-lift-ab/results.json` | 独立密集块参考和零提升交错计时 |
| `pulsatile-robin-rcr-retry/summary.json` | 615 自由度的脉动 ALE、Robin、RCR 联合算例 |
| `physics-coverage.log` | 既有物理回归与归档输入缺失的原始记录 |
| `physics-tube-rerun.log` 与 `physics-arterial-clean.log` | MPI 传输错误及修正后的干净复跑 |
| `explicit-binding-ctest.log` | 最新运行源码的 2/4 rank 整体 MG CTest |

## 复跑

使用环境中的 PETSc 3.23.7 及 Open MPI，Release 启用 OpenMP。在已核验的源码根目录执行，`run_root` 设为本次实验目录，`python` 设为现有的 Python 3.12。每次运行保存实际源码、可执行文件、网格、参数、原件哈希及失败状态。

```bash
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export OMPI_MCA_pml=ob1 OMPI_MCA_btl=self,vader,tcp
sha=$(git rev-parse HEAD)
mpi=$(command -v mpiexec)
"$python" scripts/benchmark_fsi_block_scaling.py \
  --executable build/release/eonsim --mpiexec "$mpi" --build-source "$sha" \
  --work "$run_root/energy-pressure" --campaign strong --subdivisions 10 --ranks 8 \
  --reference-mode mono_braess --modes mono_braess mono_braess_tentative mono_pressure_image \
  --timing-repeats 3 --timeout 160 --local-rss-limit-gib 180 \
  --mpi-arg=--map-by --mpi-arg=socket --mpi-arg=--bind-to --mpi-arg=core \
  --mpi-arg=--report-bindings
```

将 `--subdivisions 10 --ranks 8` 换成 `--subdivisions 22 --ranks 8 16 32 64 128` 可复现十万级强扩展矩阵。该组使用 `mono_pressure_auto` 作为各划分的运行配置，并比较与 8 rank 参考的完整场及接受历史。混合试跑的绑定参数为 `--mpi-arg=ppr:2:socket:PE=2`、`--omp-threads 2` 和 `--ranks 4`。PETSc 事件分析在额外进程运行中加 `-log_view :petsc.txt`。
