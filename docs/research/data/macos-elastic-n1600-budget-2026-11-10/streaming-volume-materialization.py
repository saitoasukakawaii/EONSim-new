"""Restore exact archived volume bytes for one monotone frame read at a time."""
from pathlib import Path
from contextlib import contextmanager
import hashlib,json,os,shutil,subprocess,tarfile

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

class Volumes:
 def __init__(self,work,receipts):
  self.work=Path(work).resolve();self.index={};self.archive_hashes={};self.manifests={};self.manifest_hashes={};self.receipt_hashes={};self.streams={};self.used=set();self.restored=[];self.peak_frame_bytes=0
  for rp in receipts:
   rp=Path(rp).resolve();r=json.loads(rp.read_text());self.receipt_hashes[str(rp)]=sha(rp)
   if r['status']!='evicted' or Path(r['work']).resolve()!=self.work:raise ValueError('Receipt work/status mismatch')
   manifest=Path(r['source_manifest']).resolve()
   if manifest not in self.manifests:
    if sha(manifest)!=r['source_manifest_sha256']:raise ValueError('Manifest SHA mismatch')
    self.manifests[manifest]={v['path']:v for v in json.loads(manifest.read_text())['files']};self.manifest_hashes[str(manifest)]=r['source_manifest_sha256']
   if self.manifest_hashes[str(manifest)]!=r['source_manifest_sha256']:raise ValueError('Conflicting manifest hash')
   expected=self.manifests[manifest];archive=Path(r['archive']).resolve();digest=r['archive_sha256']
   if archive in self.archive_hashes and self.archive_hashes[archive]!=digest:raise ValueError('Conflicting archive hashes')
   self.archive_hashes[archive]=digest
   for rel,row in r['selected'].items():
    p=Path(rel)
    if p.is_absolute() or '..' in p.parts or p.suffix!='.vtu':raise ValueError('Invalid volume path')
    if rel in self.index:raise ValueError('Duplicate receipt member')
    if rel not in expected or any(row[k]!=expected[rel][k] for k in ('bytes','sha256')):raise ValueError('Receipt member differs from original manifest')
    self.index[rel]=dict(row,archive=archive,receipt=rp)
 def _read(self,rel):
  if rel in self.used:raise ValueError('Repeated archived frame: monotone streaming only')
  row=self.index[rel];archive=row['archive']
  if archive not in self.streams:
   if sha(archive)!=self.archive_hashes[archive]:raise ValueError('Archive SHA mismatch')
   proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   tar=tarfile.open(fileobj=proc.stdout,mode='r|');self.streams[archive]=(proc,tar,iter(tar))
  proc,tar,it=self.streams[archive]
  for member in it:
   if member.name!=rel:continue
   if not member.isfile() or member.size!=row['bytes']:raise ValueError('Archive member type/size mismatch')
   data=tar.extractfile(member).read()
   if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Decoded member SHA mismatch')
   self.used.add(rel);return data
  raise ValueError('Missing member or nonmonotone request: '+rel)
 @contextmanager
 def frame(self,paths):
  created=[];total=0
  try:
   for original in paths:
    p=Path(original).absolute();rel=str(p.relative_to(self.work))
    if p.is_symlink() or p.parent.resolve()!=p.parent:raise ValueError('Symlink in materialization path')
    if rel not in self.index:raise ValueError('No restoration receipt for requested path')
    row=self.index[rel]
    if p.exists():
     if sha(p)!=row['sha256']:raise ValueError('Retained member SHA mismatch')
     continue
    if not p.parent.is_dir():raise ValueError('Missing original output directory')
    if shutil.disk_usage(self.work).free<20*2**30+row['bytes']+64*2**20:raise RuntimeError('Insufficient materialization capacity')
    data=self._read(rel);pending=p.with_name(p.name+'.stream-restore-pending')
    with pending.open('xb') as f:f.write(data)
    if sha(pending)!=row['sha256']:raise ValueError('Written member SHA mismatch')
    os.replace(pending,p);created.append((p,row));total+=row['bytes'];self.restored.append(dict(path=rel,sha256=row['sha256'],bytes=row['bytes'],archive=str(row['archive']),receipt=str(row['receipt'])))
   self.peak_frame_bytes=max(self.peak_frame_bytes,total)
   yield
  finally:
   for p,row in reversed(created):
    if sha(p)!=row['sha256']:raise ValueError('Restored input modified during read; retained for investigation')
    p.unlink()
 def close(self):
  for proc,tar,it in self.streams.values():
   tar.close();proc.stdout.close()
   if proc.poll() is None:proc.terminate()
   proc.wait();proc.stderr.close()
  self.streams.clear()
 def report(self):
  return dict(receipt_sha256=self.receipt_hashes,source_manifest_sha256=self.manifest_hashes,restored_members=self.restored,peak_frame_bytes=self.peak_frame_bytes,archive_sha256={str(k):v for k,v in self.archive_hashes.items()},scope='Only requested members are decoded/restored; archive SHA verified before streaming. Original comparison reader used inside frame context; created raw copies removed only after SHA recheck. No norm/phase/gate changes.')
