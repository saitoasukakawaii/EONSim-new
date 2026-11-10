from pathlib import Path
import importlib.util,json
b=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('audit_wrapper',b/'audit-pressure-streaming.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
w=b/'elastic-s24-l1-n800-length24';receipt=b/'archives/elastic-s24-l1-n800-length24-volume-through24584-chunks/0000.json';r=json.loads(receipt.read_text());paths=[w/rel for rel in list(r['selected'])[:2]]
assert paths[0].name.endswith('_step23201.vtu') and paths[1].name.endswith('_step23201_solid.vtu')
cfg=json.loads((w/'case.json').read_text());domains=[m.original.Domain(w/cfg['mesh']),m.original.Domain(w/cfg['fsi']['domains']['solid_mesh'])]
read,stores=m.make_reader(w,[receipt])
try:
 with stores['dense'].frame(paths):baseline=[m.original.eonsim_frame(p,d,bool(i)) for i,(p,d) in enumerate(zip(paths,domains))]
finally:
 for s in stores.values():s.close()
read,stores=m.make_reader(w,[receipt])
try:actual=[read(p,d,bool(i)) for i,(p,d) in enumerate(zip(paths,domains))]
finally:
 for s in stores.values():s.close()
assert actual==baseline and all(not p.exists() for p in paths)
report=dict(passed=True,step=23201,domains=2,exact_field_equality=True,wrapper_sha256=m.sha(Path(m.__file__)),proof={role:s.report() for role,s in stores.items()},scope='One real length24 accepted phase through the production physical-reader wrapper; complete physical audit still required')
(b/'length24-restored-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Length24 original/restored reader exact; two created files removed')
