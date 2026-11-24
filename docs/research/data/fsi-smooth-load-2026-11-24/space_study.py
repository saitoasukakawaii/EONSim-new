"""Compare EONSim and svFSI on one generated conforming quarter-tube mesh."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from audit_study import SurfaceAudit, eon_loads, external_loads
from run_study import PEAK, eon_input, external_input, file_sha

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_history import check_convergence


def solve(executable, arguments, directory, libs):
    env = dict(os.environ, LD_LIBRARY_PATH=str(libs.resolve()), OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", OMPI_MCA_pml="ob1", OMPI_MCA_btl="self,sm,tcp")
    with (directory/"solve.log").open("w") as out:
        subprocess.run([executable.resolve(),*arguments], cwd=directory, env=env,
                       stdout=out,stderr=subprocess.STDOUT,check=True)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--work", type=Path, required=True)
    cli.add_argument("--reference-scripts", type=Path, required=True)
    cli.add_argument("--eon",type=Path,required=True)
    cli.add_argument("--svfsi",type=Path,required=True)
    cli.add_argument("--eon-libs",type=Path,required=True)
    cli.add_argument("--svfsi-libs",type=Path,required=True)
    cli.add_argument("--mesh",type=int,nargs=4,metavar=("SECTORS","FLUID_RADIAL","WALL_LAYERS","AXIAL"),required=True)
    cli.add_argument("--steps",type=int,required=True)
    cli.add_argument("--krylov",type=int,default=450)
    cli.add_argument("--audit-only",action="store_true",help="Reconstruct inputs and audit a completed pair without solving again")
    args=cli.parse_args()
    sys.path.insert(0,str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as external
    import study_hydrostatic_fsi as fsi
    import study_lame_wall as wall
    import study_rigid_tube as tube

    sectors,radial,layers,axial=args.mesh
    n=args.steps
    if n<2 or n%2 or sectors<8 or sectors%4 or min(radial,layers)<1 or axial<2 or axial%2:
        cli.error("Need even steps and axial count, positive layers, and full-circle sectors divisible by four")
    def prepare(root):
        source=root/"reference"
        source.mkdir(parents=True)
        with tempfile.TemporaryDirectory(dir=source) as temp:
            tube.generate(temp,sectors=sectors,radial=radial,axial=axial,radius=wall.INNER,
                          thickness=wall.OUTER-wall.INNER,length=wall.LENGTH,wall_layers=layers)
            for domain,tags,region in (("solid",(15,16),20),("fluid",(5,6),10)):
                wall.quarter_mesh(Path(temp)/(domain+".msh"),source/(domain+".msh"),tags,region)
        base=fsi.case_config(.25,12.,PEAK,.5)
        (source/"case.json").write_text(json.dumps(base,indent=2)+"\n")
        external.prepare(source,root/"sv-input",args.krylov)
        eon=root/"eon"
        sv=root/"matched"
        eon.mkdir()
        sv.mkdir()
        eon_input(source,eon,n,1./n)
        cfg=json.loads((eon/"case.json").read_text())
        cfg["fsi"]["output_interval"]=n//2
        (eon/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
        external_input(root/"sv-input",sv,n,1./n,"matched",1e-19)
        deck=(sv/"svFSI.inp").read_text()
        old="Increment in saving VTK files: 1\n"
        if deck.count(old)!=1:
            raise ValueError("Unexpected svFSI output frequency")
        (sv/"svFSI.inp").write_text(deck.replace(old,f"Increment in saving VTK files: {n//2}\n"))

    eon=args.work/"eon"
    sv=args.work/"matched"
    if args.audit_only:
        with tempfile.TemporaryDirectory() as temp:
            expected=Path(temp)
            prepare(expected)
            for case in ("eon","matched"):
                for check in (expected/case).iterdir():
                    if file_sha(check)!=file_sha(args.work/case/check.name):
                        raise ValueError(f"Changed spatial study input: {case}/{check.name}")
    else:
        prepare(args.work)
        solve(args.eon,["-case","case.json"],eon,args.eon_libs)
        solve(args.svfsi,["svFSI.inp"],sv,args.svfsi_libs)
    source=args.work/"reference"
    mesh_files=[source/f"{domain}.msh" for domain in ("fluid","solid")]
    meshes=[tube.read_mesh(path) for path in mesh_files]
    cell_counts=[len(m[1]) for m in meshes]
    if cell_counts!=[3*(sectors//4)*(2*radial-1)*axial,6*(sectors//4)*layers*axial]:
        raise ValueError("Mesh generator cell-count mismatch")

    loads=[eon_loads(eon,n),external_loads(sv,n,"matched")]
    if loads[0].keys()!=loads[1].keys():
        raise ValueError("Incomplete matched port sets")
    mismatch=max(abs(loads[0][k]["min_pressure"]-loads[1][k]["min_pressure"]) for k in loads[0])
    if mismatch>3e-15:
        raise ValueError("Unmatched assembled pressures")
    log=(sv/"1-procs/histor.dat").read_text()
    convergence={eq:check_convergence(log,n,eq) for eq in ("FS","MS")}

    audit=SurfaceAudit(meshes[0])
    volume=audit.volume(np.zeros((len(audit.ids),7)))
    nodes,_,faces=meshes[1]
    ring_nodes={node for tag,face in faces if tag==13 for node in face}
    sections=sorted({nodes[node][0] for node in ring_nodes})
    if not {0.,wall.LENGTH/2,wall.LENGTH}.issubset(sections):
        raise ValueError("Missing paired axial sections")
    rings=[[node for node in ring_nodes if nodes[node][0]==x] for x in sections]
    exact=2*wall.lame(wall.INNER,PEAK)[0]/wall.INNER
    records=[]
    for step in (n//2,n):
        eon_fields=[fsi.recovered_state(eon,f"tube_step{step}"+suffix,mesh,i==1,1)
                    for i,(mesh,suffix) in enumerate(zip(meshes,("","_solid")))]
        sv_fields=external.external_fields(sv/f"1-procs/result_{step:03d}.vtu",meshes)
        record=dict(time=step/n)
        for mode,(fluid,solid) in zip(("eon","svfsi"),(eon_fields,sv_fields)):
            state=audit.array(fluid)
            d={k:s.displacement for k,s in solid.items()}
            strains=[wall.bore_section(nodes,d,ring)["linear_area_strain"] for ring in rings]
            record[mode]=dict(strains=strains,volume_gain=audit.volume(state)-volume)
        diff=(np.array(record["eon"]["strains"])-record["svfsi"]["strains"])/exact
        ids=[sections.index(x) for x in (0.,wall.LENGTH/2,wall.LENGTH)]
        record["signed_gap_common_sections"]=diff[ids].tolist()
        record["max_abs_gap_common_sections"]=float(np.max(np.abs(diff[ids])))
        record["max_abs_gap_all_sections"]=float(np.max(np.abs(diff)))
        records.append(record)
    result=dict(mesh=args.mesh,cells=cell_counts,steps=n,axial_sections=sections,krylov=args.krylov,
                mesh_sha256=[file_sha(p) for p in mesh_files],source_executables=dict(eon=file_sha(args.eon),svfsi=file_sha(args.svfsi)),
                matched_pressure_max_abs=mismatch,sv_convergence=convergence,results=records)
    (args.work/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(f"{args.mesh} {n} steps: max common section gap at 1 s = {records[-1]['max_abs_gap_common_sections']:.7f}")


if __name__=="__main__":
    main()
