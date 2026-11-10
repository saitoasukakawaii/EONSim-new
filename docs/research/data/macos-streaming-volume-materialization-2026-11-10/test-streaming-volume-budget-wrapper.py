from pathlib import Path
import importlib.util,json,copy,contextlib,ast
b=Path(__file__).resolve().parent

def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('stream',b/'streaming-volume-materialization.py');fields=module('original_fields',b/'compare-pressure-fields.py')
out=b/'streaming-volume-materialization-wrapper-check';out.mkdir(exist_ok=False)
works=[b/'elastic-s24-l0-n1600',b/'elastic-s24-l1-n800'];receipts=[sorted((b/'archives/elastic-s24-l0-n1600-volume-chunks').glob('*.json')),[b/'archives/elastic-s24-l1-n800-volume-materialization.json']]
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
wrapper=b/'analyze-elastic-n1600-budget-streaming.py'
node=next(n for n in ast.parse(wrapper.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='make_streaming_study')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(wrapper),'exec'))
study,store_map=make_streaming_study(fields,b)
try:
 streamed=fields.compare(*[study('eonsim',dict(case=w/'case.json',work=w,audit=b/(w.name+'-audit.json'))) for w in works],phases=4)
finally:
 for store in store_map.values():store.close()
stores=[store_map[w.resolve()] for w in works]
assert baseline==streamed,'Original-reader baseline differs from bounded restoration'
assert all(not p.exists() for ps in paths for p in ps)
# Failure during consumer read must still remove only the created verified files.
store=m.Volumes(works[0],receipts[0])
try:
 try:
  with store.frame(paths[0][:2]):raise RuntimeError('consumer probe')
 except RuntimeError as e:assert str(e)=='consumer probe'
finally:store.close()
assert all(not p.exists() for p in paths[0][:2])
rejections=[]
def rejects(label,fn):
 try:fn()
 except (ValueError,KeyError):rejections.append(label)
 else:raise AssertionError('Did not reject '+label)
rejects('duplicate receipt',lambda:m.Volumes(works[0],[receipts[0][0],receipts[0][0]]))
r=json.loads(receipts[0][0].read_text());r['selected'][next(iter(r['selected']))]['sha256']='0'*64;p=out/'bad-member.json';p.write_text(json.dumps(r));rejects('member differs from manifest',lambda:m.Volumes(works[0],[p]))
r=json.loads(receipts[0][0].read_text());r['source_manifest_sha256']='0'*64;p2=out/'bad-manifest.json';p2.write_text(json.dumps(r));rejects('manifest hash',lambda:m.Volumes(works[0],[p2]))
r=json.loads(receipts[0][1].read_text());r['source_manifest_sha256']='0'*64;pc=out/'conflicting-manifest.json';pc.write_text(json.dumps(r));rejects('conflicting shared manifest',lambda:m.Volumes(works[0],[receipts[0][0],pc]))
r=json.loads(receipts[0][0].read_text());r['archive_sha256']='0'*64;p3=out/'bad-archive.json';p3.write_text(json.dumps(r));bad=m.Volumes(works[0],[p3]);rel=next(iter(bad.index));rejects('archive hash',lambda:bad._read(rel));bad.close()
(out/'comparison-baseline.json').write_text(json.dumps(baseline,indent=2)+'\n');(out/'comparison-streamed.json').write_text(json.dumps(streamed,indent=2)+'\n')
report=dict(wrapper_sha256=m.sha(wrapper),wrapper_factory_exercised=True,helper_sha256=m.sha(b/'streaming-volume-materialization.py'),comparison_sha256=m.sha(b/'compare-pressure-fields.py'),passed=True,actual_common_phases=4,actual_restored_members=[len(s.restored) for s in stores],peak_frame_bytes=[s.peak_frame_bytes for s in stores],comparison_exact=True,consumer_exception_cleanup=True,rejections=rejections,all_original_paths_absent_after=True,scope='Actual coarse N1600/fine N800 fields, unchanged comparison and reader; 4 phase integration check only, not full error budget')
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
