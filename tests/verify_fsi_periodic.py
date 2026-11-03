"""Real MPI checkpoint continuation and conservative periodic nonconvergence status."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fsi_field_cycles import read_snapshot,difference
from verify_fsi_inlet import Runner


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();a.work=a.work/f'run-{time.time_ns()}';a.work.mkdir(parents=True)
    script=Path(__file__).resolve().parents[1]/'scripts/study_fsi_periodic.py'
    base=[sys.executable,str(script),'--executable',a.executable,'--mpiexec',a.mpiexec,'--dt','.005']
    def run(name,ranks,cycles,resume=False,extra=(),expected='Maximum cycles reached'):
        path=a.work/name
        cmd=base+['--work',str(path),'--ranks',str(ranks),'--cycles',str(cycles)]+(['--resume'] if resume else [])+list(extra)
        result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
        (a.work/(name+f'-{cycles}-{len(extra)}.log')).write_text(result.stdout)
        if result.returncode==0 or expected not in result.stdout:raise RuntimeError(result.stdout[-4000:])
        return path
    def fields(work,cycle,solid,ranks):
        name=f'cycle{cycle}_restart{(cycle-1)*20}_step{cycle*20}'+('_solid' if solid else '')+('.pvtu' if ranks>1 else '.vtu')
        return read_snapshot(work/name,solid)
    for ranks in (1,2,4):
        work=run(f'r{ranks}',ranks,3)
        receipt=json.loads((work/'periodic-result.json').read_text())
        assert not receipt['converged'] and receipt['metrics'][-1]['consecutive_passes']==0
        assert len(list((work/'checkpoint').glob('generation_*')))==3
        for solid in (False,True):
            scales={'velocity':1,'displacement':1} if solid else {'velocity':1,'pressure':1,'mesh_displacement':1}
            errors=difference(fields(a.work/'r1',3,solid,1),fields(work,3,solid,ranks),scales)
            assert max(errors.values())<2e-9,errors
    work=a.work/'r2';before=hashlib.sha256((work/'fluid.msh').read_bytes()).hexdigest()
    run('r2',2,4,True,('--n','4'),expected='Study definition changed')
    assert hashlib.sha256((work/'fluid.msh').read_bytes()).hexdigest()==before
    resumed=run('r2',2,4,True)
    continuous=run('continuous',2,4)
    for solid in (False,True):
        scales={'velocity':1,'displacement':1} if solid else {'velocity':1,'pressure':1,'mesh_displacement':1}
        errors=difference(fields(resumed,4,solid,2),fields(continuous,4,solid,2),scales)
        assert max(errors.values())<2e-9,errors
    direct=Runner(a.executable,a.mpiexec,a.work/'physical-continuous')
    for name in ('fluid.msh','solid.msh'):shutil.copy(work/name,direct.work/name)
    cfg=json.loads((continuous/'periodic-result.json').read_text())['config']
    direct.solve('direct',cfg,2)
    for solid in (False,True):
        suffix='_solid' if solid else ''
        scales={'velocity':1,'displacement':1} if solid else {'velocity':1,'pressure':1,'mesh_displacement':1}
        errors=difference(fields(resumed,4,solid,2),read_snapshot(direct.work/('direct'+suffix+'.pvtu'),solid),scales)
        assert max(errors.values())<2e-9,errors
    # A requested endpoint must publish even when it is off the regular cadence.
    cfg['fsi']['checkpoint_interval']=100
    checkpoint=direct.work/'off-cadence'
    direct.solve('endpoint',cfg,2,['-checkpoint',checkpoint,'-stop_after',3])
    generation=(checkpoint/'current').read_text().split()[1]
    assert int((checkpoint/generation/'manifest').read_text().split()[2])==3
    bad=dict(cfg);bad['fsi']=dict(cfg['fsi'],checkpoint_interval=0)
    direct.solve('bad-cadence',bad,2,fail='fsi.checkpoint_interval must be positive')
    print('1/2/4 rank fields, nonconvergence, definition rejection and cycle continuation passed')


if __name__=='__main__':main()
