"""Display completed coarse-grid observations; failed prerequisites stay visible."""
import hashlib,json,os,shutil
from pathlib import Path
os.environ['MPLBACKEND']='Agg';os.environ['OPENBLAS_NUM_THREADS']='1';os.sched_setaffinity(0,{19})
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[2];work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'elastic-time-trend-054b64a';out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[];sources={}
for n in (100,200,400):
    d=work/f'elastic-s12-l0-n{n}-ramp16-c32'
    comparison=d/'comparison.json';reference=d/'svfsi-audit.json'
    # N100 has the corrected strict-log audit in its explicit reaudit directory.
    if n==100:
        comparison=work/'elastic-convergence-reaudit-c49c69c/ramp16-comparison.json'
        reference=work/'elastic-convergence-reaudit-c49c69c/ramp16-svfsi.json'
    c=json.loads(comparison.read_text());a=json.loads(reference.read_text())
    assert not c['comparison_eligible'] and not a['periodic']
    last=max(map(int,a['cycle_differences']))
    records.append(dict(phases=n,pressure_amplitude_percent=100*c['observables']['mid_pressure']['relative_amplitude_difference'],
        pressure_phase_degrees=c['observables']['mid_pressure']['phase_difference_degrees'],
        reference_mesh_period_max=max(a['cycle_differences'][str(k)]['fluid_mesh_displacement']['relative_max'] for k in (last-1,last))))
    for p in (comparison,reference):sources[str(p)]=sha(p)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,3,figsize=(11.8,4.2),constrained_layout=False)
spec=[('pressure_amplitude_percent',2.,'Mid-pressure amplitude difference','Difference (%)'),
      ('pressure_phase_degrees',1.,'Mid-pressure phase difference','Difference (degrees)'),
      ('reference_mesh_period_max',1e-5,'Reference ALE mesh periodicity','Normalized maximum')]
x=[r['phases'] for r in records]
for ax,(key,limit,title,ylabel) in zip(axes,spec):
    y=[r[key] for r in records]
    ax.plot(x,y,'o-',color='#205a8c',lw=1.8,ms=6,label='Observed')
    ax.axhline(limit,color='#ae3e3e',ls='--',lw=1.4,label='Predeclared limit')
    ax.set_xscale('log',base=2);ax.set_xticks(x,[str(n) for n in x]);ax.set_xlim(85,470)
    ax.set_title(title,fontsize=11,pad=11);ax.set_xlabel('Steps per cycle N');ax.set_ylabel(ylabel)
    ax.grid(axis='y',alpha=.22);ax.set_ylim(0,max(max(y),limit)*1.25)
    if key=='reference_mesh_period_max':ax.ticklabel_format(axis='y',style='sci',scilimits=(-5,-5),useMathText=True)
    for xx,yy in zip(x,y):
        label=f'{yy/1e-5:.3f}e-5' if key=='reference_mesh_period_max' else f'{yy:.3f}'
        ax.annotate(label,(xx,yy),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
axes[0].legend(loc='upper right',fontsize=8,frameon=False)
fig.suptitle('Time refinement does not clear the coarse-grid qualification gates',fontsize=13,x=.5,y=.98)
fig.subplots_adjust(left=.07,right=.985,bottom=.24,top=.78,wspace=.38)
fig.text(.07,.075,'S12 / level 0; ramp16 / cycle32; default stabilization. All three cross-solver comparisons remain ineligible.\nLines connect recorded observations only. Spatial and dynamic-end budgets are still pending.',fontsize=9,color='#444444')
for suffix in ('png','svg'):fig.savefig(out/('time-refinement.'+suffix),dpi=180)
svg=out/'time-refinement.svg';svg.write_text('\n'.join(s.rstrip() for s in svg.read_text().splitlines())+'\n')
shutil.copy2(__file__,out/'original-plot.py')
(out/'observations.json').write_text(json.dumps(dict(records=records,input_sha256=sources,
    scope='Completed coarse-grid observations only; no new PDE solve, fitted order or qualification'),indent=2)+'\n')
(out/'files.json').write_text(json.dumps({p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.is_file()},indent=2)+'\n')
shutil.copy2(out/'time-refinement.png',root/'build/prod48-20261107/time-refinement.png')
print(json.dumps(dict(work=str(out),records=records)),flush=True)
