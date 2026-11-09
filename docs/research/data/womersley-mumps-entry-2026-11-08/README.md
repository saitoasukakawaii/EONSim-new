> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Explicit MUMPS study entry and complete-job resource control

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

The study now accepts explicit `--mumps`, mutually exclusive with `--schur`.
`--chord` requires one of these explicit paths. MUMPS options are frozen in
the study definition; resuming with a different solver policy is rejected
before mutation. Defaults and the C++ numerical kernels are unchanged.
The increment is based on `5091b68`; the exact tested study-script SHA256 is
`a84c28bcf23916fc4e0415ae8f0c498909d8159d002710e090e571d915376055`.

Actual commands, run from the repository root:

```text
/usr/bin/python3 -u build/prod48-20261107/check-womersley-mumps.py
/usr/bin/python3 -u build/prod48-20261107/check-bounded-cgroup-job.py
```

The [CLI results](cli-summary.json) use locked PETSc3.23.7 Release binary
`e88ba712…`, real1/2 ranks, seed6/1/2, alpha2,N4 and16 accepted steps.
All13 stored states and65/130 HDF datasets were compared. Unchanged default
direct results were reused from the earlier segmented-execution evidence,
not rerun. MUMPS versus that default differed by at most5.204170427930421e-18;
segmented MUMPS/chord versus MUMPS by at most1.613639777353626e-14.
V4 clocks were exactly equal. Changed-policy resumes were rejected without
altering existing files; completed resumes changed nothing. Three invalid
option combinations were rejected before creating a study directory.
These tiny cases shared CPU17 at low scheduling priority and support no
performance or production-accuracy claim. No C++ rebuild/full suite or
historical PETSc run was required for this CLI-only increment.

[Resource capability checks](memory-control-summary.json) verified a64MiB
private cgroup limit by actual allocation failure, zero permitted swap,
and inherited limits in actual2-rank MPI. The subsequent
[runner checks](runner-summary.json) cover normal completion and timeout
with a separate-session child ignoring SIGINT/SIGTERM. The entire owned
cgroup was empty after escalation, the original timeout propagated, and
an unrelated process remained alive. This scope includes nested sessions,
which a single Linux session identifier cannot contain.

The independent [fine-grid screen report](fine-screen-report.json) retains
the original three-step direct/Schur comparison after accepted step453:
181.986027972 versus353.399878907 seconds, a48.5042% local wall-time reduction.
Maximum final field difference was5.296499350215811e-12; all final HDF
histories met2e-9, and legacy v3 clocks met their1e-12 tolerance. The frozen
candidate binary was `162059c0…`, four ranks on four guest-reported core groups,
367620 unknowns and21295120 nonzeros. The observed cgroup peak was
10,821,701,632 bytes under a14GiB cap and swap0. Original processes resumed
at UTC01:28:58. This screen only made the candidate eligible for a separate
accepted-state handoff; it did not automatically adopt the policy. Full
fine-screen fields are retained in their immutable original directory and
queued for separate archival; this package contains its completed report.
The earlier3.5GiB-per-rank virtual-address-space failure remains a distinct,
failed experiment and is not relabeled.

[331 files](manifest.json) were hashed and verified by archive readback.
The50,220-byte archive SHA256 is
`e986f07bf89c143b942747fb94d6f63dd37ed2a1671f89e88816d35341fcc902`.
[Metadata](archives.json) identifies four omitted copied ELF files by exact
hash. Analytic accuracy, periodicity and all independent error budgets
remain separate acceptance conditions.

Later at UTC01:50:05, a separate460→463 restart was compared with the
original uninterrupted463 state. [All histories passed](later-handoff-probe.json),
with maximum4.42640715747622e-12 and zero observed clock difference; the
legacy clock contract remains approximate. [Adoption](later-handoff-adoption.json)
then explicitly created the MUMPS continuation. The old numerical family
[exited completely](later-handoff-cleanup.json), and the two unused old
waiters were cancelled. These [additional completed receipts](later-handoff-receipts.json)
have separate source hashes and are not counted in the331-file archive.
The full handoff fields and immutable inputs are queued for separate capture.
