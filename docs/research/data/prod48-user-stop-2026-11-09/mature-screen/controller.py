"""Mature S24 FSI current/history and cost screen; never adopt production."""
import argparse,fcntl,hashlib,importlib.util,json,math,os,re,shutil,sys,time,traceback
from pathlib import Path
import xml.etree.ElementTree as ET
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
ROOT=Path(__file__).resolve().parents[2]
W=Path('/home/tfblab633/EONSim-prod48-20261107');D=Path('/mnt/d/EONSim-prod48-20261107')
V=W/'fsi-lu-reuse-validation-9ccd73f'
OLD=D/'elastic-s24-l1-n200-mumps-chord-native1600-32fb313'
P=W/'length24-native-extension-proof-4f5f26d'
C=W/'fsi-retained-lu-mature-screen-b8d1c76';OUT=D/C.name;SOURCE=C/'source'
STATUS=W/'fsi-retained-lu-mature-screen-current.json'
OPTIONS=['-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2']
MODES=[('old-first','old',0,6200,6232),('new-default','new',0,6200,6232),
       ('new-window32','new',32,6200,6232),('new-window8','new',8,6200,6232),
       ('old-last','old',0,6200,6232),('new-replay16','new',32,6216,6232)]
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),control=str(C),adopted=False,**kw)
    p=STATUS.with_suffix('.tmp');dump(p,value);p.replace(STATUS);print(json.dumps(value),flush=True)
def generation(folder,step):
    found=[]
    for p in Path(folder).glob('*/manifest'):
        m=p.read_text().split()
        if int(m[2])!=step:continue
        assert m[0] in ('EONSim_checkpoint_v3','EONSim_checkpoint_v4') and m[1]=='1'
        assert len(m)==(5 if m[0].endswith('3') else 6);found.append(p.parent)
    assert len(found)==1,(str(folder),step,len(found));return found[0]
def seed(folder,step,destination):
    src=generation(folder,step);before={p.name:sha(p) for p in src.iterdir() if p.is_file()}
    assert set(before)=={'manifest','state_rank0.h5'}
    destination.mkdir();shutil.copytree(src,destination/src.name)
    (destination/'current').write_text((src/'manifest').read_text().split()[0]+' '+src.name+'\n')
    assert before=={p.name:sha(p) for p in (destination/src.name).iterdir() if p.is_file()}
    assert before=={p.name:sha(p) for p in src.iterdir() if p.is_file()};return before
def fields(directory,dt):
    result=[]
    for solid in (False,True):
        paths=[p for p in Path(directory).glob('*.pvd') if ('_solid' in p.stem)==solid];assert len(paths)==1
        mapping={}
        for e in ET.parse(paths[0]).findall('.//DataSet'):
            t=float(e.attrib['timestep']);step=round(t/dt);assert abs(t-step*dt)<1e-9 and step not in mapping
            mapping[step]=(paths[0].parent/e.attrib['file']).resolve()
        result.append(mapping)
    return result
def case():
    cfg=read(OUT/'case.json');cfg['mesh']='../fluid.msh';cfg['fsi']['domains']['solid_mesh']='../solid.msh'
    cfg['fsi']['checkpoint_interval']=1;return cfg
def command(label,binary,window,start,end):
    args=[sys.executable,C/'execution-guard.py',OUT/('eonsim-'+binary),'-case','case.json',
          '-checkpoint',OUT/label/'checkpoint','-restart',OUT/label/'checkpoint','-stop_after',end,
          '-solver_report','-log_view',':profile.txt',*OPTIONS]
    if window:args+=['-fsi_lu_pc_reuse_window',window]
    return list(map(str,args))
def validate_completion():
    assert read(W/'fsi-lu-reuse-validation-current.json')['state']=='completed'
    v=read(V/'completion.json');assert v['passed'] and not v['adopted']
    assert v['tests']==['fsi_lu_reuse','fsi_pressure_state','fluid_lu_reuse']
    assert v['histories']['passed'] and v['histories']['all_v4_clocks_exact'] and v['histories']['maximum']<2e-9
    proof=module('original_proof',P/'controller.py')
    for label in ('selection','release','debug','histories'):proof.clean_resource(read(V/(label+'.resource.json')))
    assert sha(V/'eonsim-release')==v['release']['sha256']
    assert sha(OLD/'eonsim')=='2692b6480cddebec96bd4f74479963d732aa483dc5b2be5a7635ac57e041eb12'
    return proof
