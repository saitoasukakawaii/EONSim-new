"""Compare EONSim and svFSI on one generated conforming quarter-tube mesh."""
import argparse
from collections import Counter
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from audit_study import SurfaceAudit, eon_loads, external_loads, fluid_cell_divergence
from run_study import PEAK, eon_input, external_input, file_sha

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_history import check_convergence


def mirror_half_mesh(nodes, cells, faces, length, half):
    """Extend one tetrahedral half across the midplane without adding symmetry constraints."""
    coords = {(round(x, 13), y, z): n for n, (x, y, z) in nodes.items()}
    if len(coords) != len(nodes):
        raise ValueError("Axial coordinates do not uniquely identify nodes on this mesh")
    reflected = {n: coords[round(length-x, 13), y, z] for n,(x,y,z) in nodes.items()}
    if any(reflected[reflected[n]] != n for n in nodes):
        raise ValueError("The two nodal half grids are not mirror images")
    sign = 1 if half == "left" else -1
    def kept(ids):
        return all(sign*(nodes[i][0]-length/2) <= 1e-13 for i in ids)
    selected = [cell for cell in cells if kept(cell)]
    mesh_cells = selected + [(reflected[a],reflected[c],reflected[b],reflected[d]) for a,b,c,d in selected]
    selected_faces = [(t,face) for t,face in faces if kept(face)]
    ends = {1:2,2:1,11:12,12:11}
    mesh_faces = selected_faces + [(ends.get(t,t),(reflected[a],reflected[c],reflected[b]))
                                    for t,(a,b,c) in selected_faces]
    counts = Counter(tuple(sorted(cell[:j]+cell[j+1:])) for cell in mesh_cells for j in range(4))
    boundary = {face for face,count in counts.items() if count == 1}
    if (len(mesh_cells)!=len(cells) or len(mesh_faces)!=len(faces) or max(counts.values())!=2
            or len(boundary)!=len(mesh_faces) or boundary!={tuple(sorted(face)) for _,face in mesh_faces}):
        raise ValueError("Midplane extension changed the topology or exposed an untagged interior facet")
    return mesh_cells, mesh_faces


def reuse_eon(source, destination, executable):
    """Reuse this solver only when its mesh, deck, and recorded binary are identical."""
    for name in ("case.json","fluid.msh","solid.msh"):
        if file_sha(source/name)!=file_sha(destination/name):
            raise ValueError("Cannot reuse EONSim output with changed "+name)
    if (source/"executable.sha256").read_text().strip()!=file_sha(executable):
        raise ValueError("Cannot reuse a different EONSim executable")
    if (source/"solve.log").read_text().splitlines()[-1:]!=["status=success"]:
        raise ValueError("Cannot reuse an incomplete EONSim run")
    for original in source.iterdir():
        target=destination/original.name
        if original.is_file() and not target.exists():
            shutil.copyfile(original,target)


