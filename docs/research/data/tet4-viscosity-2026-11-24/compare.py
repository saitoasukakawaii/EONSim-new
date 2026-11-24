"""Paired Release measurements of the two EONSim executables on identical inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_fluid_element_report import element_records
from profile_multistep_setup import parse
from profile_schur_mesh import delta, fields
from verify_schur import physical_records, compare_physics


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--base", required=True, type=Path)
    cli.add_argument("--candidate", required=True, type=Path)
    cli.add_argument("--mpiexec", required=True, type=Path)
    cli.add_argument("--work", required=True, type=Path)
    cli.add_argument("--pairs", type=int, default=6)
    args = cli.parse_args()
    if args.pairs < 2:
        cli.error("Use at least two pairs to alternate order.")
    executables = {"base": args.base.resolve(), "candidate": args.candidate.resolve()}
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               OMPI_MCA_pml="ob1", OMPI_MCA_btl="self,sm,tcp", SUPERLU_ACC_OFFLOAD="0")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    mesh = ROOT / "cases/poisson/cube.msh"
    result = {
        "sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in executables.items()},
        "mesh_sha256": hashlib.sha256(mesh.read_bytes()).hexdigest(),
        "platform": platform.platform(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "pairs": args.pairs, "groups": [],
    }

    def run(cmd, stem):
        start = time.perf_counter()
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                   cwd=ROOT, text=True, timeout=240)
        wall = time.perf_counter() - start
        (work / (stem + ".log")).write_text(completed.stdout)
        completed.check_returncode()
        return wall, completed.stdout

    for name, case, marker in (("fluid", "fluid/transient.yaml", "fluid_step"),
                               ("fsi", "fsi/elastic.yaml", "fsi_step")):
        case = ROOT / "cases" / case
        for ranks in (1, 2):
            partition = work / f"{name}-part{ranks}"
            run([executables["base"], "-case", case, "-mesh", mesh, "-prepare", partition,
                 "-parts", str(ranks)], f"{name}-prepare-{ranks}")
            group = {"case": name, "ranks": ranks, "runs": []}
            for repeat in range(-1, args.pairs):
                pair = {}
                field_pairs = {}
                observations = {}
                for version in (("base", "candidate") if repeat % 2 == 0 else ("candidate", "base")):
                    stem = f"{name}-{ranks}-{repeat}-{version}"
                    output = work / (stem + ".vtu")
                    cmd = [args.mpiexec, "-n", str(ranks), executables[version], "-case", case,
                           "-mesh", mesh, "-partition", partition, "-output", output, "-solver_report"]
                    if name == "fluid":
                        cmd.append("-fluid_element_report")
                    wall, text = run(cmd, stem)
                    steps = parse(text, marker)
                    item = {"wall_s": wall, "assembly_s": sum(s["assembly_seconds"] for s in steps),
                            "solve_s": sum(s["solve_seconds"] for s in steps),
                            "linear_iterations": [s["linear_iterations"] for s in steps],
                            "newton_iterations": [s["snes_iterations"] for s in steps]}
                    field_pairs[version] = [fields(output, ranks)]
                    if name == "fsi":
                        field_pairs[version].append(fields(output.with_stem(output.stem+"_solid"), ranks))
                        observations[version] = physical_records(text)
                    else:
                        rows = element_records(text, ranks, True)
                        item["kernel_s"] = max(sum(float(r["kernel_seconds"]) for r in rows
                                                   if int(r["rank"]) == rank) for rank in range(ranks))
                    pair[version] = item
                if name == "fsi":
                    compare_physics(observations["base"], observations["candidate"])
                field_errors = [delta(a, b) for a, b in zip(field_pairs["base"], field_pairs["candidate"])]
                if max(field_errors) > 2e-9:
                    raise RuntimeError(f"Baseline/candidate field difference: {field_errors}")
                group["runs"].append(dict(repeat=repeat, field_max_abs=field_errors, **pair))
            measured = group["runs"][1:]  # one warm-up for each binary
            summary = {}
            for metric in (k for k in measured[0]["base"] if k.endswith("_s")):
                ratios = [r["candidate"][metric]/r["base"][metric] for r in measured]
                summary[metric] = {
                    "base_median": statistics.median(r["base"][metric] for r in measured),
                    "candidate_median": statistics.median(r["candidate"][metric] for r in measured),
                    "ratio_median": statistics.median(ratios), "ratio_min": min(ratios), "ratio_max": max(ratios)}
            group["summary"] = summary
            result["groups"].append(group)
            (work / "pairs.json").write_text(json.dumps(result, indent=2) + "\n")
            print(name, ranks, summary, flush=True)


if __name__ == "__main__":
    main()
