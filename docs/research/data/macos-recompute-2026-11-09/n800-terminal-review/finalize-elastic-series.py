"""Finalize existing successful early+dense solves; never run the solver."""
from pathlib import Path
import argparse,json,re,hashlib,xml.etree.ElementTree as ET
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
d=json.loads((w/'definition.json').read_text());n=d['steps_per_cycle'];receipts=[];inputs={};steps=[]
assert not (w/'completion-postflight.json').exists()
for label,start,end in [('early',1,29*n),('dense',29*n+1,32*n)]:
 folder=w/label;receipt=json.loads((folder/'receipt.json').read_text());text=(folder/'solve.log').read_text()
 assert receipt['exit_code']==0 and 'status=success' in text
 actual=list(map(int,re.findall(r'^fsi_step=(\d+) time=',text,re.M)))
 assert actual==list(range(start,end+1));steps+=actual;receipts.append(receipt)
 for name in ('receipt.json','command.json','case.json','solve.log'):inputs[str((folder/name).relative_to(w))]=sha(folder/name)
assert steps==list(range(1,32*n+1))
prepared=[]
for suffix in ('','_solid'):
 root=ET.Element('VTKFile',type='Collection',version='0.1',byte_order='LittleEndian');collection=ET.SubElement(root,'Collection');times=[]
 for label,stem in [('early','solution'),('dense',f'solution_restart{29*n}')]:
  index=w/label/(stem+suffix+'.pvd');inputs[str(index.relative_to(w))]=sha(index)
  for data in ET.parse(index).findall('.//DataSet'):
   values=dict(data.attrib);values['file']=label+'/'+values['file'];assert (w/values['file']).is_file()
   times.append(float(values['timestep']));ET.SubElement(collection,'DataSet',values)
 assert len(times)==29+3*n and all(x<y for x,y in zip(times,times[1:]))
 target=w/('solution'+suffix+'.pvd');assert not target.exists(),'Never overwrite an existing index'
 prepared.append((target,root))
# Validate both domains before publishing either index.
for path,root in prepared:ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
dump(w/'completion-postflight.json',dict(accepted_steps=32*n,receipts=receipts,input_sha256=inputs,index_sha256={p.name:sha(p) for p,_ in prepared},original_failure_preserved=(w/'failure.json').exists(),scope='Recovered index collection after completed numerical phases; physics/audit/budgets pending'))
print((w/'completion-postflight.json').read_text())
