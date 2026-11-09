> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed live-reference prefixes at 2026-11-09 00:55 UTC

These are immutable prefixes of four still-running studies, selected below the
highest native checkpoint. Every final FS/MS equation row in each selected
segment satisfies its unchanged strict relative tolerance of1e-10. No live log,
native state, input, producer or frozen controller was modified.

| Study | Audited continuation steps | Full-load steps in this prefix | Worst FS / MS ratio |
|---|---:|---:|---:|
| S24 fine N400 mesh ν=.3 | 4001–6800 (2800) | 400 | 6.2e-12 / 4.2e-11 |
| S24 fine N400 mesh ν=0 | 5001–8300 (3300) | 1900 | 6.3e-12 / 4.1e-11 |
| S24 fine N200 mesh ν=.3 | 1101–3600 (2500) | 400 | 1.1e-11 / 3.6e-11 |
| S24 fine N200 mesh ν=0 | 601–1500 (900) | 0 | 3.2e-12 / 1.1e-11 |

The maximum final iteration count is3 for both equations in all four segments.
The first three studies have passed the prescribed16-cycle load ramp; the last
one is still in that ramp. The reported worst ratios include the whole listed
continuation segment, not only its full-load subset. Solid Poisson ratio remains
.3 in all studies; ν in the labels denotes the independent mesh equation.

[summary.json](summary.json) contains the original status snapshots, exact segment
counts, native1/2rank metadata and hashes. Each archived prefix has its original
log bytes, final native record, complete convergence report and input hash map.
All60 exported immutable input files are included, including pressure histories,
domain meshes, input decks, native seeds and export manifests. The inherited
restart provenance still binds the separately archived original handoff evidence.
This is not a replacement for each full1..6400/12800 restart-chain audit, complete
sampled fields, periodicity, physical observables or error budgets.

The [archive manifest](archives.json) records94 verified source files in6 parts,
7,656,276B. [index-staging.json](index-staging.json) verifies every complete part
as ordinary100644 Git bytes; D originals are retained. Large parts are omitted
from this sparse working tree, not omitted from the Git commit.

[static-preparation.json](static-preparation.json) also binds an unexecuted L24
extension plan reviewer and read-only progress readers. No extension plan,
execution-review record, new production status or adoption exists at this capture.
That preparation must wait for the complete210-field-pair/11-native-pair proof
and its separate raw review. It cannot convert the original L24 periodic failure
into a pass. No numerical rerun, new solver build, upload or complete qualification
is claimed by this archive.
