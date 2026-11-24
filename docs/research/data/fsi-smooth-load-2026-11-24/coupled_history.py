"""Diagnose converged, rebounding and capped coupled equations from complete native histories."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_history import check_convergence, equation_iterations


def equation_info(history, equation, steps, tolerance, cap):
    grouped=defaultdict(list)
    for row in equation_iterations(history,equation):
        grouped[row.step].append(row)
    if set(grouped)!=set(range(1,steps+1)):
        raise ValueError("Analysis requires a complete simulation, including rejected final histories")
    failures=[]
    rejected_linear=[]
    for step,corrections in grouped.items():
        final=corrections[-1]
        if final.residual>1e-8:
            earlier=[r for r in corrections[:-1] if r.number>=2]
            failures.append(dict(step=step,final_iteration=final.number,final_residual=final.residual,
                                 minimum_previous=min((r.residual for r in earlier),default=None),
                                 met_internal_target_earlier=any(r.residual<=tolerance for r in earlier),
                                 accepted_at_cap=final.number==cap))
        rejected_linear.extend(dict(step=step,iteration=r.number,iterations=r.linear_iterations,residual=r.residual)
                               for r in corrections if r.linear_failed and (r.linear_iterations or r.residual>1e-8))
    try:
        check_convergence(history,steps,equation)
        accepted=True
    except ValueError:
        accepted=False
    if accepted!=(not failures and not rejected_linear and grouped[steps][-1].number>=2):
        raise ValueError("Coupled history diagnosis disagrees with the strict production history reader")
    worst=max((r[-1] for r in grouped.values()),key=lambda r:r.residual)
    peak=max(len(v) for v in grouped.values())
    return dict(accepted=accepted,max_iterations=peak,worst_final=dict(step=worst.step,iteration=worst.number,residual=worst.residual),
                failed_final_count=len(failures),rebound_count=sum(f["met_internal_target_earlier"] for f in failures),
                cap_count=sum(f["accepted_at_cap"] for f in failures),first_failed=failures[0] if failures else None,
                failed_linear_count=len(rejected_linear),first_failed_linear=rejected_linear[0] if rejected_linear else None)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--runs",type=Path,required=True)
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args()
    out=[]
    for group in ("time-tail","time-tight","current-time","reference-div","mesh-increment"):
        for history in sorted((args.runs/group).glob("n*/matched/1-procs/histor.dat")):
            parent=history.parents[2]
            match=re.fullmatch(r"n(\d+)-(.+)",parent.name)
            steps=int(match[1])
            runlog=parent.with_name(parent.name+".log")
            # Running jobs may already have written the last VTU while their independent audit is unfinished.
            if not (parent/"results.json").exists() and (not runlog.exists() or "Traceback" not in runlog.read_text()):
                continue
            raw=history.read_text()
            deck=(parent/"matched/svFSI.inp").read_text()
            # Each equation has its own nonlinear control; nested LS controls are indented further.
            control=re.findall(r"^Add equation:[^\n]*\{\s*\n(.*?)(?=^\s*LS type:|^\s*Add domain:)",deck,re.M|re.S|re.I)
            if len(control)!=2:raise ValueError("Could not isolate fluid/structure and mesh solver controls")
            nonlinear=[]
            for header in control:
                cap=re.findall(r"^\s*Max iterations:\s*(\d+)\s*$",header,re.M|re.I)
                tol=re.findall(r"^\s*Tolerance:\s*([\d.Ee+-]+)\s*$",header,re.M|re.I)
                if len(cap)!=1 or len(tol)!=1:raise ValueError("Missing equation-specific tolerances")
                nonlinear.append((int(cap[0]),float(tol[0])))
            result=dict(group=group,case=parent.name,steps=steps,variant=match[2],histor_sha256=hashlib.sha256(history.read_bytes()).hexdigest(),
                        sv_executable_sha256=(parent/"matched/executable.sha256").read_text().strip(),equations={})
            for (name,(cap,tol)) in zip(("FS","MS"),nonlinear):
                result["equations"][name]=dict(internal_control=tol,iteration_cap=cap,**equation_info(raw,name,steps,tol,cap))
            result["qualified_for_comparison"]=(parent/"results.json").is_file()
            if result["qualified_for_comparison"] and not all(v["accepted"] for v in result["equations"].values()):
                raise ValueError("An unconverged solution entered the comparison")
            out.append(result)
    if not out:raise ValueError("No completed histories")
    args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+"\n")
    for row in out:
        print(row["group"],row["case"],[(k,v["failed_final_count"],v["rebound_count"],v["failed_linear_count"]) for k,v in row["equations"].items()])


if __name__=="__main__":
    main()
