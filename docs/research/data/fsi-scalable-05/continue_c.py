"""Declare and submit one longer C window after its independent predecessor and restart regression pass."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
PREDECESSOR={32:20,100:32,224:100}
FIXED='fixed-1e-6'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as f:
        value=hashlib.sha256()
        for block in iter(lambda:f.read(1<<20),b''):
            value.update(block)
    return value.hexdigest()


def elapsed(job):
    lines=subprocess.check_output(['sacct','-XnP','-j',str(job),'-o','JobIDRaw,State,ExitCode,ElapsedRaw'],
                                  text=True).splitlines()
    selected=[v.split('|') for v in lines if v.split('|')[0]==str(job)]
    if len(selected)!=1 or selected[0][1:3]!=['COMPLETED','0:0']:
        raise ValueError(f'Slurm job {job} lacks a successful, completed allocation')
    return int(selected[0][3])


def window(path):
    r=read(path/'window.json')
    start=r['start_step']
    if (r['case']!='C' or r['ranks']!=64 or r['formal'] or r['status']!='exited'
            or r['accepted_steps']!=list(range(start+1,r['steps']+1)) or r['covered_steps']!=r['steps']
            or r['checkpoint']['step']!=r['steps'] or r['policy']['protocol_id']!='CALIBRATED-v2'
            or not 0<r['rss_peak']<=r['rss_limit'] or sha(path/'solve.log')!=r['log_sha256']):
        raise ValueError(f'Incomplete C predecessor trajectory: {path}')
    duration=elapsed(r['job'])
    return r,dict(directory=str(path),window_sha256=sha(path/'window.json'),start=start,end=r['steps'],
                  T_job=r['T_job'],elapsed_seconds=duration,rss_peak=r['rss_peak'])


def restart_qualification(path,binary):
    result=read(path)
    if set(result)!={'lu',FIXED,'fixed-1e-8'}:
        raise ValueError('Missing restart regression profile')
    for profile,r in result.items():
        tail=Path(r['resumed_directory'])/'window.json'
        w=read(tail)
        if (r['start']!=4 or r['end']!=20 or r['accepted']!=list(range(5,21)) or r['threshold']!=2e-9
                or not r['calibrated_pass'] or (profile!=FIXED and not r['strict_pass'])
                or (profile==FIXED and not r['cold_control']['calibrated_pass'])
                or r['resumed_receipt']!=sha(tail) or w['binary']!=binary or w['profile']!=profile
                or w['qualification']!=('awaiting_independent_crosscheck' if profile=='lu' else 'independent_pair_passed')):
            raise ValueError(f'Missing matching uninterrupted A restart regression: {profile}')
        elapsed(r['audit_job'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path,help='campaign directory containing source and matching release build')
    parser.add_argument('end',type=int,choices=PREDECESSOR)
    parser.add_argument('restart_regression',type=Path)
    parser.add_argument('--submit',action='store_true',help='save the declaration and submit both jobs')
    args=parser.parse_args()
    root=args.root.resolve(strict=True)
    start=PREDECESSOR[args.end]
    profiles=('lu',FIXED)
    paths=[root/f'C{start}-{p}' for p in profiles]
    direct,iterative=[window(d) for d in paths]
    a,b=direct[0],iterative[0]
    if (a['qualification']!='awaiting_independent_crosscheck' or b['qualification']!='independent_pair_passed'
            or (a['profile'],b['profile'])!=profiles or b['reference_receipt']!=direct[1]['window_sha256']
            or b['reference_outputs']!=a['outputs'] or a['steps']!=start
            or any(a[k]!=b[k] for k in ('steps','start_step','inputs','partition','compiled_source','binary'))):
        raise ValueError('Prior direct and iterative windows lack an independent cross-check')
    qa=args.restart_regression.resolve(strict=True)
    restart_qualification(qa,a['binary'])
    binary=Path(a['command'][a['command'].index('-case')-1]).resolve(strict=True)
    if sha(binary)!=a['binary']:
        raise ValueError('Original qualified release binary changed')
    outdirs=[root/f'C{args.end}-{p}' for p in profiles]
    if any(d.exists() for d in outdirs):
        raise ValueError('A target directory already exists; inspect its trajectory before a retry')
    plan=dict(case='C',protocol_id='CALIBRATED-v2',start=start,end=args.end,qa=str(qa),qa_sha256=sha(qa),
              binary_sha256=a['binary'],solver_budget='ceil(1.35 * slower observed seconds/step * new steps + 60)',
              slurm_allowance='max(900 s, 120 s + 2 * prior non-solver seconds per step * total end step)',runs=[])
    for (row,receipt),profile,out,prev in zip((direct,iterative),profiles,outdirs,paths):
        anchors=[receipt]
        if start!=20:
            cold,cold_receipt=window(Path(row['prefix_segments'][0]['directory']))
            if (cold['steps']!=20 or cold['start_step'] or cold['profile']!=profile or cold['binary']!=row['binary']
                    or cold_receipt['window_sha256']!=row['prefix_segments'][0]['window_sha256']):
                raise ValueError('Invalid C20 timing anchor')
            anchors.append(cold_receipt)
        seconds_per_step=max(i['T_job']/(i['end']-i['start']) for i in anchors)
        review_per_step=max((i['elapsed_seconds']-i['T_job'])/(i['end']-i['start']) for i in anchors)
        solve=math.ceil(1.35*seconds_per_step*(args.end-start)+60)
        wall=math.ceil((solve+max(900,120+2*max(0,review_per_step)*args.end))/60)
        solver=[str(HERE/'run_case.sh'),'C',str(args.end),profile,str(binary),str(out),'--resume-from',str(prev),
                *(['--prefix-pair',str(paths[1])] if profile=='lu' else ['--reference',str(outdirs[0])]),
                '--limit',str(solve)]
        plan['runs'].append(dict(profile=profile,anchors=anchors,rss_limit=row['rss_limit'],solver_seconds=solve,
            slurm_minutes=wall,snes_max_it=row['linear']['solver_reports'][0]['snes_max_it'],
            ksp_max_it=row['linear']['effective_options'].get('-ksp_max_it'),rtol=row['policy']['rtol'],
            atol=row['policy']['atol'],refinement_steps=row['policy'].get('refinements'),command=solver))
    if args.submit:
        target=root/f'C{args.end}-plan'
        target.mkdir(exist_ok=False)
        def publish():
            tmp=target/'continuation.json.tmp'
            tmp.write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
            os.replace(tmp,target/'continuation.json')
        publish()
        for i,r in enumerate(plan['runs']):
            name=f"C{args.end}-{r['profile']}"
            cmd=['sbatch','--parsable','-n','64','--exclusive','--time',str(r['slurm_minutes']),
                 '-J',name,'-o',str(root/(name+'-%j.log'))]
            if i:
                cmd.extend(['--dependency','afterok:'+plan['runs'][0]['job']])
            r['job']=subprocess.check_output([*cmd,*r['command']],text=True,cwd=HERE,
                env={**os.environ,'FSI05_ROOT':str(root)}).strip().split(';')[0]
            if not r['job'].isdigit():
                raise RuntimeError(f'Unexpected Slurm job ID {r["job"]}')
            publish()
    print(json.dumps(plan,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
