from pathlib import Path
import importlib.util,json,copy,contextlib,ast
b=Path(__file__).resolve().parent

def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('stream',b/'streaming-volume-materialization.py');fields=module('original_fields',b/'compare-pressure-fields.py')
out=b/'streaming-tau-decomposition-reader-check';out.mkdir(exist_ok=False)
works=[b/f'elastic-s24-l1-n{n}' for n in [400,800]];receipts=[[b/f'archives/elastic-s24-l1-n{n}-volume-materialization.json'] for n in [400,800]]
def studies(cls=fields.Study):return [cls(w/'case.json',w,b/(w.name+'-audit.json')) for w in works]
base=studies();stores=[m.Volumes(w,rs) for w,rs in zip(works,receipts)]
paths=[[p for phase in range(1,5) for p in s.paths[31*s.n+phase*s.n//4]] for s in base]
assert all(not p.exists() for ps in paths for p in ps)
try:
 with contextlib.ExitStack() as stack:
  for store,ps in zip(stores,paths):stack.enter_context(store.frame(ps))
  baseline=fields.compare(*base,phases=4)
finally:
 for s in stores:s.close()
assert all(not p.exists() for ps in paths for p in ps)
wrapper=b/'decompose-elastic-tau-time-streaming.py'
entry=module('tau_stream_entry',wrapper);cls,store_map=entry.make_study(fields)
try:
 streamed=fields.compare(*studies(cls),phases=4)
finally:
 for store in store_map.values():store.close()
stores=[store_map[w.resolve()] for w in works]
assert baseline==streamed,'Original-reader baseline differs from bounded restoration'
assert all(not p.exists() for ps in paths for p in ps)
report=dict(passed=True,wrapper_sha256=m.sha(wrapper),helper_sha256=m.sha(b/'streaming-volume-materialization.py'),comparison_sha256=m.sha(b/'compare-pressure-fields.py'),decomposition_sha256=m.sha(b/'decompose-elastic-tau-time.py'),actual_common_phases=4,actual_restored_members=[len(s.restored) for s in stores],peak_frame_bytes=[s.peak_frame_bytes for s in stores],comparison_exact=True,all_created_paths_removed=True,scope='Actual production factory on archived N400/N800 fields; original comparison exact versus pre-restored baseline. Four phase reader integration only, not full tau control decomposition.')
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
