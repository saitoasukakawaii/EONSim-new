"""Archive completed immutable raw data; verify every member; never remove sources."""
from pathlib import Path
import argparse,tarfile,hashlib,json,subprocess,shutil,time,os
p=argparse.ArgumentParser();p.add_argument('alpha',type=int,choices=[1,2]);a=p.parse_args()
b=Path(__file__).resolve().parent;root=b.parents[1];name=f'alpha{a.alpha}-s96-l1-n800';w=b/name
e=root/f'docs/research/data/macos-alpha{a.alpha}-s96-l1-n800-2026-11-09';manifest=e/'raw-manifest.json';m=json.loads(manifest.read_text());completion=json.loads((e/'completion.json').read_text())
assert completion['accepted_steps']==4800 and all(completion['preliminary_gates'].values())
assert json.loads((b/(name+'.execution.json')).read_text())['exit_code']==0
expected={r['path']:r for r in m['files']};assert len(expected)==len(m['files'])
actual={str(p.relative_to(w)) for p in w.rglob('*') if p.is_file()};assert actual==set(expected)
for rel,row in expected.items():
 q=Path(rel);assert not q.is_absolute() and '..' not in q.parts and not (w/q).is_symlink();assert (w/q).stat().st_size==row['bytes']
out=b/'archives';out.mkdir(exist_ok=True);dest=out/(name+'.tar.zst');pending=dest.with_suffix(dest.suffix+'.pending');receipt=out/(name+'.json')
assert not dest.exists() and not pending.exists() and not receipt.exists()
assert shutil.disk_usage(out).free>20*1024**3+sum(r['bytes'] for r in expected.values())
cmd=['zstd','-q','-3','-T1','--long=27','-o',str(pending)]
t=time.monotonic();proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
try:
 with tarfile.open(fileobj=proc.stdin,mode='w|') as archive:
  for rel in sorted(expected):archive.add(w/rel,arcname=rel,recursive=False)
 proc.stdin.close();assert proc.wait()==0
except BaseException:
 if proc.poll() is None:proc.terminate();proc.wait()
 raise
compress_seconds=time.monotonic()-t;t=time.monotonic();proc=subprocess.Popen(['zstd','-q','-d','-c',str(pending)],stdout=subprocess.PIPE);seen=set();total=0
try:
 with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
  for member in archive:
   assert member.isfile() and member.name in expected and member.name not in seen
   row=expected[member.name];assert member.size==row['bytes'];stream=archive.extractfile(member)
   assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256'];seen.add(member.name);total+=member.size
 proc.stdout.read();assert proc.wait()==0 and seen==set(expected)
except BaseException:
 if proc.poll() is None:proc.terminate();proc.wait()
 raise
with pending.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
assert not dest.exists();os.rename(pending,dest)
result=dict(work=str(w),archive=str(dest),archive_bytes=dest.stat().st_size,archive_sha256=digest,source_manifest=str(manifest),source_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),verified_members=len(seen),source_bytes=total,compression_seconds=compress_seconds,verification_seconds=time.monotonic()-t,command=cmd,zstd_version=subprocess.check_output(['zstd','--version'],text=True).strip(),source_removed=False,scope='Complete source manifest archived and every member decoded/SHA-verified. Originals retained. Removal of redundant materialized files requires completion of all outstanding scientific consumers and a separately recorded action.')
receipt.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
