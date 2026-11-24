# Oriented circular inlet on a curved elastic tube

A 75° circular arc, 1.5 m long, has a lumen radius of 0.25 m and a wall thickness of 0.05 m. A swept affine Tet4 mesh keeps the fluid and wall interface triangles coincident. The clamped end rings hold the cap geometry fixed. The wall has Young's modulus 100 Pa and Poisson ratio 0.3. The outside carries a normal spring of 20 Pa/m and dashpot of 0.5 Pa s/m. The downstream RCR has proximal and distal resistances of 3 and 8 Pa s/m³ and compliance 0.025 m³/Pa. These numerical parameters exercise transient coupling and reversal.

The inlet specifies the centre, radius and inward vector in global coordinates. Positive prescribed flow enters the lumen. For a face point $x$, centre $c$ and unit inward vector $n$, the shape is $1-\|(I-nn^T)(x-c)\|^2/R^2$. The solver samples it on the inlet vertices and normalizes by the sum of the actual Tri3 normal flux integrals across the MPI ranks. The inlet flow has mean 0.002 m³/s, amplitude 0.003 m³/s, period 0.2 s and startup time 0.04 s. The retained Cartesian form uses `axis` equal to 0, 1 or 2. The vector form accepts a scaled direction under `profile: circle`.

The test runs one copy of each mesh with a Cartesian inlet on one rank, then rotates all geometry to inlet direction (1,2,−3), translates it to (1.25,−2.5,0.6) m and repartitions. It reconstructs both cap fluxes directly from the fluid VTU, applies the rigid rotation to every fluid, mesh and solid vector, and compares scalar pressure and coupled histories. Matching uses the reference positions recovered separately from the two deformed material grids. On 648 fluid and 432 wall tetrahedra at 20 time steps, the two-rank rotated run differs by at most 2.18e−14 Pa in pressure, 4.52e−15 m/s in velocity and 1.04e−12 m/s² in acceleration. Restarting from a positive Cartesian axis with its equivalent scaled direction reproduces every final field exactly. Inputs combining axis and direction, zero/wrong-length vectors, tilted and reversed directions have dedicated rejection checks. [Measured meshes, fields and histories](curved-inlet.json)

Use the locked Release executable produced by the repository build script. A positive bend turns toward the first transverse basis vector selected by the generator. The reference and rotated copies use identical local connectivity. The mesh test checks positive tetrahedra, cap planarity, coincident interface triangulations and axial convergence of the swept polygon volume.

```bash
python cases/fsi/generate_curved.py --output /tmp/eon-curved \
  --sectors 12 --radial 2 --axial 6 --direction 1 2 -3 --origin 1.25 -2.5 0.6
python tests/test_tube_mesh.py
python tests/verify_curved_fsi.py --executable "$eonsim" --mpiexec "$mpi" \
  --work /tmp/eon-curved-frame --ranks 2 --mesh 12 2 6 --steps 20
```
