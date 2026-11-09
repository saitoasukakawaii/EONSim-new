> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Fine-grid time-control queue provenance

At `fa9646d`, [37 files](manifest.json) were verified from a21976-byte archive.
[Hashes](archives.json) and [dated states](summary.json) preserve both frozen
controllers and their source dependencies. These are waiting controllers;
no N400 numerical trajectory or completed budget is claimed here.

Actual commands used `/usr/bin/python3 -u
build/prod48-20261107/queue-womersley-time400-reviewed.py --alpha 2` and
the same command with `--alpha 1`. They wait for the respective fine N200
producer without taking its numerical queue lock. This prevents a successor
from taking the lock during the producer's planned checkpoint handoff.
Only a completed, audited producer or a verified completed original fallback
can release the successor. Alpha2's old five-cycle fallback receives an
explicit sixth cycle under its unchanged definition if needed.

Each successor then runs six cycles of N400 on exactly the producer's mesh,
binary and options, using400 phases. It compares N200/N400 at common phases,
records5→6 tail changes and actual100→200/200→400 sampling differences using
the preceding endpoint. The intended qualification target is fine N200;
this control alone cannot spatially qualify N400.

Review found that the first waiting alpha2 controller omitted the middle
and N400 control's periodicity/mass prerequisites. It was cancelled before
any numerical work or lock acquisition. Its frozen source and cancellation
receipt remain. The independently frozen replacement includes these
prerequisites and refuses failed producer states, including cleanup-required
failures. All analytic and10%-of-space gates retain their original values.

At capture, reviewed PIDs7843/7849 are waiting; old7822 is cancelled. L24 and
production-MPI state files included in the snapshot are context only.

A later pre-execution review found an invalid timeout in these pending
controllers. [The separately archived replacement](../womersley-time-queue-recovery-2026-11-08/README.md)
preserves their cancellation and actual CLI checks; this dated capture is
historical and must not be used as the current process inventory.
