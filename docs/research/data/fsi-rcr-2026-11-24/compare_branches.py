"""Replay the two-outlet flow, pressure and storage measurements with explicit normalizations."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys
import tempfile

from branch_study import analyse
from branch_external import prepare
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from svfsi_history import check_convergence


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history(path):
    with path.open() as stream:
        return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]


def rejected_external(root, groups):
    rejected = []
    for group in groups:
        for logfile in sorted((root / group).glob('*.log')):
            case = logfile.with_suffix('')
            if not case.is_dir() or (case / 'report.json').is_file():
                continue
            output = logfile.read_text()
            if 'Traceback (most recent call last):' not in output:
                continue
            errors = [line for line in output.splitlines() if line.startswith(('ValueError:', 'AssertionError:', 'EONSim rank 0:'))]
            record = dict(group=group, case=case.name, errors=errors, driver_log_sha256=digest(logfile))
            path = case / 'sv/1-procs/histor.dat'
            if path.exists():
                log = path.read_text()
                lines = log.splitlines()
                record['history_sha256'] = digest(path)
                record['solver_errors'] = [line.strip() for line in lines if line.strip().startswith('ERROR:')]
                record['last_equation_rows'] = {}
                for eq in ('FS', 'MS', 'NS'):
                    rows = [line.strip() for line in lines if re.match(r'^\s*' + eq + r'\s+\d+-', line)]
                    if rows:
                        record['last_equation_rows'][eq] = rows[-1]
            rejected.append(record)
    return rejected


def pack(root,binaries,helpers):
    external=[]
    groups = ('cross-branched', 'cross-branched-controls', 'cross-branch-rigid', 'cross-branch-clamp')
    for group in groups:
        for path in sorted((root/group).glob('*/report.json')):
            case=path.parent;r=json.loads(path.read_text())
            if (r['mesh_sha256']!=[digest(case/'eon'/f'{name}.msh') for name in ('fluid','solid')]
                    or r['sv_deck']!=digest(case/'sv/svFSI.inp')):
                raise ValueError('Mesh or native equations changed in '+str(case))
            cfg=json.loads((case/'eon/junction.json').read_text())
            clamped=any(bc['tag']==14 and sorted(bc['components'])==[0,1,2] for bc in cfg['fsi']['domains']['solid_constraints'])
            condition='clamped' if clamped else 'elastic'
            equations=set(r['sv_convergence']);rigid=(equations=={'NS'})
            variant=binaries[r['sv_binary']]
            if (r.get('wall_condition',condition)!=condition or r.get('sv_variant',variant)!=variant or
                    (rigid and not clamped) or equations not in ({'NS'},{'FS','MS'})):
                raise ValueError('Inconsistent wall condition, external binary or audited equations')
            r.update(wall_condition=condition,sv_variant=variant,native_equations=sorted(equations))
            with tempfile.TemporaryDirectory() as temp:
                expected=Path(temp)/'native'
                prepare(case/'eon',expected,cfg,helpers,rigid)
                for p in expected.iterdir():
                    if p.read_bytes()!=(case/'sv'/p.name).read_bytes():raise ValueError('Changed native '+p.name+' in '+case.name)
            table=history(case/'paired.csv')
            eon=history(case/'eon/junction.csv')
            raw=(case/'sv/1-procs/RCR.dat').read_text().splitlines()
            logs=(case/'sv/1-procs/histor.dat').read_text()
            if not len(table)==len(raw)==len(eon)==r['steps']:raise ValueError('Incomplete port histories')
            for eq,value in r['sv_convergence'].items():
                if list(check_convergence(logs,r['steps'],eq))!=value:raise ValueError('Changed external convergence')
            for i,(row,local,line) in enumerate(zip(table,eon,raw),1):
                t,pc2,p2,pc3,p3,q2,q3=map(float,line.split())
                if not (math.isclose(t,i*r['dt'],rel_tol=2e-7) and abs(row['time']-local['time'])<1e-13 and
                        [row[k] for k in ('sv_q2','sv_q3','sv_p2','sv_p3')]==[q2,q3,p2,p3]):
                    raise ValueError('Native port mapping or evaluation time changed')
                for tag in (2,3):
                    if [row[f'eon_q{tag}'],row[f'eon_p{tag}']]!=[local[f'endpoint_rcr_{k}_{tag}'] for k in ('flow','pressure')]:
                        raise ValueError('EONSim port mapping changed')
            external.append(dict(case=case.name,group=group,report=r,history=table,
                    hashes={p:digest(case/p) for p in ('paired.csv','eon/junction.json','eon/junction.csv','sv/1-procs/RCR.dat','sv/1-procs/histor.dat')}))
    storage=[]
    for path in sorted((root/'branched-qualification').glob('*/report.json')):
        case=path.parent;r=json.loads(path.read_text())
        if not r.get('milestones') or len(r.get('history_sha256',{}))!=2:
            raise ValueError('Run requires a complete storage and circuit audit: '+case.name)
        for name,sha in r['history_sha256'].items():
            if sha!=digest(case/name):raise ValueError('Changed storage history in '+case.name)
        cfg=json.loads((case/'branched.json').read_text())
        period=cfg['fsi']['inlet']['flow_rate']['period'];rows=history(case/'branched.csv')
        calculated=analyse(rows,r['models'],period,r['dt'],r['waveform']=='periodic',r['geometry']['reference_fluid_volume'])
        if json.loads(json.dumps(calculated))!=r['terminal']:raise ValueError('Cannot reproduce terminal audit in '+case.name)
        n=round(calculated['terminal_window_s']/r['dt'])
        cols=['time','endpoint_inlet_flow','endpoint_wall_flux','endpoint_volume']
        cols.extend(f'endpoint_rcr_{kind}_{tag}' for tag in (2,3) for kind in ('flow','pressure'))
        storage.append(dict(case=case.name,report=r,terminal_cycles=[{k:row[k] for k in cols} for row in rows[-2*n:]],
                            deck_sha256=digest(case/'branched.json')))
    return dict(external=external,storage=storage,rejected_external=rejected_external(root,groups))


def tables(data):
    external=[]
    for item in data['external']:
        r=item['report'];wave=item['history'];peak=r['amplitude']
        if peak<=0 or not all(math.isfinite(x) for w in wave for x in w.values()):raise ValueError('Invalid port waveform')
        for k,tag in enumerate((2,3)):
            q,p,rq,rp=(f'{code}_{field}{tag}' for code,field in (('eon','q'),('eon','p'),('sv','q'),('sv','p')))
            dq=max(abs(w[q]-w[rq]) for w in wave);dp=max(abs(w[p]-w[rp]) for w in wave)
            ref_peak=max(abs(w[rq]) for w in wave)
            if [dq,dp,ref_peak]!=[r[key][k] for key in ('max_outlet_flow_difference','max_outlet_pressure_difference','peak_sv_outlet_flow')]:
                raise ValueError('Port errors cannot be reproduced in '+item['case'])
            frames=r['fields']
            storage=lambda code:max(abs(v[code]['flux'][0]-sum(v[code]['flux'][1:])) for v in frames)/peak
            external.append(dict(case=item['case'],wall=r['wall_condition'],sv_variant=r['sv_variant'],grid=r['refinement'],
                period_s=r['period'],steps_per_cycle=round(r['period']/r['dt']),tag=tag,imposed_peak_m3_s=peak,
                sv_port_peak_m3_s=ref_peak,max_q_difference_m3_s=dq,max_q_difference_pct_inlet=100*dq/peak,
                max_q_difference_pct_native_port=100*dq/ref_peak,max_pressure_difference_pa=dp,
                max_native_capacitor_replay_pa=r['native_capacitor_recurrence_error'][k],
                saved_frame_eon_net_influx_pct_inlet=100*storage('eonsim'),saved_frame_sv_net_influx_pct_inlet=100*storage('svfsi')))
    long=[]
    for item in data['storage']:
        r=item['report'];end=r['terminal']
        for m in r['milestones']:
            if not math.isfinite(m['mean_inlet']) or m['mean_inlet']<=0:raise ValueError('Invalid mean inlet')
            long.append(dict(case=item['case'],grid=r['geometry']['refinement'],waveform=r['waveform'],dt=r['dt'],
                time=m['time'],mean_inlet=m['mean_inlet'],mean_outlet=m['mean_outlet'],mean_wall_flux=m['mean_wall_flux'],
                mean_outlet_pct_inlet=100*m['mean_outlet']/m['mean_inlet'],volume_gain_m3=m['volume_gain'],
                mean_q2=m['mean_port_flow']['2'],mean_q3=m['mean_port_flow']['3']))
        if end['min_endpoint_fluid_j']<=0 or end['min_endpoint_solid_j']<=0:
            raise ValueError('Invalid material geometry')
    return external,long


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--runs',type=Path);source.add_argument('--archive',type=Path)
    parser.add_argument('--write-archive',type=Path)
    parser.add_argument('--reference-scripts',type=Path);parser.add_argument('--native-executable',type=Path)
    parser.add_argument('--zero-executable',type=Path)
    parser.add_argument('--ports-csv',type=Path,required=True);parser.add_argument('--storage-csv',type=Path,required=True)
    args=parser.parse_args()
    if args.runs:
        if not all((args.reference_scripts,args.native_executable,args.zero_executable)):
            parser.error('Reading raw runs requires the pinned reference scripts and both actual native and zero-grad-div binaries')
        sys.path.append(str(args.reference_scripts.resolve()))
        import compare_svfsi_wall as helpers
        data=pack(args.runs,{digest(args.native_executable):'native',digest(args.zero_executable):'grad-div-off'},helpers)
    else:
        data=json.loads(lzma.decompress(args.archive.read_bytes()))
    ports,storage=tables(data)
    for path,rows in ((args.ports_csv,ports),(args.storage_csv,storage)):
        if not rows:raise ValueError('No qualified measurements for '+path.name)
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    if args.write_archive:
        target=args.write_archive.with_suffix('.partial')
        target.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
        target.replace(args.write_archive)
    print(len(data['external']),'paired waveforms;',len(data['storage']),'storage transients;',len(storage),'milestones')


if __name__=='__main__':main()
