"""Run balanced Release ALE element timings and verify deterministic checksums across implementations."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess


def measure(executable,n,env):
    result=subprocess.run([executable,'--kernel-samples',str(n)],env=env,stdout=subprocess.PIPE,text=True,check=True)
    records=[]
    for row in result.stdout.splitlines():
        columns=dict(field.split('=',1) for field in row.split())
        record={k:float(v) for k,v in columns.items()}
        if int(record['samples'])!=n or min(record['cpu_seconds'],record['wall_seconds'])<=0 or not all(map(math.isfinite,record.values())):
            raise ValueError('Invalid timed kernel output')
        records.append(record)
    if [int(r['pressure_face']) for r in records]!=[0,1]:
        raise ValueError('Missing interior or pressure-loaded element')
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--builds',type=Path,required=True)
    parser.add_argument('--libs',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=40000)
    parser.add_argument('--rounds',type=int,default=8)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.samples<1000 or args.rounds<4 or args.rounds%4:
        parser.error('Use at least 1,000 samples and a positive multiple of four rounds')
    env=dict(os.environ,LD_LIBRARY_PATH=str(args.libs.resolve()),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    keys=['quadrature-before','moments-before','quadrature-scalar','moments-scalar']
    binaries={k:(args.builds/(k+'-kernel')).resolve() for k in keys}
    for binary in binaries.values():measure(binary,2000,env)
    report=dict(samples=args.samples,sha256={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in binaries.items()},rounds=[],summary={})
    checksums={}
    for rep in range(args.rounds):
        # A balanced four-treatment order, reversed for the next four rounds.
        perm=(0,1,3,2) if rep//4%2==0 else (2,3,1,0)
        ordered=[keys[(i+rep)%4] for i in perm]
        sample={}
        for name in ordered:
            sample[name]=measure(binaries[name],args.samples,env)
            for face,row in enumerate(sample[name]):
                expected=checksums.setdefault(face,row['checksum'])
                if not math.isclose(row['checksum'],expected,rel_tol=2e-12,abs_tol=1e-10):
                    raise ValueError('Tangent kernel checksum changed')
        report['rounds'].append(sample)
        print(rep,ordered,flush=True)
    for name in keys:
        report['summary'][name]=[]
        for face in (0,1):
            times=[r[name][face]['cpu_seconds'] for r in report['rounds']]
            deltas=[r[name][face]['cpu_seconds']/r[keys[0]][face]['cpu_seconds']-1 for r in report['rounds']]
            report['summary'][name].append(dict(pressure_face=bool(face),median_cpu_us_per_cell=1e6*statistics.median(times)/args.samples,
                                                median_paired_cpu_change_pct=100*statistics.median(deltas),range_paired_pct=[100*min(deltas),100*max(deltas)]))
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(report['summary'])


if __name__=='__main__':main()
