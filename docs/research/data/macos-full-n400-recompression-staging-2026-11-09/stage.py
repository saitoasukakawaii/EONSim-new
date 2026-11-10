"""Stage a smaller full N400 archive without changing canonical data or receipts."""
from pathlib import Path
import subprocess,json,hashlib,time,shutil
b=Path(__file__).resolve().parent;rp=b/'archives/elastic-s24-l1-n400.json';r=json.loads(rp.read_text());original=Path(r['archive']);out=b/'full-n400-level19-staged';assert not out.exists();out.mkdir();candidate=out/'candidate.pending'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def decoded(p):
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(p)],stdout=subprocess.PIPE);h=hashlib.file_digest(proc.stdout,'sha256').hexdigest();assert proc.wait()==0;return h
assert sha(original)==r['archive_sha256'] and original.stat().st_size==r['archive_bytes'];assert sha(Path(r['source_manifest']))==r['source_manifest_sha256'];assert shutil.disk_usage(b).free>20*2**30+r['archive_bytes']+256*2**20
(out/'original-receipt.json').write_bytes(rp.read_bytes());start=time.time()
(out/'status.json').write_text(json.dumps(dict(status='encoding',start_unix=start,original=str(original),original_sha256=r['archive_sha256']),indent=2)+'\n')
dec=subprocess.Popen(['zstd','-q','-d','-c',str(original)],stdout=subprocess.PIPE);enc=subprocess.Popen(['zstd','-q','-19','-T1','-o',str(candidate)],stdin=dec.stdout);dec.stdout.close()
try:
 while enc.poll() is None:
  if candidate.exists() and candidate.stat().st_size>r['archive_bytes']:raise RuntimeError('Candidate larger than original; stop without changing canonical archive')
  if shutil.disk_usage(b).free<20.5*2**30:raise RuntimeError('Preserve shared disk floor')
  time.sleep(5)
 assert enc.returncode==0 and dec.wait()==0
 assert sha(original)==r['archive_sha256'];h=decoded(original);assert decoded(candidate)==h
 result=dict(status='verified-staged',original=str(original),original_sha256=r['archive_sha256'],candidate=str(candidate),candidate_sha256=sha(candidate),original_bytes=r['archive_bytes'],candidate_bytes=candidate.stat().st_size,decoded_tar_sha256=h,start_unix=start,finished_unix=time.time(),scope='Canonical archive and all receipts untouched. Staged only. Adoption requires updating every matching archive/materialization receipt with a recoverable transaction and catalog check.')
 (out/'status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
except BaseException as error:
 for proc in [enc,dec]:
  if proc.poll() is None:proc.terminate()
 for proc in [enc,dec]:proc.wait()
 (out/'status.json').write_text(json.dumps(dict(status='failed-canonical-untouched',error=repr(error),start_unix=start,finished_unix=time.time()),indent=2)+'\n');raise
