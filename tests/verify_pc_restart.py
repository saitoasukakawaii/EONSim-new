"""Semantic recipes preserve accepted restart state and fixed-fluid COO results."""
import argparse
import json
from pathlib import Path
from verify_schur import ROOT, fields, run
from verify_fluid_coo import compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable', required=True)
    p.add_argument('--mpiexec', required=True)
    p.add_argument('--work', type=Path, required=True)
    a = p.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    results = []
    for name in ('fluid/transient', 'fsi/rigid', 'fsi/elastic'):
        case = ROOT/'cases'/f'{name}.yaml'
        for ranks in (1, 2, 4):
            directory = a.work/(name.replace('/', '-')+f'-r{ranks}')
            directory.mkdir(exist_ok=True)
            partition = directory/'partition'
            run([a.executable, '-case', case, '-prepare', partition, '-parts', ranks])
            base = [a.mpiexec, '-n', ranks, a.executable, '-case', case, '-partition', partition]
            reference = directory/'direct.vtu'
            run(base+['-output', reference])
            expected = fields(reference, ranks)
            for recipe in ('physics', 'quantity', 'hybrid'):
                checkpoint = directory/(recipe+'-checkpoint')
                full, tail = directory/(recipe+'.vtu'), directory/(recipe+'-resumed.vtu')
                command = base+['-pc_recipe', recipe]
                if name.startswith('fluid/'):
                    command += ['-fluid_coo']
                log = run(command+['-output', full])
                (directory/(recipe+'.log')).write_text(log)
                run(command+['-stop_after', 3, '-checkpoint', checkpoint, '-output', directory/'partial.vtu'])
                resumed = run(command+['-restart', checkpoint, '-output', tail])
                (directory/(recipe+'-resumed.log')).write_text(resumed)
                direct_error = compare(expected, fields(full, ranks))
                restart_error = compare(fields(full, ranks), fields(tail, ranks))
                if name == 'fsi/elastic':
                    def solid(path):
                        return fields(path.with_stem(path.stem+'_solid'), ranks)
                    direct_error = max(direct_error, compare(solid(reference), solid(full)))
                    restart_error = max(restart_error, compare(solid(full), solid(tail)))
                results.append(dict(case=name, ranks=ranks, recipe=recipe, direct_error=direct_error,
                                    restart_error=restart_error, status='passed'))
                print(name, ranks, recipe, 'direct', direct_error, 'restart', restart_error, flush=True)
    (a.work/'results.json').write_text(json.dumps(results, indent=2)+'\n')


if __name__ == '__main__':
    main()