def solve(executable, arguments, directory, libs):
    (directory/"executable.sha256").write_text(file_sha(executable)+"\n")
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
    cli.add_argument("--pressure", type=float, default=PEAK, help="Peak pressure at 1 s (Pa)")
    cli.add_argument("--linear-atol",type=float,help="Absolute tolerance for both svFSI linear solves")
    geometry = cli.add_mutually_exclusive_group()
    geometry.add_argument("--symmetric-half",choices=("left","right"),help="Reflect one half of the mesh across the midplane")
    geometry.add_argument("--reflect", action="store_true", help="Reflect the Tet4 mesh along the tube axis")
    cli.add_argument("--fluid-last-vertex",type=int,choices=range(4),default=3,
                     help="Choose the dependent local Tet4 vertex without changing cells, faces, nodes or wall connectivity")
    cli.add_argument("--krylov",type=int,default=450)
    cli.add_argument("--sv-nonlinear-tolerance",type=float,default=1e-8,help="Internal FS/MS target; the external residual audit remains at 1e-8")
    cli.add_argument("--nonlinear-limit",type=int,default=12,
                     help="Maximum FS/MS iterations. The original acceptance tolerance stays fixed")
    cli.add_argument("--reuse-eon",type=Path,help="Reuse an identical completed EONSim run when changing only svFSI controls")
    setup=cli.add_mutually_exclusive_group()
    setup.add_argument("--audit-only",action="store_true",help="Reconstruct inputs and audit a completed pair without solving again")
    setup.add_argument("--prepare-only",action="store_true",help="Generate the matching meshes and decks for external or linearized controls")
    args=cli.parse_args()
    if not np.isfinite(args.pressure) or not 0 < args.pressure <= PEAK:
        cli.error("The amplitude study requires 0 < pressure <= 0.02 Pa")
    linear_atol=1e-19*(args.pressure/PEAK) if args.linear_atol is None else args.linear_atol
    if not 0 < linear_atol <= 1e-15:
        cli.error("The linear absolute tolerance must be positive and at least as tight as the archived 1e-15")
    if not 0 < args.sv_nonlinear_tolerance <= 1e-8:
        cli.error("FS/MS tolerance must be finite, positive, and no larger than 1e-8")
    if args.nonlinear_limit<12: cli.error("Need at least the archived nonlinear iteration limit of 12")
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
                mesh=source/(domain+".msh")
                wall.quarter_mesh(Path(temp)/(domain+".msh"),mesh,tags,region)
                if args.symmetric_half:
                    nodes,cells,faces=tube.read_mesh(mesh)
                    cells,faces=mirror_half_mesh(nodes,cells,faces,wall.LENGTH,args.symmetric_half)
                    tube.write_mesh(mesh,nodes,cells,faces,region)
                if args.reflect:
                    nodes,cells,faces=tube.read_mesh(mesh)
                    nodes={n:(wall.LENGTH-x,y,z) for n,(x,y,z) in nodes.items()}
                    # Keep the reference vertex and exchange two axes to restore positive orientation.
                    cells=[(a,c,b,d) for a,b,c,d in cells]
                    end_tags={1:2,2:1,11:12,12:11}
                    faces=[(end_tags.get(tag,tag),(a,c,b)) for tag,(a,b,c) in faces]
                    tube.write_mesh(mesh,nodes,cells,faces,region)
                if domain=="fluid" and args.fluid_last_vertex!=3:
                    nodes,cells,faces=tube.read_mesh(mesh)
                    anchor=args.fluid_last_vertex
                    order=[j for j in range(4) if j!=anchor]+[anchor]
                    if (3-anchor)%2:
                        order[0],order[1]=order[1],order[0]
                    cells=[tuple(tet[j] for j in order) for tet in cells]
                    tube.write_mesh(mesh,nodes,cells,faces,region)
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
        cfg["fsi"]["pressure"]=args.pressure
        cfg["solver"]["absolute_tolerance"]*=args.pressure/PEAK
        (eon/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
        external_input(root/"sv-input",sv,n,1./n,"matched",linear_atol,args.pressure)
        deck=(sv/"svFSI.inp").read_text()
        cap="   Max iterations: 12\n"
        if deck.count(cap)!=2: raise ValueError("Expected independent FS and MS nonlinear limits")
        deck=deck.replace(cap,f"   Max iterations: {args.nonlinear_limit}\n")
        if args.sv_nonlinear_tolerance != 1e-8:
            target="   Tolerance: 1e-8\n"
            if deck.count(target)!=2: raise ValueError("Expected FS and MS nonlinear targets")
            deck=deck.replace(target,f"   Tolerance: {args.sv_nonlinear_tolerance:g}\n")
        old="Increment in saving VTK files: 1\n"
        if deck.count(old)!=1:
            raise ValueError("Unexpected svFSI output frequency")
        (sv/"svFSI.inp").write_text(deck.replace(old,f"Increment in saving VTK files: {n//2}\n"))

    eon=args.work/"eon"
    sv=args.work/"matched"
    if args.prepare_only:
        prepare(args.work)
        return
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
        if args.reuse_eon:
            reuse_eon(args.reuse_eon,eon,args.eon)
        else:
            solve(args.eon,["-case","case.json"],eon,args.eon_libs)
        solve(args.svfsi,["svFSI.inp"],sv,args.svfsi_libs)
    source=args.work/"reference"
    mesh_files=[source/f"{domain}.msh" for domain in ("fluid","solid")]
    meshes=[tube.read_mesh(path) for path in mesh_files]
    cell_counts=[len(m[1]) for m in meshes]
    if cell_counts!=[3*(sectors//4)*(2*radial-1)*axial,6*(sectors//4)*layers*axial]:
        raise ValueError("Mesh generator cell-count mismatch")

    loads=[eon_loads(eon,n,args.pressure),external_loads(sv,n,"matched",args.pressure)]
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
    exact=2*wall.lame(wall.INNER,args.pressure)[0]/wall.INNER
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
            cell_volume,divergence=fluid_cell_divergence(audit,state)
            div_rms=float(np.sqrt(np.average(divergence**2,weights=cell_volume)))
            record[mode]=dict(strains=strains,volume_gain=audit.volume(state)-volume,
                              fluid_divergence_rms=div_rms)
        diff=(np.array(record["eon"]["strains"])-record["svfsi"]["strains"])/exact
        ids=[sections.index(x) for x in (0.,wall.LENGTH/2,wall.LENGTH)]
        record["signed_gap_common_sections"]=diff[ids].tolist()
        record["max_abs_gap_common_sections"]=float(np.max(np.abs(diff[ids])))
        record["max_abs_gap_all_sections"]=float(np.max(np.abs(diff)))
        records.append(record)
    hashes={}
    receipts={}
    for name,directory,executable in (("eon",eon,args.eon),("svfsi",sv,args.svfsi)):
        hashes[name]=file_sha(executable)
        receipt=directory/"executable.sha256"
        receipts[name]=receipt.exists()
        if receipt.exists() and receipt.read_text().strip()!=hashes[name]:
            raise ValueError(f"Supplied executable differs from the run receipt for {name}")
    result=dict(mesh=args.mesh,cells=cell_counts,steps=n,axial_sections=sections,krylov=args.krylov,nonlinear_limit=args.nonlinear_limit,
                peak_pressure=args.pressure,reflected=args.reflect,equilibrium_area_strain=exact,linear_atol=linear_atol,
                mesh_sha256=[file_sha(p) for p in mesh_files],source_executables=hashes,run_hash_receipts=receipts,
                matched_pressure_max_abs=mismatch,sv_convergence=convergence,results=records)
    if args.sv_nonlinear_tolerance != 1e-8:
        result["sv_nonlinear_tolerance"]=args.sv_nonlinear_tolerance
    if args.fluid_last_vertex!=3:
        result["fluid_last_vertex"]=args.fluid_last_vertex
    if args.symmetric_half:
        result["symmetric_half"]=args.symmetric_half
    (args.work/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(f"{args.mesh} {n} steps: max common section gap at 1 s = {records[-1]['max_abs_gap_common_sections']:.7f}")


if __name__=="__main__":
    main()
