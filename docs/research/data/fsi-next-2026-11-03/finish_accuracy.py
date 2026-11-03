import sys,json,csv,math,bisect
from pathlib import Path
sys.path.insert(0,'tests');from verify_fsi_inlet import Runner
w=Path('build/fsi-next-accuracy').resolve()
def rows(path):
 with path.open() as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
def dist(a,b):
 times=[r['time'] for r in b];diff=[]
 for r in a:
  i=min(len(b)-1,bisect.bisect_left(times,r['time']));j=max(0,i-1);q=0 if i==j else (r['time']-times[j])/(times[i]-times[j])
  diff.append((r['area_displacement_x']-((1-q)*b[j]['area_displacement_x']+q*b[i]['area_displacement_x']))**2)
 return math.sqrt(sum(diff)/len(diff))
# Reuse only completed actual trajectories; these runs precede the message-only endpoint rejection refinement.
for n in (2,4,8):assert 'status=success' in (w/f'n{n}'/'spatial.log').read_text()
assert 'status=success' in (w/'n8/time-half3.log').read_text()
resolved={8:rows(w/'n8/time-half3.csv')}
for n in (2,4):
 run=Runner('build/cloud-3.23.7-release/eonsim','.cloud/petsc-3.23.7/bin/mpiexec',w/f'n{n}',timeout=2400)
 cfg=json.loads((run.work/'spatial.json').read_text());cfg['fsi'].update(dt=.00025,steps=800)
 _,resolved[n],_=run.solve('resolved-spatial',cfg)
 print('Resolved spatial grid',n,flush=True)
run=Runner('build/cloud-3.23.7-release/eonsim','.cloud/petsc-3.23.7/bin/mpiexec',w/'n8',timeout=2400)
cfg=json.loads((run.work/'spatial.json').read_text());cfg['fsi'].update(dt=.000125,steps=1600)
_,fine,_=run.solve('time-final',cfg)
space=dist(resolved[4],resolved[8]);temporal=dist(resolved[8],fine)
result=dict(dt=.00025,reference_dt=.000125,space_2_4=dist(resolved[2],resolved[4]),space_4_8=space,temporal_difference=temporal,ratio=temporal/space,final={str(n):v[-1] for n,v in resolved.items()})
(w/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
assert temporal<space/4,result
