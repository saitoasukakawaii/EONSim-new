"""Original Womersley budget with bounded archived target-state restoration per pass."""
from pathlib import Path
import importlib.util,json,sys
b=Path(__file__).resolve().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def adapter(original):
 mat=module('budget_hdf_materializer',b/'streaming-hdf-materialization.py')
 target=(b/'alpha2-s96-l1-n800').resolve();receipt=b/'archives/alpha2-s96-l1-n800-late-capacity-materialization.json'
 fine=(b/'alpha2-s96-l1-n1600').resolve();fine_receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-prefix8800-chunks').glob('*.json'));assert len(fine_receipts)==20
 fine_tail=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-tail9360-chunks').glob('*.json'));assert len(fine_tail)==14
 fine_receipts+=fine_tail
 stores={};reports=[];context={'pass':0};Base=original.TrackedStudy
 def finish():
  for key,store in stores.items():store.close();reports.append(dict(pass_id=key[0],work=key[1],cycle=key[2],report=store.report()))
  stores.clear()
 class RestoredStudy(Base):
  def __init__(self,work):super().__init__(work);self.verified={}
  def state(self,step):
   path=self.generations[step][0]/'state_rank0.h5'
   if self.work==target and 3201<=step<=4799 and step!=4000:receipts=[receipt]
   elif self.work==fine and 8001<=step<=9360:receipts=fine_receipts
   else:return super().state(step)
   key=(context['pass'],str(self.work),(step-1)//self.definition['steps_per_cycle'])
   if key not in stores:stores[key]=mat.Volumes(self.work,receipts)
   with stores[key].frame([path]):
    digest=original.sha(path);state=super().state(step)
    assert original.sha(path)==digest
    rel=str(path.relative_to(self.work))
    if rel in self.verified:assert self.verified[rel]==digest
    self.verified[rel]=digest
    return state
  def evidence(self):
   names=[self.work/'definition.json',self.work/'receipt.json',self.work/'fluid.msh']
   for step in sorted(self.used_steps):
    folder=self.generations[step][0];names.append(folder/'manifest');names.extend(folder/f'state_rank{r}.h5' for r in range(self.definition['ranks']))
   result={}
   for path in names:
    rel=str(path.relative_to(self.work))
    if path.is_file():result[rel]=original.sha(path)
    else:
     if rel not in self.verified:raise ValueError('Missing state was not restored and hashed during actual budget read')
     result[rel]=self.verified[rel]
   return result
 def call(fn,*args,**kwargs):
  finish();context['pass']+=1
  try:return fn(*args,**kwargs)
  finally:finish()
 return RestoredStudy,call,finish,reports

def main():
 original=module('original_wom_budget',b/'audit-womersley-budget.py')
 output=Path(sys.argv[sys.argv.index('--output')+1]);proof=output.with_suffix('.materialization.json')
 if output.exists() or proof.exists():raise ValueError('Fresh budget and restoration proof required')
 for option in ['--coarse','--target','--time-fine']:
  work=Path(sys.argv[sys.argv.index(option)+1]);d=json.loads((work/'definition.json').read_text());r=json.loads((work/'receipt.json').read_text())
  if r['step']!=6*d['steps_per_cycle']:raise ValueError('Complete six-cycle study required before restoration')
 cls,call,finish,reports=adapter(original);original.TrackedStudy=cls;compare=original.compare;sampling=original.sampling
 original.compare=lambda *args,**kwargs:call(compare,*args,**kwargs)
 original.sampling=lambda *args,**kwargs:call(sampling,*args,**kwargs)
 try:original.main()
 finally:
  finish();proof.write_text(json.dumps(dict(wrapper_sha256=original.sha(Path(__file__)),budget_sha256=original.sha(b/'audit-womersley-budget.py'),materializer_sha256=original.sha(b/'streaming-hdf-materialization.py'),passes=reports,scope='Original budget comparisons and10% gates unchanged. Archived target states restored per comparison pass and cycle; evidence hashes obtained while actually reading restored bytes. FineN1600 archived cycle6 prefix and tail restored by the same per-pass mechanism.'),indent=2)+'\n')
if __name__=='__main__':main()
