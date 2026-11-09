"""Queue the complete sealed N800 control and its N400-target budget archive."""
import hashlib,importlib.util,json,os,shutil,time,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[2]
w=Path('/home/tfblab633/EONSim-prod48-20261107');d=Path('/mnt/d/EONSim-prod48-20261107')
c=w/'s96-n800-complete-capture-ab0d107';status=w/'s96-n800-complete-capture-current.json'
family=w/'s96-n400-qualified-family-a3e1c87';producer=w/'s96-n400-qualified-family-current.json'
study=d/'womersley-a2-s96-r8-a8-l1-n800-native-serial32-a3e1c87'
previous=w/'alpha1-complete-family-capture-current.json'
archive='womersley-s96-n800-n400-target-budget-2026-11-09'
prior_names=['womersley-s96-n400-complete-family-2026-11-09','womersley-s96-native-coarse-time-pair-2026-11-08']
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def update(state,**kw):
 v=dict(state=state,pid=os.getpid(),utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),control=str(c),archive=archive,**kw)
 q=status.with_suffix('.tmp');dump(q,v);q.replace(status);print(json.dumps(v),flush=True)
def identity(pid):
 try:
  s=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
  return dict(pid=pid,start_ticks=int(s[19]),state=s[0])
 except (FileNotFoundError,ProcessLookupError):return None
def live(original):
 if original is None:return False
 now=identity(original['pid'])
 return bool(now and now['start_ticks']==original['start_ticks'] and now['state'] not in ('Z','X'))
def resources():
 result={}
 for p in family.glob('*.resource.json'):
  r=read(p)
  assert r['returncode']==0 and not r['remaining_scope_members']
  assert r['memory_max_bytes']==6*1024**3 and r['memory_swap_max_bytes']==0
  assert all(int(s.split()[1])==0 for s in r['memory_events'].splitlines())
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:assert r['unit'] not in (proc/'cgroup').read_text()
   except (FileNotFoundError,ProcessLookupError):pass
  result[p.name]=sha(p)
 assert set(result)=={n+'.resource.json' for n in read(family/'commands.json')}
 return result
assert not c.exists() and not status.exists()
assert not (root/'docs/research/data'/archive/'archives.json').exists()
assert not (d/'repository-archives'/archive).exists()
first=read(producer);prior_first=read(previous)
assert first['pid']==41187 and prior_first['pid']==42447
producer_identity=identity(first['pid']);capture_identity=identity(prior_first['pid'])
definition=read(family/'definition.json')
assert definition['binary_sha256']=='60eb5cc0c2ea0d03e70881b42f0219a7525461fdf3d5a63cec15333c3cb54f07'
assert definition['controller_sha256']=='23608c1338d872349a62f1bdb9819661a3441919a31108d1b9dcfc09bacfa50c'
assert definition['time_control']==str(study) and definition['steps_per_cycle']==[400,400,800]
c.mkdir();shutil.copy2(__file__,c/'controller.py')
helper=root/'build/prod48-20261107/capture-ranked-external-evidence.py'
assert sha(helper)=='81dba5d266e9cde0c74f0ae8a073e54dc6075427bd583b65ddd10ea9a2e58533'
spec=importlib.util.spec_from_file_location('capture',helper);cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
dump(c/'definition.json',dict(base='ab0d107f8f73ae2512669d72f3237d8db14b21c0',controller_sha256=sha(c/'controller.py'),
 producer_definition_sha256=sha(family/'definition.json'),producer_identity=producer_identity,prior_capture_identity=capture_identity,
 prior_archive_names=prior_names,cpus=[15],nice=19,shared_cpu=True,
 scope='Read-only complete archive after N8004800 plus all N400-target reports and clean resources. Wait for prior CPU15 capture to exit and referenced complete archives to be indexed. Preserve failed old N200 budget and all new gates. No numerical rerun, source edit, signal, automatic staging or qualification.'))
