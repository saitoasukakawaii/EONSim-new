> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Append-only external Git object storage

Source checkpoint: `224aad53d012f8aa4c661b61089eb0b070ce16e9`.
The local checkout added a D-drive object store after the
[complete isolated proof](../git-cross-drive-storage-proof-2026-11-09/README.md).
Existing C objects and all D archive originals remain in place. No Git config,
branch, remote ref, physics, or numerical producer changed; nothing was uploaded.

`storage.json` records the exact store, relative alternate and Windows junction.
The ordinary blob for `storage-probe.json` is
`834da037c8e068d3157a940df937cc65e0046cfb`; its loose object exists only in the
new D store. Default Windows and WSL Git both read the exact project index bytes.
The local checkout needs that append-only store. This is an object database,
not an archive-path substitute in the committed tree.

The isolated fixture used a complete 249028-byte archive, ordinary100644 mode,
Windows/WSL default reads and strict full object checks. A `git clone --no-local`
copy had no alternates and read every byte independently on both platforms.
The proof supports ordinary Git object transfer; no GitHub upload was tested.

Future completed archives use `stage-external-archives-dstore.py`. Before any
index write it verifies every selected source and reserves4GiB plus the entire
selected object batch and64MiB on D; C retains4GiB plus64MiB for metadata.
Selected batches plus the existing staged content are limited to1.5GB raw blobs.
Each blob is read back through default Git and checked against the original SHA.
Partial batches are labelled incomplete; only an explicit finalization rereads
all parts and writes the whole-archive `index-staging.json` receipt. A completed
capture and all ordinary part blobs remain required for a complete evidence claim.

The initial preflight rejected benign app-injected `GIT_CONFIG_*`/`GIT_PAGER`
variables before any directory creation. Its source and failure are preserved;
the actual retry rejects only inherited storage/index/worktree overrides.

Official contracts: [Git object layout](https://git-scm.com/docs/gitrepository-layout)
and [Git clone transport](https://git-scm.com/docs/git-clone).
