> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Optional velocity block metadata: correctness and bounded fine-grid screen

Resource-label clarification (2026-11-08): CPU indices and core groups are
those reported inside WSL. [Host/guest observations](../execution-topology-2026-11-08/README.md)
do not establish host physical-core pinning; frozen raw evidence is unchanged.

The optional implementation after054b64a sets block size3 on the standalone
Tet4/P1 velocity Schur submatrix after collective semantic/ownership checks.
It is explicitly enabled by `-schur_pc -schur_velocity_block3`; default
behavior, the physical matrix, numbering and stopping criteria are retained.
FSI/semantic recipes and incomplete or rank-inconsistent metadata are rejected.
See the [user-facing contract](../../../development/DOF_AND_PC_GROUPING.md).

[967 source files](manifest.json) were read back from seven bounded archives,
with byte counts and hashes in [archives.json](archives.json). Exact executable
hashes are retained separately. Capture includes the original malformed
selection-list attempt, the Release timeout, successful retries, original
controllers, source snapshots, all short-run fields and the earlier GAMG
coarsening screen. These failures were not overwritten or counted as passes.

## Actually executed checks

The pinned PETSc3.23.7 repository entry was invoked as
`bash scripts/cloud/run.sh 3.23.7 MODE explicit /home/tfblab633/EONSim/.cloud TESTS_JSON`.
Commands, exact lists, build evidence and test logs are archived. Debug newly
passes six checks: `schur_vector_mpi1`, `schur_vector_mpi2`,
`schur_vector_mpi4`, `schur_vector_verification`, `schur_verification`,
`solver_failures_mpi`. Four-rank metadata tests deliberately include two
empty owners and independently check original operator entries/order, root
and pressure block sizes, manufactured solution and true residual. Local
semantic faults and mismatched options reject collectively, then recover
using the same KSP object.

The actual transient small tube runs1/2/4rank against direct LU. Its third-step
maximum nodal field difference is1.01170e-13; all three accepted steps have
positive SNES/KSP reasons, and net flux is below1e-10. An option used without
Schur rejects before solving. This is a three-step check, not a long-cycle
accuracy qualification.

Release originally passed five of six checks; the legacy four-rank Schur
regression timed out at its unchanged100-second limit while four MPI ranks
shared one guest-reported core group with default idle spinning. The identical-source
retry sets `OMPI_MCA_mpi_yield_when_idle=1` and passes that failed check in
16.7033seconds. [Combined Release evidence](combined-release-evidence.json)
checks exact source equality and identifies the five reused successes plus
the one new success. Debug's six checks use the same idle-yield setting.
Neither numerical tolerance nor test timeout was relaxed. This is resource
configuration for oversubscribed correctness testing, not a general speed claim.

Six additional real completed-study CLI checks preserve legacy no-op resume
and reject implicit COO/chord/block3 changes or unsupported flag combinations
without launching a solver. The26 incremental-selection checks pass after
adding the nonlinear-system mapping. These Python-only changes occur after
the C++ builds; the source snapshots distinguish them. Unrelated full-suite
and historical PETSc-version tests were not rerun.

## Same accepted state, final physical field comparison

Candidate Release SHA256:
`162059c0a8ef8b24598a85bf2fc956bfc481d74b7f102b0e5390d652bce2958c`.
Both modes start from the exact original alpha2/level2/N200 checkpoint200,
take steps201–203, retain chord lag=-2 and the same stopping tolerances, and
use four ranks sharing CPU22/23, one guest-reported core group. MPI idle-yield is enabled.
The [report](report.json) binds checkpoint, binary, source, partition and
command provenance. Field differences below are at the third-step final
state; positive convergence and accepted clocks are checked on all three steps.

| Mode | Total seconds | Maximum final-field difference | Linear iterations per step |
|---|---:|---:|---|
| Candidate, default scalar metadata | 733.265 | 0 | 168 /168 /168 |
| Candidate, velocity block3 | 539.742 | 5.08531e-12 | 94 /94 /95 |

Both pass the predeclared2e-9 field limit. Against the separately retained
b072 final-state baseline, differences are5.63786e-18 and5.08531e-12.
The old run is reused only for fields, never for a cross-resource timing ratio.
The same-session candidate comparison gives26.392% lower local wall time,
passing its predeclared10% selection rule. No running study was silently
modified; a separate checkpoint400 four-core confirmation is scheduled before
any explicit long continuation. That later confirmation is not part of this
completed evidence package.

Peak reported rank RSS increases from992313344 to1063612416 bytes; the
observed reduction in wall time does not imply a memory reduction.

The earlier frozen-b072 GAMG screen used four guest-reported core groups10–17:
standard384.059s, pressure-no-aggressive375.520s, both-no-aggressive386.772s.
Final fields pass2e-9, but no candidate reached the selection benefit, so it
was not adopted. Its timings must not be compared directly with the
single-physical-core block3 screen. The original alpha1 parent was resumed
normally at20:22:49UTC, with the recovery receipt preserved.

No MPI scaling claim, full Womersley qualification, FSI support for block3,
or universal preconditioner improvement follows from these bounded checks.
