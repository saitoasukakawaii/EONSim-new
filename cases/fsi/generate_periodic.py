"""Smooth periodic pressure driving the existing conforming elastic end block."""
import argparse
import json
from pathlib import Path
from generate_domains import generate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('build/fsi-periodic'))
    a = p.parse_args()
    path = generate(a.output)
    case = json.loads(path.read_text())
    case['fsi'].update(dt=.002, steps=100, pressure=1,
                       pressure_time=dict(amplitude=.25, period=.1, ramp_time=.05),
                       output_interval=5)
    case['time'] = dict(scheme='generalized_alpha', rho_infinity=.5)
    path.write_text(json.dumps(case, indent=2)+'\n')
    print(path)


if __name__ == '__main__':
    main()
