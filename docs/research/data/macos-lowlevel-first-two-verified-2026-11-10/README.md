# First two low-level collections independently verified

Base source: fb79224. macOS arm64, Python 3, system zstd; read-only archive verification, no solver or MPI rerun.

Actual commands (repository root):

```
python3 build/recompute-20261109/verify-remaining-lowlevel-collection.py elastic-s24-l1-n1600-boundary-segments014-015-chunks --output build/recompute-20261109/remaining-lowlevel-verified-014-015.json
python3 build/recompute-20261109/verify-remaining-lowlevel-collection.py elastic-s24-l1-n1600-boundary-segments016-017-chunks --output build/recompute-20261109/remaining-lowlevel-verified-016-017.json
```

Handles 54608 and 85450 both exited 0. Each decoded all 13 chunks / 1024 members and checked member size and SHA against the original inventory and current receipt, complete set equality, current compressed SHA before and after decoding, committed journals and absence of temporary/backup archives. Savings: 85,766,939 and 85,327,074 bytes respectively. This covers only these two completed collections, not all 120 selected chunks. Existing archive verification method reused; no new algorithm article.

Womersley monitor 98038 exited 0 after the fifth capacity hold; accepted log reached 9399, original 6194 remains live. Original timeout and storage thresholds unchanged. Tau recovery 75128 remains live held; archive controller 59537 remains live. No complete numerical acceptance or push/PR.
