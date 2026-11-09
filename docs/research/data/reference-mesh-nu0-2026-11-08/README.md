> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Separate complete reference with mesh-motion Poisson ratio zero

This uses the original fixed svFSI commit
`7bdb74cdd517310d6bf32c0bb7d42072aeac8658a` and its unchanged binary.
The S12 level0/N400 physical case, fluid/solid meshes and material inputs
match the original32-cycle,16-cycle-ramp study. Only the mesh-motion
equation's Poisson ratio in a new export changes from0.3 to0.0; the physical
solid remains0.3. [Provenance](provenance.json) identifies the executable,
frozen scripts and original inputs. The original nu.3 study remains separate.

All12800 steps and25600 final FS/MS equation rows satisfy the unchanged
relative1e-10 convergence gate; [the full audit](svfsi-convergence.json)
is retained. Five-field periodicity and all quality gates pass. The maximum
mesh-displacement difference is5.8952298e-6 for cycle30/31 and5.8724441e-6
for31/32, below1e-5. Positive fluid and solid geometry is checked separately.

The [same-mesh comparison](comparison.json) is eligible, but its overall
observable gate still fails: middle-pressure amplitude difference2.5824666%
exceeds2%, although phase0.1834271 degrees passes1 degree. Radial/area
amplitude differences are about2.43229% and flow amplitudes about1.21379%
and1.12796%, all below their5% limits. The reference mean displacement
differs from the circular plane-strain Lamé value by8.31525%, still above
its2% diagnostic target. Geometry, finite-end effects and the independent
space/time/tail/sampling budgets remain unresolved.

[A separate figure](../reference-mesh-nu0-comparison-2026-11-08/README.md)
shows which metrics changed. This is a complete coarse counterfactual,
not a pass for the original nu.3 algorithm or the whole production task.

[1,783 files](manifest.json) were read back and hash-verified from two
archive parts totalling73,984,384 bytes. [Archive metadata](archives.json)
records individual part hashes and the omitted ELF identity. Raw inputs,
accepted results, convergence logs, frozen controller and audit scripts
are retained. The independent S24 mesh-nu0 family is still running/queued.
