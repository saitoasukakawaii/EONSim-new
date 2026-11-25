"""Independent small-displacement P1/P1 FSI DAE for a conforming quarter tube."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

# Two-stage third-order Radau IIA. Its last collocation value is the endpoint.
A=np.array([[5./12.,-1./12.],[3./4.,1./4.]])
C=np.array([1./3.,1.])


def read_mesh(path):
    """ASCII Gmsh 2.2, using original IDs and first physical tags."""
    lines=path.read_text().splitlines()
    i=lines.index("$Nodes")
    coords={}
    for line in lines[i+2:i+2+int(lines[i+1])]:
        row=line.split()
        if int(row[0]) in coords: raise ValueError("Duplicate mesh node")
        coords[int(row[0])]=tuple(map(float,row[1:4]))
    i=lines.index("$Elements")
    cells=[]
    faces=[]
    for line in lines[i+2:i+2+int(lines[i+1])]:
        v=list(map(int,line.split()))
        kind,ntags=v[1:3]
        if kind==4: cells.append(v[3+ntags:])
        elif kind==2: faces.append((v[3],v[3+ntags:]))
        else: raise ValueError(f"Unexpected mesh element type {kind}")
    ids=sorted(coords)
    local={node:k for k,node in enumerate(ids)}
    return (np.array([coords[n] for n in ids]),np.array([[local[n] for n in e] for e in cells]),
            [(tag,[local[n] for n in face]) for tag,face in faces])


def geometry(mesh):
    xyz,cells,_=mesh
    edge=xyz[cells[:,1:]]-xyz[cells[:,:1]]
    volume=np.linalg.det(edge)/6.
    if np.any(volume<=0): raise ValueError("Nonpositive reference tetrahedron")
    tail=np.linalg.inv(edge).transpose(0,2,1)
    grad=np.concatenate((-tail.sum(axis=1,keepdims=True),tail),axis=1)
    return volume,grad


class Entries:
    def __init__(self,size):
        self.size=size
        self.rows=[]
        self.cols=[]
        self.values=[]

    def add(self,rows,cols,values):
        keep=(rows>=0)&(cols>=0)
        self.rows.append(rows[keep])
        self.cols.append(cols[keep])
        self.values.append(np.broadcast_to(values,rows.shape)[keep])

    def matrix(self):
        m=sparse.coo_matrix((np.concatenate(self.values),(np.concatenate(self.rows),np.concatenate(self.cols))),
                            shape=(self.size,self.size)).tocsc()
        m.eliminate_zeros()
        return m


def pressure_load(mesh,velocity,selected,size):
    """Inward unit pressure integrated on the reference planar faces."""
    xyz,cells,faces=mesh
    owners={tuple(sorted(f)):None for tag,f in faces if tag in selected}
    for cell in cells:
        for j in range(4):
            face=tuple(sorted(np.delete(cell,j)))
            if face in owners:
                if owners[face] is not None: raise ValueError("Pressure evaluated on an interior face")
                owners[face]=cell[j]
    force=np.zeros(size)
    for tag,face in faces:
        if tag not in selected: continue
        other=owners[tuple(sorted(face))]
        if other is None: raise ValueError("Missing face owner")
        a,b,c=xyz[face]
        normal_area=np.cross(b-a,c-a)/2.
        if normal_area@(xyz[other]-a)>0: normal_area=-normal_area
        for node in face:
            valid=velocity[node]>=0
            np.add.at(force,velocity[node,valid],-normal_area[valid]/3.)
    return force


class Tube:
    def __init__(self,directory,tau,grad_div,time_scale=None):
        cfg=json.loads((directory/"case.json").read_text())["fsi"]
        self.meshes=fm,sm=[read_mesh(directory/name) for name in ("fluid.msh","solid.msh")]
        dom=cfg["domains"]
        interfaces=[sorted({node for tag,f in mesh[2] if tag==label for node in f})
                    for mesh,label in zip((fm,sm),(dom["fluid_interface"],dom["solid_interface"]))]
        shared=[]
        keys=[]
        for region,(mesh,idx) in enumerate(zip((fm,sm),interfaces)):
            trace={tuple(np.round(mesh[0][n],12)):n for n in idx}
            if len(trace)!=len(idx): raise ValueError("Nonunique reference interface")
            shared.append(trace)
            names=[(region,n) for n in range(len(mesh[0]))]
            for coord,n in trace.items(): names[n]=(2,coord)
            keys.append(names)
        if shared[0].keys()!=shared[1].keys(): raise ValueError("Nonmatching fluid/solid interfaces")
        blocked=set()
        for mesh,key,bc in zip((fm,sm),keys,(dom["fluid_constraints"],dom["solid_constraints"])):
            for entry in bc:
                for tag,face in mesh[2]:
                    if tag==entry["tag"]:
                        blocked.update((key[n],c) for n in face for c in entry["components"])
        numbering={}
        def velocities(names):
            v=np.full((len(names),3),-1,dtype=int)
            for n,name in enumerate(names):
                for c in range(3):
                    k=(name,c)
                    if k not in blocked:
                        if k not in numbering: numbering[k]=len(numbering)
                        v[n,c]=numbering[k]
            return v
        vf,vs=map(velocities,keys)
        nv=len(numbering)
        self.pressure=pv=np.arange(nv,nv+len(fm[0]))
        fixed=vs<0
        sd=np.full(vs.shape,-1,dtype=int)
        sd[~fixed]=np.arange(pv[-1]+1,pv[-1]+1+np.count_nonzero(~fixed))
        self.displacement=sd
        self.solid_velocity=vs
        self.fluid_velocity=vf
        self.size=int(sd.max()+1)
        M=Entries(self.size)
        K=Entries(self.size)
        if (tau is None)==(time_scale is None):
            raise ValueError("Specify one stabilization control")
        self.grad_div=grad_div
        rho=cfg["density"]
        mu=cfg["viscosity"]
        nu=cfg["poisson"]
        young=cfg["young"]
        shear=young/(2*(1+nu))
        lame=young*nu/((1+nu)*(1-2*nu))
        for region,(mesh,velocity) in enumerate(zip((fm,sm),(vf,vs))):
            vol,gn=geometry(mesh)
            if region==0:
                # Linearization around rest removes the previous-velocity contribution.
                h=np.cbrt(6*vol)
                cell_tau=np.broadcast_to(tau,vol.shape) if time_scale is None else (
                    4*rho**2/time_scale**2+16*mu**2/h**4)**(-.5)
                self.tau_range=[float(cell_tau.min()),float(cell_tau.max())]
            cells=mesh[1]
            v=velocity[cells]
            d=(vf if region==0 else sd)[cells]
            density=rho if region==0 else cfg["solid_density"]
            for a in range(4):
                for b in range(4):
                    dot=(gn[:,a]*gn[:,b]).sum(axis=1)
                    mass=vol*density*(2 if a==b else 1)/20.
                    for i in range(3):
                        M.add(v[:,a,i],v[:,b,i],mass)
                        if region==0:
                            K.add(v[:,a,i],pv[cells[:,b]],-vol*gn[:,a,i]/4.)
                            K.add(pv[cells[:,a]],v[:,b,i],vol*gn[:,b,i]/4.)
                            M.add(pv[cells[:,a]],v[:,b,i],vol*cell_tau*rho*gn[:,a,i]/4.)
                        for j in range(3):
                            sym=gn[:,a,j]*gn[:,b,i]+(dot if i==j else 0.)
                            div=gn[:,a,i]*gn[:,b,j]
                            coeff=mu*sym+grad_div*div if region==0 else shear*sym+lame*div
                            K.add(v[:,a,i],d[:,b,j],vol*coeff)
                    if region==0:
                        K.add(pv[cells[:,a]],pv[cells[:,b]],vol*cell_tau*dot)
        M.add(sd[~fixed],sd[~fixed],1.)
        K.add(sd[~fixed],vs[~fixed],-1.)
        self.mass=M.matrix()
        self.operator=K.matrix()
        self.load=pressure_load(fm,vf,set(dom["pressure_tags"]),self.size)
        self.wall_load=pressure_load(sm,vs,{dom["solid_interface"]},self.size)
        self.bore=interfaces[1]
        self.positions=sorted(set(sm[0][n,0] for n in self.bore))

    def sections(self,y):
        sd=self.displacement
        displacement=np.zeros(sd.shape)
        displacement[sd>=0]=y[sd[sd>=0]]
        xyz=self.meshes[1][0]
        result=[]
        for x in self.positions:
            ring=[n for n in self.bore if xyz[n,0]==x]
            ring.sort(key=lambda n:np.arctan2(xyz[n,2],xyz[n,1]))
            coords=xyz[ring,1:]
            trace=displacement[ring,1:]
            # Derivative of the planar polygon area (quarter symmetry radii close the arc).
            a,b=coords[:-1],coords[1:]
            da,db=trace[:-1],trace[1:]
            cross=lambda u,v:u[:,0]*v[:,1]-u[:,1]*v[:,0]
            result.append(float((cross(da,b)+cross(a,db)).sum()/cross(a,b).sum()))
        return result

    def hydrostatic_check(self):
        v=self.solid_velocity[self.displacement>=0]
        d=self.displacement[self.displacement>=0]
        y=np.zeros(self.size)
        y[self.pressure]=1.
        y[d]=splu(self.operator[v][:,d].tocsc()).solve(self.wall_load[v])
        residual=self.operator@y-self.load
        error=float(np.linalg.norm(residual,np.inf))
        if error>2e-11: raise ValueError(f"Hydrostatic force balance failed: {error}")
        return dict(max_residual=error,area_strain_per_pascal=self.sections(y))


def radau_stage_solver(mass, operator, h, method, displacement_begin=None, factor_stats=None, pivot_threshold=None):
    if pivot_threshold is not None and (method!="condensed-pair" or not 0<=pivot_threshold<=1):
        raise ValueError("A SuperLU pivot threshold in [0,1] requires the condensed complex stage solver")
    if method == "real-block":
        block=sparse.bmat([[mass+h*A[0,0]*operator,h*A[0,1]*operator],
                           [h*A[1,0]*operator,mass+h*A[1,1]*operator]],format="csc")
        factor=splu(block)
        return lambda rhs: factor.solve(rhs.ravel()).reshape(rhs.shape)
    if method not in ("complex-pair","condensed-pair"):
        raise ValueError(f"Unknown Radau stage solver: {method}")
    # A real two-stage Radau matrix has complex conjugate eigenvalues. Its
    # two coupled stage systems can be recovered from one complex LU solve,
    # even when the pressure block of M is singular.
    values,vectors=np.linalg.eig(A)
    j=int(np.argmax(values.imag))
    mode=vectors[:,j]
    basis=np.column_stack([mode,mode.conjugate()])
    weights=np.linalg.inv(basis)[0]
    matrix=(mass+h*values[j]*operator).tocsc()
    if method=="condensed-pair":
        k=displacement_begin
        if k is None or not 0<k<matrix.shape[0]:
            raise ValueError("Displacement condensation requires a nonempty final kinematic block")
        eye=sparse.eye(matrix.shape[0]-k,format="csc")
        if (matrix[k:,k:]-eye).nnz:
            raise ValueError("Expected the exact identity on displacement rate equations")
        upper=matrix[:k,k:].tocsr()
        lower=matrix[k:,:k].tocsr()
        reduced=(matrix[:k,:k]-upper@lower).tocsc()
        reduced.eliminate_zeros()
        factor=splu(reduced,diag_pivot_thresh=pivot_threshold)
        def solve_complex(rhs):
            dynamics=factor.solve(rhs[:k]-upper@rhs[k:])
            return np.concatenate((dynamics,rhs[k:]-lower@dynamics))
    else:
        factor=splu(matrix)
        solve_complex=factor.solve
    if factor_stats is not None:
        factor_stats.update(full_size=matrix.shape[0],factored_size=factor.shape[0],
                            superlu_reported_nnz=factor.nnz)
    def recover(rhs):
        transformed=solve_complex(weights @ rhs)
        return 2*(mode[:,None]*transformed).real
    def solve(rhs):
        stages=recover(rhs)
        # A small backward error in the stiff wall rows can still pollute the
        # algebraic pressure. Refine once in the original real equations.
        defect=rhs-(mass@stages.T).T-h*(A@(operator@stages.T).T)
        return stages+recover(defect)
    return solve


def integrate(tube,steps,amplitude,manufactured=False,observe=None,stage_solver="real-block",factor_stats=None,pivot_threshold=None):
    h=1./steps
    M,K=tube.mass,tube.operator
    displacement_begin=int(tube.pressure.max())+1 if stage_solver=="condensed-pair" else None
    solve=radau_stage_solver(M,K,h,stage_solver,displacement_begin,factor_stats,pivot_threshold)
    y=np.zeros(tube.size)
    if manufactured:
        rng=np.random.default_rng(4241)
        yref=rng.normal(size=tube.size)
        my,ky=M@yref,K@yref
        def forcing(t): return 2*t*my+t*t*ky
    else:
        def forcing(t): return amplitude*t**3*(10.-15.*t+6.*t**2)*tube.load
    rows=[]
    max_residual=0.
    inverse_a=np.linalg.inv(A) if observe is not None else None
    for step in range(steps):
        previous=M@y
        forces=np.stack([forcing((step+c)*h) for c in C])
        rhs=previous+h*(A@forces)
        stages=solve(rhs)
        # Check the original real stage equations irrespective of the factorization.
        residual=(M@stages.T).T+h*(A@(K@stages.T).T)-rhs
        max_residual=max(max_residual,float(np.max(np.abs(residual))))
        if observe is not None:
            rates=inverse_a @ (stages-y) / h
            for c,value,rate in zip(C,stages,rates):
                observe((step+c)*h,value,rate)
        y=stages[-1]
        if (step+1)*2==steps or step+1==steps:
            rows.append(dict(time=(step+1)*h,section_area_strain=tube.sections(y)))
    if max_residual>2e-10: raise ValueError(f"Radau stage residual {max_residual}")
    if manufactured:
        error=float(np.linalg.norm(y-yref,np.inf))
        if error>1e-8: raise ValueError(f"Manufactured quadratic trajectory error {error}")
        return error
    return dict(steps=steps,stage_residual_max=max_residual,samples=rows)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case",type=Path,required=True)
    cli.add_argument("--output",type=Path,required=True)
    controls=cli.add_mutually_exclusive_group(required=True)
    controls.add_argument("--tau",type=float,help="Spatially uniform PSPG coefficient")
    controls.add_argument("--stabilization-time-scale",type=float,help="Fixed temporal scale in seconds in the cellwise PSPG coefficient")
    cli.add_argument("--stage-solver",choices=("real-block","complex-pair"),default="real-block")
    cli.add_argument("--grad-div",type=float,required=True)
    cli.add_argument("--pressure",type=float,default=.02)
    cli.add_argument("--steps",type=int,nargs="+",required=True)
    args=cli.parse_args()
    control=args.tau if args.tau is not None else args.stabilization_time_scale
    if (not np.isfinite([control,args.grad_div,args.pressure]).all() or control<=0 or
            args.grad_div<0 or args.pressure<=0 or any(n<2 or n%2 for n in args.steps)):
        cli.error("Positive PSPG control and pressure, nonnegative grad-div viscosity and even step counts required")
    tube=Tube(args.case,args.tau,args.grad_div,args.stabilization_time_scale)
    result=dict(unknowns=tube.size,mass_nnz=tube.mass.nnz,operator_nnz=tube.operator.nnz,
                fixed_tau=args.tau,stabilization_time_scale=args.stabilization_time_scale,
                pspg_coefficient_range=tube.tau_range,stage_solver=args.stage_solver,
                grad_div_viscosity=args.grad_div,pressure=args.pressure,
                x=tube.positions,static=tube.hydrostatic_check(),
                manufactured_max_error=integrate(tube,4,1.,True,stage_solver=args.stage_solver),runs=[],
                case_sha256={k:hashlib.sha256((args.case/k).read_bytes()).hexdigest()
                             for k in ("case.json","fluid.msh","solid.msh")})
    for n in args.steps:
        result["runs"].append(integrate(tube,n,args.pressure,stage_solver=args.stage_solver))
        args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print(n,result["runs"][-1]["samples"][-1]["section_area_strain"],flush=True)


if __name__=="__main__":
    main()
