# Periodic pressure on a fixed fluid boundary

`fluid.boundaries` accepts `pressure_time` on pressure entries in transient flow:

```json
{"tag":1,"type":"pressure","value":0,"components":[0],
 "pressure_time":{"amplitude":0.02,"period":1.5707963267948966,"ramp_time":0}}
```

The pressure is `S(t)*(value + amplitude*sin(2*pi*t/period))`, where
`S=x^3*(10-15*x+6*x^2)`, `x=clamp(t/ramp_time,0,1)`. Zero ramp duration means
`S=1`. This is the same law used by `fsi.pressure_time`. The standalone boundary
cannot also specify the legacy linear `ramp_time`. Period must be positive;
amplitude, period and ramp duration must be finite, with nonnegative ramp.
Steady flow, solid boundaries, velocity and general traction entries reject this
option. Arbitrary waveform expressions are not implemented.

Natural traction uses the integrator's absolute evaluation time: the new time
for BE/BDF2, and the common stage time for generalized-alpha after its BE startup.
The profile is independent of trial fields. The cached surface residual contains
unit-pressure traction when a profile is present, allowing zero mean pressure.
Legacy entries keep their original cached residual and restart signature.
All profile parameters enter the restart signature; changing them rejects restart.

`fluid.checkpoint_interval` is a positive accepted-step count, default 1. With
`-checkpoint`, states are saved at that cadence and at the final accepted step,
including an explicit `-stop_after` endpoint. Cadence does not alter the physical
signature, so a restart may change sampling frequency. Rejected steps are not
saved. The existing checkpoint format retains each complete generation, its
accepted time and integration history; this provides phase samples for tube
studies without a separate output-state implementation.

`tests/verify_fluid_pressure_time.py` uses a unit cube with slip side walls. Its
uniform velocity and affine pressure satisfy the spatial equations exactly. A
scalar discrete momentum recurrence therefore checks time forcing independently
of mesh or fine-step reference error. It covers BE, BDF2 and generalized-alpha at
1/2/4 ranks, zero mean forcing, startup ramp, accepted-step cadence, same-partition
restart and invalid/mismatched profiles. These are implementation checks, not a
Womersley accuracy qualification. Quantitative tube gates remain in the task queue.

The study runner also records optional execution policies. `--fluid-coo`
selects the existing assembly path. `--mumps` and `--schur` are mutually
exclusive; `--chord` requires either explicit path and reuses the first valid
Jacobian only within each step's fresh SNES. `--velocity-block3` requires
Schur and supplies verified three-component velocity metadata to GAMG.

Separately, `--lu-reuse-window` requires explicit MUMPS. Its default is0
(disabled); a positive window retains an out-of-place LU factor as the
preconditioner for FGMRES, while solving the current operator and checking
the current residual. A new SNES is still created for each solve: an accepted
factor is detached before that SNES is destroyed. A changed effective
integration coefficient forces a collective refresh, including a request
from an empty owner. This execution cache is rebuilt after failure or restart;
it is not accepted integration history and does not enable cross-step
Jacobian reuse.

Nondefault options are frozen into the study definition. They cannot be
introduced by silently resuming an old study; an explicit checkpoint-origin
record and a new study are required. Default study definitions are unchanged.
The [initial cfa5d3c evidence](../research/data/womersley-execution-2026-11-08/README.md)
contains four no-solve metadata/rejection checks and unexecuted preparations
at that historical checkpoint. Subsequent [actual MUMPS entry checks](../research/data/womersley-mumps-entry-2026-11-08/README.md)
and [LU coefficient-refresh checks](../research/data/lu-time-coefficient-refresh-2026-11-08/README.md)
cover fields, histories and their stated clock contracts. The separate
[startup cost screen](../research/data/lu-refresh-startup-cost-2026-11-08/README.md)
records both eligible and rejected policies. These implementation and local
cost checks do not replace long-time physical and error-budget qualification.
