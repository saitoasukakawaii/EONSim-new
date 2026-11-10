# Geometry boundary archive execution

Baseline a5e2a4e. Prior preparation gated on physical capture, but the read-only physics audit is long-running and free disk approached the 20 GiB floor. Inspected scripts/audit_pressure_tube.py lines330–361: EON audit reads only fluid/solid PVD volume targets. The geometry response consumer uses completed reports and input meshes. Therefore complete terminal raw capture is separated from unfinished physics qualification. Neither the active numerical binaries/controllers nor active audit source was changed.

Raw capture handle40471 exited0: 9815files/18916666640 logical bytes, every SHA and before/after size/mtime checked, accepted1..25600 logs contiguous and both terminal receipts0. Saved full inventory before any deletion.

Boundary archive handle21880 started and confirmed live. Eligible4858 boundary snapshots, PVD targets excluded; per-batch decoded SHA verification and restoration receipt precede deletion. Actual first two archived members restored to a separate probe using existing restore-womersley-materialization.py, SHA checked and original materializations remain absent. This demonstrates actual restore for these two members only. Full final archive/catalog verification remains pending. Updated physical capture will verify all remaining raw files plus every decoded archived member against the original full inventory before producing its evidence.

Commands: python3 build/recompute-20261109/capture-geometry-raw-before-archive.py; python3 build/recompute-20261109/archive-geometry-boundary-chunks.py; python3 build/recompute-20261109/restore-womersley-materialization.py build/recompute-20261109/geometry-boundary-chunk-restore-probe.json.

No new numerical conclusion; physical audit81210 remains live. Partial chunk receipts fail closed; final verification/recovery still required. Reuses existing archive method, no new article, no push/PR.

Archive21880 completed0:60chunks/4858members,3963416576allocated bytes released,2859533705archive bytes retained,net1103882871B reclaimed. All original volume fields/PVD targets retained. Full decoded inventory verification15245 started; pending. See archive-summary.json and60 restoration receipts.

Final full verifier15245 exited0: all9815members/18916666640logical bytes verified against original inventory; every archived missing member decoded/SHA checked again and every retained file rehashed. Missing paths equal union of60 receipts exactly. Actual physics remains pending.
