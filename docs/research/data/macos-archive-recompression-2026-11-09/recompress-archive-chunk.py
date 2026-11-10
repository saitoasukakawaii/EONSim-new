"""Replace one chunk losslessly with a journaled old/new receipt transaction."""
from pathlib import Path
import argparse,json,hashlib,subprocess,shutil,os,time
p=argparse.ArgumentParser();p.add_argument('receipt',type=Path);p.add_argument('--probe',type=Path);a=p.parse_args();b=Path(__file__).resolve().parent;rp=a.receipt.resolve();r=json.loads(rp.read_text());archive=Path(r['archive']);assert rp.parent==archive.parent and archive.parent.parent==b/'archives' and r['status']=='evicted'
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(path,obj):
 tmp=path.with_name(path.name+'.write-pending');assert not tmp.exists();tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,path)
def decoded(path):
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(path)],stdout=subprocess.PIPE);digest=hashlib.file_digest(proc.stdout,'sha256').hexdigest();assert proc.wait()==0;return digest
assert sha(archive)==r['archive_sha256'] and archive.stat().st_size==r['archive_bytes'];assert sha(Path(r['source_manifest']))==r['source_manifest_sha256']
t=b/'archive-recompression'/archive.parent.name/archive.name.removesuffix('.tar.zst');assert not t.exists();t.mkdir(parents=True)
oldtext=rp.read_bytes();(t/'old-receipt.json').write_bytes(oldtext);oldsha=sha(archive);new=t/'new-archive.pending';backup=t/'old-archive.backup';start=time.time()
assert shutil.disk_usage(b).free>20*2**30+archive.stat().st_size+64*2**20
if a.probe:
 probe=a.probe.resolve();assert probe==b/'archive-level19-probe.tar.zst';shutil.copyfile(probe,new)
else:
 dec=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);enc=subprocess.Popen(['zstd','-q','-19','-T1','-o',str(new)],stdin=dec.stdout);dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
olddecoded=decoded(archive);assert decoded(new)==olddecoded;newsha=sha(new)
j=dict(receipt=str(rp),archive=str(archive),old_archive_sha256=oldsha,new_archive_sha256=newsha,old_bytes=archive.stat().st_size,new_bytes=new.stat().st_size,decoded_tar_sha256=olddecoded,start_unix=start,encoding='zstd19 single thread',status='verified',recovery='If interrupted after rename: retain both files; inspect current archive SHA and receipt. Restore old-archive.backup and old-receipt.json together, or finish verified new pair. Never delete the only matching pair.')
dump(t/'journal.json',j)
if new.stat().st_size>=archive.stat().st_size:
 new.unlink();j.update(status='kept-original-no-gain',finished_unix=time.time());dump(t/'journal.json',j);print(j['status'],archive,flush=True);raise SystemExit(0)
updated=dict(r,archive_sha256=newsha,archive_bytes=new.stat().st_size,recompression=dict(previous_archive_sha256=oldsha,previous_archive_bytes=r['archive_bytes'],decoded_tar_sha256=olddecoded,journal=str(t/'journal.json')))
os.replace(archive,backup);os.replace(new,archive);dump(rp,updated);j['status']='published-awaiting-catalog';dump(t/'journal.json',j)
assert sha(archive)==newsha and json.loads(rp.read_text())==updated
check=subprocess.run(['python3',str(b/'review-current-archive-catalog.py')],capture_output=True,text=True);(t/'catalog.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
# The catalog binds every recovery member to the new archive hash; identical tar bytes preserve all member proofs.
backup.unlink();j.update(status='committed',saved_bytes=j['old_bytes']-j['new_bytes'],finished_unix=time.time());dump(t/'journal.json',j);dump(t/'new-receipt.json',updated);print(json.dumps({k:j[k] for k in ['archive','status','saved_bytes']}),flush=True)
