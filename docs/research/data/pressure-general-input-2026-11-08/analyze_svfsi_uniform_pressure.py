"""Check the exact discrete uniform-pressure solution of pinned svFSI.

Requires the separate NumPy/VTK postprocessing environment. Exit status alone
does not establish that svFSI ran: every output step and physical field is read.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def read(path):
    reader=vtk.vtkXMLUnstructuredGridReader()
    errors=[]
    reader.AddObserver('ErrorEvent',lambda *args:errors.append(str(args)))
    reader.SetFileName(str(path));reader.Update()
    if errors:
        raise ValueError(f'Invalid VTK output: {path}: {errors}')
    grid=reader.GetOutput()
    fields={}
    for name in ('Velocity','Pressure'):
        value=grid.GetPointData().GetArray(name)
        if value is None:
            raise ValueError(f'Missing {name}: {path}')
        fields[name]=vtk_to_numpy(value).copy()
        if not np.all(np.isfinite(fields[name])):
            raise ValueError(f'Nonfinite {name}: {path}')
    return grid,fields


def analyze(work):
    report=json.loads((work/'export.json').read_text())
    if report['mode']!='uniform-pressure import check':
        raise ValueError('Not a uniform-pressure import check')
    for name,digest in report['files'].items():
        if hashlib.sha256((work/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Input changed: {name}')
    cfg=json.loads((work/'source-case.json').read_text());f=cfg['fsi']
    profile=f['pressure_time'];dt=f['dt'];af=1/(1+cfg['time'].get('rho_infinity',.5))
    offset=report.get('pressure_time_offset',0.)
    n=int(re.search(r'^Number of time steps: (\d+)$',(work/'svFSI.inp').read_text(),re.M)[1])
    paths={int(path.stem.rsplit('_',1)[1]):path for path in (work/'results').glob('result_*.vtu')}
    if set(paths)!=set(range(1,n+1)):
        raise ValueError('Missing or unexpected reference output steps')
    previous=0.;expected=0.;reference_coordinates=None
    rows=[];maximum_velocity=pressure_error=pressure_range=stage_error=0.
    for step in range(1,n+1):
        grid,fields=read(paths[step])
        coords=vtk_to_numpy(grid.GetPoints().GetData())
        if reference_coordinates is None:
            reference_coordinates=coords.copy()
        if (grid.GetNumberOfPoints()!=report['meshes']['fluid']['nodes'] or
            grid.GetNumberOfCells()!=report['meshes']['fluid']['tetrahedra'] or
            not np.array_equal(coords,reference_coordinates)):
            raise ValueError('Uniform-pressure mesh changed')
        pressure=fields['Pressure'];velocity=fields['Velocity']
        if velocity.shape!=(len(pressure),3):
            raise ValueError('Invalid field dimensions')
        time=step*dt
        load=f['pressure']+profile['amplitude']*math.sin(2*math.pi*(time-offset)/profile['period'])
        ramp=profile.get('ramp_time',0.)
        if ramp>0:
            x=min(1.,max(0.,(time-offset)/ramp))
            load*=6*x**5-15*x**4+10*x**3
        expected=(load-(1-af)*expected)/af
        mean=float(pressure.mean())
        pressure_error=max(pressure_error,float(np.max(abs(pressure-expected))))
        stage_error=max(stage_error,abs(af*mean+(1-af)*previous-load))
        maximum_velocity=max(maximum_velocity,float(np.max(np.linalg.norm(velocity,axis=1))))
        pressure_range=max(pressure_range,float(np.ptp(pressure)))
        rows.append(dict(step=step,time=time,load=load,pressure_mean=mean,expected_endpoint_pressure=expected))
        previous=mean
    result=dict(svfsi_commit=report['svfsi_commit'],steps=n,alpha_f=af,pressure_time_offset=offset,
        pressure_input=report.get('general_pressure',dict(kind='Fourier coefficients')),
        versions=dict(vtk=vtk.vtkVersion.GetVTKVersion(),numpy=np.__version__),
        maximum_velocity=maximum_velocity,maximum_pressure_range=pressure_range,
        maximum_endpoint_recurrence_error=pressure_error,maximum_stage_load_error=stage_error,
        passed=max(maximum_velocity,pressure_range,pressure_error,stage_error)<1e-9,
        interpretation='Stored pressure is the endpoint state; its alpha_f interpolation balances the input read at global endpoint time.',
        scope='Exact discrete import/time-convention check, not elastic or spatial qualification',rows=rows)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=analyze(args.work)
    (args.output or args.work/'uniform-analysis.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},allow_nan=False))
    if not result['passed']:
        raise SystemExit('Uniform-pressure discrete reference failed')
