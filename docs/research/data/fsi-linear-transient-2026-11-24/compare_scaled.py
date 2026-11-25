"""Compare dimensionally similar tube fields and two independent solvers at a different physical operating point."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import lzma
import math
from pathlib import Path
import sys

import numpy as np

from scaled_tube import SurfaceAudit, problem
from audit_reflection import measured_ring_strains
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"scripts"))
from svfsi_history import check_convergence, equation_iterations


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_result(path, name, executable, recovered_state, external_fields, read_mesh):
    d = json.loads(path.read_text())
    case = path.parent
    material, duration, pressure = problem(d['problem'])
    if (d['parameters'] != asdict(material) or (d['duration'], d['pressure']) != (duration, pressure)
            or not math.isclose(material.lame_area_strain(pressure), d['static_area_strain'], rel_tol=1e-13)):
        raise ValueError('Configuration and measured experiment differ')
    if d['executable_sha256'] != digest(executable):
        raise ValueError('Executable differs from solver receipt')
    if not 0 <= d['load_error'] <= pressure * 2e-12:
        raise ValueError('End pressure differs from analytic pressure ramp')
    for file, sha in d['input_sha256'].items():
        if digest(case / file) != sha:
            raise ValueError('Input changed: ' + file)
    is_eon = name in ('eonsim', 'eonsim-tight')
    hist = 'tube_pressure_faces.csv' if is_eon else '1-procs/histor.dat'
    if digest(case / hist) != d['history_sha256']:
        raise ValueError('Solver history changed')
    if is_eon:
        cfg = json.loads((case / 'case.json').read_text())['fsi']
        expected = dict(pressure=pressure, steps=d['steps'], dt=duration/d['steps'], density=material.fluid_density,
                        viscosity=material.viscosity, solid_density=material.solid_density, young=material.young,
                        poisson=material.poisson, stabilization_model=d['model'])
        if any(cfg.get(k)!=v for k,v in expected.items()):
            raise ValueError('EONSim physical parameters differ from the specified problem')
        with (case/hist).open() as stream:
            faces={(int(v['step']),int(v['tag'])):v for v in csv.DictReader(stream)}
        if len(faces)!=2*d['steps']:
            raise ValueError('Missing tagged end load')
        for step in range(1,d['steps']+1):
            for tag in (1,2):
                row=faces[step,tag]
                for phase,weight in (('stage',1. if step==1 else 2./3.),('endpoint',1.)):
                    x=(step-1+weight)/d['steps']
                    target=pressure*x**3*(10+x*(-15+6*x))
                    if abs(float(row[phase+'_prescribed_pressure'])-target)>2e-12*pressure:
                        raise ValueError('Raw pressure trace differs from the independently evaluated ramp')
    else:
        from audit_study import external_loads
        if len(external_loads(case,d['steps'],'matched',pressure,duration))!=2*d['steps']:
            raise ValueError('Incomplete native residual-side pressure trace')
        for eq in ('FS', 'MS'):
            if list(check_convergence((case / hist).read_text(), d['steps'], eq)) != d['convergence'][eq]:
                raise ValueError('Native nonlinear convergence history changed')
    meshes = [read_mesh(case / file) for file in ('fluid.msh', 'solid.msh')]
    surface = SurfaceAudit(meshes[0])
    initial = surface.volume(np.zeros((len(surface.ids),7)))
    if [s['phase'] for s in d['samples']] != [i / 8 for i in range(1, 9)]:
        raise ValueError('Eight equally spaced snapshots required')
    states = []
    for sample in d['samples']:
        phase = sample['phase']
        step = round(phase * d['steps'])
        if abs(sample['time'] - phase * duration) > 1e-13 * duration:
            raise ValueError('Changed physical observation time')
        if is_eon:
            files = [f'tube_step{step}{suffix}.vtu' for suffix in ('', '_solid')]
            if [digest(case / f) for f in files] != [sample['vtu_sha256'][s] for s in ('', '_solid')]:
                raise ValueError('Changed EONSim fields')
            state = [recovered_state(case, Path(f).stem, mesh, bool(j), 1) for j, (f, mesh) in enumerate(zip(files, meshes))]
        else:
            f = case / f'1-procs/result_{step:03d}.vtu'
            if digest(f) != sample['vtu_sha256']:
                raise ValueError('Changed svFSI fields')
            state = external_fields(f, meshes)
        xs, area = measured_ring_strains(meshes[1],state[1])
        if d['xs'] != xs or not np.allclose(area, sample['strains'], rtol=2e-13, atol=1e-16):
            raise ValueError('Ring area differs from solved displacement field')
        field = surface.array(state[0])
        observed = surface.observe(field,0.,material.viscosity)
        true_flow = [observed[t]['outward_flow'] for t in (1,2)]
        if (not np.allclose(true_flow,sample['outward_flow'],rtol=3e-12,atol=1e-22)
                or abs(surface.volume(field)/initial-1-sample['relative_volume_change'])>5e-13):
            raise ValueError('Cap flux or ALE volume differs from the saved field')
        if d['problem'] != 'arterial':
            states.append(state)
    return d, meshes, states


def similarity(a, b):
    first, mesh0, state0 = a
    twin, mesh1, state1 = b
    p = twin['pressure'] / first['pressure']
    t = twin['duration'] / first['duration']
    l = twin['parameters']['radius'] / first['parameters']['radius']
    if twin['steps'] != first['steps'] or twin['executable_sha256'] != first['executable_sha256']:
        raise ValueError('Nonmatching twin discretization')
    scale = {'displacement': l, 'velocity': l / t, 'pressure': p}
    for name, factor in (('length', l), ('outer_radius', l), ('young', p), ('viscosity', p*t),
                         ('fluid_density', p*t*t/(l*l)), ('solid_density', p*t*t/(l*l)), ('poisson', 1.)):
        if not math.isclose(twin['parameters'][name], factor * first['parameters'][name], rel_tol=2e-14):
            raise ValueError('Twin physical similitude condition failed for ' + name)
    for grid0, grid1 in zip(mesh0, mesh1):
        if (grid0[1:] != grid1[1:] or grid0[0].keys() != grid1[0].keys() or
                max(abs(a - b/l) for i in grid0[0] for a, b in zip(grid0[0][i], grid1[0][i])) > 2e-14):
            raise ValueError('Changed twin coordinate, cell connectivity or tagged port')
    fields = {}
    for ka, kb in zip(state0, state1):
        for i, (fa, fb) in enumerate(zip(ka, kb)):
            if fa.keys() != fb.keys():
                raise ValueError('Twin physical node identifiers differ')
            for name in ('displacement', 'velocity', 'pressure') if not i else ('displacement', 'velocity'):
                x = np.array([getattr(fa[k], name) for k in sorted(fa)])
                y = np.array([getattr(fb[k], name) for k in sorted(fa)]) / scale[name]
                key = ('wall_' if i else 'fluid_') + name
                obs = fields.setdefault(key, dict(peak=0., max_error=0.))
                obs['max_error'] = max(obs['max_error'], float(np.max(abs(x-y))))
                obs['peak'] = max(obs['peak'], float(np.max(abs(x))))
    for metric in fields.values():
        if metric['peak'] <= 0:
            raise ValueError('Empty physical signal')
        metric['error_over_field_peak'] = metric['max_error']/metric['peak']
    gain = max(abs(x['relative_volume_change']-y['relative_volume_change'])
               for x, y in zip(first['samples'], twin['samples']))
    strain = max(abs(i-j) for x, y in zip(first['samples'], twin['samples']) for i,j in zip(x['strains'],y['strains']))
    flow = max(abs(i-j*t/l**3) for x,y in zip(first['samples'],twin['samples']) for i,j in zip(x['outward_flow'],y['outward_flow']))
    return dict(reference_units=True, fields=fields, max_absolute_area_strain_error=strain,
                max_relative_volume_change_error=gain, max_quarter_cap_flux_error=flow)


def pack(root, reference_scripts):
    sys.path.append(str(reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    from compare_svfsi_wall import external_fields
    from study_rigid_tube import read_mesh
    inputs = [('eonsim', 'scaled-eon'), ('eonsim-tight', 'scaled-eon-atol'), ('svfsi', 'scaled-sv'), ('svfsi-krylov','scaled-sv-krylov'),
              *[(f'svfsi-bipn-{m}',f'scaled-sv-bipn-{m}') for m in ('explicit','qr','explicit-floor','qr-floor')]]
    observations, twins, raw = [], [], {}
    for name, group in inputs:
        for path in sorted((root / group).glob('*/result.json')):
            grid, variant = path.parent.name.split('-n')[0], path.parent.name.rsplit('-', 1)[1]
            if name.startswith('svfsi-bipn-'):
                build='sv-bipn-'+name.removeprefix('svfsi-bipn-')+'-build/bin/svFSI'
            elif name.startswith('svfsi'):
                build='sv-current-native-build/bin/svFSI' if variant=='native' else 'sv-regular-metric-build/bin/svFSI'
            else:
                build='regular-tet-eonsim'
            data = read_result(path, name, root / build, recovered_state, external_fields, read_mesh)
            d = data[0]
            if name.startswith('eonsim') and d['model'] != variant:
                raise ValueError('EONSim stabilization differs')
            observations.append(dict(solver=name, grid=grid, variant=variant, report=d))
            if d['problem'] != 'arterial':
                raw[name, grid, variant, d['steps'], d['problem']] = data
    for (name, grid, variant, n, physical), b in sorted(raw.items()):
        if physical != 'similar':
            continue
        a = raw[name, grid, variant, n, 'artificial']
        twins.append(dict(solver=name, grid=grid, variant=variant, steps=n, **similarity(a, b)))
    refs = [json.loads(f.read_text()) for f in sorted((root / 'scaled-meridian').glob('*.json'))]
    if not refs:
        raise ValueError('Missing independent circular meridian')
    failed = []
    for case in sorted((root/'scaled-eon-rejected').glob('*')):
        if not case.is_dir():
            continue
        log = (case/'case.log').read_text().splitlines()
        if log[-1:] != ['status=failed']:
            raise ValueError('Unexpected terminal status in rejected run')
        cfg = json.loads((case/'case.json').read_text())
        failed.append(dict(solver='EONSim',case=case.name, absolute_tolerance=cfg['solver']['absolute_tolerance'],
                           last_accepted_step=sum(s.startswith('fsi_step=') for s in log), reason=log[-2],
                           log_sha256=digest(case/'case.log')))
    for group in (group for name,group in inputs if name.startswith('svfsi')):
        for case in sorted((root/group).glob('s*/')):
            log=case.with_name(case.name+'.log')
            if (case/'result.json').is_file() or not log.exists() or 'Traceback' not in log.read_text():
                continue
            hist=case/'1-procs/histor.dat'
            terminal=log.read_text().splitlines()[-1]
            detail={}
            if hist.is_file():
                for equation in ('FS','MS'):
                    try:
                        rows=list(equation_iterations(hist.read_text(),equation))
                        if not rows:continue
                        bad=[r for r in rows if r.linear_failed and (r.linear_iterations or r.residual>1e-8)]
                        caps=[v for v in {r.step for r in rows} if next(r for r in reversed(rows) if r.step==v).residual>1e-8]
                        detail[equation]=dict(last_step=rows[-1].step,linear_failures=len(bad),
                                              first_failed_linear=bad[0]._asdict() if bad else None,unconverged_final_steps=sorted(caps))
                    except ValueError as exc:
                        detail[equation]=dict(parser_error=str(exc))
            failed.append(dict(solver='svFSI',case=case.name,group=group,reason=terminal,equations=detail,
                               log_sha256=digest(log),history_sha256=digest(hist) if hist.is_file() else None))
    return dict(runs=observations, independently_scaled_twins=twins, meridians=refs, rejected=failed)


def tables(data):
    material, _, p = problem('arterial')
    refs = sorted(data['meridians'], key=lambda r:r['unknowns'])
    for ref in refs:
        if ref['parameters'] != asdict(material) or ref['pressure'] != p or ref['duration'] != 1.:
            raise ValueError('Different axisymmetric problem')
        for r in ref['runs']:
            if (r['stage_residual_max'] > 1e-8 or r['max_flux_residual_over_peak'] > 1e-7 or
                    r['max_power_residual_over_peak'] > 1e-7):
                raise ValueError('Circular meridian failed stage residual, flux or power balance')
    fine = refs[-1]
    reference = {s['time']: s['section_area_strain'] for s in max(fine['runs'],key=lambda r:r['steps'])['samples']}
    rows = []
    for item in data['runs']:
        d = item['report']
        for sample in d['samples']:
            physical = d['problem']
            if sample['phase'] not in (.5, 1.):
                continue
            strains = sample['strains']
            end, mid = strains[0], strains[len(strains)//2]
            error, ref_end, ref_mid = None, None, None
            if physical == 'arterial':
                ideal = reference[sample['time']]
                ref_end, ref_mid = 100*ideal[0], 100*ideal[len(ideal)//2]
                xs = np.array(fine['sections'])
                indices = [int(np.argmin(abs(xs-x))) for x in d['xs']]
                if any(abs(xs[i] - x) > 1e-13*material.length for i, x in zip(indices,d['xs'])):
                    raise ValueError('Need directly coincident reference sections')
                error = 100*max(abs(a-ideal[i]) for a,i in zip(strains,indices))/d['static_area_strain']
            rows.append(dict(solver=item['solver'], model=item['variant'], grid=item['grid'], steps=d['steps'],
                             native_linear_solver=d.get('linear_solver','gmres') if item['solver'].startswith('svfsi') else None,
                             native_krylov=d.get('krylov',450) if item['solver'].startswith('svfsi') else None,
                             native_outer_budget=d.get('outer_iterations',10) if item['solver'].startswith('svfsi') else None,
                             problem=physical, time_s=sample['time'], phase=sample['phase'], peak_pa=d['pressure'],
                             static_pct_area=100*d['static_area_strain'], left_pct_area=100*end, mid_pct_area=100*mid,
                             meridian_left_pct_area=ref_end, meridian_mid_pct_area=ref_mid,
                             max_section_gap_pct_static=error, quarter_inlet_outward_m3_s=sample['outward_flow'][0],
                             quarter_outlet_outward_m3_s=sample['outward_flow'][1], rel_volume_change=sample['relative_volume_change']))
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    source = cli.add_mutually_exclusive_group(required=True)
    source.add_argument('--runs', type=Path)
    source.add_argument('--archive', type=Path)
    cli.add_argument('--reference-scripts', type=Path)
    cli.add_argument('--write-archive', type=Path)
    cli.add_argument('--csv', type=Path, required=True)
    args=cli.parse_args()
    if args.runs:
        if not args.reference_scripts:
            cli.error('Auditing raw VTUs requires the pinned reference scripts')
        data=pack(args.runs, args.reference_scripts)
    else:
        data=json.loads(lzma.decompress(args.archive.read_bytes()))
    rows=tables(data)
    with args.csv.open('w',newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=rows[0],lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    if args.write_archive:
        args.write_archive.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
    print(len(data['runs']), '3D runs;', len(data['independently_scaled_twins']), 'raw full-field twin comparisons;', len(data['meridians']), 'meridians')


if __name__=='__main__':
    main()
