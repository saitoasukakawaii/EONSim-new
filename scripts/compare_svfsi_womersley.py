"""Export the EONSim rigid tube for svFSI 2022.09.26 on the same tetrahedra."""
import argparse
import cmath
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

from svfsi_history import check_convergence
from svfsi_mesh import export_mesh
import study_rigid_tube as tube
import study_womersley as study


SVFSI_REVISION = '94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571'
FACE_NAMES = {1:'inlet', 2:'outlet', 3:'wall'}
CROSS_CODE_LIMIT = .05


def input_text(config):
    fluid = config['fluid']
    return f"""Continue previous simulation: 0
Number of spatial dimensions: 3
Number of time steps: {fluid['steps']}
Time step size: {fluid['dt']:.17g}
Spectral radius of infinite time step: 0
Save results to VTK format: 1
Name prefix of saved VTK files: result
Increment in saving VTK files: {fluid['steps']}
Start saving after time step: 1
Increment in saving restart files: {fluid['steps']}
Verbose: 1
Warning: 1

Add mesh: tube {{
   Mesh file path: fluid.vtu
   Add face: inlet {{
      Face file path: inlet.vtp
   }}
   Add face: outlet {{
      Face file path: outlet.vtp
   }}
   Add face: wall {{
      Face file path: wall.vtp
   }}
}}
Add equation: fluid {{
   Coupled: 1
   Min iterations: 2
   Max iterations: 12
   Tolerance: 1e-8
   Backflow stabilization coefficient: 0
   Density: {fluid['density']}
   Viscosity: Constant {{ Value: {fluid['viscosity']} }}
   Output: Spatial {{
      Velocity: t
      Pressure: t
   }}
   Output: Boundary_integral {{
      Velocity: t
      Pressure: t
   }}
   LS type: GMRES {{
      Max iterations: 10
      Tolerance: 1e-10
      Absolute tolerance: 1e-15
      Krylov space dimension: 150
   }}
   Add BC: inlet {{
      Type: Neu
      Time dependence: Unsteady
      Fourier coefficients file path: inlet.fcs
   }}
   Add BC: outlet {{
      Type: Neu
      Value: 0
   }}
   Add BC: inlet {{
      Type: Dir
      Effective direction: (0,1,1)
      Value: 0
   }}
   Add BC: outlet {{
      Type: Dir
      Effective direction: (0,1,1)
      Value: 0
   }}
   Add BC: wall {{
      Type: Dir
      Value: 0
   }}
}}
"""


def prepare(case, directory):
    config,_,_,_ = study.study_parameters(case)
    if config['time']!=dict(scheme='generalized_alpha',rho_infinity=0.):
        raise ValueError('The matched svFSI case requires generalized_alpha with rho_infinity=0')
    if 'stabilization_tau' in config['fluid']:
        raise ValueError('The matched case uses the default stabilization in each solver')
    directory.mkdir(parents=True)
    export_mesh(case/config['mesh'],directory,'fluid',FACE_NAMES)
    (directory/'svFSI.inp').write_text(input_text(config))
    # Upstream IFFT adds r*cos(k*t) - i*sin(k*t), starting with k=0.
    (directory/'inlet.fcs').write_text(f'0\n{study.PERIOD:.17g}\n0\n0\n2\n0 0\n0 {-tube.DROP:.17g}\n')


def read_table(path, areas, steps):
    lines = [line.split() for line in path.read_text().splitlines() if line.strip()]
    if len(lines)!=steps+2 or set(lines[0])!=set(areas) or len(lines[0])!=len(areas):
        raise ValueError(f'Unexpected columns or step count in {path.name}')
    if len(lines[1])!=len(areas) or any(not math.isclose(float(a),areas[name],rel_tol=2e-6)
                                       for name,a in zip(lines[0],lines[1])):
        raise ValueError(f'Unexpected surface area in {path.name}')
    table = []
    for raw in lines[2:]:
        values = list(map(float,raw))
        if len(values)!=len(areas) or not all(map(math.isfinite,values)):
            raise ValueError(f'Invalid boundary integral in {path.name}')
        table.append(dict(zip(lines[0],values)))
    return table


