# Oriented circular inlet on a curved elastic tube

A 75° circular arc, 1.5 m long, has a lumen radius of 0.25 m and a wall thickness of 0.05 m. A swept affine Tet4 mesh keeps the fluid and wall interface triangles coincident. The clamped end rings hold the cap geometry fixed. The wall has Young's modulus 100 Pa and Poisson ratio 0.3. The outside carries a normal spring of 20 Pa/m and dashpot of 0.5 Pa s/m. The downstream RCR has proximal and distal resistances of 3 and 8 Pa s/m³ and compliance 0.025 m³/Pa. These numerical parameters exercise transient coupling and reversal.

The inlet specifies the centre, radius and inward vector in global coordinates. Positive prescribed flow enters the lumen. For a face point $x$, centre $c$ and unit inward vector $n$, the shape is $1-\|(I-nn^T)(x-c)\|^2/R^2$. The solver samples it on the inlet vertices and normalizes by the sum of the actual Tri3 normal flux integrals across the MPI ranks. The inlet flow has mean 0.002 m³/s, amplitude 0.003 m³/s, period 0.2 s and startup time 0.04 s. The retained Cartesian form uses `axis` equal to 0, 1 or 2. The vector form accepts a scaled direction under `profile: circle`.

The test runs one copy of each mesh with a Cartesian inlet on one rank, then rotates all geometry to inlet direction (1,2,−3), translates it to (1.25,−2.5,0.6) m and repartitions. It reconstructs both cap fluxes directly from the fluid VTU, applies the rigid rotation to every fluid, mesh and solid vector, and compares scalar pressure and coupled histories. Matching uses the reference positions recovered separately from the two deformed material grids. The following maxima are from 20 accepted steps. Each rotated copy uses the stated number of MPI ranks on one host. The 1-rank Cartesian run supplies the reference. Restarting from a positive Cartesian axis with its equivalent scaled direction reproduces every final field exactly on all five runs. Inputs combining axis and direction, zero/wrong-length vectors, tilted and reversed directions have dedicated rejection checks. [Measured meshes, fields and histories](curved-inlet.json)

| Fluid / solid tetrahedra | Ranks after rotation | Max pressure difference (Pa) | Max fluid velocity difference (m/s) | Max mass defect (m³/s), rotated |
|---:|---:|---:|---:|---:|
| 96 / 192 | 1 | 2.812e-14 | 2.970e-15 | 1.260e-15 |
| 648 / 432 | 2 | 2.173e-14 | 4.511e-15 | 9.945e-15 |
| 648 / 432 | 4 | 1.844e-14 | 3.995e-15 | 9.944e-15 |
| 648 / 432 | 8 | 2.157e-14 | 4.164e-15 | 9.945e-15 |
| 3600 / 1440 | 4 | 1.587e-14 | 5.595e-15 | 2.541e-14 |

Use the locked Release executable produced by the repository build script. A positive bend turns toward the first transverse basis vector selected by the generator. The reference and rotated copies use identical local connectivity. The mesh test checks positive tetrahedra, cap planarity, coincident interface triangulations and axial convergence of the swept polygon volume.

```bash
python cases/fsi/generate_curved.py --output /tmp/eon-curved \
  --sectors 12 --radial 2 --axial 6 --direction 1 2 -3 --origin 1.25 -2.5 0.6
python tests/test_tube_mesh.py
python tests/verify_curved_fsi.py --executable "$eonsim" --mpiexec "$mpi" \
  --work /tmp/eon-curved-frame --ranks 2 --mesh 12 2 6 --steps 20
```

## Nonuniform periodic flow

The same oblique tube accepts periodic, nonuniform time/flow pairs with a late reversal. The three grids traverse five knots, a sign change and a period boundary using 13 unequal time steps. Each run has an independent piecewise formula for the prescribed inlet, a reconstruction of both cap fluxes from the final velocity field and an independent check of the outlet circuit. BE uses one rank. The other two schemes use the listed decomposition. The fourth column is the maximum error over all schemes and steps against the stage and endpoint flow targets.

| Sectors / radial / axial | Ranks | Peak prescribed flow (m³/s, before startup) | Maximum flow error (m³/s) | Maximum restart field difference |
|---|---:|---:|---:|---:|
| 8 / 1 / 3 | 1, 2 | 0.010 | 1.74e−18 | 0 |
| 12 / 2 / 6 | 1, 4 | 0.010 | 1.22e−17 | 8.75e−13 |
| 24 / 3 / 10 | 1, 2 | 0.010 | 8.68e−18 | 0 |

The startup lasts 4/1024 s and the period is 16/1024 s. A checkpoint precedes the period boundary. Resuming with an explicitly closed table reproduces the result obtained with implicit closure. Changing one internal knot fails restart validation. The test also exercises a constant one-knot table and the existing zero-amplitude sinusoid. [Case data, measured fluxes and executable identity](sampled-inlet.json) · [User input example](../../../development/FSI_PERIODIC_FLOW.md#非等间隔流量表)

```bash
python tests/verify_curved_fsi.py --sampled --executable "$eonsim" --mpiexec "$mpi" \
  --mesh 12 2 6 --ranks 4 --work /tmp/eonsim-sampled-inlet
```
