# Mesh increment normal-path equivalence

Diagnostic55589 completed0. Fixed-source vs mesh-increment-only derivative:
coarseN400 startup20 and loaded12401..12420, followed by derivative replay
12411..12420 from its actual checkpoint. All original convergence gates pass.
50 paired five-field/native states pass original node2e-9/P1mass1e-8/history2e-9.
Largest loaded deltas: node2.74087e-16, mass4.20231e-14, history8.33908e-14.
Saved time and equation norms exact; ten-step replay exact for all compared
fields/history. Independent struct decoding reconfirms all50 native pairs,
checks replay bytes except elapsed diagnostic, and binds all consumed raw files.

Commands: `build/analysis-venv/bin/python
build/recompute-20261109/screen-reference-mesh-increment-equivalence.py`
and `python3 build/recompute-20261109/review-reference-mesh-increment-equivalence.py`.
First command uses OMP/OPENBLAS/VECLIB threads1. Both exited0.
Version/binary/patch hashes are frozen in definition. No source-stop patch,
no production adoption, no whole-trajectory or fine-mesh claim from this test.
