"""Recompute the archived Womersley evidence from an extracted raw.tar.xz."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[3]/'scripts'))
import audit_womersley_fields as fields
import compare_svfsi_womersley as external
import compare_womersley_runs as compare
import study_rigid_tube as tube
import study_womersley as study


def replay(root, field_audits=False):
    dataset = json.loads((root/'dataset.json').read_text())
    runs = root/'runs'
    result = dict(flow={name:study.analyze(runs/name) for name in dataset['runs']})
    result['time'] = {name:compare.time_refinement([runs/n for n in family])
                      for name,family in dataset['time'].items()}
    if dataset.get('stabilization'):
        result['stabilization'] = {name:compare.endpoint_stabilization(runs/name)
                                   for name in dataset['stabilization']}
    result['mpi'] = {str(n):compare.mpi_comparison(runs/dataset['reference'],runs/case,n)
                     for case,n in dataset['mpi'].items()}
    result['svfsi'] = {name:external.compare(runs/case,root/'svfsi'/name)
                       for name,case in dataset['svfsi'].items()}
    result['legacy_restart'] = {}
    for n in (1,2):
        states = [tube.fields(root/'legacy'/label,n) for label in ('original','restored')]
        if states[0].keys()!=states[1].keys():
            raise ValueError('Legacy checkpoint comparison lost mesh IDs')
        error = max(abs(a-b) for node,row in states[0].items() for a,b in zip(row,states[1][node]))
        result['legacy_restart'][str(n)] = dict(nodes=len(states[0]),max_field_difference=error)
    if field_audits:
        from compare_svfsi_womersley_fields import compare_fields
        result['field'] = {}
        for name,spec in dataset['field'].items():
            case = runs/spec['case']
            result['field'][name] = fields.audit(case,case/spec['snapshot'],1,spec['quadrature'])
        result['svfsi_field'] = {name:compare_fields(runs/case,root/'svfsi'/name)
                                 for name,case in dataset['svfsi'].items()}
    return result


def check_values(actual,expected,path='results'):
    if isinstance(actual,dict) and isinstance(expected,dict) and actual.keys()==expected.keys():
        for key,value in actual.items():
            check_values(value,expected[key],f'{path}.{key}')
    elif isinstance(actual,list) and isinstance(expected,list) and len(actual)==len(expected):
        for i,(a,e) in enumerate(zip(actual,expected)):
            check_values(a,e,f'{path}[{i}]')
    elif isinstance(actual,float) and isinstance(expected,(int,float)):
        if not math.isclose(actual,expected,rel_tol=2e-10,abs_tol=2e-13):
            raise ValueError(f'{path}: {actual} differs from {expected}')
    elif actual!=expected:
        raise ValueError(f'{path}: values differ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path,help='Extracted archive root containing dataset.json')
    parser.add_argument('--fields',action='store_true',help='Also integrate the saved VTUs, requires Python VTK for svFSI')
    parser.add_argument('--output',type=Path,help='Write the recomputed JSON')
    parser.add_argument('--verify',action='store_true',help='Check input digests and compare to results.json')
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads((HERE/'manifest.json').read_text())
        for name,record in manifest['files'].items():
            data = (args.root/name).read_bytes()
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise ValueError('Archived input digest differs: '+name)
    values = replay(args.root,args.fields)
    if args.verify:
        expected = json.loads((HERE/'results.json').read_text())
        if not args.fields:
            expected = {k:v for k,v in expected.items() if k not in ('field','svfsi_field')}
        check_values(values,expected)
        print('Recorded values reproduced.',file=sys.stderr)
    output = json.dumps(values,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if args.output:
        args.output.write_text(output)
    else:
        print(output,end='')


if __name__=='__main__':
    main()
