"""Verify the compact C trajectory archives and print one cumulative row per qualified window."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

from c_archive_lineage import audit_archive_pair
from tube_protocol import BLOCKS, HERE, audit_row, budget, select


GATES={'inlet','outlet','pressure','area','mass','interface','circuit'}
# Independent C4 reference/candidate field inventory from phase-05 jobs 497/500.
NODES={'fluid':113825,'solid':63945}


def physical_passed(gates):
    return set(gates)==GATES and all(0<=v<=1 for v in gates.values())


def checked_corrections(linear,policy,expected):
    rows=linear['rows']
    reports=linear['solver_reports']
    states=linear['accepted_steps']
    finals=linear['nonlinear_fields']
    if (len(reports)!=len(expected) or len(states)!=len(expected) or len(finals)!=4*len(expected)
            or linear['protocol_hash']!=policy['hash'] or linear['corrections']!=len(rows)):
        raise ValueError('Incomplete correction or nonlinear reports')
    offset=0
    worst=0.
    total=0
    for ordinal,(step,state,report) in enumerate(zip(expected,states,reports)):
        n=int(state['snes_iterations'])
        block=rows[offset:offset+n]
        iterations=sum(int(c['ksp_iterations']) for c in block)
        if (n<0 or int(state['fsi_step'])!=step or int(report['step'])!=step or int(report['attempt'])!=1
                or report['protocol_hash']!=policy['hash'] or int(report['snes_reason'])<=0
                or int(report['linear_started'])!=n or int(report['linear_completed'])!=n or len(block)!=n
                or int(report['linear_iterations'])!=iterations or (n and block[-1]['ksp_reason']!=report['ksp_reason'])):
            raise ValueError(f'Inconsistent solver report at C step {step}')
        final=finals[4*ordinal:4*ordinal+4]
        if {f['name'] for f in final}!=BLOCKS or any(
                int(f['accepted'])!=1 or not (0<=float(f['rms'])<=float(f['limit'])
                and 0<=float(f['constraint_max'])<=float(f['constraint_limit'])) for f in final):
            raise ValueError(f'Failed nonlinear field at C step {step}')
        for i,c in enumerate(block,1):
            tags=('step','newton','solve','attempt','pc_attempt')
            if tuple(int(c[k]) for k in tags)!=(step,i,i,1,1):
                raise ValueError(f'Misaligned linear correction at C step {step}/{i}')
            worst=max(worst,audit_row(c,policy))
            fields=c['fields']
            if (len(fields)!=4 or {f['name'] for f in fields}!=BLOCKS or any(
                    f[k]!=c[k] for f in fields for k in (*tags,'protocol_hash'))
                    or sum(int(f['equation_rows'])+int(f['constraint_rows']) for f in fields)!=int(report['dofs'])):
                raise ValueError(f'Incomplete original-equation blocks at C step {step}/{i}')
            wide=float(c['wide_norm'])
            backward=float(c['backward_error'])
            if not (math.isfinite(wide) and wide>=0 and math.isfinite(backward) and backward>=0
                    and (policy['mode']!='lu' or wide<=float(c['limit']))):
                raise ValueError(f'Failed high-precision diagnostic at C step {step}/{i}')
        total+=iterations
        offset+=n
    if offset!=len(rows) or total!=linear['ksp_iterations'] or worst!=linear['max_ratio']:
        raise ValueError('Cumulative KSP or residual audit differs from the original receipt')


def read_packed(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def checked_window(entry, index, start, end):
    row = entry['data']
    name = entry['receipt']
    # Match the original Linux receipt encoding from paired_tube.save().
    raw = (json.dumps(row, indent=2, allow_nan=False) + '\n').encode()
    digest = hashlib.sha256(raw).hexdigest()
    expected = list(range(start+1, end+1))
    policy = select('CALIBRATED-v2', row['profile'])
    linear = row['linear']
    if (index[name] != dict(bytes=len(raw), sha256=digest) or row['policy'] != policy
            or row['formal'] or row['accepted_steps'] != expected
            or row['status'] != 'exited' or row['exit_code'] != 0 or not 0 < row['rss_peak'] <= row['rss_limit']
            or not physical_passed(row['physical'])):
        raise ValueError(f'Inconsistent C window, physical checks or original receipt: {name}')
    checked_corrections(linear,policy,expected)
    return row


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--through', type=int, choices=(20,32,100,224), required=True)
    cli.add_argument('--root', type=Path, default=HERE)
    args = cli.parse_args()
    spec_path = HERE/'output-fields-v2.1.json'
    spec_text = spec_path.read_text(encoding='utf-8')
    spec = json.loads(spec_text)
    spec_sha = hashlib.sha256(spec_text.encode()).hexdigest()
    profiles = ('lu','fixed-1e-6')
    lineage = None
    seconds = dict.fromkeys(profiles,0.)
    corrections = ksp = start = 0
    rows = []
    for end in (20,32,100,224):
        folder = args.root/f'c{end}'
        entries = [e for e in read_packed(folder/'run-receipts.json.gz') if e['receipt'].endswith('/window.json')]
        index = read_packed(folder/'log-index.json.gz')
        lineage = audit_archive_pair(entries,index,start,end,lineage)
        windows = {}
        for entry in entries:
            profile = entry['data']['profile']
            r = checked_window(entry,index,start,end)
            windows[profile] = r
            seconds[profile] += r['T_job']
            if not math.isclose(r['cumulative_T_job'],seconds[profile],rel_tol=1e-14):
                raise ValueError(f'Incorrect cumulative solve time: C{end} {profile}')
        direct, fixed = (windows[p] for p in profiles)
        cmp = fixed['comparison']
        phases = cmp['full_field_differences']
        if (any(fixed[k] != direct[k] for k in ('binary','compiled_source','inputs','partition','archive_receipt'))
                or cmp['output_field_budget_sha256'] != spec_sha or cmp['protocol_hash'] != fixed['policy']['hash']
                or not physical_passed(cmp['physical_gates'])
                or [p['step'] for p in phases] != list(range(start+4,end+1,4))):
            raise ValueError(f'Inconsistent independent C{end} comparison')
        limits = {f'{region}/{field}': budget(fixed['policy'],quantity)*(2*math.pi/spec['period_seconds'])**order
                  for region,fields in spec['regions'].items() for field,(quantity,order) in fields.items()}
        for phase in phases:
            if set(phase) != {'step',*limits}:
                raise ValueError(f'Missing full fields at C step {phase["step"]}')
            for field,limit in limits.items():
                v = phase[field]
                if (v['nodes']!=NODES[field.split('/')[0]] or v['limit']!=limit
                        or not (0<=v['rms']<=limit and 0<=v['maximum']<=limit)):
                    raise ValueError(f'Full-field budget exceeded at C step {phase["step"]}, {field}')
        corrections += fixed['linear']['corrections']
        ksp += fixed['linear']['ksp_iterations']
        steady={}
        if end==224:
            for profile,r in windows.items():
                periodic=r['periodic']
                changes=periodic['normalized_change']
                if (periodic['cycles_completed']!=7 or periodic['samples_per_cycle']!=8 or periodic['limit']!=1e-3
                        or set(changes)!={'flow_over_inlet','area_over_static','inlet_pressure_over_RQ',
                                          'interface_displacement_over_static_radius_change'}
                        or not all(math.isfinite(v) and v>=0 for v in changes.values())
                        or periodic['steady']!=all(v<1e-3 for v in changes.values())):
                    raise ValueError(f'Inconsistent seventh-cycle diagnostic for {profile}')
                steady[profile]=periodic['steady']
        rows.append(dict(steps=end,segment_start=start,lu_job=direct['job'],fixed_job=fixed['job'],
                         fixed_newton_total=corrections,fixed_ksp_total=ksp,lu_seconds_total=seconds['lu'],
                         fixed_seconds_total=seconds['fixed-1e-6'],saved_phases_total=end//4,
                         segment_pressure_max_Pa=max(p['fluid/pressure']['maximum'] for p in phases),
                         seven_cycles_completed=end==224,lu_steady=steady.get('lu'),fixed_steady=steady.get('fixed-1e-6')))
        if end==args.through:
            break
        start=end
    output=csv.DictWriter(sys.stdout,fieldnames=rows[0],lineterminator='\n')
    output.writeheader()
    output.writerows(rows)


if __name__=='__main__':
    main()
