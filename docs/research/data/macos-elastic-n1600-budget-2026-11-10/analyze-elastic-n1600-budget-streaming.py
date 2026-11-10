"""Apply the index-generalized original budget to complete default N1600 studies."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
b=ROOT/'build/recompute-20261109'
p=argparse.ArgumentParser();p.add_argument('--solver',choices=('eonsim',),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
roles={'coarse':(0,1600),'time':(1,800),'fine':(1,1600)};plan={};receipts={}
for role,(level,n) in roles.items():
 case=b/f'elastic-s24-l{level}-n{n}'
 work=case if a.solver=='eonsim' else b/f'reference-elastic-s24-l{level}-n{n}-nu0'
 audit=b/(work.name+'-audit.json');receipt=work/('completion.json' if (work/'completion.json').exists() else 'completion-postflight.json')
 if not audit.is_file() or not receipt.is_file():raise RuntimeError(f'Incomplete {role}: need {audit} and {receipt}; no analysis output created')
 result=json.loads(receipt.read_text());report=json.loads(audit.read_text())
 assert report['steps']==32*n and report['samples_per_cycle']==n and report['first_step']==29*n+1
 if a.solver=='eonsim':assert result['accepted_steps']==32*n and all(x['exit_code']==0 for x in result['receipts'])
 else:assert result['steps']==32*n and result['process']['exit_code']==0 and result['full_equation_convergence_passed']
 plan[role]=dict(case=str(case/'case.json'),work=str(work),audit=str(audit))
 receipts[role]=dict(path=str(receipt),sha256=sha(receipt),audit_sha256=sha(audit))
provenance=json.loads((b/'pressure-comparison-source.json').read_text())
for name,record in provenance.items():assert sha(b/name)==record['sha256']
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
fields=module('fresh_fields',b/'compare-pressure-fields.py')
source=b/'elastic-refined-budget-kernel.py'
kernel=module('unchanged_n800_kernel',source)
def make_streaming_study(fields,b):
 materializer=module('budget_volume_materializer',b/'streaming-volume-materialization.py')
 receipt_paths={
  (b/'elastic-s24-l0-n1600').resolve():sorted((b/'archives/elastic-s24-l0-n1600-volume-chunks').glob('*.json')),
  (b/'elastic-s24-l1-n800').resolve():[b/'archives/elastic-s24-l1-n800-volume-materialization.json'],
 }
 assert len(receipt_paths[(b/'elastic-s24-l0-n1600').resolve()])==22
 stores={}
 class StreamingStudy(fields.Study):
  def frame(self,step):
   if self.work not in receipt_paths:return super().frame(step)
   if self.work not in stores:stores[self.work]=materializer.Volumes(self.work,receipt_paths[self.work])
   with stores[self.work].frame(self.paths[step]):return super().frame(step)
 def study(solver,paths):
  s=StreamingStudy(Path(paths['case']),Path(paths['work']),Path(paths['audit']))
  assert s.audit['solver']==('EONSim' if solver=='eonsim' else 'svFSI')
  return s
 return study,stores
study,stores=make_streaming_study(fields,b)
out=a.output.resolve();assert not (out/a.solver).exists();out.mkdir(parents=True,exist_ok=True)
kernel.out=out;kernel.dump=dump;kernel.study=study;kernel.fields=fields;kernel.math=math;kernel.np=np;kernel.EXPECTED_ANALYZER=sha(ROOT/'scripts/audit_pressure_tube.py')
dump(out/(a.solver+'-definition.json'),dict(plan=plan,producer_receipts=receipts,kernel_source=str(source),kernel_sha256=sha(source),comparison_sources=provenance,analyzer_sha256=kernel.EXPECTED_ANALYZER,wrapper_sha256=sha(Path(__file__)),materializer_sha256=sha(b/'streaming-volume-materialization.py'),original_wrapper_sha256=sha(b/'analyze-elastic-n1600-budget.py'),scope='Original norms and10% gates preserved; target index generalized toN1600; only completed fresh default studies'))
try:
    result=kernel.analyze(a.solver,plan,receipts,target_n=1600);print(json.dumps(result))
finally:
    for store in stores.values():store.close()
    dump(out/(a.solver+'-materialization-proof.json'),{str(work):store.report() for work,store in stores.items()})
if not result['passed']:raise SystemExit('Independent N1600 error budget failed')
