"""Plot selected pressure–area histories and the measured refinement series."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    data = json.loads((HERE / 'results.json').read_text())
    fig, (history, errors) = plt.subplots(1, 2, figsize=(9.2, 3.6), layout='constrained')
    colors = ('#245882', '#a74728')
    for name, style, color in zip(('s48-w4-r4-a6-dt05', 's48-w4-r4-a6-dt025'),
                                  ('o-', '-'), colors):
        records = data['mass'][name]['history']
        exact = data['coupled'][name]['exact_linear_area_strain']
        history.plot([0.] + [r['time'] for r in records],
                     [0.] + [r['section_linear_area_strain']/exact for r in records],
                     style, color=color, ms=2.5, lw=1.4,
                     label=f"BE, Δt = {data['mass'][name]['dt']} s")
    history.axhline(1., color='#484848', ls='--', lw=1, label='Lamé equilibrium')
    history.set(xlabel='Time (s)', ylabel='Midplane area strain / analytical equilibrium')
    history.legend(frameon=False, fontsize=8, loc='lower right')

    names = ('s12-w1-a2', 's24-w2-a3', 's48-w4-a6', 's96-w8-a12', 's192-w12-a16')
    coupled = ('s24-w2-r3-a3-dt05', 's48-w4-r4-a6-dt05', 's72-w6-r5-a8-dt05')
    for results, keys, field, label, color, marker in (
        (data['static'], names, 'area_relative_error', 'Isolated elastic wall', colors[0], 'o'),
        (data['coupled'], coupled, 'worst_area_relative_error', 'Coupled ALE FSI', colors[1], 's')):
        errors.plot([results[k]['sectors'] for k in keys], [100*results[k][field] for k in keys],
                    color=color, marker=marker, ms=4, lw=1.4, label=label)
    errors.set(xscale='log', yscale='log', xlabel='Full-circle sectors',
               ylabel='Worst-section area strain error (%)')
    errors.set_xticks([12, 24, 48, 72, 96, 192], [12, 24, 48, 72, 96, 192])
    errors.set_yticks([.2, .5, 1, 2, 5, 10], ['0.2', '0.5', '1', '2', '5', '10'])
    errors.legend(frameon=False, fontsize=8)
    for ax in (history, errors):
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', color='#d7dce1', lw=.55)
    matplotlib.rcParams['svg.hashsalt'] = 'eonsim-lame-2026-11-20'
    matplotlib.rcParams['svg.fonttype'] = 'none'
    output = HERE / 'pressure-area.svg'
    fig.savefig(output, metadata={'Date': None})
    output.write_text('\n'.join(line.rstrip() for line in output.read_text().splitlines())+'\n')


if __name__ == '__main__':
    main()
