"""Measure the default and metric ALE tangents with CPU timers and balanced execution order."""
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import statistics

from compare_kernel import measure


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','libs','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--samples',type=int,default=40000)
    p.add_argument('--rounds',type=int,default=12)
    a=p.parse_args()
    if a.rounds<6 or a.rounds%6 or a.samples<1000:p.error('Use complete six-order blocks and at least 1000 samples')
    env=dict(os.environ,LD_LIBRARY_PATH=str(a.libs.resolve()),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    variants={'before':(a.before,'--kernel-samples'),'after':(a.after,'--kernel-samples'),
              'metric':(a.after,'--metric-kernel-samples')}
    def run(name,count):
        exe,option=variants[name]
        return measure(exe.resolve(),count,env,option)
    for name in variants:run(name,2000)
    observations=[]
    orders=list(itertools.permutations(variants))
    for i in range(a.rounds):
        row={}
        for name in orders[i%len(orders)]:row[name]=run(name,a.samples)
        for j in (0,1):
            if not math.isclose(row['before'][j]['checksum'],row['after'][j]['checksum'],rel_tol=1e-11,abs_tol=1e-11):
                raise ValueError('Default full tangent checksum changed')
        observations.append(row)
    summary={}
    for name in variants:
        comparison='before' if name!='metric' else 'after'
        table=[]
        for face in (0,1):
            times=[r[name][face]['cpu_seconds'] for r in observations]
            ratios=[r[name][face]['cpu_seconds']/r[comparison][face]['cpu_seconds'] for r in observations]
            table.append(dict(face=face,median_cpu_us=statistics.median(times)*1e6/a.samples,
                               paired_ratio_to=comparison,median_ratio=statistics.median(ratios),range_ratio=[min(ratios),max(ratios)]))
        summary[name]=table
    raw=dict(samples=a.samples,balanced_rounds=a.rounds,binaries={n:hashlib.sha256(v[0].read_bytes()).hexdigest() for n,v in variants.items()},
             results=observations,summary=summary)
    a.output.write_text(json.dumps(raw,indent=2,allow_nan=False)+'\n')
    print(summary)


if __name__=='__main__':main()
