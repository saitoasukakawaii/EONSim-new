"""Validate pinned native one/two-rank FSI records and explicit log chains.

This intentionally supports only the linear FSI direct-record layout used by
the pinned reference. It never synthesizes a continuous log or substitutes an
iteration-limit exit for printed convergence.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setting(inputs, key):
    values = re.findall(r'^'+re.escape(key)+r': ([^\r\n]+)$', inputs, re.M)
    if len(values) != 1:
        raise ValueError('Missing or duplicate reference setting: '+key)
    return values[0]


def native_checkpoint(path):
    """Decode all rank payloads; direct-record padding is not numerical state."""
    data = path.read_bytes()
    if len(data) < 64:
        raise ValueError('Truncated native restart record')
    ranks = struct.unpack_from('<i', data)[0]
    if ranks not in (1, 2) or len(data) % ranks:
        raise ValueError('Unsupported native FSI rank count or record length')
    record_bytes = len(data)//ranks
    records, shared, first_stamp = [], None, None
    for rank in range(ranks):
        offset = rank*record_bytes
        if record_bytes < 64:
            raise ValueError('Truncated native rank record')
        stamp = struct.unpack_from('<8i', data, offset)
        nproc, equations, meshes, nodes, coupled, dofs, displacement, step = stamp
        if ((nproc, equations, meshes, coupled, dofs, displacement) != (ranks, 2, 2, 0, 7, 1)
                or nodes <= 0 or step <= 0):
            raise ValueError('Unsupported native FSI restart stamp')
        count = 2+equations+3*dofs*nodes
        payload_bytes = 32+8*count
        if payload_bytes > record_bytes:
            raise ValueError('Native restart record length differs from stamp')
        values = struct.unpack_from('<'+str(count)+'d', data, offset+32)
        # OUTPUT.f stores physical time, diagnostic CPUT()-timeP(1), then
        # equation norms. CPUT() omits the date, so only the elapsed diagnostic
        # may be negative after midnight. Never relax physical time or norms.
        if (not all(math.isfinite(value) for value in values) or
                min(values[0], *values[2:4]) < 0):
            raise ValueError('Invalid native restart time, norms or history')
        # INITIALIZE.f uses the MPI maximum payload as RECL. Ranks may have
        # different node counts and trailing bytes; elapsed times also differ.
        identity = (step, values[0], values[2], values[3])
        if shared is None:
            shared, first_stamp = identity, list(stamp[:7])
        elif identity != shared:
            raise ValueError('Native rank steps, times or equation norms disagree')
        records.append(dict(rank=rank, stamp=list(stamp[:7]), offset=offset,
                            payload_bytes=payload_bytes, serialized_values=count))
    if max(record['payload_bytes'] for record in records) != record_bytes:
        raise ValueError('Native direct-record size differs from maximum rank payload')
    result = dict(step=shared[0], time=shared[1], stamp=first_stamp,
                  bytes=len(data), serialized_values=sum(record['serialized_values'] for record in records), sha256=sha(path))
    # Preserve the original serial provenance shape. Parallel seeds must also
    # bind every rank's layout, including local node counts and padded offsets.
    if ranks == 2:
        result.update(record_bytes=record_bytes, rank_records=records)
    return result


def restart_evidence(work, export, inputs, log):
    continued = setting(inputs, 'Continue previous simulation')
    initialization = re.findall(r'^Simulation initialization file path: (.+)$', inputs, re.M)
    if continued == '0':
        if initialization or 'restart_provenance' in export:
            raise ValueError('Unrestarted input contains restart initialization')
        return None
    if continued != '1' or len(initialization) != 1:
        raise ValueError('Restart requires explicit native initialization')
    name = initialization[0]
    path = (work/name).resolve()
    if not path.is_relative_to(work.resolve()) or path.suffix != '.bin':
        raise ValueError('Restart seed must be a local binary input')
    provenance = export.get('restart_provenance', {})
    if export.get('mode') != 'linear elastic pressure tube' or name not in export['files']:
        raise ValueError('Missing native restart provenance')
    record = native_checkpoint(path)
    layout = 'serial' if record['stamp'][0] == 1 else 'two-rank'
    if provenance.get('layout') != f'svFSI-7bdb74c-{layout}-linear-fsi-i32-f64':
        raise ValueError('Missing or incompatible native restart layout')
    keys = ['sha256', 'step', 'time', 'stamp', 'bytes']
    if layout == 'two-rank':
        keys.extend(('record_bytes', 'rank_records'))
    if any(provenance.get(key) != record[key] for key in keys):
        raise ValueError('Native restart record differs from provenance')
    if record['sha256'] != export['files'][name]:
        raise ValueError('Native restart seed differs from input manifest')
    dt = float(setting(inputs, 'Time step size'))
    expected = record['step']*dt
    # The upstream clock accumulates ordinary doubles; do not label it v4 or
    # replace the exact stored time with a recomputed product.
    if (not math.isfinite(dt) or dt <= 0 or
            abs(record['time']-expected) > max(1e-12, record['step']*math.ulp(expected))):
        raise ValueError('Native restart time is inconsistent with its step')
    text = re.sub(r'\x1b\[[0-9;]*m', '', log.read_text())
    if not re.search(r'Initializing from\s+'+re.escape(name)+r'(?:\s|$)', text):
        raise ValueError('Log does not establish native restart initialization')
    return dict(record, input_name=name, path=str(path),
                scope='Exact native saved time and complete finite Yn/An/Dn record; no v4 clock claim')


def equivalent_input(inputs):
    # Only stop-step and native checkpoint execution controls may differ.
    # Physics, mesh, pressure tables, time step, tolerances and output grid stay
    # byte-identical. Full-study eligibility is checked separately below.
    controls = ('Number of time steps', 'Continue previous simulation',
                'Simulation initialization file path', 'Increment in saving restart files')
    return '\n'.join(line for line in inputs.splitlines()
                     if not any(line.startswith(key+': ') for key in controls))


def fsi_ilut_input(inputs):
    """The sole supported transition changes only the FSI preconditioner."""
    before, marker, body = inputs.partition('Add equation: FSI {\n')
    if not marker:
        raise ValueError('Backend transition requires the FSI equation')
    block, following, rest = body.partition('\nAdd equation:')
    pattern = r'^( +)Preconditioner: FSILS$'
    if len(re.findall(pattern, block, re.M)) != 1 or 'Use Trilinos for assembly:' in block:
        raise ValueError('Unsupported original FSI backend')
    block = re.sub(pattern, lambda m: m[1]+'Preconditioner: Trilinos-ILUT\n'+m[1]+'Use Trilinos for assembly: 0', block, flags=re.M)
    return before+marker+block+following+rest


def reviewed_backend_transition(item, resolve, old_inputs, new_inputs,
                                old_binary, new_binary, files, cfg, seed):
    """Bind a bounded raw-data review to this exact physical problem and layout.

    This is execution provenance, not a claim of long-run physical agreement.
    The default v1 chain continues to reject all backend changes.
    """
    if item.get('kind') != 'svfsi-fsi-ilut-reviewed-v1':
        raise ValueError('Unsupported reviewed backend transition')
    if equivalent_input(fsi_ilut_input(old_inputs)) != equivalent_input(new_inputs):
        raise ValueError('Backend transition changes more than FSI preconditioning')
    screen, review = resolve(item['screen']), resolve(item['review'])
    report_path, review_path = screen/'report.json', review/'review.json'
    if sha(report_path) != item['screen_report_sha256'] or sha(review_path) != item['review_sha256']:
        raise ValueError('Backend proof differs from its declared digest')
    report = json.loads(report_path.read_text())
    checked = json.loads(review_path.read_text())
    definition = json.loads((screen/'definition.json').read_text())
    static = json.loads((review/'static-input-check.json').read_text())
    binaries = dict(old=old_binary, ilut=new_binary)
    if (report.get('passed') is not True or report.get('eligible') is not True or
            checked.get('passed') is not True or checked.get('bounded_eligible') is not True or
            checked.get('original_restoration_exact') is not True or
            checked.get('screen_report_sha256') != sha(report_path) or
            any(v.get('binary_hashes') != binaries for v in (report, checked, definition)) or
            checked.get('source_hashes') != definition.get('source_hashes') or
            static.get('passed') is not True or
            static.get('screen_definition_sha256') != sha(screen/'definition.json')):
        raise ValueError('Missing or inconsistent independent backend proof')
    if (sha(screen/'controller.py') != definition['controller_sha256'] or
            sha(review/'controller.py') != checked['controller_sha256']):
        raise ValueError('Backend proof controller changed')
    for name, digest in definition['source_hashes'].items():
        # Bytecode caches are runtime artifacts, not portable source evidence.
        if '__pycache__' not in Path(name).parts and (
                sha(screen/'source'/name) != digest or sha(review/'source'/name) != digest):
            raise ValueError('Backend proof analysis source changed')
    if json.loads((screen/'case.json').read_text()) != cfg:
        raise ValueError('Backend proof belongs to a different source case')
    for name, digest in static['matched_original_files'].items():
        if sha(screen/name) != digest:
            raise ValueError('Backend proof mesh or source case changed')
    if set(static['matched_original_files']) != {'case.json', 'geometry.json', 'fluid.msh', 'solid.msh'}:
        raise ValueError('Incomplete backend proof geometry inventory')
    if sha(screen/'scales.json') != static['scales_sha256']:
        raise ValueError('Backend proof normalization changed')
    if definition['ranks'] != seed['stamp'][0]:
        raise ValueError('Backend proof rank count differs from restart')
    layout_keys = ('stamp', 'bytes', 'record_bytes', 'rank_records')
    if not definition.get('seeds') or any(
            any(saved.get(k) != seed.get(k) for k in layout_keys)
            for saved in definition['seeds'].values()):
        raise ValueError('Backend proof native layout differs from restart')

    # Screen output controls differ from production only to retain every proof
    # state. Production-to-production output controls remain checked above.
    def screen_input(text):
        return '\n'.join(line for line in equivalent_input(text).splitlines()
                         if not line.startswith('Start saving after time step: '))
    for label, expected in (('old', old_inputs), ('ilut', new_inputs)):
        directory = screen/label
        inputs = (directory/'svFSI.inp').read_text()
        manifest = json.loads((directory/'export.json').read_text())
        if screen_input(inputs) != screen_input(expected):
            raise ValueError('Backend proof uses different physical or solver inputs')
        excluded = {'svFSI.inp', setting(inputs, 'Simulation initialization file path')}
        if {k:v for k,v in manifest['files'].items() if k not in excluded} != files:
            raise ValueError('Backend proof input files differ from the chain')
        for name, digest in manifest['files'].items():
            if sha(directory/name) != digest:
                raise ValueError('Backend proof input bytes changed')

    def bounded(value, limit):
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value < limit
    limits = dict(maximum_absolute_nodal=2e-9, maximum_normalized_mass_rms=1e-8,
                  maximum_native_history_difference=2e-9, maximum_saved_equation_norm_difference=2e-9)
    for name, states in (('backend', 100), ('candidate-replay', 10)):
        a, b = report['comparisons'][name], checked['pairs'][name]
        if (a.get('passed') is not True or a.get('states') != states or b.get('states') != states or
                a.get('exact_native_time') is not True or b.get('exact_native_time') is not True or
                any(not bounded(a.get(k), limit) or a.get(k) != b.get(k) for k, limit in limits.items())):
            raise ValueError('Backend proof field or native-history gate failed')
        if name == 'candidate-replay' and (
                a.get('bitwise_algorithm_except_elapsed_and_padding') is not True or
                b.get('bitwise_algorithm_except_elapsed_and_nonstate_padding') is not True or
                any(a[k] != 0 for k in limits)):
            raise ValueError('Backend proof does not establish exact candidate replay')
    restored = report['original_restoration']
    if (restored.get('bitwise_algorithm_except_elapsed_and_padding') is not True or
            restored.get('exact_native_time') is not True or
            restored.get('maximum_native_history_difference') != 0 or
            restored.get('maximum_saved_equation_norm_difference') != 0):
        raise ValueError('Backend proof did not reproduce the actual original endpoint')
    if set(report['resources']) != {'old', 'ilut', 'replay'}:
        raise ValueError('Backend proof omits a numerical execution receipt')
    receipts = [*report['resources'].values(), json.loads((review/'review.resource.json').read_text())]
    for receipt in receipts:
        if (receipt.get('returncode') != 0 or receipt.get('remaining_scope_members') != [] or
                receipt.get('scope_seen') is not True or not receipt.get('memory_events') or
                receipt.get('memory_max_bytes') != 2*1024**3 or
                receipt.get('memory_swap_max_bytes') != 0 or
                any(int(line.split()[1]) != 0 for line in receipt['memory_events'].splitlines())):
            raise ValueError('Backend proof resource execution did not finish cleanly')
    seconds = [report['resources'][name]['wall_seconds'] for name in ('old', 'ilut')]
    if any(not bounded(value, float('inf')) or value == 0 for value in seconds):
        raise ValueError('Invalid backend proof timing')
    ratio = seconds[1]/seconds[0]
    if ratio > .9 or report['cost_ratio'] != ratio or checked['cost_ratio'] != ratio:
        raise ValueError('Backend proof cost gate failed')
    first, last = definition['first_step'], definition['last_step']
    if type(first) is not int or type(last) is not int or first < 2 or last-first+1 != 100 or last > cfg['fsi']['steps']:
        raise ValueError('Invalid backend proof interval')
    from audit_svfsi_convergence import analyze
    for label, begin in (('old', first), ('ilut', first), ('replay', last-9)):
        convergence = analyze(screen/label, screen/(label+'.log'), first_step=begin, last_step=last)
        if not convergence['passed']:
            raise ValueError('Backend proof has unconverged equation rows')
    # Require the raw records actually checked by the independent reviewer,
    # rather than accepting a report with an empty or partial hash inventory.
    evidence = {Path(name).resolve(): digest for name, digest in checked['evidence_hashes'].items()}
    if len(evidence) != len(checked['evidence_hashes']):
        raise ValueError('Backend proof repeats an aliased evidence path')
    required = [screen/label/'results'/f'{prefix}_{step}.{suffix}'
                for label, begin in (('old', first), ('ilut', first), ('replay', last-9))
                for step in range(begin, last+1)
                for prefix, suffix in (('result', 'vtu'), ('stFile', 'bin'))]
    for label in ('old', 'ilut', 'replay'):
        directory = screen/label
        inputs = (directory/'svFSI.inp').read_text()
        required.extend((directory/'svFSI.inp', directory/'export.json',
                         directory/setting(inputs, 'Simulation initialization file path'), screen/(label+'.log')))
    for p in required:
        if p.resolve() not in evidence:
            raise ValueError('Backend proof omits a reviewed raw state')
    for name, digest in evidence.items():
        if sha(name) != digest:
            raise ValueError('Reviewed backend raw evidence changed')
    return dict(kind=item['kind'], screen=str(screen), review=str(review),
                screen_report_sha256=sha(report_path), review_sha256=sha(review_path),
                binary_hashes=binaries, ranks=definition['ranks'], proof_first_step=first,
                proof_last_step=last, cost_ratio=ratio,
                scope='Reviewed bounded execution transition only; all long-run convergence and physical gates remain required')


def analyze_chain(path, *, expected_work=None, expected_steps=None):
    from audit_svfsi_convergence import analyze, PIN
    chain = json.loads(path.read_text())
    schema = chain.get('schema')
    if schema not in ('svfsi-native-restart-chain-v1', 'svfsi-native-restart-chain-v2'):
        raise ValueError('Unsupported restart chain schema')
    segments = chain.get('segments', [])
    if len(segments) < 2:
        raise ValueError('Restart chain requires original and resumed segments')
    final_step = chain.get('final_step')
    if type(final_step) is not int or final_step < 1:
        raise ValueError('Invalid restart chain final step')
    if expected_steps is not None and final_step != expected_steps:
        raise ValueError('Restart chain does not cover requested study')
    resolve = lambda value: (path.parent/Path(value)).resolve()
    target = resolve(chain['target_work'])
    if expected_work is not None and target != expected_work.resolve():
        raise ValueError('Restart chain belongs to a different output directory')
    results, boundaries, transitions = [], [], []
    previous = None
    previous_binary = None
    shared_files = normalized = source_case = None
    next_step = 1
    for item in segments:
        binary = item.get('binary_sha256')
        transition = item.get('execution_transition')
        if schema.endswith('v1') and (binary is not None or transition is not None):
            raise ValueError('Execution identity requires explicit restart chain v2')
        if schema.endswith('v2') and (not isinstance(binary, str) or not re.fullmatch('[0-9a-f]{64}', binary)):
            raise ValueError('Restart chain v2 requires each execution binary digest')
        work, log = resolve(item['work']), resolve(item['log'])
        first, last = item['first_step'], item['last_step']
        if type(first) is not int or type(last) is not int or first != next_step or not first <= last <= final_step:
            raise ValueError('Restart chain has a gap, overlap or invalid range')
        report = analyze(work, log, first_step=first, last_step=last)
        export = json.loads((work/'export.json').read_text())
        inputs = (work/'svFSI.inp').read_text()
        if 'source-case.json' not in export['files']:
            raise ValueError('Restart chain requires hashed source case')
        cfg = json.loads((work/'source-case.json').read_text())
        excluded = {'svFSI.inp'}
        if report['restart'] is not None:
            excluded.add(report['restart']['input_name'])
        files = {name:digest for name, digest in export['files'].items() if name not in excluded}
        physics = equivalent_input(inputs)
        if previous is None:
            if report['restart'] is not None or transition is not None:
                raise ValueError('Restart chain must begin with the original run')
            shared_files, normalized, source_case = files, physics, cfg
        else:
            if files != shared_files or cfg != source_case:
                raise ValueError('Reference physics or input files differ across restart')
            seed = report['restart']
            if seed is None or seed['step'] != first-1:
                raise ValueError('Restart chain segment lacks its boundary seed')
            prev_work, prev_inputs = previous
            if transition is not None:
                proof = reviewed_backend_transition(transition, resolve, prev_inputs, inputs,
                    previous_binary, binary, shared_files, source_case, seed)
                transitions.append(dict(step=first-1, **proof))
                normalized = physics
            elif physics != normalized or binary != previous_binary:
                raise ValueError('Reference physics or input files differ across restart')
            folder = setting(prev_inputs, 'Save results in folder')
            if re.search(r'^Restart file name:', prev_inputs, re.M):
                raise ValueError('Custom reference restart names are unsupported')
            saved = prev_work/folder/f'stFile_{first-1}.bin'
            if native_checkpoint(saved)['sha256'] != seed['sha256']:
                raise ValueError('Restart seed is not the preceding segment checkpoint')
            output = prev_work/folder/f'result_{first-1}.vtu'
            boundary = dict(step=first-1, checkpoint=str(saved), checkpoint_sha256=sha(saved))
            if output.exists():
                boundary.update(output=str(output), output_sha256=sha(output))
            boundaries.append(boundary)
        results.append(dict(work=str(work), log=str(log), **report))
        previous = work, inputs
        previous_binary = binary
        next_step = last+1
    if next_step != final_step+1 or previous[0] != target:
        raise ValueError('Restart chain is incomplete or targets the wrong final segment')
    declared = source_case['fsi']['steps']
    if final_step > declared or float(setting(previous[1], 'Time step size')) != source_case['fsi']['dt']:
        raise ValueError('Restart chain differs from source-case time grid')
    if expected_steps is not None and final_step != declared:
        raise ValueError('Restart prefix is not full-study convergence evidence')
    equations = results[0]['equations']
    failures = [row for result in results for row in result['failed_equation_steps']]
    result = dict(svfsi_commit=PIN, steps=final_step, first_step=1, last_step=final_step,
                passed=all(result['passed'] for result in results), segments=results,
                equations=equations, final_equation_rows=sum(result['final_equation_rows'] for result in results),
                iteration_rows=sum(result['iteration_rows']-result['excluded_tail']['iteration_rows'] for result in results),
                iteration_limit_rows=sum(result['iteration_limit_rows'] for result in results),
                failed_equation_steps=failures,
                maximum_iterations={name:max(result['maximum_iterations'][name] for result in results) for name in equations},
                maximum_final_relative_ratio={name:max(result['maximum_final_relative_ratio'][name] for result in results) for name in equations},
                input_manifest_sha256=results[-1]['input_manifest_sha256'],
                boundaries=boundaries, full_source_study=final_step == declared,
                chain_sha256=sha(path), analysis_source_sha256=sha(Path(__file__)),
                scope='Contiguous selected original/resumed segments with unchanged inputs and exact native seed hashes; original excluded tails remain explicit; no physical qualification')
    if schema.endswith('v2'):
        result.update(execution_binary_sha256=[item['binary_sha256'] for item in segments],
                      execution_transitions=transitions,
                      scope='Contiguous original/resumed segments with unchanged physical inputs, exact native seeds and explicitly reviewed execution transitions; excluded tails retained; no physical qualification')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze_chain(args.chain.resolve())
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key:value for key, value in result.items() if key != 'segments'}))
    if not result['passed']:
        raise SystemExit('Reference chain convergence is not established')
