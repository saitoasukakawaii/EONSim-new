"""Remove only verified redundant cycle3 HDF materializations; retain full archives."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,time,shutil
b=Path(__file__).resolve().parent;root=b.parents[1]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for alpha in [1,2]:
 name=f'alpha{alpha}-s96-l1-n400';w=b/name;out=b/'archives'/(name+'-cycle3-materialization.json');assert not out.exists()
 receipt=json.loads((b/'archives'/(name+'.json')).read_text());archive=Path(receipt['archive']);manifest=Path(receipt['source_manifest'])
 assert sha(archive)==receipt['archive_sha256'] and sha(manifest)==receipt['source_manifest_sha256']
 rows={r['path']:r for r in json.loads(manifest.read_text())['files']}
 assert json.loads(w.with_suffix('.execution.json').read_text())['exit_code']==0
 r=json.loads((w/'receipt.json').read_text());assert r['step']==2400
 selected={}
 for p in (w/'checkpoint').glob('generation_*/manifest'):
  fields=p.read_text().split();assert fields[0]=='EONSim_checkpoint_v4' and fields[1]=='1'
  step=int(fields[2])
  if 800<step<1200:
   q=p.parent/'state_rank0.h5';rel=str(q.relative_to(w));assert not q.is_symlink() and q.is_file() and rel in rows
   assert sha(q)==rows[rel]['sha256'] and q.stat().st_size==rows[rel]['bytes']
   selected[rel]=dict(step=step,sha256=rows[rel]['sha256'],bytes=rows[rel]['bytes'],allocated_bytes=q.stat().st_blocks*512)
 assert len(selected)==399 and {v['step'] for v in selected.values()}==set(range(801,1200))
 # Decode each selected member again immediately before eviction.
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
 with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
  for member in tar:
   if member.name in selected:
    assert member.isfile() and member.name not in seen and member.size==selected[member.name]['bytes']
    assert hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==selected[member.name]['sha256'];seen.add(member.name)
 proc.stdout.read();assert proc.wait()==0 and seen==set(selected)
 record=dict(work=str(w),archive=str(archive),archive_sha256=receipt['archive_sha256'],source_manifest=str(manifest),source_manifest_sha256=receipt['source_manifest_sha256'],selected=selected,status='verified-before-eviction',dependencies={'completed':'Full analytic/periodic analysis and complete raw archive verification','remaining':'Budget uses cycles5/6; tau decomposition uses cycle6; repeated analytic audit uses cycles4/5/6. All these states retained. Cycle endpoints400/800/1200/1600/2000/2400 and current receipt retained.'},scope='Only redundant materialization removed. Complete original bytes remain in verified archive; restore selected HDF members before any future cycle3 analysis or full directory inventory audit.',restore_command=['python3',str(b/'restore-archived-womersley-cycle3.py'),str(out)])
 out.write_text(json.dumps(record,indent=2)+'\n');free=shutil.disk_usage(b).free
 for rel,item in selected.items():
  q=w/rel;assert sha(q)==item['sha256'];q.unlink()
 record.update(status='evicted',observed_free_change_bytes=shutil.disk_usage(b).free-free,removed_allocated_bytes=sum(v['allocated_bytes'] for v in selected.values()),finished_unix=time.time());out.write_text(json.dumps(record,indent=2)+'\n')
 print(name,len(selected),record['removed_allocated_bytes'],flush=True)
