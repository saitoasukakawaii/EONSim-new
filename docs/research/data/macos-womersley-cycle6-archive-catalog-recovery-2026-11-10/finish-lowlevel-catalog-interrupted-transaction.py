from pathlib import Path
import json,hashlib,subprocess,time
b=Path(__file__).resolve().parent;t=b/'archive-recompression/elastic-s24-l1-n1600-boundary-segments016-017-chunks/0000';p=t/'journal.json';j=json.loads(p.read_text());assert j['status']=='published-awaiting-catalog'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def decoded(p):
 s=subprocess.Popen(['zstd','-q','-d','-c',str(p)],stdout=subprocess.PIPE);h=hashlib.file_digest(s.stdout,'sha256').hexdigest();assert s.wait()==0;return h
backup=t/'old-archive.backup';a=Path(j['archive']);r=json.loads(Path(j['receipt']).read_text());assert sha(backup)==j['old_archive_sha256'] and sha(a)==j['new_archive_sha256']==r['archive_sha256'];assert decoded(backup)==decoded(a)==j['decoded_tar_sha256']
check=subprocess.run(['python3',str(b/'review-current-archive-catalog.py')],capture_output=True,text=True);(t/'catalog-recovered.log').write_text(check.stdout+check.stderr);assert check.returncode==0,check.stderr
(t/'interrupted-journal.json').write_bytes(p.read_bytes());backup.unlink();j.update(status='committed',saved_bytes=j['old_bytes']-j['new_bytes'],finished_unix=time.time(),recovered_after='Cycle6 prefix collection completed, independently decoded and registered; old/new archive hashes and full decoded tar identity rechecked')
p.write_text(json.dumps(j,indent=2)+'\n');(t/'new-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print('Interrupted transaction completed after full revalidation')
