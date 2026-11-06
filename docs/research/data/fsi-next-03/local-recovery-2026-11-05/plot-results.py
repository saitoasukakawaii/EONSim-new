import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path.cwd();run=root/'build/resume-20261105'
work=Path('/home/tfblab633/EONSim-next03-20261105')
output=run/'figures';output.mkdir(exist_ok=True)
budget=json.loads((run/'fixed-budget.json').read_text())
colors={2:'#2563a0',4:'#d16c28',8:'#248578'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.dpi':140,'savefig.dpi':200,'font.family':'DejaVu Sans'})

def save(fig,name):
    fig.savefig(output/(name+'.png'),bbox_inches='tight')
    fig.savefig(output/(name+'.pdf'),bbox_inches='tight')
    plt.close(fig)

fig,ax=plt.subplots(figsize=(8.5,4.4),constrained_layout=True)
for n in (2,4,8):
    for dt,style in (('001','-'),('0005','--')):
        receipt=json.loads((work/f'fixed-n{n}-dt{dt}'/'periodic-result.json').read_text())
        rows=[r for r in receipt['metrics'] if 'fluid' in r]
        values=[max(*r['fluid'].values(),*r['solid'].values(),
                    *(v['relative_max'] for v in r['observations'].values())) for r in rows]
        ax.semilogy([r['cycle'] for r in rows],values,color=colors[n],ls=style,
                    label=f'n={n}, dt={float("0."+dt):g}',lw=1.5)
ax.axhline(1e-3,color='#333333',lw=1,ls=':',label='Periodic threshold')
ax.set(xlabel='Completed driving cycles',ylabel='Largest normalized adjacent-cycle change',
       title='Periodic convergence with fixed stabilization tau = 0.05')
ax.grid(alpha=.18);ax.legend(ncol=2,fontsize=9)
save(fig,'periodic-convergence')

fields=['fluid_velocity','fluid_pressure','fluid_mesh_displacement','solid_velocity','solid_displacement']
labels=['Fluid\nvelocity','Pressure','ALE\ndisplacement','Solid\nvelocity','Solid\ndisplacement']
fig,ax=plt.subplots(figsize=(8.5,4.4),constrained_layout=True)
for i,(kind,color) in enumerate([('temporal','#2563a0'),('transient','#d16c28'),('sampling','#248578')]):
    values=[budget['budget']['ratios'][kind][field] for field in fields]
    ax.bar(np.arange(5)+(i-1)*.24,values,.23,label=kind.title(),color=color)
ax.axhline(.1,color='#333333',ls='--',lw=1,label='Strict 10% limit')
ax.set_yscale('log');ax.set_xticks(np.arange(5),labels)
ax.set(ylabel='Estimate / last spatial difference',title='Three-mesh error budget (100 actual phases)')
ax.grid(axis='y',alpha=.18);ax.legend(ncol=4,fontsize=9)
save(fig,'error-budget')

fig,axes=plt.subplots(1,2,figsize=(10,3.8),constrained_layout=True)
phase=np.arange(1,101)/100
for n in (2,4,8):
    source=work/f'fixed-n{n}-dt001'
    sample=work/f'sampling-fixed-n{n}-dt001'
    receipt=json.loads((sample/'sampling-result.json').read_text())
    pressures=budget['pressure_cycles'][str(source)]
    axes[0].plot(phase,[v['pressure_drop'] for v in pressures],color=colors[n],label=f'n={n}')
    with (sample/f'dense_restart{receipt["start_cycle"]*100}.csv').open() as stream:
        rows=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
    final=[r for r in rows if r['time']>(receipt['end_cycle']-1)*.1+1e-10]
    axes[1].plot([(r['time']-(receipt['end_cycle']-1)*.1)/.1 for r in final],
                 [r['area_displacement_y'] for r in final],color=colors[n],label=f'n={n}')
axes[0].set(ylabel='Inlet minus outlet pressure (model units)',title='Pressure response')
axes[1].set(ylabel='Mean top-wall displacement (model units)',title='Elastic-wall response')
for ax in axes:ax.set_xlabel('Driving phase / period');ax.grid(alpha=.18);ax.legend()
fig.suptitle('Fixed tau = 0.05, dt = 0.001, independently converged states')
save(fig,'periodic-responses')
print('Saved three PNG/PDF figure pairs in',output)
