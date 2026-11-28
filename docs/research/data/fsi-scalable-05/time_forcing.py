"""Alternate two qualified cold starts under the same independent LU reference."""
import argparse
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'fsi-scalable-02'))
from paired_tube import digest, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixed','challenger','reference','binary','output'):
        parser.add_argument(name,type=Path)
    parser.add_argument('--change',choices=('forcing','fixed-tolerance','owner','coarse_rows'),default='forcing')
    args = parser.parse_args()
    qualified = [json.loads((d/'window.json').read_text()) for d in (args.fixed,args.challenger)]
    base, other = qualified
    reference = args.reference.resolve(strict=True)
    pcs = [q.get('preconditioner',{'pc':'physics'}) for q in qualified]
    if args.change in ('owner','coarse_rows'):
        different = {k for k in pcs[0].keys() | pcs[1].keys() if pcs[0].get(k)!=pcs[1].get(k)}
        matched = (base['policy']==other['policy'] and different=={args.change} and pcs[0]['pc']=='pressure-mg')
    elif args.change=='forcing':
        matched = pcs[0]==pcs[1] and other['profile']==base['profile'].replace('fixed-','inexact-',1)
    else:
        matched = pcs[0]==pcs[1] and other['profile'].startswith('fixed-') and other['profile']!=base['profile']
    if (not base['profile'].startswith('fixed-') or not matched or
            base['binary']!=digest(args.binary) or
            any(base[k]!=other[k] for k in ('binary','compiled_source','case','inputs','steps','partition','ranks')) or
            any(q['qualification']!='independent_pair_passed' or
                q['reference_receipt']!=digest(reference/'window.json') for q in qualified)):
        parser.error('requires matched, independently qualified fixed and inexact windows')
    root = args.output.resolve()
    root.mkdir(parents=True,exist_ok=False)
    result = dict(job=os.environ['SLURM_JOB_ID'], experiment=args.change, runs=[], status='incomplete')
    try:
        for index in range(4):
            for side in ((0,1) if index%2==0 else (1,0)):
                q, pc = qualified[side], pcs[side]
                folder = root/f"{index}-{side}-{q['profile']}"
                command = [sys.executable, str(HERE/'run_window.py'), q['case'], str(q['steps']),
                           q['profile'], str(args.binary.resolve()), str(folder), '--reference',
                           str(reference), '--limit',str(q['limit_seconds']), '--formal']
                if pc['pc']=='pressure-mg':
                    command.extend(['--pc','pressure-mg','--owner',pc['owner'],'--coarse-rows',str(pc['coarse_rows'])])
                    if pc['mg_scale']:
                        command.append('--mg-scale')
                subprocess.run(command,check=True)
                row = json.loads((folder/'window.json').read_text())
                if row['qualification']!='independent_pair_passed' or row['policy']!=q['policy']:
                    raise ValueError('Timing sample failed the qualified profile')
                result['runs'].append(dict(side=side, profile=q['profile'], pc=pc, warmup=index==0,
                    receipt_sha256=digest(folder/'window.json'), receipt=str(folder/'window.json'),
                    T_job=row['T_job'], memory_bytes=row['rss_peak'], core_hours=row['core_hours'],
                    newton=row['linear']['corrections'], ksp=row['linear']['ksp_iterations']))
        timings = [median(r['T_job'] for r in result['runs'] if
                   r['side']==side and not r['warmup']) for side in (0,1)]
        result.update(status='passed',medians=timings,
                      reduction=1-timings[1]/timings[0])
    finally:
        save(root/'timings.json',result)


if __name__=='__main__':
    main()
