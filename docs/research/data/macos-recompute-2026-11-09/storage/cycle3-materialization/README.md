# Verified eviction of redundant cycle3 materializations

Baseline39aa87e; action50390 exit0 on2026-11-09. Completed alpha1/alpha2 S96L1N400 studies each retain a previously full-member-verified tar.zst archive. Before this action the archive SHA and original full raw-manifest SHA were checked, every selected live HDF file was checked, and all selected members were freshly decoded from the archive and SHA-checked. Then only399 HDF files per study, accepted steps801..1199, were removed from the expanded directory. Complete original bytes remain in each archive. No active solver files or archive files removed.

Allocated bytes reclaimed2588737536 total (2.41GiB); logical content still preserved in archives. All generation manifests, physical inputs, current state and cycle endpoints remain. Future budget uses cycles5/6, tau decomposition cycle6; repeated analytic/periodic audit uses cycles4/5/6. These states all remain materialized. Source hashes bind this dependency analysis.

Actual restore probe21060 restored step1000 from the full archive, checked original SHA, then removed only that redundant restored copy again. Both Study loaders succeeded; all required states1200..2400 exist, endpoints1200/1600/2000/2400 were actually read and hash checked. No numerical gate changed.

IMPORTANT: expanded directories now intentionally omit cycle3 internal HDF members. Before any future cycle3 consumer or full directory-inventory audit, run the receipt's restore_command; the restore script safely restores exactly listed members with SHA verification and preserves existing identical files. The original raw manifest describes the complete logical dataset across archive/materializations, not an assertion that every file remains expanded. Do not run a new complete-family capture without restoration.

Actual commands: `python3 build/recompute-20261109/evict-archived-womersley-cycle3.py`; restore probe used `python3 build/recompute-20261109/restore-archived-womersley-cycle3.py build/recompute-20261109/archives/cycle3-one-member-restore-probe.json`. Per-family receipts contain exact restoration commands for all399 members.
