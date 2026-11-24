"""Plot measured end expansion and the linearized stabilization coefficient from authenticated runs."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from compare_metric import read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('linear','pairs','reference','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    linear=read(args.linear)
    records=read(args.pairs)
    meridian=read(args.reference)
    target=max(meridian['runs'],key=lambda r:r['steps'])['samples'][-1]
    if target['time']!=1. or meridian['sections'][0]!=0. or meridian['pressure']!=linear['pressure']:
        raise ValueError('Time, station or pressure differs in the independent meridian')
    valid=[r for r in records if r['group'] in ('current-time','reference-div')
           and r['report']['mesh_sha256']==[linear['input_sha256'][k] for k in ('fluid.msh','solid.msh')]
           and r['peak_pressure']==linear['pressure']]
    styles=[('current-equations','native','svFSI standard','#b34323','s'),
            ('current-equations-grad-div-off','zero','svFSI without grad-div','#15846a','^'),
            ('current-equations-grad-div-time-1over128','fixed-div-time','svFSI with grad-div time fixed','#8156a3','D')]
    fig,(left,right)=plt.subplots(1,2,figsize=(10.8,4.65),gridspec_kw={'width_ratios':(1.45,1.)})
    available=set()
    for variant,mode,label,color,marker in styles:
        rows=sorted((v['report'] for v in valid if v['sv_variant']==variant),key=lambda v:v['steps'])
        if not rows:raise ValueError('Missing observations for '+label)
        steps=[v['steps'] for v in rows]
        available.update(steps)
        samples=[v['results'][-1] for v in rows]
        if any(v['time']!=1. for v in samples):raise ValueError('Run does not finish at 1 s')
        if mode=='native':
            left.plot(steps,[100*v['eon']['strains'][0] for v in samples],color='#214e80',marker='o',linewidth=1.7,label='EONSim')
        left.plot(steps,[100*v['svfsi']['strains'][0] for v in samples],color=color,marker=marker,
                  linestyle='-' if mode!='fixed-div-time' else '--',markersize=5,linewidth=1.45,label=label)
    left.axhline(100*target['section_area_strain'][0],color='#444444',linestyle=':',label='Axisymmetric Q2/Q1')
    ns=sorted(available)
    if not ns:raise ValueError('No matched observations')
    for mode,label,color,marker in [('native','Standard metric','#b34323','s'),('fixed-div-time','Time fixed at 1/128 s','#8156a3','D')]:
        rows=sorted((r for r in linear['runs'] if r['mode']==mode and r['source_steps'] in ns),key=lambda r:r['source_steps'])
        if [r['source_steps'] for r in rows]!=ns:raise ValueError('Missing cell coefficients in the DAE')
        right.plot(ns,[r['grad_div_pa_s']['volume_median'] for r in rows],color=color,marker=marker,
                   linestyle='-' if mode=='native' else '--',linewidth=1.45,markersize=5,label=label)
    left.set_title('Left end of the tube at 1 s',loc='left',weight='bold',fontsize=12)
    left.set_ylabel('Area increase (% of initial area)')
    right.set_title('Momentum grad-div at rest',loc='left',weight='bold',fontsize=12)
    right.set_ylabel('Volume-weighted median coefficient (Pa s)')
    for ax in (left,right):
        ax.set_xscale('log',base=2)
        ax.set_xticks(ns)
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.set_xlabel('Time steps over the first second')
        ax.grid(axis='y',alpha=.27,linewidth=.7)
        ax.spines[['right','top']].set_visible(False)
        ax.legend(fontsize=8,frameon=False)
    fig.subplots_adjust(bottom=.16,top=.9,wspace=.32,left=.077,right=.98)
    fig.savefig(args.output,dpi=175,facecolor='white',metadata={'Software':'EONSim-new matched FSI study'})
    plt.close(fig)


if __name__=='__main__':main()
