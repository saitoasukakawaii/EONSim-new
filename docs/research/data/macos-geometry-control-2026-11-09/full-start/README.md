# Full fixed-topology geometry control started

Baselineb56f173; active session21558, original EON binary04a7aa5b... . Fresh zero-state S24level1N800 topology projected to48-sided boundary,32cycles/16ramp, unchanged physical/time case and solver options. Baseline and smoke-probe binary hashes match. Actual accepted startup steps observed; no full-run or periodic qualification yet.

Command: `build/analysis-venv/bin/python build/recompute-20261109/run-elastic-geometry-control.py --work build/recompute-20261109/elastic-s24-l1-n800-geometry48 --level 1 --n 800`. One rank/thread,3GiBRSS,20GiB disk floor and24h per-stage timeout. Early29cycle fields estimated225050614B plus native/log overhead; dense final3cycles require continued storage management. Starting capacity exceeded40GiB. Existing original studies were not restarted.

An initial separate preflight read used a nonexistent copied probe/eonsim path; the probe actually used the release executable directly. That check failed and the shell continued to the already authorized controller. The actual launched binary was then independently matched against both probe definition and baseline, and case/options checked. This inspection failure is preserved in start-verification.json, not claimed as successful first preflight.

After completion, run the full audit and `compare-elastic-control-response.py --mode geometry` with complete matched baseline/control reports. Do not feed this projected mesh into the fixed-polygon spatial budget. The original 48-hour awake guard4354 remains live.
