# Fresh recorded-patch reference production family (running)

The user permits recorded, validated patches. Adoption checks completed0:
fixed base7bdb74c, onlyPIC.f/MESH.f differ, reconstructed patch exact, component
and combined proofs/raw states/binary hashes rechecked. Combined fine1..600
strict convergence1200 rows and140 field/native pairs pass; normal50 pairs and
independent native review pass; coarse100 startup200 rows pass.

All three new studies use binaryf249a3fe / patche5191d7e, full32 cycles from
zero with16-cycle ramp. Sessions18416(coarseN800),96964(fineN400),67898(fineN800)
are live. Coarse uses FSILS FSI, fine uses proven ILUT FSI; meshCG/FSILS nu0,
physical solidnu.3 and all original tolerances unchanged. Independent original
fineN400 still runs and is retained, not mixed into the patched budget.

Each export binds patch/binary and freezes both audit sources. Original source
and failed runs remain. Coarse prefix1..200:400 final equation rows pass, no cap;
this is only a prefix, not full qualification. Raw outputs remain local.

Commands: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
build/analysis-venv/bin/python build/recompute-20261109/run-reference-patched-elastic.py
--level 0 --n 800 --backend fsils` and `(1,400,ilut)`, `(1,800,ilut)`.
All preserve3GiB RSS/20GiB disk/24h bounds,1rank/1thread. After full convergence
run the existing field audit then the supplied patched budget wrapper, which
requires identical actual patch/binary across all three studies and keeps the
original kernel and10% thresholds. Physical/cross-code/geometry/end gates remain.
