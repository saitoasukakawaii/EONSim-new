from pathlib import Path
import importlib.util,json,contextlib
b=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('wrapper',b/'audit-pressure-streaming.py');wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
w=b/'elastic-s24-l1-n800-geometry48';rs=sorted((b/'archives/elastic-s24-l1-n800-geometry48-volume-chunks').glob('*.json'));out=b/'streaming-physical-reader-check';out.mkdir()
cfg=json.loads((w/'case.json').read_text());original=wrapper.original;domains=[original.Domain(w/cfg['mesh']),original.Domain(w/cfg['fsi']['domains']['solid_mesh'])]
series=[original.series(w/name) for name in ['solution.pvd','solution_solid.pvd']];paths=[{round(t/cfg['fsi']['dt']):p for t,p in s} for s in series];steps=[23200,23201,24000,25600];items=[(paths[i][step],domains[i],bool(i)) for step in steps for i in range(2)];assert all(not p.exists() for p,d,s in items)
read,stores=wrapper.make_reader(w,rs)
try:
 with contextlib.ExitStack() as stack:
  for role,store in stores.items():stack.enter_context(store.frame([p for p,d,s in items if ('early' if p.relative_to(w).parts[0]=='early' else 'dense')==role]))
  baseline=[original.eonsim_frame(p,d,s) for p,d,s in items]
finally:
 for store in stores.values():store.close()
read,stores=wrapper.make_reader(w,rs)
try:actual=[read(p,d,s) for p,d,s in items]
finally:
 for store in stores.values():store.close()
assert actual==baseline and all(not p.exists() for p,d,s in items)
report=dict(passed=True,steps=steps,domains_per_step=2,exact_field_equality=True,original_reader_used=True,all_created_inputs_removed=True,wrapper_sha256=wrapper.sha(Path(wrapper.__file__)),analyzer_sha256=wrapper.sha(wrapper.ROOT/'scripts/audit_pressure_tube.py'),proof={role:s.report() for role,s in stores.items()},scope='Real geometry48 original endpoint and three dense phases, including last phase; full physical audit not rerun or claimed')
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'}))
