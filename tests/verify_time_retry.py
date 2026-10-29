"""Real Newton nonconvergence -> rollback/cutback; compare to a direct small-step trajectory."""
import argparse,copy,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/fsi'))
from generate_domains import generate
p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
case=generate(a.work);config=json.loads(case.read_text());config['fsi'].update(material='neo_hookean',pressure=20,dt=.04,steps=1);config['time_control']=dict(max_retries=6,minimum_dt=.0005,reduction=.5);case.write_text(json.dumps(config))
def run(args,ok=True):
 r=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=100)
 if (r.returncode==0)!=ok:raise RuntimeError(r.stdout)
 return r.stdout
def compare(first,second,ranks):
 for solid in ('','_solid'):
  for rank in range(ranks):
   suffix=solid+(f'_rank{rank}' if ranks>1 else '')+'.vtu';x=ET.parse(first.with_name(first.stem+suffix));y=ET.parse(second.with_name(second.stem+suffix))
   for u,v in zip(x.findall('.//DataArray'),y.findall('.//DataArray')):
    if u.attrib.get('type')=='Float64':assert max((abs(float(i)-float(j)) for i,j in zip(u.text.split(),v.text.split())),default=0)<2e-8
for ranks in (1,2):
 part=a.work/f'parts{ranks}';run([a.executable,'-case',case,'-prepare',part,'-parts',ranks]);launcher=[a.mpiexec,'-n',ranks] if ranks>1 else []
 prefix=launcher+[a.executable,'-case',case,'-partition',part,'-snes_max_it',2]
 full=a.work/f'full{ranks}.vtu';text=run(prefix+['-output',full]);retries=re.findall(r'step_retry=\d+ time=(\S+) next_dt=(\S+)',text)
 assert retries and all(float(time)==0 for time,dt in retries)
 dt=float(retries[-1][1]);steps=round(.04/dt);assert abs(steps*dt-.04)<1e-12
 reference=copy.deepcopy(config);reference['fsi'].update(dt=dt,steps=steps);reference['time_control']['max_retries']=0
 fixed=a.work/'fixed.yaml';fixed.write_text(json.dumps(reference));ref=a.work/f'reference{ranks}.vtu'
 run(launcher+[a.executable,'-case',fixed,'-partition',part,'-snes_max_it',2,'-output',ref]);compare(full,ref,ranks)
 checkpoint=a.work/f'checkpoint{ranks}';run(prefix+['-checkpoint',checkpoint,'-stop_after',3,'-output',a.work/'partial.vtu'])
 resumed=a.work/f'resumed{ranks}.vtu';tail=run(prefix+['-restart',checkpoint,'-output',resumed]);compare(full,resumed,ranks)
 assert float(re.findall(r'fsi_step=\d+ time=(\S+)',tail)[0])>3*dt
 failure=run(prefix+['-snes_max_it',0],False);assert 'retries exhausted' in failure
 print('retry rollback/restart',ranks,'accepted dt',dt,'steps',steps)
print('time retry verification passed')
