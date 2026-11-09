> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Rejected reference execution options

Captured at 2026-11-08 11:58:16 UTC from checkpoint
`243c9d0784b18d55d8b267fa0554767f20ca7554`: 293 files in six archives,
56,537,864 bytes. Every archive member was read back and checked against
[manifest.json](manifest.json); [archives.json](archives.json) records the parts.
The original data and failures remain preserved. No production handoff occurred.

The completed S12 full-load screen starts at actual native step6000. Both arms
use the same pinned-source candidate binary and FSI Trilinos-ILUT; only the mesh
preconditioner changes from FSILS to Trilinos-IC. Mesh CG, assembly option0,
physical inputs and all tolerances remain unchanged. Commands, frozen source,
inputs, raw50 states, native histories and resource receipts are included.

- Baseline20 steps:105.185993 seconds; candidate20:149.428208; replay10:71.768049.
- Cost ratio1.420609379 fails the prespecified ≤0.9 screen. This option is rejected.
- Node/P1-mass/history maxima:1.735e-16/4.482e-14/2.966e-14; saved norm difference0,
  exact native time. Candidate replay is bitwise identical except elapsed time.
- Numerical checks pass, but eligibility/adoption are false. Baseline comparison
  to original production has only20 VTU fields; unavailable original native
  endpoint comparisons are explicitly null, not measured zeros.

The archive also preserves the first two-rank placement screen cancelled at
10:56:06 because CPU12 competed with the existing alpha1/S12 placement. Its
partial output, cancellation request and own empty-scope cleanup are retained;
it supplies no completed endpoint comparison. The later retry is separate.

These are bounded shared-CPU WSL execution observations, not physical
qualification or a general preconditioner ranking. See [summary.json](summary.json)
and [mesh-ic-report.json](mesh-ic-report.json). The executable is identified by
its ELF hash; full build/source evidence is in the previously committed
[serial proof](../reference-trilinos-serial-proof-2026-11-08/README.md).
