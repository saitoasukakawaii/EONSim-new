"""Bind recorded, user-authorized Newmark mesh-increment reference to actual proofs."""
from pathlib import Path
import json,hashlib,subprocess,difflib
b=Path(__file__).resolve().parent;out=b/'reference-kinematic-adoption.json';assert not out.exists()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
exe=b/'svfsi-kinematic-increment-build/bin/svFSI';patch=b/'svfsi-kinematic-increment.patch';definition=json.loads((b/'svfsi-kinematic-increment-definition.json').read_text());pin=definition['base_commit'];base=b/'svfsi-source';src=b/'svfsi-kinematic-increment-source'
assert sha(patch)==definition['patch_sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=base,text=True).strip()==pin and not subprocess.check_output(['git','status','--porcelain'],cwd=base,text=True)
changed=[];source_hashes={}
for rel in filter(None,subprocess.check_output(['git','ls-files','-z'],cwd=base).decode().split('\0')):
 old=(base/rel).read_bytes();new=(src/rel).read_bytes();source_hashes[rel]=hashlib.sha256(new).hexdigest()
 if old!=new:changed.append(rel)
expected=['Code/Source/svFSI/PIC.f','Code/Source/svFSI/MESH.f'];assert sorted(changed)==sorted(expected)
reconstructed=''.join(''.join(difflib.unified_diff((base/rel).read_text().splitlines(True),(src/rel).read_text().splitlines(True),fromfile='a/'+rel,tofile='b/'+rel)) for rel in expected);assert reconstructed==patch.read_text()
proofs={}
def read(rel):
 p=b/rel;proofs[rel]=sha(p);return json.loads(p.read_text())
for folder in ['reference-kinematic-increment-startup','reference-kinematic-increment-coarse-startup','reference-kinematic-increment-equivalence','reference-kinematic-increment-fine-diagnostic']:
 assert read(folder+'/definition.json')['new_sha256']==sha(exe)
for folder,first,last in [('reference-kinematic-increment-startup',1,600),('reference-kinematic-increment-coarse-startup',1,800),('reference-kinematic-increment-fine-diagnostic',401,540)]:
 r=read(folder+'/cg-fsils/convergence.json');assert r['passed'] and r['iteration_limit_rows']==0 and (r['first_step'],r['last_step'],r['final_equation_rows'])==(first,last,2*(last-first+1));assert r['log_sha256']==sha(b/folder/'cg-fsils/solve.log')
for folder in ['reference-kinematic-increment-startup','reference-kinematic-increment-fine-diagnostic']:
 r=read(folder+'/field-diagnostic.json');assert all(v['pairs']==140 and v['field_and_history_tolerances_passed'] and v['saved_norm_bound_passed'] for v in r['comparisons'].values())
 for rel,digest in r['consumed_sha256'].items():assert sha(b/rel)==digest
r=read('reference-kinematic-increment-equivalence/field-diagnostic.json');assert not r['original_exact_norm_check_passed'];assert sum(v['pairs'] for v in r['comparisons'].values())==50
assert all(v['field_and_history_tolerances_passed'] for v in r['comparisons'].values());assert r['comparisons']['loaded-replay']['maximum_native_history_delta']==0
independent=read('reference-kinematic-increment-equivalence/independent-review.json');assert independent['independent_diagnostic_verified'] and not independent['original_exact_norm_check_passed']
for rel,digest in independent['consumed_sha256'].items():assert sha(b/rel)==digest
roundoff=read('reference-kinematic-increment-equivalence/startup-norm-roundoff.json');assert roundoff['positive_norm_ulp_distances']==[0,1]
# An already-running from-zero coarse long diagnostic must use this exact build
# and every available frozen strict prefix must pass. Completion remains separate.
w=b/'reference-kinematic-long-elastic-s24-l0-n800-nu0';assert sha(w/'svFSI')==sha(exe);prefixes=sorted(w.glob('prefix-*/convergence.json'),key=lambda p:int(p.parent.name.split('-')[1]));assert prefixes
last=0
for p in prefixes:
 r=json.loads(p.read_text());assert r['passed'] and r['iteration_limit_rows']==0 and r['log_sha256']==sha(p.parent/'frozen.log');proofs[str(p.relative_to(b))]=sha(p);last=r['last_step']
assert last>=800
cache=b/'svfsi-kinematic-increment-build/CMakeCache.txt';assert 'CMAKE_HOME_DIRECTORY:INTERNAL='+str(src/'Code') in cache.read_text()
for name in ['svfsi-kinematic-increment-definition.json','svfsi-kinematic-increment-configure.log','svfsi-kinematic-increment-build.log','svfsi-kinematic-increment-rebuild.log']:proofs[name]=sha(b/name)
result=dict(passed=True,user_authorized=True,user_instruction='允许采用有记录、经验证的补丁',base_commit=pin,binary_sha256=sha(exe),patch_sha256=sha(patch),changed_source_files=changed,source_sha256=source_hashes,proofs=proofs,coarse_long_prefix_verified=last,original_exact_norm_probe_passed=False,recorded_norm_difference=roundoff,scope='Adopt only for this constant-step linear-elastic FSI pressure-tube family with homogeneous fixed ends, meshnu0 and matched shared spectral radius. Mesh interior uses mesh beta; structural/interface copies use FSI beta. Original convergence/field limits retained; startup saved MS norm differs by1ULP and exact-identity failure remains preserved. Full32cycle convergence, physics and independent budgets are not yet qualified. Original/older patched trajectories remain distinct.')
out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print({k:v for k,v in result.items() if k not in ['source_sha256','proofs','recorded_norm_difference']})
