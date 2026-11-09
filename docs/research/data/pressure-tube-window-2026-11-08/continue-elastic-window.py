"""One separately pinned serial elastic study beside the primary MPI queue."""
import fcntl,hashlib,json,math,os,re,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
prefix=Path('/home/tfblab633/EONSim/.cloud/petsc-3.23.7')
source=work/'elastic-s12-l0-region20'
out=work/'elastic-s12-l0-n100-c132-window'
status=work/'elastic-window-current.json'
assert not out.exists() and not status.exists()
cpu=8;warmup=12800;last=13200
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
env=os.environ.copy()
for k in ('LD_LIBRARY_PATH','LIBRARY_PATH','PETSC_DIR','PETSC_ARCH','PKG_CONFIG_PATH'):env.pop(k,None)
env.update(PATH=str(prefix/'bin')+':/usr/bin:/bin',LD_LIBRARY_PATH=str(prefix/'lib'),
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    OMPI_MCA_btl='self,sm,tcp',OMPI_MCA_pml='ob1',TMPDIR=tempfile.mkdtemp(prefix='eonsim-elastic-window-'))
def update(state,**kwargs):
    value=dict(state=state,pid=os.getpid(),cpu=cpu,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kwargs)
    tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(status)
    print(json.dumps(value),flush=True)
def guard():
    mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(mem['MemAvailable'].split()[0])<2*1024*1024:raise RuntimeError('Insufficient available memory for the serial job')
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:
            command=(process/'cmdline').read_bytes().split(b'\0')
            if command and b'womersley-a2-s48-l2-n200-chord-m200/eonsim' in command[0]:
                if cpu in os.sched_getaffinity(int(process.name)):
                    raise RuntimeError('Primary MPI affinity overlaps reserved serial CPU')
        except (FileNotFoundError,ProcessLookupError):pass
def run(label,command,cwd,timeout=10800):
    guard();command=list(map(str,command))
    update('running',job=label,command=command,cwd=str(cwd))
    (out/(label+'-command.json')).write_text(json.dumps(dict(command=command,cwd=str(cwd)),indent=2)+'\n')
    with (out/(label+'.log')).open('w') as log:
        subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
def check_eon(label,first,end):
    text=(out/(label+'.log')).read_text()
    rows=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines() if line.startswith('fsi_step=')]
    if 'status=success' not in text or len(rows)!=end-first+1:raise ValueError('Incomplete EONSim accepted sequence')
    for step,row in enumerate(rows,first):
        if int(row['fsi_step'])!=step or abs(float(row['time'])-step*cfg['fsi']['dt'])>1e-9:
            raise ValueError('EONSim accepted clock changed')
        if any(not math.isfinite(float(row[k])) or float(row[k])<=0 for k in ('endpoint_min_fluid_j','endpoint_min_solid_j')):
            raise ValueError('Invalid accepted endpoint geometry')
        if not math.isfinite(float(row['residual'])):raise ValueError('Nonfinite accepted residual')
    return dict(first_step=first,last_step=end,accepted_count=len(rows),
        minimum_fluid_jacobian=min(float(r['endpoint_min_fluid_j']) for r in rows),
        minimum_solid_jacobian=min(float(r['endpoint_min_solid_j']) for r in rows))
