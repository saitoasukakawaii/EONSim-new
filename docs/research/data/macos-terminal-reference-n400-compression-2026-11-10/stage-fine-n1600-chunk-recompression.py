"""Stage a single stronger lossless encoding without changing any live archive/receipt."""
from pathlib import Path
import subprocess,hashlib,json,time,shutil
b=Path(__file__).resolve().parent;rp=b/'archives/elastic-s24-l1-n1600-volume-after48000-chunks/0000.json';r=json.loads(rp.read_text());old=Path(r['archive']);new=b/'fine-n1600-level19-probe.tar.zst';report=b/'fine-n1600-level19-probe.json';assert not new.exists() and not report.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def decoded(p):
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(p)],stdout=subprocess.PIPE);h=hashlib.file_digest(proc.stdout,'sha256').hexdigest();assert proc.wait()==0;return h
assert sha(old)==r['archive_sha256'] and old.stat().st_size==r['archive_bytes'];assert shutil.disk_usage(b).free>20*2**30+old.stat().st_size+64*2**20
start=time.time();dec=subprocess.Popen(['zstd','-q','-d','-c',str(old)],stdout=subprocess.PIPE);enc=subprocess.Popen(['zstd','-q','-19','-T1','-o',str(new)],stdin=dec.stdout);dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
h=decoded(old);assert decoded(new)==h
result=dict(receipt=str(rp),receipt_sha256=sha(rp),old_archive_sha256=sha(old),old_bytes=old.stat().st_size,new_path=str(new),new_archive_sha256=sha(new),new_bytes=new.stat().st_size,possible_saving_bytes=old.stat().st_size-new.stat().st_size,decoded_tar_sha256=h,seconds=time.time()-start,adopted=False,scope='Single completed fine N1600 chunk probe; original archive/receipt untouched. No released capacity until a verified journaled adoption.')
report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
