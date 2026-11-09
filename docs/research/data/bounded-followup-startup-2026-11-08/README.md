> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bounded follow-up startup receipts

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

At base `c509af0`, two separately frozen follow-ups were started. These
receipts establish preparation and resource coordination, not numerical
success. The original long studies continue unchanged.

The four-rank fine Womersley diagnostic waits for alpha1's middle study
and its analysis to finish naturally. It holds `mpi-option-probe.lock`,
so the existing alpha1 fine screen waits without competing for the same
four guest-reported core groups (logical CPUs10–17). It then compares MUMPS/chord
with Schur/vector/chord at the same complete step400 checkpoint, using
the same frozen binary, mesh, case and three accepted steps401–403.
Each mode has a900s limit and each rank a3.5GiB address-space limit.
Available memory must initially exceed16GiB; the owned process group is
stopped if it falls below8GiB. A failed candidate skips baseline repetition.
Positive convergence, final field difference below2e-9 and at least10%
lower local wall time are required even to become eligible for a separate
handoff review. This diagnostic does not adopt a production policy.

The independent mesh-nu0 reference budget watcher waits without an
analysis lock for all three S24 family members. Its `study` and `analyze`
functions are structurally identical to the existing S24 budget auditor.
It checks physical input hashes and the separate mesh-nu0 export identity,
then retains every periodic/convergence/quality prerequisite and every
field's strict10% space-denominator requirement. The later same-fine-mesh
cross-program comparison is separate. Original mesh-nu.3 failures and
the original EONSim budget queue remain unchanged.

Actual launches used WSL Ubuntu24.04 `/usr/bin/python3`:

```text
python3 build/prod48-20261107/screen-womersley-fine-direct.py
python3 build/prod48-20261107/analyze-reference-nu0-s24-budgets.py
```

Their startup PIDs were20915 and20925, sessions60954 and50721. Both were
waiting at capture. [Source checks](checks.json) cover syntax and the
unchanged budget functions only; no numerical test was rerun or claimed.
The archive contains frozen controllers/readers, process identities,
copied step400 seed, source definitions and startup reports.

[All30 files](manifest.json) were read back and hashed. The single
4,635,864-byte archive has SHA256
`3ecbe53db6f239de479663f5a656562a3b54a8815806045592516c93f38998da`.
[Archive metadata](archives.json) records exact paths and copied receipts.
Neither follow-up nor the complete PROD-02 milestone has passed yet.
