# Active N1600 immutable cycle3 archival

Baseline7ad2dfb. Controller/binary unchanged. study_womersley.py only loads checkpoint/current between stages; final analyze_womersley.py uses cycles6/5/4. Internal cycle3 states3201..4799 archived; endpoint4800 and later states retained. Future cycle3 consumers must restore first.

31349capture exited0:1599states; completed attempt003 contiguous log ends success, receipt>=4800/current>4800, hashes/stable size/mtime verified.24343archive exited0:39chunks/1599HDF, every member decoded/SHA checked before deletion.82079full independent archive reread exited0; original1599HDF bytes and generation manifests verified. Two actual HDF restored separately and SHA checked. Net reclaimed1192696188B. Missing archive negative check rejected. Final capture now verifies archived members plus materialized files, still requires9600steps/full analytic report; actual final capture NOT run.

Actual commands: python3 build/recompute-20261109/prepare-womersley-n1600-cycle3-archive.py; python3 build/recompute-20261109/archive-womersley-n1600-cycle3-chunks.py; python3 build/recompute-20261109/verify-womersley-n1600-cycle3-archives.py; python3 build/recompute-20261109/restore-womersley-materialization.py build/recompute-20261109/womersley-n1600-cycle3-restore-probe.json.

39receipts/logs/source retained; raw archives local. No new numerical claim/article; no push/PR. First evidence-recording inline Python had SyntaxError and made no changes; corrected recording script retained.
