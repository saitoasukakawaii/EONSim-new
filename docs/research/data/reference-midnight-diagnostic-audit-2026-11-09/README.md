> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pinned svFSI diagnostic midnight-wrap audit

Base: `a0a4675b561b07feabe19e52c9d993b7da3a4a83`. The pinned upstream is
`7bdb74cdd517310d6bf32c0bb7d42072aeac8658`; its complete `UTIL.f`, `OUTPUT.f`
and `INITIALIZE.f` used for this diagnosis are retained with hashes.

Capture completed2026-11-08T16:44:20Z:344 files in four parts totaling
134,713,104 bytes, with every member read back against its original SHA256.

`CPUT()` omits the date. Its diagnostic elapsed can wrap at local midnight,
including the elapsed field stored in native checkpoints. The change accepts
finite signed diagnostic elapsed only: physical time, equation norms, residual
ratios, complete algorithm histories and exact input/seed hash binding retain
their prior requirements. Negative/nonfinite physical state is still rejected.

The original fine N200600→700 baseline returned0 in3004.393521s, with zero memory
events and an empty2GiB/swap0 scope. Its frozen auditor then failed. That failed
controller, reviewer, original logs and all baseline fields/native histories
remain unchanged and are captured here. Corrected audit passes all100 steps;
resumed700 algorithm bytes equal original700 except diagnostic elapsed. Actual
two-rank4400 is also decoded, including its unequal diagnostic rank timers.

WSL28 reference+8 pressure tests passed with raw logs. Final validation took
4.083539s, peak33239040B, zero memory events and an empty2GiB/swap0 scope.
Windows6 convergence+16 native restart tests passed as observed in tool output;
26 CI-selection tests passed with a raw log included. No C++ change or unrelated
numerical retest was required.

Preserved failures include the original signed-time rejection, first validation
incorrectly expecting every rank timer to wrap, initial Windows Git ownership
refusal and preparation-only successor errors. No failed status is overwritten.
Later candidate/continuation output is excluded because it was still active.

`archives.json` and `manifest.json` describe full verified source bytes. Every
listed part must be stored as an ordinary Git blob and independently read back
before commit; `index-staging.json` records that step. Execution proof and
diagnostic repair do not establish physical accuracy or complete FSI-PROD-02.
