# Bounded default-field restoration for FSI tau decomposition

Base8bf841c. Actual test session56200 exit0 with analysis-venv Python, OPENBLAS/OMP/VECLIB threads1 on macOS. Command: `build/analysis-venv/bin/python build/recompute-20261109/test-streaming-tau-decomposition-reader.py`.

Production wrapper factory restores archived N400/N800 default fields one phase at a time; control remains original. Original decompose-elastic-tau-time.py main, 400 common phases, P1 cross terms, closure/default-budget identity, binary/config/audit checks remain unchanged. Sidecar binds wrapper, original decomposition and materializer hashes and actual restored members.

Test compares original full-field comparison at four real common phases with all test fields pre-restored against the same comparison using production wrapper factory. Reports exactly equal;8 members per default study, peak4476955/4477007B, all created files removed. Actual incomplete control preflight refuses before restoration and creates neither report nor sidecar. This verifies reader integration only; full tau decomposition remains UNRUN because the control is still held/incomplete. Does not establish a numerical pass or tau causality. Previous original decomposition tests are unchanged, not rerun here.
