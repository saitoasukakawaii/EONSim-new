"""Independent complex Stokes admittance and downstream-reservoir response of a rigid 3D T-junction."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator,gmres,splu

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'cases/fsi')]
from generate_branched import generate
from study_rigid_tube import read_mesh

EDGES=tuple(itertools.combinations(range(4),2))
PORTS=(2,3)


def quadrature():
    """Normalized positive tensor Gauss quadrature on a Duffy-mapped tetrahedron."""
    x,w=np.polynomial.legendre.leggauss(4)
    x=(x+1)/2
    w=w/2
    points=[]
    weights=[]
    for i,j,k in itertools.product(range(4),repeat=3):
        a,b,c=x[i],(1-x[i])*x[j],(1-x[i])*(1-x[j])*x[k]
        points.append([1-a-b-c,a,b,c])
        weights.append(6*w[i]*w[j]*w[k]*(1-x[i])**2*(1-x[j]))
    return np.array(points),np.array(weights)


def element(edges,order,tau,density,viscosity,bary,w):
    grad=np.vstack((-np.ones((1,3)),np.eye(3)))@np.linalg.inv(edges).T
    volume=abs(np.linalg.det(edges))/6
    if volume==0:raise ValueError('Singular tetrahedron')
    if order==1:
        values=bary
        g=np.broadcast_to(grad,(len(w),4,3))
    else:
        values=np.column_stack([*(bary[:,i]*(2*bary[:,i]-1) for i in range(4)),
                                *(4*bary[:,i]*bary[:,j] for i,j in EDGES)])
        linear=[(4*bary[:,i,None]-1)*grad[i] for i in range(4)]
        quadratic=[4*(bary[:,i,None]*grad[j]+bary[:,j,None]*grad[i]) for i,j in EDGES]
        g=np.stack(linear+quadratic,axis=1)
    if max(np.max(abs(values.sum(axis=1)-1)),np.max(abs(g.sum(axis=1))))>1e-11:
        raise ValueError('Velocity basis failed partition-of-unity check')
    nv=3*values.shape[1]
    m=np.zeros((nv+4,nv+4))
    k=np.zeros_like(m)
    moment=values.T@(w[:,None]*values)
    m[:nv,:nv]=np.kron(moment,np.eye(3))*density
    gg=np.einsum('q,qai,qbj->abij',w,g,g,optimize=True)
    visc=np.einsum('abii,kl->akbl',gg,np.eye(3))+gg.transpose(0,3,1,2)
    k[:nv,:nv]=viscosity*visc.reshape(nv,nv)
    div=np.einsum('q,qp,qai->pai',w,bary,g,optimize=True).reshape(4,nv)
    k[:nv,nv:]=-div.T
    k[nv:,:nv]=div
    if order==1:
        k[nv:,nv:]=tau*grad@grad.T
        m[nv:,:nv]=tau*density*np.einsum('pi,a->pai',grad,w@values).reshape(4,nv)
    return volume*m,volume*k


def assemble(mesh,order,tau=.01):
    nodes,tets,faces=mesh
    ids={key:i for i,key in enumerate(nodes)}
    xyz=np.array(list(nodes.values()))
    cells=np.array([[ids[n] for n in c] for c in tets])
    vertex_nodes=len(xyz)
    velocity_cells=cells
    edge_numbers={}
    if order==2:
        pairs=np.sort(cells[:,EDGES],axis=2)
        all_edges,indices=np.unique(pairs.reshape(-1,2),axis=0,return_inverse=True)
        velocity_cells=np.column_stack((cells,vertex_nodes+indices.reshape(len(cells),6)))
        edge_numbers={tuple(pair):vertex_nodes+i for i,pair in enumerate(all_edges.tolist())}
    nv=vertex_nodes+len(edge_numbers)
    local=np.column_stack(((3*velocity_cells[:,:,None]+np.arange(3)).reshape(len(cells),-1),3*nv+cells))
    size=3*nv+vertex_nodes
    volume=float(np.abs(np.linalg.det(xyz[cells[:,1:]]-xyz[cells[:,:1]])).sum()/6)
    rows=[]
    cols=[]
    masses=[]
    operators=[]
    bary,w=quadrature()
    # The Cartesian box decomposition has few distinct affine element maps.
    # Group identical physical maps without rounding arbitrary coordinates.
    maps,types=np.unique((xyz[cells[:,1:]]-xyz[cells[:,:1]]).reshape(-1,9),axis=0,return_inverse=True)
    for i,flat in enumerate(maps):
        m,k=element(flat.reshape(3,3),order,tau,1.,1.,bary,w)
        ii,jj=np.nonzero((m!=0)|(k!=0))
        dofs=local[types==i]
        rows.append(dofs[:,ii].ravel())
        cols.append(dofs[:,jj].ravel())
        masses.append(np.tile(m[ii,jj],len(dofs)))
        operators.append(np.tile(k[ii,jj],len(dofs)))
    indices=np.concatenate(rows),np.concatenate(cols)
    def matrix(values):
        a=sparse.coo_matrix((np.concatenate(values),indices),shape=(size,size)).tocsc()
        a.eliminate_zeros()
        return a
    mass,op=matrix(masses),matrix(operators)
    fixed=set()
    b=np.zeros((size,2))
    areas=np.zeros(2)
    for tag,face in faces:
        v=[ids[n] for n in face]
        edges=[edge_numbers[tuple(sorted((i,j)))] for i,j in itertools.combinations(v,2)] if order==2 else []
        if tag in (1,4):
            fixed.update(v+edges)
            continue
        if tag not in PORTS:raise ValueError('Unexpected exterior tag')
        vector=np.cross(xyz[v[1]]-xyz[v[0]],xyz[v[2]]-xyz[v[0]])/2
        area=abs(vector[1])
        if area==0 or abs(area-np.linalg.norm(vector))>1e-13*area:raise ValueError('Unexpected terminal orientation')
        j=PORTS.index(tag)
        areas[j]+=area
        # A P2 triangle integrates its vertex basis to zero and each edge basis to area/3.
        face_nodes=edges if order==2 else v
        b[3*np.asarray(face_nodes)+1,j]+=(1 if tag==2 else -1)*area/3
    if not np.allclose(areas,.25,rtol=1e-11,atol=0):raise ValueError('Incomplete daughter areas')
    free=np.ones(size,dtype=bool)
    free[(3*np.array(sorted(fixed))[:,None]+np.arange(3)).ravel()]=False
    indices=np.flatnonzero(free)
    return dict(mass=mass[free][:,free],operator=op[free][:,free],trace=b[free],velocity=indices<3*nv,
                tets=len(tets),unknowns=len(indices),volume=volume,ports_area=areas.tolist())


def zpair(z):
    return [float(z.real),float(z.imag)]


def generalized_alpha_symbol(hz,samples):
    """Endpoint-equivalent derivative and applied downstream stage forcing at rho_infinity=0.5."""
    if not samples or hz==0:
        return 2j*np.pi*hz,1.+0j
    alpha_f,alpha_m=2/3,5/6
    gamma=.5+alpha_m-alpha_f
    dt=1/(hz*samples)
    theta=2*np.pi/samples
    previous=np.exp(-1j*theta)
    stage=alpha_f+(1-alpha_f)*previous
    endpoint_rate=(1-previous)/(dt*(gamma+(1-gamma)*previous))
    derivative=endpoint_rate*(alpha_m+(1-alpha_m)*previous)/stage
    forcing=np.exp(-1j*(1-alpha_f)*theta)/stage
    return derivative,forcing


def response(system,hz,order,samples=0,linear_solver='direct'):
    omega,forcing=generalized_alpha_symbol(hz,samples)
    mass,k,b=system['mass'],system['operator'],system['trace']
    a=(k+omega*mass).tocsc()
    iterations=[]
    if linear_solver=='direct':
        factor=splu(a)
        states=factor.solve(-b.astype(complex))
        states+=factor.solve(-b-a@states)
    else:
        if 'steady_factor' not in system:
            system['steady_factor']=splu(k)
        factor=system['steady_factor']
        def inverse(v):
            return factor.solve(v.real)+1j*factor.solve(v.imag)
        pre=LinearOperator(a.shape,matvec=inverse,dtype=np.complex128)
        states=np.empty(b.shape,dtype=complex)
        for j in range(b.shape[1]):
            trace=[]
            states[:,j],info=gmres(a,-b[:,j].astype(complex),M=pre,rtol=2e-13,atol=1e-17,
                                    restart=30,maxiter=20,callback=trace.append,callback_type='pr_norm')
            if info:raise ValueError('Steady-preconditioned Krylov solve failed')
            iterations.append(len(trace))
    y=b.T@states
    # The common-pressure mode must recover a unit physical pressure with zero velocity.
    vel=system['velocity']
    common=states[:,0]+states[:,1]
    common_error=max(np.max(abs(common[vel])),np.max(abs(common[~vel]-1)))
    if common_error>5e-10:raise ValueError(f'Constant pressure null-flow check {common_error}')
    jump=np.array([.5,-.5])
    q=y@jump
    lumen=-1/q[0]
    if lumen.real<=0 or abs(sum(q))>1e-8*abs(q[0]):raise ValueError('Nonpassive or unbalanced differential lumen')
    # At the two terminals, the distal pressures have opposite signs and different time constants.
    rp=np.array([3.,12.])
    rd=np.array([8.,32.])
    compliance=np.array([.025,.0125])
    h=1/(1+omega*rd*compliance)
    z=rp+rd*h
    prescribed=np.array([.02,-.02])
    pb=np.linalg.solve(np.eye(2)-np.diag(z)@y,h*forcing*prescribed)
    state=states@pb
    qc=b.T@state
    pc=pb-rp*qc
    predicted=-forcing*(h[0]*prescribed[0]-h[1]*prescribed[1])/(lumen+z.sum())
    flow_scale=max(abs(qc))
    mass_error=abs(sum(qc))/flow_scale
    port_error=max(abs(pc-rd*h*qc-h*forcing*prescribed))/max(abs(pb))
    formula_error=abs(qc[0]-predicted)/flow_scale
    weak_error=np.max(abs(a@state+b@pb))
    vv=state.copy()
    vv[~vel]=0.
    d=np.vdot(vv,k@vv).real
    inertia=np.vdot(vv,mass@vv).real
    applied=np.vdot(qc,pb)
    scale=max(abs(applied),1e-35)
    physical_work=d+omega*inertia+applied
    pressure=state-vv
    stabilization=np.vdot(pressure,k@pressure).real
    acceleration=np.conj(omega*np.vdot(pressure,mass@vv))
    # Conjugate the pressure-tested continuity equation when removing
    # pressure work from the conjugate-velocity-tested momentum equation.
    power_error=abs(physical_work)/scale
    stabilized_error=abs(physical_work+stabilization+acceleration)/scale
    if stabilized_error>3e-8 or stabilization < -1e-14*scale:
        raise ValueError('Stabilized complex power balance failed')
    if min(d,inertia)<0 or max(mass_error,port_error,formula_error)>3e-8 or weak_error>3e-10:
        raise ValueError('Unbalanced closed outlet solution')
    if order==2 and power_error>3e-8:raise ValueError('Taylor–Hood physical power balance failed')
    return dict(hz=hz,steps_per_cycle=samples,solver=linear_solver,iterations=iterations,derivative_symbol=zpair(omega),stage_forcing_over_endpoint=zpair(forcing),
                admittance=[[zpair(v) for v in row] for row in y],differential_lumen_impedance=zpair(lumen),
                outlet_flows=[zpair(v) for v in qc],port_pressures=[zpair(v) for v in pb],capacitor_pressures=[zpair(v) for v in pc],
                prescribed_reservoir_pressures=prescribed.tolist(),resistances_capacitance=list(zip(rp.tolist(),rd.tolist(),compliance.tolist())),
                common_flow_pressure_error=float(common_error),mass_defect=float(mass_error),terminal_defect=float(port_error),
                scalar_network_defect=float(formula_error),weak_defect=float(weak_error),physical_power_defect=float(power_error),
                stabilized_power_defect=float(stabilized_error),pressure_gradient_work_over_port_power=float(stabilization/scale),
                acceleration_pspg_work_over_port_power=zpair(acceleration/scale))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mesh',type=Path,required=True,help='Existing generated junction directory or a new output location')
    p.add_argument('--refinement',type=int,required=True)
    p.add_argument('--order',type=int,choices=(1,2),required=True)
    p.add_argument('--linear-solver',choices=['direct','steady-lu'],default='direct')
    p.add_argument('--steps-per-cycle',type=int,nargs='+',default=[0],help='0 for continuous time; otherwise the generalized-alpha symbol')
    p.add_argument('--tau',type=float,default=.01,help='Fixed PSPG time in the P1/P1 problem')
    p.add_argument('--hz',type=float,nargs='+',default=(0.,.25,1.,2.))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if any(n!=0 and n<8 for n in a.steps_per_cycle):p.error('Use zero or at least eight time steps per cycle')
    if a.refinement<1 or not math.isfinite(a.tau) or a.tau<=0 or any(not math.isfinite(h) or h<0 for h in a.hz):p.error('Invalid grid or frequency')
    if not (a.mesh/'geometry.json').is_file():generate(a.mesh,a.refinement)
    geo=json.loads((a.mesh/'geometry.json').read_text())
    if geo['refinement']!=a.refinement:raise ValueError('Existing mesh resolution differs')
    path=a.mesh/'fluid.msh'
    system=assemble(read_mesh(path),a.order,a.tau)
    if not math.isclose(system['volume'],geo['reference_fluid_volume'],rel_tol=1e-11):raise ValueError('Mismatch in lumen volume')
    out=dict(refinement=a.refinement,order=a.order,fixed_pspg=a.tau if a.order==1 else None,
             fluid_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),tets=system['tets'],unknowns=system['unknowns'],
             volume=system['volume'],outlet_areas=system['ports_area'],runs=[])
    for hz,samples in itertools.product(a.hz,a.steps_per_cycle):
        q=response(system,hz,a.order,samples,a.linear_solver)
        out['runs'].append(q)
        print(hz,q['differential_lumen_impedance'],q['mass_defect'],flush=True)
    a.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
