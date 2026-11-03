"""Plot accepted FSI load and response CSV (requires matplotlib)."""
import argparse
import csv
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('history', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with a.history.open() as source:
        rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(source)]
    if not rows:
        raise SystemExit('History contains no accepted steps')
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(8, 9), constrained_layout=True)
    for ax, (name, time, label) in zip(axes, [
        ('applied_pressure', 'evaluation_time', 'Applied pressure'),
        ('endpoint_position', 'time', 'Mean axial\ndisplacement'),
        ('endpoint_velocity', 'time', 'Mean axial\nvelocity'),
        ('evaluation_fluid_force', 'evaluation_time', 'Axial fluid force'),
    ]):
        ax.plot([r[time] for r in rows], [r[name] for r in rows])
        ax.set_ylabel(label)
        ax.grid(True, alpha=.3)
    axes[-1].set_xlabel('Time (consistent case units)')
    fig.savefig(a.output or a.history.with_suffix('.png'), dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
