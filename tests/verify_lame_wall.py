"""Pressure compliance and an exactly representable hydrostatic wall patch."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import study_lame_wall as wall
import study_rigid_tube as tube


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--mpiexec',required=True)
    args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(dir=args.work))
    executable=args.executable.resolve()
    print('Evidence in',work,flush=True)
    wall.solve(work/'bore',executable,args.mpiexec,1,48,4,6,wall.PRESSURE)
    result=wall.analyze(work/'bore')
    assert result['passed'] and result['relative_work_energy_residual']<1e-10, result
    # Equal pressure on both curved surfaces gives an affine contraction on a
    # polygon too. The axial rollers supply the plane-strain axial reaction.
    patch=work/'patch'
    wall.make_case(patch,24,2,3,wall.PRESSURE)
    cfg=json.loads((patch/'case.json').read_text())
    next(b for b in cfg['solid']['boundaries'] if b['tag']==14)['value']=wall.PRESSURE
    (patch/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
    nodes,_,_=tube.read_mesh(patch/cfg['mesh'])
    strain=-(1+wall.POISSON)*(1-2*wall.POISSON)*wall.PRESSURE/wall.YOUNG
    command=[executable,'-case','case.json']
    tube.run([*command,'-prepare','parts','-parts',2],patch,'prepare.log')
    for ranks in (1,2):
        launch=command if ranks==1 else [args.mpiexec,'-n',ranks,*command,'-partition','parts']
        tube.run(launch,patch,f'solve-{ranks}.log')
        state=wall.displacements(patch,ranks,nodes)
        error=max(abs(v-ref) for n,(x,y,z) in nodes.items()
                  for v,ref in zip(state[n],(0.,strain*y,strain*z)))
        assert error<1e-12, (ranks,error)
        print('Hydrostatic patch',ranks,'rank(s), max displacement error',error)


if __name__=='__main__':
    main()
