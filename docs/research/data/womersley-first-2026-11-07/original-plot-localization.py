"""Scientific plot of existing localization data; no new solver results."""
import argparse,hashlib,json,shutil
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='eonsim-womersley-localization-v1'
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--replace-derived-figure',action='store_true');args=p.parse_args()
out=root/'docs/research/data/womersley-first-2026-11-07'
source=out/'localization.json';data=json.loads(source.read_text())
fig,axes=plt.subplots(3,1,figsize=(8.4,8.7),sharex=True,layout='constrained')
colors=['#2563a6','#c55b20','#27866a']
for report,color in zip(data['reports'],colors):
    d=report['definition'];bands=report['axial_bands']
    x=[sum(b['x_interval'])/(2*d['length']) for b in bands]
    label=f"Red level {d['level']}, {d['steps_per_cycle']} steps/cycle"
    axes[0].plot(x,[100*b['velocity_first_harmonic_relative_l2'] for b in bands],'-o',color=color,label=label,ms=4)
    for i in range(2):
        axes[i+1].plot(x,[b['mean_axial_pressure_gradient_over_exact'][i] for b in bands],'-o',color=color,ms=4)
axes[0].set_ylabel('Velocity first-harmonic\nrelative L2 error (%)')
axes[1].set_ylabel('Real part of normalized\naxial pressure gradient')
axes[2].set_ylabel('Imaginary part of normalized\naxial pressure gradient')
axes[1].axhline(1,color='#4a4a4a',ls='--',lw=1,label='Analytical value')
axes[2].axhline(0,color='#4a4a4a',ls='--',lw=1)
axes[0].legend(loc='lower left',bbox_to_anchor=(0,1.01),ncol=3,fontsize=8,frameon=False)
axes[1].legend(loc='lower center',frameon=False,fontsize=9)
axes[2].set_xlabel('Reference axial position x/L (band center)')
for ax in axes:
    ax.grid(alpha=.2);ax.set_xlim(0,1)
    ax.spines[['top','right']].set_visible(False)
fig.suptitle('Womersley error localization: existing alpha=2 cycle-5 fields\n48-sided tube, default tau, four MPI ranks',fontsize=12)
for extension in ('png','svg'):
    path=out/('localization.'+extension)
    if path.exists() and not args.replace_derived_figure:raise ValueError('Do not overwrite an existing figure')
    fig.savefig(path,dpi=170,metadata={'Date':None} if extension=='svg' else None)
    if extension=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
plt.close(fig)
shutil.copy2(__file__,out/'original-plot-localization.py')
record=dict(input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),matplotlib_version=matplotlib.__version__,
    outputs={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in (
        'localization.png','localization.svg','original-plot-localization.py')},
    scope='Plot of existing analytical-reference field diagnostics; no new PDE solve or causal attribution')
(out/'plot-files.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
