"""Stage pressure, accepted flux history and MPI restart for a rigid tube."""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import study_womersley as study
import study_rigid_tube as tube
from audit_womersley_fields import audit


def compare_states(actual, expected):
    assert actual.keys() == expected.keys()
    error = max(abs(x-y) for n in actual for x,y in zip(actual[n], expected[n]))
    assert error < 2e-9, error
    return error


def compare_history(actual, expected):
    assert actual.keys() == expected.keys()
    for step, tags in expected.items():
        assert actual[step].keys() == tags.keys()
        for tag, row in tags.items():
            assert max(abs(x-y) for x,y in zip(actual[step][tag],row)) < 2e-10


def check_patch(directory, executable):
    # Equal pressures at both open ends admit u=0 and uniform p. This gives
    # an exact oracle for the load stage independently of a pipe flow formula.
    mean, amplitude, period, ramp = .013, .026, .37, .16
    for scheme in ('be','bdf2','generalized_alpha'):
        config = study.case_config(16, 2, scheme)
        config['fluid'].update(dt=.071, steps=7)
        for b in config['fluid']['boundaries']:
            if b['type']=='pressure':
                b.update(value=mean, pressure_time=dict(amplitude=amplitude, period=period, ramp_time=ramp))
        (directory/'patch.json').write_text(json.dumps(config))
        log = f'patch-{scheme}.log'
        tube.run([executable,'-case','patch.json','-fluid_boundary_history'],directory,log)
        rows = study.boundary_history((directory/log).read_text())
        assert set(rows)==set(range(1,8))
        previous = 0.
        for step in range(1,8):
            af = 2/3 if scheme=='generalized_alpha' and step>1 else 1.
            stage_time = (step-1+af)*.071
            x = min(stage_time/ramp,1.)
            stage = x**3*(10-15*x+6*x*x)*(mean+amplitude*math.sin(2*math.pi*stage_time/period))
            endpoint = previous+(stage-previous)/af
            assert set(rows[step])=={1,2,3}
            for row in rows[step].values():
                assert abs(row.time-step*.071)<1e-13 and abs(row.flow)<1e-11
                assert abs(row.pressure-endpoint)<2e-10, (scheme,step,row.pressure,endpoint)
            previous = endpoint
        for vx,vy,vz,p in tube.fields(directory,1).values():
            assert max(abs(vx),abs(vy),abs(vz),abs(p-previous))<2e-9


def rejected(command, directory, expected):
    result = subprocess.run(list(map(str,command)), cwd=directory, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=40)
    assert result.returncode and expected in result.stdout, result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--mpiexec',required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(dir=args.work))
    print('Evidence in',work,flush=True)
    exe=args.executable.resolve()
    # A coarse, short smoke case for regular CI. The finer study has its own
    # predeclared quantitative gates and is run separately.
    study.solve(work/'tube',exe,args.mpiexec,1,12,2,3,16,3,'bdf2')
    directory=work/'tube'
    metrics=study.analyze(directory)
    assert metrics['amplitude_relative_error']<.2 and metrics['phase_error_degrees']<10, metrics
    assert metrics['max_net_outward_flux']<1e-10
    field=audit(directory,directory)
    assert field['max_wall_speed']<1e-12 and field['velocity_relative_l2']<.4, field
    serial=tube.fields(directory,1)
    serial_history=study.boundary_history((directory/'solve.log').read_text())
    tube.run([exe,'-case','case.json','-prepare','parts','-parts',2],directory,'prepare.log')
    mpi=[args.mpiexec,'-n',2,exe,'-partition','parts']
    tube.run([*mpi,'-case','case.json','-fluid_boundary_history'],directory,'mpi.log')
    parallel=tube.fields(directory,2)
    mpi_error=compare_states(parallel, serial)
    compare_history(study.boundary_history((directory/'mpi.log').read_text()),serial_history)
    cut=5
    tube.run([*mpi,'-case','case.json','-stop_after',cut,'-checkpoint','checkpoint'],
             directory,'partial.log')
    assert 'fluid_boundary_step=' not in (directory/'partial.log').read_text()
    config=json.loads((directory/'case.json').read_text())
    config['fluid']['boundaries'].reverse()
    (directory/'restart.json').write_text(json.dumps(config))
    tube.run([*mpi,'-case','restart.json','-restart','checkpoint','-fluid_boundary_history'],
             directory,'restart.log')
    restart_error=compare_states(tube.fields(directory,2),parallel)
    compare_history(study.boundary_history((directory/'restart.log').read_text()),
                    {i:rows for i,rows in serial_history.items() if i>cut})
    idx=next(i for i,b in enumerate(config['fluid']['boundaries']) if 'pressure_time' in b)
    for key,value in (('amplitude',-.02),('period',2.),('ramp_time',.1)):
        changed=copy.deepcopy(config)
        changed['fluid']['boundaries'][idx]['pressure_time'][key]=value
        (directory/'changed.json').write_text(json.dumps(changed))
        rejected([*mpi,'-case','changed.json','-restart','checkpoint'],directory,'physics mismatch')
    for modify, message in (
        (lambda c,b:c['fluid'].update(mode='stokes'),'requires transient fluid'),
        (lambda c,b:b.update(ramp_time=.1),'Use pressure_time.ramp_time'),
        (lambda c,b:b['pressure_time'].update(period=0),'Invalid fluid.boundaries.pressure_time'),
        (lambda c,b:b['pressure_time'].update(ramp_time=-.1),'Invalid fluid.boundaries.pressure_time'),
        (lambda c,b:b.update(type='traction',value=[0,0,0]),'Unknown key'),
    ):
        changed=copy.deepcopy(config)
        modify(changed,changed['fluid']['boundaries'][idx])
        (directory/'invalid.json').write_text(json.dumps(changed))
        rejected([exe,'-case','invalid.json'],directory,message)
    check_patch(directory,exe)
    print('Womersley smoke, exact uniform pressure and restart passed.',
          'MPI max field difference',mpi_error,'restart',restart_error)


if __name__=='__main__':
    main()
