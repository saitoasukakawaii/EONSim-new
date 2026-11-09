> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Natural-cycle segmentation of long Womersley execution

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

The study CLI's86400-second limit is per solver invocation. A legal CLI
value alone does not ensure a fine-mesh segment can finish in that time.
An explicit `--cycles-per-solve N` now ends each invocation at an accepted
whole-cycle checkpoint. The physical final time, problem definition,
solver options and sampling cadence stay fixed. Without the option, the
original two-stage behavior remains. Each attempt receipt records the
explicit policy; it does not imply physical qualification.

This script increment is based on `86bbdac`. Exact source hashes are in
the [v4 result](v4-summary.json) and [legacy result](legacy-summary.json).
The modified study script has SHA256
`ff9d8ef039bfc9c66907d56ee2ea608d123c258bbcaaa871aff45a8fb549da43`.

Two independent real checks used the already frozen binaries:

- V4 `e88ba712…`: seed6/1/2, default direct solver,1/2 ranks. Continuous
  sampling versus stops4/8/12/16 had exactly identical clocks, fields
  and histories at all13 stored states, comparing65/130 datasets.
- Legacy v3 `162059c0…`: seed12/1/4, Schur/chord/velocity-block3,1/2 ranks.
  Maximum field/history differences were0 and6.938893903907228e-18.
  The small fixture's clocks also happened to agree exactly, but legacy
  clocks were checked against1e-12, not assigned a new exact guarantee.
  The original production v3 failure remains documented separately.

Both used alpha2,N4,four total cycles,one warmup cycle and all four
phases. They check execution equivalence, not analytic accuracy or
periodicity. All cases retain final step16, avoiding a change in terminal
step clipping. A completed-study resume creates no extra attempt and
does not change the receipt. Invalid segment counts0 and-1 are rejected
before creating the study directory. The physical definitions and mesh
hashes match within each binary's comparison.

Actual controllers, commands, complete inputs, logs, HDF histories and
outputs are archived. They were run from the repository root with:

```text
/usr/bin/python3 -u build/prod48-20261107/check-womersley-segments.py
/usr/bin/python3 -u build/prod48-20261107/check-womersley-legacy-segments.py
```

Each takes `reference-diagnostic.lock` and usesCPU23, single-thread
libraries and idle-yield MPI. The shared guest-reported core group is suitable only
for correctness here. No rebuild or repetition of the eight unaffected
Debug/Release checks was necessary.

[604 files](manifest.json) were verified by archive readback. The97,592-byte
archive has SHA256
`83a028381145d63ca1841b9084588309b6c59622c4ac416af31fde482231cd83`.
[Metadata](archives.json) records eight omitted copied ELF hashes.
At this checkpoint no running long controller had been changed or
cancelled. Adoption requires a separately frozen successor or a verified
accepted-state handoff; the existing long numerical work continues.
