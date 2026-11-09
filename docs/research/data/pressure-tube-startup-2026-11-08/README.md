> **轻量进度快照 / 2026-11-09**：此分支只含当前代码、进度、报告和清单。本轮新增的1114个原始压缩包（约22GB）未上传，完整历史与数据保留在本地`codex/fsi-production-48h-20261107`、提交`407c655`。下文“已归档/已提交”的历史记录指该完整本地历史，不表示原始包存在于本快照。后台计算和定时任务已停止，项目验收尚未完成。

# Pressure-tube startup and complete reference convergence

All 6846 archived input, log, checkpoint, field, controller and analysis files
were read back and SHA256 verified. The frozen EONSim executable is b072cc8,
SHA256 2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12.
The reference remains svFSI 7bdb74cdd517310d6bf32c0bb7d42072aeac8658.
Analysis checkpoint c49c69c plus exact captured Python sources; no new C++ build.
The four archives are below GitHub's 100 MiB single-file limit.

The S12/level0 linear elastic tube uses R=1, Rout=1.2, L=12, E=1000,
nu=.3, both densities and viscosity=1, clamped solid/ALE caps and a free outer
wall. Both fluid caps carry .02+.01*sin(t), period 2*pi, N100, generalized-alpha
rho_infinity=.5, default stabilization. Startup ramps are explicit quintics;
no physical parameter, nonlinear tolerance or acceptance gate was relaxed.

| Completed study | EONSim | Reference |
| --- | --- | --- |
| Original startup, 132 cycles | Last two cycle maximum <3.73e-6; periodic/quality pass | All 26400 equation-step rows converge; ALE displacement cycle maximum 1.95256e-5 fails 1e-5 |
| Two-cycle ramp, 12 cycles | Last-two-cycle maximum .0036926; fails | All 2400 final equation rows hit the iteration cap; 1215 fail relative convergence |
| Sixteen-cycle ramp, 32 cycles | Cycle maximum 1.8513e-6; periodic/quality pass | Explicit linear absolute floor 1e-26; all 6400 equation-step rows converge, but ALE cycle maximum 1.94875e-5 fails |

The original long run and ramp2 reference first failed in MPI_Init because an
OpenMPI5 `sm` setting was inherited by the system OpenMPI4 reference. Failed
inputs/logs remain. Recovery copied hash-identical input and cleared OMPI,
PMIX and PRTE runtime options; only the reference was retried. The first ramp2
recovery also exposed a lock-release/status-update race and stopped before a
new solve; its failed controller and receipt are retained.

The ramp16 EON computation completed all 3200 steps before a planned controller
handoff. Termination also ended its read-only audit child without a report;
only that audit was repeated. The reference then used the independently
checked tighter linear floor. The nonlinear relative input limit stayed 1e-10.
The [convergence evidence](../svfsi-convergence-2026-11-08/README.md) distinguishes
process completion, iteration caps and actual relative convergence.

Before comparing the long and ramp16 startup, fixed a 1e-5 maximum-phase
normalized exact P1 field-difference limit, with periodic/quality/convergence
prerequisites. Both selected windows are after their ramps. Only startup
duration differs; no fitted phase shift or pressure gauge adjustment.

| Field | EONSim difference | Reference difference |
| --- | ---: | ---: |
| Fluid velocity | 1.58087e-7 | 1.51047e-7 |
| Fluid pressure | 8.36924e-9 | 2.53307e-8 |
| Fluid mesh displacement | 1.09132e-6 | .00217017 |
| Solid velocity | 1.89028e-6 | 1.79255e-6 |
| Solid displacement | 1.10297e-6 | 1.06621e-6 |

EONSim passes the declared startup comparison. The reference fails both the
mesh-period prerequisite and field-difference limit. This shorter preheat
conclusion applies only to EONSim. Do not omit ALE displacement or infer that
an incremental-mesh formulation alone quantitatively explains the drift.

The long cross-code mid-pressure amplitude/phase differences are about
4.902%/2.658 degrees, failing the unchanged 2%/1 degree gates. Radial/area
amplitude differences about 4.868% and both flow observable gates pass only as
individual diagnostics; the full reference prerequisite fails. Geometry,
space/time, tail and sampling budgets are still required. No elastic or
production qualification, push, PR or publication follows from these data.

Every actual command is in the corresponding archive. Reanalysis controller
`reaudit-elastic-convergence.py` and its frozen helpers are in the final group;
`startup-summary.json` is also copied here. The N200 controller copy records
the next study, not completed N200 evidence. Concurrent serial jobs used
disjoint CPUs8/18; timings are not performance benchmarks.
