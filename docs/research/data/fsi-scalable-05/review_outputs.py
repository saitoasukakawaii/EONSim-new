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
from tube_protocol import audit_corrections, compare_trajectories, output_manifest, select


def compatible(a,b):
    return (all(a[k]==b[k] for k in ('case','steps','inputs','partition','ranks','binary')) and
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
            command=row['command']
            part=Path(command[command.index('-partition')+1])
            if any(digest(part/n)!=sha for n,sha in row['partition'].items()):
                raise ValueError('Original partition changed')
            audit=audit_corrections(d,row['steps'],row['ranks'],policy)
            result.update(linear={k:audit[k] for k in ('corrections','ksp_iterations','max_ratio','ksp','pc')},
                          outputs=output_manifest(d,row['steps'],row['ranks']), status='linear_window_only')
            if 'outputs' in row and result['outputs']!=row['outputs']:
                raise ValueError('Original output snapshot changed')
            if row['steps']>=4:
                meshes=[read_mesh(d/(n+'.msh')) for n in ('fluid','solid')]
                state=physical(d,'eon',meshes,row['steps'],row['ranks'],write=False)
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
            result['comparison']=compare_trajectories(d,p,row['steps'],meshes,(row['ranks'],r['ranks']),
                                                       select('CALIBRATED-v2',row['profile']))
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
