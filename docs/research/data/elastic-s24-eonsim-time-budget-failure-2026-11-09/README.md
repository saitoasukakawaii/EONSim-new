> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 EON complete time-budget failure

The original EON S24 level1/N400 budget finished on 2026-11-09 01:14 UTC.
Its periodic, geometry and conservation prerequisites pass, but three time
terms fail the unchanged requirement `time / last_space < 0.1`.

| Field | Last spatial difference | N200/N400 time difference | Time / space | Result |
|---|---:|---:|---:|---|
| ALE displacement | 0.106670979584 | 0.005896258559 | 0.0552751890 | Pass |
| Fluid pressure | 0.009879926584 | 0.009023740388 | 0.9133408342 | **Fail** |
| Fluid velocity | 0.013045936620 | 0.005037554810 | 0.3861397581 | **Fail** |
| Solid displacement | 0.138258550638 | 0.007925817125 | 0.0573260539 | Pass |
| Solid velocity | 0.041711169963 | 0.007949632087 | 0.1905876075 | **Fail** |

All ten tail and sampling terms pass. The fixed P1 mass norms, common actual
phases, original coarse/fine spatial comparison and temporal comparison are
unchanged. No phase fitting, pressure offset, Richardson factor or relaxed
tolerance has been applied. Default stabilization also depends on the effective
time coefficient, so this observation alone does not establish an integration
order or identify the source of the difference.

[Budget](budget.json), [summary](summary.json), [resource receipt](resource.json),
[producer receipts](producer-receipts.json) and [capture definition](definition.json)
bind the exact results to frozen sources and inputs. The analysis completed in
2536.857888903 seconds, peak 165564416 bytes, under 2 GiB / zero swap with zero
memory events and an empty owned process group. Clean execution is distinct from
the failed numerical budget. The reference program's budget and cross-program
qualification remain pending.

The archive contains 57 files in one 1449600-byte part, including all EON budget
reports, the three matching audits, original analysis source and case/mesh inputs.
[Manifest](archives.json) and [complete Git readback](index-staging.json) verify
the part as a regular Git blob, not a path pointer. Part SHA-256:
`5ce70320a143116f9fcdc8692f1d0ab6b76e15dc62798bed77a830dd7b5ba306`.
The raw trajectories are preserved in their separate complete captures; this
report archive does not substitute for them. Source checkpoint: `9ccd73f`.

No finer-time study or new FSI execution policy was adopted by this capture.
The optional FSI LU implementation being checked separately is unqualified
until its actual field/history, convergence and cost checks have passed.
