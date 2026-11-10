# Explicit patched-reference provenance

User explicitly permits recorded, validated patches. The convergence auditor
now accepts an optional reference_build declaration identifying patched-fixed-
reference/base pin and local patch/binary artifacts. Both must be manifest-bound
and hash-identical; escaping paths, changed artifacts, missing binding or wrong
base are rejected. Normal pinned inputs remain supported without a declaration.
This is provenance, not proof that arbitrary patches are correct. Relative
convergence and rounded-threshold rejection are unchanged.

Actual focused checks:7 convergence,16 restart,11 pressure-audit tests passed.
The prepared full-study controller freezes the patch, binary and both audit
source files before launching; final convergence runs in a separate process
against that frozen source. It requires a validated adoption receipt that does
not yet exist; no production job was launched by preparing the controller.

Two already-running controllers82743/75644 imported the old audit function
before this metadata-only edit. Its hash helper reads the file from disk; their
in-process source hash must not be taken as executed-code identity. The exact
old source is retained here. After completion preserve their original report
and run a fresh explicit convergence-reviewed.json. This affects provenance,
not their numerical solver or original relative thresholds.
