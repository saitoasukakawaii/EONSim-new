> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Optional retained LU preconditioner: correctness evidence

Baseline d0f9bb3 plus the exact [source hashes](summary.json) implements a
default-off MUMPS factor cache. Only its LU preconditioner survives across
successful calls; SNES/KSP callbacks and physical history do not. FGMRES
solves the current operator and original final field acceptance remains.
The fluid application option is `-fluid_lu_pc_reuse_window`; the study
entry requires explicit `--mumps --lu-reuse-window`. See
[supported options and invalidation](../../../development/DOF_AND_PC_GROUPING.md).

The Release executable SHA256 is
`f7bf9f3d767968dd2b04950c687a94393c46ee8c6a65e0a6d37cdff09c9c10e2`;
Debug is `ebf546ab61484fc835aea878e481907f3942236bc516e13824883339483983a9`.
Both use the repository's locked PETSc3.23.7. Actual MPI checks ran with
single-thread libraries on shared CPU17. Their elapsed times are not a
performance comparison. Exact selected-test JSON, build/runtime provenance,
CTest commands/output, frozen source, input meshes and complete HDF states
are in the archive.

The frozen validation controllers execute
`bash scripts/cloud/run.sh 3.23.7 <mode> explicit <prefix> <tests.json>`.
The selected ten checks are `lu_reuse_mpi1`, `lu_reuse_mpi2`,
`lu_reuse_mpi4`, `fluid_lu_reuse`, `nonlinear_acceptance`,
`nonlinear_acceptance_mpi`, `coo_jacobian_mpi4`, `pc_plan_mpi2`,
`schur_vector_mpi2` and `fluid_verification`.

| Attempt | Result | Interpretation |
|---|---|---|
| Initial Release | 7 passed, 3 LU-count failures | Extra PC reference did not protect its factors from SNESReset |
| Corrected Release | 4 new LU checks passed | Actual factor counts now obey the policy; separate HDF audit then rejected duplicate old/new step generations |
| Isolated test directories | Release fluid check passed; Debug10/10 passed | Complete histories passed; unaffected Release tests explicitly reuse earlier passing evidence |

Independent PETSc `MatLUFactorNum` events give1/0/0/1 factorizations across
four changing-operator solves with window3, for AIJ and COO on1/2/4 ranks.
The tests include an empty owner, exact initial state, one-rank options
change, incompatible policy, rejected PREONLY/lag settings, callback
failure and fresh recovery. Retaining an object or obtaining equal fields
alone would not prove actual factor reuse; the first failed attempt shows why.

For each build, actual eight-step variable-BDF2 direct/cache runs and
five-step restarted tails on1/2/4 ranks compare455 HDF datasets. Maximum
field/history difference is1.0401913569857077e-12 against2e-9; clocks and
time metadata are exact. The fresh per-invocation directory keeps repeated
test runs separate without deleting previous attempts.

The frozen `check-womersley-lu-reuse.py` additionally runs complete tiny
studies on1/2 ranks, including natural-cycle segmentation. Its13 saved
states contain65/130 datasets; maximum difference1.1719791803699309e-14,
clocks exact. Changing window during resume is rejected without mutation;
resuming a completed study changes no files. Negative/oversized windows
and implicit MUMPS selection are rejected. `tests/test_ci_selection.py`
passed26 checks; the observed command/output and source hashes are recorded.

[2,859 files](manifest.json) were read back and hash-verified in one
753,592-byte archive. [Metadata](archives.json) identifies six omitted ELF
copies by hash and records capture d0f9bb3. Both failures remain available.
No fine-grid performance, production adoption, full-suite, old-PETSc or
long-period physical qualification is claimed by this evidence.
