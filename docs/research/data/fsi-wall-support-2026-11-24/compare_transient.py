"""Compare the same seven wall sections in transient 3D and mixed axisymmetric solves."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"fsi-linear-transient-2026-11-24"))
from axisymmetric import TubeParameters


SUPPORTS = [(0,0), (0,5), (50,0), (50,5), (50,30)]
AXIAL = [(36,36,12), (48,48,16), (64,64,16)]


def entry(path):
    data = path.read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(), report=json.loads(data))


def collect(root):
    result = {"meridian": {}, "tetrahedron": {}}
    for k,c in SUPPORTS:
        for x,r,w in AXIAL:
            name = f"axisym-x{x}-f{r}-w{w}-g4-fullno-k{k}-c{c}.json"
            result["meridian"][f"{x}/{k}/{c}"] = entry(root/name)
    for s,shape in [(48,"s48-r4-w4-a6"),(96,"s96-r8-w8-a12")]:
        directory=root/("wall-transient-"+shape)
        result["tetrahedron"][str(s)] = item = entry(directory/"results.json")
        item["decks"]={}
        for k,c in SUPPORTS:
            work=directory/f"k{k}-c{c}"
            item["decks"][f"{k}/{c}"]=entry(work/"case.json")
            for mesh,digest in item["report"]["mesh_sha256"].items():
                if hashlib.sha256((work/mesh).read_bytes()).hexdigest()!=digest:
                    raise ValueError("Changed 3D support mesh")
    return result


def compare(records):
    rows = []
    for sectors,raw in records["tetrahedron"].items():
        tetra = raw["report"]
        regimes = {(r["stiffness"],r["damping"]):r for r in tetra["regimes"]}
        if set(regimes)!=set(SUPPORTS) or tetra["steps"]!=128 or tetra["dt"]!=1/128:
            raise ValueError("Missing support regimes or changed 3D time controls")
        for k,c in SUPPORTS:
            regime = regimes[k,c]
            deck=raw["decks"][f"{k}/{c}"]["report"]
            fsi=deck["fsi"]
            if (fsi["material"]!="linear" or fsi["domains"]["wall_supports"]!=[dict(tag=14,stiffness=k,damping=c)] or
                    fsi["pressure_time"]!=dict(amplitude=0,period=1,ramp_time=1) or
                    fsi["domains"]["pressure_tags"]!=[1,2] or fsi["dt"]!=tetra["dt"] or fsi["steps"]!=tetra["steps"] or
                    fsi["pressure"]!=tetra["peak_pressure"] or deck["time"]!=dict(scheme="generalized_alpha",rho_infinity=.5)):
                raise ValueError("Mismatched pressure ramp, support, time scheme or mesh tags")
            refs = [records["meridian"][f"{x}/{k}/{c}"]["report"] for x,_,_ in AXIAL]
            for mesh,ref in zip(AXIAL,refs):
                material = TubeParameters(**ref["parameters"])
                if (ref["mesh"]!=list(mesh) or ref["pressure"]!=tetra["peak_pressure"] or
                        (material.support_stiffness,material.support_damping)!=(k,c) or
                        ref["corner_levels"]!=4 or ref["full_length"] or
                        ref["static"]["relative_lame_area_error"]>1e-6):
                    raise ValueError("The meridian and 3D support or material differ")
                for label, attr in (("density","fluid_density"),("viscosity","viscosity"),("solid_density","solid_density"),
                                    ("young","young"),("poisson","poisson")):
                    if fsi[label]!=getattr(material,attr):
                        raise ValueError("Different material in the meridian and 3D tube")
                equilibrium = material.lame_area_strain(ref["pressure"])
                if not math.isclose(equilibrium,regime["equilibrium_area_strain"],rel_tol=1e-12):
                    raise ValueError("Independent supported static compliances disagree")
                if [r["steps"] for r in ref["runs"]]!=[64,128,256]:
                    raise ValueError("Incomplete time refinement")
                for r in ref["runs"]:
                    if (r["max_power_residual_over_peak"]>1e-7 or r["max_flux_residual_over_peak"]>1e-7 or
                            [s["time"] for s in r["samples"]]!=[.5,1.]):
                        raise ValueError("Invalid independent power, mass or sampling history")
            stations = refs[-1]["sections"]
            if (len(stations)!=7 or any(max(abs(a-b) for a,b in zip(stations,ref["sections"]))>1e-12 for ref in refs) or
                    [s["time"] for s in regime["samples"]]!=[.5,1.]):
                raise ValueError("Mismatched sampling histories")
            indices = []
            for x in stations:
                locations = [i for i,y in enumerate(tetra["x"]) if abs(x-y)<1e-11]
                if len(locations)!=1: raise ValueError("Missing common physical cross section")
                indices.append(locations[0])
            for sample_id,sample in enumerate(regime["samples"]):
                values = [sample["strain"][i] for i in indices]
                def sections(ref, level):
                    return ref["runs"][level]["samples"][sample_id]["section_area_strain"]
                exact = sections(refs[-1],-1)
                def norm(values):
                    return max(abs(x-y) for x,y in zip(values,exact))/equilibrium
                if not all(map(math.isfinite,values+exact)) or any(len(sections(ref,-1))!=7 for ref in refs):
                    raise ValueError("Nonfinite or incomplete section observations")
                worst=max(range(len(exact)),key=lambda i:abs(values[i]-exact[i]))
                row=dict(sectors=int(sectors),spring_pa_per_m=k,dashpot_pa_s_per_m=c,time=sample["time"],
                         equilibrium_strain=equilibrium,meridian_unknowns=refs[-1]["unknowns"],
                         max_3d_meridian_difference_pct_static=100*norm(values),
                         meridian_48_to_64_pct_static=100*norm(sections(refs[-2],-1)),
                         meridian_128_to_256_steps_pct_static=100*norm(sections(refs[-1],-2)),
                         eon_left_strain_pct_area=100*values[0],ref_left_strain_pct_area=100*exact[0],
                         eon_mid_strain_pct_area=100*values[3],ref_mid_strain_pct_area=100*exact[3],
                         eon_right_strain_pct_area=100*values[-1],ref_right_strain_pct_area=100*exact[-1],
                         worst_common_x=stations[worst],eon_worst_strain_pct_area=100*values[worst],
                         ref_worst_strain_pct_area=100*exact[worst],endpoint_support_spring_energy_j=sample["spring_energy"],
                         stage_support_dissipation_w=sample["stage_dissipation"],stage_support_power_w=sample["stage_power"],
                         full_run_support_work_j=regime["total_support_work"],full_run_dissipation_j=regime["total_damping_work"],
                         max_support_energy_balance_error_j=regime["max_energy_error_joules"])
                rows.append(row)
    return rows


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    inp=cli.add_mutually_exclusive_group(required=True)
    inp.add_argument("--runs",type=Path)
    inp.add_argument("--archive",type=Path)
    cli.add_argument("--write-archive",type=Path)
    cli.add_argument("--csv",type=Path,required=True)
    args=cli.parse_args()
    records=collect(args.runs) if args.runs else json.loads(lzma.decompress(args.archive.read_bytes()))
    rows=compare(records)
    if args.write_archive:
        args.write_archive.write_bytes(lzma.compress(json.dumps(records,separators=(",",":"),allow_nan=False).encode()))
    with args.csv.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=rows[0],lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(len(rows),"matched combinations of support, mesh and sample time")


if __name__=="__main__":
    main()
