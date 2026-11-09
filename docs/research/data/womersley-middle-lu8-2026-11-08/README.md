> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Middle-grid LU screen, independent review and accepted480 adoption

On the same alpha2 S48 level1 N200 accepted480 state, three configurations
computed eight steps481–488. The original vector/Schur Release binary is
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`;
the candidate MUMPS Release binary is
`f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`.
The default path and explicit LU window8 use the same candidate binary.

| Configuration | Whole-job seconds | Actual LU factorizations | Peak cgroup bytes |
|---|---:|---:|---:|
| Original vector/Schur/chord | 500.678313912 | Not a direct-LU configuration | 798,986,240 |
| New default MUMPS/chord | 101.535775972 | 8 | 823,713,792 |
| New MUMPS/chord/window8 | 45.120052223 | 1 | 811,597,824 |

The [report](report.json) gives candidate ratios0.09011784806587429 to
the original vector baseline and0.4443759038729575 to the new default,
both below the predeclared0.9 selection threshold. Four MPI ranks share
WSL CPU21 with MPI idle-yield, PETSc3.23.7 and single-thread libraries.
Other project jobs run concurrently. This is one local execution screen,
without repeated timing statistics, host-core isolation or scalability claims.

Each comparison checks160 HDF datasets across all eight states/four ranks:

| Comparison | Maximum current/history difference | Clock check |
|---|---:|---|
| Original continuous vs restarted vector | 3.469446951953614e-17 | Legacy difference4.440892098500626e-16 |
| Restarted vector vs new default | 4.6010053406098095e-12 | Legacy difference0 |
| New default vs new cached | 4.85722573273506e-17 | Exact v4 clock/time metadata |
| Original continuous vs new cached | 4.6010070753332855e-12 | Legacy difference4.440892098500626e-16 |

All field/history checks pass2e-9; legacy clock checks pass1e-12 without
claiming to reconstruct missing compensation. Solver reasons are positive.
Each mode has a private2GiB/swap0 scope and900-second timeout,10GiB
available-memory admission and8GiB running guard. No memory-limit/OOM
events occurred. All scopes were empty before the original six numerical
processes [resumed](resume.json) at UTC04:56:02.

The [independent review](handoff-review.json) rereads all640 compared
datasets, profiles, resource receipts and seed hashes. It binds the decision
to report SHA256
`4c978283c4e436299f7ccfe801625ca4776c76cac3c136646dc2e2bc07d296f0`.
The screen's `adopted:false` remains correct: separate controller25664
[adopted](adoption.json) at04:59:26, from480 through1200, so all sampled
cycles4–6 use the candidate. Original7509/7603/24479/24482–24485 are retired;
their complete partial trajectory through491 remains archived.

Unused fine N400 waiter25369 was explicitly cancelled before numerical work.
Successor25665 waits for fine25368 to complete and for adopted middle25664;
it requires the middle's completed1200 receipt before spatial/budget analysis.
The [controller checks](controller-checks.json) execute five extracted
admission cases, verify the middle wait is outside CPU/memory locks and
confirm the numerical budget tail is byte-identical to its predecessor.
No threshold or fallback was changed. Frozen source hashes:

- Screen `faa6d713dc6f113de6ba70e11b8c93743d4dbee95b9556f6f8d68123488fe11f`.
- Handoff `6b95a64b116406f68af2b3e977307a4364ea1888f193ddc3e6138040ad65d855`.
- N400 queue `1ccca6dffe4ab3887657e5fa6c320a3ae317923ec9050583270081ea834e50a9`.

Commands use `/usr/bin/python3 build/prod48-20261107/` followed by
`screen-alpha2-middle-lu8.py`, `handoff-womersley-middle-lu8-m480.py`, and
`queue-womersley-time400-lu8-middle.py --alpha 2`, respectively. Original
commands, frozen source and the actual five-case check are retained.

[833 files](manifest.json) were captured at source checkpoint2367903 and
read back from three48,559,380-byte parts; [metadata](archives.json) records
six omitted ELF copies by hash. Capture completed UTC05:19:11. Complete
screen/reference/old partial trajectory and immutable new handoff evidence
are included; growing new output is excluded. Analytic, periodic and
time/tail/sampling gates still require the complete long studies.
