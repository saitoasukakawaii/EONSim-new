"""Export the bounded large-grid campaign, preserving failures and every timing sample."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('root',type=Path);cli.add_argument('output',type=Path)
    args=cli.parse_args();root=args.root.resolve(); records=[]
    keys=('mode','label','status','wall_seconds','linear_seconds','assembly_seconds','solve_seconds',
          'dofs','nnz','corrections','outer_iterations','max_true_residual_ratio','field_max_difference',
          'history_max_difference','peak_rss_max_bytes','local_job_peak_sampled_rss_bytes','log_sha256',
          'error','exit_code','timeout','memory_failure')
    for threads in (2,4,1):
        files=sorted((root/f'large-t{threads}').glob('*/results.json'))
        if len(files)!=1: raise ValueError(f'Expected one campaign receipt for t={threads}, got {files}')
        raw=files[0].read_bytes();snapshot=json.loads(raw)
        for case in snapshot['cases']:
            compact=dict(threads=threads,ranks=case['ranks'],subdivisions=case['subdivisions'],status=case['status'],
                         source=snapshot['build_source'],binary=snapshot['executable_sha256'],driver=snapshot['driver_sha256'],
                         receipt=str(files[0].relative_to(root)),receipt_sha256=hashlib.sha256(raw).hexdigest(),
                         prepare_seconds=case.get('preparation',{}).get('wall_seconds'),inputs=case.get('input_sha256'),
                         error=case.get('error'),runs=[])
            for r in case.get('runs',[]):
                row={k:r[k] for k in keys if k in r};row['log']=str(Path(r['log']).relative_to(root))
                compact['runs'].append(row)
            if case['status']=='passed':
                samples=[r for r in compact['runs'] if r['label'].startswith('timing-')]
                if len(samples)!=3 or any(r['status']!='passed' for r in samples):raise ValueError('Incomplete timed trials')
                times=[r['wall_seconds'] for r in samples];compact['median_seconds']=statistics.median(times)
                compact['core_hours']=compact['median_seconds']*compact['ranks']*threads/3600
            records.append(compact)
    expected={(n,r,t) for n in (37,47) for r,t in ((64,2),(32,4),(32,1),(64,1),(128,1))}
    missing=expected-{(x['subdivisions'],x['ranks'],x['threads']) for x in records}
    args.output.write_text(json.dumps(dict(cases=records,missing=sorted(missing)),indent=2)+'\n')


if __name__=='__main__': main()
