from pathlib import Path
import importlib.util,json
b=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('audit_wrapper',b/'audit-pressure-streaming.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
w=b/'elastic-s24-l1-n800-length24';receipts=[];paths=[]
for suffix,step in [('volume-through24584-chunks',23201),('volume-tail-through25349-chunks',24585),('late-output-tail-through25550-chunks',25350)]:
 pair=[w/'dense'/f'solution_restart23200_step{step}{ending}.vtu' for ending in ['', '_solid']]
 candidates=sorted((b/'archives'/('elastic-s24-l1-n800-length24-'+suffix)).glob('*.json'))
 for p in pair:
  matching=[rp for rp in candidates if str(p.relative_to(w)) in json.loads(rp.read_text())['selected']];assert len(matching)==1
  if matching[0] not in receipts:receipts.append(matching[0])
 paths+=pair
cfg=json.loads((w/'case.json').read_text());domains=[m.original.Domain(w/cfg['mesh']),m.original.Domain(w/cfg['fsi']['domains']['solid_mesh'])]*3
read,stores=m.make_reader(w,receipts)
try:
 with stores['dense'].frame(paths):baseline=[m.original.eonsim_frame(p,d,bool(i%2)) for i,(p,d) in enumerate(zip(paths,domains))]
finally:
 for s in stores.values():s.close()
read,stores=m.make_reader(w,receipts)
try:actual=[read(p,d,bool(i%2)) for i,(p,d) in enumerate(zip(paths,domains))]
finally:
 for s in stores.values():s.close()
assert actual==baseline and all(not p.exists() for p in paths)
report=dict(passed=True,steps=[23201,24585,25350],domains=2,exact_field_equality=True,wrapper_sha256=m.sha(Path(m.__file__)),proof={role:s.report() for role,s in stores.items()},scope='Three real phases across all volume archive sets through production physical-reader wrapper; complete4702-member physical audit remains required')
(b/'length24-late-tail-restored-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Three archive sets: exact original/restored fields, six created files removed')
