> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S12 native restart and explicit convergence-chain proof

The original reference run hit its43200s limit at07:35:13UTC, after complete
step5641 and a partial5642. Its failed status, original log, input, actual
checkpoints and42 stored field files remain. No6400-step success is claimed.

The actual step5600 native checkpoint is558,664 bytes, SHA256
`8ff753de115aa4c3ab5cfd918baf8ff24d666b0df90acb8eafd429e8162e95c3`.
The same pinned binary resumes5601..5620 in a separate directory, then replays
5611..5620 from the actual5610 checkpoint. All five physical fields agree
exactly with the original20 states. The entire native record is byte-identical
across10 replay states except elapsed execution time; saved physical time also
matches exactly. This is an upstream native clock, not an EON checkpoint-v4 claim.

Independent review uses16 reference and8 pressure-audit tests and actual two-
and three-segment log chains. Every selected equation/step has a printed relative
ratio strictly below1e-10. Original1..5600 worst FS/MS ratios are5.6e-11/9.8e-11.
The old excluded tail is explicit. Seed hashes, native stamps, finite complete
history, identical pressure/mesh/physical inputs and contiguous ranges are
validated. Full pressure audits require the complete chain and the original
boundary field bytes; a late resumed log cannot qualify earlier missing steps.

The first resource-scope attempt failed before solver execution when its parent
observed MemoryMax before installation. The retry waits at most5s for setup;
the child still requires2GiB/swap0 before execution. That failure and the first
review preparation's missing tests directory are preserved. Neither is labelled
a numerical failure or silently overwritten.

The original failure, complete probes, reviews, sources and immutable full-
recovery definition total443 files in4 parts(56,165,088 bytes). Full recovery
started08:52:59 toward6400; its growing logs and results are explicitly excluded
from this archive. `summary.json` and `independent-review.json` retain scope;
`continuous-convergence.json`/`replay-convergence.json` retain real segment
evidence. `manifest.json`/`archives.json` verify all archive members;
`index-staging.json` adds actual ordinary Git blob byte verification.

The code accepts `--reference-chain` for a manifest with schema
`svfsi-native-restart-chain-v1`, `final_step`, `target_work` and ordered segments
(`work`, `log`, `first_step`, `last_step`). Paths may be relative to the manifest.
Only the pinned serial linear-FSI i32/f64 record layout is supported. This proof
permits native recovery; physical qualification and independent budgets remain
required. No PR/push or tolerance change occurred.
