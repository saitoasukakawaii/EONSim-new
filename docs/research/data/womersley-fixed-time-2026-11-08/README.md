> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Actual fixed-tau-time diagnostic at coarse N200

Source2eabb47; frozen numerical binary2189a8c SHA256
52dcc56e3e269b115125309f0f4abd8ae697fcf7ca4777778771526d042f876c,
after targeted Debug/Release checks. Alpha2,48/4/8 seed level0,
1737nodes/8064tets, four ranks, BDF2, N200,100phases, two warmup and three
sampled cycles. The only new operator input is
`fluid.stabilization_time_scale=2*(T/100)/3=.010471975511965978`.
No fixed-tau shortcut, material change or tolerance relaxation.

The study reached1000steps. Last-period velocity/pressure differences are
8.09e-13/1.24e-14; preceding-period checks also pass1e-6. Analytic velocity,
pressure and Q-amplitude errors2.36596%/1.15364%/1.50620% still **fail**.
Phase.25111degrees and net flux1.40e-13 pass their separate gates.

|Actual cycle5 field comparison|Velocity normalized RMS|Pressure normalized RMS|
|---|---:|---:|
|Default N100 → N200 with common BDF2 tau-time|.000551645544|.000008412011|
|Fixed tau-time N200 → default N200|.004092458963|.008230315559|

Exact P1 norms use the same reference mesh and100actual common phases. Vector
differences do not give additive scalar error norms. Default N100's first BE
step has a different tau-time; identical startup operators are not claimed.
Fixed-time results do not replace default qualification. Earlier default
fields remain in[the first archive](../womersley-first-2026-11-07/README.md).

`numerical.tar.xz` contains inputs/mesh/partitions/logs/accepted histories;
`analysis.tar.xz` contains exact commands and the analysis helper;
`continuation.tar.xz` records the completed coarse job and explicit fine fork,
not completion of the running fine study. Actual analysis command:
`/usr/bin/python3 build/prod48-20261107/analyze-womersley-fixed-time.py`.
Fresh destinations are required; original paths/commands are retained.
All1574raw files were read back against `manifest.json`; `archives.json`
records archive/copy hashes. Largest archive21,336,780bytes. No binary is
duplicated. Full space/time/tail/sampling and default-tau qualification remain.
