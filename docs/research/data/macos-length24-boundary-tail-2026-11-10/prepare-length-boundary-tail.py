from pathlib import Path
import json,re,hashlib,subprocess,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';out=b/'length24-boundary-tail-through25180-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
hold=json.loads((b/'length24-capacity-hold-sixth.json').read_text());assert hold['status']=='held' and hold['accepted_last_before_hold']==25181
ps=subprocess.check_output(['ps','-p',str(hold['pid']),'-o','pgid=,state=,command='],text=True).strip();group,state,cmd=ps.split(None,2);assert int(group)==hold['pgid'] and 'T' in state and cmd==hold['command']
raw=(w/'dense/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fsi_step=(\d+) ',raw,re.M)));assert steps==list(range(23201,25182))
refs={(p.parent/n.attrib['file']).resolve() for p in w.rglob('*.pvd') for n in ET.parse(p).findall('.//DataSet')}
pattern=re.compile(r'^(early|dense)/solution(?:_restart\d+)?_step(\d+)_(solid_)?boundary\.vtu$');rows=[];groups={}
for p in sorted(w.rglob('*.vtu')):
 rel=str(p.relative_to(w));m=pattern.fullmatch(rel)
 if not m or not 24454<=int(m[2])<=25180:continue
 assert not p.is_symlink() and p.resolve() not in refs
 before=p.stat();digest=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 rows.append(dict(path=rel,bytes=before.st_size,sha256=digest));groups.setdefault((m[1],int(m[2])),set()).add(bool(m[3]))
assert len(rows)==1454 and all(x=={False,True} for x in groups.values())
assert {s for label,s in groups if label=='early'}==set()
assert {s for label,s in groups if label=='dense'}==set(range(24454,25181))
result=dict(work=str(w),files=rows,count=len(rows),total_bytes=sum(r['bytes'] for r in rows),through=25180,last_complete_step=25181,log_prefix_bytes=len(raw),log_prefix_sha256=hashlib.sha256(raw).hexdigest(),scope='Immutable boundary prefix only; unfinished study, no full raw inventory or numerical qualification')
out.write_text(json.dumps(result,indent=2)+'\n');print('captured',len(rows))
