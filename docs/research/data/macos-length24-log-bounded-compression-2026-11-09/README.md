# Length24 log-bounded immutable snapshot compression

Baseline6f3789a. Early solve1..23200 completed0,28477.676890166942s,peakRSS1251164160B. Dense phase started; no complete physical audit yet.

12783completed0: python3 build/recompute-20261109/compress-logged-elastic-frames.py --work build/recompute-20261109/elastic-s24-l1-n800-length24 --through 23205. Published checkpoint still23200, but complete contiguous accepted stdout through23218 proves older selected outputs completed: frozen source2c0f392 and current output-before-log blocks identical, frozen binary hash verified.34frames/136VTU, all four fields required. Each replacement checked stable size/mtime and SHA before/after; all136files independently rehashed afterwards. Accepted log prefix SHA matched and preserved.260284416allocated bytes reclaimed; paths and logical content unchanged. No removal of samples, no checkpoints/index/log changes or running controller edits.

This verifies the new log boundary on actual dense output beyond the published checkpoint, rather than only repeating checkpoint-bounded behavior. Current/future snapshots remain excluded. Whole trajectory and physical/end-response qualification still pending. No push/PR.
