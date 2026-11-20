# Pressure-to-flow verification in an oscillating rigid tube

The reference BDF2 run on 48 sectors, 8 radial rings and 12 axial slabs had
1.5047% amplitude error, 0.2858° phase error and 1.5864% relative waveform
RMS error. On the same 25,920 tetrahedra, a separate generalized-alpha run
and upstream svFSI differed by 2.0395% of the analytical flow amplitude.
These results apply to the synthetic rigid circular-tube problem at α=2.
[Boundary model, reference solution and commands](../../../development/WOMERSLEY_FLOW.md)

![Last-cycle flow and normalized error for EONSim and svFSI](waveform.svg)

## Quantities and acceptance

All flow signs refer to positive x except the explicitly outward boundary
integrals. Fit the last complete cycle of `(Qout−Qin)/2` to sine and cosine
at every accepted endpoint. Normalize the complex comparison and intercycle
maximum change by the circular reference amplitude 0.00323951534417 m³/s.
Normalize the waveform RMS by the RMS of the analytical waveform on those
same phases. Pressure averages use the discrete P1 trace with the absolute
level fixed by boundary stress.

| Quantity | Predeclared limit | 48/8/12, 64 steps/cycle, 3 cycles |
|---|---:|---:|
| Flow amplitude error | <2% | 1.504734% |
| Flow phase error | <2° | 0.285763° |
| Waveform relative RMS error | <3% | 1.586417% |
| Maximum cycle 3 vs. 2 difference | <0.1% | 0.004873% |
| Maximum absolute net outward flux | <1e−10 m³/s | 1.995e−17 m³/s |

The 24/4/4 configuration at 48 samples and the 32/6/6 configuration at 64
samples missed the amplitude gate with 2.65% and 2.33% error. A 48/7/8
grid at 64 samples also missed at 2.12%. The checks use the original limits.
The much smaller CTest checks loading stages, accepted diagnostics, MPI and
restart. Its coarse flow target serves as a regression check.

## Pressure, velocity and conservation

At step 144 (positive pressure peak), the quarter-cycle field had velocity
relative L² error 1.1855% over the polygonal fluid domain. The velocity
integral uses 27 positive Gauss points per tetrahedron. Increasing this to
64 points gave 1.1888%. The P1 pressure square integrates exactly and yielded
RMS pressure error 1.0523% of the imposed drop amplitude. At step 176 the
respective errors were 1.1855% and 1.0522%. At the final zero-pressure phase
they were 0.9179% and 0.3376%. The no-slip wall velocity was zero in the VTUs.

The fitted computed end-pressure difference had amplitude 0.0184844 Pa,
7.58% below the applied 0.02 Pa. The slice integrals localize part of this
effect. At the positive load peak the means at x=0, 1 and 2 m were 0.0192128,
0.0100203 and 0.0007367 Pa against 0.02, 0.01 and 0 Pa. Axial flux at the
two ends was 0.00275852 m³/s and at midspan 0.00267533 m³/s. The RMS element
divergence at this phase was 6.6994e−5 s⁻¹. The fitted end-flux target and
the local velocity, pressure and divergence diagnostics address different
quantities. The pressure trace has no acceptance claim.

## Independent solver

