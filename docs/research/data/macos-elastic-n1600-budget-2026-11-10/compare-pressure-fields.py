"""Exact P1 cycle differences for same or genuinely nested pressure-tube meshes.

Use audited endpoint fields and exact common stored phases. No time interpolation,
pressure gauge adjustment, fitted phase shift, or subtraction of error norms.
Both physical domains are integrated on the finer reference mesh. Differences
are reported, not automatically attributed to a particular error source.
"""
import argparse,copy,hashlib,importlib.util,json,math,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import study_rigid_tube as tube
from analyze_womersley import Mesh
from compare_womersley import interpolation
from audit_pressure_tube import Domain,eonsim_frame,svfsi_frame
from fsi_field_cycles import series

spec=importlib.util.spec_from_file_location('pressure_comparison',Path(__file__).with_name('compare-pressure-audits.py'))
audit_comparison=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_comparison)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def nested(coarse,fine,levels):
    if type(levels) is not int or not 0<=levels<=3:raise ValueError('Invalid refinement direction')
    expected=tube.read_mesh(coarse)
    for _ in range(levels):expected=tube.refine(*expected)
    actual=tube.read_mesh(fine)
    if expected[0].keys()!=actual[0].keys():raise ValueError('Not the declared red-refined node set')
    if max(abs(x-y) for n in expected[0] for x,y in zip(expected[0][n],actual[0][n]))>1e-12:
        raise ValueError('Not the declared red-refined coordinates')
    if {tuple(sorted(c)) for c in expected[1]}!={tuple(sorted(c)) for c in actual[1]}:
        raise ValueError('Not the declared red-refined tetrahedra')
    if {(tag,tuple(sorted(f))) for tag,f in expected[2]}!={(tag,tuple(sorted(f))) for tag,f in actual[2]}:
        raise ValueError('Not the declared red-refined boundary tags')


def physical_config(cfg,allow_startup_difference=False):
    result=copy.deepcopy(cfg)
    for name in ('mesh','output'):result.pop(name,None)
    for name in ('dt','steps','output_interval','checkpoint_interval'):result['fsi'].pop(name,None)
    result['fsi']['domains'].pop('solid_mesh')
    if allow_startup_difference:result['fsi'].get('pressure_time',{}).pop('ramp_time',None)
    return result


class Study:
    def __init__(self,case,work,audit_path):
        self.case=case.resolve();self.work=work.resolve();self.audit_path=audit_path.resolve()
        self.cfg=json.loads(self.case.read_text());self.audit=json.loads(self.audit_path.read_text())
        self.reference=self.audit['solver']=='svFSI'
        self.valid=audit_comparison.validate(self.audit,'svFSI' if self.reference else 'EONSim')
        if self.audit['case_sha256']!=sha(self.case):raise ValueError('Audit belongs to a different case')
        self.geometry=json.loads((case.parent/'geometry.json').read_text())
        self.domains=[Domain(case.parent/self.cfg['mesh']),Domain(case.parent/self.cfg['fsi']['domains']['solid_mesh'])]
        for domain in self.domains:
            if self.audit['reference_meshes'][domain.path.name]!=sha(domain.path):raise ValueError('Audited mesh changed')
        self.meshes=[Mesh(d.path) for d in self.domains]
        self.steps=self.audit['steps'];self.n=self.audit['samples_per_cycle'];self.period=self.audit['period']
        self.first=self.audit.get('first_step',1)
        self.files={str(self.case):sha(self.case),str(self.audit_path):sha(self.audit_path)}
        self.paths={}
        if self.reference:
            export=json.loads((self.work/'export.json').read_text())
            if export['load_evaluation']!='alpha_f stage':raise ValueError('Wrong reference input clock')
            if json.loads((self.work/'source-case.json').read_text())!=self.cfg:raise ValueError('Reference source case changed')
            for name,digest in export['files'].items():
                if sha(self.work/name)!=digest:raise ValueError('Reference input changed')
            for path in (self.work/'results').glob('result_*.vtu'):
                step=int(path.stem.rsplit('_',1)[1])
                if step in self.paths:raise ValueError('Duplicate reference output step')
                self.paths[step]=[path]
            if not set(range(self.first,self.steps+1))<=set(self.paths):raise ValueError('Incomplete reference history')
        else:
            all_paths=[series(self.work/name) for name in ('solution.pvd','solution_solid.pvd')]
            if len(all_paths[0])!=len(all_paths[1]):raise ValueError('Incomplete EONSim history')
            for pair in zip(*all_paths):
                step=round(pair[0][0]*self.n/self.period)
                if step in self.paths:raise ValueError('Duplicate EONSim step')
                if any(abs(t-step*self.period/self.n)>1e-9*self.period for t,_ in pair):raise ValueError('Output clock changed')
                self.paths[step]=[path for _,path in pair]
            if not set(range(self.first,self.steps+1))<=set(self.paths):raise ValueError('Incomplete EONSim history')

    def frame(self,step):
        paths=self.paths[step]
        for path in paths:
            self.files[str(path)]=sha(path)
            if path.suffix=='.pvtu':
                for piece in ET.parse(path).findall('.//Piece'):
                    child=path.parent/piece.attrib['Source'];self.files[str(child)]=sha(child)
        frames=svfsi_frame(paths[0],self.domains) if self.reference else (
            eonsim_frame(paths[0],self.domains[0]),eonsim_frame(paths[1],self.domains[1],True))
        for domain,frame,disp in zip(self.domains,frames,('mesh_displacement','displacement')):
            domain.geometry(frame,disp)
        return frames

    def periodic_at(self,cycle):
        return cycle>=3 and all(str(c) in self.audit['cycle_differences'] for c in (cycle-1,cycle)) and all(v['relative_max']<1e-5 for c in (cycle-1,cycle)
            for v in self.audit['cycle_differences'][str(c)].values())


