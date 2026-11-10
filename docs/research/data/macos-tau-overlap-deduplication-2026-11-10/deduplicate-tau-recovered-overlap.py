"""Preserve both immutable overlap paths while sharing identical allocated bodies."""
from pathlib import Path
import hashlib,json,os,re,time
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-tautime-n400';proof=b/'tau-recovered-overlap-deduplication.json';assert not proof.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
raw=(w/'dense-recovery/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fsi_step=(\d+) ',raw,re.M)));assert steps==list(range(23201,steps[-1]+1)) and steps[-1]>23639
assert json.loads((w/'failure.json').read_text())['error']=="RuntimeError('Disk floor')"
rows=[];started=time.time()
def dump(status,error=None):
 proof.write_text(json.dumps(dict(status=status,error=error,started_unix=started,observed_unix=time.time(),accepted_log_prefix_sha256=hashlib.sha256(raw).hexdigest(),accepted_through=steps[-1],files=rows,saved_allocated_bytes=sum(r['old_allocated_bytes'] for r in rows),scope='Only old failed dense body paths23201..23639 replaced by hardlinks to byte-identical immutable recovered bodies; both paths preserved, failed logs/checkpoint/boundaries unchanged.'),indent=2)+'\n')
try:
 for step in range(23201,23640):
  for suffix in ['', '_solid']:
   name=f'solution_restart23200_step{step}{suffix}.vtu';old=w/'dense'/name;new=w/'dense-recovery'/name;temp=old.with_name(old.name+'.verified-link-pending')
   assert not old.is_symlink() and not new.is_symlink() and not temp.exists()
   a=old.stat();c=new.stat();assert a.st_dev==c.st_dev and a.st_ino!=c.st_ino and a.st_nlink==1
   digest=sha(old);assert digest==sha(new) and a.st_size==c.st_size
   os.link(new,temp);assert sha(temp)==digest
   assert old.stat().st_ino==a.st_ino and old.stat().st_mtime_ns==a.st_mtime_ns and sha(old)==digest
   os.replace(temp,old);assert sha(old)==digest
   rows.append(dict(old_path=str(old.relative_to(w)),recovered_path=str(new.relative_to(w)),sha256=digest,bytes=a.st_size,old_allocated_bytes=a.st_blocks*512))
   dump('running')
 assert len(rows)==878
 for r in rows:assert sha(w/r['old_path'])==sha(w/r['recovered_path'])==r['sha256']
 dump('complete');print('878 immutable overlap bodies preserved; saved',sum(r['old_allocated_bytes'] for r in rows),flush=True)
except BaseException as error:dump('failed-review-remaining',repr(error));raise
