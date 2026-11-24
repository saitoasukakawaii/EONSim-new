"""Plot seven common section area strains for both native solvers and the circular reference."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--comparison',type=Path,default=Path(__file__).with_name('axisym-comparison.json'))
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    doc=json.loads(args.comparison.read_text())
    fig,axes=plt.subplots(1,2,figsize=(8.8,3.7),sharey=True)
    for sectors,ax in zip((48,96),axes):
        matches=[r for r in doc['observations'] if r['svfsi_stabilization']=='native' and
                 r['time']==1 and r['peak_pressure']==.02 and r['steps']==128 and r['mesh'][0]==sectors]
        if len(matches)!=1: raise ValueError('Missing or ambiguous matched observation')
        row=matches[0]
        for key,label,color,style,marker in [('reference','Axisymmetric reference','#242729','-','o'),
                                              ('eon','EONSim','#227666','--','s'),
                                              ('svfsi','svFSI','#ab4b29',':','^')]:
            values=row[key] if key=='reference' else row[key]['area_strains']
            ax.plot(row['x'],100*np.array(values),linestyle=style,marker=marker,color=color,lw=1.9,
                    ms=4.6,markerfacecolor='white',label=label)
        ax.set_title(f'{sectors} circumferential sectors',fontsize=12,loc='left',pad=8)
        ax.set_xlabel('Axial position (m)')
        ax.set_xlim(-.055,2.055)
        ax.set_xticks([0,.5,1,1.5,2])
        ax.grid(axis='y',color='#d9dcdb',lw=.65)
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Increase in lumen area (% of initial area)')
    axes[0].set_ylim(.058,.115)
    fig.suptitle('Elastic tube at 1 s under equal end pressures',x=.085,y=.97,ha='left',fontsize=15)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False,
               bbox_to_anchor=(.5,-.009))
    fig.subplots_adjust(left=.088,right=.985,top=.765,bottom=.23,wspace=.13)
    fig.savefig(args.output,dpi=155,bbox_inches='tight',pad_inches=.1,metadata={'Software':'Matplotlib'})
    plt.close(fig)


if __name__=='__main__':
    main()
