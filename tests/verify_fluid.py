"""Channel refinement, accepted BE history, partition consistency and failure exit."""
import argparse
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cases/poisson'))
from generate_mesh import write_mesh
p=argparse.ArgumentParser()
p.add_argument('--executable',type=Path,required=True)
p.add_argument('--mpiexec',required=True)
p.add_argument('--work',type=Path,required=True)
a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args,success=True):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=80)
    if (r.returncode==0)!=success: raise RuntimeError(r.stdout)
    return r.stdout
def fields(path):
    root=ET.parse(path).getroot()
    return {x.attrib['Name']:list(map(float,x.text.split())) for x in root.findall('.//PointData/DataArray')}
def values(path,ranks):
    owned={}; ghosts=[]
    for rank in range(ranks):
        f=fields(path if ranks==1 else path.with_name(f'{path.stem}_rank{rank}.vtu'))
        for i,node in enumerate(f['mesh_node_id']):
            v=f['velocity'][3*i:3*i+3]+[f['pressure'][i]]
            if int(f['owner'][i])==rank:
                assert node not in owned
                owned[node]=v
            else: ghosts.append((node,v))
    for node,v in ghosts: assert max(abs(x-y) for x,y in zip(v,owned[node]))<1e-10
    return owned
def metric(text,name):
    return float(re.search(r'\b'+name+r'=([^\s]+)',text)[1])
coarse=None
for n in (4,8):
    mesh=a.work/f'cube{n}.msh'; write_mesh(mesh,n)
    for mode in (('stokes','steady','transient') if n==4 else ('stokes',)):
        case=a.work/f'{mode}{n}.yaml'; out=a.work/f'{mode}{n}.vtu'
        case.write_text(f'mesh: {mesh.resolve()}\noutput: {out.resolve()}\nfluid:\n  mode: {mode}\n  dt: 0.05\n  steps: 10\n  ramp_time: 0.1\nsolver:\n  maximum_iterations: 30\n')
        serial=run([a.executable,'-case',case])
        assert abs(metric(serial,'inlet_flow')-metric(serial,'outlet_flow'))<1e-12
        assert metric(serial,'divergence_l2')<.04
        if mode=='stokes':
            err=metric(serial,'velocity_l2_error'); dp=metric(serial,'pressure_drop')
            if n==4: coarse=err; coarse_dp=dp
            else:
                assert err<coarse/2.5
                assert abs(dp-1)<abs(coarse_dp-1)*.6
        if n==4:
            partition=a.work/'partition2'
            if mode=='stokes': run([a.executable,'-case',case,'-prepare',partition,'-parts',2])
            out2=a.work/f'{mode}2.vtu'
            parallel=run([a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',partition,'-output',out2])
            x,y=values(out,1),values(out2,2)
            assert x.keys()==y.keys()
            assert max(abs(v-w) for node in x for v,w in zip(x[node],y[node]))<2e-10
            if mode=='transient':
                assert serial.count('fluid_step=')==10
                # BE stabilization contains dt: compare its own equilibrium, not the
                # steady discretization with a different tau.
                case.write_text(case.read_text().replace('steps: 10','steps: 20'))
                out20=a.work/'transient20.vtu'
                run([a.executable,'-case',case,'-output',out20])
                settled=values(out20,1)
                assert max(abs(v-w) for node in x for v,w in zip(x[node],settled[node]))<2e-6
            if mode=='steady':
                run([a.executable,'-case',case,'-snes_max_it',0],False)
                # PETSc independently differences the assembled constrained Jacobian.
                run([a.executable,'-case',case,'-snes_test_jacobian'])
        print(mode,n,serial.strip().splitlines()[-2])
print('fluid verification passed')
