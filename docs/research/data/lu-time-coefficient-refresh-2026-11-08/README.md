> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Refresh retained LU when the integration coefficient changes

The [rejected startup screen](../rounder-mesh-startup-screen-2026-11-08/README.md)
showed that keeping one BE-startup factor through32 BDF2 steps reduced the
factor count but increased total cost. Its first step took1 linear iteration,
whereas the following steps used11–12. With window8, a later refreshed factor
reduced subsequent counts to2–3. FGMRES still solved each current operator;
this was an execution-cost issue, not proof of an incorrect accepted field.

The patch afterd844e40 adds an explicit refresh request to
`NonlinearSystem::solve`. The existing collective cache decision discards the
old factor if any rank requests refresh, including an empty owner. The fluid
driver requests it whenever its effective integration time differs from that
of the previous accepted solve. This covers BE→BDF2 startup, variable steps,
event restarts and generalized-alpha startup. Equality is deliberately exact:
an altered coefficient conservatively starts a new window, including a
truncated final increment. The current Jacobian/residual, acceptance gates
and default disabled policy are unchanged. Cached factors and the last
coefficient are execution state; a restarted solver starts fresh.

Exact [source hashes](source.json), frozen source copies, commands, test
outputs, logs and complete HDF states are archived. The actual invocation was
`/usr/bin/python3 build/prod48-20261107/validate-lu-time-refresh.py`, which ran
`bash scripts/cloud/run.sh 3.23.7 MODE explicit /home/tfblab633/EONSim/.cloud PLAN`
for Release and Debug with these six tests:

- `lu_reuse_mpi1`, `lu_reuse_mpi2`, `lu_reuse_mpi4`;
- `fluid_lu_reuse`, `nonlinear_acceptance_mpi`, `fluid_verification`.

Both builds passed6/6 at UTC06:22:09 on2026-11-08. AIJ/COO tests verify
actual PETSc LU events, one-rank refresh on an empty owner, later reuse,
options/window invalidation, and failure recovery. The variable8-step fluid
schedule observes6 factors; constant10-step startup with window32 observes2.
Two-rank event and generalized-alpha cases observe4 and2 factors respectively.
Each is compared with a fresh default solve. Tests use binary-exact increments
for the factor-count schedule; this isolates intended coefficient transitions
from an incidental final-time subtraction.

Independent [Release](release-histories.json) and [Debug](debug-histories.json)
audits each check1,005 HDF datasets over1/2/4 ranks: complete current/history
fields, variable-step restart, constant startup, event and alpha cases.
Maximum differences are1.465017343549313e-14 and1.4650607116362124e-14,
below2e-9; v4 clocks and time metadata are exact. Restart field histories
also pass. These are correctness checks, not timing or scalability evidence.

[Release resource evidence](release.resource.json) and
[Debug resource evidence](debug.resource.json) record2GiB/swap0 scopes on
CPU21, observed peaks376,479,744/370,085,888 bytes, no memory events, and
empty scopes after completion. The frozen Release executable is
`60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07`;
Debug is`c2c64a20b339bfcb5e8511c84df0ecddabad964832964a1e26dae02eb9babe20`.
Existing f7 production processes retain their own frozen binaries.

The [summary](summary.json) records completion. `capture-lu-time-refresh-validation.py`
completed UTC06:29:36: [3,001 verified files](manifest.json),
[one565,360-byte part](archives.json), with ELF binaries represented by exact
hashes and source/build evidence. Native Python3.13 then ran
`stage-external-archives.py lu-time-coefficient-refresh-2026-11-08`;
[full Git-index readback](index-staging.json) verifies the complete ordinary
blob, sparse flag and retained D source. No performance benefit or production
adoption is claimed by this validation archive; the
[completed independent startup cost screen](../lu-refresh-startup-cost-2026-11-08/README.md)
is separate evidence. No push or PR has occurred.
