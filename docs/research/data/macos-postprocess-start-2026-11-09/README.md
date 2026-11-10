# Completed trajectories entering full postprocessing

Source HEAD 89fa0b6. α2 N800 tau-time control terminal execution exit 0, receipt step 4800; default elastic coarse N1600 terminal controller handle 31036 exit 0, both stages exit 0, accepted 1..51200. These receipts prove solver completion, not physical or numerical-budget qualification.

Started analysis handle 29359: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/analyze_womersley.py --work build/recompute-20261109/alpha2-s96-l1-n800-tautime-n400 --quadrature 4 --output build/recompute-20261109/alpha2-s96-l1-n800-tautime-n400-analysis.json`.

Started full coarse audit handle 31914: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l0-n1600/case.json --work build/recompute-20261109/elastic-s24-l0-n1600 --first-step 46401 --output build/recompute-20261109/elastic-s24-l0-n1600-audit.json`.

First transparent-compression attempt exited 1: ditto returned but pending checkpoint copy was 0 bytes versus original 228240 bytes. Byte check rejected before any replacement (verified_replacements empty); original intact, failed temporary retained. Root cause not established. Revised helper restricts to completed VTU output and runs with required filesystem capability; handle 16153 live, success/capacity gain unproven. Per-file SHA validation remains required.

Eight existing numerical handles 6194,10563,21558,75644,68000,38893,60952,34110 independently polled live. No restart, push or PR. Original default budget failures remain failures. Full analysis, raw capture, tau decomposition, verified archive and N1600 budget still pending.

Update: analysis handle 29359 finished exit 0. All six preliminary gates pass: velocity 0.4711065589%, pressure 0.3367620703%, flow amplitude 0.1836923764%, flow phase 0.05785629565 degrees, maximum net flux 1.5932319161e-17. Raw capture 10627 and actual-field tau decomposition 46523 started, not yet complete. This diagnostic does not replace default-tau acceptance.