def prepare():
    assert not C.exists() and not OUT.exists() and not STATUS.exists()
    os.sched_setaffinity(0,{19});os.nice(19);validate_completion()
    assert read(W/'elastic-n200-native1600-current.json')['state']=='completed'
    audit=read(OLD/'eonsim-audit.json');assert audit['periodic'] and audit['steps']==6400
    assert audit['first_step']==5801 and all(x['passed'] for x in audit['quality_gates'].values())
    assert sha(OLD/'eonsim-audit.json')=='939301461aeae7a5e1d1960f56bbf75399f777fd061c3e0ac8e820b82c0cf7a5'
    C.mkdir();OUT.mkdir();shutil.copy2(__file__,C/'controller.py')
    shutil.copytree(P/'source',SOURCE,ignore=shutil.ignore_patterns('__pycache__'))
    source_hashes=read(P/'definition.json')['source_hashes']
    for name,h in source_hashes.items():assert sha(SOURCE/name)==h
    for name in ('case.json','geometry.json','fluid.msh','solid.msh'):shutil.copy2(OLD/name,OUT/name)
    shutil.copy2(OLD/'eonsim',OUT/'eonsim-old');shutil.copy2(V/'eonsim-release',OUT/'eonsim-new')
    shutil.copy2(P/'bounded_cgroup_job_2g.py',C/'bounded_cgroup_job_2g.py')
    assert sha(C/'bounded_cgroup_job_2g.py')=='5070df17d8c299ea4bc393971e69fcc77f09821c1d0b895df6074c7a9997a939'
    guard=C/'execution-guard.py'
    guard.write_text('import os,sys,time\nfrom pathlib import Path\nos.sched_setaffinity(0,{19})\n'
        'g=Path("/sys/fs/cgroup")/Path("/proc/self/cgroup").read_text().strip().split("::",1)[1].lstrip("/")\n'
        'end=time.monotonic()+5\nwhile (g/"memory.max").read_text().strip()=="max" and time.monotonic()<end:time.sleep(.05)\n'
        'assert int((g/"memory.max").read_text())==2*1024**3 and int((g/"memory.swap.max").read_text())==0\n'
        'os.execv(sys.argv[1],sys.argv[1:])\n')
    shutil.copy2(V/'definition.json',C/'validation-definition.json');shutil.copy2(V/'completion.json',C/'validation-completion.json')
    shutil.copy2(OLD/'eonsim-audit.json',C/'original-audit.json');dump(C/'scales.json',audit['scales'])
    seed_hashes=seed(OLD/'checkpoint',6200,OUT/'seed')
    oracle=fields(OLD/'sample',read(OUT/'case.json')['fsi']['dt'])
    paths={OLD/n for n in ('case.json','geometry.json','fluid.msh','solid.msh','eonsim','eonsim-audit.json')}
    paths.update(generation(OLD/'checkpoint',6200).iterdir());paths.update((OLD/'sample').glob('*.pvd'))
    for domain in oracle:paths.update(domain[step] for step in range(6201,6233))
    dump(C/'oracle-fields.json',[{str(step):str(one[step]) for step in range(6201,6233)} for one in oracle])
    dump(C/'immutable-inputs.json',{str(p):sha(p) for p in sorted(paths)})
    definition=dict(controller_sha256=sha(C/'controller.py'),source_hashes=source_hashes,
        input_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file()},seed_hashes=seed_hashes,
        validation_completion_sha256=sha(V/'completion.json'),validation_definition_sha256=sha(V/'definition.json'),
        cpus=[19],nice=19,shared_cpu=True,lock='elastic-budget-analysis.lock',memory_max_bytes=2*1024**3,swap_max_bytes=0,
        admission_bytes=10*1024**3,running_floor_bytes=8*1024**3,mode_timeout=1800,comparison_timeout=7200,
        modes=MODES,expected_lu_counts={'old-first':32,'new-default':32,'new-window32':1,'new-window8':4,'old-last':32,'new-replay16':1},
        planned_commands={row[0]:command(*row) for row in MODES},
        nodal_limit=2e-9,history_limit=2e-9,mass_limit=1e-8,legacy_clock_limit=1e-12,cost_ratio_limit=.9,
        immutable_manifest_sha256=sha(C/'immutable-inputs.json'),oracle_fields_sha256=sha(C/'oracle-fields.json'),
        scales_sha256=sha(C/'scales.json'),cap_sha256=sha(C/'bounded_cgroup_job_2g.py'),guard_sha256=sha(guard),
        adopted=False,scope='Mature full-load6200seed,32states per main mode and16state native replay. Current five fields, all11datasets, integer metadata and exact new/new v4 clocks; old/new v3 clock1e-12 only. Candidate32 must be10% faster than both old baselines, new default and window8. SharedCPU timing only. No automatic adoption, refined-time or physics qualification.')
    dump(C/'definition.json',definition);print(json.dumps(dict(prepared=True,definition_sha256=sha(C/'definition.json'),candidate_sha256=sha(OUT/'eonsim-new'),adopted=False)),flush=True)
