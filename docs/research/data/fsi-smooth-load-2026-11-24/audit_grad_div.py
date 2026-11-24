"""Isolate the grad-div term using independently converged paired svFSI runs."""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

from audit_study import SurfaceAudit, eon_loads, external_loads, write_csv
from run_study import file_sha

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_history import check_convergence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ("reference-scripts","archive","eon","native","ablated","output"):
        parser.add_argument("--"+option,type=Path,required=True)
    parser.add_argument("--steps",type=int,nargs="+",required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as sv
    import study_hydrostatic_fsi as fsi
    import study_lame_wall as wall
    import study_rigid_tube as tube

    source=args.archive/"coupled/sv05-s48"
    meshes=[tube.read_mesh(source/path) for path in ("fluid.msh","solid.msh")]
    surface=SurfaceAudit(meshes[0])
    volume=surface.volume(np.zeros((len(surface.ids),7)))
    nodes=meshes[1][0]
    rings={}
    for node in {i for tag,f in meshes[1][2] if tag==13 for i in f}:
        rings.setdefault(nodes[node][0],[]).append(node)
    sections=sorted(rings)
    exact=2*wall.lame(wall.INNER,.02)[0]/wall.INNER
    data=[]
    rows=[]
    for n in args.steps:
        good=args.native/f"matched-{n}"
        trial=args.ablated/f"matched-{n}"
        eon=args.eon/f"eon-{n}"
        # The 48-sector tube has identical material, time stepping and deck
        # (including linear tolerances). A fresh process reads the two binaries.
        for path in ["svFSI.inp",*(p.name for g in ("*.vtu","*.vtp","*.dat") for p in good.glob(g))]:
            if file_sha(good/path)!=file_sha(trial/path):
                raise ValueError(f"Changed paired input {path}")
        if (good/"executable.sha256").read_bytes()==(trial/"executable.sha256").read_bytes():
            raise ValueError("Ablation requires two different binaries")
        loads=[eon_loads(eon,n)]
        norms={}
        for mode,folder in (("native",good),("no_grad_div",trial)):
            h=(folder/"1-procs/histor.dat").read_text()
            norms[mode]={e:check_convergence(h,n,e) for e in ("FS","MS")}
            loads.append(external_loads(folder,n,"matched"))
        max_load=max(abs(ports[key]["min_pressure"]-loads[0][key]["min_pressure"])
                     for key in loads[0] for ports in loads[1:])
        if max_load>3e-15:
            raise ValueError("Mismatched applied pressures")
        result=dict(steps=n,dt=1./n,svfsi_acceptance=norms,max_pressure_delta=max_load,samples=[])
        for step in (n//2,n):
            states={"eon":[fsi.recovered_state(eon,f"tube_step{step}"+suffix,mesh,solid,1)
                           for mesh,suffix,solid in zip(meshes,("","_solid"),(False,True))]}
            for mode,folder in (("native",good),("no_grad_div",trial)):
                states[mode]=sv.external_fields(folder/f"1-procs/result_{step:03d}.vtu",meshes)
            strains={}
            sample=dict(time=step/n)
            for mode,(fluid,solid) in states.items():
                disp={node:state.displacement for node,state in solid.items()}
                strain=np.array([wall.bore_section(nodes,disp,rings[x])["linear_area_strain"] for x in sections])
                if not np.all(np.isfinite(strain)):
                    raise ValueError("Invalid sectional displacement")
                strains[mode]=strain
                state=surface.array(fluid)
                points=(surface.reference+state[:,:3])[surface.tets]
                gradu=np.linalg.solve(points[:,1:]-points[:,:1],state[surface.tets[:,1:],3:6]-state[surface.tets[:,:1],3:6])
                vols=np.linalg.det(points[:,1:]-points[:,:1])/6
                div_rms=float(np.sqrt(np.average(np.trace(gradu,axis1=1,axis2=2)**2,weights=vols)))
                sample[mode]=dict(volume_gain=surface.volume(state)-volume,
                                  fluid_divergence_rms=div_rms,section_area_strain=strain.tolist())
            for mode in ("native","no_grad_div"):
                delta=(strains["eon"]-strains[mode])/exact
                j=int(np.argmax(abs(delta)))
                row=dict(steps=n,time=step/n,svfsi=mode,max_abs_gap=abs(delta[j]),worst_section=sections[j],
                         signed_gap_x0=delta[0],signed_gap_mid=delta[len(sections)//2],
                         svfsi_divergence_rms=sample[mode]["fluid_divergence_rms"])
                rows.append(row)
            result["samples"].append(sample)
        result["binary_sha256"]={key:(folder/"executable.sha256").read_text().strip()
                                for key,folder in (("eon",eon),("native",good),("no_grad_div",trial))}
        data.append(result)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"grad-div.json").write_text(json.dumps(dict(sections=sections,cases=data),indent=2,allow_nan=False)+"\n")
    write_csv(args.output/"grad-div.csv",rows)


if __name__=="__main__":
    main()
