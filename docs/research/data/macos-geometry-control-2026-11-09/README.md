# Fixed topology geometry control: prepared and smoke-tested

Actual fresh WomersleyS96 and elasticS24 level0/1 meshes were compared with
the complete deterministic midpoint refinement: every node,cell andtag matches.
Independent summed tetra volumes match regular polygon volumes and do not
change under refinement. Area deficits versus circle are .0713794% and1.138407%.
These are geometry metrics, not solution-error estimates.

Separate elastic geometry control maps each original S24 level1 node radially:
(y,z)*=cos(theta-theta_c)/cos(pi/24), with theta_c the seed-sector midpoint;
x and the center remain unchanged. This gives a48-sided boundary while
retaining4225 fluid/3600 solid nodes,20736/13824 cells and all connectivity/tags.
All cells positive,1200 interface nodes match; fluid/solid volumes match the
independent48-sided analytic volumes. Original inputs are hash-unchanged.
Area deficit becomes .2853343%. The transported discrete basis and geometry
interact, so a future response difference is not an exact continuum error.

Probe87939 completed8 fresh steps in7.35s/583401472B, original solver/tolerances
and generalized-alpha/16cycle ramp, positive endpoint Jacobians. This proves
input/solver smoke only. Full32cycle geometry response is not started, pending
storage scheduling. The supplied controller consumes only the validated input,
uses corrected restart PVD collection and retains existing resource limits.
Do not feed projected geometry into the unchanged same-polygon space budget.

Commands: `python3 build/recompute-20261109/audit-fresh-mesh-geometry.py`,
`python3 build/recompute-20261109/prepare-elastic-geometry-control.py`,
`python3 build/recompute-20261109/probe-elastic-geometry.py`; all exited0.
The probe enforces one OMP/BLAS thread and copied input hashes. No original
trajectory or solver implementation was changed.
