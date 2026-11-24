"""Reintegrate the new histories from fields and align two archived independent runs."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from run import cases, FIXED_TAU, INPUT_SHA256
from run_external import input_text

NAMES = ('area', 'mean_pressure', 'mean_normal_traction', 'outward_flow',
         'prescribed_pressure', 'pressure_power')


class SurfaceAudit:
    """Owner Tet4s and outward Tri3 traces, built from the archived fluid mesh."""
    def __init__(self, mesh):
        nodes, cells, faces = mesh
        self.ids = list(nodes)
        indices = {n: i for i, n in enumerate(self.ids)}
        self.reference = np.array([nodes[n] for n in self.ids])
        self.tets = np.array([[indices[n] for n in cell] for cell in cells])
        self.ports = {}
        exterior = {tuple(sorted(face)): (tag, face) for tag, face in faces if tag in (1, 2)}
        for cell in cells:
            for opposite in cell:
                key = tuple(sorted(n for n in cell if n != opposite))
                if key in exterior:
                    tag, face = exterior.pop(key)
                    self.ports.setdefault(tag, []).append([indices[n] for n in (*face, opposite)])
        if exterior or set(self.ports) != {1, 2}:
            raise ValueError('Incomplete tagged fluid ends')
        self.ports = {k: np.array(v) for k, v in self.ports.items()}

    def array(self, state):
        return np.array([(*state[n].displacement, *state[n].velocity, state[n].pressure)
                         for n in self.ids])

    def volume(self, state):
        points = (self.reference + state[:, :3])[self.tets]
        determinants = np.linalg.det(points[:, 1:] - points[:, :1])
        if not np.all(determinants > 0):
            raise ValueError('Invalid deformed volume')
        return float(determinants.sum()/6)

    def observe(self, state, load):
        result = {}
        for tag, cells in self.ports.items():
            xyz = (self.reference + state[:, :3])[cells]
            u = state[cells, 3:6]
            edges = xyz[:, 1:] - xyz[:, :1]
            area_vectors = .5*np.cross(edges[:, 0], edges[:, 1])
            inward = (area_vectors*edges[:, 2]).sum(axis=1) > 0
            area_vectors[inward] *= -1
            areas = np.linalg.norm(area_vectors, axis=1)
            normal = area_vectors/areas[:, None]
            grad = np.linalg.solve(edges, u[:, 1:] - u[:, :1])
            strain = np.einsum('fi,fij,fj->f', normal, grad, normal)
            area = float(areas.sum())
            pressure = state[cells[:, :3], 6].mean(axis=1)
            mean_p = float(areas@pressure/area)
            # The locked tube viscosity is 1 Pa s.
            mean_traction = float(areas@(2*strain-pressure)/area)
            flow = float((u[:, :3].mean(axis=1)*area_vectors).sum())
            result[tag] = dict(zip(NAMES, (area, mean_p, mean_traction, flow, load, -load*flow)))
        return result


def imposed(load, t):
    if load == 'step':
        return .02
    x = min(1., t)
    return .02*x**3*(10 - 15*x + 6*x*x)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--archive', type=Path, required=True)
    cli.add_argument('--reference-scripts', type=Path, required=True, help='scripts/ at PR 42 0c8f6fb')
    cli.add_argument('--work', type=Path, required=True, help='Output of run.py')
    cli.add_argument('--external-work', type=Path, required=True, help='Output of run_external.py')
    cli.add_argument('--output', type=Path, required=True)
    a = cli.parse_args()
    sys.path.insert(0, str(a.reference_scripts.resolve()))
    import compare_svfsi_wall as external
    import study_hydrostatic_fsi as fsi
    import study_lame_wall as wall
    import study_rigid_tube as tube

    source = a.archive/'coupled/sv05-s48'
    meshes = [tube.read_mesh(source/name) for name in ('fluid.msh','solid.msh')]
    audit = SurfaceAudit(meshes[0])
    nodes, _, faces = meshes[1]
    rings = {}
    for n in {n for tag, face in faces if tag == 13 for n in face}:
        rings.setdefault(nodes[n][0], []).append(n)
    sections = sorted(rings)
    mid = sections.index(wall.LENGTH/2)
    exact = 2*wall.lame(wall.INNER, .02)[0]/wall.INNER
    zero = np.zeros((len(audit.ids), 7))
    volume0 = audit.volume(zero)
    errors = {name: 0. for name in NAMES}
    traces, strains, runs = [], {}, {}
    experiments = [(name, load, dt, a.work/name, None) for load, _, dt, name in cases()]
    for dt, folder in ((.5,'alpha05-medium'), (.25,'alpha05-medium-dt025')):
        experiments.append((f'svFSI-{dt}', 'step', dt, a.archive/'svfsi'/folder, external))
    experiments.append(('svFSI-0.125', 'step', .125, a.external_work/'0.125', external))
    archived_control = a.archive/'svfsi/alpha05-medium-dt025'
    rebuilt_control = a.external_work/'0.25'
    control_errors = dict(displacement=0., velocity=0., pressure=0.)
    for dt in (.25,.125):
        directory = a.external_work/str(dt)
        if (directory/'svFSI.inp').read_text() != input_text(archived_control,dt):
            raise ValueError('Unexpected inputs for rebuilt svFSI')
        for mesh in (*archived_control.glob('*.vtp'), *archived_control.glob('*.vtu')):
            if mesh.read_bytes() != (directory/mesh.name).read_bytes():
                raise ValueError('External mesh or boundary changed '+mesh.name)
        if (directory/'executable.sha256').read_text() != (rebuilt_control/'executable.sha256').read_text():
            raise ValueError('Refinement and control require the same executable')
        for equation in ('FS','MS'):
            external.check_convergence((directory/'1-procs/histor.dat').read_text(),round(1/dt),equation)
    for step in range(1,5):
        relative = f'1-procs/result_{step:03d}.vtu'
        for old, rebuilt in zip(external.external_fields(archived_control/relative,meshes),
                                external.external_fields(rebuilt_control/relative,meshes)):
            for n in old:
                for field in control_errors:
                    delta = np.subtract(getattr(old[n],field), getattr(rebuilt[n],field))
                    control_errors[field] = max(control_errors[field], float(np.max(np.abs(delta))))
    if max(control_errors.values()) > 2e-9:
        raise ValueError(f'Rebuilt svFSI control differs from archived fields: {control_errors}')
    for name, load, dt, directory, upstream in experiments:
        nsteps = round(1/dt)
        if upstream is None:
            for mesh in ('fluid.msh','solid.msh'):
                if hashlib.sha256((directory/mesh).read_bytes()).hexdigest() != INPUT_SHA256[mesh]:
                    raise ValueError('Mesh mismatch '+name)
            cfg = json.loads((directory/'case.json').read_text())
            expected = json.loads((source/'case.json').read_text())
            expected['fsi'].update(steps=nsteps, dt=dt, pressure_face_history=True)
            if load == 'ramp':
                expected['fsi']['pressure_time'] = dict(amplitude=0., period=1., ramp_time=1.)
            if '-fixed-' in name:
                expected['fsi']['stabilization_tau'] = FIXED_TAU
            if cfg != expected or (directory/'solve.log').read_text().splitlines()[-1] != 'status=success':
                raise ValueError('Case or convergence mismatch '+name)
            with (directory/'tube_pressure_faces.csv').open() as stream:
                history = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
            if [(r['step'],r['tag']) for r in history] != [(i,k) for i in range(1,nsteps+1) for k in (1,2)]:
                raise ValueError('Missing or duplicated face record '+name)
        elif dt in (.5,.25):
            if (directory/'executable.sha256').read_text().strip() != '76fa8bccbe419b4c8cf95d40c74b64290d2b55079750e7f44ef270f7c8760c06':
                raise ValueError('Unexpected external executable')
            log = (directory/'1-procs/histor.dat').read_text()
            for equation in ('FS','MS'):
                upstream.check_convergence(log, round(12/dt), equation)
        prev = zero
        old_q = old_power = inflow = work = 0.
        first_inflow_correction = first_work_correction = None
        strains[name] = {}
        for step in range(1,nsteps+1):
            time = step*dt
            if upstream is None:
                fluid = fsi.recovered_state(directory, f'tube_step{step}', meshes[0], False, 1)
                solid = fsi.recovered_state(directory, f'tube_step{step}_solid', meshes[1], True, 1)
            else:
                fluid, solid = upstream.external_fields(directory/f'1-procs/result_{step:03d}.vtu',meshes)
            state = audit.array(fluid)
            end = audit.observe(state, imposed(load,time))
            stage = {}
            evaluation_time = None
            if upstream is None:
                weight = 1. if step == 1 else 2/3
                evaluation_time = (step-1+weight)*dt
                stage = audit.observe((1-weight)*prev+weight*state, imposed(load,evaluation_time))
                for i,tag in enumerate((1,2)):
                    row = history[2*(step-1)+i]
                    if max(abs(row[k]-v) for k,v in [('time', time), ('evaluation_time', evaluation_time),
                                                      ('accepted_dt', dt)]) > 1e-14:
                        raise ValueError('Incorrect time layer '+name)
                    for sample, observed in [('endpoint',end[tag]),('stage',stage[tag])]:
                        for k, v in observed.items():
                            err = abs(v - row[sample+'_'+k])
                            if not math.isfinite(err) or err > 5e-12:
                                raise ValueError((name, step, tag, sample, k, err))
                            errors[k] = max(errors[k], err)
            d = {n: v.displacement for n,v in solid.items()}
            v = {n: s.velocity for n,s in solid.items()}
            strains[name][time] = [wall.bore_section(nodes,d,rings[x])['linear_area_strain'] for x in sections]
            wall_speed = wall.bore_section(nodes,v,rings[sections[mid]])['radial_displacement']
            q = sum(r['outward_flow'] for r in end.values())
            power = sum(r['pressure_power'] for r in end.values())
            inflow -= .5*dt*(old_q+q)
            work += .5*dt*(old_power+power)
            gain = audit.volume(state)-volume0
            # EONSim starts with BE from rest. Replacing the first trapezoid by its
            # right endpoint isolates startup quadrature without changing a field.
            if upstream is None and step == 1:
                first_inflow_correction = -.5*dt*q
                first_work_correction = .5*dt*power
            for tag in (1,2):
                row = dict(case=name, step=step, time=time, evaluation_time=evaluation_time, tag=tag,
                           mid_area_strain=strains[name][time][mid], mid_radial_speed=wall_speed,
                           volume_gain=gain, trapezoid_net_inflow=inflow, trapezoid_pressure_work=work,
                           be_first_net_inflow=inflow+first_inflow_correction if upstream is None else None,
                           be_first_pressure_work=work+first_work_correction if upstream is None else None)
                for sample, values in [('stage',stage.get(tag,{})), ('endpoint',end[tag])]:
                    row.update({sample+'_'+k: values.get(k) for k in NAMES})
                traces.append(row)
            prev, old_q, old_power = state, q, power
        runs[name] = dict(mid_area_strain=strains[name][1.][mid], volume_gain=gain,
                          trapezoid_net_inflow=inflow, trapezoid_inflow_minus_gain=inflow-gain,
                          trapezoid_pressure_work=work)
        if upstream is None:
            runs[name].update(be_first_inflow_minus_gain=inflow+first_inflow_correction-gain,
                              be_first_pressure_work=work+first_work_correction)
    cross = {}
    tau_sensitivity = {}
    for dt in (.5,.25,.125):
        eon, sv = strains[f'step-default-{dt}'], strains[f'svFSI-{dt}']
        cross[str(dt)] = {str(t): max(abs(x-y) for x,y in zip(eon[t],sv[t]))/exact for t in eon}
        tau_sensitivity[str(dt)] = {
            load: max(abs(x-y) for x,y in zip(strains[f'{load}-default-{dt}'][1.],
                                              strains[f'{load}-fixed-{dt}'][1.]))/exact
            for load in ('step','ramp')}
    results = dict(time_end=1., axial_sections=sections, exact_equilibrium_area_strain=exact,
                   max_field_reintegration_abs=errors, svfsi_rebuild_control_max_abs=control_errors,
                   rebuilt_svfsi_sha256=(rebuilt_control/'executable.sha256').read_text().strip(),
                   cases_at_one_second=runs,
                   worst_section_intercode_gap_over_equilibrium_strain=cross,
                   worst_section_fixed_vs_default_at_one_second_over_equilibrium_strain=tau_sensitivity)
    a.output.mkdir(parents=True, exist_ok=True)
    with (a.output/'traces.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(traces[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(traces)
    (a.output/'results.json').write_text(json.dumps(results, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
