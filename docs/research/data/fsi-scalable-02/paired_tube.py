"""Cold-start single-core arterial comparison using the archived physical SI meshes."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time

DATA = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(DATA.parents[2] / 'scripts'), str(DATA / 'fsi-linear-transient-2026-11-24')]
import compare_svfsi_wall as wall
from perfused_svfsi import deck, native_waveform
from harmonic_eon import SurfaceAudit
from audit_reflection import measured_ring_strains
from scaled_tube import problem
from study_rigid_tube import read_mesh
from study_hydrostatic_fsi import recovered_state
from svfsi_history import check_convergence
from vtkmodules.vtkIOXML import vtkXMLPolyDataReader

PEAK = 2e-7
DT = 1 / 32
MATERIAL = problem('arterial')[0]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            result.update(block)
    return result.hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def prepare(source, root, steps):
    eon, native = root / 'eon', root / 'svfsi'
    eon.mkdir(); native.mkdir()
    cfg = json.loads((source / 'case.json').read_text())
    fsi = cfg['fsi']
    fsi.pop('pressure_time')
    fsi.update(pressure=0., steps=steps, dt=DT, output_interval=4, checkpoint_interval=steps)
    fsi['inlet'] = dict(tag=1, ramp_time=0., flow_rate=dict(profile='circle', axis=0, center=[0,0,0],
                        radius=.01, mean=0., amplitude=PEAK/4, period=1.))
    domains = fsi['domains']
    domains.update(pressure_tags=[2], rcr_outlet=dict(tag=2, proximal_resistance=8e7,
                   distal_resistance=3.2e8, compliance=6.25e-10, distal_pressure=0., initial_capacitor_pressure=0.))
    for key, tags in [('mesh_constraints', (1,2)), ('solid_constraints', (11,12))]:
        for bc in domains[key]:
            if bc['tag'] in tags:
                bc['components'] = [0,1,2]
    save(eon / 'case.json', cfg)
    for mesh, region, tags in [('fluid','lumen',wall.FLUID_FACES), ('solid','wall',wall.SOLID_FACES)]:
        path = source / (mesh + '.msh')
        shutil.copyfile(path, eon / path.name)
        wall.export_mesh(path, native, region, tags)
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(native / 'fluid_in.vtp')); reader.Update()
    face = reader.GetOutput()
    ids = face.GetPointData().GetArray('GlobalNodeID')
    profile = {}
    for index in range(face.GetNumberOfPoints()):
        x,y,z = face.GetPoint(index)
        node = int(ids.GetTuple1(index))
        if abs(x)>1e-12 or node in profile or node<=0:
            raise ValueError('Invalid inlet identity')
        profile[node] = max(0., 1-(y*y+z*z)/.01**2)
    (native/'profile.dat').write_text(''.join(f'{node} {v:.17g}\n' for node,v in sorted(profile.items())))
    (native/'flow.fcs').write_text(native_waveform(1., 0., PEAK))
    (native/'svFSI.inp').write_text(deck(wall, MATERIAL, steps, DT, 4, False))
    return {str(p.relative_to(root)):digest(p) for folder in (eon,native) for p in sorted(folder.iterdir())}


def samples(pid):
    stack, seen, rss = [pid], set(), []
    while stack:
        current = stack.pop()
        if current in seen: continue
        seen.add(current)
        proc = Path('/proc') / str(current)
        try:
            rss.append(int((proc/'statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE'))
            for thread in (proc/'task').iterdir():
                stack.extend(map(int,(thread/'children').read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return sum(rss), max(rss, default=0)


def run(folder, command, receipt, limit):
    receipt.update(command=command, status='running', rss_peak=0, process_rss_peak=0)
    save(folder/'run.json',receipt)
    with (folder/'solve.log').open('w') as stream:
        start=time.monotonic()
        process=subprocess.Popen(command,cwd=folder,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while process.poll() is None:
                group, largest=samples(process.pid)
                receipt['rss_peak']=max(receipt['rss_peak'], group)
                receipt['process_rss_peak']=max(receipt['process_rss_peak'], largest)
                if group>8*2**30: raise MemoryError('8 GiB process-tree budget')
                if time.monotonic()-start>limit: raise TimeoutError('job time budget')
                try: process.wait(timeout=.2)
                except subprocess.TimeoutExpired: pass
            if process.returncode: raise RuntimeError(f'exit {process.returncode}')
            receipt['status']='exited'
        except BaseException as error:
            receipt.update(status=type(error).__name__,error=str(error))
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL); process.wait()
            raise
        finally:
            receipt.update(T_job=time.monotonic()-start, exit_code=process.returncode)
            stream.flush(); receipt['log_sha256']=digest(folder/'solve.log'); save(folder/'run.json',receipt)


def physical(folder, solver, meshes, steps):
    log=(folder/'solve.log').read_text(errors='replace')
    if solver=='eon':
        rows=re.findall(r'^fsi_step=(\d+) .*? residual=([^ ]+) ',log,re.M)
        if [int(s) for s,_ in rows]!=list(range(1,steps+1)) or 'status=success' not in log:
            raise ValueError('Missing EONSim accepted step or success marker')
        residuals=[float(v) for _,v in rows]
        if not all(map(math.isfinite,residuals)): raise ValueError('Nonfinite EONSim residual')
        convergence={'maximum_accepted_residual':max(residuals)}
        with (folder/'tube.csv').open() as stream: history=list(csv.DictReader(stream))
    else:
        outputs=folder/'1-procs'
        history=[list(map(float,row.split())) for row in (outputs/'RCR.dat').read_text().splitlines()]
        convergence={eq:check_convergence((outputs/'histor.dat').read_text(),steps,eq) for eq in ('FS','MS')}
    if len(history)!=steps: raise ValueError('Incomplete terminal history')
    terminal=0.; capacitor=0.; oldq=0.
    for step, row in enumerate(history,1):
        if solver=='eon':
            if int(row['step'])!=step or abs(float(row['time'])-step*DT)>1e-10: raise ValueError('Time mismatch')
            q,pc,pout,rate=[float(row['stage_'+name]) for name in ('rcr_flow','capacitor_pressure','rcr_pressure','capacitor_rate')]
            errors=[abs(6.25e-10*rate-q+pc/3.2e8)/(PEAK/4)]
        else:
            timestamp,pc,pout,q=row
            if abs(timestamp-step*DT)>1e-6: raise ValueError('Incorrect native time')
            decay=-math.expm1(-DT/.2)
            capacitor=(1-decay)*capacitor+3.2e8*(oldq*decay+(q-oldq)*(1-.2*decay/DT))
            oldq=q; errors=[abs(pc-capacitor)/20]
        errors.append(abs(pout-pc-8e7*q)/20)
        if not all(map(math.isfinite,errors)): raise ValueError('Nonfinite circuit observation')
        terminal=max(terminal,*errors)
    audit=SurfaceAudit(meshes[0],(1,2,3)); trace=[]
    interface=[]
    for mesh,tag in zip(meshes,(3,13)):
        interface.append({mesh[0][node]:node for face,triangle in mesh[2] if face==tag for node in triangle})
    if not interface[0] or interface[0].keys()!=interface[1].keys(): raise ValueError('Interface identity mismatch')
    for step in range(4,steps+1,4):
        if solver=='eon':
            states=[recovered_state(folder,f'tube_step{step}'+suffix,mesh,bool(i),1) for i,(suffix,mesh) in enumerate(zip(('','_solid'),meshes))]
        else: states=wall.external_fields(outputs/f'result_{step:03d}.vtu',meshes)
        ports=audit.observe(audit.array(states[0]),0.,.004)
        flow=[4*ports[tag]['outward_flow']/PEAK for tag in (1,2,3)]
        gap=max(math.dist(states[0][node].displacement,states[1][interface[1][coord]].displacement) for coord,node in interface[0].items())
        _,area=measured_ring_strains(meshes[1],states[1])
        trace.append(dict(step=step, outlet=flow[1], inlet_error=abs(-flow[0]-math.sin(2*math.pi*DT*step)),
                          mass_error=abs(sum(flow)), interface_gap=gap, dp=ports[1]['mean_pressure']-ports[2]['mean_pressure'], area=list(area)))
    result=dict(convergence=convergence, circuit_error=terminal, trace=trace)
    save(folder/'physical.json',result)
    return result


def compare(left,right):
    checks={'circuit':max(left['circuit_error'],right['circuit_error'])/2e-6}
    for a,b in zip(left['trace'],right['trace']):
        pair=dict(inlet=max(a['inlet_error'],b['inlet_error'])/2e-6, mass=max(a['mass_error'],b['mass_error'])/.05,
                  interface=max(a['interface_gap'],b['interface_gap'])/1e-8, outlet=abs(a['outlet']-b['outlet'])/.05,
                  pressure=abs(a['dp']-b['dp'])/1.6, area=max(abs(x-y) for x,y in zip(a['area'],b['area']))/(.08*MATERIAL.lame_area_strain(20)))
        for key,value in pair.items(): checks[key]=max(checks.get(key,0),value)
    return checks


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('case','root','eon','svfsi'): cli.add_argument('--'+name,required=True,type=Path)
    cli.add_argument('--steps',type=int,choices=(20,32,100),required=True)
    cli.add_argument('--timeout',type=int,default=1800)
    cli.add_argument('--gate',type=Path)
    args=cli.parse_args()
    binaries={name:getattr(args,name).resolve() for name in ('eon','svfsi')}
    identities={name:digest(file) for name,file in binaries.items()}
    case_files={name:digest(args.case/name) for name in ('case.json','fluid.msh','solid.msh')}
    affinity=sorted(os.sched_getaffinity(0))
    if len(affinity)!=1 or not os.environ.get('SLURM_JOB_ID'): cli.error('requires a one-core Slurm job step')
    if args.steps!=20:
        gate=json.loads(args.gate.read_text()) if args.gate else {}
        if not (gate.get('passed') and gate.get('steps')==20 and gate.get('binaries')==identities and gate.get('case')==case_files):
            cli.error('requires a passing 20-step receipt with the same inputs and binaries')
    os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    root=args.root.resolve(); root.mkdir(parents=True,exist_ok=False)
    prepared=root/'prepared'; prepared.mkdir(); start=time.monotonic(); files=prepare(args.case,prepared,args.steps)
    result=dict(steps=args.steps,binaries=identities,case=case_files,inputs=files,affinity=affinity,slurm=os.environ['SLURM_JOB_ID'],
                T_prepare=time.monotonic()-start,passed=False,runs=[])
    save(root/'summary.json',result)
    meshes=[read_mesh(args.case/(s+'.msh')) for s in ('fluid','solid')]
    for iteration in range(1 if args.steps==20 else 4):
        pair={}; receipts={}
        for solver in (('eon','svfsi') if iteration%2==0 else ('svfsi','eon')):
            folder=root/f'{iteration}-{solver}'; shutil.copytree(prepared/solver,folder)
            extra=['-case','case.json'] if solver=='eon' else ['svFSI.inp']
            kind='correctness' if args.steps==20 else 'timed' if iteration else 'warmup'
            receipt=dict(solver=solver,kind=kind,iteration=iteration)
            receipts[solver]=receipt; result['runs'].append(receipt)
            try:
                run(folder,[str(binaries[solver]),*extra],receipt,args.timeout)
                pair[solver]=physical(folder,solver,meshes,args.steps)
                receipt['status']='validated-output'
            except Exception as error:
                receipt.update(error=str(error),status='failed'); raise
            finally: save(root/'summary.json',result)
        checks=compare(pair['eon'],pair['svfsi']); result.setdefault('normalized_gates',[]).append(checks)
        save(root/'summary.json',result)
        if not all(math.isfinite(v) and v<=1 for v in checks.values()): raise ValueError(f'Physical gates failed: {checks}')
    result['passed']=True
    if args.steps!=20:
        medians={solver:statistics.median(r['T_job'] for r in result['runs'] if r['solver']==solver and r['kind']=='timed') for solver in binaries}
        result.update(medians=medians,S_svFSI=medians['svfsi']/medians['eon'])
    save(root/'summary.json',result)


if __name__=='__main__': main()
