"""Fresh six-cycle Womersley budgets, fixed original10% gates and dense sampling."""
from pathlib import Path
import sys,json,math,hashlib,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from analyze_womersley import Study
from compare_womersley import compare
FIELDS=('velocity','pressure')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
class TrackedStudy(Study):
 def __init__(self,work):super().__init__(work);self.used_steps=set()
 def state(self,step):self.used_steps.add(step);return super().state(step)
 def evidence(self):
  names=[self.work/'definition.json',self.work/'receipt.json',self.work/'fluid.msh']
  for step in sorted(self.used_steps):
   folder=self.generations[step][0];names.append(folder/'manifest');names.extend(folder/f'state_rank{r}.h5' for r in range(self.definition['ranks']))
  return {str(p.relative_to(self.work)):sha(p) for p in names}
def family(studies):
 coarse,target,fine=studies;d=[s.definition for s in studies];n=d[1]['steps_per_cycle']
 if n<8 or n%2 or [x['steps_per_cycle'] for x in d]!=[n,n,2*n]:raise ValueError('Need matched target spatial pair and dt/2 control')
 if [x['level'] for x in d]!=[d[0]['level'],d[0]['level']+1,d[0]['level']+1]:raise ValueError('Need one red-refinement spatial pair and same fine time mesh')
 for s,x in zip(studies,d):
  if x['phases']!=x['steps_per_cycle'] or x['warmup']!=2 or s.receipt['step']!=6*x['steps_per_cycle']:raise ValueError('Need complete six cycles with every accepted phase after two warmup cycles')
 ignored={'level','steps_per_cycle','phases'}
 if any({k:v for k,v in x.items() if k not in ignored}!={k:v for k,v in d[0].items() if k not in ignored} for x in d[1:]):raise ValueError('Study definitions differ beyond field refinement and timestep')
 if sha(target.work/'fluid.msh')!=sha(fine.work/'fluid.msh'):raise ValueError('Time-control mesh differs')
 return n
def checked_analysis(path,study):
 r=json.loads(path.read_text());m=r['metrics']
 if r['definition']!=study.definition or r['last_cycle']!=6 or r['quadrature_order']!=4:raise ValueError('Analysis belongs to a different study/window/quadrature')
 for item in (r['last_periodic_difference'],r['preceding_periodic_difference']):
  if set(item)!=set(FIELDS) or any(not math.isfinite(v) or v<0 for v in item.values()):raise ValueError('Invalid periodic evidence')
 required=('velocity_relative_l2_error','pressure_rms_over_amplitude','flow_amplitude_relative_error','flow_phase_error_degrees','maximum_net_flux')
 if any(not math.isfinite(m[k]) or m[k]<0 for k in required):raise ValueError('Invalid analytic metric')
 gates=dict(velocity=m[required[0]]<.01,pressure=m[required[1]]<.01,flow_amplitude=m[required[2]]<.01,flow_phase=m[required[3]]<1,global_mass=m[required[4]]<1e-10,periodic=max(*r['last_periodic_difference'].values(),*r['preceding_periodic_difference'].values())<1e-6)
 if gates!=r['preliminary_gates']:raise ValueError('Changed or inconsistent analytic gate')
 return gates
def sampling(study,scales):
 n=study.definition['steps_per_cycle'];start=5*n;cache={};sums={k:0. for k in FIELDS};maximum=sums.copy()
 def frame(step):
  if step not in cache:cache[step]=study.state(step)
  return cache[step]
 for phase in range(1,n+1):
  step=start+phase;actual=frame(step);lo=frame(step-phase%2);hi=frame(step+phase%2);delta=actual-(lo+hi)/2
  for field,sl in (('velocity',slice(0,3)),('pressure',slice(3,4))):
   value=study.mesh.squared(delta[:,sl])/study.mesh.volume/scales[field]**2
   if not math.isfinite(value) or value<0:raise ValueError('Invalid sampling norm')
   sums[field]+=value/n;maximum[field]=max(maximum[field],math.sqrt(value))
  for old in list(cache):
   if old<step:del cache[old]
 return dict(relative_rms={k:math.sqrt(v) for k,v in sums.items()},relative_maximum_phase_rms=maximum,dense_phases=n,reconstruction_phases=n//2,cycle=6,method='Linear reconstruction from actual every-other states including the real cycle5 endpoint; exact P1 mass')
def main():
 p=argparse.ArgumentParser()
 for name in ('coarse','target','time-fine','coarse-analysis','target-analysis','time-analysis','output'):p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args()
 for work in (a.coarse,a.target,a.time_fine):
  if not (work/'definition.json').is_file() or not (work/'receipt.json').is_file():raise ValueError('Incomplete study receipt: '+str(work))
  definition=json.loads((work/'definition.json').read_text());receipt=json.loads((work/'receipt.json').read_text())
  if receipt['step']!=6*definition['steps_per_cycle']:raise ValueError('Incomplete six-cycle study: '+str(work))
 studies=[TrackedStudy(w.resolve()) for w in (a.coarse,a.target,a.time_fine)];n=family(studies)
 paths=[a.coarse_analysis,a.target_analysis,a.time_analysis];gates=[checked_analysis(path,s) for path,s in zip(paths,studies)]
 if a.output.exists():raise ValueError('Refuse to overwrite a prior budget')
 coarse,target,fine=studies
 reports=dict(space=compare(coarse,target),time=compare(target,fine),tail=compare(target,target,5,6));reports['sampling']=sampling(target,reports['space']['reference_scales'])
 terms={}
 for field in FIELDS:
  space=reports['space']['relative_rms'][field];rows={}
  for name in ('time','tail','sampling'):
   value=reports[name]['relative_rms'][field];rows[name]=dict(relative_rms=value,ratio_to_space=value/space if space>0 else None,passed=space>0 and value<.1*space)
  terms[field]=dict(space_relative_rms=space,terms=rows)
 eligible=all(gates[1].values()) and all(gates[2].values()) and gates[0]['periodic'] and gates[0]['global_mass']
 result=dict(target_steps_per_cycle=n,alpha=target.definition['alpha'],eligibility=dict(zip(('coarse','target','time_fine'),gates)),eligible=eligible,fields=terms,limit_fraction=.1,passed=eligible and all(t['passed'] for f in terms.values() for t in f['terms'].values()),reports=reports,input_sha256={str(s.work):s.evidence() for s in studies},analysis_sha256={str(p.resolve()):sha(p) for p in paths},source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'scripts/analyze_womersley.py',ROOT/'scripts/compare_womersley.py')},scope='Target fine state numerical budget only; geometry and remaining production gates separate; dt/2 control is not independently spatially qualified')
 a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('reports','input_sha256')}))
 if not result['passed']:raise SystemExit('Original Womersley analytic or independent10% budget gate failed')
if __name__=='__main__':main()
