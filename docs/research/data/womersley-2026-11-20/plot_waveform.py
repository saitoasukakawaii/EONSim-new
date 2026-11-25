"""Plot the matched last-cycle integrated flow and its error from archived traces."""
import argparse
import cmath
import json
import math
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import compare_svfsi_womersley as sv
import study_womersley as study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path,help='Unpacked evidence directory')
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    dataset = json.loads((args.root/'dataset.json').read_text())
    case = args.root/'runs'/dataset['svfsi']['medium']
    ext = args.root/'svfsi/medium'
    matched = sv.compare(case,ext)
    history = study.boundary_history((case/'solve.log').read_text())
    n,steps = matched['samples_per_cycle'],matched['steps']
    indices = range(steps-n,steps+1)
    phases = [i/n for i in range(n+1)]
    eon = [(history[i][2].flow-history[i][1].flow)/2 for i in indices]
    areas = {name:history[steps][tag].area for tag,name in sv.FACE_NAMES.items()}
    rows = sv.read_table(ext/'1-procs/B_NS_Velocity_flux.txt',areas,steps)
    external = [(rows[i-1]['outlet']-rows[i-1]['inlet'])/2 for i in indices]
    q = study.reference_flow()
    reference = [(q*cmath.exp(2j*math.pi*t)).imag for t in phases]
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','svg.hashsalt':'eonsim-womersley'})
    fig,(wave,error) = plt.subplots(2,1,figsize=(7.5,5.4),sharex=True,
                                    gridspec_kw={'height_ratios':(2,1)},layout='constrained')
    wave.plot(phases,[1e3*v for v in reference],color='#282d34',label='Circular analytical solution',lw=2)
    for name,values,color,marker in [('EONSim',eon,'#126298','o'),('svFSI',external,'#af551b','s')]:
        wave.plot(phases,[1e3*v for v in values],color=color,marker=marker,markevery=4,
                  mfc='white',ms=4,lw=1.1,label=name)
        error.plot(phases,[100*(v-ref)/abs(q) for v,ref in zip(values,reference)],
                   color=color,marker=marker,markevery=4,mfc='white',ms=3,lw=1.5)
    wave.set_title('Pressure-driven flow in a rigid tube, α = 2',loc='left',fontweight='bold')
    wave.set_ylabel('Flow (10⁻³ m³/s)')
    wave.legend(loc='lower left',frameon=False,ncol=3,fontsize=8)
    wave.margins(y=.18)
    error.set_ylabel('Flow error\n(% of reference amplitude)')
    error.set_xlabel('Fraction of the final forcing cycle')
    error.set_xticks([0,.25,.5,.75,1])
    error.set_xlim(0,1)
    for ax in (wave,error):
        ax.axhline(0,color='#6b7180',lw=.6,zorder=0)
        ax.grid(axis='y',color='#d9dde1',lw=.6)
        ax.spines[['right','top']].set_visible(False)
    fig.savefig(args.output,metadata={'Date':None},bbox_inches='tight')


if __name__=='__main__':
    main()
