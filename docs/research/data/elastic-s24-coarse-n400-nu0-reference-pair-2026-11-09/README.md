> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Complete S24 coarse N400 reference with independent mesh-nu0

Completed 2026-11-08 20:54:47 UTC. This is a complete coarse member and comparison,
not full project qualification. Physical solid Poisson ratio remains0.3;
only the independently declared reference mesh-motion value is0.

- Original pinned reference binary f3bdbb, two ranks, CPUs10/12,2GiB/swap0;
 12800 steps, full relative convergence FS3.7e-11/MS9.6e-11<1e-10.
- All1200 stored states11601–12800 audited, including actual preceding11600;
 last-two-cycle maximum across five fields6.611520782e-6<1e-5; kinematics0,
 stage mass5.85469e-18, divergence theorem5.78545e-18, positive Jacobians.
- Same bounded analyzer6fdd2a4 and all400 common phases: radial/area amplitude
 difference3.026038%, flows1.838383%/1.854909%, respective phase gates pass.
 Mid-pressure amplitude3.112768487% **FAIL2%**; EON/reference Lamé means
3.195039047%/3.195043167% **FAIL2%**. No threshold changed.
- Full-field P1 RMS differences and scales are in [fields](cross-code-fields.json).
 They are pairwise differences with no automatic new gate or causal attribution.
 All original inputs were hashed before/after analysis and capture, unchanged.

[Observables](cross-code-observables.json), [audit](svfsi-audit.json),
[summary and clean private-scope resources](summary.json).
The full reference inputs, meshes, original native checkpoints, all stored fields,
sealed coarse commands/logs/receipts and frozen analysis source are preserved.
Live fineN200 family logs are excluded. Existing EON coarse raw bytes are
[individually SHA-linked](eonsim-raw-evidence-references.json) to the
[complete EON archive](../elastic-s24-coarse-eonsim-pair-2026-11-08/README.md).
Original mesh-nu.3 failures remain in that earlier comparison and reference archive.

[Manifest](manifest.json):1408 files,4 parts,109627948B. All parts are complete
ordinary100644 Git blobs, with [full index readback](index-staging.json),
not metadata pointers. D archive originals are retained; the sparse worktree
does not duplicate their bytes. No remote upload/PR or fine-family acceptance.
