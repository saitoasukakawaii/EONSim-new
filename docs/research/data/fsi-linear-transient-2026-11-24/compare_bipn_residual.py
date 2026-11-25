"""Compare the native BIPN convergence flag with a full scaled matrix-vector residual."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from svfsi_history import check_convergence


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(log, explicit):
    corrections=[]
    pending=None
    prev=(0,0)
    for line in re.sub(r'\x1b\[[\d;]*m','',log).splitlines():
        if line.startswith('bipn_residual '):
            if pending is not None:
                raise ValueError('Two matrix observations for one correction')
            fields=line.split()
            if len(fields)!=8 or fields[2] not in ('T','F'):
                raise ValueError('Invalid BIPN residual observer record')
            iterations=int(fields[1])
            initial,projected,reported,actual,threshold=map(float,fields[3:])
            if (not all(map(math.isfinite,(initial,projected,actual,threshold))) or min(initial,actual)<0 or threshold<=0
                    or not math.isclose(threshold,max(1e-23,1e-10*initial),rel_tol=2e-12)):
                raise ValueError('Invalid measured residual scale or different linear tolerances')
            pending=dict(iterations=iterations,algorithm_success=fields[2]=='T',initial=initial,projected_squared=projected,
                         solver_norm=reported if math.isfinite(reported) else None,full_norm=actual,threshold=threshold)
            continue
        step=re.match(r'^\s*FS\s+(\d+)-(\d+)s?\s+',line)
        if not step:
            continue
        marker=re.search(r'([!\[])\s*(\d+)\s+-?\d+\s+-?\d+[!\]]\s*$',line)
        if not marker or pending is None or pending['iterations']!=int(marker[2]):
            raise ValueError('Unmatched native correction and independently applied matrix')
        pair=tuple(map(int,step.groups()))
        if pair not in ((prev[0],prev[1]+1),(prev[0]+1,1)):
            raise ValueError('Noncontiguous FSI corrections')
        prev=pair
        returned=marker[1]=='['
        actual_pass=pending['full_norm']<=pending['threshold']
        if returned!=(actual_pass if explicit else pending['algorithm_success']):
            raise ValueError('Solver success marker differs from selected stopping condition')
        corrections.append(dict(step=pair[0],correction=pair[1],returned=returned,full_pass=actual_pass,**pending))
        pending=None
    if pending is not None or not corrections or prev[0]!=32:
        raise ValueError('Incomplete 32-step BIPN trace')
    return corrections


def pack(root):
    data=[]
    for mode in ('observer','explicit','qr','explicit-floor','qr-floor'):
        group=root/('scaled-sv-bipn-'+mode)
        for receipt in sorted(group.glob('*.time')):
            case=receipt.with_suffix('')
            if not case.is_dir():
                raise ValueError('Missing measured solve')
            base=root/'scaled-sv-krylov'/case.name
            if not (base/'1-procs/histor.dat').is_file():
                raise ValueError('Missing matching unmodified BIPN control')
            inputs=('fluid.msh','solid.msh','fluid_in.dat','fluid_out.dat','svFSI.inp')
            hashes={k:sha(case/k) for k in inputs}
            if any(sha(base/k)!=v for k,v in hashes.items()):
                raise ValueError('Different mesh, physical load or solver deck')
            log=(case/'solve.log').read_text()
            history=(case/'1-procs/histor.dat').read_text()
            rows=records(log,mode!='observer')
            ns=(case/'FSILS_NS.log').read_text().splitlines()
            if len(ns)!=len(rows)+1 or int(ns[0].split()[1])!=1:
                raise ValueError('Incomplete or different rank-count split-solver history')
            for rec,line in zip(rows,ns[1:]):
                # Upstream format I4.3,I3,I4,I5,3I4,3ES9.2E2,3I4. Adjacent fields may have no space.
                if (int(line[:4])>=100)!=rec['returned'] or int(line[4:7])!=rec['iterations']:
                    raise ValueError('Native split-solver file disagrees with the full observer')
                rec['momentum_square_pct']=int(line[55:59])
                rec['continuity_square_pct']=int(line[59:63])
            native_history=(base/'1-procs/histor.dat').read_text()
            matches=None
            snapshots={}
            if mode=='observer':
                matches=True
                for step in range(4,33,4):
                    name=f'1-procs/result_{step:03d}.vtu'
                    actual,original=sha(case/name),sha(base/name)
                    matches &= actual==original
                    snapshots[name]=[actual,original]
                if not matches:
                    raise ValueError('Diagnostic-only binary altered a stored VTU field')
            strict={}
            for key,hist in [('measured',history),('native',native_history)]:
                try:
                    strict[key]=dict(passed=True,FS=check_convergence(hist,32,'FS'),MS=check_convergence(hist,32,'MS'))
                except ValueError as exc:
                    strict[key]=dict(passed=False,reason=str(exc))
            physical=case/'result.json'
            if physical.is_file()!=strict['measured']['passed']:
                raise ValueError('Raw convergence and external result acceptance disagree')
            data.append(dict(mode=mode,case=case.name,hashes=hashes,executable=sha(root/f'sv-bipn-{mode}-build/bin/svFSI'),
                             native_executable=sha(root/'sv-current-native-build/bin/svFSI'),log_sha256=sha(case/'solve.log'),
                             history_sha256=sha(case/'1-procs/histor.dat'),split_log_sha256=sha(case/'FSILS_NS.log'),native_history_sha256=sha(base/'1-procs/histor.dat'),
                             paired_vtu_hashes=snapshots,identical_native_fields=matches,strict=strict,
                             resource=json.loads(receipt.read_text()),corrections=rows))
    return data


def table(data):
    rows=[]
    for run in data:
        r=run['corrections']
        if not r or len({(x['step'],x['correction']) for x in r})!=len(r):
            raise ValueError('Empty or duplicate linear-solve receipt')
        successes=[x for x in r if x['returned']]
        false=[x for x in successes if not x['full_pass']]
        worst=max(r,key=lambda x:x['full_norm']/x['threshold'])
        floor=1e-24 if run['mode'].endswith('-floor') else 1e-23
        missed=[x for x in r if not x['full_pass']]
        block_limited=[]
        if run['mode']!='observer':
            for x in missed:
                frac=max(x['momentum_square_pct'],x['continuity_square_pct'])
                if x['solver_norm'] is not None and 0<=frac<=100 and x['solver_norm']*math.sqrt(min(1.,(frac+.5)/100))<=floor:
                    block_limited.append(x)
        rows.append(dict(case=run['case'],mode=run['mode'],inner_absolute_floor=floor,
                         missed_with_both_block_norms_below_inner_absolute_floor=len(block_limited) if run['mode']!='observer' else None,steps=r[-1]['step'],linear_solves=len(r),
                         reported_successes=len(successes),true_successes=sum(x['full_pass'] for x in r),
                         false_successes=len(false),negative_projected_squares=sum(x['projected_squared']<0 for x in r),
                         nonfinite_reported_norms=sum(x['solver_norm'] is None for x in r),
                         first_false_step=false[0]['step'] if false else None,
                         first_false_correction=false[0]['correction'] if false else None,
                         first_false_true_norm_over_tolerance=false[0]['full_norm']/false[0]['threshold'] if false else None,
                         worst_true_norm_over_tolerance=worst['full_norm']/worst['threshold'],worst_step=worst['step'],
                         max_true_over_tolerance_among_reported_successes=max((x['full_norm']/x['threshold'] for x in successes),default=None),
                         outer_iterations=sum(x['iterations'] for x in r),identical_native_vtus=run['identical_native_fields'],
                         accepted_fsi_history=run['strict']['measured']['passed'],native_accepted=run['strict']['native']['passed'],
                         peak_rss_kib=run['resource']['max_rss_kib'],cpu_s=run['resource']['user_seconds']+run['resource']['sys_seconds']))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--runs',type=Path)
    source.add_argument('--archive',type=Path)
    p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--write-archive',type=Path)
    a=p.parse_args()
    data=pack(a.runs) if a.runs else json.loads(lzma.decompress(a.archive.read_bytes()))
    rows=table(data)
    if not rows:raise ValueError('No matched completed measurements')
    with a.csv.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    if a.write_archive:
        a.write_archive.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
    print(len(rows),'complete trajectories;',sum(r['linear_solves'] for r in rows),'independent coupled linear residuals')


if __name__=='__main__':
    main()
