# Sixth-cycle tail archive and readers verified

Basee154106; macOS arm64, single-thread zstd19, Python3 and analysis-venv Python. No numerical solver changes or rerun.

Actual commands from repository root:

```
python3 build/recompute-20261109/archive-womersley-n1600-cycle6-tail9360-chunks.py
python3 build/recompute-20261109/verify-womersley-n1600-cycle6-tail9360-archives.py
build/analysis-venv/bin/python build/recompute-20261109/check-womersley-cycle6-tail-reader.py
build/analysis-venv/bin/python build/recompute-20261109/check-womersley-budget-fine-tail-streaming.py
python3 build/recompute-20261109/review-current-archive-catalog.py
```

12766/53823/46135/87153/42650 each exited0. All560 members in14chunks independently decoded and matched source/receipt SHA and sizes. Archived payload1815031680B; compressed642155501B; allocated net reclaimed1174502419B. All current/period endpoints retained.

Analytic adapter restored8801/9080/9360 and read retained9361 with exact original arrays and cleanup. Budget adapter tested repeated8802/9080 passes and9080/9361/9360, exact arrays, SHA evidence and cleanup. Original formulas and10% gates unchanged. This is reader verification, not full9600-step numerical acceptance. Prior prefix-only check scripts assumed retained8801 and are historical; do not rerun unchanged after this archive.

Catalog now16complete inventories/13immutable subsets. Native identity/T-state check then SIGCONT restored controller83479 only after catalog success;59537 live poll confirmed. Womersley still held at last complete9398 line, pending safe original-process resume; tau still held pending24GiB. No push/PR. Existing archive methodology reused, no new article.