def compare(case, directory):
    eon = study.analyze(case)
    executable_sha = (directory/'executable.sha256').read_text().strip()
    if not re.fullmatch('[0-9a-f]{64}',executable_sha):
        raise ValueError('Missing svFSI executable SHA-256')
    # Verify the external mesh, both end conditions, Fourier coefficients and
    # solver settings against the original EONSim case when replaying results.
    with tempfile.TemporaryDirectory() as temporary:
        fresh = Path(temporary)/'inputs'
        prepare(case,fresh)
        for path in fresh.iterdir():
            if path.read_bytes()!=(directory/path.name).read_bytes():
                raise ValueError(f'svFSI input differs from matched case: {path.name}')
    samples = eon['samples_per_cycle']
    steps = samples*eon['cycles']
    results = directory/'1-procs'
    final_norm,zero = check_convergence((results/'histor.dat').read_text(),steps)
    angle = 2*math.pi/eon['sectors']
    cap = eon['sectors']*tube.RADIUS**2*math.sin(angle)/2
    areas = dict(inlet=cap,outlet=cap,wall=2*eon['sectors']*tube.RADIUS*tube.LENGTH*math.sin(angle/2))
    flows = read_table(results/'B_NS_Velocity_flux.txt',areas,steps)
    pressures = read_table(results/'B_NS_Pressure_average.txt',areas,steps)
    q = [(r['outlet']-r['inlet'])/2 for r in flows]
    phases = [2*math.pi*i/samples for i in range(1,samples+1)]
    measured = study.harmonic(q[-samples:],phases)
    p = study.harmonic([r['inlet']-r['outlet'] for r in pressures[-samples:]],phases)
    reference = study.reference_flow()
    eon_q = cmath.rect(eon['flow_amplitude'],math.radians(eon['flow_phase_degrees']))
    difference = abs(measured-eon_q)/abs(reference)
    cycle_change = max(abs(a-b) for a,b in zip(q[-samples:],q[-2*samples:-samples]))/abs(reference)
    return dict(svfsi_target_revision=SVFSI_REVISION,svfsi_executable_sha256=executable_sha,
                steps=steps,ranks=1,samples_per_cycle=samples,
                sectors=eon['sectors'],radial=eon['radial'],axial=eon['axial'],
                svfsi_max_final_normalized_residual=final_norm,svfsi_zero_corrections=zero,
                svfsi_flow_amplitude=abs(measured),svfsi_flow_phase_degrees=math.degrees(cmath.phase(measured)),
                svfsi_amplitude_relative_error=abs(abs(measured)/abs(reference)-1),
                svfsi_phase_error_degrees=abs(math.degrees(cmath.phase(measured/reference))),
                svfsi_pressure_drop_amplitude=abs(p),svfsi_pressure_drop_phase_degrees=math.degrees(cmath.phase(p)),
                svfsi_cycle_max_change_relative=cycle_change,eonsim_flow_amplitude=abs(eon_q),
                eonsim_flow_phase_degrees=eon['flow_phase_degrees'],relative_phasor_difference=difference,
                passed=(difference<CROSS_CODE_LIMIT and cycle_change<study.LIMITS['cycle_max_change_relative']
                        and eon['cycle_max_change_relative']<study.LIMITS['cycle_max_change_relative']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True,help='EONSim study directory')
    parser.add_argument('--work',type=Path,required=True,help='New svFSI comparison directory')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--executable',type=Path,help='Run the pinned svFSI binary after exporting')
    mode.add_argument('--analyze-only',action='store_true',help='Replay the two recorded histories')
    parser.add_argument('--check',action='store_true',help='Require the periodic cross-code target')
    args=parser.parse_args()
    if args.check and not (args.executable or args.analyze_only):
        parser.error('--check requires a solve or --analyze-only')
    if not args.analyze_only:
        prepare(args.case,args.work)
    if args.executable:
        executable = args.executable.resolve()
        with (args.work/'solve.log').open('w') as log:
            subprocess.run([executable,'svFSI.inp'],cwd=args.work,stdout=log,stderr=subprocess.STDOUT,check=True)
        (args.work/'executable.sha256').write_text(hashlib.sha256(executable.read_bytes()).hexdigest()+'\n')
    if args.analyze_only or args.executable:
        result = compare(args.case,args.work)
        print(json.dumps(result,indent=2,allow_nan=False))
        if args.check and not result['passed']:
            raise SystemExit('Periodic cross-code flow target missed')
    else:
        print(json.dumps(dict(svfsi_revision=SVFSI_REVISION,input=str(args.work/'svFSI.inp'))))


if __name__=='__main__':
    main()
