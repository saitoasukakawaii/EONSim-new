"""COO/element assembly equivalence on fixed-mesh fluid; actual fields, restart and failures."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from verify_schur import ROOT, fields

sys.path.insert(0, str(ROOT / 'cases/fluid'))
from generate_layered_channel import layered_mesh


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def compare(expected, actual, tolerance=2e-8):
    require(expected and expected.keys() == actual.keys(), 'Missing/different owned node sets')
    maximum = 0.
    for node in expected:
        require(len(expected[node]) == len(actual[node]), 'Field shape mismatch')
        for x, y in zip(expected[node], actual[node]):
            require(math.isfinite(x) and math.isfinite(y), 'Nonfinite physical output')
            maximum = max(maximum, abs(x-y))
    require(maximum < tolerance, f'Physical field/pressure/reaction discrepancy: {maximum}')
    return maximum


def records(text, marker):
    return [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
            if line.startswith(marker + ' ')]


def check_plan(text, ranks, enabled):
    plans = records(text, 'fluid_coo_plan')
    if not enabled:
        require(not plans, 'Default path constructed a COO plan')
        return
    require(len(plans) == ranks and {int(p['rank']) for p in plans} == set(range(ranks)),
            'Expected exactly one COO plan per rank, reused across time steps')
    for plan in plans:
        require(int(plan['entries']) == int(plan['local_cells'])*16*16, 'Unexpected Tet4 COO size')
        require(int(plan['value_bytes']) >= int(plan['entries'])*8, 'Invalid value buffer size')
        seconds = float(plan['setup_seconds'])
        require(math.isfinite(seconds) and seconds >= 0, 'Invalid setup timer')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--mpiexec', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    exe = args.executable.resolve()
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=True)
    evidence = []

    def run(command, label, success=True):
        command = list(map(str, command))
        process = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=90)
        (work / (label+'.log')).write_text(process.stdout)
        require((process.returncode == 0) == success, process.stdout)
        if success:
            require('status=success' in process.stdout, 'Missing success marker')
        evidence.append(dict(label=label, command=command, returncode=process.returncode))
        return process.stdout

    layered = work/'layered.msh'; layered_mesh(layered)
    layered_case = work/'layered.yaml'
    layered_case.write_text((ROOT/'cases/fluid/layered_channel.yaml').read_text().replace('mesh: layered_channel.msh', f'mesh: {layered}'))
    mean_case = work/'mean.json'
    mean_case.write_text(json.dumps(dict(mesh=str(ROOT/'cases/poisson/cube.msh'),
        output=str(work/'mean.vtu'), fluid=dict(mode='steady', pressure_normalization='mean',
        boundaries=[dict(tag=tag, type='velocity', value=[0, 0, 0],
                        gradient=[[.2, 0, 0], [0, -.2, 0], [0, 0, 0]]) for tag in range(1, 7)]))))
    cases = [(name, ROOT/'cases/fluid'/f'{name}.yaml')
             for name in ('stokes', 'steady', 'transient', 'rotated_channel', 'traction')]
    cases += [('layered', layered_case), ('mean', mean_case)]
    max_delta = 0.
    for name, case in cases:
        rank_reference = None
        for ranks in (1, 2, 4):
            stem = f'{name}-r{ranks}'; part = work/(stem+'-partition')
            run([exe, '-case', case, '-prepare', part, '-parts', ranks], stem+'-prepare')
            base = [args.mpiexec, '-n', ranks, exe, '-case', case, '-partition', part]
            modes = {}
            for coo in (False, True):
                label = stem+('-coo' if coo else '-values'); output = work/(label+'.vtu')
                text = run(base+['-output', output, '-solver_report']+(['-fluid_coo'] if coo else []), label)
                check_plan(text, ranks, coo)
                reports = records(text, 'solver_report')
                require(len(reports) == (10 if name == 'transient' else 1), 'Missing accepted steps')
                for report in reports:
                    require(int(report['snes_reason']) > 0 and int(report['ksp_reason']) > 0, 'Unconverged solve')
                    require(int(report['domain_rejections']) == 0, 'Unexpected rejected evaluation')
                modes[coo] = fields(output, ranks)
            max_delta = max(max_delta, compare(modes[False], modes[True]))
            if rank_reference is None:
                rank_reference = modes[False]
            max_delta = max(max_delta, compare(rank_reference, modes[True]))
            if name in ('rotated_channel', 'transient'):
                output = work/(stem+'-schur.vtu')
                text = run(base+['-fluid_coo', '-schur_pc', '-linear_report', '-output', output], stem+'-schur')
                max_delta = max(max_delta, compare(modes[False], fields(output, ranks)))
                residuals = records(text, 'linear_residual')
                require(residuals and 'linear_residual_unavailable' not in text, 'Missing true linear residuals')
                for row in residuals:
                    norm, rhs = float(row['norm']), float(row['rhs_norm'])
                    require(math.isfinite(norm) and math.isfinite(rhs) and norm <= 1e-8+1e-7*rhs,
                            'True linear residual exceeded tolerance')
            if name == 'transient':
                # Restart in both directions: the assembly representation is not physical checkpoint state.
                for source_coo in (False, True):
                    label = stem+f'-restart{int(source_coo)}'; checkpoint = work/(label+'-checkpoint')
                    run(base+(['-fluid_coo'] if source_coo else [])+['-checkpoint', checkpoint,
                        '-stop_after', 3, '-output', work/(label+'-partial.vtu')], label+'-save')
                    output = work/(label+'.vtu')
                    run(base+([] if source_coo else ['-fluid_coo'])+['-restart', checkpoint, '-output', output], label)
                    max_delta = max(max_delta, compare(modes[False], fields(output, ranks)))
                failed = work/(stem+'-failed.vtu')
                text = run(base+['-fluid_coo', '-snes_max_it', 0, '-output', failed], stem+'-failure', False)
                require('retries exhausted' in text and not failed.exists() and
                        not list(work.glob(failed.stem+'_rank*.vtu')), 'Failed solve published new output')
            print(stem, 'fields/reactions/plan and applicable Schur/restart/failure checks passed', flush=True)
    for name, case in [('poisson', 'cases/poisson/case.yaml'), ('fsi', 'cases/fsi/rigid.yaml'),
                       ('ale', 'cases/motion/shear.yaml')]:
        text = run([exe, '-case', ROOT/case, '-fluid_coo'], name+'-unsupported', False)
        require('standalone fixed-mesh fluid' in text, 'Unsupported COO option was silently ignored')
    (work/'results.json').write_text(json.dumps(dict(max_field_delta=max_delta, runs=evidence), indent=2)+'\n')
    print(f'PASS: {len(evidence)} commands; maximum field discrepancy {max_delta:.6g}')


if __name__ == '__main__':
    main()
