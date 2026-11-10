"""Finalize original early plus independent recovered dense trajectory; preserve failed dense branch."""
from pathlib import Path
import argparse,json,re,hashlib,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve()
assert w.name=='elastic-s24-l1-n800-tautime-n400'
if not (w/'dense-recovery/receipt.json').is_file():raise ValueError('Recovered dense trajectory is incomplete; no index published')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
d=json.loads((w/'definition.json').read_text());n=d['steps_per_cycle'];receipts=[];inputs={};steps=[]
assert not (w/'completion-postflight.json').exists()
for label,start,end in [('early',1,29*n),('dense-recovery',29*n+1,32*n)]:
 folder=w/label;receipt=json.loads((folder/'receipt.json').read_text());text=(folder/'solve.log').read_text()
 assert receipt['exit_code']==0 and 'status=success' in text
 actual=list(map(int,re.findall(r'^fsi_step=(\d+) time=',text,re.M)))
 assert actual==list(range(start,end+1));steps+=actual;receipts.append(receipt)
 for name in ('receipt.json','command.json','case.json','solve.log'):inputs[str((folder/name).relative_to(w))]=sha(folder/name)
assert steps==list(range(1,32*n+1))
recovery=json.loads((w/'dense-recovery/definition.json').read_text())
assert recovery['binary_sha256']==d['binary_sha256']==sha(w/'eonsim')
assert all(sha(w/name)==digest for name,digest in d['inputs'].items())
seed=Path(recovery['seed']);assert all(sha(seed/name)==digest for name,digest in recovery['seed_sha256'].items())
assert json.loads((w/'failure.json').read_text())['error']=="RuntimeError('Disk floor')"
assert sha(w/'failure.json')==recovery['original_failure_sha256']
overlap=json.loads((w/'dense-recovery/overlap.json').read_text());assert overlap['all_byte_identical'] and len(overlap['pairs'])==878
assert {(row['step'],row['suffix']) for row in overlap['pairs']}=={(step,suffix) for step in range(23201,23640) for suffix in ['', '_solid']}
for row in overlap['pairs']:
 name=f"solution_restart23200_step{row['step']}{row['suffix']}.vtu"
 assert sha(w/'dense'/name)==sha(w/'dense-recovery'/name)==row['sha256']
for name in ['definition.json','overlap.json']:
 inputs['dense-recovery/'+name]=sha(w/'dense-recovery'/name)
inputs['original-failure.json']=sha(w/'failure.json')
prepared=[]
for suffix in ('','_solid'):
 root=ET.Element('VTKFile',type='Collection',version='0.1',byte_order='LittleEndian');collection=ET.SubElement(root,'Collection');times=[]
 for label,stem in [('early','solution'),('dense-recovery',f'solution_restart{29*n}')]:
  index=w/label/(stem+suffix+'.pvd');inputs[str(index.relative_to(w))]=sha(index)
  for data in ET.parse(index).findall('.//DataSet'):
   values=dict(data.attrib);values['file']=label+'/'+values['file'];assert (w/values['file']).is_file()
   times.append(float(values['timestep']));ET.SubElement(collection,'DataSet',values)
 assert len(times)==29+3*n and all(x<y for x,y in zip(times,times[1:]))
 target=w/('solution'+suffix+'.pvd');assert not target.exists(),'Never overwrite an existing index'
 prepared.append((target,root))
# Validate both domains before publishing either index.
for path,root in prepared:ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
dump(w/'completion-postflight.json',dict(accepted_steps=32*n,receipts=receipts,input_sha256=inputs,index_sha256={p.name:sha(p) for p,_ in prepared},original_failure_preserved=(w/'failure.json').exists(),scope='Original successful early1..23200 plus independent recovered dense23201..25600; failed original dense preserved and878 overlapping body files byte-identical. Physics/audit/budgets pending'))
print((w/'completion-postflight.json').read_text())
