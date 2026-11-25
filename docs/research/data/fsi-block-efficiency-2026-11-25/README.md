# FSI block response efficiency and nodal structural feedback

This is the FSI-PC-03 delivery from main
`296246e53d895f29ea3d0f7e5c960dc26b1426dc`, tracked in
[PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50).
Source changes were pushed before their numerical runs. The final default
implementation is `c4fb266edec94afbf610cb1379dd1595ed96ae40`.
Its local PETSc 3.23.7 Release acceptance passed **9/9**, and the independent
replay of the complete performance campaign passed. CI provenance is recorded
below separately; a documentation commit is not a new numerical execution.

## Delivered behavior

- `-pc_plan_structure_approx nodal` builds the optional structural matrix
  `P_s = K - G H_F E`. Each entity-local inverse in `H_F` includes its active
  fluid velocity and pressure components. Two-sided equilibration handles
  mixed units; pressure-only and distinct RCR boundary entities are retained.
  Numeric refresh shares stable USER matrix handles across main/inner/upper.
- Added-mass fluid responses now default to **PREONLY**, applying their full
  velocity/pressure PC once. Structural `a11` remains the default P and keeps
  its FGMRES `rtol=1e-2, max_it=20` response.
- The coupled twolevel velocity response now defaults to **PREONLY**, applying
  the existing PCMG V-cycle once. Smoothers, coarse solves and coarse-space
  construction are unchanged.
- Both changed leaves retain `rtol=1e-4, max_it=20` for explicit FGMRES
  overrides. Distinct inner/upper solvers still apply their own options.

The complete physical Jacobian, time integration, constraints and physical
acceptance criteria are unchanged. The actual structural action is
`v -> K v - G B_F(E v)`, where `B_F` is the configured approximate fluid
response. Changing the fluid response changes this approximate action; the
Schur object must not be described as applying an exact fluid inverse.
Tolerance-dependent coarse solves can make even one PC application variable.
The complete-system outer solve remains FGMRES.

The nodal structural matrix passed its correctness checks, but the measured
arterial screening did **not** establish a useful performance advantage. It
remains an explicit experimental option. The adopted speed improvements come
from reducing nested response work, not from promoting that matrix to the
default.

## Source and execution provenance

| Source | Executed work | Result |
|---|---|---|
| `664a6238ab08a42639a6c180addc99ddbf38886b` | Initial nodal implementation: `pc_plan_mpi1/2/4` | 3/3 passed, clean Release |
| Same source | `fsi_tube_rcr`, `pc_added_mass_nodal_retry`, original `fsi_block_efficiency` screening | 3/3 passed; the screening contains 12 four-step runs |
| Same binary, bounded probes | Nodal P with iterative structure; a11 with one fluid PC application, coarse grid only | Both four-step probes passed; their single samples are not timing medians |
| `66b0a62af6575d8a98d85b7c90d88d6e22666439` driver, unchanged `664a623` production binary | Selected quick plus full campaign | 72/72 runs passed |
| `c4fb266edec94afbf610cb1379dd1595ed96ae40` | Final PREONLY defaults and strengthened default/override oracles | 9/9 local checks passed, clean Release |
| Same pushed source | Independent standard-library archive replay | Passed; no solver execution |

The campaign explicitly fixes both old and candidate solver types and
budgets. Its binary predates the two default-type changes; this is deliberate
and recorded, not a claim to have rerun that campaign with a rebuilt c4fb266
binary. The final default paths were compiled and exercised by the last row
of local numerical checks and by the affected CI selection.

Campaign executable SHA256:
`654f809bc2e273d0c74d77ea2813859a7ca0ee2044e0f2729f4b20e8a113aed9`.
The final rebuilt executable hash is in
[default-archive-metadata.json](default-archive-metadata.json).
The fixture archive SHA256 is
`662518aa06f1d9f3072c92910fcfd08c3788f0be8bf0875ec035ff6e0984fae6`.
The three exact driver/helper snapshots and their hashes are inside the
campaign archive and recorded in [replay-result.json](replay-result.json).

### Final local acceptance

The exact selection is [default-tests.json](default-tests.json); the unedited
runner receipt is [default-summary.json](default-summary.json). All build,
runtime-linkage, MPI preflight and CTest commands exited zero. The CTest wall
time was 72.71 s; this is a correctness batch, not a performance comparison.

| Check | Result | Scope |
|---|---|---|
| `pc_plan_mpi1`, `pc_plan_mpi2`, `pc_plan_mpi4` | 3 passed | Independent nonsymmetric matrices; mixed-unit inverse; numeric refresh; empty rank; default PCApply action; explicit main/inner/upper overrides; failure propagation |
| `fsi_tube_rcr` | Passed | Existing direct BE/BDF2/alpha checks plus two-rank alpha added-mass, nodal-structure and twolevel continuation |
| `pc_added_mass_retry`, `pc_added_mass_nodal_retry`, `pc_twolevel_retry` | 3 passed | Actual nonlinear cutback, same small-step direct reference and same-partition restart on 1/2 ranks |
| `pc_recipe_restart` | Passed | Existing recipe restart checks; added-mass/twolevel FSI branches on two ranks |
| `pc_recipe_hybrid` | Passed | Existing 1/2/4-rank baseline; added-mass nodal and quantity-twolevel variants on two ranks for rigid, elastic-domain and Neo-Hookean cases |

