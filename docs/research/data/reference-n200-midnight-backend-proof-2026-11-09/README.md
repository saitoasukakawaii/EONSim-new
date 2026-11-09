> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 fine N200: complete backend and native replay proof

Screen38663 completed2026-11-08 17:05:41UTC; independent38676 raw readback passed
17:09:38UTC. Capture39299 completed556 files in ten parts,279699816 bytes, at
17:23:44UTC. This is a bounded execution comparison, not long-run qualification.

| Actual execution | Steps | Wall seconds |
| --- | --- | ---: |
| Original FSILS, byte-imported completed baseline | 600→700 | 3004.393521160 |
| Candidate FSI ILUT, same physics/time/tolerances | 600→700 | 1590.483061353 |
| Candidate native replay | 690→700 | 167.676861234 |

The candidate uses about52.94% of the original local elapsed wall time. All
receipts use external monotonic time,2GiB/no swap, zero memory events and empty
groups on completion. Shared CPU16/nice19 measurements do not imply dedicated
core throughput, general scalability or the same speedup over an entire study.

All100 compared states have maximum nodal difference1.8431436932253575e-17,
normalized P1 mass difference4.482710502635609e-15 and full native-history
difference2.95572485757567e-15. Saved equation norms are identical; native physical
time is exact. Ten replay states are algorithmically byte-identical except
diagnostic elapsed and nonstate padding. Every printed final equation row passes
the original strict relative tolerance. Independent review took236.938041348s.

The original baseline was not rerun: every closed field/history/log/resource byte
was imported from the numerically successful run whose old auditor rejected a
cross-midnight diagnostic elapsed. That original failure and complete baseline
are also retained in the [midnight validation archive](../reference-midnight-diagnostic-audit-2026-11-09/README.md).

- [Screen definition](screen-definition.json), [full report](screen-report.json)
  and [baseline import inventory](baseline-import.json).
- [Independent review](independent-review.json), [resource receipt](independent-resource.json)
  and [capture summary](summary.json).
- [Archive inventory](archives.json), [per-file manifest](manifest.json) and
  [actual Git index byte verification](index-staging.json).

All manifest parts are ordinary Git blobs, including parts absent from the sparse
working tree; D-drive originals remain intact. No growing production output is
included. A separate reviewed natural1100 handoff was requested later; this proof
does not claim that handoff, full6400 convergence, periodicity or physics passed.
