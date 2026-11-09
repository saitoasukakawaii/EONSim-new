> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed startup checks and dated queue snapshots

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

Atf0422d0, [390 original files](manifest.json) were read back from one3403720-byte
archive. [Hashes and capture details](archives.json) include immutable scripts,
input/partition provenance and ELF identities. [The snapshot](summary.json)
records actual states at capture time; running/waiting jobs are not complete.

S12/level0/N400 pressure-tube five-step preflight passes for1/2/4ranks with
frozen b072 and identical MUMPS/chord options. Full12800-step trajectories,
three saved cycles and rank2 restart from12400 are still running. The first
controller failed during import because its frozen dependencies omitted
`cases/fsi/generate_tube.py`; the complete failed directory is retained and
attempt2 includes that module. No numerical tolerance was changed.

The [alpha2 middle N200 three-step comparison](preflight.json) passes at
final maximum nodal difference1.716951e-12, below2e-9, with positive reasons
and exact accepted clocks. Original b072/default Schur and candidate162059c0
with chord/block3 take124.325/105.634s on CPU21, which shares a guest-reported core group
with ongoing reference20. These are local observations, not scaling claims.
Only the final fields are compared. The six-cycle study has just started.

Its first attempt was rejected for zero fluid checkpoint cadence, before
solving. That failure is preserved. The same zero value was then identified
in the pending alpha2 fine400 probe. Waiting controller6906 was cancelled
before any probe ran; its finally block resumed the same Python631. Original
MPI632 and ranks635–638 remained running with identical process identities.
Separately frozen controller7542, with positive probe cadence3, again holds
only631 until the natural400 endpoint. Replacement/resume receipts are archived.

Alpha1 controller7639 holds only outer Python1180 while its middle-study child
5422 continues. A future fine-grid screen must meet both2e-9 final field and
10% local cost criteria before any explicit new fine study. Otherwise the old
parent resumes. S24 budget controller7593 waits for complete coarseN400,
fineN200 and fineN400 producer receipts for each solver. Its five-field10%
budget checks preserve all convergence/periodic/quality prerequisites.

Live long-run logs/checkpoints are excluded. Failed startup, planned controller
replacement, bounded preflight, long execution and physical qualification are
different states; this capture does not claim the latter two are complete.
