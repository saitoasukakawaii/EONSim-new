"""Exercise native checkpoint continuation against short, uninterrupted A trajectories."""
import argparse
import json
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
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    def window(end,profile,label,extra):
        dest=out/label
        subprocess.run([sys.executable,str(HERE/'run_window.py'),'A',str(end),profile,str(args.binary.resolve()),
                        str(dest),'--limit','120',*map(str,extra)],check=True)
        return dest
    profile='fixed-1e-6'
    direct=window(4,'lu','prefix-lu',['--save-checkpoint'])
    iterative=window(4,profile,'prefix-iterative',['--save-checkpoint','--reference',direct])
    direct_tail=window(20,'lu','resumed-lu',['--resume-from',direct,'--prefix-pair',iterative])
    iterative_tail=window(20,profile,'resumed-iterative',['--resume-from',iterative,'--reference',direct_tail])
    result={}
    cold_lu=None
    for p,tail in [('lu',direct_tail),(profile,iterative_tail)]:
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
        mesh=[read_mesh(tail/(n+'.msh')) for n in ('fluid','solid')]
        delta=compare_trajectories(tail,cold,20,mesh,(4,4),select('CALIBRATED-v2',p),starts=(4,0))
        fields=max(s['maximum'] for phase in delta['full_field_differences'] for k,s in phase.items() if k!='step')
        history=max(delta['history_maximum_difference'].values())
        if max(fields,history,max(delta['pressure_face_differences'].values()))>2e-9:
            raise ValueError(f'Same-profile restart differs from uninterrupted trajectory: {p}')
        result[p]=dict(start=4,end=20,accepted=target['accepted_steps'],cold_receipt=digest(cold/'window.json'),
                       resumed_receipt=digest(tail/'window.json'),full_field_max=fields,history_max=history,
                       pressure_face_max=max(delta['pressure_face_differences'].values()),threshold=2e-9)
    save(out/'restart-regression.json',result)


if __name__=='__main__':
    main()
