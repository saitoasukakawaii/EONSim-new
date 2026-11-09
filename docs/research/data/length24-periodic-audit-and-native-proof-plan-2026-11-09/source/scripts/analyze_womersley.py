"""Audit accepted Womersley checkpoint phases (NumPy, SciPy and h5py required).

P1 field norms use the exact consistent tetrahedral mass matrix. The analytic
velocity cross term uses positive tensor Gauss/Duffy quadrature, avoiding a
comparison only at nodes. Pressure remains in the traction-fixed gauge.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import h5py
import numpy as np
import scipy
from scipy.special import jv

import study_rigid_tube as tube
from womersley_reference import velocity_amplitude, flow_amplitude


def tetra_rule(order):
    x,w=np.polynomial.legendre.leggauss(order)
    x=(x+1)/2;w=w/2
    shapes=[];weights=[]
    for i,u in enumerate(x):
        for j,v in enumerate(x):
            for k,s in enumerate(x):
                shapes.append(((1-u)*(1-v)*(1-s),u,(1-u)*v,(1-u)*(1-v)*s))
                weights.append(6*w[i]*w[j]*w[k]*(1-u)**2*(1-v))
    weights=np.asarray(weights)
    if abs(weights.sum()-1)>1e-13:
        raise ValueError('Invalid tetrahedral quadrature')
    return np.asarray(shapes),weights


class Mesh:
    def __init__(self,path):
        nodes,cells,faces=tube.read_mesh(path)
        self.ids=np.array(sorted(nodes),dtype=np.int64)
        self.xyz=np.array([nodes[n] for n in self.ids])
        index={n:i for i,n in enumerate(self.ids)}
        self.cells=np.array([[index[n] for n in c] for c in cells])
        self.points=self.xyz[self.cells]
        matrix=np.transpose(self.points[:,1:]-self.points[:,:1],(0,2,1))
        self.volumes=np.linalg.det(matrix)/6
        if not np.all(np.isfinite(self.volumes)) or np.min(self.volumes)<=0:
            raise ValueError('Nonpositive tetrahedral mesh')
        self.volume=float(self.volumes.sum())
        self.flow_weights=np.zeros((len(nodes),3))
        self.net_weights=np.zeros_like(self.flow_weights)
        self.pressure_drop_weights=np.zeros(len(nodes))
        ends={1:[],2:[]}
        for tag,face in faces:
            ix=np.array([index[n] for n in face])
            a,b,c=self.xyz[ix]
            av=np.cross(b-a,c-a)/2
            center=(a+b+c)/3
            outward=np.array((-1,0,0) if tag==1 else (1,0,0) if tag==2 else (0,center[1],center[2]))
            if av@outward<0:
                av=-av
            self.net_weights[ix]+=av/3
            if tag in ends:
                self.flow_weights[ix]+=(1 if tag==2 else -1)*av/6
                ends[tag].append((ix,np.linalg.norm(av)))
        for tag,entries in ends.items():
            area=sum(a for _,a in entries)
            for ix,a in entries:
                self.pressure_drop_weights[ix]+=(1 if tag==1 else -1)*a/(3*area)

    def squared(self,values):
        if values.ndim==1:
            values=values[:,None]
        local=values[self.cells]
        return float(np.sum(self.volumes*(np.sum(local.sum(axis=1)**2,axis=1)+np.sum(local**2,axis=(1,2)))/20))

    def reference(self,definition,order):
        shape,weight=tetra_rule(order)
        load=np.zeros(len(self.ids),dtype=complex)
        squared=0.
        for begin in range(0,len(self.cells),4096):
            end=min(begin+4096,len(self.cells))
            positions=np.einsum('qa,cad->cqd',shape,self.points[begin:end])
            radius=np.linalg.norm(positions[:,:,1:],axis=2)
            amplitude=velocity_amplitude(radius,definition['alpha'],definition['radius'],definition['viscosity'],
                                         definition['pressure_amplitude']/definition['length'],bessel=jv)
            local=np.einsum('cq,q,qa->ca',amplitude,weight,shape)*self.volumes[begin:end,None]
            np.add.at(load,self.cells[begin:end].ravel(),local.ravel())
            squared+=np.sum(self.volumes[begin:end]*np.sum(abs(amplitude)**2*weight,axis=1))
        return load,float(squared)


class Study:
    def __init__(self,work):
        self.work=Path(work)
        self.definition=json.loads((self.work/'definition.json').read_text())
        self.receipt=json.loads((self.work/'receipt.json').read_text())
        d=self.definition
        if self.receipt['definition']!=d:
            raise ValueError('Receipt/definition mismatch')
        if hashlib.sha256((self.work/'fluid.msh').read_bytes()).hexdigest()!=(self.work/'mesh-sha256.txt').read_text().strip():
            raise ValueError('Mesh digest mismatch')
        self.mesh=Mesh(self.work/'fluid.msh')
        s=d['seed'][0]
        expected=s*d['radius']**2*math.sin(2*math.pi/s)*d['length']/2
        if abs(self.mesh.volume-expected)>1e-10*expected:
            raise ValueError('Polygon volume changed')
        # Snapshot point order is exactly the local mesh order used by checkpoint
        # fields. Verify IDs/coordinates/ownership before reading any state.
        self.mapping=[]
        owners=np.zeros(len(self.mesh.ids),dtype=int)
        output=self.work/self.receipt['output']
        for rank in range(d['ranks']):
            path=output if d['ranks']==1 else output.with_name(output.stem+f'_rank{rank}.vtu')
            tree=ET.parse(path)
            arrays={v.attrib['Name']:v.text.split() for v in tree.findall('.//PointData/DataArray')}
            ids=np.array(arrays['mesh_node_id'],dtype=np.int64)
            ix=np.searchsorted(self.mesh.ids,ids)
            if np.any(ix>=len(self.mesh.ids)) or not np.array_equal(self.mesh.ids[ix],ids):
                raise ValueError('Unknown checkpoint mesh node')
            xyz=np.array(tree.find('.//Points/DataArray').text.split(),dtype=float).reshape(-1,3)
            if not np.allclose(xyz,self.mesh.xyz[ix],rtol=0,atol=1e-14):
                raise ValueError('Snapshot coordinates differ from mesh')
            owned=np.array(arrays['owner'],dtype=int)==rank
            np.add.at(owners,ix[owned],1)
            self.mapping.append((ix,owned))
        if not np.all(owners==1):
            raise ValueError('Incomplete/duplicate owned nodes')
        self.generations={}
        for path in (self.work/'checkpoint').glob('generation_*/manifest'):
            m=path.read_text().split()
            sizes={'EONSim_checkpoint_v3':5,'EONSim_checkpoint_v4':6}
            if not m or len(m)!=sizes.get(m[0]) or int(m[1])!=d['ranks']:
                raise ValueError('Invalid manifest')
            step=int(m[2]);time=float(m[3]);clock=tuple(map(float,m[3:]));version=int(m[0][-1])
            if step in self.generations or not all(map(math.isfinite,clock)) or clock[1]<=0 or abs(time-step*d['period']/d['steps_per_cycle'])>1e-10*max(1.,time):
                raise ValueError('Duplicate state or inconsistent accepted time')
            self.generations[step]=(path.parent,version,clock)
        if self.receipt['step'] not in self.generations:
            raise ValueError('Receipt has no complete generation')
        cfg=json.loads((self.work/self.receipt['attempt']/'case.json').read_text())
        expected_cfg=tube.case_config()
        expected_cfg['fluid'].update(mode='transient',dt=d['period']/d['steps_per_cycle'],
            steps=cfg['fluid']['steps'],checkpoint_interval=cfg['fluid']['checkpoint_interval'])
        expected_cfg['fluid']['boundaries'][1].update(value=0.,pressure_time=dict(amplitude=d['pressure_amplitude'],period=d['period']))
        if d['tau'] is not None:
            expected_cfg['fluid']['stabilization_tau']=d['tau']
        if d.get('tau_time_scale') is not None:
            expected_cfg['fluid']['stabilization_time_scale']=d['tau_time_scale']
        expected_cfg.update(mesh='../fluid.msh',output='solution.vtu',time=dict(scheme='bdf2'))
        if cfg!=expected_cfg:
            raise ValueError('Actual case differs from declared reference problem')
        self.signatures={}

    def state(self,step):
        path,version,expected_clock=self.generations[step]
        state=np.empty((len(self.mesh.ids),4))
        ghosts=[]
        for rank,(ix,owned) in enumerate(self.mapping):
            with h5py.File(path/f'state_rank{rank}.h5','r') as file:
                meta=file['metadata'][()]
                clock=file['clock'][()]
                value=file['fluid'][()].reshape(-1,4)
            if len(meta)!=9 or tuple(meta[:3])!=(version,rank,self.definition['ranks']) or int(meta[8])!=step or int(meta[3])!=int(owned.sum()):
                raise ValueError('Checkpoint metadata mismatch')
            signature=int(meta[7])
            if self.signatures.setdefault(rank,signature)!=signature:
                raise ValueError('Physics signature changed within study')
            if clock.shape!=(len(expected_clock),) or not np.array_equal(clock,expected_clock):
                raise ValueError('Checkpoint clock mismatch')
            if value.shape!=(len(ix),4) or not np.all(np.isfinite(value)):
                raise ValueError('Invalid checkpoint field')
            state[ix[owned]]=value[owned]
            ghosts.append((ix[~owned],value[~owned]))
        for ix,values in ghosts:
            if len(ix) and np.max(abs(state[ix]-values))>=2e-9:
                raise ValueError('Ghost mismatch')
        return state

    def cycle(self,number):
        d=self.definition;n=d['steps_per_cycle'];m=d['phases']
        if number<=d['warmup']:
            raise ValueError('Requested cycle was not phase sampled')
        return np.stack([self.state((number-1)*n+j*n//m) for j in range(1,m+1)])


def metrics(study,states,order):
    mesh=study.mesh;d=study.definition;m=len(states)
    theta=2*np.pi*np.arange(1,m+1)/m
    sine=np.einsum('m,mnc->nc',2*np.sin(theta)/m,states)
    cosine=np.einsum('m,mnc->nc',2*np.cos(theta)/m,states)
    load,reference_sq=mesh.reference(d,order)
    reference_avg=reference_sq/2
    field_avg=sum(mesh.squared(v[:,:3]) for v in states)/m
    cross_avg=float((sine[:,0]@load.real+cosine[:,0]@load.imag)/2)
    error=field_avg-2*cross_avg+reference_avg
    if error < -1e-12*reference_avg or not math.isfinite(error):
        raise ValueError('Invalid velocity error integral')
    pressure_error=0.
    for phase,state in zip(theta,states):
        exact=d['pressure_amplitude']*(1-mesh.xyz[:,0]/d['length'])*math.sin(phase)
        pressure_error+=mesh.squared(state[:,3]-exact)/m
    q=np.einsum('mnc,nc->m',states[:,:,:3],mesh.flow_weights)
    net=np.einsum('mnc,nc->m',states[:,:,:3],mesh.net_weights)
    qhat=complex(q@(2*np.sin(theta)/m),q@(2*np.cos(theta)/m))
    exact_q=flow_amplitude(d['alpha'],d['radius'],d['viscosity'],d['pressure_amplitude']/d['length'],bessel=jv)
    result=dict(velocity_relative_l2_error=math.sqrt(max(0.,error)/reference_avg),
        pressure_rms_over_amplitude=math.sqrt(pressure_error/mesh.volume)/d['pressure_amplitude'],
        flow_amplitude_relative_error=float(abs(abs(qhat)/abs(exact_q)-1)),
        flow_phase_error_degrees=abs(math.degrees(np.angle(qhat/exact_q))),
        flow_mean=float(q.mean()),maximum_net_flux=float(np.max(abs(net))),
        velocity_reference_rms=math.sqrt(reference_avg/mesh.volume),
        pressure_reference_rms=d['pressure_amplitude']/math.sqrt(6),
        flow_amplitude=[qhat.real,qhat.imag],reference_flow_amplitude=[exact_q.real,exact_q.imag])
    return result


def cycle_difference(mesh,a,b,scales):
    if a.shape!=b.shape:
        raise ValueError('Phase sets differ')
    return {name:max(math.sqrt(mesh.squared(x[:,sl]-y[:,sl])/mesh.volume)/scale for x,y in zip(a,b))
            for name,sl,scale in (('velocity',slice(0,3),scales['velocity_reference_rms']),
                                  ('pressure',slice(3,4),scales['pressure_reference_rms']))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--quadrature',type=int,default=4)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 3<=args.quadrature<=8:
        parser.error('Quadrature order must be 3..8')
    study=Study(args.work);d=study.definition
    if study.receipt['step']%d['steps_per_cycle']:
        raise ValueError('Latest receipt is not a complete cycle')
    last=study.receipt['step']//d['steps_per_cycle']
    states=study.cycle(last)
    result=metrics(study,states,args.quadrature)
    previous=study.cycle(last-1)
    periodic=cycle_difference(study.mesh,states,previous,result)
    preceding=cycle_difference(study.mesh,previous,study.cycle(last-2),result)
    report=dict(definition=d,last_cycle=last,quadrature_order=args.quadrature,
        versions=dict(numpy=np.__version__,scipy=scipy.__version__,h5py=h5py.__version__),
        nodes=len(study.mesh.ids),tetrahedra=len(study.mesh.cells),metrics=result,
        last_periodic_difference=periodic,preceding_periodic_difference=preceding,
        preliminary_gates=dict(velocity=result['velocity_relative_l2_error']<.01,
            pressure=result['pressure_rms_over_amplitude']<.01,
            flow_amplitude=result['flow_amplitude_relative_error']<.01,
            flow_phase=result['flow_phase_error_degrees']<1,
            global_mass=result['maximum_net_flux']<1e-10,
            periodic=max(*periodic.values(),*preceding.values())<1e-6),
        scope='Analytic and periodic diagnostics; spatial/time/tail/sampling budgets still required')
    output=args.output or args.work/'analysis.json'
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,allow_nan=False))


if __name__=='__main__':
    main()
