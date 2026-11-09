> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# First alpha1 periodic field result

Frozen b072cc8 executable, source/controller checkpoint0b9e980. PETSc3.23.7,
four ranks, standard Schur, default stabilization, alpha1,48/4/8 seed level0,
1737nodes/8064tetrahedra,100steps and100saved phases per cycle. Six cycles
completed, including the first two warmup cycles. All2071 archived input,
checkpoint, analysis and provenance files were read back and SHA256 verified.
The executable hash is retained; the binary is not redistributed.

| Last-cycle metric | Result | Gate |
| --- | ---: | --- |
| Velocity relative L2 | 2.435798% | fail1% |
| Pressure RMS / amplitude | 1.767865% | fail1% |
| Flow amplitude | 3.136784% | fail1% |
| Flow phase | .145188degrees | pass1degree |
| Maximum net flux | 6.9375e-14 | pass1e-10 |
| Last periodic u/p differences | 7.030e-15 /9.861e-15 | pass1e-6 |

The preceding periodic differences also pass. No coarse physical accuracy
qualification is inferred from periodicity. Paired time/space studies and the
fine-level run remain active in the same sequential alpha1 controller.

The exact commands, frozen analysis sources and real four-process affinity
preflight are in analysis-and-controller.tar.xz. Each rank is restricted to
CPUs10-17, separate from the primary alpha2 CPUs0-7 and serial elastic CPU8.
Concurrent execution here is not a speed/scaling benchmark. NumPy1.26.4,
SciPy1.17.1 and h5py3.14.0 were used for the analysis.
