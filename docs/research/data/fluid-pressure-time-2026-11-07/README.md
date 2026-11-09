> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Transient pressure boundary implementation evidence

Source `b072cc81e29160488e5c08044d8aee3b0245078f`; baseline main `c218c18`.
This is a local checkpoint within the active 48-hour task. It is not a completed
PROD-02 qualification or permission to push before that task's acceptance.

The fixed-grid pressure law now shares the FSI sinusoidal law and uses the
integrator's evaluation time. Zero mean pressure is supported by caching a
unit-pressure surface contribution. The profile is included in restart identity.
Accepted-step checkpoint cadence is configurable, including a final partial
interval. [Interface specification](../../../development/FLUID_PRESSURE_TIME.md).

Actual build/validation, WSL Ubuntu 24.04, repository lock PETSc 3.23.7, Release:

```bash
# selection.json contains precisely the following four tests:
# fluid_pressure_time, tagged_fluid_verification, fsi_element_jacobian, fsi_pressure_state
bash scripts/cloud/run.sh 3.23.7 release explicit /home/tfblab633/EONSim/.cloud selection.json
python -m unittest discover -s tests -p 'test_rigid_tube*.py'
python tests/test_ci_selection.py
```

Four numerical tests passed, zero failed/skipped. The new uniform accelerating
flow case checks three time schemes at 1/2/4 ranks. Its maximum discrepancy from
the exact scalar discrete recurrence was `1.97758476261356e-16`; maximum rank
difference `6.245004513516506e-17`. The same test checks cadence, partial-interval
save, same-partition restart, changed pressure-profile rejection, and invalid
period/ramp/mode/cadence/boundary type. Existing tagged boundary and FSI pressure
checks passed. These are implementation checks, with no spatial tube accuracy or
HPC scaling conclusion.

Subsequent Debug validation used the same repository entry and exactly
`fluid_pressure_time` and `fsi_element_jacobian`: 2/2 passed, zero failures or
skips, total 5.67 seconds. The largest discrete-reference error remained
`1.97758476261356e-16`. `debug-*` files retain the original build receipt,
logs, binary identity and all 280 raw test files, read back and hash-verified.
The C++/test sources were unchanged from b072cc8 when this build ran; later
working-tree stabilization-time-control changes are not covered by it.

Nine rigid-tube Python checks passed. The first CI policy check failed because
the newly added rule omitted the required `python` list. Adding `python: []`
fixed the metadata; all 26 selection checks then passed. The initial failure is
recorded separately and is not described as a numerical solver failure.

The original build receipt was produced before the local commit and retains its
actual baseline commit and `dirty=true`. `identity.json` associates the unchanged
tested C++/test contents with the subsequent source commit and hashes the binary.
The 280 original small-case files are losslessly stored in `raw.tar.xz`, with
individual SHA-256 and byte sizes in `manifest.json`. Paths inside case files are
the original local paths; rerunning the test creates portable fresh cases.

The 48-hour steady Schur study uses a different, frozen baseline binary and has
separate evidence. Its failures or results must not be conflated with this test.
