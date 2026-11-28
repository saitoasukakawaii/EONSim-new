"""Inspect job 438's MS failure and screen the native MS and FS solvers separately."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np

DATA = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(DATA/'fsi-scalable-02'), str(DATA.parents[2]/'scripts')]
from paired_tube import digest, read_mesh, run, save
from svfsi_history import check_convergence, equation_iterations


def mesh_summary(mesh):
    """Initial free Tet4 elasticity, modulo a common positive scalar (MESH.f/LELAS3D)."""
    nodes, cells, faces = read_mesh(mesh)
    tags = {1:(0,1,2), 2:(0,1,2), 3:(0,1,2), 5:(1,), 6:(2,)}
    # A solid-domain mask fixes every structural node, including the common interface.
    # Only the nonzero free fluid block enters this calculation.
    ids = {n:i for i,n in enumerate(nodes)}
    xyz = np.asarray(list(nodes.values()))
    tet = np.array([[ids[n] for n in cell] for cell in cells])
    free = np.ones(xyz.shape, dtype=bool)
    for tag, face in faces:
        free[np.ix_([ids[n] for n in face], tags[tag])] = False
    diff = xyz[tet[:,1:]] - xyz[tet[:,0,None]]
    grad = np.linalg.inv(diff).transpose(0,2,1)
    grad = np.concatenate((-grad.sum(axis=1,keepdims=True), grad), axis=1)
    # MESH.f uses the reference quadrature weight, without multiplication by det(J).
    # Remove the common factor w*mu*af*beta*dt^2. rho=0 and nu=.3 for this deck.
    lambda_over_mu = 2*.3/(1-2*.3)
    local_diag = (grad**2).sum(axis=2,keepdims=True) + (1+lambda_over_mu)*grad**2
    diag = np.zeros(xyz.shape)
    np.add.at(diag, tet, local_diag)
    # A smooth axial trial obeying the end and wall constraints gives an upper
    # bound on the smallest eigenvalue of D^(-1/2) K D^(-1/2).
    x,y,z = xyz.T
    u = np.zeros_like(xyz)
    u[:,0] = np.sin(np.pi*x/.12)*(1-(y*y+z*z)/.01**2)
    u[~free] = 0
    du = np.einsum('tai,taj->tij',u[tet],grad)
    energy = ((du**2).sum() + np.einsum('tij,tji->',du,du)
              + lambda_over_mu*(np.trace(du,axis1=1,axis2=2)**2).sum())
    rq = float(energy/(diag*u*u).sum())
    d = diag[free]
    if not 0 < rq or not np.isfinite(d).all() or d.min() <= 0:
        raise ValueError('Nonpositive or nonfinite native free-block diagnostic')
    return dict(fluid_nodes=len(nodes), fluid_cells=len(cells), free_components=int(free.sum()),
                free_diagonal_range_without_common_factor=[float(d.min()),float(d.max())],
                free_diagonal_ratio=float(d.max()/d.min()), smooth_trial_rayleigh=rq,
                jacobi_condition_lower_bound=max(1., 1/rq),
                scope='Cold, zero-deformation tetrahedral free matrix reconstructed from geometry; native RHS unavailable.')


def history(folder):
    out = folder/'32-procs'
    lines = (out/'histor.dat').read_text(errors='replace')
    result = {}
    for eq in ('MS','FS'):
        events = list(equation_iterations(lines,eq))
        fractions = re.findall(r'^\s*' + eq + r'\s+\d+-\d+s?\s+\S+\s+[!\[]\s*-?\d+\s+\S+\s+\S+\s+([^\s!\]]+)[!\]]',lines,re.M)
        if len(fractions) != len(events):
            raise ValueError('Incomplete native residual columns')
        rows = []
        for event, value in zip(events,fractions):
            ratio = float(value)
            if not math.isfinite(ratio) or ratio < 0:
                raise ValueError('Invalid native scaled residual')
            rows.append(dict(**event._asdict(), scaled_linear_ratio=ratio))
        result[eq] = rows
    rcr = out/'RCR.dat'
    times = [float(s.split()[0]) for s in rcr.read_text().splitlines() if s.strip()] if rcr.exists() else []
    if any(abs(t-i/32) > 1e-7 for i,t in enumerate(times,1)):
        raise ValueError('Incomplete native RCR times')
    result['completed_rcr_steps'] = len(times)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inspect','probe','probe-bipn'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    old = Path.home()/'workspace/fsi-scalable-04-runs/native-B850'
    b = Path.home()/'workspace/fsi-scalable-02-runs/B20'
    index = json.loads((DATA/'fsi-scalable-04/tube-log-index.json').read_text())
    prior = json.loads((old/'run.json').read_text())
    for n in ('run.json','32-procs/histor.dat','32-procs/RCR.dat','svFSI.inp'):
        if digest(old/n) != index['$HOME/workspace/fsi-scalable-04-runs/native-B850/'+n]['sha256']:
            raise ValueError(f'Changed archive {n}')
    report = dict(source_job=438, svfsi_revision='7bdb74cdd517310d6bf32c0bb7d42072aeac8658',
                  algorithm='Native FSILS CG with diagonal scaling',
                  relative_tolerance=1e-10, absolute_tolerance=1e-23, max_iterations=2000,
                  compiled_with_trilinos=False, native_mesh_poisson=.3,
                  deck_sha256=digest(old/'svFSI.inp'), history_sha256=digest(old/'32-procs/histor.dat'),
                  rcr_sha256=digest(old/'32-procs/RCR.dat'), source_binary_sha256=prior['binary_sha256'])
    if args.mode == 'inspect':
        mesh = b/'prepared/eon/fluid.msh'
        report['mesh_sha256'] = digest(mesh)
        if report['mesh_sha256'] != json.loads((b/'summary.json').read_text())['inputs']['eon/fluid.msh']:
            raise ValueError('Changed archived mesh')
        report.update(matrix=mesh_summary(mesh), native=history(old))
        save(args.output, report)
        return
    job = os.environ.get('SLURM_JOB_ID')
    if not job or len(os.sched_getaffinity(0)) != 32:
        parser.error('requires 32 physical cores under Slurm')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    cmd = prior['command']
    if digest(Path(cmd[-2])) != prior['binary_sha256']:
        raise ValueError('svFSI binary changed')
    for name, expected in prior['inputs'].items():
        if digest(old/name) != expected:
            raise ValueError(f'Changed frozen native input {name}')
        shutil.copyfile(old/name,root/name)
    deck = root/'svFSI.inp'
    text = deck.read_text()
    window = 'Number of time steps: 20'
    marker = 'LS type: CG {'
    if text.count(window) != 1 or text.count(marker) != 1:
        raise ValueError('Unexpected native input deck')
    text = text.replace(window,'Number of time steps: 1').replace(marker,marker+'\n      Preconditioner: row-column-scaling')
    if args.mode == 'probe-bipn':
        # The pinned svFSI_master.inp gives a BIPN example for its FSI equation.
        # Keep both physical equations and their outer/absolute tolerances.
        if text.count('LS type: GMRES {') != 1 or text.count('Krylov space dimension: 850') != 1:
            raise ValueError('Unexpected FS block')
        text = text.replace('LS type: GMRES {','LS type: BIPN {').replace('Krylov space dimension: 850',
            'Krylov space dimension: 50\n      NS-GM tolerance: 1e-3\n      NS-GM max iterations: 3'
            '\n      NS-CG tolerance: 1e-3\n      NS-CG max iterations: 500')
    deck.write_text(text)
    fs = 'BIPN' if args.mode == 'probe-bipn' else 'GMRES'
    budget = 120 if fs == 'BIPN' else 360
    report.update(job=job, affinity=sorted(os.sched_getaffinity(0)), inputs={n:digest(root/n) for n in prior['inputs']},
                  candidate='MS CG with RCS, FS '+fs, scope='single-step native linear screen only',
                  limits=dict(seconds=budget,rss_bytes=8*2**30))
    os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    try:
        run(root,cmd,report,budget,8*2**30)
        report['native'] = history(root)
        hist = (root/'32-procs/histor.dat').read_text()
        if ('Using preconditioner: RCS' not in hist or 'Using linear solver: '+fs not in hist
                or report['native']['completed_rcr_steps'] != 1):
            raise ValueError('Missing effective MS scaling or incomplete diagnostic window')
        # NSSOLVER.f can set its reported norm to zero after loss of definiteness.
        if 'unexpected behavior in FSILS' in (root/'solve.log').read_text(errors='replace'):
            raise ValueError('Native BIPN reported an invalid residual decomposition')
        report['convergence'] = {eq:check_convergence(hist,1,eq) for eq in ('MS','FS')}
        report['native_linear_screen'] = 'passed'
    except Exception as error:
        report.update(native_linear_screen='failed',diagnosis=str(error))
        if (root/'32-procs/histor.dat').exists():
            try:
                report['native'] = history(root)
            except ValueError as parse_error:
                report['history_error'] = str(parse_error)
        raise
    finally:
        save(root/'native-mesh.json',report)


if __name__ == '__main__':
    main()
