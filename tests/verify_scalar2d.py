"""Real P1/Q1 scalar solves: independent patch/MMS, rank and time oracles."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cases/scalar2d'))
from generate import generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--checks',choices=['space','time','failure'],default='space');a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    def run(args,error=None):
        r=subprocess.run(list(map(str,args)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
        if error:
            assert r.returncode and error in r.stdout,r.stdout
        elif r.returncode:raise RuntimeError(r.stdout[-10000:])
        return r.stdout
    def solve(label,n=4,topology='mixed',version='4.1',ranks=1,distorted=False,permuted=False,change=None,extra=(),error=None):
        folder=a.work/label;case=generate(folder,n,topology,version,distorted,permuted)
        cfg=json.loads(case.read_text())
        if change:change(cfg)
        case.write_text(json.dumps(cfg));part=folder/'part'
        run([a.executable,'-case',case,'-prepare',part,'-parts',ranks])
        text=run([a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part,*extra],error)
        (folder/'run.log').write_text(text)
        if error:return {},{},text
        values={};types=set()
        for rank in range(ranks):
            path=folder/('solution.vtu' if ranks==1 else f'solution_rank{rank}.vtu');tree=ET.parse(path)
            fields={x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')}
            types.update(map(int,tree.find('.//Cells/DataArray[@Name="types"]').text.split()))
            for i,node in enumerate(fields['mesh_node_id']):
                if int(fields['owner'][i])==rank:values[int(node)]=[fields['u'][i]]+([fields['algorithmic_rate'][i]] if 'algorithmic_rate' in fields else [])
            assert len(tree.find('.//Cells/DataArray[@Name="offsets"]').text.split())==int(tree.find('.//Piece').attrib['NumberOfCells'])
        assert types==({5} if topology=='tri' else {9} if topology=='quad' else {5,9}),types
        report=dict(item.split('=') for item in [line for line in text.splitlines() if line.startswith('scalar_step=')][-1].split())
        report={k:float(v) for k,v in report.items()}
        if ranks>1:ET.parse(folder/'solution.pvtu')
        return values,report,text
    def compare(x,y,tol=2e-9):
        assert x.keys()==y.keys()
        assert max(abs(v-w) for k in x for v,w in zip(x[k],y[k]))<tol
    evidence=[]
    if a.checks=='space':
        for topology in ('tri','quad','mixed'):
            baseline=None
            for ranks in (1,2,4):
                values,report,_=solve(f'patch-{topology}-{ranks}',topology=topology,ranks=ranks,distorted=True,permuted=ranks!=1)
                assert report['l2_error']<2e-10 and report['h1_error']<2e-9,report
                assert abs(report['area']-1)<1e-12 and abs(report['stage_boundary_flux'])<2e-9,report
                if baseline:compare(values,baseline)
                baseline=values;evidence.append(dict(case=f'patch-{topology}-{ranks}',**report))
            values,_,_=solve(f'legacy-{topology}',topology=topology,version='2.2',distorted=True)
            compare(values,baseline)
            def quadratic(cfg):
                cfg['scalar2d']['manufactured']='quadratic'
                for b in cfg['scalar2d']['boundaries']:b.update(type='dirichlet');b.pop('coefficient',None)
            previous=None
            for n in (4,8,16):
                _,r,_=solve(f'refine-{topology}-{n}',n=n,topology=topology,distorted=True,change=quadratic)
                if previous:
                    r['l2_order']=math.log(previous['l2_error']/r['l2_error'],2);r['h1_order']=math.log(previous['h1_error']/r['h1_error'],2)
                    assert r['l2_order']>1.8 and r['h1_order']>.9,r
                    assert abs(r['stage_flux_balance'])<abs(previous['stage_flux_balance']),r
                previous=r;evidence.append(dict(case=f'refine-{topology}-{n}',**r))
            for ranks in (1,2,4):
                def neumann(cfg):
                    for b in cfg['scalar2d']['boundaries']:b.update(type='neumann');b.pop('coefficient',None)
                _,r,_=solve(f'neumann-{topology}-{ranks}',topology=topology,ranks=ranks,change=neumann)
                assert r['l2_error']<2e-10 and abs(r['integral'])<1e-12,r
        # A user-defined two-material problem has constant flux but a slope jump.
        for ranks in (1,2,4):
            def material(cfg):
                mesh_path=a.work/f'material-{ranks}'/'mesh.msh'
                lines=mesh_path.read_text().splitlines();start=lines.index('$Nodes');count=int(lines[start+1])
                coordinates={int(r.split()[0]):float(r.split()[1]) for r in lines[start+2:start+2+count]}
                first=lines.index('$Elements');number=int(lines[first+1])
                for i in range(first+2,first+2+number):
                    row=list(map(int,lines[i].split()))
                    if row[1] in (2,3) and sum(coordinates[n] for n in row[5:])/len(row[5:])>.5:row[3]=20
                    lines[i]=' '.join(map(str,row))
                mesh_path.write_text('\n'.join(lines)+'\n')
                cfg['scalar2d']=dict(mode='poisson',source=0,regions={'10':1,'20':2},boundaries=[dict(region='left',type='dirichlet',value=0),dict(region='right',type='dirichlet',value=.75),dict(region='bottom',type='neumann',value=0),dict(region='top',type='neumann',value=0)])
            values,r,_=solve(f'material-{ranks}',version='2.2',ranks=ranks,change=material)
            for node,v in values.items():
                x=((node-17)//7%5)/4;expected=x if x<=.5 else .5+.5*(x-.5)
                assert abs(v[0]-expected)<2e-10,(node,v,expected)
            assert abs(r['stage_boundary_flux'])<2e-9,r
        def incompatible(cfg):
            cfg['scalar2d'].pop('manufactured');cfg['scalar2d']['source']=1
            for b in cfg['scalar2d']['boundaries']:b.update(type='neumann',value=0);b.pop('coefficient',None)
        solve('incompatible',ranks=4,change=incompatible,error='Incompatible pure Neumann load')
    elif a.checks=='time':
        def transient(scheme,h,schedule=None,events=None):
            def change(cfg):
                cfg['scalar2d'].update(mode='diffusion',dt=h,steps=round(.2/h),manufactured_rate=-1)
                cfg['time']=dict(scheme=scheme)
                if scheme=='generalized_alpha':cfg['time']['rho_infinity']=.5
                cfg['time_control']={}
                if schedule:cfg['time_control']['step_sizes']=schedule
                if events:cfg['time_control']['events']=events
            return change
        for topology in ('tri','quad','mixed'):
            for scheme in ('be','bdf2','generalized_alpha'):
                previous=None
                for h in (.05,.025,.0125):
                    _,r,_=solve(f'time-{topology}-{scheme}-{h}',topology=topology,change=transient(scheme,h))
                    if previous:
                        r['order']=math.log(previous/r['l2_error'],2);assert r['order']>(.85 if scheme=='be' else 1.7),r
                    previous=r['l2_error'];evidence.append(dict(case=f'time-{topology}-{scheme}-{h}',**r));print(evidence[-1],flush=True)
                change=transient(scheme,.02,[.03,.05],[.08]);baseline=None
                for ranks in (1,2,4):
                    label=f'restart-{topology}-{scheme}-{ranks}'
                    full,_,_=solve(label,topology=topology,ranks=ranks,change=change)
                    if baseline:compare(full,baseline)
                    baseline=full
                    checkpoint=(a.work/f'checkpoint-{label}').resolve()
                    solve(label+'-partial',topology=topology,ranks=ranks,change=change,extra=['-checkpoint',checkpoint,'-stop_after',2])
                    resumed,_,text=solve(label+'-resumed',topology=topology,ranks=ranks,change=change,extra=['-restart',checkpoint])
                    compare(full,resumed)
                    assert 'time_order=1' in text.split('scalar_step=3',1)[1].splitlines()[0]
                    tree=ET.parse(a.work/label/'solution.pvd');times=[float(x.attrib['timestep']) for x in tree.findall('.//DataSet')]
                    assert times==sorted(set(times)) and abs(times[-1]-.2)<1e-14
                    for x in tree.findall('.//DataSet'):assert (a.work/label/x.attrib['file']).exists()
        # With insulating boundaries and a uniform source, the exact mass grows
        # by area*t and is representable by both P1 and Q1, without boundary reaction.
        for ranks in (1,2,4):
            def mass(cfg):
                cfg['scalar2d'].pop('manufactured')
                cfg['scalar2d'].update(mode='diffusion',dt=.025,steps=8,source=1,initial=2)
                cfg['time']=dict(scheme='bdf2')
                for b in cfg['scalar2d']['boundaries']:b.update(type='neumann',value=0);b.pop('coefficient',None)
            values,report,_=solve(f'insulated-mass-{ranks}',ranks=ranks,change=mass)
            assert max(abs(v[0]-2.2) for v in values.values())<2e-9
            assert abs(report['integral']-2.2)<2e-9 and abs(report['stage_flux_balance'])<2e-9,report
    else:
        for scheme in ('be','bdf2','generalized_alpha'):
            for ranks in (1,2,4):
                label=f'failure-{scheme}-{ranks}';checkpoint=(a.work/f'checkpoint-{label}').resolve()
                def change(cfg):
                    cfg['scalar2d'].update(mode='diffusion',dt=.05,steps=4,manufactured_rate=-1)
                    cfg['time']=dict(scheme=scheme)
                    cfg['time_control']=dict(max_retries=8,minimum_dt=1e-9)
                solve(label+'-partial',ranks=ranks,change=change,extra=['-checkpoint',checkpoint,'-stop_after',2])
                solve(label,ranks=ranks,change=change)
                snapshot=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.rglob('*') if p.is_file()}
                before=snapshot();pvd=(a.work/label/'solution.pvd').read_bytes()
                pieces=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.work/label).glob('solution_step*') if p.is_file()}
                old_pieces=pieces()
                solve(label,ranks=ranks,change=change,extra=['-checkpoint',checkpoint,'-restart',checkpoint,'-ksp_max_it',0],error='Time-step retries exhausted')
                assert snapshot()==before and (a.work/label/'solution.pvd').read_bytes()==pvd
                retried,report,text=solve(label,ranks=ranks,change=change,extra=['-restart',checkpoint,'-ksp_max_it',12,'-stop_after',3])
                assert 'step_retry=' in text,text
                assert (a.work/label/'solution.pvd').read_bytes()==pvd and pieces()==old_pieces
                segment=ET.parse(a.work/label/'solution_restart2.pvd');assert len(segment.findall('.//DataSet'))==1
                def trajectory(cfg):
                    change(cfg);cfg['time_control']['step_sizes']=[.05,.05,report['accepted_dt']]
                direct,_,_=solve(label+'-direct',ranks=ranks,change=trajectory,extra=['-stop_after',3])
                compare(retried,direct)
                evidence.append(dict(case=label,**report))
    (a.work/'results.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
