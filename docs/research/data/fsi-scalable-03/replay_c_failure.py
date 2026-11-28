"""Instrument the archived C ASM failure in a fresh 64-core Slurm allocation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fsi-scalable-02"))
from paired_tube import digest, run, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    case = args.archive.resolve()
    root = args.output.resolve()
    if not os.getenv("SLURM_JOB_ID") or len(os.sched_getaffinity(0)) != 64:
        parser.error("requires 64 allocated physical cores")
    summary = json.loads((case / "summary.json").read_text())
    archived = case / "0-eon"
    original = json.loads((archived / "run.json").read_text())
    command = original["command"]
    binary = Path(command[command.index("-case") - 1])
    if digest(binary) != summary["binaries"]["eon"] or digest(archived / "solve.log") != original["log_sha256"]:
        raise ValueError("Archived binary or log differs from receipt")
    root.mkdir(parents=True, exist_ok=False)
    inputs = {}
    for name in ("case.json", "fluid.msh", "solid.msh"):
        if digest(archived / name) != summary["inputs"]["eon/" + name]:
            raise ValueError(f"Archived input changed: {name}")
        shutil.copyfile(archived / name, root / name)
        inputs[name] = digest(root / name)
    partition = Path(command[command.index("-partition") + 1])
    if not all((partition / f"rank_{rank}.h5").is_file() for rank in range(64)):
        raise ValueError("Incomplete archived partition")
    receipt = dict(inputs=inputs, binary=digest(binary), original_log=original["log_sha256"],
                   partition={p.name: digest(p) for p in sorted(partition.iterdir()) if p.is_file()},
                   job=os.environ["SLURM_JOB_ID"], affinity=sorted(os.sched_getaffinity(0)))
    os.environ.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    flags = ["-ksp_monitor", "-snes_monitor", "-ksp_converged_reason", "-ksp_view",
             "-ksp_view_mat", "binary:operator.petsc", "-ksp_view_rhs", "binary:rhs.petsc"]
    try:
        run(root, command + flags, receipt, 780, 140 * 2**30)
    except RuntimeError:
        log = (root / "solve.log").read_text(errors="replace")
        if "linear_iteration_limit_residual solve=1 " not in log or "DIVERGED_ITS" not in log:
            raise
        receipt["diagnosis"] = "first_linear_iteration_limit_reproduced"
    else:
        raise ValueError("Archived failure did not reproduce")
    finally:
        receipt["artifacts"] = {p.name: digest(p) for p in root.glob("*.petsc*") if p.is_file()}
        save(root / "diagnosis.json", receipt)


if __name__ == "__main__":
    main()
