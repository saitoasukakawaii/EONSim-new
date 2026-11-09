> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S96 fine N200 complete Womersley trajectory

The independent alpha2, S96/R8/A8 level1 study completed all1200 steps,
six cycles with200 phases per cycle, on50,609 nodes and276,480 tetrahedra.
The final three cycles are sampled. Native one-rank candidate60eb5cc0 uses
explicit MUMPS/chord and LU reuse window32; the default solver is unchanged.

| Diagnostic | Result | Gate |
|---|---:|---:|
| Velocity relative L2 error |0.475825763%|<1%|
| Pressure RMS/amplitude |0.360074480%|<1%|
| Flow amplitude error |0.234326215%|<1%|
| Flow phase error |0.060445160 degrees|<1 degree|
| Maximum net flux |1.087198552e-17|<1e-10|
| Last-cycle velocity/pressure difference |4.946e-15 /5.524e-15|<1e-6|

All six preliminary gates pass. [Full analysis](n200-analysis.json) and
[capture summary](n200-summary.json) explicitly retain full_qualification=false.
The paired fine N400 trajectory and the spatial, time, tail and sampling
budgets remain pending. Each budget term must still be below10% of its
specified final spatial field difference. This result does not erase the
original S48 fine N200 velocity error1.046822% or the S96 coarse N200 flow
amplitude error1.058047%, both above their1% gates.

The immutable capture completed2026-11-08T15:56:24Z:1,672 verified source
files,2,827,259,646 raw bytes,44 lossless tar.xz parts totaling1,820,122,244
bytes. It preserves the complete retained current/history fields, mesh,
input definitions, actual commands, frozen sources and completed N200
analysis. Growing N400 results are excluded. ELF files are identified by
their exact SHA256 rather than included; source and build evidence remain
available in this archive and the earlier execution proofs.

[Member manifest](manifest.json) and [part checksums](archives.json) bind
all original bytes. Every part is stored as an ordinary100644 Git blob;
the D-drive originals remain in place, while the sparse working tree avoids
a duplicate copy. [Index readback](index-staging.json) independently verifies
all44 archived blobs against those checksums before the local commit.

Related evidence: [coarse N200/N400 pair](../womersley-s96-native-coarse-time-pair-2026-11-08/README.md),
[fine execution proof](../womersley-s96-fine-execution-screen-2026-11-08/README.md).
Archive completion and local commits do not constitute full physical
qualification, public upload or a pull request.
