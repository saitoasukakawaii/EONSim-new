"""Validate complete per-equation iteration histories from svFSI 2022.09.26."""
import math
import re


def check_convergence(log, steps, equation='NS'):
    """svFSI can write results at its iteration cap or exit zero after a fatal input error."""
    if re.search(r'ERROR occurred|fatal error|Singular matrix detected|\bNaN\b',log,re.I):
        raise ValueError('svFSI reported a solver or input failure')
    prefix = r'^\s*'+re.escape(equation)+r'\s+'
    pattern = re.compile(prefix+r'(\d+)-(\d+)s?\s+\S+\s+\[\s*-?\d+\s+'
                         r'(\S+)\s+(\S+)\s+[^\]]+\]\s+([!\[])\s*(\d+)')
    final_norms = {}
    zero_corrections = 0
    prior_step = prior_iteration = 0
    for line in log.splitlines():
        if not re.match(prefix+r'\d+-',line):
            continue
        row = pattern.match(line)
        if row is None:
            raise ValueError('Unrecognized svFSI iteration record: '+line)
        step,iteration = map(int,row.group(1,2))
        if not ((step==prior_step and iteration==prior_iteration+1)
                or (step==prior_step+1 and iteration==1 and (not prior_step or prior_iteration>=2))):
            raise ValueError('Incomplete svFSI iteration history')
        prior_step,prior_iteration = step,iteration
        norms = tuple(map(float,row.group(3,4)))
        if not all(math.isfinite(n) and n>=0 for n in norms):
            raise ValueError('Invalid svFSI normalized residual')
        # PIC.f accepts either normalization. GMRES.f can return with zero
        # iterations when the correction is already below its absolute tolerance.
        final_norms[step] = min(norms)
        if row[5]=='!':
            if int(row[6])!=0 or min(norms)>1e-8:
                raise ValueError('Unconverged svFSI linear solve: '+line)
            zero_corrections += 1
    if prior_iteration<2 or set(final_norms)!=set(range(1,steps+1)) or max(final_norms.values())>1e-8:
        raise ValueError('Incomplete or unconverged svFSI time step')
    return max(final_norms.values()), zero_corrections
