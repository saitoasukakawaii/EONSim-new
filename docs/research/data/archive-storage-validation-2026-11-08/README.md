> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Byte-preserving archive order and sparse Git storage validation

This is storage evidence only. No numerical state, tolerance or production
trajectory changed. The completed alpha2 fine new-default screen supplies
the same16 HDF files: four ranks at accepted steps605–608,24,191,616 bytes.
Both runs use tar.xz preset3 and read back every original file by SHA256.

| Member order | Archive bytes | Observed seconds |
|---|---:|---:|
| Generation, then rank | 17,411,816 | 82.019077993 |
| Rank, then generation | 11,205,436 | 62.349219185 |

The [sample result](summary.json) gives a byte ratio0.6435535500719741,
about35.64% smaller with rank ordering. Both reconstruct exactly the same
16 files. Timings are one observation on WSL CPU17 at nice19 while other
jobs run; they are not a general compression benchmark. The result does
not establish savings for other cases or full trajectories. Both trial
archives and all original sample files are retained.

The new [capture helper](capture-ranked-external-evidence.py) groups HDF
members by checkpoint family, rank and generation, keeps the existing
64MiB raw-part bound and preset3, and verifies every archived member.
Large parts are stored locally on D, while metadata remains in this
checkout. It does not stage Git or replace archive bytes with pointers.
[26 files](manifest.json) were read back from one39,834,848-byte part;
[capture metadata](archives.json) records source checkpoint2367903 and
the local storage path. Capture completed UTC05:21:03.

An [isolated native-Git fixture](sparse-index-check.json) first proved a
regular100644 blob can be indexed from an external file, marked
skip-worktree, and recovered byte-for-byte from a written tree while its
working copy is absent. The [actual project-index check](index-staging.json)
then staged this archive and verified its mode, skip flag, byte count and
SHA256 by reading `git show :path`. Blob
`858cd6ab83181cb68e75012521ae81767d022d42` contains all39,834,848 archive
bytes. The [staging script](stage-external-archives.py) preserves the D
original, refuses an existing index entry and changes no refs or repository
configuration. No source was moved or deleted. A normal checkout of the
eventual commit can materialize the full archive without access to D.

Actual commands at2367903 were `/usr/bin/python3` with
`build/prod48-20261107/check-artifact-ordering.py` and
`build/prod48-20261107/validate-external-evidence.py`; native Python3.13 ran
`build/prod48-20261107/check-sparse-evidence.py` and
`build/prod48-20261107/stage-external-archives.py archive-storage-validation-2026-11-08`.
The frozen capture helper SHA256 is
`81dba5d266e9cde0c74f0ae8a073e54dc6075427bd583b65ddd10ea9a2e58533`.
Project-index verification completed UTC05:30:28; capture alone did not
imply staging. No push or PR is part of this validation.

The native Windows JSON receipts retain their original CRLF bytes. The
default whitespace check reports those carriage returns; the final check
uses `git -c core.whitespace=cr-at-eol diff --cached --check`. This changes
only that check's interpretation, not Git configuration, archived bytes or
recorded hashes. No other whitespace finding remains.