def compare(left,right,left_cycle=None,right_cycle=None,phases=None,allow_startup_difference=False):
    if physical_config(left.cfg,allow_startup_difference)!=physical_config(right.cfg,allow_startup_difference):raise ValueError('Different physical/solver configuration')
    if left.audit['analysis_script_sha256']!=right.audit['analysis_script_sha256']:raise ValueError('Different field audit implementations')
    definitions=[copy.deepcopy(s.audit['physical_definition']) for s in (left,right)]
    if allow_startup_difference:
        for definition in definitions:definition['pressure_time'].pop('ramp_time',None)
    if definitions[0]!=definitions[1] or left.audit['scales']!=right.audit['scales']:
        raise ValueError('Different physical definition/scales')
    a=left.geometry.copy();b=right.geometry.copy()
    la=a.pop('red_refinements');lb=b.pop('red_refinements')
    if a!=b:raise ValueError('Different polygon or seed geometry')
    ca=left_cycle or left.steps//left.n;cb=right_cycle or right.steps//right.n
    if not (left.first-1)//left.n+1<=ca<=left.steps//left.n or not (right.first-1)//right.n+1<=cb<=right.steps//right.n:raise ValueError('Cycle outside audited history')
    if allow_startup_difference:
        if left.audit['solver']!=right.audit['solver']:raise ValueError('Startup comparison requires the same solver')
        for study,cycle in ((left,ca),(right,cb)):
            if (cycle-1)*study.period<study.cfg['fsi']['pressure_time'].get('ramp_time',0.)-1e-10*study.period:
                raise ValueError('Selected cycle intersects the startup ramp')
    m=phases or math.gcd(left.n,right.n)
    if m<4 or left.n%m or right.n%m:raise ValueError('Need exact common stored phases')
    stencils=[]
    for a,b,ma,mb in zip(left.domains,right.domains,left.meshes,right.meshes):
        nested(a.path,b.path,lb-la)
        stencils.append(interpolation(ma,mb))
    sums={};maximum={}
    for phase in range(1,m+1):
        frames_a=left.frame((ca-1)*left.n+phase*left.n//m)
        frames_b=right.frame((cb-1)*right.n+phase*right.n//m)
        for i,(a,b,mesh,stencil,scales) in enumerate(zip(frames_a,frames_b,right.meshes,stencils,right.audit['scales'])):
            for name,scale in scales.items():
                x=np.array([a[int(n)][name] for n in left.meshes[i].ids])
                y=np.array([b[int(n)][name] for n in mesh.ids])
                if stencil is not None:
                    indices,weights=stencil;x=np.einsum('na,nad->nd',weights,x[indices])
                squared=mesh.squared(x-y)/mesh.volume
                if not math.isfinite(squared) or squared<0:raise ValueError('Invalid field norm')
                key=('fluid_' if i==0 else 'solid_')+name
                sums[key]=sums.get(key,0.)+squared/m
                maximum[key]=max(maximum.get(key,0.),math.sqrt(squared))
    scales={('fluid_' if i==0 else 'solid_')+k:v for i,d in enumerate(right.audit['scales']) for k,v in d.items()}
    return dict(left_cycle=ca,right_cycle=cb,common_phases=m,
        startup_comparison=allow_startup_difference,
        pressure_profiles=[s.cfg['fsi']['pressure_time'] for s in (left,right)],
        left_solver=left.audit['solver'],right_solver=right.audit['solver'],
        left_dt=left.cfg['fsi']['dt'],right_dt=right.cfg['fsi']['dt'],left_red_level=la,right_red_level=lb,
        selected_cycles_periodic=[left.periodic_at(ca),right.periodic_at(cb)],
        audit_prerequisites=[left.valid,right.valid],scales=scales,
        rms={k:math.sqrt(v) for k,v in sums.items()},maximum_phase_rms=maximum,
        relative_rms={k:math.sqrt(v)/scales[k] for k,v in sums.items()},
        relative_maximum_phase_rms={k:v/scales[k] for k,v in maximum.items()},
        input_files_sha256={'left':left.files,'right':right.files},
        synthetic_input=bool(left.audit.get('synthetic_fixture_not_a_solver_result') or right.audit.get('synthetic_fixture_not_a_solver_result')),
        norm='Exact consistent P1 mass on the verified red-refined target reference domains',
        qualification='Not evaluated: pairwise differences only, with recorded parameter changes and no causal attribution')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for side in ('left','right'):
        for name in ('case','work','audit'):p.add_argument('--'+side+'-'+name,type=Path,required=True)
        p.add_argument('--'+side+'-cycle',type=int)
    p.add_argument('--phases',type=int);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-startup-difference',action='store_true',help='Explicit same-solver comparison after both startup ramps have ended; all other physical inputs must match')
    a=p.parse_args()
    left=Study(a.left_case,a.left_work,a.left_audit);right=Study(a.right_case,a.right_work,a.right_audit)
    result=compare(left,right,a.left_cycle,a.right_cycle,a.phases,a.allow_startup_difference)
    result['helper_sha256']=sha(Path(__file__))
    result['analysis_sources_sha256']={name:sha(ROOT/name) for name in (
        'scripts/audit_pressure_tube.py','scripts/analyze_womersley.py','scripts/compare_womersley.py','scripts/study_rigid_tube.py')}
    with a.output.open('x') as file:file.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='input_files_sha256'},allow_nan=False))


if __name__=='__main__':main()
