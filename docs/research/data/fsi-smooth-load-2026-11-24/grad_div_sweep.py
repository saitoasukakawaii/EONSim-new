"""Measure fixed grad-div viscosity in EONSim against native matched-load svFSI."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from audit_study import SurfaceAudit, eon_loads, fluid_cell_divergence
from run_study import eon_input, file_sha, INPUT_SHA256


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for key in ("archive","reference-scripts","executable","work","native"):
        cli.add_argument("--"+key,type=Path,required=True)
    cli.add_argument("--steps",type=int,nargs="+",required=True)
    cli.add_argument("--coefficients",type=float,nargs="+",default=[0.,1.,4.,16.])
    args=cli.parse_args()
    sys.path.insert(0,str(args.reference_scripts.resolve()))
    import study_hydrostatic_fsi as fsi
    import study_rigid_tube as tube
    import study_lame_wall as wall
    import compare_svfsi_wall as external

    src=args.archive/"coupled/sv05-s48"
    if any(file_sha(src/name)!=sha for name,sha in INPUT_SHA256.items()):
        raise ValueError("Unexpected original mesh or case")
    meshes=[tube.read_mesh(src/name) for name in ("fluid.msh","solid.msh")]
    nodes=meshes[1][0]
    rings={}
    for n in {n for tag,face in meshes[1][2] if tag==13 for n in face}:
        rings.setdefault(nodes[n][0],[]).append(n)
    sections=sorted(rings)
    audit=SurfaceAudit(meshes[0])
    scale=2*wall.lame(wall.INNER,.02)[0]/wall.INNER
    env=dict(os.environ,OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",
             OMPI_MCA_pml="ob1",OMPI_MCA_btl="self,sm,tcp")
    args.work.mkdir(parents=True)
    result=dict(eon_sha256=file_sha(args.executable),sections=sections,
                equilibrium_area_strain=scale,cases=[])
    exe=args.executable.resolve()
    for n in args.steps:
        if n<2 or n%2: raise ValueError("Need an even number of steps")
        native=args.native/f"matched-{n}"
        for eq in ("FS","MS"):
            external.check_convergence((native/"1-procs/histor.dat").read_text(),n,eq)
        reference={}
        for step in (n//2,n):
            _,solid=external.external_fields(native/f"1-procs/result_{step:03d}.vtu",meshes)
            d={node:s.displacement for node,s in solid.items()}
            reference[step]=[wall.bore_section(nodes,d,rings[x])["linear_area_strain"] for x in sections]
        for coefficient in args.coefficients:
            directory=args.work/f"gamma-{coefficient:g}-n{n}"
            directory.mkdir()
            eon_input(src,directory,n,1./n)
            cfg=json.loads((directory/"case.json").read_text())
            cfg["fsi"].update(grad_div_viscosity=coefficient,output_interval=n//2)
            (directory/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
            with (directory/"solve.log").open("w") as out:
                subprocess.run([exe,"-case","case.json"],cwd=directory,env=env,check=True,
                               stdout=out,stderr=subprocess.STDOUT)
            eon_loads(directory,n)
            samples=[]
            for step in (n//2,n):
                fluid=fsi.recovered_state(directory,f"tube_step{step}",meshes[0],False,1)
                solid=fsi.recovered_state(directory,f"tube_step{step}_solid",meshes[1],True,1)
                displacement={i:s.displacement for i,s in solid.items()}
                eps=np.array([wall.bore_section(nodes,displacement,rings[x])["linear_area_strain"] for x in sections])
                state=audit.array(fluid)
                volumes,divergence=fluid_cell_divergence(audit,state)
                diff=(eps-reference[step])/scale
                j=int(np.argmax(abs(diff)))
                samples.append(dict(time=step/n,area_strain=eps.tolist(),native_area_strain=reference[step],
                                    normalized_max_gap=abs(diff[j]),worst_x=sections[j],
                                    rms_divergence=float(np.sqrt(np.average(divergence**2,weights=volumes))),
                                    grad_div_dissipation=float(coefficient*np.dot(volumes,divergence**2))))
            result["cases"].append(dict(n=n,coefficient=coefficient,samples=samples))
            (args.work/"fixed-grad-div.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
            print(n,coefficient,samples[-1]["normalized_max_gap"],flush=True)


if __name__=="__main__":
    main()
