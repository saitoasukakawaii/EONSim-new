"""Render the archived FSI-NEXT-01 measurements (Python 3 + matplotlib)."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
data=json.loads((root/'inlet-time.json').read_text())
fig,axes=plt.subplots(2,2,figsize=(9,6),layout='constrained')
for ax,field in zip(axes.flat,('fluid_velocity','fluid_mesh_displacement','solid_velocity','solid_displacement')):
    for scheme in ('be','bdf2','generalized_alpha'):
        rows=[r for r in data if r['scheme']==scheme]
        ax.loglog([r['h'] for r in rows],[r[field] for r in rows],'o-',label=scheme)
    ax.set_title(field.replace('_',' '));ax.set_xlabel('Time step');ax.set_ylabel('Nodal RMS difference')
    ax.grid(True,which='both',alpha=.25)
axes[0,0].legend();fig.suptitle('Fixed spatial grid; BDF2 reference dt = 0.0000625')
fig.savefig(root/'inlet-time.png',dpi=160);plt.close(fig)

curves={}
for n in (2,4,8):
    with (root/f'space-n{n}.csv').open() as f:curves[n]=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
for n,rows in curves.items():axes[0].plot([r['time'] for r in rows],[r['area_displacement_x'] for r in rows],label=f'n={n}')
for a,b in ((2,4),(4,8)):
    axes[1].plot([r['time'] for r in curves[a]],[r['area_displacement_x']-s['area_displacement_x'] for r,s in zip(curves[a],curves[b])],label=f'n={a} minus n={b}')
axes[0].set_ylabel('Reference-area mean x displacement');axes[1].set_ylabel('Difference at common accepted times')
for ax in axes:ax.set_xlabel('Time');ax.grid(alpha=.25);ax.legend()
fig.suptitle('Neo-Hookean end block, dt = 0.00025; time/space RMS ratio = 0.0951')
fig.savefig(root/'spatial.png',dpi=160);plt.close(fig)

data=json.loads((root/'performance-summary.json').read_text())
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
groups=[(4,1),(8,1),(8,2),(8,4)]
for j,recipe in enumerate(('direct','physics','hybrid')):
    rows=[r for r in data if r['recipe']==recipe]
    x=[groups.index((r['n'],r['ranks']))+(j-1)*.23 for r in rows]
    med=[r['solve_seconds_median'] for r in rows]
    err=[[m-r['solve_seconds_range'][0] for m,r in zip(med,rows)],[r['solve_seconds_range'][1]-m for m,r in zip(med,rows)]]
    axes[0].bar(x,med,width=.22,label=recipe,yerr=err,capsize=2)
    axes[1].bar(x,[r['peak_rss_max_bytes_median']/2**20 for r in rows],width=.22,label=recipe)
for ax in axes:
    ax.set_xticks(range(len(groups)),[f'n={n}\n{r} rank' for n,r in groups]);ax.grid(axis='y',alpha=.25)
axes[0].set_ylabel('Five-step solve time (s), median + min/max');axes[1].set_ylabel('Maximum process peak RSS (MiB), median')
axes[0].legend();fig.suptitle('Release: 3 alternating samples/configuration; warmups excluded')
fig.savefig(root/'performance.png',dpi=160);plt.close(fig)
