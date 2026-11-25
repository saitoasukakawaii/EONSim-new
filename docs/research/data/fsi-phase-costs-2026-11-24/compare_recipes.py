"""Audit named field splits against direct solutions, including the actual PETSc tree and time-step residual."""
import argparse
import csv
import hashlib
import json
import lzma
from pathlib import Path
import re
import statistics

from compare import accepted_outcomes
from profile_case import digest, events, field_diff, fields


def pack(root):
    sources=[('production',p) for p in sorted((root/'pc-recipes').glob('*/results.json'))]
    sources.append(('prototype',root/'unified-velocity-pilot/results.json'))
    records=[]
    mesh=case=None
    for version,p in sources:
        report=json.loads(p.read_text())
        checks=[digest(p.parent/file) for file in ('fluid.msh','solid.msh')]
        cfg=(p.parent/'case.json').read_bytes()
        if mesh is None:mesh,case=checks,cfg
        if checks!=mesh or checks!=report['mesh_sha256'] or cfg!=case:raise ValueError('Changed numerical problem')
        controls={}
        for r in report['runs']:
            ranks,pc,rep,logging=(r[k] for k in ('ranks','pc','repeat','logging'))
            directory=p.parent/f'r{ranks}-{pc}-{rep}-log{int(logging)}'
            log=(directory/'solve.log').read_text()
            actual=accepted_outcomes(directory,report['steps'])
            if actual['linear_iterations']!=r['linear_iterations']:raise ValueError('Stale iteration count')
            tree={}
            for line in log.splitlines():
                if not line.startswith('solver_node rank=0 '):continue
                node=dict(re.findall(r'(\w+)=([^\s]+)',line))
                if node['path'] in tree and tree[node['path']]!=[node['prefix'],node['ksp'],node['pc']]:
                    raise ValueError('Solver tree changed between accepted steps')
                tree[node['path']]=[node['prefix'],node['ksp'],node['pc']]
            if 'root' not in tree:raise ValueError('Missing PETSc solver tree')
            if pc!='direct':
                expected={'physics':'fieldsplit_fluid_','quantity':'fieldsplit_velocity_',
                          'hybrid':'fieldsplit_dynamics_','coupled_velocity':'fieldsplit_dynamics_'}[pc]
                if tree['root/field0'][0]!=expected:raise ValueError('Unexpected outer block')
                if pc in ('hybrid','coupled_velocity'):
                    branch=tree['root/field0/field0']
                    if branch[2]!=('gamg' if pc=='coupled_velocity' else 'fieldsplit'):
                        raise ValueError('Unexpected velocity inner preconditioner')
            if ranks not in controls:
                direct=p.parent/f'r{ranks}-direct-0-log0'
                controls[ranks]=[fields(direct/('tube'+suffix+'.vtu'),ranks) for suffix in ('','_solid')]
            delta=[field_diff(ref,fields(directory/('tube'+suffix+'.vtu'),ranks)) for ref,suffix in zip(controls[ranks],('','_solid'))]
            if max(delta)>2e-8:raise ValueError(f'Direct and preconditioned fields disagree: {delta}')
            entry=dict(version=version,series=p.parent.name,ranks=ranks,pc=pc,repeat=rep,logging=logging,
                       binary_sha256=report['binary_sha256'],log_sha256=digest(directory/'solve.log'),tree=tree,
                       direct_field_differences=delta,wall_seconds=r['wall_seconds'],dofs=r['dofs'],nnz=r['nnz'],**actual)
            if logging:
                actual_events=events(directory/'events.csv',ranks,report['steps'],report['cells'])
                if r['events']!=actual_events:raise ValueError('PETSc event history differs from original receipt')
                entry['events']=actual_events
            records.append(entry)
    return dict(mesh_sha256=mesh,case=json.loads(case),case_sha256=hashlib.sha256(case).hexdigest(),measurements=records)


def table(data):
    rows=[]
    records=data['measurements']
    for version,ranks,pc in sorted({(r['version'],r['ranks'],r['pc']) for r in records}):
        group=[r for r in records if (r['version'],r['ranks'],r['pc'])==(version,ranks,pc)]
        on=[r for r in group if r['logging']]
        off=[r for r in group if not r['logging']]
        if len(on)!=len(off) or not on:raise ValueError('Missing logging control')
        counts={r['linear_iterations'] for r in group}
        if len(counts)!=1:raise ValueError('Inconsistent total Krylov count')
        rows.append(dict(version=version,ranks=ranks,pc=pc,unlogged_samples=len(off),dofs=off[0]['dofs'],
                         linear_iterations=counts.pop(),median_wall_s=statistics.median(r['wall_seconds'] for r in off),
                         median_max_rank_pc_setup_s=statistics.median(r['events']['PCSetUp']['max_rank_seconds'] for r in on),
                         median_max_rank_pc_apply_s=statistics.median(r['events']['PCApply']['max_rank_seconds'] for r in on),
                         max_fluid_field_difference=max(r['direct_field_differences'][0] for r in group),
                         max_solid_field_difference=max(r['direct_field_differences'][1] for r in group),
                         max_final_residual=max(r['largest_accepted_residual'] for r in group)))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--runs',type=Path);inputs.add_argument('--archive',type=Path)
    parser.add_argument('--write-archive',type=Path)
    parser.add_argument('--csv',type=Path,required=True)
    args=parser.parse_args()
    data=pack(args.runs) if args.runs else json.loads(lzma.decompress(args.archive.read_bytes()))
    rows=table(data)
    if args.write_archive:args.write_archive.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
    with args.csv.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(len(data['measurements']),'complete, field-checked solves;',len(rows),'configurations')


if __name__=='__main__':main()
