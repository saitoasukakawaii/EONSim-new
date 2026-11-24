"""Profile a pressure-driven elastic tube and compare every final nodal field."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/"tests"))
from verify_schur import fields

PHASES=("FSIFluidRes","FSIFluidAleJac","FSISolidRes","FSISolidJac","FSIInsert","FSIForceReplay",
        "MatAssemblyBegin","MatAssemblyEnd","PCSetUp","PCApply")
FLAGS={"direct":[],"schur":["-schur_pc"],
       **{name:["-pc_recipe",name] for name in ("physics","quantity","hybrid","coupled_velocity")}}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events(path,ranks,accepted_steps,cell_counts):
    selected={}
    with path.open() as stream:
        for row in csv.DictReader(stream):
            name=row["Event Name"]
            if row["Stage Name"]!="Main Stage" or name not in PHASES:
                continue
            rank,count,seconds=int(row["Rank"]),int(row["Count"]),float(row["Time"])
            if not 0<=rank<ranks or count<0 or not math.isfinite(seconds) or seconds<0:
                raise ValueError(f"Invalid PETSc event {row}")
            if rank in selected.setdefault(name,{}):
                raise ValueError(f"Duplicated event {name} on rank {rank}")
            selected[name][rank]=(count,seconds)
    if set(selected)!=set(PHASES) or any(set(v)!=set(range(ranks)) for v in selected.values()):
        raise ValueError("Incomplete rank/event records")
    result={name:dict(global_count=sum(v[0] for v in seen.values()),
                      max_rank_seconds=max(v[1] for v in seen.values()),
                      rank_seconds=[seen[i][1] for i in range(ranks)])
            for name,seen in selected.items()}
    count=lambda name:result[name]["global_count"]
    fluid,solid=cell_counts
    # The solid Jacobian evaluation already contains its primal residual.
    if (any(count(name)<=0 for name in PHASES)
            or count("FSIFluidRes")%fluid or count("FSIFluidAleJac")%fluid
            or count("FSISolidRes")%solid or count("FSISolidJac")%solid
            or count("FSIInsert")%(fluid+solid)
            or count("FSIForceReplay")!=ranks*accepted_steps):
        raise ValueError("FSI event counts disagree with mesh or accepted-step count")
    evals=count("FSIInsert")//(fluid+solid)
    jac=count("FSIFluidAleJac")//fluid
    if (jac!=count("FSISolidJac")//solid or count("FSIFluidRes")//fluid!=evals
            or (count("FSISolidRes")+count("FSISolidJac"))//solid!=evals):
        raise ValueError("Inconsistent FSI residual/Jacobian/insert evaluations")
    return result


def field_diff(reference,current):
    if reference.keys()!=current.keys():
        raise ValueError("Output node sets differ")
    error=0.
    for n,values in current.items():
        if len(values)!=len(reference[n]) or not all(map(math.isfinite,values+reference[n])):
            raise ValueError("Invalid output values")
        error=max(error,max(abs(a-b) for a,b in zip(values,reference[n])))
    return error


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case",type=Path,required=True,help="Baseline two-ended EONSim case directory")
    cli.add_argument("--work",type=Path,required=True)
    cli.add_argument("--executable",type=Path,required=True)
    cli.add_argument("--mpiexec",type=Path,required=True)
    cli.add_argument("--ranks",type=int,nargs="+",default=[1,2,4])
    cli.add_argument("--pcs",choices=FLAGS,nargs="+",default=["direct","schur"])
    cli.add_argument("--repeats",type=int,default=3)
    cli.add_argument("--steps",type=int,default=2)
    args=cli.parse_args()
    exe=args.executable.resolve()
    work=args.work.resolve()
    work.mkdir(parents=True)
    if min(args.ranks)<1 or args.repeats<1 or args.steps<1 or len(set(args.ranks))!=len(args.ranks):
        cli.error("Positive distinct rank counts, repeats and steps are required")
    env=dict(os.environ,OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",
             OMPI_MCA_pml="ob1",OMPI_MCA_btl="self,sm,tcp",
             PRTE_MCA_rmaps_default_mapping_policy=":oversubscribe")
    cfg=json.loads((args.case/"case.json").read_text())
    cfg["fsi"].update(dt=.25,steps=args.steps,output_interval=0,pressure_face_history=False,
                      pressure_time=dict(amplitude=0.,period=1.,ramp_time=1.))
    (work/"case.json").write_text(json.dumps(cfg,indent=2)+"\n")
    counts=[]
    for mesh in ("fluid.msh","solid.msh"):
        target=work/mesh
        shutil.copyfile(args.case/mesh,target)
        lines=target.read_text().splitlines()
        ids=lines.index("$Elements")
        counts.append(sum(int(row.split()[1])==4 for row in lines[ids+2:ids+2+int(lines[ids+1])]))
    def run(cmd,directory):
        with (directory/"solve.log").open("w") as out:
            start=time.monotonic()
            subprocess.run(cmd,cwd=directory,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
            return time.monotonic()-start

    result=dict(binary_sha256=digest(exe),mesh_sha256=[digest(work/n) for n in ("fluid.msh","solid.msh")],
                cells=counts,steps=args.steps,runs=[])
    reference=None
    for ranks in args.ranks:
        partition=work/f"parts-{ranks}"
        prep=work/f"prepare-{ranks}"
        prep.mkdir()
        run([exe,"-case",work/"case.json","-prepare",partition,"-parts",str(ranks)],prep)
        for pc in args.pcs:
            for rep in range(-1,args.repeats):
                # First sample warms both code paths. Alternate their order in timed pairs.
                modes=([False] if rep<0 else [False,True] if rep%2==0 else [True,False])
                for enabled in modes:
                    stem=f"r{ranks}-{pc}-{rep}-log{int(enabled)}"
                    directory=work/stem
                    directory.mkdir()
                    cmd=[args.mpiexec.resolve(),"-n",str(ranks),exe,"-case",work/"case.json",
                         "-partition",partition,"-output",directory/"tube.vtu","-solver_report",*FLAGS[pc]]
                    if enabled:
                        cmd.extend(["-log_view",":events.csv:ascii_csv"])
                    elapsed=run(cmd,directory)
                    log=(directory/"solve.log").read_text()
                    if "status=success" not in log or "step_retry=" in log:
                        raise ValueError(f"Rejected or unfinished timing run {stem}")
                    reports=[dict(re.findall(r"(\w+)=([^\s]+)",line)) for line in log.splitlines()
                             if line.startswith("solver_report ")]
                    if (len(reports)!=args.steps or any(int(r["snes_reason"])<=0 or int(r["ksp_reason"])<=0
                        or int(r["domain_rejections"])!=0 for r in reports)):
                        raise ValueError(f"Solver acceptance failed in {stem}")
                    current=[fields(directory/(suffix+".vtu"),ranks) for suffix in ("tube","tube_solid")]
                    if reference is None: reference=current
                    differences=[field_diff(a,b) for a,b in zip(reference,current)]
                    if max(differences)>2e-8:
                        raise ValueError(f"Rank/solver/logging changed final nodal fields: {differences}")
                    if rep<0: continue
                    row=dict(ranks=ranks,pc=pc,repeat=rep,logging=enabled,wall_seconds=elapsed,
                             max_field_delta=differences,nnz=float(reports[0]["nnz"]),dofs=int(reports[0]["dofs"]),
                             linear_iterations=sum(int(r["linear_iterations"]) for r in reports))
                    if enabled:
                        row["events"]=events(directory/"events.csv",ranks,args.steps,counts)
                    result["runs"].append(row)
                    (work/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    for ranks in args.ranks:
        for pc in args.pcs:
            on=[r for r in result["runs"] if (r["ranks"],r["pc"],r["logging"])==(ranks,pc,True)]
            print(ranks,pc,{name:round(statistics.median(r["events"][name]["max_rank_seconds"] for r in on),5)
                            for name in ("FSIFluidAleJac","FSIInsert","PCSetUp","PCApply")})


if __name__=="__main__":
    main()
