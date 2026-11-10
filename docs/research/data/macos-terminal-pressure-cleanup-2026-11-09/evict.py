"""Reclaim only freshly verified archived pressure inputs in three terminal diagnostics."""
from pathlib import Path
import json,hashlib,subprocess,tarfile,time
b=Path(__file__).resolve().parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for name in ['reference-fine-backend-screen','reference-kinematic-increment-startup','reference-strict-increment-startup']:
 w=b/name;r=json.loads((b/'archives'/(name+'.json')).read_text());archive=Path(r['archive']);manifest=Path(r['source_manifest']);assert sha(archive)==r['archive_sha256'] and sha(manifest)==r['source_manifest_sha256']
 prior=json.loads((b/'archives'/(name+'-materialization.json')).read_text());assert prior['status']=='evicted'
 out=b/'archives'/(name+'-pressure-materialization.json');assert not out.exists();rows={v['path']:v for v in json.loads(manifest.read_text())['files']};selected={}
 for p in w.rglob('pressure-*.txt'):
  rel=str(p.relative_to(w));v=rows[rel];assert not p.is_symlink() and p.stat().st_nlink==1 and sha(p)==v['sha256'] and p.stat().st_size==v['bytes'];selected[rel]=dict(bytes=v['bytes'],sha256=v['sha256'],allocated_bytes=p.stat().st_blocks*512)
 assert len(selected)==(8 if name=='reference-fine-backend-screen' else 2)
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
 with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
  for m in tar:
   if m.name in selected:
    v=selected[m.name];assert m.isfile() and m.name not in seen and m.size==v['bytes'];assert hashlib.file_digest(tar.extractfile(m),'sha256').hexdigest()==v['sha256'];seen.add(m.name)
 proc.stdout.read();assert proc.wait()==0 and seen==set(selected)
 record=dict(work=str(w),archive=str(archive),archive_sha256=r['archive_sha256'],source_manifest=str(manifest),source_manifest_sha256=r['source_manifest_sha256'],selected=selected,status='verified-before-eviction',scope='Only archived pressure inputs of previously archived terminal diagnostics; fresh expanded/archive/manifest SHA equality. All raw bytes remain in full archive. Restore before replay, input rehash or full inventory consumption. No active reference input touched.',restore_command=['python3',str(b/'restore-womersley-materialization.py'),str(out)])
 out.write_text(json.dumps(record,indent=2)+'\n')
 for rel,v in selected.items():
  p=w/rel;assert sha(p)==v['sha256'];p.unlink()
 record.update(status='evicted',finished_unix=time.time(),removed_allocated_bytes=sum(v['allocated_bytes'] for v in selected.values()));out.write_text(json.dumps(record,indent=2)+'\n');print(name,record['removed_allocated_bytes'],flush=True)
