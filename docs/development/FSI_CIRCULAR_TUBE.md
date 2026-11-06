# Circular inlet and solid-wall tube

FSI-PROD-01 adds `fsi.inlet.flow_rate.profile: circle` with finite `center`,
positive `radius`, and `axis` 0/1/2. `mean`, `amplitude`, `period` and the smooth
startup retain the rectangular inlet semantics. Omitted `profile` preserves
`rectangle`, including its old checkpoint signature. Circle and rectangle
geometry parameters cannot be mixed.

```yaml
inlet:
  tag: 1
  ramp_time: 0.01
  flow_rate:
    profile: circle
    axis: 0
    center: [0, 0, 0]
    radius: 1
    mean: 0.01
    amplitude: 0.005
    period: 0.04
```

The inlet is a fixed plane with outward normal equal to the negative coordinate
axis. Nodal shape is `max(0, 1-r^2/R^2)` along the positive axis. Its P1 triangular
surface flux is integrated over owned fluid elements and globally reduced once;
this discrete integral normalizes the profile. Do not normalize by the analytic
circle area: the computational disk is polygonal and the velocity is P1.
All inlet nodes must lie inside the specified disk and in its plane. Shared
clamped interface nodes must have zero prescribed velocity. Changing circle
geometry changes the physics checkpoint signature.

Generate an independent, conforming fluid disk/solid annulus pair:

```bash
python cases/fsi/generate_tube.py --output build/tube --sectors 12 --axial 4 --radial 2
# Build with scripts/cloud/run.sh using the locked PETSc 3.23.7 environment.
build/cloud-3.23.7-release/eonsim -case build/tube/case.json -prepare build/tube/part2 -parts 2
mpiexec -n 2 build/cloud-3.23.7-release/eonsim -case build/tube/case.json -partition build/tube/part2
```

The default synthetic case uses radius 1, thickness .2, length 4, Young modulus
100, Poisson ratio .3, default fluid/solid densities and viscosity 1, Neo-Hookean
solid, clamped solid ends, fixed mesh ends and zero prescribed outlet pressure.
Its units are internally consistent, not calibrated to a patient. The wall's
outer surface has zero natural traction. It uses fixed stabilization tau=.05.
The mesh consists of flat Tet4 facets, not curved high-order elements.

`tests/test_tube_mesh.py` independently verifies positive volumes, exterior
face incidence, exact matching of the two interface triangulations and polygon
volume convergence. `fsi_tube` checks the coupled response, three time schemes,
flow and mass diagnostics, interface constraints, 1/2/4 ranks, full Jacobian,
and same-partition checkpoint/rejection behavior. Test results and actual
commands belong to the session evidence, not this interface specification.

Limits: one fixed axis-aligned circular inlet; no RCR, external tissue support,
prestress, patient calibration, svFSI cross-code agreement or multi-node
performance claim. Quantitative physiological qualification is PROD-02 onward.
