"""Regenerate the figure from the archived numerical receipts (matplotlib)."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parent
fields=json.loads((root/'summary.json').read_text())
mass=json.loads((root/'mass-convergence.json').read_text())
fig,axes=plt.subplots(2,2,figsize=(10,7.5),layout='constrained')
styles={'be':('Backward Euler','#3268a8','o'),'bdf2':('BDF2','#c75928','s'),'generalized_alpha':('Generalized alpha','#258070','^')}
for scheme,(label,color,marker) in styles.items():
    rows=[r for r in fields if r['scheme']==scheme]
    for ax,key,title in zip(axes.flat,('fluid_velocity','solid_displacement','fluid_pressure'),('Fluid velocity','Solid displacement','Fluid pressure')):
        ax.loglog([r['dt'] for r in rows],[r['errors'][key] for r in rows],marker=marker,color=color,label=label,lw=1.8)
        ax.set_title(title,loc='left',fontweight='bold');ax.set_ylabel('Phase RMS field difference')
    rows=[r for r in mass if r['scheme']==scheme]
    axes[1,1].loglog([r['dt'] for r in rows],[r['max_absolute_defect'] for r in rows],marker=marker,color=color,lw=1.8)
axes[1,1].set_title('Cumulative volume budget',loc='left',fontweight='bold')
axes[1,1].set_ylabel('Maximum absolute volume defect')
for ax in axes.flat:
    ax.set_xlabel('Time step (case units)');ax.grid(True,which='major',alpha=.25)
    ax.spines[['top','right']].set_visible(False)
axes[0,0].legend(fontsize=8,frameon=False)
fig.suptitle('FSI-NEXT-03: temporal refinement and mass budget\nn=2, tau=0.05, 2 MPI ranks; fields: second cycle, budget: full run',fontsize=13)
fig.savefig(root/'temporal-refinement.png',dpi=180)
