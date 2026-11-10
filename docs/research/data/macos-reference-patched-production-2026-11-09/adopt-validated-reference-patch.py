"""Validate explicit user-authorized patch evidence before full fresh studies."""
from pathlib import Path
import json,hashlib,subprocess,difflib
b=Path(__file__).resolve().parent;out=b/'reference-patched-adoption.json';assert not out.exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
exe=b/'svfsi-strict-increment-build/bin/svFSI';patch=b/'svfsi-strict-increment.patch';definition=json.loads((b/'svfsi-strict-increment-definition.json').read_text())
assert definition['patch_sha256']==sha(patch)
base=b/'svfsi-source';src=b/'svfsi-strict-increment-source';pin=definition['base_commit']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=base,text=True).strip()==pin
assert not subprocess.check_output(['git','status','--porcelain'],cwd=base,text=True)
files=subprocess.check_output(['git','ls-files','-z'],cwd=base).decode().split('\0');changed=[];source_hashes={};reconstructed=''
for rel in filter(None,files):
 old=(base/rel).read_bytes();new=(src/rel).read_bytes();source_hashes[rel]=hashlib.sha256(new).hexdigest()
 if old!=new:changed.append(rel)
assert sorted(changed)==sorted(definition['changed'])
for rel in definition['changed']:
 reconstructed+=''.join(difflib.unified_diff((base/rel).read_text().splitlines(True),(src/rel).read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
assert reconstructed==patch.read_text()
proofs={}
for folder in ['reference-strict-increment-startup','reference-strict-increment-coarse-startup','reference-strict-increment-equivalence']:
 d=b/folder;r=json.loads((d/'definition.json').read_text());assert r['new_sha256']==sha(exe);proofs[folder+'/definition.json']=sha(d/'definition.json')
for rel in ['reference-strict-increment-startup/cg-fsils/convergence-reviewed.json','reference-strict-increment-coarse-startup/cg-fsils/convergence.json','reference-strict-increment-equivalence/report.json','reference-strict-increment-equivalence/independent-review.json']:
 p=b/rel;r=json.loads(p.read_text());assert r['passed'];proofs[rel]=sha(p)
r=json.loads((b/'reference-strict-increment-startup/cg-fsils/convergence-reviewed.json').read_text());assert (r['first_step'],r['last_step'],r['final_equation_rows'])==(1,600,1200)
assert r['log_sha256']==sha(b/'reference-strict-increment-startup/cg-fsils/solve.log')
p=b/'reference-strict-increment-startup/field-diagnostic.json';r=json.loads(p.read_text());assert all(v['pairs']==140 and v['field_and_history_tolerances_passed'] and v['saved_norm_bound_passed'] for v in r['comparisons'].values())
for rel,digest in r['consumed_sha256'].items():assert sha(b/rel)==digest
proofs[str(p.relative_to(b))]=sha(p)
p=b/'reference-strict-increment-equivalence/independent-review.json';r=json.loads(p.read_text())
for rel,digest in r['consumed_sha256'].items():assert sha(b/rel)==digest
cache=b/'svfsi-strict-increment-build/CMakeCache.txt';assert 'CMAKE_HOME_DIRECTORY:INTERNAL='+str(src/'Code') in cache.read_text()
for name in ['svfsi-strict-increment-configure.log','svfsi-strict-increment-build.log','svfsi-strict-increment-definition.json']:proofs[name]=sha(b/name)
result=dict(passed=True,user_authorized=True,user_instruction='允许采用有记录、经验证的补丁',base_commit=pin,patch_sha256=sha(patch),binary_sha256=sha(exe),changed_source_files=changed,source_sha256=source_hashes,proofs=proofs,scope='Adopt the recorded patched reference for fresh complete studies. Coarse100/fine600 strict convergence and normal50/fine140 field-history probes passed. This is not full32-cycle convergence or physical qualification. Original failures and unmodified source preserved.')
out.write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['proofs','source_sha256']})