def verify():
    definition=read(C/'definition.json');assert definition['controller_sha256']==sha(C/'controller.py')==sha(Path(__file__))
    assert definition['planned_commands']=={row[0]:command(*row) for row in MODES}
    assert definition['validation_completion_sha256']==sha(V/'completion.json')
    assert definition['validation_definition_sha256']==sha(V/'definition.json')
    for name,h in definition['input_hashes'].items():assert sha(OUT/name)==h
    for name,h in definition['source_hashes'].items():assert sha(SOURCE/name)==h
    for name,key in [('immutable-inputs.json','immutable_manifest_sha256'),('oracle-fields.json','oracle_fields_sha256'),('scales.json','scales_sha256'),('bounded_cgroup_job_2g.py','cap_sha256'),('execution-guard.py','guard_sha256')]:assert sha(C/name)==definition[key]
    for name,h in read(C/'immutable-inputs.json').items():assert sha(name)==h
    assert {p.name:sha(p) for p in generation(OUT/'seed',6200).iterdir()}==definition['seed_hashes']
    return definition
def accepted(label,start,end,expected):
    text=(C/(label+'.log')).read_text();assert 'status=success' in text
    rows=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('fsi_step=')]
    reports=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('solver_report ')]
    assert [int(x['fsi_step']) for x in rows]==list(range(start+1,end+1)) and len(reports)==end-start
    for row,report in zip(rows,reports):
        assert int(report['snes_reason'])>0 and int(report['ksp_reason'])>0 and math.isfinite(float(row['residual']))
        assert all(float(row[k])>0 for k in ('endpoint_min_fluid_j','endpoint_min_solid_j'))
    events=[s.split() for s in (OUT/label/'profile.txt').read_text().splitlines() if s.lstrip().startswith('MatLUFactorNum ')]
    assert len(events)==1 and int(events[0][1])==expected and float(events[0][2])==1,events
    if label in ('new-window32','new-window8','new-replay16'):
        window=8 if label=='new-window8' else 32
        uses=[dict(re.findall(r'(\w+)=([^\s]+)',s)) for s in text.splitlines() if s.startswith('lu_preconditioner ')]
        assert [int(x['uses']) for x in uses]==[n%window+1 for n in range(end-start)]
        assert all(x['ksp']=='fgmres' and x['pc']=='lu' for x in reports)
    return dict(steps=len(rows),actual_lu_count=int(events[0][1]))
def worker():
    import h5py,numpy as np
    sys.path.insert(0,str(SOURCE/'scripts'));from audit_pressure_tube import Domain,eonsim_frame
    definition=verify();cfg=read(OUT/'case.json');scales=read(C/'scales.json')
    domains=[Domain(OUT/'fluid.msh'),Domain(OUT/'solid.msh')]
    maps={label:fields(OUT/label,cfg['fsi']['dt']) for label,*_ in MODES}
    maps['original']=[{int(k):Path(v) for k,v in one.items()} for one in read(C/'oracle-fields.json')]
    pairs=[('original','old-first',6201,6232),('old-first','new-default',6201,6232),('new-default','new-window32',6201,6232),
           ('new-default','new-window8',6201,6232),('old-first','old-last',6201,6232),('new-window32','new-replay16',6217,6232)]
    checks=[];raw={}
    for left,right,first,last in pairs:
        for step in range(first,last+1):
            maximum=clock=0.;datasets=0;legacy=False
            if left!='original':
                paths=[generation(OUT/label/'checkpoint',step)/'state_rank0.h5' for label in (left,right)]
                with h5py.File(paths[0]) as a,h5py.File(paths[1]) as b:
                    assert set(a)==set(b) and len(a)==11
                    av,bv=int(a['metadata'][0]),int(b['metadata'][0]);legacy=av==3 or bv==3
                    assert av in (3,4) and bv in (3,4) and av<=bv
                    for name in a:
                        x,y=a[name][...],b[name][...];assert x.dtype==y.dtype
                        assert np.all(np.isfinite(x)) and np.all(np.isfinite(y));datasets+=1
                        if name=='clock' and legacy:
                            assert x.shape==(2,) and y.shape==((2,) if bv==3 else (3,))
                            clock=float(np.max(np.abs(x-y[:2])));assert clock<1e-12
                        elif name=='metadata' and av!=bv:
                            assert x.shape==y.shape and x[0]==3 and y[0]==4 and np.array_equal(x[1:],y[1:])
                        elif x.dtype.kind in 'iu' or name in ('clock','time_metadata'):
                            assert np.array_equal(x,y),(left,right,step,name)
                        else:
                            assert x.shape==y.shape;maximum=max(maximum,float(np.max(np.abs(x-y),initial=0)))
                    assert int(a['metadata'][8])==step
                assert maximum<2e-9
                for p in paths:raw[str(p)]=sha(p)
            node=mass=0.
            for index,domain in enumerate(domains):
                files=[maps[label][index][step] for label in (left,right)]
                values=[eonsim_frame(p,domain,solid=bool(index)) for p in files]
                for value in values:domain.geometry(value,'displacement' if index else 'mesh_displacement')
                for name,scale in scales[index].items():
                    node=max(node,max(abs(x-y) for n in domain.nodes for x,y in zip(values[0][n][name],values[1][n][name])))
                    mass=max(mass,domain.rms_difference(values[0],values[1],name)/scale)
                for p in files:raw[str(p)]=sha(p)
            assert math.isfinite(node) and node<2e-9 and math.isfinite(mass) and mass<1e-8
            checks.append(dict(left=left,right=right,step=step,datasets=datasets,maximum_history=maximum,maximum_node=node,maximum_normalized_mass=mass,legacy_clock_difference=clock,exact_v4_clock=left!='original' and not legacy))
            if len(checks)%16==0:print(json.dumps(dict(compared_pairs=len(checks))),flush=True)
    resources=read(C/'numerical-completion.json')['resources']
    ratios={label:resources['new-window32']['wall_seconds']/resources[label]['wall_seconds'] for label in ('old-first','new-default','new-window8','old-last')}
    eligible=all(r<=.9 for r in ratios.values())
    counts={}
    for label,binary,window,start,end in MODES:
        assert read(OUT/label/'case.json')==case()
        counts[label]=accepted(label,start,end,definition['expected_lu_counts'][label])
        for p in [OUT/label/'case.json',OUT/label/'profile.txt',C/(label+'.log'),C/(label+'.resource.json'),C/(label+'-command.json')]:raw[str(p)]=sha(p)
    verify();assert len(checks)==176 and sum(x['datasets'] for x in checks)==1584
    dump(C/'report.json',dict(passed=True,numerical_passed=True,cost_passed=eligible,eligible=eligible,adopted=False,full_qualification=False,
        definition_sha256=sha(C/'definition.json'),checks=checks,counts=counts,cost_ratios=ratios,resources=resources,raw_hashes=raw,scope=definition['scope']))
