"""Validate the measured single-owner GAMG coarse layout for each frozen tube."""
import math
from tube_protocol import records


EXPERIMENT='single-rank-v1'
# Rows were measured on the original field splits before testing Telescope.
# The respective baselines are A20 at 4 ranks, B20 at 32 and C4 at 64.
COARSE_FIELDS = (
    'fieldsplit_fluid_fieldsplit_velocity_mg_coarse_',
    'fieldsplit_fluid_fieldsplit_pressure_mg_coarse_',
    'fieldsplit_solid_mg_coarse_',
    'fieldsplit_mesh_mg_coarse_',
)
COARSE_ROWS = {4: (8, 5, 8, 18), 32: (42, 12, 39, 10), 64: (11, 3, 14, 50)}


COARSE_KRYLOV = {'ksp_type': 'gmres', 'pc_type': 'jacobi', 'ksp_rtol': '1e-10',
                 'ksp_max_it': '200', 'ksp_norm_type': 'unpreconditioned'}


def solver_flags(ranks):
    flags = []
    wrapper = {'ksp_type': 'preonly', 'ksp_norm_type': 'none', 'pc_type': 'telescope',
               'pc_telescope_reduction_factor': str(ranks), 'pc_telescope_ignore_dm': 'true'}
    for prefix in COARSE_FIELDS:
        for key, value in wrapper.items():
            flags.extend(['-' + prefix + key, value])
        for key, value in COARSE_KRYLOV.items():
            flags.extend(['-' + prefix + 'telescope_' + key, value])
    return flags


def coarse_receipt(log, ranks, steps, wrapped, effective_options):
    """Verify ownership, actual inner options, and the final coarse solve on each step."""
    if ranks not in COARSE_ROWS:
        raise ValueError('Undeclared GAMG coarse layout')
    parents = ('preonly', 'telescope') if wrapped else ('gmres', 'jacobi')
    result = {}
    for prefix, rows in zip(COARSE_FIELDS, COARSE_ROWS[ranks]):
        inner_prefix = '-' + prefix + ('telescope_' if wrapped else '')
        for key, expected in COARSE_KRYLOV.items():
            if effective_options.get(inner_prefix + key) != expected:
                raise ValueError('Unexpected effective coarse Krylov option: ' + inner_prefix + key)
        result[prefix] = dict(rows=rows, owner=0, krylov_communicator=1 if wrapped else ranks,
                              last_iterations=[], last_reported_norms=[], last_ksp_reasons=[])
    # Synchronized solver_node records follow their solver_report. Check each
    # step individually so a duplicate tree cannot stand in for a missing one.
    reports = ('\n' + log).split('\nsolver_report ')
    if len(reports) != steps + 1:
        raise ValueError('Incomplete set of coarse solver reports')
    for step, report in enumerate(reports[1:], 1):
        header, _, body = report.partition('\n')
        if int(records(['solver_report ' + header], 'solver_report ')[0]['step']) != step:
            raise ValueError('Unexpected step in coarse solver report')
        nodes = records(body.splitlines(), 'solver_node ')
        for prefix, field in result.items():
            rows = field['rows']
            parent = [node for node in nodes if node['prefix'] == prefix]
            if sorted(int(node['rank']) for node in parent) != list(range(ranks)):
                raise ValueError('Missing coarse parent on an active rank: ' + prefix)
            for node in parent:
                if (int(node['comm_size']) != ranks or (node['ksp'], node['pc']) != parents or
                        int(node['ksp_reason']) <= 0 or int(node['pc_reason']) != 0 or
                        int(node['operator_rows']) != rows or
                        int(node['operator_local_rows']) != (rows if int(node['rank']) == 0 else 0)):
                    raise ValueError('Field coarse solver or ownership changed: ' + prefix)
            if wrapped:
                inner = [node for node in nodes if node['prefix'] == prefix + 'telescope_']
            else:
                inner = [node for node in parent if int(node['rank']) == 0]
            if len(inner) != 1:
                raise ValueError('Missing or duplicate effective coarse Krylov solve: ' + prefix)
            node = inner[0]
            iterations = int(node['last_iterations'])
            norm = float(node['reported_norm'])
            reason = int(node['ksp_reason'])
            if (int(node['rank']) != 0 or int(node['comm_size']) != field['krylov_communicator'] or
                    (node['ksp'], node['pc']) != ('gmres', 'jacobi') or int(node['norm_type']) != 2 or
                    int(node['operator_local_rows']) != rows or int(node['operator_rows']) != rows or
                    int(node['pc_reason']) != 0 or reason not in (2, 3) or not 0 <= iterations <= 200 or
                    not math.isfinite(norm) or norm < 0):
                raise ValueError('Effective coarse GMRES/Jacobi differs from the qualified solver: ' + prefix)
            field['last_iterations'].append(iterations)
            field['last_reported_norms'].append(norm)
            field['last_ksp_reasons'].append(reason)
    return result
