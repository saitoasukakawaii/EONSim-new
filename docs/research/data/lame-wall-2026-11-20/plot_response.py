"""Plot selected pressure–area histories and the measured refinement series."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def save_figure(figure, filename):
    output = HERE / filename
    figure.savefig(output, metadata={'Date': None})
    output.write_text('\n'.join(line.rstrip() for line in output.read_text().splitlines())+'\n')
    plt.close(figure)


def main():
    data = json.loads((HERE / 'results.json').read_text())
    matplotlib.rcParams['svg.hashsalt'] = 'eonsim-lame-2026-11-20'
    matplotlib.rcParams['svg.fonttype'] = 'none'
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
    save_figure(fig, 'pressure-area.svg')

    records = data['svfsi']['alpha05-medium']['settling']['history']
    exact = data['coupled']['sv05-s48']['exact_linear_area_strain']
    fig, (area, gap) = plt.subplots(1, 2, figsize=(9.2, 3.2), layout='constrained')
    for key, label, color, marker in (
            ('eonsim_midplane', 'EONSim', colors[0], 'o'),
            ('svfsi_midplane', 'svFSI', colors[1], 's')):
        area.plot([r['time'] for r in records], [r[key]/exact for r in records],
                  color=color, marker=marker, lw=1.4, ms=3, label=label)
    area.axhline(1., color='#484848', ls='--', lw=1, label='Lamé equilibrium')
    area.set(ylabel='Midplane strain / static reference')
    area.legend(frameon=False, fontsize=8, loc='lower right')
    for name, color, marker in (('alpha05-medium', colors[0], 'o'),
                                ('alpha05-medium-dt025', colors[1], 's')):
        pair = data['svfsi'][name]
        positive = [r for r in pair['settling']['history'] if r['max_cross_code_difference']>0]
        gap.semilogy([r['time'] for r in positive],
                     [100*r['max_cross_code_difference'] for r in positive],
                     color=color, marker=marker, ms=2.5, lw=1.2, label=f"Δt = {pair['dt']} s")
    gap.legend(frameon=False, fontsize=8)
    gap.set(ylabel='Max. sectional difference (% of static strain)')
    for ax in (area, gap):
        ax.set(xlabel='Time after pressure step (s)')
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', color='#d7dce1', lw=.55)
    save_figure(fig, 'paired-settling.svg')


if __name__ == '__main__':
    main()
