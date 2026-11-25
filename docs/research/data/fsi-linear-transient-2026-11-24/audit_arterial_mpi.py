"""Audit an independently launched, completed prefix of the 32-step arterial case."""
import argparse
import json
from pathlib import Path
import sys

from compare_arterial_ksp import digest, fields_at, parse, read_mesh, residual_shares


def audit(directory, reference, case, executable):
    receipt = json.loads((directory/'result.json').read_text())
    output = directory/'solve.log'
    ranks = receipt['expected_ranks']
    steps = receipt['accepted_steps']
    expected_exits = [dict(rank=i, exit_code=0) for i in range(ranks)]
    if (ranks < 1 or steps not in range(4, 33, 4) or receipt['ranks'] != expected_exits
            or receipt['launcher_exit'] != 0 or not receipt['clean_exit'] or not receipt['application_reported_success']):
        raise ValueError('A complete saved phase and successful individual rank and launcher exits are required')
    if receipt['log_sha256'] != digest(output) or receipt['executable_sha256'] != digest(executable):
        raise ValueError('The solve log or executable differs from the exit receipt')

    cfg = json.loads(case.read_text())
    direct = json.loads((reference/'case.json').read_text())
    source = [case.parent/cfg['mesh'], case.parent/cfg['fsi']['domains']['solid_mesh']]
    meshes = [reference/direct['mesh'], reference/direct['fsi']['domains']['solid_mesh']]
    if any(digest(p) != digest(q) for p, q in zip(source, meshes)):
        raise ValueError('The direct solution used different volume meshes')
    cfg['mesh'] = direct['mesh']
    cfg['fsi']['domains']['solid_mesh'] = direct['fsi']['domains']['solid_mesh']
    if cfg['fsi']['steps'] != steps or direct['fsi']['steps'] != 32:
        raise ValueError('Run length and case disagree')
    cfg['fsi']['steps'] = 32
    if cfg != direct:
        raise ValueError('The two solvers used different physical inputs')

    result = parse(output.read_text(), True, ranks, steps)
    corrections = result['corrections']
    for row in corrections:
        residual_shares(row, result['equation_rows'])
    ratios = [r['norm']/max(1e-23, 1e-10*r['rhs']) for r in corrections]
    fields = fields_at(directory, reference, [read_mesh(p) for p in meshes], ranks, steps)
    return dict(process=receipt, case_sha256=digest(case), reference_case_sha256=digest(reference/'case.json'),
                meshes_sha256=[digest(p) for p in meshes], equation_rows=result['equation_rows'],
                placement=result['placement'], accepted_outer_iterations=sum(r['linear_iterations'] for r in result['solver']),
                within_target=sum(v <= 1 for v in ratios), largest_ratio=max(ratios), residual_over_target=ratios,
                **fields)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'reference', 'case', 'executable', 'reference-scripts', 'output'):
        cli.add_argument('--'+name, type=Path, required=True)
    args = cli.parse_args()
    sys.path.append(str(args.reference_scripts.resolve()))
    data = audit(args.work, args.reference, args.case, args.executable)
    args.output.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    print(data['process']['accepted_steps'], data['within_target'], len(data['residual_over_target']), data['largest_ratio'])


if __name__ == '__main__':
    main()
