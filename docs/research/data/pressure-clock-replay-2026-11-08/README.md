> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Repaired production checkpoint clock replay

This completed two-rank, locked PETSc3.23.7 Release replay verifies the v4
clock repair introduced at86bbdac. The tested executable SHA256 is
`e88ba71276b688ee0c5364883e61396899944a2629317a1fd1c8c420f5b11ed2`.
[Execution provenance](execution-definition.json) identifies its source and
the preceding eight Debug/eight Release checks. The frozen production
controller, exact MPI commands, physical inputs, meshes, logs, VTU fields
and HDF histories are in the archives; [manifest](manifest.json) records
their individual hashes. Capture checkpoint5091b68 identifies the archive
operation, not a different numerical executable.

Both trajectories start from the same legacy11600 state with an explicit
zero for the unavailable old clock correction. The continuous trajectory
runs to12800; the restart trajectory resumes a new v4 checkpoint at12400.
Across the final400 steps, logged time, accepted step size and evaluation
time are [exactly equal](clock-replay.json). Final checkpoint clocks and
time metadata are exact; all stored physical histories pass their original
absolute/relative limits in the [dataset audit](restart-history-comparison.json).

[All400 common final-cycle fields](summary.json) pass: maximum nodal
difference6.453171330633722e-16 and maximum normalized mass-norm
difference7.184309590182767e-14, versus limits2e-9 and1e-8. Comparing the
old and corrected binaries over1200 common sampled states gives maxima
7.28583859910259e-16 and7.732931403199335e-14. No phase interpolation,
fitting or pressure gauge adjustment is used. Periodicity and the existing
kinematic, mass and divergence-theorem checks also pass for this replay.

[19,302 files](archives.json) were read back and hash-verified in15 parts,
totaling106,899,680 compressed bytes. ELF binaries are omitted with exact
hashes retained. The [original clock failure](../pressure-mpi-original-clock-failure-2026-11-08/README.md)
remains a failure: this replay does not recover a discarded v3 correction
or certify unrelated pressure, Lamé, mesh-refinement or time-error gates.
