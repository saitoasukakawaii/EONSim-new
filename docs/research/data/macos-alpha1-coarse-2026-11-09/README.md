# Fresh S96 alpha1 coarse N400, macOS, 2026-11-09

This is new computation from zero, not recovery of the omitted Linux raw data.
Solver source is `92fef88ec6c7dad48cfe8a25ecdb79db48f9a8cc`; documentation
checkpoint `e6a01a7` did not change the executable. Environment and initial
validation are in [the runtime record](../macos-recompute-2026-11-09/README.md).

The study completed all 2,400 contiguous accepted steps in six cycles. Two
startup cycles were fully computed; cycles 3–6 saved every accepted state.
All six original solve logs, commands, configurations and receipts are retained
in `attempt-001` through `attempt-006`. The exact initial invocation is recorded
in the linked runtime report. Analysis commands, actually run from repository root:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/analyze_womersley.py --work build/recompute-20261109/alpha1-s96-l0-n400 --output build/recompute-20261109/alpha1-s96-l0-n400-analysis.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 build/analysis-venv/bin/python scripts/compare_womersley.py --coarse build/recompute-20261109/alpha1-s96-l0-n400 --fine build/recompute-20261109/alpha1-s96-l0-n400 --coarse-cycle 5 --fine-cycle 6 --output build/recompute-20261109/alpha1-s96-l0-n400-tail.json
```

Both commands returned 0; that is not physical acceptance. The unchanged
analytic checks give velocity L2 error **0.7059441352%**, pressure RMS/amplitude
**0.8709598692%**, flow amplitude error **1.4470282864%**, phase error
**0.0596533544 degrees**. The flow amplitude still **fails the 1% gate**.
Maximum net flux is `8.08e-18`; both last cycle differences are below `1e-6`.
See [analysis](analysis.json) and [actual cycle 5–6 tail difference](tail.json).

The complete new local raw dataset is 3,250 files / 744,089,529 bytes, individually
hashed in [raw-manifest.json](raw-manifest.json). That manifest records the local
location; it does **not** embed or upload the trajectories. They remain intact
for the subsequent matching fine-grid space/time/tail/sampling budget. No raw
archive from the prior stopped workspace was used. [Completion](completion.json)
explicitly preserves the failed coarse physical gate and pending fine-family work.
