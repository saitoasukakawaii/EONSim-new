> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Reference convergence and linear-floor evidence

Pinned svFSI7bdb74c, source checkpointc49c69c plus the exact Python files copied
here. All181 archived files were read back and SHA256 verified. Reference
source/binary and nonlinear tolerance1e-10 were unchanged. Tests used one
process on CPU8 after its serial lock was released; no performance claim.

PIC.f:270-275 marks an equation ok when it reaches maxItr, as well as when a
relative criterion succeeds. Successful process exit and VTU output therefore
do not establish convergence. The new auditor checks every equation/step,
input hashes, iteration sequences and printed ratios. Either Ri/R0 or Ri/R1
must be strictly below the actual input tolerance. A rounded equality remains
unproven. Logs are bound to the field audit's exact export manifest. Missing
log evidence makes reference comparison ineligible; it is not silently passed.

| Actual coupled five-step probe | Linear absolute tolerance | Result |
| --- | ---: | --- |
| Two-period ramp, N100 | 1e-22 | pass, at most3 iterations |
| Sixteen-period ramp, N100 | 1e-22 | fail: first mesh step1.1e-10, cap30 |
| Sixteen-period ramp, N100 | 1e-26 | pass, at most2 iterations |
| Sixteen-period ramp, N200 | 1e-26 | pass, at most3 iterations |

This tightens the linear absolute floor only; the nonlinear relative and
physical gates are unchanged. The default exporter still writes1e-14.
--tight-linear-atol is explicit and only permits a smaller positive value.
It is recorded in export.json. Short probes are not periodic qualification.

The completed original13200-step reference log passes all26400 equation-step
checks, with no iteration caps. The earlier ramp2/c12 reference reaches the
cap in all2400 final equation rows;1215 fail the relative criterion. That run
is not converged even though its process and field-output stages completed.
Actual long/candidate logs and fields are in the
[startup evidence](../pressure-tube-startup-2026-11-08/README.md).

Actual minimal tests passed6 exporter,4 log-auditor,7 field-auditor and26 CI
selection checks. Four manufactured integration checks passed: matching log
inclusion, absent-log rejection for eligibility, input-manifest mismatch and
preservation of synthetic ineligibility. The first integration attempt used
whitespace before a closing bracket that the initial parser did not accept;
its script/input/failure are preserved. Accepting whitespace changes no
numeric criterion. Receipts are explicitly distinguished from raw logs.

```sh
/usr/bin/python3 tests/test_svfsi_convergence.py
/usr/bin/python3 tests/test_svfsi_export.py
/usr/bin/python3 tests/test_pressure_tube_audit.py
/usr/bin/python3 tests/test_ci_selection.py
/usr/bin/python3 scripts/audit_svfsi_convergence.py --work REFERENCE --log SOLVE_LOG --output NEW_REPORT
```

Exact executed probe/integration controllers, commands, sources and artifacts
are archived. No C++ rebuild, unrelated numeric suite or compatibility matrix
was needed for these Python input/analysis changes.

Final parser review also rejects an unreadable later iteration instead of
silently accepting an earlier row. The affected four unit tests passed in
.043s. Four real logs (132 cycles, ramp2, ramp16 and N200 five-step probe) were
reanalyzed with unchanged conclusions. Eight copied source/result files were
SHA256 verified in `final-parser-review/`; the original 181-file archive and
its original parser are retained, rather than relabeled as the later version.
