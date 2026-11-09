> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pinned native one/two-rank record audit

Base `1374b625b829f03c1d37fbc167cf390bc3aa8bb4`; exact changed source and
test SHA values are in [definition.json](definition.json), raw tests and five
immutable native files in the archive.28files, one2,781,956-byte part, with
full member SHA readback. Ordinary Git blob staging is recorded separately.

Actually ran19 `test_svfsi*.py` and8 `test_pressure_tube_audit.py` checks,
then decoded actual two-rank startup20/2600/2700 and serial5600/6000 records.
[Report](report.json) explicitly sets actual_parallel_restart_validated=false.

Pinned upstream INITIALIZE.f chooses the MPI maximum payload as direct RECL.
Here both ranks use709864bytes, but local node counts are4225/3600. Rank1
has604864 meaningful bytes and105000 bytes of non-state padding. The reader
checks all finite histories, shared step/time/equation norms, maximum payload
equal to RECL and complete per-rank provenance. It does not demand identical
elapsed times or interpret padding as numerical values. The full-file SHA
still covers every stored byte. Serial provenance remains unchanged.

No solver or C++ behavior changed. Real parallel recovery, changed linear
backend and full production qualification require their own evidence.
