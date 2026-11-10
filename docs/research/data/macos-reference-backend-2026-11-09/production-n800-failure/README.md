# Fresh fine N800 production convergence failure

The independently validated startup prefix is insufficient for long-run adoption.
Frozen log audit of complete steps 1..526 contains 35 failed equation steps and
70 final rows at iteration cap. First unproven convergence is MS at step491
(printed1e-10 equals strict input1e-10); maximum MS ratio is1.4e-10.
The nonlinear cap remains30, no tolerance was relaxed. FS maximum3.5e-11.

The original controller continued because svFSI permits cap exit. The exact
owned process was terminated with SIGTERM after this failed audit; controller
session61527 exited1 and records solver exit-15. No completion receipt exists.
All raw checkpoints/logs remain locally; this failure is retained, not replaced
by the earlier successful 300-step prefix. Other studies continue.

Next: diagnose MS linear/nonlinear residual floor and backend options with
bounded independently checked execution. Restarting past the first invalid
step is not acceptable. Do not rerun or promote this directory.
