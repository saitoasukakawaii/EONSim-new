"""Check accepted steps, the two assembled port loads, and the two solvers' saved fields."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

from run_study import PEAK, PORTS, INPUT_SHA256, eon_stage, file_sha, smooth_pressure

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"fsi-pressure-faces-2026-11-24"))
from audit import SurfaceAudit


def fluid_cell_divergence(surface, state):
    points = (surface.reference + state[:, :3])[surface.tets]
    edges = points[:, 1:] - points[:, :1]
    volumes = np.linalg.det(edges) / 6
    if not np.all(volumes > 0):
        raise ValueError("Invalid deformed fluid cell")
    velocity = state[surface.tets, 3:6]
    gradient = np.linalg.solve(edges, velocity[:, 1:] - velocity[:, :1])
    divergence = np.trace(gradient, axis1=1, axis2=2)
    if not np.all(np.isfinite(divergence)):
        raise ValueError("Nonfinite fluid divergence")
    return volumes, divergence


def close(x, y, tol, context):
    if not math.isfinite(x) or not math.isfinite(y) or abs(x-y) > tol:
        raise ValueError(f"{context}: {x} vs {y}")


def read_csv(path):
    with path.open() as stream:
        return [{key:float(value) for key,value in row.items()} for row in csv.DictReader(stream)]


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def external_loads(directory, steps, mode, peak=PEAK, duration=1., through_step=None):
    log = (directory/"1-procs/histor.dat").read_text()
    expected = [(int(s),int(i),p) for s,i in re.findall(r"^\s*FS\s+(\d+)-(\d+)s?\s",log,re.M)
                for p in PORTS]
    rows = [line.split() for line in (directory/"solve.log").read_text().splitlines()
            if line.startswith("pressure_observer ")]
    if through_step is not None:
        if not 1<=through_step<=steps:raise ValueError('Requested pressure prefix is outside the run')
        expected=[rec for rec in expected if rec[0]<=through_step]
        rows=[r for r in rows if int(r[2])<=through_step]
        if {s for s,_,_ in expected}!=set(range(1,through_step+1)):
            raise ValueError('Missing time step in pressure prefix')
    if [(int(r[2]),int(r[3]),r[1]) for r in rows] != expected or not expected:
        raise ValueError(f"Incomplete port/iteration trace {directory}")
    stages = {}
    for _, face, s, it, ts, weight, low, high in rows:
        step, iteration = int(s), int(it)
        time, af, lo, hi = map(float,(ts,weight,low,high))
        dt = duration/steps
        close(time,step*dt,2e-13*duration,"svFSI lookup time")
        close(af,2./3.,2e-15,"svFSI state weight")
        source_time = eon_stage(step,dt) if mode == "matched" else time
        p = smooth_pressure(source_time/duration, peak)
        for load in (lo,hi):
            close(load,p,3e-15*peak/PEAK,"svFSI residual-side pressure")
        key = (step,PORTS.index(face)+1)
        if key not in stages:
            stages[key] = dict(lookup_time=time, source_time=source_time, solver_state_time=(step-1+af)*dt,
                               min_pressure=lo, max_pressure=hi, observations=0)
        values = stages[key]
        values.update(min_pressure=min(values["min_pressure"],lo), max_pressure=max(values["max_pressure"],hi),
                      observations=iteration)
    return stages


def eon_loads(directory, steps, peak=PEAK):
    log = (directory/"solve.log").read_text()
    if log.splitlines()[-1:] != ["status=success"]:
        raise ValueError(f"Unsuccessful EONSim run {directory}")
    faces = read_csv(directory/"tube_pressure_faces.csv")
    accepted = read_csv(directory/"tube.csv")
    if ([(r["step"],r["tag"]) for r in faces] != [(s,k) for s in range(1,steps+1) for k in (1,2)]
            or [r["step"] for r in accepted] != list(range(1,steps+1))):
        raise ValueError(f"Incomplete EONSim history {directory}")
    result = {}
    for row in faces:
        step,tag = int(row["step"]),int(row["tag"])
        time = eon_stage(step,1./steps)
        pressure = row["stage_prescribed_pressure"]
        close(row["evaluation_time"],time,2e-13,"EONSim evaluation time")
        close(row["time"],step/steps,2e-13,"EONSim accepted time")
        close(row["accepted_dt"],1./steps,2e-14,"EONSim dt")
        close(pressure,smooth_pressure(time,peak),3e-15,"EONSim stage pressure")
        close(pressure,accepted[step-1]["applied_pressure"],3e-15,"EONSim accepted assembly load")
        close(row["endpoint_prescribed_pressure"],smooth_pressure(step/steps,peak),3e-15,"EONSim endpoint load")
        result[step,tag] = dict(lookup_time=time,source_time=time,solver_state_time=time,
                                min_pressure=pressure,max_pressure=pressure,observations=1)
    return result


def control_error(reference, modified, steps, meshes, external):
    differences = {"displacement":0., "velocity":0., "pressure":0.}
    for step in range(1,steps+1):
        fields = [external.external_fields(p/f"1-procs/result_{step:03d}.vtu",meshes)
                  for p in (reference, modified)]
        for left,right in zip(*fields):
            for node, state in left.items():
                for key in differences:
                    delta = np.max(np.abs(np.subtract(getattr(state,key),getattr(right[node],key))))
                    if not np.isfinite(delta):
                        raise ValueError(f"Nonfinite control difference {key}")
                    differences[key] = max(differences[key],float(delta))
    return differences


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--reference-scripts", type=Path, required=True)
    cli.add_argument("--work", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--steps", type=int, nargs="+", required=True)
    args = cli.parse_args()
    sys.path.insert(0,str(args.reference_scripts.resolve()))
    import compare_svfsi_wall as external
    import study_hydrostatic_fsi as fsi
    import study_lame_wall as wall
    import study_rigid_tube as tube

    source = args.archive/"coupled/sv05-s48"
    for name,digest in INPUT_SHA256.items():
        if file_sha(source/name) != digest:
            raise ValueError(f"Changed reference input {name}")
    meshes = [tube.read_mesh(source/name) for name in ("fluid.msh","solid.msh")]
    mesh_audit = SurfaceAudit(meshes[0])
    ref_volume = mesh_audit.volume(np.zeros((len(mesh_audit.ids),7)))
    nodes,_,faces = meshes[1]
    rings = {}
    for node in {n for tag,face in faces if tag==13 for n in face}:
        rings.setdefault(nodes[node][0],[]).append(node)
    sections = sorted(rings)
    exact = 2*wall.lame(wall.INNER,PEAK)[0]/wall.INNER
    convergence = {}
    traces, loads, cross, first = [],[],[],[]
    max_mismatch = 0.
    ref_external = args.archive/"svfsi/alpha05-medium-dt025"
    svmesh_sha = {p.name:file_sha(p) for p in (*ref_external.glob("*.vtu"),*ref_external.glob("*.vtp"))}
    for n in sorted(set(args.steps)):
        if n <= 0 or n%2:
            raise ValueError("An even step count is needed for common 0.5 and 1 s samples")
        strain = {}
        applied = {}
        for mode in ("eon","endpoint","matched"):
            name = f"{mode}-{n}"
            directory = args.work/name
            if mode == "eon":
                for mesh in ("fluid.msh","solid.msh"):
                    if file_sha(directory/mesh) != INPUT_SHA256[mesh]:
                        raise ValueError(f"Mesh mismatch {name} {mesh}")
                cfg = json.loads((directory/"case.json").read_text())
                expected = json.loads((source/"case.json").read_text())
                expected["fsi"].update(steps=n,dt=1./n,pressure_face_history=True,
                                       pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.))
                if cfg != expected:
                    raise ValueError(f"EONSim deck mismatch {name}")
                port = eon_loads(directory,n)
            else:
                if any(file_sha(directory/k) != v for k,v in svmesh_sha.items()):
                    raise ValueError(f"External mesh or face mismatch {name}")
                history = (directory/"1-procs/histor.dat").read_text()
                convergence[name] = {eq:external.check_convergence(history,n,eq) for eq in ("FS","MS")}
                port = external_loads(directory,n,mode)
            applied[mode] = port
            for (step,tag),values in sorted(port.items()):
                loads.append(dict(case=name,step=step,tag=tag,**values))
            for step in range(1,n+1):
                if mode == "eon":
                    fluid = fsi.recovered_state(directory,f"tube_step{step}",meshes[0],False,1)
                    solid = fsi.recovered_state(directory,f"tube_step{step}_solid",meshes[1],True,1)
                else:
                    fluid,solid = external.external_fields(directory/f"1-procs/result_{step:03d}.vtu",meshes)
                state = mesh_audit.array(fluid)
                gain = mesh_audit.volume(state)-ref_volume
                ends = mesh_audit.observe(state,smooth_pressure(step/n))
                inlet = -sum(end["outward_flow"] for end in ends.values())
                disp = {node:value.displacement for node,value in solid.items()}
                velo = {node:value.velocity for node,value in solid.items()}
                measures = [wall.bore_section(nodes,disp,rings[x]) for x in sections]
                mid = sections.index(wall.LENGTH/2)
                speed = wall.bore_section(nodes,velo,rings[sections[mid]])["radial_displacement"]
                radial = measures[mid]["radial_displacement"]
                strain[mode,step] = np.array([m["linear_area_strain"] for m in measures])
                row = dict(case=name,step=step,time=step/n,mid_displacement=radial,mid_velocity=speed,
                           lumen_volume_gain=gain,net_fluid_inflow=inlet)
                row.update({f"strain_{i}":v for i,v in enumerate(strain[mode,step])})
                if not all(math.isfinite(v) for k,v in row.items() if k!="case"):
                    raise ValueError(f"Nonfinite field observable {name} step {step}")
                traces.append(row)
                if step==1:
                    ratio = radial*n/speed
                    # svFSI's FSI/lElas equation uses alpha_m=5/6, gamma=2/3,
                    # beta=49/144 at rho_inf=.5. From rest d1/(dt*v1)=beta/gamma.
                    close(ratio,1. if mode=="eon" else 49./96.,1e-6,"First-step wall kinematics")
                    first.append(dict(case=name,dt=1./n,displ_over_dt_velocity=ratio,**{k:row[k] for k in
                                      ("mid_displacement","mid_velocity","lumen_volume_gain","net_fluid_inflow")}))
        for key, matched in applied["matched"].items():
            mismatch = abs(matched["min_pressure"]-applied["eon"][key]["min_pressure"])
            close(mismatch,0.,3e-15,"Intercode assembled pressure mismatch")
            max_mismatch = max(max_mismatch,mismatch)
        for step in range(1,n+1):
            for mode in ("endpoint","matched"):
                diff = (strain["eon",step]-strain[mode,step])/exact
                worst = int(np.argmax(abs(diff)))
                cross.append(dict(steps=n,dt=1./n,time=step/n,mode=mode,worst_x=sections[worst],
                                  signed_gap_at_worst=diff[worst],max_abs_gap=abs(diff[worst])))
    left,right = [args.work/f"{mode}-4" for mode in ("control","endpoint")]
    if (left/"svFSI.inp").read_bytes() != (right/"svFSI.inp").read_bytes():
        raise ValueError("Observer control needs identical input")
    for path in [*svmesh_sha,*(f"{name}.dat" for name in PORTS)]:
        if (left/path).read_bytes() != (right/path).read_bytes():
            raise ValueError(f"Observer control input mismatch: {path}")
    for eq in ("FS","MS"):
        external.check_convergence((left/"1-procs/histor.dat").read_text(),4,eq)
    control = control_error(left,right,4,meshes,external)
    if max(control.values()) > 0.:
        raise ValueError(f"Observer changed the saved fields {control}")
    args.output.mkdir(parents=True,exist_ok=True)
    for fname,rows in (("fields",traces),("ports",loads),("section-gaps",cross),("startup",first)):
        write_csv(args.output/f"{fname}.csv",rows)
    summary = dict(reference_volume=ref_volume,axial_positions=sections,lame_equilibrium_area_strain=exact,
                   max_matched_pressure_delta_pa=max_mismatch,unmodified_vs_observer_abs_max=control,
                   svfsi_worst_normalized_residual_and_zero_corrections=convergence,
                   checkpoints=[r for r in cross if r["time"] in (.5,1.)],
                   binaries={mode:(args.work/f"{mode}-4/executable.sha256").read_text().strip()
                             for mode in ("eon","endpoint","control")})
    (args.output/"results.json").write_text(json.dumps(summary,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
