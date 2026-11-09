# Separate transient tau sensitivity from time integration

Standalone transient fluid accepts the optional positive finite value
`fluid.stabilization_time_scale`. It replaces only the effective integration
time in the existing estimate

```
tau_K = 1 / sqrt((2*rho_K / t_tau)^2
                + (2*rho_K*|mean(u_accepted)| / h_K)^2
                + (4*mu_K / h_K^2)^2)
h_K = cbrt(6*V_K)
```

Without this option, `t_tau` remains the actual effective integration time:
`dt` for BE, `2*dt/3` for constant-step BDF2 after startup, and
`alpha_f*gamma*dt/alpha_m` for generalized-alpha. The option does **not** change
the derivative, stage time, boundary load, accepted time or checkpoint cadence.
It is a diagnostic control and does not alter the default stabilization rule.
It is restricted to transient standalone fluid, excludes `stabilization_tau`,
and participates in restart identity. No FSI counterpart is introduced here.

For a time-step study, compare three states on one fixed mesh and common phases:

1. Default run with step `h`.
2. Step `h/2`, with `t_tau=2*h/3` for the BDF2 periodic regime.
3. Default run with step `h/2`.

The first difference measures derivative refinement with the explicit tau time
scale held fixed. The second measures sensitivity to that scale at the same
time step. At each phase their **field vectors** sum to the direct difference;
their norms generally do not. This is not a completely frozen tau operator:
the advection estimate still follows each run's accepted solution. Startup
effects must be bounded separately because BDF2 begins with BE. Fixed-scale
results never substitute for acceptance of the default scheme.

The motivating coarse Womersley data at alpha 2 has a 100→200-step velocity
cycle-RMS difference of `.00412730` times the analytical RMS, versus `.00735754`
for the first spatial refinement at 100 steps. Thus its time/parameter effect
is not below the prespecified 10% budget. This evidence motivates a controlled
comparison; it does not establish that tau alone causes the observed error.

`fluid_stabilization_time` checks BE default identity, a real change on a
no-slip pressure-driven cube, 1/2-rank consistency, same-partition restart and
input/signature rejection. A spatially exact uniform accelerating flow checks
all three derivative/load recurrences under a different tau time scale.
Implementation and these new checks await execution at this checkpoint.

Subsequent offline reconstruction from actual BDF2 history found the squared
temporal term contributes66.25% /12.47% on coarse/level1 N100 meshes, while
the maximum squared advection contribution is about1.06e-8 /5.02e-9. Halving
dt at the same accepted field gives volume/phase-mean tau ratios.58293 /.85711.
This coefficient sensitivity supports the planned controlled comparison;
it is not a solution-error estimate. The two N100 histories'200 previous
states matched their separately saved predecessors exactly. Full details and
cadence limitations are in the [evidence](../research/data/womersley-first-2026-11-07/README.md).
