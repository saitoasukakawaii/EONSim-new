# A pressure–area reference for an elastic tube

An equal positive pressure on both fluid ends expands the wall while the fluid approaches rest. The reference uses a quarter of a straight tube, bore radius $a=1$ m, outer radius $b=1.2$ m and length $L=2$ m. Young's modulus is 100 Pa, Poisson's ratio is 0.3, and the inner and outer pressures are 0.02 and 0 Pa. The reference bore displacement is 0.001087272727 m. The resulting first-order relative area increase is 0.002174545455. All dimensions and materials are synthetic.

## Analytic equilibrium

Let $r$ denote distance from the tube axis. Radial equilibrium gives
`dσᵣ/dr + (σᵣ − σθ)/r = 0`. The plane-strain isotropic elastic solution has
`σᵣ = A − B/r²` and `σθ = A + B/r²`. The conditions `σᵣ(a) = −pᵢ` and
`σᵣ(b) = −pₒ` determine

$$
A=\frac{p_i a^2-p_o b^2}{b^2-a^2},\qquad B=\frac{a^2 b^2(p_i-p_o)}{b^2-a^2}.
$$

The symmetry planes constrain the normal component of displacement. Both axial ends constrain only axial displacement, permitting radial expansion. The analytic solution has zero axial strain throughout. Hooke's law gives `σₓ = ν(σᵣ + σθ)` and the hoop strain `uᵣ/r`, hence

$$
u_r(r)=\frac{1+\nu}{E}\left[(1-2\nu)Ar+\frac{B}{r}\right],\qquad
\frac{\delta A}{A}=\frac{2u_r(a)}{a}.
$$

At zero outer pressure the inverse bore compliance is `E(b²−a²)/[(1+ν)a((1−2ν)a²+b²)]`. This independent implementation gives the same closed form in its elastic limit. [TensorMesh thick cylinder, analytical references](https://github.com/camlab-ethz/TensorMesh/blob/1b0af5b909956dacc8bf267f5f82b19eb6cb2f40/examples/solid/plasticity_cylinder/README.md#analytical-references)

## Measuring compliance on Tet4 meshes

`cases/fsi/generate_tube.py` accepts a positive `--wall-layers`. Concentric solid rings preserve the existing fluid–solid interface. Both studies keep the positive-y, positive-z quarter mesh and tag its two new symmetry faces. Sector counts in all tables refer to the complete circle. For the isolated elastic solve, positive bore pressure produces traction `−pᵢ n` on the reference inner surface, with zero exterior traction.

At each axial mesh plane, sort the bore nodes by polar angle. The oriented polygon area is half the sum of `yᵢzᵢ₊₁ − zᵢyᵢ₊₁`. The two straight edges to the axis have zero contribution in both configurations under symmetry. Differentiate the polygon sum in the direction of the computed displacements to obtain the linearized area change. Normalize by the reference **polygon** area at that plane. The report also records the finite deformed area, edge-length-weighted mean radial displacement, and the worst axial-section error. Using the reference polygon removes its initial area deficit from the strain measurement. Flat facet normals and interpolation still affect the solution.

For the isolated wall the error in the displacement vector uses an 11-point degree-four tetrahedral quadrature of the squared errors on the discrete domain. The analytic displacement includes $1/r$, so this norm is evaluated by quadrature. The work check integrates the applied reference pressure traction against displacement and compares it with twice the strain energy. The regression includes an affine patch with equal inner and outer pressures, which eliminates the inverse-radius term.

## Monolithic fluid–structure cases

The ALE fluid has density and viscosity one in SI units, and the solid density is one. The two fluid ends receive equal positive pressure tractions and the two subdomains share a conforming interface. The outer solid boundary is free. Both symmetry planes enforce zero normal fluid velocity and mesh displacement. The end planes constrain axial mesh displacement. Use the regular `fsi` driver with a linear wall, initialized from rest. In the backward Euler series the pressure starts at zero, ramps over one second and then holds. Measurements use the final field and the preceding solid field. The pressure error is a fluid-volume RMS, normalized by the imposed pressure. The velocity and interface checks use maxima. A moving-domain audit integrates actual end/wall fluxes and recomputes the sum of deformed tetrahedral volumes at each saved step.

For the external pair, use a constant pressure from the initial step, the same cells, wall, supports and fluid parameters, `dt=0.5` s, `T=12` s and generalized-alpha spectral radius 0.5. The external input projects the two interface faces and solves FSI (fluid plus linear elasticity) and mesh equations. The reader checks the two domains and their tetrahedral connectivity, distinguishes the mechanical and mesh displacement arrays, and checks the full iteration history of both equations. The external stopping criteria and per-case linear solver controls are stored with each input. Both time integrators and mesh-motion operators may produce different transients. The comparison uses the settled pressure–area response. [Upstream pipe input](https://github.com/SimVascular/svFSI-Tests/blob/c38514ff7d7128583ec530971080dd0fac8026bf/07-fsi/ale/03-pipe_3D/svFSI.inp)

## Running a new measurement

Use fresh case directories, the locked Release build and its MPI launcher. The study writes the generated mesh, physical parameters, solver output and diagnostics. The external executable must be built from svFSI 2022.09.26 at commit `94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571`. Python VTK 9.3.1 reads its binary VTU files.

~~~bash
exe=build/cloud-3.23.7-release/eonsim
python3 scripts/study_lame_wall.py --executable "$exe" --work build/lame48 --mesh 48 4 6 --check
python3 scripts/study_hydrostatic_fsi.py --executable "$exe" --work build/hydro48 --mesh 48 4 4 6 --dt 0.5 --duration 12 --check
python3 scripts/audit_hydrostatic_mass.py --work build/hydro48
python3 scripts/study_hydrostatic_fsi.py --executable "$exe" --work build/paired48 --mesh 48 4 4 6 --dt 0.5 --duration 12 --matched-svfsi-rho 0.5 --check
python3 scripts/compare_svfsi_wall.py --case build/paired48 --work build/external48 --executable /path/to/svFSI --check
~~~

The measured convergence, MPI checks, time histories, failed attempts and raw field archive are available together. [Results and replay](../research/data/lame-wall-2026-11-20/README.md)
