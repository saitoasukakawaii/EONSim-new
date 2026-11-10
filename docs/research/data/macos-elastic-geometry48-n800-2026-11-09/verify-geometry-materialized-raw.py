"""Verify complete terminal inventory including decoded archived boundary members."""
from pathlib import Path
import json,hashlib,subprocess,tarfile

def verified_inventory(b):
 w=b/'elastic-s24-l1-n800-geometry48';manifest=b/(w.name+'-raw-before-archive.json')
 def sha(p):
  with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 m=json.loads(manifest.read_text());rows={r['path']:r for r in m['files']};assert len(rows)==m['count']
 present={str(p.relative_to(w)) for p in w.rglob('*') if p.is_file() and not p.name.endswith('.compressed-pending')}
 assert present<=set(rows)
 missing=set(rows)-present;accounted=set()
 for rp in sorted((b/'archives'/(w.name+'-boundary-chunks')).glob('*.json')):
  receipt=json.loads(rp.read_text());assert receipt['status']=='evicted'
  assert receipt['source_manifest_sha256']==sha(manifest)
  archive=Path(receipt['archive']);assert sha(archive)==receipt['archive_sha256']
  selected=receipt['selected'];assert set(selected)<=missing and not set(selected)&accounted
  proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
   for member in tar:
    assert member.isfile() and member.name in selected and member.name not in seen
    row=rows[member.name];assert member.size==row['bytes']==selected[member.name]['bytes']
    assert hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==row['sha256']==selected[member.name]['sha256'];seen.add(member.name)
  proc.stdout.read();assert proc.wait()==0 and seen==set(selected);accounted.update(seen)
 assert accounted==missing
 for rel in present:
  q=w/rel;assert not q.is_symlink() and q.stat().st_size==rows[rel]['bytes'] and sha(q)==rows[rel]['sha256']
 return m
if __name__=='__main__':
 m=verified_inventory(Path(__file__).resolve().parent);print('Full inventory verified',m['count'],m['total_bytes'])
