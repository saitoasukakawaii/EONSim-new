"""Compare paired baseline/compact profile_case runs, including both domains' fields."""
import argparse
import csv
import json
import lzma
from pathlib import Path
import statistics

from profile_case import PHASES, field_diff, fields


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--work",type=Path,required=True,help="Contains rN-baseline and rN-compact")
    cli.add_argument("--output",type=Path,required=True)
    cli.add_argument("--pairs",type=int,default=5)
    args=cli.parse_args()
    if args.pairs<3: cli.error("Need at least three independent pairs")
    rows=[]
    binary={}
    mesh=None
    for repeat in range(args.pairs):
        run={}
        for variant in ("baseline","compact"):
            directory=args.work/f"r{repeat}-{variant}"
            info=json.loads((directory/"results.json").read_text())
            if mesh is None: mesh=info["mesh_sha256"]
            if mesh!=info["mesh_sha256"] or binary.setdefault(variant,info["binary_sha256"])!=info["binary_sha256"]:
                raise ValueError("Changed paired mesh or build")
            run[variant]={(r["ranks"],r["pc"],r["logging"]):r for r in info["runs"]}
            if len(run[variant])!=len(info["runs"]): raise ValueError("Ambiguous within-pair repeat")
        if run["baseline"].keys()!=run["compact"].keys(): raise ValueError("Unpaired runs")
        for (ranks,pc,logging),base in run["baseline"].items():
            cand=run["compact"][ranks,pc,logging]
            row=dict(pair=repeat,ranks=ranks,pc=pc,logging=logging,baseline_nnz=base["nnz"],compact_nnz=cand["nnz"],
                     linear_iterations=cand["linear_iterations"],dofs=cand["dofs"])
            if cand["dofs"]!=base["dofs"] or cand["linear_iterations"]!=base["linear_iterations"]:
                raise ValueError("Paired algebra dimension or iteration count differs")
            stem=f"r{ranks}-{pc}-0-log{int(logging)}"
            for label,suffix in (("fluid","tube.vtu"),("solid","tube_solid.vtu")):
                a,b=[fields(args.work/f"r{repeat}-{version}"/stem/suffix,ranks) for version in ("baseline","compact")]
                row[label+"_max_field_delta"]=field_diff(a,b)
                if row[label+"_max_field_delta"]>2e-8: raise ValueError("Baseline/candidate field mismatch")
            for variant,record in (("baseline",base),("compact",cand)):
                row[variant+"_wall"]=record["wall_seconds"]
                if logging:
                    for name in PHASES:
                        row[variant+"_"+name]=record["events"][name]["max_rank_seconds"]
                        row[variant+"_"+name+"_count"]=record["events"][name]["global_count"]
            rows.append(row)
    summary=[]
    for ranks,pc in sorted({(r["ranks"],r["pc"]) for r in rows}):
        for metric in ("wall",*PHASES):
            enabled=metric!="wall"
            selected=[r for r in rows if (r["ranks"],r["pc"],r["logging"])==(ranks,pc,enabled)]
            if len(selected)!=args.pairs: raise ValueError("Incomplete set of paired observations")
            base=[r["baseline_"+metric] for r in selected]
            cand=[r["compact_"+metric] for r in selected]
            changes=[v/u-1 for u,v in zip(base,cand)]
            summary.append(dict(ranks=ranks,pc=pc,metric=metric,baseline_median_seconds=statistics.median(base),
                                compact_median_seconds=statistics.median(cand),median_paired_change=statistics.median(changes),
                                min_paired_change=min(changes),max_paired_change=max(changes)))
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/"phase-medians.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=summary[0],lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    metadata=dict(sha256=binary,mesh_sha256=mesh,pairs=args.pairs,fields_max_over_runs={
        domain:max(r[domain+"_max_field_delta"] for r in rows) for domain in ("fluid","solid")},runs=rows)
    with lzma.open(args.output/"pair-results.json.xz","wt") as f:
        json.dump(metadata,f,indent=2,allow_nan=False)
        f.write("\n")


if __name__=="__main__":
    main()
