# Explicit length input and fresh finite-end computation

Based on2c0f392 plus the recorded generator hash. The generator accepts an
explicit finite positive length; default12 and every one of eight generated
files remain byte-identical to the prior source. Actual command
`python3 tests/test_pressure_tube_audit.py` passed11 tests, including a matched
axial-spacing length pair and invalid-length rejection before file creation.

A new S24/L1/N800 length24/axial24 study has started from zero, with full32cycles
and16-cycle ramp. Actual generated domains preserve refined axial spacing0.5,
double volumes, and identical case-level material/load/time settings compared
with length12/axial12. This does not establish finite-end qualification.

Actual launch (one OpenMP/BLAS thread):

```sh
build/analysis-venv/bin/python build/recompute-20261109/run-elastic-length.py --work build/recompute-20261109/elastic-s24-l1-n800-length24 --level 1 --n 800 --length 24 --axial 24
```

The separately frozen controller includes the corrected restart PVD filename;
active prior controllers were not modified. Limits remain3GiB RSS,20GiB free
disk and24h per phase. Its definition records both generator and controller
hashes because the generator change was not yet committed at launch.

The original N800 elastic budget kernel is also wired to fresh local inputs
without any arithmetic or threshold changes. Preflight rejected the still
missing fineN400 audit/receipt before creating any budget output directory.
This is an expected incomplete-data refusal, not a budget pass or numerical
failure. The prepared wrapper is retained; actual budgets remain unrun.
