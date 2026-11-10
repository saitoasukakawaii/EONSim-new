from pathlib import Path
import json,hashlib,re,subprocess,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';out=b/'length24-volumes-through24584-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
h=json.loads((b/'length24-capacity-hold-fourth.json').read_text());raw=subprocess.check_output(['ps','-p',str(h['pid']),'-o','pgid=,state=,command='],text=True).strip();group,state,cmd=raw.split(None,2);assert int(group)==h['pgid'] and 'T' in state and cmd==h['command']
proof=json.loads((b/(w.name+'-tail-logged-frames-through24584-compression.json')).read_text())['proof'];assert proof['through']==24584 and proof['last_logged_step']>=24585
assert sha(b.parents[1]/'src/physics/fsi.cpp')==proof['source_sha256']
assert json.loads((w/'early/receipt.json').read_text())['exit_code']==0
text=(w/'dense/solve.log').read_text();text=text[:text.rfind('\n')+1];steps=list(map(int,re.findall(r'^fsi_step=(\d+) ',text,re.M)));assert steps==list(range(23201,steps[-1]+1)) and steps[-1]>=24585
refs={(p.parent/n.attrib['file']).resolve() for p in w.rglob('*.pvd') for n in ET.parse(p).findall('.//DataSet')}
pattern=re.compile(r'^solution(?:_restart\d+)?_step(\d+)(_solid)?\.vtu$');rows=[];groups={}
for label in ('early','dense'):
 for p in sorted((w/label).glob('*.vtu')):
  m=pattern.fullmatch(p.name)
  if not m or int(m[1])>24584:continue
  assert p.resolve() in refs and not p.is_symlink();before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  rows.append(dict(path=str(p.relative_to(w)),bytes=after.st_size,sha256=digest));groups.setdefault((label,int(m[1])),set()).add(bool(m[2]))
assert len(rows)==2826 and all(v=={False,True} for v in groups.values())
assert {s for (l,s) in groups if l=='early'}==set(range(800,23201,800))
assert {s for (l,s) in groups if l=='dense'}==set(range(23201,24585))
out.write_text(json.dumps(dict(work=str(w),files=rows,through=24584,source_proof=proof,hold_receipt_sha256=sha(b/'length24-capacity-hold-fourth.json'),early_receipt_sha256=sha(w/'early/receipt.json'),accepted_log_prefix_sha256=hashlib.sha256(text.encode()).hexdigest(),scope='Immutable output-before-log body prefix only; current checkpoint and step24585 onward retained; future full audit must restore each archived input'),indent=2)+'\n');print('Captured',len(rows))
