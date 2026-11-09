"""Plot the completed coarse mesh-motion variant without implying qualification."""
import argparse, hashlib, json, math, os, shutil, subprocess
from pathlib import Path
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '1'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--data', type=Path, help='Replot the archived extracted numbers')
a = parser.parse_args()
out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
fields = ['fluid_velocity', 'fluid_pressure', 'fluid_mesh_displacement', 'solid_velocity', 'solid_displacement']
observables = ['mid_radial_displacement', 'mid_ring_projected_area', 'mid_pressure', 'outward_flow_left', 'outward_flow_right']
if a.data:
    data = json.loads(a.data.read_text())
else:
    work = Path('/home/tfblab633/EONSim-prod48-20261107')
    storage = Path('/mnt/d/EONSim-prod48-20261107')
    origins = {'original': work/'elastic-s12-l0-n400-ramp16-c32', 'mesh_nu0': storage/'reference-s12-l0-n400-meshnu0-a7a177e'}
    data = dict(source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                plot_source_sha256=sha(Path(__file__)), matplotlib=matplotlib.__version__, variants={},
                scope='S12 level0, N400,32cycles,ramp16. Only reference mesh equation nu changes; physical solid nu=.3. Original EONSim result is common. Space/time/geometry/end budgets remain incomplete.')
    common_eonsim = None
    for label, directory in origins.items():
        audit = json.loads((directory/'svfsi-audit.json').read_text())
        comparison = json.loads((directory/'comparison.json').read_text())
        assert audit['steps'] == 12800 and audit['samples_per_cycle'] == 400
        assert audit['reference_convergence']['passed']
        current = {name: comparison['observables'][name]['eonsim'] for name in observables}
        if common_eonsim is None: common_eonsim = current
        else: assert common_eonsim == current
        periodic = {field: dict(value=max(audit['cycle_differences'][str(cycle)][field]['relative_max'] for cycle in (31,32)), limit=1e-5) for field in fields}
        for row in periodic.values(): row['ratio'] = row['value']/row['limit']
        amplitude = {name: dict(value=comparison['observables'][name]['relative_amplitude_difference'], limit=comparison['observables'][name]['amplitude_limit']) for name in observables}
        for row in amplitude.values(): row['ratio'] = row['value']/row['limit']
        lame = comparison['lame_mean_diagnostics']['svFSI']
        mean = dict(value=lame['relative_difference'], limit=lame['limit'], ratio=lame['relative_difference']/lame['limit'])
        assert all(math.isfinite(row['ratio']) and row['ratio'] > 0 for row in [*periodic.values(), *amplitude.values(), mean])
        assert audit['periodic'] == all(row['ratio'] < 1 for row in periodic.values())
        data['variants'][label] = dict(periodic=periodic, amplitude=amplitude, lame_mean=mean,
            periodic_passed=audit['periodic'], observable_gates_passed=comparison['observable_gates_passed'],
            source_files={str(directory/name): sha(directory/name) for name in ['svfsi-audit.json', 'comparison.json']})
    (out/'plot-data.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
                     'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
fig, axes = plt.subplots(1, 2, figsize=(12.6, 6.5), gridspec_kw={'width_ratios': [1, 1.14]})
fig.subplots_adjust(left=.14, right=.98, bottom=.23, top=.78, wspace=.42)
colors = ['#436A8A', '#B66A34']; labels = [r'Original mesh $\nu=0.3$', r'Separate mesh $\nu=0$']
for index, (name, variant) in enumerate(data['variants'].items()):
    assert name == ['original', 'mesh_nu0'][index]
    offset = (index-.5)*.34
    axes[0].barh(np.arange(5)+offset, [variant['periodic'][field]['ratio'] for field in fields],
                 height=.3, color=colors[index], label=labels[index])
    values = [variant['amplitude'][field]['ratio'] for field in observables]+[variant['lame_mean']['ratio']]
    axes[1].barh(np.arange(6)+offset, values, height=.3, color=colors[index])

axes[0].set_yticks(range(5), ['Fluid velocity', 'Fluid pressure', 'Mesh displacement', 'Solid velocity', 'Solid displacement'])
axes[0].set_xscale('log'); axes[0].set_xlim(4e-4, 3.2)
axes[0].set_title('A  Reference periodicity', loc='left', pad=14)
axes[0].text(0, 1.02, 'Worst phase over cycle pairs 30/31 and 31/32', transform=axes[0].transAxes, fontsize=9, color='#555555')
axes[1].set_yticks(range(6), ['Radial amplitude', 'Area amplitude', 'Pressure amplitude', 'Left-flow amplitude', 'Right-flow amplitude', 'Lamé mean*'])
axes[1].set_xlim(0, 4.65); axes[1].set_xticks([0,1,2,3,4])
axes[1].set_title('B  Cross-program amplitude and mean checks', loc='left', pad=14)
axes[1].text(0, 1.02, 'EONSim versus svFSI; *svFSI versus circular Lamé mean', transform=axes[1].transAxes, fontsize=9, color='#555555')
for ax in axes:
    ax.invert_yaxis(); ax.axvline(1, color='#333333', linestyle='--', linewidth=1.1)
    ax.grid(axis='x', color='#dddddd', linewidth=.6); ax.set_axisbelow(True)
    ax.set_xlabel('Measured difference / stated limit  (must be <1)')
axes[0].legend(loc='lower left', bbox_to_anchor=(-.1, 1.15), ncol=2, frameon=False, fontsize=10)
fig.suptitle('Mesh-motion parameter study: periodicity and remaining errors', x=.5, y=.96, fontsize=16)
fig.text(.14, .13, 'S12 level 0 · 400 steps/cycle · 32 cycles · 16-cycle ramp · same physical solid Poisson ratio 0.3', fontsize=10)
fig.text(.14, .085, 'Both complete reference trajectories converged. Only the separate mesh-nu0 variant passes the five-field periodic gate.', fontsize=10)
fig.text(.14, .045, 'Pressure amplitude and Lamé mean remain above their limits. Spatial, temporal, geometry and finite-end checks remain incomplete.', fontsize=10)
fig.savefig(out/'reference-nu0-gates.png', dpi=160, facecolor='white')
fig.savefig(out/'reference-nu0-gates.svg', facecolor='white')
svg = out/'reference-nu0-gates.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
plt.close(fig)
if Path(__file__).resolve() != out/'plot-reference-nu0-gates.py': shutil.copy2(__file__, out/'plot-reference-nu0-gates.py')
print(json.dumps(dict(output=str(out), periodic_ratio={name: value['periodic']['fluid_mesh_displacement']['ratio'] for name,value in data['variants'].items()},
                     pressure_ratio={name: value['amplitude']['mid_pressure']['ratio'] for name,value in data['variants'].items()})))
