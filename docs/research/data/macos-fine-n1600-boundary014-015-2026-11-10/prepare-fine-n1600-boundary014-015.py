"""Capture only boundary outputs from completed fine N1600 segments."""
from pathlib import Path
import json,hashlib,re,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n1600';out=b/'fine-n1600-boundary-segments014-015-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
labels=[f'dense-{i:03}' for i in range(14,16)];proof={};expected_steps={};previous=49728
for label in labels:
 rp=w/label/'receipt.json';r=json.loads(rp.read_text());target=46400 if label=='early' else previous+256
 assert r['exit_code']==0 and r['previous']==previous and r['accepted_first']==previous+1 and r['accepted_last']==target
 proof[str(rp.relative_to(w))]=sha(rp);expected_steps[label]=set(range(1600,46401,1600)) if label=='early' else set(range(previous+1,target+1));previous=target
assert previous==50240
refs={(p.parent/n.attrib['file']).resolve() for p in w.rglob('*.pvd') for n in ET.parse(p).findall('.//DataSet')}
rows=[];groups={};pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)_(solid_)?boundary\.vtu$')
for label in labels:
 for p in sorted((w/label).glob('*boundary.vtu')):
  m=pattern.fullmatch(p.name)
  if not m:continue
  assert not p.is_symlink() and p.resolve() not in refs and int(m[1]) in expected_steps[label]
  before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  rows.append(dict(path=str(p.relative_to(w)),bytes=before.st_size,sha256=digest));groups.setdefault((label,int(m[1])),set()).add(bool(m[2]))
assert len(rows)==1024 and all(v=={False,True} for v in groups.values())
for label in labels:assert {step for lab,step in groups if lab==label}==expected_steps[label]
out.write_text(json.dumps(dict(work=str(w),files=rows,through=50240,receipt_sha256=proof,scope='Completed segment boundary prefix only; remaining trajectory unfinished'),indent=2)+'\n');print('captured',len(rows))
