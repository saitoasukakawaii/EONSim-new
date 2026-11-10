"""Original EONSim physical audit with exact archived frame restoration."""
from pathlib import Path
import argparse,importlib.util,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[2];b=ROOT/'build/recompute-20261109';sys.path.insert(0,str(ROOT/'scripts'))
import audit_pressure_tube as original

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def make_reader(work,receipts):
 spec=importlib.util.spec_from_file_location('physical_volume_restore',b/'streaming-volume-materialization.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 work=Path(work).resolve();stores={};saved=original.eonsim_frame
 # Initial endpoint is in early/, which may sort after dense/ within the same archive.
 # Separate cursors keep both actual read sequences monotone without skipping any frame.
 for role in ('early','dense','dense-repeat'):stores[role]=m.Volumes(work,receipts)
 counts={}
 def read(path,domain,solid=False):
  path=Path(path).resolve();rel=str(path.relative_to(work));role='early' if Path(rel).parts[0]=='early' else 'dense';store=stores[role]
  if rel not in store.index:return saved(path,domain,solid)
  occurrence=counts.get(rel,0)
  if occurrence:
   if role!='dense' or occurrence!=1:raise ValueError('Unexpected archived audit read multiplicity')
   store=stores['dense-repeat']
  counts[rel]=occurrence+1
  # Original analyze reads all current phases monotonically and re-reads previous
  # cycle phases in a second monotone sequence. Keep those cursors independent.
  with store.frame([path]):return saved(path,domain,solid)
 return read,stores

def main():
 p=argparse.ArgumentParser();p.add_argument('--case',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--first-step',type=int,required=True);p.add_argument('--receipts',type=Path,action='append',required=True);a=p.parse_args()
 work=a.work.resolve();case=a.case.resolve();proof=a.output.with_suffix('.materialization.json')
 if case!=work/'case.json' or a.output.exists() or proof.exists():raise ValueError('Need original case and fresh output/proof')
 cfg=json.loads(case.read_text());rp=work/'completion.json'
 if not rp.exists():rp=work/'completion-postflight.json'
 if not rp.exists():raise ValueError('Complete trajectory receipt required')
 receipt=json.loads(rp.read_text())
 if receipt['accepted_steps']!=cfg['fsi']['steps'] or not all(r['exit_code']==0 for r in receipt['receipts']):raise ValueError('Complete successful trajectory required')
 receipts=[rp for folder in a.receipts for rp in sorted(folder.glob('*.json'))]
 if not receipts:raise ValueError('No restoration receipts')
 read,stores=make_reader(work,receipts);saved=original.eonsim_frame;original.eonsim_frame=read
 try:
  result=original.analyze(case,work,first_step=a.first_step)
  a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
  print(json.dumps({k:v for k,v in result.items() if k not in ('rows','cycle_differences')}))
 finally:
  original.eonsim_frame=saved
  for store in stores.values():store.close()
  proof.write_text(json.dumps(dict(wrapper_sha256=sha(Path(__file__)),analyzer_sha256=sha(ROOT/'scripts/audit_pressure_tube.py'),materializer_sha256=sha(b/'streaming-volume-materialization.py'),stores={role:s.report() for role,s in stores.items()}),indent=2)+'\n')
if __name__=='__main__':main()
