"""Restore exactly the verified archived HDF members listed in an eviction receipt."""
from pathlib import Path
import sys,json,hashlib,subprocess,tarfile,os
r=json.loads(Path(sys.argv[1]).read_text());w=Path(r['work']);archive=Path(r['archive'])
with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['archive_sha256']
proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);seen=set()
with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
 for member in tar:
  if member.name not in r['selected']:continue
  rel=Path(member.name);assert not rel.is_absolute() and '..' not in rel.parts and member.isfile();row=r['selected'][member.name];assert member.size==row['bytes'] and member.name not in seen
  q=w/rel;assert q.parent.is_dir() and not q.is_symlink();data=tar.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==row['sha256']
  if q.exists():assert hashlib.sha256(q.read_bytes()).hexdigest()==row['sha256']
  else:
   pending=q.with_suffix('.restore-pending');assert not pending.exists();pending.write_bytes(data);assert hashlib.sha256(pending.read_bytes()).hexdigest()==row['sha256'];os.rename(pending,q)
  seen.add(member.name)
proc.stdout.read();assert proc.wait()==0 and seen==set(r['selected']);print('Restored/verified',len(seen),'members; original archival receipt retained')
