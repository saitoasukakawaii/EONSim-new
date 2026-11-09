"""Bounded sixteen-period startup, thirty-two-cycle coupled comparison with N400 on CPU8."""
import fcntl,hashlib,json,math,os,re,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'elastic-s12-l0-n400-ramp16-c32'
status=work/'elastic-n400-current.json'
prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
cpu=8;warmup=11200;last=12800
assert not out.exists() and not status.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
env=os.environ.copy()
for key in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH'):env.pop(key,None)
env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR=tempfile.mkdtemp(prefix='eonsim-ramp-'))
reference_env=env.copy();reference_env['PATH']='/usr/bin:/bin'
for key in list(reference_env):
    if key=='LD_LIBRARY_PATH' or key.startswith(('OMPI_','PMIX_','PRTE_')):reference_env.pop(key)

def update(state,**kw):
    value=dict(state=state,pid=os.getpid(),cpu=cpu,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(status)
    print(json.dumps(value),flush=True)

def guard():
    processes=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            args=(p/'cmdline').read_bytes().split(b'\0')
            if args and Path(os.fsdecode(args[0])).name in ('eonsim','svFSI'):
                affinity=sorted(os.sched_getaffinity(int(p.name)))
                if cpu in affinity:raise RuntimeError('Numerical CPU overlap')
                processes.append(dict(pid=int(p.name),command=os.fsdecode(args[0]),cpus=affinity))
        except (FileNotFoundError,ProcessLookupError):pass
    memory=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(memory['MemAvailable'].split()[0])<2*1024*1024:raise RuntimeError('Insufficient available memory')
    return dict(cpu=cpu,other_processes=processes,available_memory_kib=int(memory['MemAvailable'].split()[0]))

def run(label,command,cwd,reference=False):
    resources=guard();command=list(map(str,command));update('running',job=label,command=command)
    (out/(label+'-command.json')).write_text(json.dumps(dict(command=command,cwd=str(cwd),resources=resources),indent=2)+'\n')
    with (out/(label+'.log')).open('w') as log:
        subprocess.run(command,cwd=cwd,env=reference_env if reference else env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=7200)
    if re.search(r'\bERROR\b',(out/(label+'.log')).read_text()):raise RuntimeError('Reference logged ERROR')

def accepted(label,first,end):
    text=(out/(label+'.log')).read_text()
    rows=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith('fsi_step=')]
    assert 'status=success' in text and len(rows)==end-first+1
    for step,row in enumerate(rows,first):
        assert int(row['fsi_step'])==step and abs(float(row['time'])-step*cfg['fsi']['dt'])<1e-9
        assert all(math.isfinite(float(row[k])) and float(row[k])>0 for k in ('endpoint_min_fluid_j','endpoint_min_solid_j'))
        assert math.isfinite(float(row['residual']))
    return dict(first_step=first,last_step=end,accepted_count=len(rows),
        minimum_fluid_jacobian=min(float(r['endpoint_min_fluid_j']) for r in rows),
        minimum_solid_jacobian=min(float(r['endpoint_min_solid_j']) for r in rows))

