from pathlib import Path
import importlib.util,json
b=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('audit_wrapper',b/'audit-pressure-streaming.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
w=b/'elastic-s24-l1-n800-length24';receipts=[b/'archives'/('elastic-s24-l1-n800-length24-'+suffix)/'0000.json' for suffix in ['volume-through24584-chunks','volume-tail-through25349-chunks']]
paths=[]
for receipt,step in zip(receipts,[23201,24585]):
 r=json.loads(receipt.read_text());pair=[w/rel for rel in list(r['selected'])[:2]]
 assert pair[0].name.endswith(f'_step{step}.vtu') and pair[1].name.endswith(f'_step{step}_solid.vtu');paths+=pair
cfg=json.loads((w/'case.json').read_text());domains=[m.original.Domain(w/cfg['mesh']),m.original.Domain(w/cfg['fsi']['domains']['solid_mesh'])]*2
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
report=dict(passed=True,steps=[23201,24585],domains=2,exact_field_equality=True,wrapper_sha256=m.sha(Path(m.__file__)),proof={role:s.report() for role,s in stores.items()},scope='Two real phases across original and new tail archive sets through production physical-reader wrapper; complete4300-member physical audit remains required')
(b/'length24-tail-restored-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Two archive sets: exact original/restored fields, four created files removed')
