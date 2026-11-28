"""Single-node solver-window allocation and active-rank accounting."""
import math
from pathlib import Path
import re


def direct_memory_budget(limit):
    """Check the exclusive reference job against actual RAM and ancestor cgroup limits."""
    reserve = 32 * 2**30
    meminfo = Path('/proc/meminfo').read_text()
    host = {k: int(v)*1024 for k,v in re.findall(r'^(MemTotal|MemAvailable):\s+(\d+) kB$',meminfo,re.M)}
    if host['MemAvailable'] < limit + reserve:
        raise ValueError('Insufficient available RAM for the declared direct reference and node reserve')
    groups = []
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        hierarchy,controllers,relative = line.split(':',2)
        if hierarchy=='0' and not controllers:
            root = Path('/sys/fs/cgroup')
            cap,usage = 'memory.max','memory.current'
        elif 'memory' in controllers.split(','):
            root = Path('/sys/fs/cgroup/memory')
            cap,usage = 'memory.limit_in_bytes','memory.usage_in_bytes'
        else:
            continue
        group = root/relative.lstrip('/')
        while True:
            if (group/cap).is_file():
                value = (group/cap).read_text().strip()
                used = int((group/usage).read_text())
                ceiling = None if value=='max' else int(value)
                groups.append(dict(path=str(group),limit=ceiling,usage=used))
                if ceiling is not None and ceiling-used < limit + reserve:
                    raise ValueError(f'Insufficient cgroup headroom for direct reference: {group}')
            if group==root:
                break
            group=group.parent
    if not groups:
        raise ValueError('Unable to verify the direct reference job memory cgroup')
    return dict(host=host,cgroups=groups,process_tree_budget=limit,reserved_bytes=reserve)


def resource_hours(ranks, allocation, seconds):
    match = re.fullmatch(r'([1-9]\d*)(?:\(x1\))?', str(allocation))
    if not match or ranks <= 0 or int(match[1]) < ranks:
        raise ValueError(f'Invalid single-node allocation {allocation} for {ranks} ranks')
    if seconds is not None and (not math.isfinite(seconds) or seconds < 0):
        raise ValueError('Invalid solver wall time')
    cpus = int(match[1])
    return dict(active_ranks=ranks, allocated_cpus=cpus,
                active_rank_hours=None if seconds is None else ranks*seconds/3600,
                allocated_core_hours=None if seconds is None else cpus*seconds/3600)


def formal_resources(row):
    """Only mandatory per-correction validation and receipt reporting may be active."""
    opts = row['linear']['effective_options']
    if not row['formal'] or row.get('start_step',0)!=0 or opts.get('-linear_componentwise_error') != 'false':
        raise ValueError('Formal sample includes the extended row diagnostic or lacks a formal declaration')
    for key, value in opts.items():
        extra = ('monitor' in key or key.endswith(('_converged_reason','_report','_profile','_log_view'))
                 or key == '-log_view')
        if extra and key not in ('-linear_report','-solver_report') and value.lower() not in ('false','0'):
            raise ValueError('Detailed monitoring enabled in formal sample: '+key)
    command = row['command']
    ranks = row['ranks']
    for key, expected in (('-n', str(ranks)), ('--map-by', 'core'), ('--bind-to', 'core')):
        if command.count(key) != 1 or command[command.index(key)+1] != expected:
            raise ValueError('Nonmatching MPI layout in formal command')
    if len(set(row['affinity'])) != ranks or len(row['affinity']) != ranks:
        raise ValueError('Invalid rank affinity in formal sample')
    threads = row.get('thread_environment')
    if threads is not None and threads != dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1'):
        raise ValueError('Thread settings changed in formal sample')
    cpus = resource_hours(ranks, row['allocation'], row['T_job'])['allocated_cpus']
    return (row['job'], cpus, ranks, tuple(row['affinity']), command[0])
