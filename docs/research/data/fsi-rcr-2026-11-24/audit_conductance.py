"""Recover the differential resistance and steady RCR fluxes from the two independent VTU fields."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

from branch_conductance import cap_flows
from branch_external import observations
from study_rigid_tube import read_mesh
from verify_fsi_inlet import check_rcr_history


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stokes_observations(case):
    cfg = json.loads((case / 'stokes.json').read_text())['fluid']
    if (cfg['mode'], cfg['viscosity'], cfg['density']) != ('stokes', 1., 1.):
        raise ValueError('Unexpected conductance equation')
    bc = {v['tag']: v for v in cfg['boundaries']}
    if set(bc) != {1, 2, 3, 4} or any(bc[t]['value'] != [0., 0., 0.] for t in (1, 4)):
        raise ValueError('Expected prescribed zero velocity on inlet and walls')
    if any(bc[t]['type'] != 'pressure' for t in (2, 3)):
        raise ValueError('Expected prescribed daughter pressures')
    jump = bc[2]['value'] - bc[3]['value']
    flows = cap_flows(case)
    log = (case / 'solve.log').read_text()
    if log.splitlines()[-1:] != ['status=success']:
        raise ValueError('Incomplete Stokes solution')
    diagnostics = {int(tag): float(flow) for tag, flow in re.findall(
        r'^boundary_tag=(\d+) area=\S+ outward_flow=(\S+)', log, re.M)}
    discrepancy = max(abs(v - diagnostics[t]) for t, v in flows.items())
    if discrepancy > 1e-12 * abs(flows[2]) or abs(sum(flows.values())) > 1e-10 * abs(flows[2]):
        raise ValueError('Independent Stokes cap flux differs from the accepted history')
    return dict(pressure_jump_pa=jump, outward_flow=flows, cap_flux_check=discrepancy,
                differential_resistance=-jump / (flows[2] - flows[3]),
                files={f: digest(case / f) for f in ('fluid.msh', 'stokes.json', 'solve.log', 'solution.vtu')})


def coupled_observations(case, resistance, recover):
    cfg = json.loads((case / 'coupled.json').read_text())['fsi']
    if [m['tag'] for m in cfg['domains']['rcr_outlets']] != [2, 3]:
        raise ValueError('Expected both RCR terminals')
    qin = cfg['inlet']['flow_rate']['mean']
    if qin <= 0 or cfg['inlet']['flow_rate']['amplitude'] != 0:
        raise ValueError('Expected constant positive inlet')
    models = cfg['domains']['rcr_outlets']
    rs = [m['proximal_resistance'] + m['distal_resistance'] for m in models]
    if any(m['distal_pressure'] for m in models):
        raise ValueError('Expected common zero downstream pressures')
    with (case / 'coupled.csv').open() as stream:
        history = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
    n = cfg['steps']
    log = (case / 'coupled.log').read_text()
    steps = list(range(1, n + 1))
    if (log.splitlines()[-1:] != ['status=success'] or
        [int(i) for i in re.findall(r'^fsi_step=(\d+)', log, re.M)] != steps or
        [r['step'] for r in history] != steps or
        not all(math.isfinite(v) for r in history for v in r.values())):
        raise ValueError('Incomplete accepted coupled step history')
    circuit = max(check_rcr_history(SimpleNamespace(work=case), 'coupled', m, history, sole_pressure=False) for m in models)
    fluid = read_mesh(case / 'fluid.msh')
    state = recover(case, 'coupled', fluid, False, 1)
    obs = observations(fluid, state)
    last = history[-1]
    q = [last[f'endpoint_rcr_flow_{t}'] for t in (2, 3)]
    p = [last[f'endpoint_rcr_pressure_{t}'] for t in (2, 3)]
    discrepancy = max(abs(a - b) for a, b in zip(obs['flux'], [qin, *q]))
    motion = max(abs(d) for field in state.values() for d in field.displacement)
    drift = max(abs(r[f'endpoint_rcr_flow_{t}'] - v) / qin for r in history[-max(2, n // 4):] for t, v in zip((2, 3), q))
    pressure_error = max(abs(pb - r * flow) for pb, r, flow in zip(p, rs, q))
    if (discrepancy > 1e-10 * qin or abs(sum(q) / qin - 1) > 1e-9 or motion > 1e-11
            or drift > 1e-7 or pressure_error > 1e-7 * max(p)):
        raise ValueError('Saved fields or final circuit history failed the steady clamped control')
    actual = obs['flux'][1] / qin
    prediction = (resistance + rs[1]) / (2 * resistance + sum(rs))
    return dict(inlet=qin, resistances=rs, outlet_flows=q, outlet_pressures=p, tag2_fraction=actual,
                predicted_tag2_fraction=prediction, difference=actual - prediction, last_quarter_drift_inlet=drift,
                max_circuit_residual=circuit, vtu_cap_flux_check=discrepancy, max_displacement=motion,
                terminal_pressure_error=pressure_error, time_steps=n, duration_s=n * cfg['dt'],
                files={f: digest(case / f) for f in ('fluid.msh', 'solid.msh', 'coupled.json', 'coupled.log',
                                                       'coupled.csv', 'coupled_pressure_faces.csv', 'coupled.vtu')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runs', 'executable', 'reference-scripts', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path.append(str(args.reference_scripts.resolve()))
    from study_hydrostatic_fsi import recovered_state
    results = []
    exe = digest(args.executable)
    for receipt in sorted(args.runs.glob('g*/result.json')):
        case = receipt.parent
        source = json.loads(receipt.read_text())
        if source['executable_sha256'] != exe:
            raise ValueError('The binary differs from the experiment receipt')
        stokes = [stokes_observations(f) for f in sorted(case.glob('stokes-*'))]
        if {s['pressure_jump_pa'] for s in stokes} != {-.01, .02}:
            raise ValueError('Missing a pressure reversal')
        res = stokes[0]['differential_resistance']
        if res <= 0 or abs(stokes[1]['differential_resistance'] / res - 1) > 1e-9:
            raise ValueError('Pressure reversal or amplitude checks failed')
        coupled = [coupled_observations(f, res, recovered_state) for f in sorted(case.glob('clamped-*'))]
        expected = {(.002, 44., 11.), (.0002, 44., 11.), (.002, 11., 44.), (.002, 11., 11.)}
        if ({(r['inlet'], *r['resistances']) for r in coupled} != expected or
                len({s['files']['fluid.msh'] for s in stokes + coupled}) != 1):
            raise ValueError('Unmatched mesh or missing terminal control')
        mesh = read_mesh(next(case.glob('clamped-*')) / 'fluid.msh')
        results.append(dict(refinement=source['refinement'], fluid_tetrahedra=len(mesh[1]),
                            differential_resistance=res, stokes=stokes, coupled=coupled))
    if [row['refinement'] for row in results] != [1, 2, 3]:
        raise ValueError('Need all three mesh refinements')
    archive = dict(executable_sha256=exe, grids=results)
    args.output.write_bytes(lzma.compress((json.dumps(archive, indent=2, allow_nan=False) + '\n').encode()))
    for row in results:
        c = next(r for r in row['coupled'] if (r['inlet'], *r['resistances']) == (.002, 44., 11.))
        print(row['fluid_tetrahedra'], row['differential_resistance'], c['tag2_fraction'], c['difference'])


if __name__ == '__main__':
    main()
