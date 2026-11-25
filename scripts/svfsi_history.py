"""Validate complete per-equation iteration histories from svFSI 2022.09.26."""
import math
import re
from typing import NamedTuple


class Iteration(NamedTuple):
    step: int
    number: int
    residual: float
    linear_failed: bool
    linear_iterations: int


def equation_iterations(log, equation):
    """Read the smaller of the two PIC residual norms on each contiguous correction."""
    if re.search(r'ERROR occurred|fatal error|Singular matrix detected|\bNaN\b',log,re.I):
        raise ValueError('svFSI reported a solver or input failure')
    prefix = r'^\s*'+re.escape(equation)+r'\s+'
    # OUTPUT.f marks temporary nonlinear growth above 20 dB with !...!.
    # Its independent, second column marks failures of the linear solver.
    pattern = re.compile(prefix+r'(?P<step>\d+)-(?P<it>\d+)s?\s+\S+\s+'
                         r'(?P<left>[!\[])\s*(?P<db>-?\d+)\s+(?P<relative>\S+)\s+(?P<initial>\S+)\s+'
                         r'[^\s!\]]+(?P<right>[!\]])\s+(?P<linear>[!\[])\s*(?P<linear_it>\d+)')
    prior_step = prior_iteration = 0
    for line in log.splitlines():
        if not re.match(prefix+r'\d+-',line):
            continue
        row = pattern.match(line)
        if row is None:
            raise ValueError('Unrecognized svFSI iteration record: '+line)
        growth_warning = int(row['db'])>20
        if (row['left'],row['right']) != (('!','!') if growth_warning else ('[',']')):
            raise ValueError('Inconsistent svFSI nonlinear status: '+line)
        step,iteration = map(int,row.group('step','it'))
        if not ((step==prior_step and iteration==prior_iteration+1)
                or (step==prior_step+1 and iteration==1 and (not prior_step or prior_iteration>=2))):
            raise ValueError(f'Incomplete svFSI iteration history at {equation} {step}-{iteration}')
        prior_step,prior_iteration = step,iteration
        norms = tuple(map(float,row.group('relative','initial')))
        if not all(math.isfinite(n) and n>=0 for n in norms):
            raise ValueError('Invalid svFSI normalized residual')
        yield Iteration(step, iteration, min(norms), row['linear']=='!', int(row['linear_it']))


def check_convergence(log, steps, equation='NS'):
    """Require complete steps and current residual convergence independently for each equation."""
    final = {}
    zero_corrections = 0
    for row in equation_iterations(log,equation):
        final[row.step] = row
        # GMRES.f can return without iterations when a correction is below its absolute tolerance.
        if row.linear_failed:
            if row.linear_iterations or row.residual>1e-8:
                raise ValueError(f'Unconverged svFSI linear solve at {equation} {row.step}-{row.number}, '
                                 f'{row.linear_iterations} iterations, residual {row.residual:.4g}')
            zero_corrections += 1
    if set(final)!=set(range(1,steps+1)) or not final or final[steps].number<2:
        raise ValueError(f'Incomplete svFSI time step history for {equation}, expected {steps}, found {len(final)}')
    for row in final.values():
        if row.residual>1e-8:
            raise ValueError(f'Unconverged svFSI time step at {equation} {row.step}-{row.number}, residual {row.residual:.4g}')
    return max(row.residual for row in final.values()), zero_corrections
