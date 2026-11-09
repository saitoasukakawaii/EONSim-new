> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S12 reference chain and matched-source comparison

The original reference stopped at its twelve-hour limit with step5641 complete
and a partial5642. Its unchanged native5600 checkpoint was replay-validated,
then used to compute5601..6400. The numerical process returned0, but the
controller correctly retained a cleanup failure because an MPI helper remained
in its resource group. That helper was cleared; original failures remain here.

Independent postprocessing established all6400 steps/12800 final equation rows
at the unchanged relative tolerance1e-10 (maximum FS5.6e-11/MS9.8e-11), then
audited all800 saved states5601..6400. Cross-program comparison initially
rejected mismatched analyzer hashes. Recomputing the EONSim report with the exact
reference analyzer preserved every value except its source digest; subsequent
observable and200-phase field comparisons completed12:34:16UTC. All numerical
output bytes remained unchanged. No numerical rerun or identity-gate removal.

Reference ALE periodic maxima in cycles31/32 are2.62492137e-5/2.62484837e-5,
failing1e-5. The other four fields, kinematics, conservation and positive
Jacobians pass. Lamé mean errors are4.802660% EONSim and4.802611% reference,
both failing2%. Comparison eligibility and full physical qualification remain
false; observable agreement cannot override those prerequisites.

Pinned svFSI is7bdb74cdd517310d6bf32c0bb7d42072aeac8658; unchanged native
serial binary SHA f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf.
The5600 seed SHA is8ff753de115aa4c3ab5cfd918baf8ff24d666b0df90acb8eafd429e8162e95c3.
Actual recovery ran on shared WSL CPU13/nice19,2GiB/swap0. These saved times are
native reference times, not EONSim v4 clocks.

Capture35431 completed12:46:36UTC:1070 files/eight parts/287476596 bytes.
Native Git readback passed13:52:27UTC at27f5c82. Each part is an ordinary Git
blob; D originals remain. [Summary](summary.json), [chain](restart-chain.json),
[convergence](svfsi-convergence.json), [field audit](svfsi-audit.json),
[source equivalence](analysis-equivalence.json), [observables](cross-code-observables.json)
and [fields](cross-code-fields.json) accompany full commands, frozen source,
input meshes, raw fields/native records and all failed controllers/waiters.
The separate [EONSim trajectory](../elastic-s12-fine-eonsim-complete-2026-11-08/README.md)
was already saved at27f5c82; it is not duplicated here.
