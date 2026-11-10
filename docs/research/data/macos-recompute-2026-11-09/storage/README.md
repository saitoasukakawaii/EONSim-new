# Verified transparent storage compression

Fine trajectories need disk headroom. A first restricted ditto probe returned0
but produced a zero-logical-length copy whose readback hash failed; the original
was untouched. This failure is preserved. A separate authorized unrestricted
probe returned the original bytes through the normal filesystem API with reduced
allocation. No unverified copy replaced an original.

Actual command: `python3 build/recompute-20261109/compress-completed-elastic.py`
(with normal OS file-flag access). It processed only the completed and audited
elastic-s24-l0-n800 dataset, never active solver outputs. For each file, it
checked original stability, size and SHA256 of the compressed copy before atomic
replacement, then checked the same hash again.9756 files passed, freeing
1359437824 allocated bytes in104.27s. Names, logical contents and hashes stay
unchanged, so ordinary field readers continue to work. Manifest lists every
verified replacement. Numerical results and prior audit evidence are unchanged.

## 2026-11-09 partial materialization update

[Completed Womersley cycle3 duplicate HDF materializations](cycle3-materialization/README.md) now removed after fresh archive/member verification; full raw bytes remain in verified archives. This differs from transparent compression: those individual HDF paths require explicit restoration for future cycle3 consumers or full directory inventory audit. Remaining analyses and all cycle endpoints are retained and checked. Reclaimed2588737536 allocated bytes; one actual restore/SHA probe passed.
