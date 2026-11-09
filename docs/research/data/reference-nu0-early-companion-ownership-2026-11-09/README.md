> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Explicit early ownership of the two pending independent nu0 companions

Source checkpoint `a3e1c87e071ce73f480b63a1144874cd75e3e1c5`.
69 files, one686896-byte part with complete member/index readback:
[archives](archives.json), [manifest](manifest.json), [index receipt](index-staging.json),
[definition and adoption](nu0-summary.json), [old idle consumer retirement](old-consumer-cancelled.json).

At20:03:35UTC new controller41283 adopted the originally planned but unstarted
coarse S24N400 and fine S24N200 reference members. They run sequentially on
CPUs10/12, in parallel with the original fine N400 already running on9/23.
Each job retains original f3bdbb189f6cc1600014990eb5356ab218b135d869c5c41ada7497795e9926bf
svFSI binary, two ranks, exporter, input meshes, pressure history, tolerances
and output cadence. Mesh Poisson ratio0 is still the independent counterfactual;
solid Poisson ratio.3 and all other physical data remain unchanged.
Private2GiB/swap0 scopes retain10GiB admission and8GiB global floor.

The original planned output paths are explicitly claimed with ownership
receipts before execution; this is not an implicit overwrite or duplicate
study. The exact frozen old companion loop was extracted and executed in a
fixture: its existing `assert not reference.exists()` rejected a claimed
directory before any export/numerical call. The original fine producer39157
receives no signal and its frozen source is untouched. After its full fine
solve/convergence/audit, this guard is expected to retire the old queue before
any duplicate companion work. That future original failure must remain failed;
the new family requires the exact guard failure, complete fine reports, clean
fine resources and no old companion commands before assembling completion.
This future boundary has **not yet occurred** in this archive.

New bounded budget waiter41284 was ready before the only signal, SIGTERM to
verified childless/unlocked idle40214. Old40214 is cancelled_before_analysis.
The new consumer changes six routing/decision strings only; inverse byte/AST
comparison matches the prior consumer. The physical budget kernel is byte
identical, fine uses its explicit restart chain, and coarse/time use the actual
new family solve logs. Source/input checks and independent review bind the
adoption. The coarse solve starts20:03:37UTC; no new numerical result or full
qualification is asserted here. Growing outputs and live fine evidence are
excluded; immutable original coarse export/input bytes are included.
