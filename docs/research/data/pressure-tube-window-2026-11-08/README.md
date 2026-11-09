> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Late-cycle windows with a real preceding state

Increment after2eabb47; exact changed analyzer/exporter/comparison files are
archived with hashes. The repository commit containing this directory records
the implementation. No actual long-tail physical result was complete at capture.

`audit_pressure_tube.py --first-step` defaults to1. Later windows must start a
cycle, contain at least three full cycles and supply the actual preceding
field. That state initializes alpha stages and the volume budget. Gaps,
duplicates, unaligned/short windows and field comparisons outside the audited
window are rejected. Reports name their window and make no unstored warmup
field claim. The reference `--output-start-step` changes saving only; pinned
MAIN.f uses cTS>=saveATS. Include the audit predecessor. Four exporter tests
passed; the receipt explicitly identifies the observed tool result provenance.

A64-step/16phase manufactured history has zero velocity, known sinusoidal
uniform pressure and1% static affine dilation. Window17..64 from real step16
matches full-history rows/harmonics exactly, with zero window volume defect.
Wrongly initializing with reference volume would give a defect greater than1.
The dilation deliberately violates cap constraints, and both readers correctly
fail kinematics (maximum.12059850745); synthetic markers forbid physical passes.
Eleven window, predecessor, phase/count, duplicate, range and comparison
checks passed. The first harness passed integer-key dicts to a JSON comparator
and hit KeyError3. That attempt/script is preserved; attempt2 reads serialized
reports. No PDE rerun or gate change was made for this harness error.

Actual commands: `check-pressure-pipeline.py --repo . --work /new/fixture
--cycles 4 --first-step 17 --dilation .01`, then `check-pressure-window.py`
(both under build/prod48-20261107, using /usr/bin/python3), plus
`python tests/test_svfsi_export.py`. Helpers retain original work paths; use
fresh destinations when replaying. All551raw files were read back against
`manifest.json`; archive/copy hashes are in `archives.json`.

The separate real controller preserves the600-step state, freezes analysis
sources and runs to128warmup+4sample cycles, then the pinned reference, keeping
actual step12800. It was only started at capture; no periodic success implied.
The resource receipt proves primary rank affinity0-1/2-3/4-5/6-7 on24logical
CPUs/32GiB with about28GiB available. One separately locked serial job is fixed
toCPU8 and checks memory/affinity. This supersedes the earlier one-job scheduling
choice without duplicating the main study or making performance claims.
