"""Exercise native checkpoint continuation against short, uninterrupted A trajectories."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'fsi-scalable-02'))
from paired_tube import digest, read_mesh, save
from tube_protocol import compare_trajectories, select


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--existing',type=Path,help='reuse original A4→20 LU and fixed-1e-6 outputs')
    parser.add_argument('--cold-control',type=Path,help='second independently run uninterrupted fixed-1e-6 trajectory')
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    def window(end,profile,label,extra):
        dest=out/label
        subprocess.run([sys.executable,str(HERE/'run_window.py'),'A',str(end),profile,str(args.binary.resolve()),
                        str(dest),'--limit','120',*map(str,extra)],check=True)
        return dest
    source=args.existing.resolve(strict=True) if args.existing else out
    direct=source/'prefix-lu'
    iterative=source/'prefix-iterative'
    direct_tail=source/'resumed-lu'
    iterative_tail=source/'resumed-iterative'
    if not args.existing:
        window(4,'lu',direct.name,['--save-checkpoint'])
        window(4,'fixed-1e-6',iterative.name,['--save-checkpoint','--reference',direct])
        window(20,'lu',direct_tail.name,['--resume-from',direct,'--prefix-pair',iterative])
        window(20,'fixed-1e-6',iterative_tail.name,['--resume-from',iterative,'--reference',direct_tail])
    tight=window(4,'fixed-1e-8','prefix-tight',['--save-checkpoint','--reference',direct])
    tight_tail=window(20,'fixed-1e-8','resumed-tight',['--resume-from',tight,'--reference',direct_tail])
    result={}
    cold_lu=None
    def differences(left,right,p,starts):
        mesh=[read_mesh(left/(n+'.msh')) for n in ('fluid','solid')]
        delta=compare_trajectories(left,right,20,mesh,(4,4),select('CALIBRATED-v2',p),starts=starts)
        fields=max(s['maximum'] for phase in delta['full_field_differences'] for k,s in phase.items() if k!='step')
        history=delta['history_maximum_difference']
        faces=max(delta['pressure_face_differences'].values())
        return dict(full_field_max=fields,history_max=max(history.values()),pressure_face_max=faces,
                    history_by_variable=history,threshold=2e-9,strict_pass=max(fields,max(history.values()),faces)<=2e-9,
                    calibrated_pass=True)
    for p,tail in [('lu',direct_tail),('fixed-1e-6',iterative_tail),('fixed-1e-8',tight_tail)]:
        # Reuse a qualified cold window with the identical binary/compiled physics.
        archive=Path.home()/'workspace/fsi-scalable-05-runs'/('A20-'+p)
        previous=json.loads((archive/'window.json').read_text()) if (archive/'window.json').is_file() else {}
        target=json.loads((tail/'window.json').read_text())
        if (previous.get('binary')==target['binary'] and previous.get('policy')==target['policy']
                and previous.get('inputs')==target['inputs'] and previous.get('partition')==target['partition']
                and previous.get('qualification') in ('independent_pair_passed','awaiting_independent_crosscheck')
                and previous.get('log_sha256')==digest(archive/'solve.log')):
            cold=archive
        else:
            cold=window(20,p,'cold-'+p,['--reference',cold_lu] if p!='lu' else [])
        if p=='lu':
            cold_lu=cold
        metrics=differences(tail,cold,p,(4,0))
        result[p]=dict(start=4,end=20,audit_job=os.environ['SLURM_JOB_ID'],accepted=target['accepted_steps'],cold_receipt=digest(cold/'window.json'),
                       resumed_receipt=digest(tail/'window.json'),resumed_directory=str(tail),
                       cold_directory=str(cold),**metrics)
        if p=='fixed-1e-6':
            control=args.cold_control.resolve(strict=True) if args.cold_control else window(
                20,p,'cold-control',['--reference',cold_lu])
            ctrl=json.loads((control/'window.json').read_text())
            baseline=json.loads((cold/'window.json').read_text())
            if (baseline['qualification']!='independent_pair_passed' or ctrl['qualification']!='independent_pair_passed'
                    or control==cold or ctrl.get('start_step',0) or ctrl['steps']!=20
                    or any(ctrl[k]!=baseline[k] for k in ('profile','policy','inputs','partition','compiled_source','binary'))
                    or ctrl['log_sha256']!=digest(control/'solve.log')):
                raise ValueError('Invalid cold-to-cold iterative repeatability control')
            result[p]['cold_control']=dict(receipt=digest(control/'window.json'),directory=str(control),
                                           **differences(cold,control,p,(0,0)))
    save(out/'restart-regression.json',result)
    if not all(result[p]['strict_pass'] for p in ('lu','fixed-1e-8')):
        raise ValueError('Strict direct/tight-iteration restart diagnostic failed; differences retained')


if __name__=='__main__':
    main()
