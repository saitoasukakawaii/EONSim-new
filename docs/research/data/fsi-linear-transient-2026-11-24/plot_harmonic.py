"""Plot complex left-end compliance and section/flux differences from the audited tables."""
import argparse
import csv
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def read(path):
    with path.open() as source:
        return list(csv.DictReader(source))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('meridian-csv','eon-csv','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    meridian=read(args.meridian_csv)
    candidates=[r for r in read(args.eon_csv) if r['periodic_within_0p1_pct']=='True'
                and int(r['steps_per_cycle'])==32 and not r['stabilization_time_s'] and '-cyc' in r['case']]
    fig,axes=plt.subplots(2,2,figsize=(10,6.6),layout='constrained')
    colors={0.:('#21618b','Free wall'),50.:('#a94a1e','Supported wall')}
    for stiffness,(color,label) in colors.items():
        curves=sorted((r for r in meridian if float(r['stiffness'])==stiffness and float(r['hz'])>=.0625),
                      key=lambda r:float(r['hz']))
        frequencies=[float(r['hz']) for r in curves]
        for ax,column in zip(axes[0],('end_area_modulus_per_pa','end_phase_deg')):
            ax.plot(frequencies,[float(r[column]) for r in curves],color=color,lw=2,label=label)
        for grid,marker in ((24,'s'),(48,'o'),(96,'^')):
            rows=sorted((r for r in candidates if float(r['stiffness'])==stiffness
                         and int(re.match(r's(\d+)-',r['case'])[1])==grid),key=lambda r:float(r['hz']))
            f=[float(r['hz']) for r in rows]
            for ax,column in zip(axes.flat,('end_area_modulus_per_pa','end_phase_deg','max_area_difference_pct_static',
                                            'influx_complex_difference_pct')):
                ax.scatter(f,[float(r[column]) for r in rows],s=42,marker=marker,facecolors='none',
                           edgecolors=color,linewidths=1.4)
    for ax in axes.flat:
        ax.set_xscale('log',base=2)
        ax.grid(True,color='0.89',lw=.75)
    for ax in axes[0]:
        ax.set_xticks([.0625,.125,.25,.5,1,2],['1/16','1/8','1/4','1/2','1','2'])
        ax.set_xlim(.052,2.4)
    for ax in axes[1]:
        ax.set_xticks([.25,.5,1],['1/4','1/2','1'])
        ax.set_xlim(.18,1.4)
        ax.set_ylim(bottom=0)
        ax.set_xlabel('Drive frequency (Hz)')
    axes[0,0].set_ylabel('End compliance magnitude (Pa$^{-1}$)')
    axes[0,1].set_ylabel('End area phase (degrees)')
    axes[1,0].set_ylabel('Max. section error (% of static compliance)')
    axes[1,1].set_ylabel('Total inward flux error (% of reference)')
    handles=axes[0,0].get_legend_handles_labels()[0]
    for grid,marker in ((24,'s'),(48,'o'),(96,'^')):
        if any(r['case'].startswith('s'+str(grid)+'-') for r in candidates):
            handles.append(Line2D([],[],marker=marker,linestyle='none',color='.24',mfc='none',label=f'3D, {grid} sectors'))
    fig.legend(handles=handles,loc='outside upper center',ncols=len(handles),frameon=False)
    fig.savefig(args.output,dpi=165)
    plt.close(fig)


if __name__=='__main__':main()
