"""Archive all polygon-reference attempts and make a provenance-bound figure."""
import hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.sched_setaffinity(0, {23})
root = Path(__file__).resolve().parents[2]
work = Path('/home/tfblab633/EONSim-prod48-20261107')
base = 'womersley-polygon-reference-fa9646d'
final = work / (base + '-attempt4')
assert json.loads((work / 'womersley-polygon-reference-retry4-current.json').read_text())['state'] == 'completed'
report = json.loads((final / 'summary.json').read_text())
assert report['passed']
out = work / 'womersley-polygon-evidence-fa9646d'
assert not out.exists()
out.mkdir()
shutil.copy2(__file__, out / 'capture-polygon-reference.py')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, axes = plt.subplots(2, 2, figsize=(10.4, 7.8))
colors = {48: '#1d628c', 96: '#c35d27'}
inputs = {}
for sectors in (48, 96):
    path = final / f's{sectors}' / 'levels.json'
    inputs[str(path)] = digest(path)
    levels = json.loads(path.read_text())
    x = [d['p2_dofs'] for d in levels]
    for alpha in (1, 2):
        values = [d['results'][str(alpha)] for d in levels]
        style = '-' if alpha == 1 else '--'
        marker = 'o' if alpha == 1 else 's'
        kwargs = dict(color=colors[sectors], linestyle=style, marker=marker,
                      markersize=4, label=f'S{sectors}, alpha={alpha}')
        axes[0, 0].semilogx(x, [100*v['relative_velocity_l2_on_polygon'] for v in values], **kwargs)
        axes[0, 1].semilogx(x, [100*v['flow_amplitude_relative_error'] for v in values], **kwargs)
        axes[1, 0].loglog(x[1:], [v['successive_relative_field_difference'] for v in values[1:]], **kwargs)
        axes[1, 1].semilogx(x, [v['flow_phase_difference_degrees'] for v in values], **kwargs)
axes[0, 0].set_title('Polygon vs circle: velocity field')
axes[0, 0].set_ylabel('Relative L2 difference on polygon (%)')
axes[0, 1].set_title('Polygon vs circle: flow amplitude')
axes[0, 1].set_ylabel('Relative amplitude difference (%)')
axes[1, 0].set_title('Observed reference resolution')
axes[1, 0].set_ylabel('Successive field difference / circle norm')
axes[1, 0].axhline(1e-4, color='#555555', linewidth=1, linestyle=':', label='Declared resolution criterion')
axes[1, 1].set_title('Polygon vs circle: flow phase')
axes[1, 1].set_ylabel('Phase difference (degrees)')
axes[0, 0].legend(frameon=False, fontsize=9)
axes[1, 0].legend(handles=axes[1, 0].get_legend_handles_labels()[0][-1:],
                  labels=['Declared resolution criterion'], frameon=False, fontsize=8)
for ax in axes.flat:
    ax.set_xlabel('P2 cross-section degrees of freedom')
    ax.grid(True, alpha=.18)
fig.suptitle('Independent polygon Womersley reference', fontsize=15)
fig.text(.5, .014, 'Complex P2 scalar solve; fixed straight facets. Observed refinement is not a rigorous error bound or 3D solver qualification.',
         ha='center', fontsize=8.5)
fig.tight_layout(rect=(0, .04, 1, .96))
for suffix in ('png', 'svg'):
    fig.savefig(out / ('polygon-reference.' + suffix), dpi=160)
svg = out / 'polygon-reference.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
dump(out / 'figure-provenance.json', dict(inputs=inputs,
    outputs={p.name: digest(p) for p in [out/'polygon-reference.png', svg]},
    source_sha256=digest(Path(__file__)), matplotlib=matplotlib.__version__))
dump(out / 'attempt-history.json', dict(attempts=[
    dict(name=base, state='failed', observation='Stopped during S96 level3 before saving alpha1; original error message empty. Partial S48 and S96 levels1/2 retained.'),
    dict(name=base+'-attempt2', state='failed', observation='Explicit double true residual at 86785 dofs: 2.83746e-11 initially, then 1.68e-11 floor after corrections; unchanged gate1e-11 failed.'),
    dict(name=base+'-attempt3', state='failed', observation='Independent summation check converted its oracle to double but imposed an extended-precision bound; failed at the first manufactured test. Numerical production gates unchanged.'),
    dict(name=base+'-attempt4', state='completed', observation='Extended state/residual with independent 80-digit decimal summation checks. S96 level3 alpha1/2 residuals9.081e-15/7.788e-15 after one correction. All original reference gates passed.')],
    scope='The repeated attempts repair only the independent reference. EONSim and svFSI production binaries/configuration are unchanged.'))
helper = root / 'build/prod48-20261107/capture-production-followups.py'
spec = importlib.util.spec_from_file_location('capture', helper)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
paths = list(out.rglob('*'))
for suffix in ('', '-attempt2', '-attempt3', '-attempt4'):
    paths.extend((work/(base+suffix)).rglob('*'))
for suffix in ('', '-retry2', '-retry3', '-retry4'):
    paths.append(work / ('womersley-polygon-reference'+suffix+'-current.json'))
capture.capture('womersley-polygon-reference-2026-11-08', paths,
    [final/'summary.json', final/'provenance.json', out/'attempt-history.json',
     out/'figure-provenance.json', out/'polygon-reference.png', out/'polygon-reference.svg',
     out/'capture-polygon-reference.py'])