Both solvers used the identical Tet4 connectivity, coordinates, zero initial
velocity, unit density and viscosity, zero backflow term, fixed no-slip wall
and the same mixed end constraints. The pressure sine acts on the normal
component. The generalized-alpha spectral radius is zero so both load stages
are at the endpoint. Spatial stabilization, algebraic tolerances and startup
implementations are specific to the two codes. Files were exported with VTK
scalar connectivity, one-based parent IDs and outward-oriented boundary
triangles. The upstream Fourier convention is `r cos − i sin`, including the
zeroth coefficient. Its original linear and nonlinear solvers were used.
[svFSI source revision](https://github.com/SimVascular/svFSI/tree/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571)
· [Fourier evaluation](https://github.com/SimVascular/svFSI/blob/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571/Code/Source/svFSI/FFT.f#L133)
· [Nonlinear stopping rules](https://github.com/SimVascular/svFSI/blob/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571/Code/Source/svFSI/PIC.f#L257)

| Mesh, samples per cycle | Complex flow difference / analytical amplitude | 5% criterion | Endpoint velocity L² difference / EONSim norm | Endpoint pressure RMS difference / 0.02 Pa |
|---|---:|---|---:|---:|
| 12/2/3, 16 | 8.7814% | Miss | 4.1432% | 0.3306% |
| 48/8/12, 64 | 2.0395% | Pass | 0.3160% | 0.1400% |

For the 48/8/12 case, svFSI's error against the circular reference was
0.4947% in amplitude and 0.0565° in phase. Its maximum last-cycle change
was 0.00556%. The final nonlinear residual satisfied one of svFSI's two
normalizations at every step, with maximum 4.85e−9 versus tolerance 1e−8.
There were 50 zero-iteration GMRES returns when the nonlinear target had
already been reached. The parser rejects a failed positive-iteration
linear solve, missing step or unconverged final normalization. The final
binary VTU independently reproduced the external end-flow and mean-pressure
tables to their printed precision.

## Reproduce and inspect

The EONSim C++ solver used commit `62c0b2fc0b59d5377e1a085a8f4e94ac4b5eb209`.
The field and cross-code tools used `bef75bda4c6674452757cee3629a38854f34807e`.
The baseline checkpoint binary came from `89a1a3d823396df02fa9e8acb5ded36b70938e9c`.
PETSc 3.23.7 was real/double with 32-bit indices, Open MPI 5.0.8 and GCC
15.3.0. The shared machine had four CPU cores of quota and 16 GiB of memory.
The EONSim binary SHA-256 was
`9ad78529a9ab73aa9cb814bcf72aa549c36d9ba9a32de70cdebdd8e2ccaffef5`.
The svFSI 2022.09.26 binary SHA-256 was
`76fa8bccbe419b4c8cf95d40c74b64290d2b55079750e7f44ef270f7c8760c06`.

```sh
# From the EONSim repository root. The destination can be anywhere.
d=docs/research/data/womersley-2026-11-20
mkdir -p /tmp/eonsim-womersley-raw
tar -xJf "$d/raw.tar.xz" -C /tmp/eonsim-womersley-raw
python "$d/replay.py" /tmp/eonsim-womersley-raw --verify --output /tmp/wom-integrals.json
# The additional external VTU audit used vtk 9.3.1.
python "$d/replay.py" /tmp/eonsim-womersley-raw --verify --fields --output /tmp/wom-fields.json
python "$d/plot_waveform.py" /tmp/eonsim-womersley-raw /tmp/wom-waveform.svg
```

The raw archive contains the Gmsh volume meshes, case inputs, every accepted
boundary row, the audited VTU fields, the matched external inputs and
histories, the baseline checkpoint generations and both legacy endpoints.
The manifest authenticates each extracted file. The JSON results include
the coarse misses as well as the gated cases.
[Inputs and raw outputs](raw.tar.xz) · [File digests](manifest.json) · [Recomputed metrics](results.json)

Use a separate compiler environment for the external Fortran solver. The
unmodified Fortran/C/C++ sources were built on Linux with GNU 15.3,
Open MPI 5.0.8, CMake 3.x, Ninja, BLAS, LAPACK and zlib. Set `svprefix` to
that environment and issue the following commands from a checkout of svFSI.

```sh
git checkout 94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571
cmake -S Code -B build-wom -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$svprefix/bin/gcc" -DCMAKE_CXX_COMPILER="$svprefix/bin/g++" \
  -DCMAKE_Fortran_COMPILER="$svprefix/bin/gfortran" -DMPI_C_COMPILER="$svprefix/bin/mpicc" \
  -DMPI_CXX_COMPILER="$svprefix/bin/mpicxx" -DMPI_Fortran_COMPILER="$svprefix/bin/mpifort" \
  -DCMAKE_PREFIX_PATH="$svprefix" -DSV_USE_TRILINOS=OFF
cmake --build build-wom --parallel 2
```

Two initial interoperability attempts are archived. The upstream ASCII
reader inferred one index per tetrahedron. A trial vector-connectivity
workaround was rejected by the standard VTK reader and the trial NS solver
reported a singular projected system. The accepted comparisons use standard
appended binary arrays, GMRES and explicit convergence checks. Two local
regression harness faults (a non-string argument and an incorrect mesh lookup)
are also retained with the corrected test receipts.

The current study measures flow, pressure and velocity for a stationary rigid
wall. The production roadmap retains compliant-wall pressure/area response,
material matching and multi-node verification as separate work.
[Production FSI roadmap](../../../development/FSI_PRODUCTION_ROADMAP.md)
