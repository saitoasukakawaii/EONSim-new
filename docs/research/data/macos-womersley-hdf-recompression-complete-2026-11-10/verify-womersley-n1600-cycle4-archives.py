"""Decode and verify every archived cycle4 state against the pre-archive inventory."""
from pathlib import Path
import json,hashlib,tarfile,subprocess

def verified_archived_rows(b):
 w=b/'alpha2-s96-l1-n1600';manifest=b/(w.name+'-cycle4-before-archive.json')
 def sha(p):
  with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 m=json.loads(manifest.read_text());rows={r['path']:r for r in m['files']};assert len(rows)==1599
 assert sha(w/'definition.json')==m['definition_sha256'] and sha(w/'attempt-004/solve.log')==m['completed_log_sha256']
 accounted=set()
 for rp in sorted((b/'archives'/(w.name+'-cycle4-chunks')).glob('*.json')):
  r=json.loads(rp.read_text());assert r['status']=='evicted' and r['source_manifest_sha256']==sha(manifest)
  selected=r['selected'];assert set(selected)<=set(rows) and not set(selected)&accounted
  archive=Path(r['archive']);assert sha(archive)==r['archive_sha256']
  proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
   for member in tar:
    assert member.isfile() and member.name in selected and member.name not in seen
    row=rows[member.name];assert member.size==row['bytes']==selected[member.name]['bytes']
    assert hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==row['sha256']==selected[member.name]['sha256'];seen.add(member.name)
  proc.stdout.read();assert proc.wait()==0 and seen==set(selected);accounted.update(seen)
 assert accounted==set(rows)
 for rel,row in rows.items():
  assert not (w/rel).exists() and sha(w/row['checkpoint_manifest'])==row['checkpoint_manifest_sha256']
 return [dict(path=rel,bytes=row['bytes'],sha256=row['sha256']) for rel,row in sorted(rows.items())]
if __name__=='__main__':
 rows=verified_archived_rows(Path(__file__).resolve().parent);print('Verified archived cycle4',len(rows),sum(r['bytes'] for r in rows))
