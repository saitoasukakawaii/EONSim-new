> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Elastic-tube readers: manufactured data checks

**No solver was executed for these checks. These are synthetic fixtures, not
elastic tube simulation results or physical qualification.** Source is local
commit `2189a8c9589add9376c060ef4e4c2e871fdb0c60`. Python's system environment
with VTK9.6.1 is separate from the locked PETSc solver environment.

The first helper writes two physical domains with distinct nonzero solid/ALE
displacements. It uses standard VTK to read the compressed reference layout,
and the EONSim reader to read deformed coordinates, large IDs and unused points.
All physical field values round-trip exactly; maximum reference-coordinate
difference is `1.1102230246251565e-16`. A deliberately imposed interface
displacement mismatch of `.004` is recovered as `.004000000000000002`.
The fixture also violates cap constraints deliberately; those are reported,
not accepted as a physical solution.

The legacy fixture contains two arrays named Displacement. VTK emitted
`Another point data array named Displacement already exists. Ignoring.`
and returned only Velocity, Pressure and one Displacement array. The new
auditor rejects it because the two unambiguous physical fields are missing.
The aliased fixture retains both fields, and each is used only on its domain.

The second helper creates 48 snapshots over three cycles, 16 phases each,
with prescribed zero motion and spatially uniform `.02+.01*sin(t)` pressure.
Both complete analysis paths recover mean `.02`, amplitude
`.010000000000000016`, phase `-5.79e-14` degrees, zero volume-budget defect
and zero kinematic/mass defects. Periodicity is recovered for the manufactured
fields. The first-stage clocks remain distinct: EONSim's BE startup uses dt,
the reference alpha convention uses 2dt/3. This fixture does not solve the
elastic equations and does not verify either program's response to loading.

## Reproduce

Run each retained helper with the separate VTK-capable Python and fresh work
directories; `--repo` points to this source checkout:

```sh
/usr/bin/python3 original-reader-check.py --repo /path/to/repo --work /new/reader
/usr/bin/python3 original-pipeline-check.py --repo /path/to/repo --work /new/pipeline
```

The actual commands used helpers under `build/prod48-20261107/` and work
directories `/home/tfblab633/EONSim-prod48-20261107/pressure-reader-check-2189a8c`
and `pressure-pipeline-check-2189a8c`. Original helper copies, generated cases,
meshes, all synthetic snapshots and analysis results are retained. Both archives
were reopened and all **185 files** SHA256-verified. Manifests and archive
hashes are provided. No numerical rerun, performance claim, upload or PR.

The actual coupled runs and their audits are queued separately and remain
pending. See the [field definitions and gates](../../../development/PRESSURE_TUBE_FIELD_AUDIT.md).
