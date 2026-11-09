> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Actual independent mesh-nu0 native5000 continuation

307 immutable files, 6 parts, 66,801,540 bytes. Adopted17:59:41UTC after the original two-rank family exited
naturally at5000. All10000 final FS/MS rows passed, maxima4.8e-11/9.5e-11.
The1419728-byte native seed has time78.5398163397418 and SHA
`bfc1a4cb2e75145dce204edc09b4b7c98d663a6974d63000a6d1dafde9750e91`.

New39157 uses the reviewed ILUT candidate for fine5000..12800 on CPU9+23 with
2GiB/swap0. The later unstarted coarseN400/fineN200 members retain the original
reference binary and exporter. Solid Poisson ratio remains.3; only mesh-nu0 is
this independent counterfactual. Original failures and the unchanged nu.3 family
remain explicit. Growing continuation outputs are excluded. Full chain, fields,
periodicity and each independent error budget remain pending.

[Actual adoption](adoption.json), [definition](family-definition.json),
[independent review](independent-review.json), [prefix](prefix-convergence.json),
[old completion](old-completion.json), [chain](restart-chain.json),
[summary](summary.json), [manifest](manifest.json), [archives](archives.json),
[actual Git bytes](index-staging.json).
