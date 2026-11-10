# Transparent compression of completed immutable FSI snapshots

Baseline14fa0d2. Session23946 exit0:3312files/828frames through23999 (including completed early outputs), all byte hashes verified before copy, before replacement and after replacement; saved3353251840 allocated bytes in115.21s. Snapshot selection records the actual published checkpoint24800 at start, source/controller hash and every replacement hash. No logical byte/path changed.

Source inspection matters: src/physics/fsi.cpp602..615 publishes checkpoint BEFORE that step's snapshot at617..631. Therefore this entry requires cutoff STRICTLY LESS than published checkpoint; current checkpoint step itself is excluded. Per-step snapshots are written once, and all four domain/boundary files are required. Completed early-stage receipt0 also checked. Indexes, logs, native checkpoints, current/future frames are not touched. This is not deleting data from an active trajectory; only immutable older file allocation changes.

Command: `python3 build/recompute-20261109/compress-accepted-elastic-frames.py --work build/recompute-20261109/elastic-s24-l1-n800 --through 23999`. The next cutoff24799 is running after the first process completed; already compressed frames are skipped. Full trajectory/audit remains pending. No scientific gate changed.
