import glob
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(os.environ["FSI_RUNS"])
sys.path.insert(0, "scripts")
import benchmark_fsi_block_scaling as bench

prior = json.loads(Path(glob.glob(str(root / "coarse-timing/*/results.json"))[0]).read_text())
case = prior["cases"][0]
run = next(item for item in case["runs"] if item["label"] == "warmup-mono_pressure_auto")
reference_command = run["command"]
reference_output = Path(reference_command[reference_command.index("-output") + 1])
reference_fields = reference_output.parent / "fields.sqlite"
reference_history = bench.assembly.history(reference_output.with_suffix(".csv"), 5, 0.02)
paths = {"before": root / "eonsim-before-zero-lift", "after": Path("build/release/eonsim").resolve()}
shas = {"before": prior["build_source"], "after": "796153b6ebf5a665d6f0ed30a037d9a7c154e78d"}
output = root / "zero-lift-ab"
output.mkdir()
result = {"modes": {mode: {"build_source": shas[mode], "executable_sha256": bench.assembly.digest(path)}
                   for mode, path in paths.items()}, "runs": []}
for repeat, order in enumerate((("before","after"), ("before","after"), ("after","before"), ("before","after"))):
    for mode in order:
        folder = output / f"{repeat}-{mode}"
        folder.mkdir()
        solution = folder / "solution.vtu"
        command = list(run["command"])
        executable_index = command.index(prior["executable"])
        command[executable_index] = str(paths[mode])
        command[command.index("-output")+1] = str(solution)
        receipt = {"mode": mode, "timing_sample": repeat > 0, "command": command}
        result["runs"].append(receipt)
        log = folder / "solver.log"
        try:
            text = bench.block.timed_command(command, log, 130, receipt, rss_interval=0.5, rss_limit=180*2**30)
            history = bench.assembly.history(solution.with_suffix(".csv"), 5, 0.02)
            receipt.update(bench.multigrid.audit(text, history, 8, "mono_pressure_auto"))
            bench.spool_fields(solution, 8, folder / "fields.sqlite")
            receipt["field_max_difference"] = bench.compare_spools(reference_fields, folder / "fields.sqlite")
            receipt["history_max_difference"] = bench.multigrid.previous.compare_history(reference_history, history)
            solver = bench.assembly.records(text, "monolithic_mg_stats ")
            receipt["max_rank_reported_zero_lifts"] = max(int(row.get("braess_zero_lift_skips", 0)) for row in solver)
            if mode == "after" and not receipt["max_rank_reported_zero_lifts"]:
                raise RuntimeError("the zero-lift branch did not execute")
            receipt["status"] = "passed"
        except Exception as err:
            receipt["status"] = "failed"
            receipt["error"] = str(err)
        receipt["log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest() if log.is_file() else None
        bench.save(result, output / "results.json")
        print(mode, repeat, receipt["status"], receipt.get("wall_seconds"),
              receipt.get("max_rank_reported_zero_lifts"), receipt.get("error"), flush=True)
assert all(row["status"] == "passed" for row in result["runs"])
