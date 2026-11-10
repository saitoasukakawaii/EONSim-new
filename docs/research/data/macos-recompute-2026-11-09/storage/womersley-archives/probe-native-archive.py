from pathlib import Path
import tarfile,hashlib,subprocess,json,time
b=Path(__file__).resolve().parent;w=b/'alpha1-s96-l1-n400';out=b/'native-archive-probe';out.mkdir()
files=sorted(w.glob('checkpoint/generation_*/state_rank0.h5'))[:32];assert len(files)==32
expected={str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
source=b.parents[1]/'docs/research/data/macos-alpha1-fine-2026-11-09/raw-manifest.json';manifest={r['path']:r for r in json.loads(source.read_text())['files']}
assert all(manifest[n]['sha256']==h for n,h in expected.items())
tar=out/'sample.tar'
with tarfile.open(tar,'w') as f:
 for p in files:f.add(p,arcname=str(p.relative_to(w)),recursive=False)
rows=[]
for label,options in [('default',['-3','-T1']),('long',['-3','-T1','--long=27'])]:
 dest=out/(label+'.tar.zst');cmd=['zstd','-q',*options,str(tar),'-o',str(dest)];t=time.monotonic();subprocess.run(cmd,check=True);elapsed=time.monotonic()-t
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(dest)],stdout=subprocess.PIPE);seen={}
 with tarfile.open(fileobj=proc.stdout,mode='r|') as f:
  for member in f:
   assert member.isfile() and member.name in expected and member.name not in seen
   raw=f.extractfile(member).read();seen[member.name]=hashlib.sha256(raw).hexdigest()
 # Drain trailing frame bytes before wait to avoid pipe blockage.
 proc.stdout.read();assert proc.wait()==0 and seen==expected
 rows.append(dict(label=label,command=cmd,seconds=elapsed,bytes=dest.stat().st_size,ratio=dest.stat().st_size/tar.stat().st_size,archive_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),members_verified=len(seen)))
assert all(hashlib.sha256((w/n).read_bytes()).hexdigest()==h for n,h in expected.items())
r=dict(input_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_members=expected,tar_bytes=tar.stat().st_size,results=rows,scope='32 completed native files only; both archives fully decoded and per-member SHA checked; original data unchanged; no full-family ratio extrapolation or deletion')
(out/'report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
