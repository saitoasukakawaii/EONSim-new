from pathlib import Path
import subprocess,hashlib,json,time,shutil
b=Path(__file__).resolve().parent;p=b/'archives/elastic-s24-l1-n800-geometry48-volume-chunks/0000.tar.zst';q=b/'archive-level19-probe.tar.zst';assert not q.exists();assert shutil.disk_usage(b).free>22*2**30
start=time.monotonic();dec=subprocess.Popen(['zstd','-q','-d','-c',str(p)],stdout=subprocess.PIPE);enc=subprocess.Popen(['nice','-n','15','zstd','-q','-19','-T1','-o',str(q)],stdin=dec.stdout);dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
elapsed=time.monotonic()-start
def decoded_sha(path):
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(path)],stdout=subprocess.PIPE);h=hashlib.file_digest(proc.stdout,'sha256').hexdigest();assert proc.wait()==0;return h
first=decoded_sha(p);assert decoded_sha(q)==first
r=dict(original=str(p),probe=str(q),original_bytes=p.stat().st_size,probe_bytes=q.stat().st_size,decoded_tar_sha256=first,seconds=elapsed,scope='One immutable archive compression probe only; original untouched, decoded tar bytes identical. No migration or receipt update performed.')
(b/'archive-level19-probe.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2),flush=True)
