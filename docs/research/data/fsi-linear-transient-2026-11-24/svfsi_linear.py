"""Linearize the pinned svFSI Tet4 metric stabilization on the actual quarter-tube connectivity."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile

import numpy as np

from reference import Tube, geometry, integrate, read_mesh
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_mesh import write_piece


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coefficients(mesh, density, viscosity, steps, mode, fixed_div_steps, metric_basis="native"):
    volume,gradients = geometry(mesh)
    # NN.f uses the last Tet4 vertex as the dependent barycentric coordinate.
    # CHECKIEN may exchange the first two vertices; their dyad sum is unchanged.
    independent=gradients[:,:3,:]
    metric=np.einsum("eai,eaj->eij",independent,independent)
    if metric_basis=="regular-simplex":
        # I + 11^T on a unit reference Tet4 has determinant four.
        # This factor preserves the determinant of the original metric.
        symmetric=4**(-1/3)*np.einsum("eai,eaj->eij",gradients,gradients)
        if not np.allclose(np.linalg.det(metric),np.linalg.det(symmetric),rtol=2e-12,atol=0):
            raise ValueError("The regular-simplex normalization changed metric volume")
        metric=symmetric
    trace=np.trace(metric,axis1=1,axis2=2)
    spatial=36*(viscosity/density)**2*np.einsum("eij,eij->e",metric,metric)
    temporal=4.*steps**2  # the physical ramp spans exactly one second
    tau_m=1/(density*np.sqrt(temporal+spatial))
    if mode=="native":
        tau_c=1/(tau_m*trace)
    elif mode=="fixed-div-time":
        tau_c=density*np.sqrt(4.*fixed_div_steps**2+spatial)/trace
    else:
        tau_c=np.zeros_like(volume)
    return volume,tau_m,tau_c,temporal/(temporal+spatial)


def stats(values,volume):
    sort=np.argsort(values)
    cum=np.cumsum(volume[sort])
    median=values[sort[np.searchsorted(cum,.5*cum[-1])]]
    return dict(min=float(values.min()),volume_median=float(median),volume_mean=float(np.average(values,weights=volume)),max=float(values.max()))


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case",type=Path,required=True)
    cli.add_argument("--native-mesh",type=Path,required=True,help="The exact lumen.vtu supplied to the external 3D solver")
    cli.add_argument("--source-steps",nargs="+",type=int,required=True,help="Counts over one second for the stabilized spatial operator")
    cli.add_argument("--integration-steps",nargs="+",type=int,default=(128,256))
    cli.add_argument("--fixed-div-steps",type=int,default=128)
    cli.add_argument("--modes",nargs="+",choices=("native","zero","fixed-div-time"),default=("native","zero","fixed-div-time"))
    cli.add_argument("--metric-basis",choices=("native","regular-simplex"),default="native")
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args()
    if (min(args.source_steps)<=0 or args.fixed_div_steps<=0 or any(v<2 or v%2 for v in args.integration_steps) or
            len(set(args.source_steps))!=len(args.source_steps) or len(set(args.modes))!=len(args.modes) or
            len(set(args.integration_steps))!=len(args.integration_steps)):
        cli.error("Require distinct positive source steps and even integration counts")
    fluid=read_mesh(args.case/"fluid.msh")
    coords,cells,_=fluid
    with tempfile.TemporaryDirectory() as temp:
        vtk=Path(temp)/"lumen.vtu"
        write_piece(vtk,coords,range(1,len(coords)+1),cells,range(1,len(cells)+1))
        if digest(vtk)!=digest(args.native_mesh):
            raise ValueError("The source Gmsh connectivity does not reproduce the external VTK mesh byte for byte")
    cfg=json.loads((args.case/"case.json").read_text())["fsi"]
    out=dict(input_sha256={k:digest(args.case/k) for k in ("case.json","fluid.msh","solid.msh")},
             lumen_vtu_sha256=digest(args.native_mesh),fixed_div_steps=args.fixed_div_steps,
             pressure=cfg["pressure"],integration="complex-pair Radau IIA with real-residual correction",runs=[])
    if args.metric_basis!="native":out["metric_basis"]=args.metric_basis
    for n in args.source_steps:
        for mode in args.modes:
            vol,tm,tc,ratio=coefficients(fluid,cfg["density"],cfg["viscosity"],n,mode,args.fixed_div_steps,args.metric_basis)
            tube=Tube(args.case,tm,tc)
            out["sections"]=tube.positions
            record=dict(source_steps=n,mode=mode,pspg=stats(tm,vol),grad_div_pa_s=stats(tc,vol),
                        temporal_fraction=stats(ratio,vol),fraction_volume_time_term_larger=float(vol[ratio>.5].sum()/vol.sum()),
                        unknowns=tube.size,static=tube.hydrostatic_check(),
                        manufactured_error=integrate(tube,4,1.,True,stage_solver="complex-pair"),time_study=[])
            for stages in args.integration_steps:
                rec=integrate(tube,stages,out["pressure"],stage_solver="complex-pair")
                if not math.isfinite(rec["stage_residual_max"]) or rec["stage_residual_max"]>1e-9:
                    raise ValueError("Linearized stage equation failed")
                record["time_study"].append(rec)
            out["runs"].append(record)
            print(n,mode,tc.min(),tc.max(),record["time_study"][-1]["samples"][-1]["section_area_strain"][0],flush=True)
    temporary=args.output.with_suffix(".partial")
    temporary.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    temporary.replace(args.output)


if __name__=="__main__":
    main()
