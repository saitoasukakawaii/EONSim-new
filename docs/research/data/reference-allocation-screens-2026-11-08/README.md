> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Bounded reference allocation screens: no new policy selected

These attempts reuse the pinned svFSI binary and the same20 full-load startup
inputs from the [serial/two-rank preflight](../production-followup-preflights-2026-11-08/README.md).
The spatial problem is S24/level1, mesh-motion Poisson ratio0, solid ratio0.3.
All physical and convergence tolerances remain unchanged. This is execution
evidence, not a32-cycle reference qualification.

| Attempt | Observed outcome | Selection |
|---|---|---|
| Four ranks, GMRES space100, WSL CPUs10/12/14/16 | No completed step; cancelled at643.680s after its cost already exceeded the complete two-rank baseline. Four diagnostic stacks remain inside GMRES; root cause unconfirmed. | Not selected |
| Four ranks, space200, same CPUs |300s limit; cleanup finished at301.167s. Five outputs exist, but mesh equation step5 reached iteration30 with relative-to-initial ratio2.51e-9, above1e-10. | Not selected |
| Two ranks, original space100, WSL CPUs10/12 | All20 five-field states and all40 final equation rows pass;236.232s versus prior two-rank261.554s. |9.68% reduction is below the predeclared10% gate; not selected |

For the final attempt, maximum absolute nodal difference from the serial
reference is1.6653345369377348e-16, and maximum normalized mass RMS difference
is2.4558182111500794e-14, below2e-9/1e-8. These results are in the
[combined summary](summary.json). The original two-rank long study continues.

Each attempt temporarily stopped the same identified alpha1 study driver,
MPI launcher and four ranks. Each private scope was limited to2GiB and swap0;
observed peaks were79,679,488/110,989,312/88,580,096 bytes, with no memory-limit
or OOM events. Every owned scope emptied before the six original processes
resumed. Alpha1 was restored after the final attempt at UTC03:57:42.
The alpha2 study and its separate natural-boundary LU screen were not changed.

CPU indices refer to **WSL guest logical CPUs**. Earlier raw labels saying
“dedicated/physical cores” describe guest-reported groups, not demonstrated
host-core pinning; see the [host/guest observations](../execution-topology-2026-11-08/README.md).
The baseline and candidates also ran at different times with other project
workloads present. Their timings do not establish isolated host scalability.
The first duration includes debugger attachment and is not a clean timing
sample; it is retained as an unsuccessful bounded diagnostic.

[162 immutable files](manifest.json), including both failures, five incomplete
outputs, all20 successful two-rank outputs, input manifests, frozen analysis
sources, resource/cleanup/resume receipts and diagnostic stacks, were read back
and hash-verified in one17,790,032-byte part. [Archive metadata](archives.json)
records capture d1ad62b. The previously archived serial/two-rank baseline is
referenced by hashes rather than recalculated. No tolerance was relaxed and
no long-study configuration was adopted from these attempts.
