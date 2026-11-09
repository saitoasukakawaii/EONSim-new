> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Coefficient-refresh startup cost screen and independent review

The frozen candidate60eb5cc0 (full hash in[definition](definition.json)) has
already passed the [coefficient-refresh correctness checks](../lu-time-coefficient-refresh-2026-11-08/README.md).
This independent S96/r8/a8 level0 alpha2 screen uses32 startup states, the
same BDF2/default-stabilization input and final time, four idle-yield ranks
sharing WSL guest CPU21, 2GiB memory/swap0 and complete checkpoints.

| Observed mode | Wall seconds | Actual LU factors |
|---|---:|---:|
|Old f7 window8, first|103.181454243|4|
|New default, reuse off|160.046561114|32|
|New window8|82.359251955|5|
|New window32|57.494194266|2|
|Old f7 window8, last|87.337229434|4|

The [report](report.json) applies the predeclared10% reduction requirement
against **both** old-window8 observations and the new default. New window8
fails against the later old baseline (ratio0.943002800624); new window32 is
eligible, with ratios0.557214420826,0.658301100671 and0.359234174517.
Measured old baselines vary, so these are local observations, not a general
speedup or scaling result. The candidate explicitly refreshes after the BE
startup coefficient changes; it does not keep that first factor for32 steps.

Four complete32-state comparisons each read640 HDF datasets. Maxima are
1.0839098715798023e-12 (old8/new default),2.0296264668928643e-16
(default/new8),8.118505867571457e-16 (default/new32) and
4.391018798566293e-18 (old8 repeat). All pass2e-9; v4 clocks and time metadata
match exactly. Every nonlinear/linear acceptance reason is positive.
Actual PETSc event counts are checked across all ranks. The largest observed
scope peak is389,713,920 bytes; all five scopes finish empty with zero memory
events. These checks do not establish physical accuracy or periodicity.

The first controller incorrectly required FGMRES for the disabled-cache
default, whose unchanged valid policy is PREONLY with fresh factors.
It stopped after the successful old8/default calculations. Its failure,
controller, complete logs and states are retained. The [recovery record](recovery.json)
explains the new attempt: byte-verify imported completed outputs, recheck their
logs and actual factor counts, and run only the remaining three modes.
No numerical source, tolerance or cost gate was changed to repair this checker.

Actual commands atd844e40 were `/usr/bin/python3` followed by
`build/prod48-20261107/screen-lu-time-refresh-startup.py`,
`screen-lu-time-refresh-startup-retry2.py`, and
`review-lu-time-refresh-startup.py`. Retry2 completed UTC06:35:28 on2026-11-08.
The independent [review](review.json) reopens all2,560 datasets, hashes inputs
and sources, verifies raw logs/profiles/resources and checks that no process
remains in any screen scope. Report SHA256 is
`600c1192249c14fcee653b4e93325f2ca5aa33cbd3fde537e4f5000303f2cb73`.
Its decision permits only a fresh independent coarse S96/window32 study.
The new coarse controller starts at06:41:24; its growing output is not part
of this completed archive. Fine-resource/cost review and matched N400 remain
separate, and original S48 producers/consumers remain unchanged.

`capture-lu-refresh-startup.py` completed UTC06:46:07. The
[manifest](manifest.json) retains1,296 files, including the entire first
failure and retry2 data; [three parts](archives.json) total35,863,880 bytes.
Native Python3.13 ran
`stage-external-archives.py lu-refresh-startup-cost-2026-11-08`; the
[actual index readback](index-staging.json) verifies all ordinary Git blob
bytes and preserves every D original. No push or PR is implied.
