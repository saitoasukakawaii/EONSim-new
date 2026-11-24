"""Solve the two-ended tube using the same mesh and sampled quintic loading."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PEAK = .02
PORTS = ("fluid_in", "fluid_out")
MODES = ("eon", "endpoint", "matched", "control")
INPUT_SHA256 = {
    "case.json": "9095e0a94682c746a2e23a84741af875018e64c7bbe9178d3e717514e8980c03",
    "fluid.msh": "6a2eddd7ee53d6cd43d6c0706d21a3295b99d79431ec037e21a5d1149d8b8f7f",
    "solid.msh": "ca61d566c848adb2bc41b9bbbebf5dff3454818008b921960d135e05a1a27016",
}


def smooth_pressure(time):
    x = min(1., max(0., time))
    return PEAK * x**3 * (10. + x * (-15. + 6.*x))


def eon_stage(step, dt):
    return (step - 1 + (1. if step == 1 else 2./3.))*dt


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def face_ids(path):
    from vtkmodules.vtkIOXML import vtkXMLPolyDataReader
    reader = vtkXMLPolyDataReader()
    reader.SetFileName(str(path))
    reader.Update()
    mesh = reader.GetOutput()
    ids = mesh.GetPointData().GetArray("GlobalNodeID")
    if not ids or not mesh.GetNumberOfPoints():
        raise ValueError(f"Missing GlobalNodeID in {path}")
    nodes = [int(ids.GetValue(i)) for i in range(mesh.GetNumberOfPoints())]
    if len(set(nodes)) != len(nodes) or min(nodes) <= 0:
        raise ValueError(f"Invalid face node IDs in {path}")
    return nodes


def external_input(source, directory, steps, dt, mode, linear_atol):
    for mesh in (*source.glob("*.vtp"), *source.glob("*.vtu")):
        shutil.copyfile(mesh, directory/mesh.name)
    # svFSI repeats general tables at their final timestamp. Add one hold
    # sample past the requested run so its last accepted step cannot wrap.
    times = [i*dt for i in range(steps+2)]
    values = [smooth_pressure(eon_stage(i,dt) if mode == "matched" and i else t)
              for i,t in enumerate(times)]
    values[-1] = values[-2]
    deck = (source/"svFSI.inp").read_text()
    replacements = {
        "Number of time steps: 48": f"Number of time steps: {steps}",
        "Time step size: 0.25": f"Time step size: {dt:.17g}",
        "Increment in saving restart files: 48": f"Increment in saving restart files: {steps}",
    }
    for port in PORTS:
        ids = face_ids(directory/f"{port}.vtp")
        table = [f"1 {len(times)} {len(ids)}", *(f"{t:.17g}" for t in times)]
        # General Neumann input is signed scalar normal traction. On each
        # end the original steady-pressure branch applies minus pressure.
        traction = [f"{-value:.17g}" for value in values]
        for node in ids:
            table.append(str(node))
            table.extend(traction)
        (directory/f"{port}.dat").write_text("\n".join(table)+"\n")
        old = f"   Add BC: {port} {{\n      Type: Neu\n      Value: 0.02"
        replacements[old] = (f"   Add BC: {port} {{\n      Type: Neu\n"
                             f"      Time dependence: General\n"
                             f"      Temporal and spatial values file path: {port}.dat")
    if linear_atol is not None:
        old = "Absolute tolerance: 1e-15"
        if deck.count(old) != 2 or not 0 < linear_atol <= 1e-15:
            raise ValueError("Expected two external linear solvers and a positive tightened tolerance")
        deck = deck.replace(old, f"Absolute tolerance: {linear_atol:.17g}")
    for old,new in replacements.items():
        if deck.count(old) != 1:
            raise ValueError(f"Unexpected external deck while replacing {old!r}")
        deck = deck.replace(old,new)
    (directory/"svFSI.inp").write_text(deck)


def eon_input(source, directory, steps, dt):
    for mesh in ("fluid.msh","solid.msh"):
        shutil.copyfile(source/mesh, directory/mesh)
    cfg = json.loads((source/"case.json").read_text())
    cfg["fsi"].update(dt=dt, steps=steps, pressure_face_history=True,
                      pressure_time=dict(amplitude=0., period=1., ramp_time=1.))
    (directory/"case.json").write_text(json.dumps(cfg, indent=2)+"\n")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--work", type=Path, required=True)
    cli.add_argument("--executable", type=Path, required=True)
    cli.add_argument("--mode", choices=MODES, required=True,
                     help="control uses the pristine svFSI binary with endpoint tables")
    cli.add_argument("--steps", type=int, nargs="+", required=True,
                     help="Number of uniform steps covering exactly one second")
    cli.add_argument("--linear-atol", type=float,
                     help="Tighten both svFSI linear solves for small first-step residuals")
    args = cli.parse_args()
    if args.mode == "eon" and args.linear_atol is not None:
        cli.error("--linear-atol applies only to svFSI")
    exe = args.executable.resolve()
    for steps in args.steps:
        if steps <= 0:
            raise ValueError("steps must be positive")
        dt = 1./steps
        directory = args.work/f"{args.mode}-{steps}"
        directory.mkdir(parents=True)
        if args.mode == "eon":
            source = args.archive/"coupled/sv05-s48"
            for name, digest in INPUT_SHA256.items():
                if file_sha(source/name) != digest:
                    raise ValueError(f"Unexpected EONSim reference input {name}")
            eon_input(source, directory, steps, dt)
            command = [exe, "-case", "case.json"]
        else:
            external_input(args.archive/"svfsi/alpha05-medium-dt025", directory, steps, dt, args.mode, args.linear_atol)
            command = [exe, "svFSI.inp"]
        (directory/"executable.sha256").write_text(file_sha(exe)+"\n")
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   OMPI_MCA_pml="ob1", OMPI_MCA_btl="self,sm,tcp")
        with (directory/"solve.log").open("w") as stream:
            subprocess.run(command, cwd=directory, env=env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        print(f"Completed {directory.name}", flush=True)


if __name__ == "__main__":
    main()
