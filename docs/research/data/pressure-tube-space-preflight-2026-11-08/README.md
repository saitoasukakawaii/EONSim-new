> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Same-polygon pressure-tube space preflight

All 123 archived files were read back and SHA256 verified. Source c49c69c plus
captured Python sources, frozen EONSim b072cc8, PETSc3.23.7 and pinned svFSI
7bdb74c. This is one red refinement of the existing S12/R1/Rout1.2/L12 polygon,
not a circle-geometry change. Materials, clamps, pressure law, generalized-alpha
rho_infinity=.5 and default stabilization match the earlier tube; N200.

Five no-ramp onset steps completed with both programs on CPU18. EONSim has
15877 coupled DoFs, positive geometry and positive solver convergence reasons.
Local elapsed times were 23.9521/26.2190 seconds (EON/reference); concurrent
timings only estimate queue cost, not performance or scalability. The reference
uses explicit linear absolute floor1e-26 with unchanged nonlinear1e-10.

The distinct ramp16 five-step reference check on CPU20 also passed every
relative equation/step: maximum final ratios FS9.9e-13 and MS9.8e-12, at most
two iterations, no cap. It checks the tiny initial load on the refined mesh.
Both commands, sources, inputs, fields, raw logs and convergence reports are
archived. Neither short run establishes periodicity or spatial accuracy.

The ensuing 6400-step ramp16/c32 EON/reference study is prepared separately at
elastic-s12-l1-n200-ramp16-c32, with immutable common input and independently
locked serial CPU18/20 workers. Its long-run results are not in this evidence
set and remain unverified. Compare it with level0 at the same N200 only after
both studies' actual field and reference-log prerequisites are inspected.
