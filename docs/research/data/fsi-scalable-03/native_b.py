"""Screen native FSILS row/column scaling against the archived B20 direct trajectory."""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'fsi-scalable-02'))
from paired_tube import compare, digest, physical, read_mesh, run, save


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for key in ('archive','output','binary','mpiexec'):
        cli.add_argument(key,type=Path)
    args = cli.parse_args()
    archive, root = args.archive.resolve(), args.output.resolve()
    old = json.loads((archive/'summary.json').read_text())
    ranks, steps = old['ranks'], old['steps']
    if (steps!=20 or ranks!=32 or not os.getenv('SLURM_JOB_ID') or len(os.sched_getaffinity(0))!=ranks
            or digest(args.binary)!=old['binaries']['svfsi']):
        cli.error('requires archived B20 native binary and the same 32-core allocation')
    root.mkdir(parents=True,exist_ok=False)
    row = dict(external='OPEN', slurm=os.environ['SLURM_JOB_ID'], affinity=sorted(os.sched_getaffinity(0)),
               archived_summary=digest(archive/'summary.json'), binaries=old['binaries'], inputs={})
    try:
        for relative, sha in old['inputs'].items():
            if relative.startswith('svfsi/'):
                path = archive/'prepared'/relative
                if digest(path)!=sha:
                    raise ValueError(f'Archived input changed: {relative}')
                shutil.copyfile(path,root/path.name)
                row['inputs'][path.name] = sha
        deck = root/'svFSI.inp'
        source = deck.read_text()
        marker = 'LS type: GMRES {'
        if source.count(marker)!=1:
            raise ValueError('Expected one native FSI GMRES block')
        deck.write_text(source.replace(marker,marker+'\n      Preconditioner: row-column-scaling'))
        row['inputs'][deck.name] = digest(deck)
        os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        command = [str(args.mpiexec.resolve()),'--map-by','core','--bind-to','core','-n',str(ranks),
                   str(args.binary.resolve()),'svFSI.inp']
        run(root,command,row,780,140*2**30)
        ref = archive/'0-eon'
        original = json.loads((ref/'run.json').read_text())
        if original['exit_code']!=0 or original['log_sha256']!=digest(ref/'solve.log'):
            raise ValueError('Invalid reference execution')
        for name in ('case.json','fluid.msh','solid.msh'):
            if digest(ref/name)!=old['inputs']['eon/'+name]:
                raise ValueError('Archived EONSim input changed')
        meshes = [read_mesh(ref/(s+'.msh')) for s in ('fluid','solid')]
        checks = compare(physical(ref,'eon',meshes,steps,ranks,write=False),
                         physical(root,'svfsi',meshes,steps,ranks))
        row['normalized_gates'] = checks
        if not all(math.isfinite(v) and v<=1 for v in checks.values()):
            raise ValueError('Frozen physical budget exceeded')
        row['external'] = 'passed-20-step-screen'
    except Exception as error:
        row.update(external='FAILED',error=str(error))
        raise
    finally:
        save(root/'screen.json',row)


if __name__=='__main__':
    main()
