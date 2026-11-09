"""Archive completed bounded probes, retaining failed/not-selected choices."""
import importlib.util,json,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-first-coupled.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
os.sched_setaffinity(0,{22})
names=['pc-probe-coarse-c49c69c','pc-probe-fine-c49c69c']
for name in names:assert json.loads((c.work/name/'report.json').read_text())['complete']
c.capture('womersley-schur-options-2026-11-08',[(n,list((c.work/n).rglob('*'))) for n in names],
    [Path(__file__).with_name('probe-womersley-pc.py'),Path(__file__)])
names=['elastic-s12-l1-n200-probe-c49c69c','reference-space-startup-c49c69c']
assert json.loads((c.work/names[0]/'summary.json').read_text())['reference_convergence']['passed']
assert json.loads((c.work/names[1]/'summary.json').read_text())['ramp16']['passed']
c.capture('pressure-tube-space-preflight-2026-11-08',[(n,list((c.work/n).rglob('*'))) for n in names],
    [Path(__file__).with_name('probe-pressure-space.py'),Path(__file__).with_name('probe-reference-space-startup.py'),Path(__file__)])
