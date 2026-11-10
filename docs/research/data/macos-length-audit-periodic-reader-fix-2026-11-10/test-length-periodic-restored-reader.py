from pathlib import Path
import importlib.util,json
b=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('audit_wrapper',b/'audit-pressure-streaming.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);w=b/'elastic-s24-l1-n800-length24'
receipts=[p for suffix in ['volume-through24584-chunks','volume-tail-through25349-chunks','late-output-tail-through25550-chunks'] for p in sorted((b/'archives'/('elastic-s24-l1-n800-length24-'+suffix)).glob('*.json'))]
cfg=json.loads((w/'case.json').read_text());domains=[m.original.Domain(w/cfg['mesh']),m.original.Domain(w/cfg['fsi']['domains']['solid_mesh'])]
def paths(step):
 folder='early' if step==23200 else 'dense';stem='solution' if folder=='early' else 'solution_restart23200'
 return [w/folder/f'{stem}_step{step}{suffix}.vtu' for suffix in ['', '_solid']]
# Original ordering includes first current phase of next cycle then previous-phase reread.
sequence=[23200,23201,23202,24001,23201,24002,23202,24801,24001,24802,24002]
unique=sorted(set(sequence));read,stores=m.make_reader(w,receipts);baseline={}
try:
 for step in unique:
  ps=paths(step);role='early' if step==23200 else 'dense'
  with stores[role].frame(ps):baseline[step]=[m.original.eonsim_frame(p,d,bool(i)) for i,(p,d) in enumerate(zip(ps,domains))]
finally:
 for s in stores.values():s.close()
read,stores=m.make_reader(w,receipts)
try:
 for step in sequence:
  actual=[read(p,d,bool(i)) for i,(p,d) in enumerate(zip(paths(step),domains))];assert actual==baseline[step]
finally:
 for s in stores.values():s.close()
assert all(not p.exists() for step in unique for p in paths(step))
assert {k:len(s.restored) for k,s in stores.items()}=={'early':2,'dense':12,'dense-repeat':8}
failed=json.loads((b/'elastic-s24-l1-n800-length24-audit.failed-first.materialization.json').read_text())
assert all(not (w/r['path']).exists() for store in failed['stores'].values() for r in store['restored_members'])
report=dict(passed=True,sequence=sequence,domains=2,exact_original_fields=True,all_created_files_removed=True,failed_run_created_copies_removed=True,wrapper_sha256=m.sha(Path(m.__file__)),proof={k:s.report() for k,s in stores.items()},scope='Actual archived fields across two periodic comparison transitions. Original analyze unchanged; full2400-phase audit remains required.')
(b/'length-periodic-restored-reader-check.json').write_text(json.dumps(report,indent=2)+'\n');print('Current/previous periodic read sequences exact;22 restorations cleaned')