try:
 update('waiting_for_complete_n800_and_prior_capture',holds_locks=False)
 while True:
  s=read(producer);p=read(previous)
  if s['state']=='failed':raise RuntimeError('N800 family failed; no complete-family archive may be claimed')
  if s['state']=='completed' and p['state'] in ('completed','failed') and not live(capture_identity):
   prior_terminal=p;break
  time.sleep(10)
 deadline=time.monotonic()+30
 while live(producer_identity):assert time.monotonic()<deadline,'Completed N800 producer remains live';time.sleep(.5)
 assert read(study/'receipt.json')['step']==4800
 n=read(study/'definition.json')
 assert n['alpha']==2 and n['seed']==[96,8,8] and n['level']==1 and n['ranks']==1
 assert n['steps_per_cycle']==n['phases']==800 and n['warmup']==2
 numerical_command=read(family/'commands.json')['fine-n800']
 assert numerical_command[numerical_command.index('--cycles')+1]=='6'
 assert numerical_command[numerical_command.index('--warmup')+1]=='2'
 assert n['tau'] is None and 'tau_time_scale' not in n
 assert sha(study/'eonsim')==n['executable_sha256']==definition['binary_sha256']
 assert sha(family/'definition.json')==read(c/'definition.json')['producer_definition_sha256']
 assert sha(family/'controller.py')==definition['controller_sha256']
 for name,z in definition['source_hashes'].items():assert sha(family/'source'/name)==z
 for name,z in definition['file_hashes'].items():assert sha(family/name)==z
 for path,z in definition['input_hashes'].items():assert sha(path)==z
 reports=['prior-n200-budget.json','n400-analysis.json','n800-analysis.json','middle-analysis.json','space-n400.json',
  'time-n400-n800.json','tail-n400.json','tail-n800.json','sampling-200-400.json','sampling-400-800.json','budget.json']
 assert all((family/name).is_file() for name in reports)
 budget=read(family/'budget.json');old=read(family/'prior-n200-budget.json')
 assert old['passed'] is False and budget['limit_fraction']==.1 and budget['passed']==s['passed']
 assert set(budget['fields'])=={'velocity','pressure'}
 assert all(set(v['terms'])=={'time','tail','sampling'} for v in budget['fields'].values())
 resource_hashes=resources()
 update('waiting_for_complete_prior_archive_index',holds_locks=False)
 while not all((root/'docs/research/data'/name/'index-staging.json').exists() for name in prior_names):time.sleep(10)
 references={}
 for name in prior_names:
  folder=root/'docs/research/data'/name;a=read(folder/'archives.json');r=read(folder/'index-staging.json')
  assert r['passed'] and r['archives_json_sha256']==sha(folder/'archives.json')
  assert len(a['archives'])==len(r['archives'])
  for part,row in zip(a['archives'],r['archives']):
   for key in ('file','bytes','sha256'):assert part[key]==row[key]
  references[name]=dict(archives_sha256=sha(folder/'archives.json'),manifest_sha256=sha(folder/'manifest.json'),
   indexed_parts=[dict(file=v['file'],blob_oid=v['blob_oid'],sha256=v['sha256']) for v in r['archives']])
 snapshot=c/'reports';snapshot.mkdir();copies=[]
 for name in reports:
  p=snapshot/name;shutil.copy2(family/name,p);assert sha(p)==sha(family/name);copies.append(p)
 dump(snapshot/'summary.json',dict(producer=s,step=4800,prior_capture_terminal=prior_terminal,
  n400_gates=read(family/'n400-analysis.json')['preliminary_gates'],n800_gates=read(family/'n800-analysis.json')['preliminary_gates'],
  n400_target_budget=budget,old_failed_n200_budget=old,resource_hashes=resource_hashes,prior_complete_archives=references,
  full_project_qualification=False,scope='Complete retained raw N800 states/current/history and all source, numerical logs, cycle receipts, analyses and unchanged N400-target budget. Prior full coarse/fine N400 states are SHA-linked. N800 is a time control, not independently spatially qualified.'))
 copies.append(snapshot/'summary.json')
 files=[p for folder in (study,family) for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 files.extend(copies+[c/'controller.py',c/'definition.json'])
 os.sched_setaffinity(0,{15});os.nice(19);update('capturing')
 cap.capture(archive,files,copies)
 for name in reports:assert sha(snapshot/name)==sha(family/name)
 for name,z in resource_hashes.items():assert sha(family/name)==z
 update('completed',git_staging_complete=False,full_project_qualification=False)
except BaseException as error:
 dump(c/'failure.json',dict(error=str(error),traceback=traceback.format_exc(),full_project_qualification=False))
 update('failed',error=str(error));raise
