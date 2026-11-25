"""Compare physical axial stations against a separately refined axisymmetric transient."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def current(path):
    doc = json.loads(path.read_text())
    if doc["parameters"].get("support_stiffness",0) or doc["parameters"].get("support_damping",0):
        raise ValueError("The two-code pressure-ramp study uses a traction-free outer wall")
    runs = sorted(doc["runs"],key=lambda r:r["steps"])
    if len(runs)<2 or 2*runs[-2]["steps"]!=runs[-1]["steps"]:
        raise ValueError("Need an independently time-refined model")
    if any(max(r["max_power_residual_over_peak"],r["max_flux_residual_over_peak"])>1e-7 for r in runs):
        raise ValueError("Axisymmetric power/flux check failed")
    return doc,runs


def strains(run):
    if [s["time"] for s in run["samples"]]!=[.5,1.]:
        raise ValueError("The reference must share both physical observation times")
    return np.array([s["section_area_strain"] for s in run["samples"]])


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ("reference","previous-mesh","output"):
        cli.add_argument("--"+name,type=Path,required=True)
    cli.add_argument("--native",type=Path,nargs="+",required=True)
    cli.add_argument("--ablated",type=Path,nargs="*",default=[])
    args=cli.parse_args()
    source,runs=current(args.reference)
    previous,older=current(args.previous_mesh)
    if (source["parameters"]!=previous["parameters"] or source["sections"]!=previous["sections"]
            or source["pressure"]!=previous["pressure"] or runs[-1]["steps"]!=older[-1]["steps"]):
        raise ValueError("Reference controls or observation points differ")
    p=source["parameters"]
    a,b=p["radius"],p["outer_radius"]
    compliance=2*(1+p["poisson"])*((1-2*p["poisson"])*a*a+b*b)/(p["young"]*(b*b-a*a))
    scale=source["pressure"]*compliance
    baseline=strains(runs[-1])
    time_change=float(np.max(np.abs(baseline-strains(runs[-2])))/scale)
    space_change=float(np.max(np.abs(baseline-strains(older[-1])))/scale)
    if not np.all(np.isfinite([time_change,space_change])) or max(time_change,space_change)>.001:
        raise ValueError("The two finest axisymmetric results differ by more than 0.1% of equilibrium strain")
    result=dict(reference_sha256=hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                previous_mesh_sha256=hashlib.sha256(args.previous_mesh.read_bytes()).hexdigest(),
                axisymmetric_pressure=source["pressure"],equilibrium_area_compliance_per_pascal=compliance,
                time_refinement_delta_over_equilibrium=time_change,space_refinement_delta_over_equilibrium=space_change,
                reference_steps=runs[-1]["steps"],observations=[])
    for mode,files in (("native",args.native),("no_grad_div",args.ablated)):
        for path in files:
            case=json.loads(path.read_text())
            if case.get("reflected",False):
                raise ValueError("Use the original orientation for cross-mesh comparisons")
            pressure=case.get("peak_pressure",.02)
            if abs(case.get("equilibrium_area_strain",pressure*compliance)-pressure*compliance)>1e-12*pressure:
                raise ValueError("The reported equilibrium scale is incompatible with the reference")
            pairs=[]
            for j,x in enumerate(source["sections"]):
                matching=np.flatnonzero(np.abs(np.array(case["axial_sections"])-x)<1e-12)
                if len(matching)>1:
                    raise ValueError("Duplicate axial station")
                if len(matching)==1:
                    pairs.append((j,matching[0]))
            selected=[source["sections"][j] for j,_ in pairs]
            if not all(x in selected for x in (0,p["length"]/2,p["length"])):
                raise ValueError("Need at least both ends and the midplane in common")
            if len(case["results"])!=len(runs[-1]["samples"]):
                raise ValueError("Missing paired observation")
            for step,record in enumerate(case["results"]):
                if record["time"]!=runs[-1]["samples"][step]["time"]:
                    raise ValueError("Mismatched sample time")
                ref=baseline[step,[j for j,_ in pairs]]*pressure/source["pressure"]
                row=dict(mesh=case["mesh"],steps=case["steps"],peak_pressure=pressure,
                         time=record["time"],svfsi_stabilization=mode,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         x=selected,reference=ref.tolist())
                for solver in ("eon","svfsi"):
                    actual=np.array(record[solver]["strains"])[[i for _,i in pairs]]
                    delta=(actual-ref)/(pressure*compliance)
                    if not np.all(np.isfinite(delta)): raise ValueError("Nonfinite solver/reference difference")
                    row[solver]=dict(area_strains=actual.tolist(),normalized_signed_errors=delta.tolist(),
                                     max_abs_error=float(np.max(np.abs(delta))),rms_error=float(np.sqrt(np.mean(delta**2))))
                result["observations"].append(row)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    main()
