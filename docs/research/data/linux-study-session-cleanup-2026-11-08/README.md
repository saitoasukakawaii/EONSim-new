> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Linux study invocation cleanup includes every MPI process group

Inspection of real OpenMPI5 ranks showed that each rank had its own process
group, while all belonged to the launcher's new session. Waiting for only
the launcher's group therefore cannot prove that the numerical ranks have
stopped. A real four-rank fixture confirmed that ranks can survive a killed
launcher. The old diagnostic waiter20915 was cancelled before any numerical
work; its source, identity and cancellation receipt are preserved.

The replacement21129 uses session and process-start identities for bounded
cleanup. It still waits for alpha1's natural middle endpoint under the same
option lock. Its900s/3.5GiB bounds and field/cost criteria are unchanged;
there is still no direct-solver qualification or automatic production adoption.

The same correction is now implemented in `study_rigid_tube.run`, shared by
rigid and Womersley study invocations. On Linux/WSL, each invocation starts a
new session. Timeout or interruption first lets the launcher relay SIGINT,
then checks and stops all remaining session members, including ranks in
separate process groups. PID/start identities are rechecked before signalling.
It waits for no executing members, writes a cleanup receipt and propagates
the original failure. A successful launcher that leaves running children is
also rejected after cleanup. Other sessions are untouched. The previous
non-Linux runner remains unchanged; no new non-Linux cleanup claim is made.

[Exact source hashes](source.json) identify the changes on `30828c5`.
Python3.12 on WSL Ubuntu24.04 passed all7 `tests/test_rigid_tube.py` checks:
three existing mesh/reference checks plus success/failure logs, timeout,
premature launcher success, and KeyboardInterrupt cleanup. Each process
check also keeps a separate unrelated session alive. The run took9.065s.
Real OpenMPI5, from the PETSc3.23.7 runtime, separately passed two-rank
success and four-rank timeout through the production runner. The original
timeout propagated only after its session became empty. The earlier
launcher-killed four-rank fixture additionally exercised forced cleanup
of ranks ignoring SIGINT/SIGTERM. No PDE, full suite or old-PETSc test ran.

[Summary and exact commands](summary.json), raw logs, test source, fixture
and controller receipts are among [24 verified files](manifest.json).
The17,260-byte archive SHA256 is
`9c8d9599034bc811f46f351cf520188d6c442b58c88b0016201b77f7fc01c404`.
[Archive metadata](archives.json) records its readback and hashes.
Already frozen long studies do not automatically adopt this runner change.
