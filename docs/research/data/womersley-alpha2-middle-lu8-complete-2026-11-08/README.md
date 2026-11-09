> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Completed alpha2 middle retained-LU trajectory

This preserves the independently reviewed480→1200 continuation at2367903,
captured atd844e40. The S48/r4/a8 level1 mesh has12,257 nodes and64,512
tetrahedra. The frozen f7bf9f3d executable uses four ranks, BDF2, N200,
default stabilization, MUMPS/chord and LU window8. The study reaches six
cycles with all200 phases; the last three cycles are wholly within the
adopted continuation. [Earlier screening and handoff evidence](../womersley-middle-lu8-2026-11-08/README.md)
retains the old trajectory and the independent adoption review.

The producer completed UTC05:56:47 on2026-11-08. Its [analysis](analysis.json)
has velocity error0.018511161244531674 (1.851116%, **fails1%**), pressure
error0.005318232460078735, flow-amplitude error0.0015783925877070892,
phase error0.1033308894814128 degrees and net flux5.23254603166344e-18.
The last-cycle maximum-phase velocity/pressure differences are
5.8246757568232514e-15 and5.520384874844434e-15; periodicity passes.
This is the middle spatial level, not finest-grid qualification.

The original diagnostic comparisons are retained without changing their
definitions. [N100→N200 at level1](time-l1-n100-n200.json) uses cycle5 and
100 common phases: relative RMS velocity/pressure differences
0.0008209521501165857/0.0016758787493160296. The
[level0→level1 N200 pair](space-l0-l1-n200.json), also cycle5 and100 phases,
gives0.0048351044607735615/0.009375492852160675. These denominators are
the first spatial difference, not the required last fine-grid difference;
they do not establish the pending fine N200/N400 budgets. Definitions also
record the earlier comparator's frozen b072 executable and Schur policy.
[Cycle5→6](tail5-6.json) uses200 phases and preserves both cycle-RMS and
maximum-phase norms. No failed or incomplete gate is promoted to a pass.

Actual controller command: `/usr/bin/python3 build/prod48-20261107/handoff-womersley-middle-lu8-m480.py`.
It freezes the study/analyzer/comparator sources and all individual commands
inside this archive. The [continuation resource record](continuation.resource.json)
shows3246.157957159s, four MPI ranks sharing WSL guest CPU21 with idle-yield,
2GiB memory/swap0, observed peak866,045,952 bytes, no memory events, and
an empty completed scope. This resource choice supplies no scaling result.

`capture-alpha2-middle-complete.py` completed UTC06:27:22. The
[manifest](manifest.json) contains3,713 verified files: complete seed and
continued checkpoint histories, input mesh/partitions, phase map, logs,
frozen controller/source, accepted receipts and all completed analyses.
The still-waiting N400 child's `new-n400.log` is explicitly excluded because
it may grow; the [summary](summary.json) records this boundary.
[Ten archive parts](archives.json) total214,006,344 bytes and remain locally
on D. Native Python3.13 ran
`build/prod48-20261107/stage-external-archives.py womersley-alpha2-middle-lu8-complete-2026-11-08`;
[complete index readback](index-staging.json) at UTC06:28:33 verifies each
regular100644 Git blob's bytes, SHA256 and sparse flag. All source files
remain available; no push or PR is part of this preservation.
