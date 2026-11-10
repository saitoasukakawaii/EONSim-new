from pathlib import Path
import json,hashlib,re,subprocess,xml.etree.ElementTree as ET
b=Path(__file__).resolve().parent;w=b/'elastic-s24-l1-n800-length24';out=b/'length24-late-output-tail-through25550-before-archive.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
hp=b/'length24-capacity-hold-eighth.json';h=json.loads(hp.read_text());assert h['accepted_last_before_hold']==25551
ps=subprocess.check_output(['ps','-p',str(h['pid']),'-o','pgid=,state=,command='],text=True).strip();group,state,cmd=ps.split(None,2);assert int(group)==h['pgid'] and 'T' in state and cmd==h['command']
cp=b/(w.name+'-tail4-logged-frames-through25550-compression.json');proof=json.loads(cp.read_text())['proof'];assert proof['through']==25550 and proof['last_logged_step']==25551 and sha(b.parents[1]/'src/physics/fsi.cpp')==proof['source_sha256']
raw=(w/'dense/solve.log').read_bytes();raw=raw[:raw.rfind(b'\n')+1];steps=list(map(int,re.findall(rb'^fsi_step=(\d+) ',raw,re.M)));assert steps==list(range(23201,25552))
refs={(p.parent/n.attrib['file']).resolve() for p in w.rglob('*.pvd') for n in ET.parse(p).findall('.//DataSet')}
pat=re.compile(r'^solution_restart23200_step(\d+)(_solid_boundary|_boundary|_solid)?\.vtu$');rows=[];groups={}
for p in sorted((w/'dense').glob('*.vtu')):
 m=pat.fullmatch(p.name)
 if not m:continue
 step=int(m[1]);suffix=m[2] or '';boundary='boundary' in suffix
 if not (25181 if boundary else 25350)<=step<=25550:continue
 assert not p.is_symlink() and (p.resolve() not in refs if boundary else p.resolve() in refs)
 st=p.stat();digest=sha(p);after=p.stat();assert (st.st_size,st.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
 rows.append(dict(path=str(p.relative_to(w)),bytes=st.st_size,sha256=digest));groups.setdefault(step,set()).add(suffix)
assert len(rows)==1142 and set(groups)==set(range(25181,25551))
for step,kinds in groups.items():assert kinds==({'_boundary','_solid_boundary'} if step<25350 else {'','_solid','_boundary','_solid_boundary'})
out.write_text(json.dumps(dict(work=str(w),files=rows,through=25550,source_proof=proof,hold_receipt_sha256=sha(hp),early_receipt_sha256=sha(w/'early/receipt.json'),log_prefix_sha256=hashlib.sha256(raw).hexdigest(),scope='Immutable late outputs:740 boundary25181..25550 and402 body25350..25550; current step25551/checkpoint retained; complete audit restores body members'),indent=2)+'\n');print('Captured',len(rows))