try:
    with (work/'elastic-serial-queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if cpu not in os.sched_getaffinity(0):raise ValueError('Reserved serial CPU is not available')
        os.sched_setaffinity(0,{cpu});guard()
        out.mkdir();shutil.copy2(__file__,out/'original-controller.py')
        analysis_root=out/'analysis-source'
        analysis_hashes={}
        for name in ('scripts/audit_pressure_tube.py','scripts/export_svfsi_tube.py','scripts/study_rigid_tube.py',
            'scripts/fsi_field_cycles.py','scripts/fsi_cycle_metrics.py','cases/fsi/generate_tube.py',
            'build/prod48-20261107/compare-pressure-audits.py'):
            target=analysis_root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(root/name,target);analysis_hashes[name]=sha(target)
        (out/'analysis-sources.json').write_text(json.dumps(analysis_hashes,indent=2)+'\n')
        shutil.copy2(work/'resource-observation-2eabb47.json',out/'resource-observation.json')
        for name in ('fluid.msh','solid.msh','geometry.json'):shutil.copy2(source/name,out/name)
        cfg=json.loads((source/'case.json').read_text());cfg['fsi']['steps']=last
        (out/'case.json').write_text(json.dumps(cfg,indent=2)+'\n')
        marker,generation=(source/'checkpoint/current').read_text().split()
        origin=source/'checkpoint'/generation
        words=(origin/'manifest').read_text().split()
        assert marker=='EONSim_checkpoint_v3' and words[1]=='1' and words[2]=='600'
        assert abs(float(words[3])-600*cfg['fsi']['dt'])<1e-9
        shutil.copytree(origin,out/'checkpoint'/generation)
        hashes={p.name:sha(p) for p in origin.iterdir() if p.is_file()}
        assert all(sha(out/'checkpoint'/generation/name)==digest for name,digest in hashes.items())
        (out/'checkpoint/current').write_text(marker+' '+generation+'\n')
        shutil.copy2(work/'eonsim-b072cc8',out/'eonsim')
        (out/'provenance.json').write_text(json.dumps(dict(source_study=str(source),source_case_sha256=sha(source/'case.json'),
            checkpoint_generation=generation,checkpoint_hashes=hashes,executable_sha256=sha(out/'eonsim'),
            first_new_step=601,warmup_endpoint=warmup,final_step=last,cpu=cpu,
            policy='One serial study on CPU8, separate from primary four-rank queue on CPUs0-7; no performance comparison'),indent=2)+'\n')
        stages={}
        for name,start,end,interval in (('warmup',601,warmup,0),('sample',warmup+1,last,1)):
            directory=out/name;directory.mkdir()
            current=json.loads(json.dumps(cfg));current['mesh']='../fluid.msh'
            current['fsi']['domains']['solid_mesh']='../solid.msh'
            current['fsi']['output_interval']=interval
            (directory/'case.json').write_text(json.dumps(current,indent=2)+'\n')
            run('eonsim-'+name,[out/'eonsim','-case','case.json','-restart',out/'checkpoint',
                '-checkpoint',out/'checkpoint','-stop_after',end],directory)
            stages[name]=check_eon('eonsim-'+name,start,end)
        (out/'accepted-stage-checks.json').write_text(json.dumps(stages,indent=2)+'\n')
        for solid in (False,True):
            suffix='_solid' if solid else ''
            tree=ET.Element('VTKFile',type='Collection',version='0.1');collection=ET.SubElement(tree,'Collection')
            ET.SubElement(collection,'DataSet',timestep=format(warmup*cfg['fsi']['dt'],'.17g'),file='warmup/solution'+suffix+'.vtu')
            sampled=ET.parse(out/'sample'/('solution_restart'+str(warmup)+suffix+'.pvd'))
            for item in sampled.findall('.//DataSet'):
                item.attrib['file']='sample/'+item.attrib['file'];collection.append(item)
            ET.ElementTree(tree).write(out/('solution'+suffix+'.pvd'),encoding='utf-8',xml_declaration=True)
        run('audit-eonsim',[sys.executable,analysis_root/'scripts/audit_pressure_tube.py','--case',out/'case.json',
            '--work',out,'--first-step',warmup+1,'--output',out/'eonsim-audit.json'],root,1800)
        ref=out/'reference'
        run('export-reference',[sys.executable,analysis_root/'scripts/export_svfsi_tube.py','--case',out/'case.json',
            '--output',ref,'--stage-pressure','--output-start-step',warmup],root,600)
        reference_env=env.copy();reference_env['PATH']='/usr/bin:/bin';reference_env.pop('LD_LIBRARY_PATH',None)
        # The system-built reference must not load the locked EONSim MPI ABI.
        saved_env=env;env=reference_env
        run('svfsi-long',[work/'reference/build/bin/svFSI','svFSI.inp'],ref)
        env=saved_env
        if re.search(r'\bERROR\b',(out/'svfsi-long.log').read_text()):raise ValueError('Reference reported ERROR')
        actual={int(p.stem.rsplit('_',1)[1]) for p in (ref/'results').glob('result_*.vtu')}
        if actual!=set(range(warmup,last+1)):raise ValueError('Reference saved window differs')
        run('audit-svfsi',[sys.executable,analysis_root/'scripts/audit_pressure_tube.py','--case',out/'case.json',
            '--work',ref,'--svfsi','--first-step',warmup+1,'--output',out/'svfsi-audit.json'],root,1800)
        run('compare',[sys.executable,analysis_root/'build/prod48-20261107/compare-pressure-audits.py',
            '--eonsim',out/'eonsim-audit.json','--svfsi',out/'svfsi-audit.json','--output',out/'comparison.json'],root,300)
        reports={name:json.loads((out/(name+'-audit.json')).read_text()) for name in ('eonsim','svfsi')}
        update('completed',work=str(out),periodic={k:v['periodic'] for k,v in reports.items()},
            scope='Stored late cycles analyzed; full physical qualification remains incomplete')
except Exception as error:
    update('failed',error=str(error));raise
