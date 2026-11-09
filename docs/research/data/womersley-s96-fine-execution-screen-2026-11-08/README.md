> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S96 fine execution-path evidence

All comparisons use the same mesh, physics, CPU21 and6GiB/swap0 boundary.
The32-state four-rank window8/32 times are943.454471935/632.060752033s
with5/2 LU factorizations. Partitioned MPI rank1 takes397.682864605s;
the actual native unpartitioned rank1 study-driver path takes394.727331581s,
2 factorizations and3,553,603,584B observed peak memory.

Independent960-dataset readback compares current/history fields and exactv4
clocks across all three window32 execution paths. Native vs four-rank maximum
is1.5504091e-16 nodally and2.3822603e-16 in normalized P1 mass; native vs
partitioned rank1 maximum is6.9388939e-18. Native cost is0.624509 of the
four-rank window32 cost for this resource layout. This is not a scaling study.

The idle four-rank adoption waiter was retired before long work, preserving
its complete screen, handler failure and distinct cancellation record. The
fresh native coarse/fine/N400 family was adopted only after the actual
driver path passed. Its immutable source, configuration, adoption, budget
and history-check worker are included; growing long-study outputs are not.
No fine physical qualification or full error-budget pass is inferred.

595 original files are captured and read back in10 parts(244,664,400 bytes).
`archives.json`/`manifest.json` record exact members and hashes; the additional
`index-staging.json` verifies ordinary Git blob bytes. D originals remain;
the sparse local checkout can omit duplicated part files. Full reports and
the independent native review retain detailed metrics and scope.
