> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# S24 / level1 / N400 elastic preflight

Five steps of the explicit ramp16 candidate completed in both programs:
frozen b072 EONSim and unmodified svFSI7bdb74c. Reference nonlinear relative
convergence is audited at1e-10 with explicit linear absolute floor1e-26;
positive EON geometry and accepted steps are recorded in [summary.json](summary.json).
Local concurrent wall observations are34.983s/31.634s, respectively. These
five steps do not establish periodicity, fine-grid accuracy or performance scaling.

[79 original files](manifest.json), including exact meshes, commands, source
snapshots, all short-run fields and logs, were read back from one10909296-byte
archive. [Hashes and the omitted executable's digest](archives.json) are retained.

The first capture rejected svFSI's valid hard-linked `stFile_last.bin` because
the verifier required a regular archive member. The
[original failed archive, source and failure record](../pressure-s24-preflight-failed-2026-11-08/README.md)
remain intact. Retrying with `tarfile` dereference enabled stores each path as
regular bytes and passes the same source-content hashes. This reran only
archiving; neither numerical program nor the completed fields changed.

The later long S24 study and any explicit execution-policy continuation have
separate state/provenance records and are not qualified by this package.
