> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Native restart audit and incremental test selection

The new restart helper and affected convergence/pressure tests are explicitly
mapped into incremental CI. The policy selects the relevant Python tests and
its existing Poisson smoke requirement, rather than an unrequested full suite.

The final native-restart proof separately records16 reference and8 pressure
tests. This validation adds26 CI-selection and6 evidence tests, then runs only
`poisson_verification` with PETSc3.23.7 Release and Debug. All pass. Both solver
binaries match the previously validated coefficient-refresh binaries exactly;
the build reports no work. There is no new solver-performance claim.

Runs use low-priority shared CPU15 under2GiB/swap0. Resource scopes empty,
all memory events remain zero, and observed peaks stay below100MB. Full logs,
selected tests, frozen changed source, JUnit/CTest evidence and receipts are
retained in70 files, one65,144-byte archive. `archives.json` and `manifest.json`
verify members; `index-staging.json` records actual ordinary Git blob readback.
`report.json` preserves exact results and source hashes. No push/PR occurred.
