from pathlib import Path
import json,hashlib,struct
root=Path(__file__).resolve().parents[2];w=root/'build/recompute-20261109/reference-strict-stop-equivalence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def actual(folder,kind,step):
 matches=[p for p in folder.glob(kind+'_*') if p.stem.rsplit('_',1)[1].isdecimal() and int(p.stem.rsplit('_',1)[1])==step]
 assert len(matches)==1;return matches[0]
r=json.loads((w/'report.json').read_text());assert r['passed'] and not r['adopted'];used={};pairs=0
for name,baseline in [('startup-strict','startup-old'),('loaded-strict','loaded-old'),('loaded-replay','loaded-strict')]:
 run=r['runs'][name]
 for step in range(run['start']+1,run['stop']+1):
  files=[actual(w/x/'results','stFile',step) for x in (baseline,name)];a,b=[p.read_bytes() for p in files]
  assert len(a)==len(b) and a[:40]==b[:40] and a[48:]==b[48:]
  stamp=struct.unpack_from('<8i',a);assert stamp[0]==1 and stamp[-1]==step
  assert len(a)==32+8*(2+stamp[1]+3*stamp[5]*stamp[3])
  vtk=[actual(w/x/'results','result',step) for x in (baseline,name)];assert vtk[0].read_bytes()==vtk[1].read_bytes()
  for p in files+vtk:used[str(p.relative_to(w))]=sha(p)
  pairs+=1
assert pairs==50
out=dict(passed=True,report_sha256=sha(w/'report.json'),source_sha256=sha(Path(__file__)),native_pairs=pairs,vtu_pairs=pairs,native_bitwise_equal_except_elapsed=True,vtu_files_bitwise_equal=True,consumed_sha256=used,production_adopted=False,scope='Independent byte-level review of bounded already-converged paths; diagnostic derivative is not original pinned source or full physical qualification')
assert not (w/'independent-review.json').exists();(w/'independent-review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='consumed_sha256'},indent=2))
