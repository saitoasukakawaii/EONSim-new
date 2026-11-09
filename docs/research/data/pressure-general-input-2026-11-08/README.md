> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Fixed-step General pressure input

Source checkpoint0b9e980 plus the exact modified Python sources copied here;
individual hashes are in archives.json. Reference svFSI is unchanged commit
7bdb74cdd517310d6bf32c0bb7d42072aeac8658, built with the system MPI runtime.
All288 archived files were read back and SHA256 verified. The binary is named
by hash in provenance, not redistributed. This is input/analysis validation,
not coupled elastic qualification or a performance comparison.

| Actual100-step input | Maximum velocity | Endpoint recurrence error | Stage load error |
| --- | ---: | ---: | ---: |
| General sinusoid, no ramp | 2.801e-15 | 4.188e-13 | 1.157e-13 |
| General sinusoid, half-cycle quintic ramp | 2.524e-15 | 4.050e-13 | 1.171e-13 |

Both satisfy the unchanged1e-9 discrete uniform-pressure gate, including the
final endpoint. Pressure spans are4.136e-13/3.991e-13. The input has one extra
future knot, so IGBC's MOD(time,last_time) does not wrap at the simulation end.
General scalar Neumann values already contain the pressure minus sign;
SETBCNEUL only adds that sign automatically for the Fourier/constant paths.
Stage-time offsets remain derived from alpha_f, never fitted from results.

Commands, logs, input meshes, boundary tables, every VTU, analyzed rows and
the executed controller are in uniform-input.tar.xz. Two bounded serial jobs
used CPU18 after actual affinity/resource checks; concurrent studies were on
other CPUs. No extra reference source or physical operator was modified.

The actual targeted unit runs passed5 exporter and7 auditor checks. Their
receipts identify the commands, timings and exact source hashes; they are
explicitly labeled execution receipts rather than raw subprocess logs.
Six additional manufactured checks verify explicit post-ramp same-solver
comparison, exact zero difference, and rejection of other physical changes,
cross-solver startup comparison and cycles intersecting the ramp. Manufacturing
outputs remain marked synthetic and cannot qualify a physical solver.

```sh
/usr/bin/python3 tests/test_svfsi_export.py
/usr/bin/python3 tests/test_pressure_tube_audit.py
/usr/bin/python3 build/prod48-20261107/check-general-pressure.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /usr/bin/python3 build/prod48-20261107/check-pressure-startup.py
```

Default export still rejects a startup ramp unless --general-pressure is
explicit. General tables reproduce this fixed-step law at the times actually
read; no claim is made about a different/adaptive time grid. Coupled startup
experiments and their long-tail equivalence are separate pending studies.
