"""Check the nonlinear EONSim solution against the independent small-pressure DAE."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for key in ("reference","case","reference-scripts","work","executable"):
        cli.add_argument("--"+key,type=Path,required=True)
    cli.add_argument("--steps",type=int,nargs="+",required=True)
    cli.add_argument("--pressures",type=float,nargs="+",required=True)
    a=cli.parse_args()
    sys.path.insert(0,str(a.reference_scripts.resolve()))
    import study_hydrostatic_fsi as fsi
    import study_rigid_tube as tube
    import study_lame_wall as wall
    ref=json.loads(a.reference.read_text())
    by_n={r["steps"]:r for r in ref["runs"]}
    if len(by_n)<2: raise ValueError("Need an independently time-refined reference")
    finest=by_n[max(by_n)]
    next_finest=by_n[sorted(by_n)[-2]]
    scale=ref["pressure"]
    exact=2*wall.lame(wall.INNER,scale)[0]/wall.INNER
    floor=max(abs(np.array(a1["section_area_strain"])-b["section_area_strain"]).max()/exact
              for a1,b in zip(finest["samples"],next_finest["samples"]))
    if not np.isfinite(floor) or floor>=1e-4:
        raise ValueError("Radau reference has insufficient temporal refinement")
    for name,sha in ref["case_sha256"].items():
        if hashlib.sha256((a.case/name).read_bytes()).hexdigest()!=sha:
            raise ValueError("Solvers must use the same baseline case and mesh")
    sm=tube.read_mesh(a.case/"solid.msh")
    nodes=sm[0]
    rings={}
    for n in {n for tag,face in sm[2] if tag==13 for n in face}:
        rings.setdefault(nodes[n][0],[]).append(n)
    if sorted(rings)!=ref["x"]: raise ValueError("Different reference sections")
    a.work.mkdir(parents=True)
    exe=a.executable.resolve()
    env=dict(os.environ,OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",
             OMPI_MCA_pml="ob1",OMPI_MCA_btl="self,sm,tcp")
    result=dict(executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),reference_steps=finest["steps"],
                reference_step_doubling_delta=floor,fixed_tau=ref["fixed_tau"],
                stabilization_time_scale=ref.get("stabilization_time_scale"),grad_div_viscosity=ref["grad_div_viscosity"],cases=[])
    scale_time=ref.get("stabilization_time_scale")
    if (ref["fixed_tau"] is None)==(scale_time is None):
        raise ValueError("The reference must specify a unique stabilization control")
    for n in a.steps:
        if n<2 or n%2: raise ValueError("An even step count is needed")
        for pressure in a.pressures:
            if pressure<=0: raise ValueError("Pressure must be positive")
            directory=a.work/f"n{n}-p{pressure:g}"
            directory.mkdir()
            for name in ("fluid.msh","solid.msh"):
                shutil.copyfile(a.case/name,directory/name)
            cfg=json.loads((a.case/"case.json").read_text())
            cfg["fsi"].update(dt=1./n,steps=n,output_interval=n//2,pressure=pressure,
                              pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.),
                              grad_div_viscosity=ref["grad_div_viscosity"])
            if scale_time is None:
                cfg["fsi"]["stabilization_tau"]=ref["fixed_tau"]
                cfg["fsi"].pop("stabilization_time_scale",None)
            else:
                cfg["fsi"]["stabilization_time_scale"]=scale_time
                cfg["fsi"].pop("stabilization_tau",None)
            cfg["solver"]["absolute_tolerance"]*=pressure/scale
            (directory/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
            with (directory/"solve.log").open("w") as out:
                subprocess.run([exe,"-case","case.json"],cwd=directory,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
            if (directory/"solve.log").read_text().splitlines()[-1:]!=["status=success"]:
                raise ValueError("Incomplete EONSim solve")
            with (directory/"tube.csv").open() as stream:
                accepted=list(csv.DictReader(stream))
            if (len(accepted)!=n or any(int(row["step"])!=i or abs(float(row["time"])-i/n)>2e-14
                    for i,row in enumerate(accepted,1))):
                raise ValueError("Incomplete or mistimed accepted history")
            samples=[]
            for baseline in finest["samples"]:
                step=round(baseline["time"]*n)
                solid=fsi.recovered_state(directory,f"tube_step{step}_solid",sm,True,1)
                d={node:state.displacement for node,state in solid.items()}
                strains=np.array([wall.bore_section(nodes,d,rings[x])["linear_area_strain"] for x in ref["x"]])
                delta=(strains*scale/pressure-baseline["section_area_strain"])/exact
                if not np.all(np.isfinite(delta)): raise ValueError("Nonfinite relative errors")
                idx=int(np.argmax(abs(delta)))
                samples.append(dict(time=step/n,sections=strains.tolist(),normalized_differences=delta.tolist(),
                                    max_abs_gap=abs(delta[idx]),worst_x=ref["x"][idx]))
            result["cases"].append(dict(steps=n,pressure=pressure,absolute_tolerance=cfg["solver"]["absolute_tolerance"],samples=samples))
            (a.work/"comparison.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
            print(n,pressure,samples[-1]["max_abs_gap"],flush=True)


if __name__=="__main__":
    main()