The largest field difference among the newly checked two-rank added-mass,
nodal-structure and twolevel variants was `2.28650431921551e-12`, below that
test's unchanged absolute `2e-8` limit. Every recorded target response had the
expected default type, and each rank's observation total matched the number
of solver reports. These small-fixture absolute errors
are distinct from the arterial relative field-peak metric below.

Actual entry point, from the repository root:

```bash
scripts/cloud/run.sh 3.23.7 release explicit \
  /workspace/scratch/6d25aa929185/pr42/.cloud \
  build/ci/fsi-efficient-defaults.json
```

The last argument had exactly the contents of `default-tests.json`. That
absolute dependency prefix records this execution; a new installation must
use its own restored locked prefix. No Debug, PETSc 3.19.6, or full-suite local
run was added for this task.

## Performance campaign

The pinned 20 mm tube uses 80 Pa smooth loading, generalized-alpha
`rho_inf=0.5`, `dt=1/32` s and 32 steps. Both candidate and reference runs use
the same equations, material parameters, constraints, partition and load.
The coarse grid has 1,027 DoFs on one rank with natural local factor ordering;
the fine grid has 3,024 DoFs on two ranks with RCM. This is not a strong-scaling
experiment because the grid and rank count change together.

Environment: Intel Xeon Platinum 8573C, Linux 6.18.57 x86_64, 9 CPUs in the
reported affinity/budget and 10,451,423,232 bytes memory budget; PETSc 3.23.7,
Open MPI 5.0.8, GCC 15.3.0 and OpenBLAS 0.3.34. OMP/OpenBLAS/MKL threads were
one. Each sample was a fresh MPI process with `--map-by core --bind-to core`,
`OMPI_MCA_pml=ob1`, `OMPI_MCA_btl=self,sm,tcp`. No other local numerical job was
launched during the campaign; exclusive physical-host ownership is not claimed.

Each of six modes on both grids completed a four-step quick run, a full
32-step trajectory, one four-step warmup and three interleaved four-step
timing samples: **72 runs, 624 accepted steps, 1,248 linear corrections**.
The twelve full trajectories contribute 384 steps and 768 corrections.

Every correction must satisfy the recomputed complete-Jacobian residual
target `max(1e-23, 1e-10*rhs_norm)`, with the unchanged `1.00001` comparison
margin. Five physical fields are compared on owned nodes at every saved
state against the direct reference, with relative peak limit `2e-6`.
The maximum residual/target ratio was **0.5547250920882967**; the maximum
relative field-peak difference was **3.138204081400456e-11**. No tolerance or
physical gate was relaxed for timing. `-linear_report` itself is diagnostic;
the extra true-linear-residual threshold is enforced by the verifier.

### Three-sample medians

Times are seconds. Linear intervals include PC setup and all nested solves.
Wall time includes MPI launch, the same diagnostics/output and log read.
`setup_seconds` is nonlinear-solve initialization, not all PC setup.
Inner iteration observations are last-call snapshots, not accumulated inner
iterations. Each median is calculated independently from the three samples.

| Mode | Coarse outer | Coarse linear | Coarse wall | Fine outer | Fine linear | Fine wall |
|---|---:|---:|---:|---:|---:|---:|
| Direct | 8 | 0.060408 | 0.365677 | 8 | 0.257188 | 0.716814 |
| Coupled nodal | 331 | 0.167959 | 0.567337 | 645 | 1.014540 | 1.569494 |
| Added mass, old fluid FGMRES20 | 179 | 6.482707 | 6.885585 | 354 | 44.477524 | 45.057488 |
| Added mass, fluid PREONLY | 332 | 0.974291 | 1.368866 | 661 | 6.506006 | 7.148527 |
| Twolevel, old velocity FGMRES20 | 288 | 0.614463 | 1.017857 | 563 | 3.931200 | 4.585011 |
| Twolevel, velocity PREONLY | 380 | 0.119125 | 0.515940 | 682 | 0.609956 | 1.237586 |

The added-mass linear intervals improve by factors of about 6.65 and 6.84;
twolevel improves by about 5.16 and 6.45. More outer iterations accompany
less elapsed work. Added mass still costs more than the coupled-nodal baseline
on these grids, and direct factorization remains fastest. These observations
do not establish universal speedup, mesh-independent iteration counts or
multi-node scalability.

### Negative findings and verifier correction

The original 664a623 single four-step screening gave fine-grid linear times
of 49.117077 s for a11/iterative structure, 68.456574 s for a11/structural
PREONLY, and 65.788333 s for nodal/structural PREONLY. The nodal matrix is
implemented correctly but is not a demonstrated efficient default. Its
local fluid blocks must be invertible; there is no automatic regularization,
pressure pin or fallback. RCR feedback can introduce port-wide fill.

