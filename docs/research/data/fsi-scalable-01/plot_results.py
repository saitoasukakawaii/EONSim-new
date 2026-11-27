"""Generate CSV and figures from the compact server receipt export."""

import argparse
import csv
import json
from pathlib import Path
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def cases(campaigns, prefix):
    return [case for directory, campaign in campaigns.items()
            if directory.startswith(prefix + "/") for case in campaign["cases"]]


def write_csv(summary, directory):
    columns = ("campaign", "build_source", "subdivisions", "ranks", "omp_threads",
               "mode", "label", "status", "timing_sample", "dofs", "accepted_steps",
               "outer_iterations", "wall_seconds", "linear_seconds", "solve_seconds",
               "assembly_seconds", "peak_rss_max_bytes", "local_job_peak_sampled_rss_bytes",
               "max_true_residual_ratio", "field_max_difference", "prepare_seconds",
               "global_nodes", "global_cells")
    with (directory / "runs.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, columns, extrasaction="ignore")
        writer.writeheader()
        for name, campaign in summary["campaigns"].items():
            for case in campaign["cases"]:
                mesh = case["mesh"] or {}
                for run in case["runs"]:
                    writer.writerow(dict(run, campaign=name, build_source=campaign["build_source"],
                                         subdivisions=case["subdivisions"], ranks=case["ranks"],
                                         omp_threads=campaign.get("fsi_threads", 1),
                                         prepare_seconds=case["prepare_seconds"],
                                         global_nodes=mesh.get("global_nodes"), global_cells=mesh.get("global_cells")))
        for phase in ("zero-lift-ab", "hybrid-128"):
            evidence = summary.get(phase, {})
            for run in evidence.get("runs", []):
                source = evidence.get("build_source") or evidence["modes"][run["mode"]]["build_source"]
                writer.writerow(dict(run, campaign=phase, build_source=source,
                                     subdivisions=10 if phase == "zero-lift-ab" else 22,
                                     ranks=run.get("ranks", 8), omp_threads=run.get("threads", 1),
                                     mode=run.get("mode", "mono_pressure_auto"),
                                     label=run.get("label", run.get("repeat"))))


def plot_energy_and_pressure(campaigns, directory):
    observed = cases(campaigns, "pressure-timing")[0]["medians"]
    variants = ("mono_braess", "mono_braess_tentative", "mono_pressure_image")
    labels = ("Energy optimization", "Tentative transfer", "Compressed pressure image")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), layout="constrained")
    fig.suptitle("10,387 DoFs · 8 MPI ranks · five accepted FSI steps", fontsize=14)
    for ax, key, factor, unit in (
            (axes[0], "wall_seconds", 1, "End-to-end time (s)"),
            (axes[1], "local_job_peak_sampled_rss_bytes", 2**20, "Sampled job RSS (MiB)")):
        values = [observed[name][key]["median"] / factor for name in variants]
        bars = ax.barh(labels, values, color=("#336398", "#2e805d", "#a45b2a"))
        ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel(unit)
        ax.set_xlim(0, max(values) * 1.32)
        ax.grid(axis="x", alpha=0.18)
        ax.set_axisbelow(True)
    fig.savefig(directory / "energy-and-pressure.png", dpi=160)
    plt.close(fig)


def plot_strong_scaling(campaigns, directory):
    mode = "mono_pressure_auto"
    measured = [(case["ranks"], case["medians"][mode]["wall_seconds"]["median"])
                for case in cases(campaigns, "scale-n22") if mode in case["medians"]]
    if not measured:
        return
    measured.sort()
    baseline = measured[0][1]
    ranks, seconds = zip(*measured)
    fig, ax = plt.subplots(figsize=(7.8, 4.0), layout="constrained")
    ax.plot(ranks, [baseline / value for value in seconds], "o-", color="#336398", label="Measured median")
    target_ranks = [8, 16, 32, 64, 128]
    ax.plot(target_ranks, [1, 1.7, 3.2, 5.6, 8], "s--", color="#a45b2a", label="Acceptance target")
    ax.set_xscale("log", base=2)
    ax.set_xticks(target_ranks, [str(rank) for rank in target_ranks])
    ax.set(xlabel="MPI ranks", ylabel="Speedup over 8 ranks",
           title="108,379 DoFs · single-node strong scaling")
    ax.grid(alpha=0.2)
    ax.legend()
    fig.savefig(directory / "strong-scaling.png", dpi=160)
    plt.close(fig)


def plot_weak_scaling(campaigns, directory):
    measured = [row for name, campaign in campaigns.items() if name.startswith("weak/")
                for row in campaign.get("scaling", []) if row["weak_load_comparable"] is not None]
    if not measured:
        return
    measured.sort(key=lambda row: row["ranks"])
    fig, ax = plt.subplots(figsize=(7.8, 4.0), layout="constrained")
    for row in measured:
        ax.scatter(row["ranks"], 100 * row["efficiency"], color="#336398"
                   if row["weak_load_comparable"] else "#a45b2a")
    ax.set_xscale("log", base=2)
    ranks = [row["ranks"] for row in measured]
    ax.set_xticks(ranks, [str(rank) for rank in ranks])
    ax.set(xlabel="MPI ranks", ylabel="Weak scaling efficiency (%)",
           title="Approximately 10,000 DoFs per MPI rank")
    ax.axhline(100, linestyle=":", color="gray")
    ax.grid(alpha=0.2)
    fig.savefig(directory / "weak-scaling.png", dpi=160)
    plt.close(fig)


def plot_hybrid(summary, directory):
    samples = {}
    for row in summary.get("hybrid-128", {}).get("runs", []):
        if row["status"] == "passed" and row["timing_sample"]:
            samples.setdefault((row["ranks"], row["threads"]), []).append(row["wall_seconds"])
    values = [(f"{ranks} × {threads}", statistics.median(timings))
              for (ranks, threads), timings in sorted(samples.items(), reverse=True) if len(timings) == 3]
    if not values:
        return
    fig, ax = plt.subplots(figsize=(7.8, 4.0), layout="constrained")
    labels, times = zip(*values)
    bars = ax.bar(labels, times, color="#336398")
    ax.bar_label(bars, fmt="%.2f", padding=4)
    ax.set_ylim(0, max(times) * 1.18)
    ax.set(xlabel="MPI ranks × OpenMP threads", ylabel="End-to-end median (s)",
           title="108,379 DoFs · 128 physical cores")
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    fig.savefig(directory / "hybrid-scaling.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    summary = json.loads(args.summary.read_bytes())
    campaigns = summary["campaigns"]
    directory = args.summary.resolve().parent
    write_csv(summary, directory)
    plot_energy_and_pressure(campaigns, directory)
    plot_strong_scaling(campaigns, directory)
    plot_weak_scaling(campaigns, directory)
    plot_hybrid(summary, directory)


if __name__ == "__main__":
    main()
