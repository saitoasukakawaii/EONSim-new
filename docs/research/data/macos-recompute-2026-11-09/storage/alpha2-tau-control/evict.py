"""Remove only verified archived duplicates after all current alpha2 consumers complete."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,time,shutil
b=Path(__file__).resolve().parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
dp=b/'alpha2-tau-decomposition.json';d=json.loads(dp.read_text());budget=b/'alpha2-n400-budget.json';assert json.loads(budget.read_text())['passed'] is False # Original default N400 failure remains failed; next target uses N800/N1600.
assert d['common_phases']==400 and d['cycle']==6 and d['maximum_node_closure']<1e-15
for name,digest in d['source_sha256'].items():assert sha(Path(name))==digest
for name,digest in d['analysis_sha256'].items():assert sha(Path(name))==digest
for name,n,first in [('alpha2-s96-l1-n800-tautime-n400',800,1600)]:
 w=b/name;out=b/'archives'/(name+'-completed-consumers-materialization.json');assert not out.exists()
 receipt=json.loads((b/'archives'/(name+'.json')).read_text());archive=Path(receipt['archive']);manifest=Path(receipt['source_manifest'])
 assert sha(archive)==receipt['archive_sha256'] and sha(manifest)==receipt['source_manifest_sha256']
 rows={r['path']:r for r in json.loads(manifest.read_text())['files']};assert json.loads(w.with_suffix('.execution.json').read_text())['exit_code']==0;assert json.loads((w/'receipt.json').read_text())['step']==6*n
 selected={}
 for p in (w/'checkpoint').glob('generation_*/manifest'):
  f=p.read_text().split();assert f[0]=='EONSim_checkpoint_v4' and f[1]=='1';step=int(f[2])
  if first<step<6*n and step%n:
   q=p.parent/'state_rank0.h5';rel=str(q.relative_to(w));assert q.is_file() and not q.is_symlink();assert sha(q)==rows[rel]['sha256'];assert q.stat().st_size==rows[rel]['bytes']
   # Every removed final-cycle state consumed by decomposition is still its exact original bytes.
   if rel in d['input_sha256'][str(w)]:assert rows[rel]['sha256']==d['input_sha256'][str(w)][rel]
   selected[rel]=dict(step=step,sha256=rows[rel]['sha256'],bytes=rows[rel]['bytes'],allocated_bytes=q.stat().st_blocks*512)
 assert {v['step'] for v in selected.values()}=={s for s in range(first+1,6*n) if s%n}
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
 with tarfile.open(fileobj=proc.stdout,mode='r|') as t:
  for m in t:
   if m.name in selected:
    assert m.isfile() and m.name not in seen and m.size==selected[m.name]['bytes'];assert hashlib.file_digest(t.extractfile(m),'sha256').hexdigest()==selected[m.name]['sha256'];seen.add(m.name)
 proc.stdout.read();assert proc.wait()==0 and seen==set(selected)
 record=dict(work=str(w),archive=str(archive),archive_sha256=receipt['archive_sha256'],source_manifest=str(manifest),source_manifest_sha256=receipt['source_manifest_sha256'],selected=selected,status='verified-before-eviction',decomposition_sha256=sha(dp),budget_sha256=sha(budget),scope='Alpha2 tau-control analytic and actual-field decomposition consumers completed. Entire control archived and decoded SHA-verified before removing redundant expanded fields; default N800 cycles5/6 remain expanded for its pending N800/N1600 budget. Complete original raw bytes remain archived; every endpoint/manifest retained. Any future field consumer or repeated analysis MUST restore selected members and earlier materialization receipts first.',restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(out)])
 out.write_text(json.dumps(record,indent=2)+'\n');free=shutil.disk_usage(b).free
 for rel,row in selected.items():
  q=w/rel;assert sha(q)==row['sha256'];q.unlink()
 record.update(status='evicted',removed_allocated_bytes=sum(v['allocated_bytes'] for v in selected.values()),observed_free_change_bytes=shutil.disk_usage(b).free-free,finished_unix=time.time());out.write_text(json.dumps(record,indent=2)+'\n');print(name,len(selected),record['removed_allocated_bytes'],flush=True)
