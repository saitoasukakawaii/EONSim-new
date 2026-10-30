"""Accepted-state checkpoint continuation for fluid, solid and both FSI modes."""
import argparse, re, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
p=argparse.ArgumentParser(); p.add_argument('--executable',type=Path,required=True); p.add_argument('--mpiexec',required=True)
p.add_argument('--root',type=Path,required=True); p.add_argument('--work',type=Path,required=True)
a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
def run(args,ok=True):
    r=subprocess.run([str(x) for x in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    if (r.returncode==0)!=ok: raise RuntimeError(r.stdout)
    return r.stdout
def compare(x,y,ranks,solid=False):
    for suffix in (('','_solid') if solid else ('',)):
        for rank in range(ranks):
            tail=suffix+('' if ranks==1 else f'_rank{rank}')+'.vtu'
            one=ET.parse(x.parent/(x.stem+tail)); two=ET.parse(y.parent/(y.stem+tail))
            for d,e in zip(one.findall('.//DataArray'),two.findall('.//DataArray')):
                u,v=list(map(float,d.text.split())),list(map(float,e.text.split()))
                assert len(u)==len(v)
                assert max((abs(i-j) for i,j in zip(u,v)),default=0)<2e-8
cases=['fluid/transient','solid/unload','fsi/rigid','fsi/elastic','fsi/hyperelastic']
for name in cases:
    case=a.root/'cases'/f'{name}.yaml'
    for ranks in (1,2):
        work=a.work/(name.replace('/','_')+str(ranks)); work.mkdir(exist_ok=True)
        partition=work/'partition'; checkpoint=work/'checkpoint'
        run([a.executable,'-case',case,'-prepare',partition,'-parts',ranks])
        prefix=([a.mpiexec,'-n',ranks] if ranks>1 else [])+[a.executable,'-case',case,'-partition',partition]
        full=work/'full.vtu'; resumed=work/'resumed.vtu'
        run(prefix+['-output',full])
        run(prefix+['-checkpoint',checkpoint,'-stop_after',3,'-output',work/'partial.vtu'])
        text=run(prefix+['-restart',checkpoint,'-output',resumed])
        compare(full,resumed,ranks,name in ('fsi/elastic','fsi/hyperelastic'))
        assert not re.search(r'^(fluid|solid|fsi)_step=[123]\s',text,re.MULTILINE)
        if name=='fsi/rigid' and ranks==2:
            generation=checkpoint/(checkpoint/'current').read_text().split()[1]
            rankfile=generation/'state_rank1.h5'; missing=generation/'state_rank1.hidden'
            rankfile.rename(missing)
            run(prefix+['-restart',checkpoint],False)
            missing.rename(rankfile)
            changed=work/'changed.yaml'
            changed.write_text(case.read_text().replace('mesh: cube.msh',f'mesh: {(case.parent/"cube.msh").resolve()}').replace('pressure: 1','pressure: 2'))
            run([a.mpiexec,'-n',2,a.executable,'-case',changed,'-partition',partition,'-restart',checkpoint],False)
            run([a.executable,'-case',case,'-restart',checkpoint],False)
        print(name,ranks,'checkpoint continuation passed')
# Same coupled problem: direct and FGMRES block solve must agree on 1/2/4 ranks.
case=a.root/'cases/fsi/hyperelastic.yaml'
for ranks in (1,2,4):
    work=a.work/f'block{ranks}'; work.mkdir(exist_ok=True); partition=work/'partition'
    run([a.executable,'-case',case,'-prepare',partition,'-parts',ranks])
    prefix=([a.mpiexec,'-n',ranks] if ranks>1 else [])+[a.executable,'-case',case,'-partition',partition]
    direct=work/'direct.vtu'; block=work/'block.vtu'
    run(prefix+['-output',direct])
    report=run(prefix+['-output',block,'-block_pc','-solver_report'])
    assert 'ksp=fgmres pc=fieldsplit' in report
    compare(direct,block,ranks,True)
    print('block FGMRES',ranks,'passed')
print('restart and block solver verification passed')
