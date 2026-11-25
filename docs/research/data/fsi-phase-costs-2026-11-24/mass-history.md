# Mass conservation history on a moving tube

EONSim measures the lumen volume, inlet and outlet flow, outward wall flux and integrated divergence on owned fluid cells. The stage and accepted endpoint remain distinct in generalized-alpha. Backward Euler and BDF2 use the same physical state for both observations. The volume secant uses the preceding accepted endpoint, including the first step after a checkpoint.

The mesh setup now classifies each boundary face once. An active history integrates two states on a generalized-alpha step and one on a backward Euler or BDF2 step, plus the preceding state on the first observed step. A single collective propagates local exceptions and one sum reduces the measurements for the step. The previous implementation performed a separate exception check and sum for each of the three states. With mass history disabled, these cell integrations and collectives are skipped. Geometric validity and the current cap flow needed by moving RCRs still run on accepted steps. [Implementation](../../../../src/physics/fsi.cpp)

## Paired observations

The fixture has an elastic circular tube with an expanding outlet and nine accepted steps of 0.005 s. Both versions solve the same input. The baseline adds only the PETSc timing event to the previous executable. Each row summarizes five paired runs, with the executable order reversed on alternate repetitions. Timings cover the maximum-rank elapsed time for the mass observation over all nine steps. The shared host also carried independent solves.

| MPI ranks | Scheme | Median paired new/old time with history | Paired range | Maximum field or history change |
|---:|---|---:|---:|---:|
| 1 | Generalized-alpha | 0.486 | 0.026–8.173 | 0 |
| 2 | Generalized-alpha | 0.443 | 0.033–3.254 | 0 |
| 1 | Backward Euler | 0.197 | 0.019–0.348 | 0 |
| 2 | Backward Euler | 0.211 | 0.009–1.216 | 0 |

With history disabled the baseline executed the timed observation nine times on every rank. The new version executed it zero times. All 40 before/after pairs reproduced every final nodal field and every emitted history value. Shared-host timing varies considerably, especially for generalized-alpha. The counts and complete numerical comparisons can be replayed independently. [Per-rank events and physical comparisons](mass-history.json) · [Paired timing table](mass-history.csv)

The moving-port regression also checks the first volume secant after restarting from a checkpoint with diagnostics disabled and after a rejected time step. [Restart and retry regression](../../../../tests/verify_fsi_moving_port.py)

## Reproduction

Apply the observer patch to baseline commit `4e6e43f5af97364c7bbed0fc1ded3dbac78e0542`. Build both executables with the repository PETSc 3.23.7 Release compile script, using an explicit numerical selection that builds the `eonsim` executable. [Baseline timing patch](mass-baseline-event.patch) · [Measurement driver](mass_history.py)

```bash
python mass_history.py --baseline "$before" --optimized "$after" --mpiexec "$mpi" \
  --work "$work" --pairs 5 --ranks 1 2 --steps 9 --write-archive "$work/measurements-full.json" --csv "$work/timings.csv"
python mass_history.py --archive mass-history.json --csv "$work/replayed.csv"
```
