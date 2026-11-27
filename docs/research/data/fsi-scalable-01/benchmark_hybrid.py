"""Interleave equal-core pure MPI and hybrid FSI comparisons on an audited input."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "scripts"))
import benchmark_fsi_block_scaling as bench


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--build-source", required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_bytes())
    reference = next(row for row in receipt["cases"][0]["runs"]
                     if row["label"] == "reference" and row["status"] == "passed")
    reference_command = reference["command"]
    reference_output = Path(reference_command[reference_command.index("-output") + 1])
    expected_history = bench.assembly.history(reference_output.with_suffix(".csv"), 5, 0.02)
    expected_fields = reference_output.parent / "fields.sqlite"
    result = {"build_source": args.build_source, "executable_sha256": bench.assembly.digest(args.executable),
              "runs": []}
    args.work.mkdir()
    configurations = [(rank, 128 // rank) for rank in (128, 64, 32, 16, 8)]
    completed = set(configurations)
    for repeat in range(4):
        order = configurations if repeat % 2 == 0 else list(reversed(configurations))
        for ranks, threads in order:
            if (ranks, threads) not in completed:
                continue
            case = next(case for case in receipt["cases"] if case["ranks"] == ranks)
            source_row = next((row for row in case["runs"]
                               if row["label"] == "reference" and row["status"] == "passed"), None)
            record = {"ranks": ranks, "threads": threads, "repeat": repeat, "timing_sample": repeat > 0}
            result["runs"].append(record)
            folder = args.work / f"repeat-{repeat}-r{ranks}-t{threads}"
            folder.mkdir()
            if source_row is None:
                record.update(status="failed", error="Missing accepted single-thread partition reference")
                completed.discard((ranks, threads))
                bench.save(result, args.work / "results.json")
                continue
            command = list(source_row["command"])
            command[command.index(receipt["executable"])] = str(args.executable.resolve())
            command[command.index("--map-by") + 1] = f"ppr:{ranks // 2}:socket:PE={threads}"
            command[command.index("-fsi_threads") + 1] = str(threads)
            output = folder / "solution.vtu"
            command[command.index("-output") + 1] = str(output)
            record["command"] = command
            os.environ.update(OMP_NUM_THREADS=str(threads), OMP_DYNAMIC="FALSE", OMP_PROC_BIND="close",
                              OMP_PLACES="cores", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
            log = folder / "solver.log"
            try:
                text = bench.block.timed_command(command, log, 300, record, rss_interval=0.5, rss_limit=180 * 2**30)
                history = bench.assembly.history(output.with_suffix(".csv"), 5, 0.02)
                record.update(bench.multigrid.audit(text, history, ranks, "mono_pressure_auto"))
                plan = bench.assembly.records(text, "fsi_execution_plan ")
                if not plan or any(int(item["threads_requested"]) != threads for item in plan):
                    raise RuntimeError("FSI thread-count evidence differs from the launch configuration")
                database = folder / "fields.sqlite"
                bench.spool_fields(output, ranks, database)
                record["field_max_difference"] = bench.compare_spools(expected_fields, database)
                record["history_max_difference"] = bench.multigrid.previous.compare_history(expected_history, history)
                record["status"] = "passed"
            except Exception as err:
                record.update(status="failed", error=str(err))
                completed.discard((ranks, threads))
            if log.is_file():
                record["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
            bench.save(result, args.work / "results.json")
            print(ranks, threads, repeat, record["status"], record.get("wall_seconds"), record.get("error"), flush=True)
    return 0 if len(completed) == len(configurations) else 1


if __name__ == "__main__":
    sys.exit(main())
