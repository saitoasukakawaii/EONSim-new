"""Compare the discrete metric prediction and the frozen-grad-div experiment on identical tetrahedra."""
import argparse
import csv
import json
import lzma
import math
from pathlib import Path

from axisymmetric import TubeParameters


MODES={"native":"native", "grad-div-off":"zero", "current-equations":"native",
       "current-equations-grad-div-off":"zero",
       "current-equations-grad-div-time-1over128":"fixed-div-time","current-equations-regular-simplex":"native"}


def read(path):
    raw=path.read_bytes()
    return json.loads(lzma.decompress(raw) if path.suffix==".xz" else raw)


def write_csv(path,rows):
    if not rows: raise ValueError("No comparable observations")
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0],lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def compare(linear, pairs):
    modes={(row["source_steps"],row["mode"]):row for row in linear["runs"]}
    if len(modes)!=len(linear["runs"]): raise ValueError("Duplicate DAE control")
    mesh=[linear["input_sha256"][k] for k in ("fluid.msh","solid.msh")]
    rows=[]
    focused={}
    for pair in pairs:
        data=pair["report"]
        if (pair["sv_variant"]=="current-equations-regular-simplex")!=(linear.get("metric_basis","native")=="regular-simplex"):
            continue
        mode=MODES[pair["sv_variant"]]
        key=(data["steps"],mode)
        if key not in modes or mesh!=data["mesh_sha256"]:continue
        if (any(abs(a-b)>1e-12 for a,b in zip(data["axial_sections"],linear["sections"])) or
                len(data["axial_sections"])!=len(linear["sections"])):
            raise ValueError("Changed axial stations on the same mesh")
        ref=modes[key]
        studies=sorted(ref["time_study"],key=lambda r:r["steps"])
        if len(studies)<2 or ref["manufactured_error"]>1e-8 or ref["static"]["max_residual"]>2e-11:
            raise ValueError("Incomplete independent semidiscrete checks")
        peak=pair["peak_pressure"]
        scale=peak/linear["pressure"]
        equilibrium=TubeParameters().lame_area_strain(peak)
        if not math.isclose(data.get("equilibrium_area_strain",equilibrium),equilibrium,rel_tol=1e-12):
            raise ValueError("Incorrect equilibrium denominator")
        for snapshot,at,fine,previous in zip(data["results"],(.5,1.),studies[-1]["samples"],studies[-2]["samples"]):
            if {snapshot["time"],fine["time"],previous["time"]}!={at}:raise ValueError("Unequal measurement times")
            target=[v*scale for v in fine["section_area_strain"]]
            actual=snapshot["svfsi"]["strains"]
            if len(actual)!=len(target) or not all(map(math.isfinite,actual+target)):
                raise ValueError("Invalid section array")
            difference=[100*(v-w)/equilibrium for v,w in zip(actual,target)]
            worst=max(range(len(difference)),key=lambda i:abs(difference[i]))
            floor=100*scale*max(abs(v-w) for v,w in zip(fine["section_area_strain"],previous["section_area_strain"]))/equilibrium
            rows.append(dict(group=pair["group"],case=pair["case"],sv_variant=pair["sv_variant"],steps=data["steps"],
                             time=at,pressure_pa=peak,reference_mode=mode,reference_steps=studies[-1]["steps"],
                             observed_x0_pct_area=100*actual[0],linear_x0_pct_area=100*target[0],
                             max_abs_discrete_gap_pct_static=abs(difference[worst]),worst_station=data["axial_sections"][worst],
                             radau_temporal_change_pct_static=floor,grad_div_volume_median_pa_s=ref["grad_div_pa_s"]["volume_median"],
                             fraction_volume_temporal_term_larger=ref["fraction_volume_time_term_larger"]))
        if pair["group"] in ("current-time","reference-div") and math.isclose(peak,.02):
            group=focused.setdefault(data["steps"],{})
            if mode in group:raise ValueError("Duplicate paired intervention")
            group[mode]=pair
    controls=[]
    for n,group in sorted(focused.items()):
        if set(group)!={"native","zero","fixed-div-time"}:continue
        for k in ("eon_case_sha256","sv_deck_sha256"):
            if len({g[k] for g in group.values()})!=1:raise ValueError("Unmatched decks in controlled grad-div intervention")
        for at in (0,1):
            records={mode:g["report"]["results"][at] for mode,g in group.items()}
            source=records["native"]["eon"]["strains"]
            if any(r["eon"]["strains"]!=source for r in records.values()):
                raise ValueError("The EONSim control changed during the svFSI intervention")
            ref=modes[n,"native"]
            row=dict(steps=n,time=records["native"]["time"],eon_x0_pct_area=100*source[0],
                     grad_div_median_pa_s=ref["grad_div_pa_s"]["volume_median"],
                     temporal_dominant_volume_pct=100*ref["fraction_volume_time_term_larger"])
            for mode,r in records.items():
                row[mode+"_x0_pct_area"]=100*r["svfsi"]["strains"][0]
                row[mode+"_max_gap_pct_static"]=100*r["max_abs_gap_all_sections"]
            controls.append(row)
    return rows,controls


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--linear",type=Path,required=True)
    cli.add_argument("--pairs",type=Path,required=True)
    cli.add_argument("--csv",type=Path,required=True)
    cli.add_argument("--controls-csv",type=Path,help="Three-way native/zero/frozen intervention on the original mesh")
    args=cli.parse_args()
    rows,controls=compare(read(args.linear),read(args.pairs))
    write_csv(args.csv,rows)
    if args.controls_csv:write_csv(args.controls_csv,controls)
    print(len(rows),"external/DAE observations;",len(controls),"three-way cuts with byte-identical inputs")


if __name__=="__main__":
    main()
