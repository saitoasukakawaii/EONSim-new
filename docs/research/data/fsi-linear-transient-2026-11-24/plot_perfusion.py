"""Compare clamped and radially expanding outlet sections in the 20 mm perfused tube."""
import argparse
import json
import lzma
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from compare_perfusion import references, tables


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(lzma.decompress(args.archive.read_bytes()))
    grids,_=references(data)
    _,rows=tables(data)
    accepted={(r['group'],r['case']) for r in rows if r['periodic_pass']}
    fig,(left,right)=plt.subplots(1,2,figsize=(11,4.65),gridspec_kw={'width_ratios':[1.2,1.]})
    for moving,color,label in [(False,'#234f80','Clamped outlet'),(True,'#af4928','Radially free outlet')]:
        ref,obs=grids[False,moving,1.][-1]
        x=np.array(ref['sections'])/ref['parameters']['length']
        za=[complex(*p) for p in obs['area_strain']]
        target=100*abs(complex(*obs['outlet_phasor_m3_s']))/ref['amplitude_m3_s']
        left.plot(x,100*np.abs(za),color=color,label=label+' · meridian',linewidth=2.)
        right.axhline(target,color=color,linestyle=':',linewidth=1.5)
        eligible={}
        for item in data['runs']:
            d=item['report']
            if ((item['group'],item['case']) not in accepted or item['solver']!='EONSim' or d['model']!='volume' or d['rigid']
                    or d.get('outlet_tangential_motion',False)!=moving or d['frequency_hz']!=1. or d['steps_per_cycle']!=32
                    or d['full_amplitude']!=2e-7 or d.get('full_mean', 0.) != 0.):
                continue
            m=re.match(r's24-r3-w2-a(\d+)-',item['case'])
            if m:eligible.setdefault(int(m[1]),d)
        if not eligible:raise ValueError('Missing 3D curve')
        for n in sorted({min(eligible),max(eligible)}):
            d=eligible[n]
            sample=np.array(d['sections'])/d['parameters']['length']
            y=100*np.abs([complex(*p) for p in d['phasors']['area_strain']])
            left.plot(sample,y,marker='o' if n==min(eligible) else 's',fillstyle='none',markersize=4,
                      linestyle='none',color=color,label=f'{label} · 3D, {n} axial')
        levels=sorted(eligible)
        gain=[100*abs(complex(*eligible[n]['phasors']['full_outlet']))/eligible[n]['full_amplitude'] for n in levels]
        right.plot(levels,gain,color=color,marker='o',linewidth=1.5,label=label+' · 3D')
    left.set(xlabel='Axial position / length',ylabel='Area-strain amplitude (% of initial area)',xlim=(-.015,1.015))
    right.set(xlabel='Axial Tet4 layers',ylabel='Outlet / inlet flow amplitude (%)')
    right.set_xscale('log',base=2)
    ticks=sorted({int(re.match(r's24-r3-w2-a(\d+)-',i['case'])[1]) for i in data['runs']
                  if re.match(r's24-r3-w2-a(\d+)-',i['case'])})
    right.set_xticks(ticks,[str(t) for t in ticks])
    right.plot([],[],color='#555555',linestyle=':',label='Circular meridian')
    left.set_title('Wall motion at 1 Hz',loc='left',weight='bold',fontsize=12)
    right.set_title('Axial refinement at fixed cross-section mesh',loc='left',weight='bold',fontsize=12)
    for ax in [left,right]:
        ax.grid(axis='y',alpha=.27)
        ax.spines[['top','right']].set_visible(False)
        ax.legend(frameon=False,fontsize=7)
    fig.tight_layout(pad=1.25)
    fig.savefig(args.output,dpi=175,facecolor='white',metadata={'Software':'EONSim-new tube qualification'})
    plt.close(fig)


if __name__=='__main__':
    main()
