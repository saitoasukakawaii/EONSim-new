"""Check reference-normal wall supports against the supported Lamé tube and independent work integration."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np


def equilibrium(wall, stiffness, inner_pressure):
    # Lamé displacement at the outer surface is affine in both pressures.
    due_inner = wall.lame(wall.OUTER, inner_pressure)[0]
    due_unit_outer = wall.lame(wall.OUTER, 0., 1.)[0]
    outer_pressure = stiffness * due_inner / (1 - stiffness * due_unit_outer)
    inner_area = 2 * wall.lame(wall.INNER, inner_pressure, outer_pressure)[0] / wall.INNER
    return outer_pressure, inner_area


class OuterWall:
    def __init__(self, mesh):
        nodes, _, faces = mesh
        self.order = list(nodes)
        index = {n:i for i,n in enumerate(self.order)}
        self.faces = np.array([[index[n] for n in f] for tag,f in faces if tag == 14])
        xyz = np.array([nodes[n] for n in self.order])[self.faces]
        normal = np.cross(xyz[:,1] - xyz[:,0], xyz[:,2] - xyz[:,0])
        length = np.linalg.norm(normal,axis=1)
        self.area = length/2
        self.normal = normal/length[:,None]
        self.barycentric = np.full((3,3), 1/6)
        np.fill_diagonal(self.barycentric, 2/3)

    def trace(self, fields, name):
        values = np.array([getattr(fields[n],name) for n in self.order])[self.faces]
        projected = np.einsum("fac,fc->fa", values, self.normal)
        return projected @ self.barycentric.T

    def metrics(self, d, v, k, c):
        integrate = lambda values: float(self.area @ values.mean(axis=1))
        return np.array([.5*k*integrate(d*d), c*integrate(v*v), -integrate((k*d+c*v)*v)])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "work", "executable", "reference-scripts"):
        cli.add_argument("--"+name, type=Path, required=True)
    cli.add_argument("--support", action="append", nargs=2, type=float, metavar=("STIFFNESS","DAMPING"), required=True)
    cli.add_argument("--dt", type=float, default=.25)
    cli.add_argument("--steps", type=int, default=64)
    cli.add_argument("--output-interval", type=int, default=1)
    cli.add_argument("--audit-only",action="store_true",help="Verify archived inputs and re-integrate existing output fields")
    args = cli.parse_args()
    if args.dt <= 0 or args.steps < 2 or args.output_interval < 1 or args.steps % args.output_interval:
        cli.error("Need positive dt and a snapshot interval dividing the final step")
    sys.path.insert(0,str(args.reference_scripts.resolve()))
    import study_hydrostatic_fsi as fsi
    import study_lame_wall as wall
    import study_rigid_tube as tube

    mesh = tube.read_mesh(args.case/"solid.msh")
    surface = OuterWall(mesh)
    nodes = mesh[0]
    rings = {}
    for n in {n for tag,f in mesh[2] if tag == 13 for n in f}:
        rings.setdefault(nodes[n][0], []).append(n)
    positions = sorted(rings)
    cfg = json.loads((args.case/"case.json").read_text())
    p = cfg["fsi"]["pressure"]
    if cfg["time"] != {"scheme":"generalized_alpha","rho_infinity":.5} or cfg["fsi"]["material"] != "linear":
        raise ValueError("The reference requires the archived linear wall and alpha time integration")
    cfg["fsi"].update(dt=args.dt, steps=args.steps, output_interval=args.output_interval,
                      pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.))
    args.work.mkdir(parents=True,exist_ok=args.audit_only)
    exe = args.executable.resolve()
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(binary_sha256=digest(exe), mesh_sha256={f:digest(args.case/f) for f in ("solid.msh","fluid.msh")},
                  dt=args.dt, steps=args.steps, output_interval=args.output_interval, x=positions,
                  peak_pressure=p, regimes=[])
    if args.audit_only:
        saved=json.loads((args.work/"results.json").read_text())
        if any(saved[key]!=result[key] for key in ("binary_sha256","mesh_sha256","steps","dt","output_interval","peak_pressure")):
            raise ValueError("Audit parameters differ from the original solver run")
    for k,c in args.support:
        if not np.all(np.isfinite([k,c])) or min(k,c)<0:
            cli.error("Coefficients must be finite and nonnegative")
        path = args.work/f"k{k:g}-c{c:g}"
        cfg["fsi"]["domains"]["wall_supports"] = [dict(tag=14,stiffness=k,damping=c)]
        if args.audit_only:
            if json.loads((path/"case.json").read_text())!=cfg or any(digest(path/f)!=s for f,s in result["mesh_sha256"].items()):
                raise ValueError("Saved wall support configuration or mesh differs from the requested case")
        else:
            path.mkdir()
            for name in ("fluid.msh","solid.msh"):
                shutil.copyfile(args.case/name,path/name)
            (path/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
            with (path/"solve.log").open("w") as out:
                subprocess.run([exe,"-case","case.json"],cwd=path,env=dict(os.environ,OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1"),
                               stdout=out,stderr=subprocess.STDOUT,check=True)
        if (path/"solve.log").read_text().splitlines()[-1:] != ["status=success"]:
            raise ValueError("Incomplete nonlinear solve")
        with (path/"tube.csv").open() as stream:
            rows = [{key:float(v) for key,v in row.items()} for row in csv.DictReader(stream)]
        if len(rows) != args.steps or any(r["step"] != i or abs(r["time"]-i*args.dt)>1e-12 for i,r in enumerate(rows,1)):
            raise ValueError("Incomplete or mistimed accepted steps")
        p_ext, exact = equilibrium(wall,k,p)
        old_d = old_v = np.zeros((len(surface.faces),3))
        energy_old = total_work = total_damping_work = 0.
        energy_error = power_error = 0.
        samples = []
        for i,row in enumerate(rows,1):
            damping = row["stage_support_dissipation"]
            energy = row["endpoint_support_spring_energy"]
            work = row["step_support_work"]
            if min(damping,energy) < -1e-20 or not all(map(math.isfinite,row.values())):
                raise ValueError("Nonfinite history or negative stored/dissipated energy")
            total_work += work
            total_damping_work += args.dt*damping
            energy_error = max(energy_error,abs(work + energy - energy_old + args.dt*damping))
            energy_old = energy
            if i % args.output_interval:
                continue
            fields = fsi.recovered_state(path,f"tube_step{i}_solid",mesh,True,1)
            d = surface.trace(fields,"displacement")
            v = surface.trace(fields,"velocity")
            integrated = surface.metrics(d,v,k,c)
            energy_error = max(energy_error,abs(integrated[0]-energy))
            if args.output_interval == 1:
                af = 1. if i==1 else 2/3
                stage = surface.metrics((1-af)*old_d+af*d,(1-af)*old_v+af*v,k,c)
                written = [row["stage_support_spring_energy"],damping,row["stage_support_power"]]
                energy_error = max(energy_error,abs(stage[0]-written[0]))
                power_error = max(power_error,float(np.abs(stage[1:]-written[1:]).max()))
            old_d,old_v = d,v
            disp = {n:s.displacement for n,s in fields.items()}
            strain = [wall.bore_section(nodes,disp,rings[x])["linear_area_strain"] for x in positions]
            speed = max(math.dist(s.velocity,(0.,0.,0.)) for s in fields.values())
            samples.append(dict(time=row["time"],strain=strain,max_wall_speed=speed,
                                spring_energy=energy,stage_dissipation=damping,stage_power=row["stage_support_power"]))
        energy_error=max(energy_error,abs(total_work+energy_old+total_damping_work))
        energy_scale=max(abs(total_work),max(r["endpoint_support_spring_energy"] for r in rows),1e-15)
        power_scale=max(max(abs(r["stage_support_power"]) for r in rows),
                        max(r["stage_support_dissipation"] for r in rows),1e-15)
        if energy_error>2e-9*energy_scale or power_error>2e-9*power_scale:
            raise ValueError(f"Independent support audit mismatch: {energy_error} J, {power_error} W")
        endpoint = np.array(samples[-1]["strain"])
        result["regimes"].append(dict(stiffness=k,damping=c,outer_equilibrium_pressure=p_ext,
            equilibrium_area_strain=exact,normalized_final_section_errors=(endpoint/exact-1).tolist(),
            total_support_work=total_work,total_damping_work=total_damping_work,
            max_energy_error_joules=energy_error,
            max_power_error_watts=power_error if args.output_interval==1 else None,samples=samples))
        if not args.audit_only or len(result["regimes"])==len(args.support):
            temporary=args.work/"results.tmp"
            temporary.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
            temporary.replace(args.work/"results.json")
        print(k,c,exact,float(np.max(np.abs(endpoint/exact-1))),samples[-1]["max_wall_speed"],flush=True)


if __name__ == "__main__":
    main()