def run():
    assert not STATUS.exists() and not (C/'report.json').exists();validate_completion();definition=verify()
    review=read(C/'plan-review.json');assert review['decision']=='run_bounded_fsi_mature_lu_screen_only' and review['definition_sha256']==sha(C/'definition.json')
    os.sched_setaffinity(0,{19});os.nice(19)
    try:
        update('waiting_for_analysis_resources')
        with (W/'elastic-budget-analysis.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);cap=module('cap',C/'bounded_cgroup_job_2g.py');proof=module('original_proof',P/'controller.py')
            prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
            env={k:v for k,v in os.environ.items() if not k.startswith(('OMPI_','PMIX_','PRTE_')) and k not in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH')}
            env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR='/tmp')
            resources={}
            for label,binary,window,start,end in MODES:
                while cap.available()<=10*1024**3:time.sleep(10)
                assert shutil.disk_usage('/mnt/d').free>24*1024**3
                directory=OUT/label;directory.mkdir();dump(directory/'case.json',case())
                seed(OUT/'new-window32/checkpoint' if label=='new-replay16' else OUT/'seed',start,directory/'checkpoint')
                cmd=command(label,binary,window,start,end);dump(C/(label+'-command.json'),cmd);update('running',mode=label)
                resources[label]=cap.run(cmd,directory,C/(label+'.log'),env,f'eonsim-fsi-lu-screen-{label}-{os.getpid()}.scope',1800)
                proof.clean_resource(resources[label]);accepted(label,start,end,definition['expected_lu_counts'][label]);verify()
            dump(C/'numerical-completion.json',dict(resources=resources,adopted=False))
            while cap.available()<=10*1024**3:time.sleep(10)
            update('comparing_all_fields_and_histories')
            resource=cap.run([sys.executable,C/'execution-guard.py',sys.executable,C/'controller.py','worker'],SOURCE,C/'compare.log',env,f'eonsim-fsi-lu-screen-compare-{os.getpid()}.scope',7200)
            proof.clean_resource(resource);report=read(C/'report.json');assert report['numerical_passed'];verify()
            dump(C/'completion.json',dict(comparison_resource=resource,report_sha256=sha(C/'report.json'),eligible=report['eligible'],adopted=False))
            update('completed',passed=True,eligible=report['eligible'])
    except BaseException as error:
        dump(C/'failure.json',dict(error=str(error),traceback=traceback.format_exc()));update('failed',error=str(error));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','verify','run','worker'));a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='verify':print(json.dumps(verify()))
    elif a.action=='run':run()
    else:worker()
