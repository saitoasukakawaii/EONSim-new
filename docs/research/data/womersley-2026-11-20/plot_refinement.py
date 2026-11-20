"""Plot separate spatial and temporal sensitivity measurements from the replay JSON."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path,help='Output from replay.py --fields')
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    names = ['s48-r4-a6-n64','s48-r8-a12-n64','s48-r12-a18-n64']
    cases = [data['flow'][name] for name in names]
    fig, (space, time) = plt.subplots(1,2,figsize=(9.2,3.45),layout='constrained')
    colors = ('#255e86','#a4492b','#317665')
    space.plot(range(3),[100*c['amplitude_relative_error'] for c in cases],
               'o-',color=colors[0],label='Flow amplitude')
    space.plot(range(3),[100*data['field'][k]['velocity_relative_l2'] for k in names],
               's-',color=colors[2],label='Endpoint velocity L²')
    space.plot(range(3),[100*abs(1-c['pressure_drop_amplitude']/.02) for c in cases],
               '^-',color=colors[1],label='End-pressure amplitude')
    space.set_xticks(range(3),[f"{c['radial']} / {c['axial']}" for c in cases])
    space.set(yscale='log',ylabel='Error against analytical reference (%)',
              xlabel='Radial rings / axial slabs (48 sectors)')
    space.set_yticks([.5,1,2,5,10],['0.5','1','2','5','10'])

    for family,label,color,marker in [('default','Default τ',colors[0],'o'),
                                     ('uniform','Fixed τ = 0.003',colors[1],'s')]:
        pairs = data['time'][family]['successive_pairs']
        time.loglog([v['fine_samples'] for v in pairs],
                    [100*v['relative_phasor_change'] for v in pairs],
                    color=color,marker=marker,lw=1.5,label=label)
    reference = data['time']['uniform']['successive_pairs'][0]
    origin = reference['fine_samples']
    anchor = 100*reference['relative_phasor_change']
    time.plot([origin,4*origin],[anchor,anchor/16],color='#707070',ls='--',
              lw=1,label='Second-order slope',zorder=0)
    time.set(xlabel='Finer time resolution (steps per cycle)',
             ylabel='Successive complex-flow difference (%)')
    time.set_xticks([32,64,128,256],['32','64','128','256'])
    time.xaxis.set_minor_formatter(NullFormatter())
    time.set_yticks([.1,.2,.5,1,2],['0.1','0.2','0.5','1','2'])
    for ax in (space,time):
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',color='#d7dce1',lw=.55)
        ax.legend(frameon=False,fontsize=8)
    matplotlib.rcParams['svg.hashsalt'] = 'eonsim-womersley-refinement-2026-11-20'
    matplotlib.rcParams['svg.fonttype'] = 'none'
    fig.savefig(args.output,metadata={'Date':None})
    if args.output.suffix.lower()=='.svg':
        args.output.write_text('\n'.join(line.rstrip() for line in args.output.read_text().splitlines())+'\n')


if __name__ == '__main__':
    main()
