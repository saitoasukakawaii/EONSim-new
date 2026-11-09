> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Retained-LU and checkpoint source review

At source head `7ed5a5ddda43b7d3af4a51d35c3a054062f0ab54`, the executing
agent reviewed retained-PC ownership, collective invalidation, effective
integration-coefficient refresh, final physical acceptance, and checkpoint
v4 time compensation. This is a targeted source review, not external review
or whole-project acceptance.

[The record](review.json) binds fifteen current source/test files byte for
byte to the archived [coefficient-refresh validation](../lu-time-coefficient-refresh-2026-11-08/README.md)
and [checkpoint-v4 validation](../checkpoint-clock-v4-2026-11-08/README.md).
The former passed Debug/Release six checks each with actual1/2/4-rank LU
events and1,005 HDF datasets per configuration. The latter passed eight
checks per build and separately retained the completed400-step exact-clock
production replay. These are reused historical results, not newly run tests.

No new runtime defect was identified in this scope. The state architecture
document still denied retained factors unconditionally; it now distinguishes
the disabled default from the explicit fluid MUMPS/FGMRES option. The option
contract also now links the later effective-coefficient refresh evidence.
Current equations and final field acceptance remain separate from cached
preconditioning. Cache state is discarded after failure or restart; v4 clock
compensation is accepted algorithm state and must be restored. Legacy v3
explicitly reports its missing correction and cannot promise exact replay.

The read-only collector was run from the repository root as:

```text
"C:/Program Files/Python313/python.exe" -X utf8 build/prod48-20261107/review-solver-clock-source.py
```

[Its exact source](review-source.py) records file hashes and reviewed source
anchors. It does not execute tests or launch/alter a numerical process.
There was no build, solver change, frozen-producer edit, push or PR.
All remaining physical studies and error budgets still require completion;
the full delivery review remains pending.
