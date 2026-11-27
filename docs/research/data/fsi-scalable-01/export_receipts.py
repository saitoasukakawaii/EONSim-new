"""Export compact campaign evidence without publishing meshes, logs or host paths."""

import argparse
import hashlib
import json
from pathlib import Path


RUN_FIELDS = ("mode", "label", "status", "timing_sample", "dofs", "accepted_steps",
              "ranks", "threads", "repeat",
              "corrections", "outer_iterations", "iterations_per_correction", "wall_seconds",
              "solve_seconds", "linear_seconds", "assembly_seconds", "nnz",
              "peak_rss_max_bytes", "local_job_peak_sampled_rss_bytes", "local_job_rss_samples",
              "max_true_residual_ratio", "field_max_difference", "history_max_difference",
              "cross_partition_field_difference", "exit_code", "timeout", "log_sha256",
              "max_rank_reported_zero_lifts")


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def run_summary(run, root):
    row = {field: run[field] for field in RUN_FIELDS if field in run}
    if "error" in run:
        error = str(run["error"]).replace(str(root), "$RUN_ROOT").replace(str(root.parent), "$WORKSPACE")
        row["error"] = error.partition("\n")[0][:400]
    if "log" in run and Path(run["log"]).is_relative_to(root):
        row["raw_log"] = str(Path(run["log"]).relative_to(root))
    if "compressed_pressure_transfers" in run:
        keys = ("pressure_rows", "coarse_pressure_rows", "divergence_commuting_defect",
                "compatible_pressure_modes", "saturated_pressure_aggregates")
        row["first_hierarchy"] = []
        for transfer in run["compressed_pressure_transfers"]:
            if row["first_hierarchy"] and int(transfer["level"]) == 0:
                break
            row["first_hierarchy"].append({key: transfer[key] for key in keys})
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.run_root.resolve()
    campaigns = {}
    for receipt in sorted(root.glob("*/*/results.json")):
        receipt_bytes = receipt.read_bytes()
        data = json.loads(receipt_bytes)
        if "cases" not in data or "build_source" not in data:
            continue
        directory = str(receipt.parent.relative_to(root))
        entry = {key: data[key] for key in ("source_commit", "build_source", "executable_sha256",
                                           "campaign", "status", "fsi_threads", "timing_repeats",
                                           "expected_steps", "scaling") if key in data}
        entry["receipt_sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
        entry["cases"] = []
        for case in data["cases"]:
            prep = case.get("preparation", {})
            entry["cases"].append({
                "subdivisions": case["subdivisions"], "ranks": case["ranks"],
                "status": case["status"], "mesh": prep.get("metadata"),
                "prepare_seconds": prep.get("wall_seconds"),
                "prepare_peak_sampled_rss_bytes": prep.get("local_job_peak_sampled_rss_bytes"),
                "medians": case["medians"],
                "runs": [run_summary(run, root) for run in case["runs"]],
            })
        campaigns[directory] = entry
    summary = {"campaigns": campaigns}
    for name in ("zero-lift-ab", "hybrid-128"):
        receipt = root / name / "results.json"
        if not receipt.is_file():
            continue
        receipt_bytes = receipt.read_bytes()
        data = json.loads(receipt_bytes)
        summary[name] = {key: data[key] for key in ("modes", "build_source", "executable_sha256") if key in data}
        summary[name]["receipt_sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
        summary[name]["runs"] = [run_summary(run, root) for run in data["runs"]]
    pulsatile = root / "pulsatile-robin-rcr-retry/summary.json"
    if pulsatile.is_file():
        summary["pulsatile_robin_rcr"] = json.loads(pulsatile.read_bytes())
    patterns = ("environment.log", "*-source.txt", "*-ctest.log", "*-verify-*.log", "*-build.log",
                "*driver.log", "memory-guard.json", "physics-coverage.log", "petsc-profiles/*/petsc.txt",
                "run-*.sh", "profile-fsi.py", "zero-lift-ab.py", "benchmark_hybrid.py",
                "verify_pulsatile_robin_rcr*.py", "pulsatile-robin-rcr*.log", "zero-lift-ab*.py",
                "benchmark_hybrid*.py", "*.exit")
    summary["raw_artifacts"] = {
        str(file.relative_to(root)): digest(file)
        for pattern in patterns for file in sorted(root.glob(pattern)) if file.is_file()
    }
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
