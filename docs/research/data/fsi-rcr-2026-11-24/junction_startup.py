"""Solve the independent, time-discrete linear T-junction and compare actual 3D startup fields."""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from junction_harmonic import assemble
from junction_periodic import cap_and_volume,configure,digest
from study_rigid_tube import read_mesh
from verify_fsi_inlet import Runner,check_rcr_history


def advance(system,hz,n,end,first_system=None):
    b=sparse.csc_matrix(system['trace'])
    rp=sparse.diags([3.,12.]); inv_rd=sparse.diags([1/8,1/32])
    def coupled(s):
        m=sparse.block_diag([s['mass'],sparse.diags([.025,.0125])],format='csc')
        k=sparse.bmat([[s['operator']+b@rp@b.T,b],[-b.T,inv_rd]],format='csc')
        return m,k
    later=coupled(system)
    initial=coupled(first_system) if first_system is not None else later
    x=np.zeros(later[1].shape[0]);dx=np.zeros_like(x)
    dt=1/(hz*n)
    am,af,gamma=5/6,2/3,2/3
    factors={}
    history=[]
    for step in range(1,end+1):
        m,k=initial if step==1 else later
        a,f,g=(1.,1.,1.) if step==1 else (am,af,gamma)
        h=dt*f*g/a
        if h not in factors:factors[h]=splu(k+m/h)
        t=dt*(step-1+f)
        distal=np.array([.02,-.02])*math.sin(2*math.pi*hz*t)
        forcing=np.zeros_like(x)
        forcing[-2:]=inv_rd@distal
        base=x+f*dt*(1-g/a)*dx
        rhs=forcing+m@base/h
        stage=factors[h].solve(rhs)
        stage+=factors[h].solve(rhs-(k@stage+m@stage/h))
        defect=np.max(abs(k@stage+m@((stage-base)/h)-forcing))
        end_rate=(stage-x)/(f*g*dt)-(1-g)*dx/g
        x=x+(stage-x)/f
        dx=end_rate
        qs=b.T@stage[:-2]
        qe=b.T@x[:-2]
        if max(abs(qs.sum()),abs(qe.sum()))>1e-13 or defect>1e-10:raise ValueError('Unbalanced DAE step')
        history.append(dict(step=step,time=step*dt,evaluation_time=t,weak_residual=float(defect),
                            stage_flow=qs.tolist(),endpoint_flow=qe.tolist(),stage_capacitor=stage[-2:].tolist(),
                            endpoint_capacitor=x[-2:].tolist(),stage_pressure=(stage[-2:]+rp@qs).tolist(),
                            endpoint_pressure=(x[-2:]+rp@qe).tolist(),stage_distal=distal.tolist()))
    return history


def compare(reference,rows):
    if len(reference)!=len(rows):raise ValueError('Missing startup samples')
    flux_scale=max(abs(q) for r in reference for q in r['endpoint_flow'])
    p_scale=max(abs(p) for r in reference for p in r['endpoint_pressure'])
    metrics={}
    for phase in ('stage','endpoint'):
        for role,column in [('flow','rcr_flow'),('capacitor','capacitor_pressure'),('pressure','rcr_pressure')]:
            key=phase+'_'+role
            errors=[abs(ref[key][j]-row[f'{phase}_{column}_{tag}']) for ref,row in zip(reference,rows) for j,tag in enumerate((2,3))]
            metrics[key]=max(errors)/(flux_scale if role=='flow' else p_scale)
    for ref,row in zip(reference,rows):
        if max(abs(ref[k]-row[k]) for k in ('time','evaluation_time'))>1e-12:raise ValueError('Mismatched solver stage')
    return metrics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--grid',type=int,required=True)
    p.add_argument('--hz',type=float,default=1.)
    p.add_argument('--samples',type=int,default=32)
    p.add_argument('--steps',type=int,required=True)
    p.add_argument('--default-pspg',action='store_true',help='Use the normal EONSim volume coefficient and its linearization at rest')
    p.add_argument('--tau',type=float,default=.01)
    a=p.parse_args()
    if a.steps<2 or a.samples<8 or min(a.hz,a.tau)<=0:p.error('Invalid integration controls')
    exe=a.executable.resolve()
    cfg,geo=configure(a.work,a.grid,a.hz,a.samples,math.ceil(a.steps/a.samples),False,a.tau)
    cfg['fsi'].update(steps=a.steps,output_interval=a.steps)
    mesh=read_mesh(a.work/'fluid.msh')
    initial_tau=later_tau=a.tau
    initial=None
    if a.default_pspg:
        del cfg['fsi']['stabilization_tau']
        # These generated Cartesian decompositions have equal cell volumes. Check all maps before using one h.
        nodes,cells,_=mesh
        tetra=np.array([[nodes[i] for i in cell] for cell in cells])
        lengths=np.cbrt(abs(np.linalg.det(tetra[:,1:]-tetra[:,:1])))
        if np.ptp(lengths)>2e-13*lengths.mean():raise ValueError('Default-coefficient reference requires equal-volume cells')
        h=lengths[0]
        dt=1/(a.hz*a.samples)
        def tau(dt_eff):
            return float(1/math.sqrt(4/dt_eff**2+16/h**4))
        initial_tau=tau(dt)
        later_tau=tau(8*dt/15)
        initial=assemble(mesh,1,initial_tau)
    system=assemble(mesh,1,later_tau)
    reference=advance(system,a.hz,a.samples,a.steps,initial)
    runner=Runner(exe,'mpiexec',a.work,timeout=14400,interface_area=geo['interface_area'],singleton=True)
    fields,rows,_=runner.solve('startup',cfg)
    closure=max(check_rcr_history(runner,'startup',m,rows,sole_pressure=False) for m in cfg['fsi']['domains']['rcr_outlets'])
    vtu=cap_and_volume(mesh,fields)
    if max(abs(x-y) for x,y in zip(vtu['flux'][1:],(rows[-1]['endpoint_rcr_flow_2'],rows[-1]['endpoint_rcr_flow_3'])))>1e-14:
        raise ValueError('Saved field and terminal trace differ')
    keep=['step','time','evaluation_time']+[f'{phase}_{role}_{tag}' for phase in ('stage','endpoint')
                                            for role in ('rcr_flow','rcr_pressure','capacitor_pressure') for tag in (2,3)]
    raw=[{k:r[k] for k in keep} for r in rows]
    metrics=compare(reference,raw)
    names=('fluid.msh','solid.msh','startup.json','startup.csv','startup_pressure_faces.csv','startup.vtu','startup_solid.vtu')
    out=dict(grid=a.grid,hz=a.hz,samples=a.samples,steps=a.steps,tau=None if a.default_pspg else a.tau,initial_tau=initial_tau,later_tau=later_tau,unknowns=system['unknowns']+2,
             deformed_cap=vtu,circuit_residual=closure,reference=reference,three_dimensional=raw,relative_error=metrics,
             sha256={f:digest(a.work/f) for f in names},executable_sha256=digest(exe))
    (a.work/'result.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(metrics,flush=True)


if __name__=='__main__':
    main()
