"""Archive completed time, mesh-replay and static diagnostics in bounded chunks."""
import importlib.util,json,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-first-coupled.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);os.sched_setaffinity(0,{22})
names=['lame-quarter-6093f01','lame-quarter-6093f01-attempt2','static-time-analysis-6093f01']
c.capture('lame-static-2026-11-08',[(n,list((c.work/n).rglob('*'))) for n in names]+[
    ('status',[c.work/'lame-quarter-current.json',c.work/'lame-quarter-retry-current.json'])],
    [c.work/'lame-quarter-6093f01-attempt2/summary.json',c.work/'static-time-analysis-6093f01/static-nested-differences.json',
     c.work/'static-time-analysis-6093f01/lame-refinement.png',c.work/'static-time-analysis-6093f01/lame-refinement.svg',Path(__file__)])
assert json.loads((c.work/'elastic-n200-current.json').read_text())['state']=='completed'
assert json.loads((c.work/'elastic-time-fields-current.json').read_text())['state']=='completed'
assert json.loads((c.work/'reference-mesh-replay-current.json').read_text())['state']=='completed'
study=c.work/'elastic-s12-l0-n200-ramp16-c32';groups=[];chunk=[];size=0
for p in sorted(study.rglob('*')):
    if not p.is_file() or p.name=='eonsim':continue
    if chunk and size+p.stat().st_size>64*1024**2:
        groups.append((f'n200-part{len(groups)+1:02d}',chunk));chunk=[];size=0
    assert p.stat().st_size<64*1024**2
    chunk.append(p);size+=p.stat().st_size
if chunk:groups.append((f'n200-part{len(groups)+1:02d}',chunk))
for name in ('elastic-time-fields-6093f01','reference-mesh-replay-6093f01','reference-tight-linear-n400-6093f01'):
    groups.append((name,list((c.work/name).rglob('*'))))
groups.append(('completed-status',[c.work/'elastic-n200-current.json',c.work/'elastic-time-fields-current.json',c.work/'reference-mesh-replay-current.json']))
c.capture('pressure-tube-time-2026-11-08',groups,
    [c.work/'elastic-time-fields-6093f01/summary.json',c.work/'static-time-analysis-6093f01/phase-sampling-oracle.json',
     c.root/'build/prod48-20261107/run-pressure-n400.py',Path(__file__)])
