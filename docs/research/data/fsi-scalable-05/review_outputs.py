"""Re-audit archived tube windows in place. Write separate supplementary receipts.

Example: review_outputs.py ~/workspace/fsi-scalable-05-runs /path/to/new/supplement --cases A B
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'fsi-scalable-02'))
from paired_tube import compare, digest, physical, read_mesh, save
from tube_checkpoint import verified_prefix
from scale_c import read_bindings, verify_baseline
from tube_protocol import archived_case, audit_corrections, compare_trajectories, output_manifest, select


def compatible(a,b):
    partition_matches=(a['partition']==b['partition'] and a['ranks']==b['ranks'])
    if 'scaling' in a:
        partition_matches=(a['scaling']['source_partition']==b['partition'] and b['ranks']==64)
    return (partition_matches and a.get('start_step',0)==b.get('start_step',0) and all(a[k]==b[k] for k in ('case','steps','inputs','binary')) and
            a.get('compiled_source',a['source'])==b.get('compiled_source',b['source']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--cases',nargs='+',choices=('A','B','C'),default=['A','B','C'])
    parser.add_argument('--steps',type=int,nargs='+')
    args=parser.parse_args()
    root=args.root.resolve(strict=True)
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE,text=True).strip()
    spec=digest(HERE/'output-fields-v2.1.json')
    entries=[]
    for p in sorted(root.rglob('window.json')):
        if 'source' in p.relative_to(root).parts or out in p.parents:
            continue
        row=json.loads(p.read_text())
        if row['case'] not in args.cases or (args.steps and row['steps'] not in args.steps):
            continue
        d=p.parent
        result=dict(run=str(d.relative_to(root)),original_qualification=row['qualification'],
                    window_sha256=digest(p),review_source=source,field_budget_sha256=spec)
        entries.append((d,row,result))
        try:
            if row.get('exit_code')!=0:
                raise ValueError('Original run failed: '+row.get('error','missing successful exit'))
            policy=select('CALIBRATED-v2',row['profile'])
            if row['policy']!=policy or row['log_sha256']!=digest(d/'solve.log'):
                raise ValueError('Original selection or log changed')
            if any(digest(d/n)!=sha for n,sha in row['inputs'].items()):
                raise ValueError('Original input changed')
            archived,origin,origin_sha=archived_case(row['case'])
            result['original_benchmark_sha256']=origin_sha
            archive_ranks=64 if 'scaling' in row else row['ranks']
            expected_names=['manifest.yaml',*(f'rank_{i}.h5' for i in range(archive_ranks))]
            frozen={n:origin['partition'][n] for n in expected_names}
            originals=row.get('scaling',{}).get('source_partition',row['partition'])
            if (originals!=frozen
                    or any(row['inputs'][n]!=origin['inputs'][n] for n in ('fluid.msh','solid.msh'))
                    or digest(archived/'case.json')!=origin['inputs']['case.json']):
                raise ValueError('Mesh, partition or physics differs from archived benchmark')
            expected=json.loads((archived/'case.json').read_text())
            if expected['fsi']['steps']!=row['steps']:
                expected['fsi'].update(steps=row['steps'],checkpoint_interval=row['steps'])
            if json.loads((d/'case.json').read_text())!=expected:
                raise ValueError('Window changes more than its declared step/checkpoint count')
            command=row['command']
            part=Path(command[command.index('-partition')+1])
            if any(digest(part/n)!=sha for n,sha in row['partition'].items()):
                raise ValueError('Original partition changed')
            if 'scaling' in row:
                evidence=row['scaling']
                if evidence!=verify_baseline(Path(evidence['baseline_directory']),
                        Path(evidence['reference_directory']),row,frozen):
                    raise ValueError('Scaling baseline identity changed')
                prep=d/'prepare'
                info=json.loads((prep/'run.json').read_text())
                if (info!=row['partition_preparation'] or info['exit_code']!=0 or info['log_sha256']!=digest(prep/'solve.log')
                        or info['inputs']!=row['inputs'] or info['binary']!=row['binary'] or info['parts']!=row['ranks']
                        or any(digest(prep/k)!=v for k,v in row['inputs'].items())
                        or row['rank_bindings']!=read_bindings((d/'solve.log').read_text(),row['ranks'])):
                    raise ValueError('Scaling preparation or binding receipt changed')
            start=row.get('start_step',0)
            if start:
                prefix=Path(row['prefix_segments'][-1]['directory'])
                partner=Path(row['prefix_pair_directory']) if row['profile']=='lu' else None
                previous,segments,generation=verified_prefix(prefix,row,d,partner)
                if (previous['steps']!=start or segments!=row['prefix_segments']
                        or str(generation)!=row['restart_generation'] or str(generation)!=command[command.index('-restart')+1]):
                    raise ValueError('Continuation does not match its declared lineage')
            audit=audit_corrections(d,row['steps'],row['ranks'],policy,start)
            result.update(linear={k:audit[k] for k in ('corrections','ksp_iterations','max_ratio','ksp','pc')},
                          outputs=output_manifest(d,row['steps'],row['ranks'],start), status='linear_window_only')
            if 'outputs' in row and result['outputs']!=row['outputs']:
                raise ValueError('Original output snapshot changed')
            if row['steps']>=4:
                meshes=[read_mesh(d/(n+'.msh')) for n in ('fluid','solid')]
                state=physical(d,'eon',meshes,row['steps'],row['ranks'],write=False,start_step=start)
                gates=compare(state,state)
                if not all(0<=v<=1 for v in gates.values()):
                    raise ValueError(f'Frozen individual physical conditions failed: {gates}')
                result.update(status='awaiting_independent_crosscheck',physical_gates=gates)
        except Exception as error:
            result.update(status='failed',error=str(error))
        print(result['run'],result['status'],result.get('error',''),flush=True)
    for d,row,result in entries:
        if result['status']!='awaiting_independent_crosscheck' or row['profile']=='lu':
            continue
        refs=[(p,r,s) for p,r,s in entries if r['profile']=='lu' and compatible(row,r) and
              s['status'] in ('awaiting_independent_crosscheck','independent_pair_passed')]
        if not refs:
            continue
        if len(refs)>1 and len({json.dumps(s['outputs'],sort_keys=True) for _,_,s in refs})!=1:
            result.update(status='failed',error='Multiple matching LU outputs differ')
            continue
        p,r,s=refs[0]
        try:
            linear=result['linear']
            if s['linear']['ksp']!='preonly' or s['linear']['pc']!='lu' or linear['ksp'] not in ('fgmres','pipefgmres') or linear['pc']=='lu':
                raise ValueError('Independent algorithms required')
            meshes=[read_mesh(d/(n+'.msh')) for n in ('fluid','solid')]
            start=row.get('start_step',0)
            if start:
                prior=json.loads((Path(row['prefix_segments'][-1]['directory'])/'window.json').read_text())
                if prior['reference_receipt']!=r['prefix_receipt']:
                    raise ValueError('Independent continuation prefixes differ')
            result['comparison']=compare_trajectories(d,p,row['steps'],meshes,(row['ranks'],r['ranks']),
                                                       select('CALIBRATED-v2',row['profile']),starts=(start,start))
            result.update(status='independent_pair_passed',reference=s['run'],reference_window_sha256=s['window_sha256'])
            s['status']='independent_pair_passed'
            s.setdefault('independent_windows',[]).append(result['window_sha256'])
        except Exception as error:
            result.update(status='failed',error=str(error))
        print(result['run'],result['status'],result.get('error',''),flush=True)
    if not entries:
        raise ValueError('No matching archived windows')
    index={}
    for d,row,result in entries:
        path=out/d.relative_to(root)/'review.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        save(path,result)
        index[result['run']]=dict(status=result['status'],receipt_sha256=digest(path),
                                 original_window_sha256=result['window_sha256'])
    save(out/'supplement.json',dict(source=source,field_budget_sha256=spec,runs=index))


if __name__=='__main__':
    main()