try:
    with (work/'elastic-serial-queue.lock').open('a') as lock:
        update('waiting_for_cpu8_queue',reason='Default N100 reference ALE displacement still fails the unchanged periodic gate; explicit time refinement')
        fcntl.flock(lock,fcntl.LOCK_EX)
        resources=guard();os.sched_setaffinity(0,{cpu})
        prerequisite=json.loads((work/'reference-general-pressure-0b9e980/summary.json').read_text())
        assert all(v['passed'] for v in prerequisite.values())
        tight_probe=json.loads((work/'reference-tight-linear-n400-6093f01/summary.json').read_text())
        assert all(v['passed'] for v in tight_probe.values())
        out.mkdir();shutil.copy2(__file__,out/'original-controller.py')
        source=out/'source';hashes={}
        for name in ('scripts/audit_pressure_tube.py','scripts/audit_svfsi_convergence.py','scripts/export_svfsi_tube.py','scripts/study_rigid_tube.py',
            'scripts/fsi_field_cycles.py','scripts/fsi_cycle_metrics.py','scripts/analyze_womersley.py',
            'scripts/compare_womersley.py','scripts/womersley_reference.py','cases/fsi/generate_tube.py',
            'build/prod48-20261107/compare-pressure-audits.py','build/prod48-20261107/compare-pressure-fields.py'):
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/name,target);hashes[name]=sha(target)
        origin=work/'elastic-s12-l0-region20'
        for name in ('fluid.msh','solid.msh','geometry.json'):shutil.copy2(origin/name,out/name)
        cfg=json.loads((origin/'case.json').read_text());cfg['fsi']['steps']=last;cfg['fsi']['dt']/=4;cfg['fsi']['checkpoint_interval']=400
        cfg['fsi']['pressure_time']['ramp_time']=16*cfg['fsi']['pressure_time']['period']
        case=out/'case.json';case.write_text(json.dumps(cfg,indent=2)+'\n')
        shutil.copy2(work/'eonsim-b072cc8',out/'eonsim')
        (out/'provenance.json').write_text(json.dumps(dict(source_head='6093f01',modified_analysis_sources=hashes,
            eonsim_sha256=sha(out/'eonsim'),uniform_pressure_prerequisite=prerequisite,resources=resources,
            warmup_endpoint=warmup,final_step=last,scope='N400 default-tau time refinement with explicit sixteen-cycle startup and tighter reference linear floor. No physical gate relaxed'),indent=2)+'\n')
        stages={}
        for name,start,end,interval in (('warmup',1,warmup,0),('sample',warmup+1,last,1)):
            directory=out/name;directory.mkdir();current=json.loads(json.dumps(cfg))
            current['mesh']='../fluid.msh';current['fsi']['domains']['solid_mesh']='../solid.msh'
            current['fsi']['output_interval']=interval
            (directory/'case.json').write_text(json.dumps(current,indent=2)+'\n')
            command=[out/'eonsim','-case','case.json','-checkpoint',out/'checkpoint','-stop_after',end]
            if start>1:command+=['-restart',out/'checkpoint']
            run('eonsim-'+name,command,directory);stages[name]=accepted('eonsim-'+name,start,end)
        (out/'accepted-stage-checks.json').write_text(json.dumps(stages,indent=2)+'\n')
        for solid in (False,True):
            suffix='_solid' if solid else '';tree=ET.Element('VTKFile',type='Collection',version='0.1')
            collection=ET.SubElement(tree,'Collection')
            ET.SubElement(collection,'DataSet',timestep=format(warmup*cfg['fsi']['dt'],'.17g'),file='warmup/solution'+suffix+'.vtu')
            sampled=ET.parse(out/'sample'/('solution_restart'+str(warmup)+suffix+'.pvd'))
            for item in sampled.findall('.//DataSet'):
                item.attrib['file']='sample/'+item.attrib['file'];collection.append(item)
            ET.ElementTree(tree).write(out/('solution'+suffix+'.pvd'),encoding='utf-8',xml_declaration=True)
        run('audit-eonsim',[sys.executable,source/'scripts/audit_pressure_tube.py','--case',case,
            '--work',out,'--first-step',warmup+1,'--output',out/'eonsim-audit.json'],root)
        reference=out/'reference'
        run('export-reference',[sys.executable,source/'scripts/export_svfsi_tube.py','--case',case,
            '--output',reference,'--stage-pressure','--general-pressure','--output-start-step',warmup,'--tight-linear-atol','1e-26'],root)
        run('svfsi',[work/'reference/build/bin/svFSI','svFSI.inp'],reference,True)
        run('convergence-svfsi',[sys.executable,source/'scripts/audit_svfsi_convergence.py','--work',reference,
            '--log',out/'svfsi.log','--output',out/'svfsi-convergence.json'],root)
        run('audit-svfsi',[sys.executable,source/'scripts/audit_pressure_tube.py','--case',case,
            '--work',reference,'--svfsi','--reference-log',out/'svfsi.log','--first-step',warmup+1,'--output',out/'svfsi-audit.json'],root)
        run('compare',[sys.executable,source/'build/prod48-20261107/compare-pressure-audits.py',
            '--eonsim',out/'eonsim-audit.json','--svfsi',out/'svfsi-audit.json','--output',out/'comparison.json'],root)
        reports={name:json.loads((out/(name+'-audit.json')).read_text()) for name in ('eonsim','svfsi')}
        update('completed',work=str(out),periodic={k:v['periodic'] for k,v in reports.items()},
            scope='Thirty-two-cycle startup candidate; equivalence to long unmodified startup still unverified')
except Exception as error:
    update('failed',error=str(error));raise
