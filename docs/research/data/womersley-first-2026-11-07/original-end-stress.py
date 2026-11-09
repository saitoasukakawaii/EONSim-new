"""Compare existing pressure traces and reconstructed normal-stress harmonics.

Strong surface stress reconstructed from P1 fields need not exactly equal a
weakly imposed traction. This diagnostic does not add or relax an accuracy gate.
"""
import hashlib,json,math,shutil,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts'))
import study_rigid_tube as tube
from analyze_womersley import Study
work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'womersley-end-stress-cfa5d3c';out.mkdir()
reports=[]
for name in ('womersley-a2-s48-l0-n100','womersley-a2-s48-l1-n100','womersley-a2-s48-l0-n200'):
    study=Study(work/name);mesh=study.mesh;d=study.definition
    nodes,cells,faces=tube.read_mesh(work/name/'fluid.msh')
    index={int(n):i for i,n in enumerate(mesh.ids)}
    requested={tuple(sorted(face)):None for tag,face in faces if tag in (1,2)}
    for i,cell in enumerate(cells):
        for j in range(4):
            face=tuple(sorted(cell[:j]+cell[j+1:]))
            if face not in requested:continue
            if requested[face] is not None:raise ValueError('End face has two parents')
            requested[face]=i
    if any(i is None for i in requested.values()):raise ValueError('End face lacks a parent')
    ends={tag:[] for tag in (1,2)}
    for tag,face in faces:
        if tag not in ends:continue
        ix=np.array([index[n] for n in face]);xyz=mesh.xyz[ix]
        if np.max(abs(xyz[:,0]-(0 if tag==1 else d['length'])))>1e-12:raise ValueError('Nonplanar end')
        area=float(np.linalg.norm(np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0]))/2)
        ends[tag].append((ix,requested[tuple(sorted(face))],area))
    inverse=np.linalg.inv(np.transpose(mesh.points[:,1:]-mesh.points[:,:1],(0,2,1)))

    def traces(values):
        ux=values[mesh.cells,0]
        derivative=np.einsum('ci,ci->c',ux[:,1:]-ux[:,:1],inverse[:,:,0])
        result={}
        for tag,entries in ends.items():
            area=sum(v[2] for v in entries)
            pressure=sum(weight*values[ix,3].mean() for ix,parent,weight in entries)/area
            viscous=2*d['viscosity']*sum(weight*derivative[parent] for ix,parent,weight in entries)/area
            result[tag]=dict(area=area,faces=len(entries),pressure=pressure,
                             viscous_normal_stress=viscous,equivalent_pressure=pressure-viscous)
        return result

    # Independent affine oracle: p=3+2x, ux=x, so -sigma_nn=p-2mu.
    affine=np.zeros((len(mesh.ids),4));affine[:,0]=mesh.xyz[:,0];affine[:,3]=3+2*mesh.xyz[:,0]
    oracle=traces(affine);oracle_error=0.
    for tag,x in ((1,0),(2,d['length'])):
        oracle_error=max(oracle_error,abs(oracle[tag]['pressure']-(3+2*x)),
            abs(oracle[tag]['viscous_normal_stress']-2*d['viscosity']),
            abs(oracle[tag]['equivalent_pressure']-(3+2*x-2*d['viscosity'])))
    if oracle_error>1e-11:raise ValueError('Affine surface-stress oracle failed')
    states=study.cycle(5);phase=2*np.pi*np.arange(1,len(states)+1)/len(states)
    amplitude=np.einsum('m,mnc->nc',2*(np.sin(phase)+1j*np.cos(phase))/len(states),states)
    actual=traces(amplitude);drop=d['pressure_amplitude'];result={}
    for tag,value in actual.items():
        target=drop if tag==1 else 0.
        result[tag]={k:([float(v.real),float(v.imag)] if isinstance(v,complex) else v) for k,v in value.items()}
        result[tag].update(pressure_complex_amplitude_error_over_drop=float(abs(value['pressure']-target)/drop),
            equivalent_pressure_complex_amplitude_error_over_drop=float(abs(value['equivalent_pressure']-target)/drop))
    pressure_drop=actual[1]['pressure']-actual[2]['pressure']
    equivalent_drop=actual[1]['equivalent_pressure']-actual[2]['equivalent_pressure']
    report=dict(study=name,definition=d,cycle=5,affine_oracle_error=oracle_error,ends=result,
        pressure_drop_amplitude=[float(pressure_drop.real),float(pressure_drop.imag)],
        equivalent_pressure_drop_amplitude=[float(equivalent_drop.real),float(equivalent_drop.imag)],
        pressure_drop_complex_amplitude_error=float(abs(pressure_drop-drop)/drop),
        equivalent_pressure_drop_complex_amplitude_error=float(abs(equivalent_drop-drop)/drop))
    reports.append(report);print(json.dumps(report,allow_nan=False),flush=True)
(out/'report.json').write_text(json.dumps(dict(reports=reports,
    scope='Offline first-harmonic P1 pressure/stress traces on existing fields; no new PDE solve, extra gate or causal attribution',
    analysis_sources={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in (
        'scripts/analyze_womersley.py','scripts/study_rigid_tube.py')}),indent=2,allow_nan=False)+'\n')
shutil.copy2(__file__,out/'original-end-stress.py')
