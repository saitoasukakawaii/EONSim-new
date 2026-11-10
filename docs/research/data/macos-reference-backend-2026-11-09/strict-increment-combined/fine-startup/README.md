# Combined patch fine N800 zero-state600-step diagnostic

82743 completed0,1253.22s,peak328712192B. All1200 final equation rows pass
strict original1e-10, maximumFS3.5e-11/MS9.9e-11, at most3 iterations/no cap.
New-process review of the complete log also passed; its current source hash
is authoritative. The original in-process convergence report is retained and
has the previously documented imported-old-code/source-hash ambiguity.

The diagnostic was prepared before the explicit reference_build manifest
extension, so its review has null reference_build; the actual combined binary
and patch are instead bound by the separately frozen definition and source
patch receipts, not claimed to be the unmodified reference. Future formal
studies use the new explicit manifest format.

Command: `python3 scripts/audit_svfsi_convergence.py --work
build/recompute-20261109/reference-strict-increment-startup/cg-fsils --log
build/recompute-20261109/reference-strict-increment-startup/cg-fsils/solve.log
--output build/recompute-20261109/reference-strict-increment-startup/cg-fsils/convergence-reviewed.json`.
Complete field/native comparison401..540 against the preserved original
failed CG window completed0 (50574), original bounds passed for all140 pairs. Recorded-patch adoption is now complete and full fresh studies have started; this diagnostic is not their full qualification.