The initial parser controls exposed one false pass: an incorrect early KSP
type was hidden by a later correct snapshot. The initial 21/22 result is
retained. Driver 66b0a62 checks every required observation and requires each
rank's total to equal the accepted-step count; the expanded **25/25**
positive/negative controls then matched expectations. The independent replay
additionally requires exactly one target observation per rank in each
accepted-step interval, and checks root and target KSP/PC
reasons, allowing bounded iterative ITS but rejecting genuine breakdowns,
PC failures and negative PREONLY reasons. These are verifier corrections,
not changes to physical tolerances.

## Archived evidence and independent replay

[evidence.tar.xz](evidence.tar.xz), **4,678,856 bytes**, SHA256:

```text
c5d141d7881790c670c991f23c30763be197fa197003f1983e2f60b2f7d3b1dc
```

The archive contains 2,635 payload files plus its root manifest, preserving
repository-relative paths and original JSON bytes. [manifest.json](manifest.json)
is the same manifest outside the archive; [archive-metadata.json](archive-metadata.json)
records packaging scope. Its `not_executed_pending_source_push` field records
the packaging-time state; the subsequent actual result is
[replay-result.json](replay-result.json).

Included paths cover `build/diagnostics/fsi-efficient-66b0a62/campaign/`, its
two stdout logs, environment, exact source snapshots, initial 664a623
screening/probes, original algebra/physical receipts, and failed/corrected
parser controls. Binaries and partition trees are excluded. Initial screening
and historical controls are hash-verified, not counted in the selected
campaign's numerical replay totals.

[replay.py](replay.py) uses only the Python standard library. It does not run
the solver or import archived verification code:

```bash
python3 docs/research/data/fsi-block-efficiency-2026-11-25/replay.py \
  --archive docs/research/data/fsi-block-efficiency-2026-11-25/evidence.tar.xz \
  --sha256 c5d141d7881790c670c991f23c30763be197fa197003f1983e2f60b2f7d3b1dc \
  --work build/replay-fsi-efficiency
```

The work directory must not exist. The actual c4fb266 execution used
`build/diagnostics/fsi-efficient-c4fb266/replay` and exited zero. It verified
all file hashes, all 72 run labels, 1,248 corrections, 2,028 required solver
observations, 468 distinct volume VTUs, 156 saved states and 780 field
comparisons. The field count includes the direct reference's self-comparisons;
there are 650 comparisons against non-direct modes. Raw phase-time sums and
sample medians are recomputed. External wall time is checked for finite
recorded values and recomputed medians; replay cannot reconstruct elapsed time.

[default-validation.tar.xz](default-validation.tar.xz) separately preserves
the c4fb266 build/CTest receipts and test outputs written during that final
run. Its manifest records the exact regular-file inventory and hashes;
[default-archive-metadata.json](default-archive-metadata.json) gives its
source, executable hash and archive hash. Earlier untouched files in reused
test directories were excluded by the recorded output timestamp boundary.
The performance archive is unchanged by this later acceptance batch.

## CI and delivery

The four required source checks passed for head `c4fb266`:
[core run 45622859538](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45622859538)
and [website run 45622859337](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45622859337).
Release executed **15 affected tests, all passed**, and reused **39** compatible
prior receipts; the complete required selection therefore covers 54 tests.
No Python test was newly selected by this source delta. Debug and PETSc 3.19.6
were deliberately skipped under the repository policy.

The PR CI checked GitHub's merge commit
`aa248d65e884792539da2616fb80050e2e7f1134`, whose head is c4fb266 and base is
296246e. [ci-source-c4fb266.json](ci-source-c4fb266.json) preserves the exact
selection, new/existing origins, successful release summary, run/job states
and four required branch-protection contexts. The last documentation head
must receive its own successful checks; these source receipts do not preclaim
the outcome of a later head.

The final protected head must pass selection, PETSc 3.23.7 Release, incremental
evidence recording and Build VitePress before the authorized head-locked
squash merge. No protected check, numerical threshold or review rule is
bypassed. The algorithm explanation remains an unpublished
[website draft](../../../../website/drafts/fsi-schur-response-cost.md).

## Reproduce the selected comparison

From the recorded locked environment, the two commands used the same work
directory and exact mode list; full requires a matching successful quick
receipt. The launcher and executable are explicit in every archived command.

```bash
python3 tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim --mpiexec "$(command -v mpiexec)" \
  --work build/fsi-efficiency-reproduction --stage quick \
  --modes coupled_nodal added_mass added_mass_fluid_onecycle \
    twolevel_iterative twolevel_onecycle
python3 tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim --mpiexec "$(command -v mpiexec)" \
  --work build/fsi-efficiency-reproduction --stage full \
  --modes coupled_nodal added_mass added_mass_fluid_onecycle \
    twolevel_iterative twolevel_onecycle
```

`direct` is included automatically. The archived 66b0a62 driver snapshots and
664a623 production source identify the historical experiment; rebuilding and
running them is a new measurement, whose new executable hash must be recorded.
The independent replay above verifies the exact stored measurements without
requiring the old binary.
