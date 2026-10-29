"""Reproducible B5 accuracy and CPU measurements; output JSON, logs and Markdown."""
import argparse
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cases/fsi'))
from generate_domains import generate
from generate_mesh import write_mesh


def metric(text, name):
    return float(re.findall(r'\b' + name + r'=([^\s]+)', text)[-1])


def pressure_error(path):
    """Exact P1 mass integral of (p_h - (1-x))^2 on the unit channel."""
    root = ET.parse(path)
    xyz = list(map(float, root.find('.//Points/DataArray').text.split()))
    pressure = list(map(float, root.find('.//PointData/DataArray[@Name="pressure"]').text.split()))
    cells = list(map(int, root.find('.//Cells/DataArray[@Name="connectivity"]').text.split()))
    integral = 0.0
    for start in range(0, len(cells), 4):
        nodes = cells[start:start+4]
        points = [xyz[3*n:3*n+3] for n in nodes]
        a, b, c = [[p[i]-points[0][i] for i in range(3)] for p in points[1:]]
        volume = abs(sum(a[i]*(b[(i+1)%3]*c[(i+2)%3]-b[(i+2)%3]*c[(i+1)%3]) for i in range(3)))/6
        errors = [pressure[n]-(1-xyz[3*n]) for n in nodes]
        integral += volume*(sum(errors)**2+sum(e*e for e in errors))/20
    return math.sqrt(integral)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--executable', type=Path, required=True)
    p.add_argument('--mpiexec', default='/usr/bin/mpiexec')
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--subdivisions', type=int, nargs='+', default=[4, 6])
    p.add_argument('--ranks', type=int, nargs='+', default=[1, 2, 4])
    a = p.parse_args()
    a.executable = a.executable.resolve()
    a.work = a.work.resolve()
    a.work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', SUPERLU_ACC_OFFLOAD='0')

    def run(command, label):
        start = time.perf_counter()
        result = subprocess.run(list(map(str, command)), env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=240)
        wall = time.perf_counter()-start
        (a.work / f'{label}.log').write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(f'{label}: {result.stdout}')
        return result.stdout, wall

    spatial, temporal, performance = [], [], []
    for n in (4, 8, 12):
        mesh = a.work / f'flow{n}.msh'
        write_mesh(mesh, n)
        case, output = a.work / f'flow{n}.yaml', a.work / f'flow{n}.vtu'
        case.write_text(json.dumps(dict(mesh=str(mesh), output=str(output), fluid=dict(mode='stokes'))))
        text, _ = run([a.executable, '-case', case, '-schur_pc', '-solver_report'], f'flow{n}')
        record = dict(n=n, cells=6*n**3, dofs=int(metric(text, 'dofs')),
                      velocity_l2=metric(text, 'velocity_l2_error'), pressure_l2=pressure_error(output),
                      pressure_drop=metric(text, 'pressure_drop'), divergence_l2=metric(text, 'divergence_l2'),
                      iterations=int(metric(text, 'linear_iterations')))
        spatial.append(record)
        print('space', json.dumps(record), flush=True)
    assert all(y['velocity_l2'] < x['velocity_l2'] and y['pressure_l2'] < x['pressure_l2']
               for x, y in zip(spatial, spatial[1:]))

    case = generate(a.work / 'time', 2)
    config = json.loads(case.read_text())
    for steps in (4, 8, 16, 32, 64):
        dt = .04/steps
        config['fsi'].update(dt=dt, steps=steps)
        case.write_text(json.dumps(config))
        text, _ = run([a.executable, '-case', case], f'time{steps}')
        record = dict(dt=dt, steps=steps, position=metric(text, 'position'), velocity=metric(text, 'velocity'))
        temporal.append(record)
        print('time', json.dumps(record), flush=True)
    for record in temporal[:-1]:
        record['position_error'] = abs(record['position']-temporal[-1]['position'])
    assert all(y['position_error'] < x['position_error'] for x, y in zip(temporal[:-2], temporal[1:-1]))

    for n in a.subdivisions:
        case = generate(a.work / f'domains{n}', n)
        config = json.loads(case.read_text())
        config['fsi'].update(steps=3)
        case.write_text(json.dumps(config))
        reference = None
        for ranks in a.ranks:
            part = a.work / f'part{n}_{ranks}'
            run([a.executable, '-case', case, '-prepare', part, '-parts', ranks], f'prepare{n}_{ranks}')
            # FD is an accuracy/performance reference, not the default implementation.
            for solver in ('direct', 'schur', 'fd'):
                if solver == 'fd' and ranks != 1:
                    continue
                name = f'domains{n}_{ranks}_{solver}'
                command = ([a.mpiexec, '-n', ranks] if ranks > 1 else []) + [
                    a.executable, '-case', case, '-partition', part, '-output', a.work / f'{name}.vtu',
                    '-solver_report', '-device_enable', 'none']
                if solver == 'schur':
                    command += ['-schur_pc']
                elif solver == 'fd':
                    command += ['-fsi_fd_tangent']
                text, wall = run(command, name)
                reports = [dict(re.findall(r'(\w+)=([^\s]+)', line)) for line in text.splitlines()
                           if line.startswith('solver_report ')]
                assert len(reports) == 3
                position = metric(text, 'position')
                if reference is None:
                    reference = position
                assert abs(position-reference) < 2e-9
                record = dict(n=n, fluid_cells=6*n**3, solid_cells=6*n**3+3, ranks=ranks, solver=solver,
                              dofs=int(reports[0]['dofs']), nnz=int(float(reports[0]['nnz'])),
                              linear_iterations=sum(int(x['linear_iterations']) for x in reports),
                              wall_seconds=wall, position=position)
                for key in ('solve_seconds', 'assembly_seconds', 'ghost_seconds'):
                    record[key] = sum(float(x[key]) for x in reports)
                for key in ('peak_rss_max_bytes', 'peak_rss_sum_bytes'):
                    record[key] = max(float(x[key]) for x in reports)
                performance.append(record)
                print('performance', json.dumps(record), flush=True)

    cpu = next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines()
                if s.startswith('model name')), platform.machine())
    result = dict(cpu=cpu, system=platform.platform(), spatial=spatial, temporal=temporal, performance=performance)
    (a.work / 'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    report = ['# B5 精度与求解记录', '', f'CPU：{cpu}；单机、每进程 BLAS/OpenMP 线程数为 1。', '',
              '运行命令：', '', '```sh', 'python3 scripts/benchmark_foundations.py --executable build/release/eonsim --work build/b5_benchmark', '```', '',
              '## 固定网格 Stokes 通道空间加密', '',
              '单位通道解析压力 p=1−x，压降为 1；压力 L2 误差采用 Tet4 质量积分精确计算。均使用 Schur/GAMG。', '',
              '| n | cells | DoFs | 速度 L2 误差 | 压力 L2 误差 | 压降 | div L2 | KSP 迭代 |',
              '|---|---|---|---|---|---|---|---|']
    for r in spatial:
        report.append(f"| {r['n']} | {r['cells']} | {r['dofs']} | {r['velocity_l2']:.6g} | {r['pressure_l2']:.6g} | {r['pressure_drop']:.6g} | {r['divergence_l2']:.6g} | {r['iterations']} |")
    report += ['', '## 独立双域 FSI 时间加密', '',
               '固定 n=2 网格，BE，终止时间 0.04；以 dt=0.000625 的位置作为数值参考，不作为解析真解。', '',
               '| dt | steps | 界面平均 x 位移 | 对最细步长的位置差 |', '|---|---|---|---|']
    for r in temporal:
        report.append(f"| {r['dt']:.6g} | {r['steps']} | {r['position']:.10g} | {r.get('position_error', 0):.6g} |")
    report += ['', '## 独立双域 FSI CPU 测量', '',
               '每项计算 3 个 dt=0.02 步。direct/Schur 默认使用解析几何与前向链式切线；fd 使用原中心差分切线和整体直接解。',
               'solve 包含显式预条件准备及 SNES；assembly 包含这段时间内残量/切线装配；ghost 是其子集。wall 还包含 MPI 启动、读入和输出。',
               'RSS 是作业中各 rank 的进程峰值；sum 是各进程峰值之和，不代表同一时刻总内存。每配置单次测量，不能据此宣称并行加速或大规模可扩展。', '',
               '| n | rank | solver | DoFs | nnz | KSP 总迭代 | solve s | assembly s | ghost s | wall s | peak RSS max/sum MiB |',
               '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in performance:
        report.append(f"| {r['n']} | {r['ranks']} | {r['solver']} | {r['dofs']} | {r['nnz']} | {r['linear_iterations']} | {r['solve_seconds']:.5g} | {r['assembly_seconds']:.5g} | {r['ghost_seconds']:.5g} | {r['wall_seconds']:.5g} | {r['peak_rss_max_bytes']/2**20:.1f}/{r['peak_rss_sum_bytes']/2**20:.1f} |")
    report += ['', '全部 FSI 对照的最终界面位移差小于 2e-9；完整节点场与力平衡的 1/2/4 rank 对照见 schur_verification。', '']
    (a.work / 'report.md').write_text('\n'.join(report))


if __name__ == '__main__':
    main()
