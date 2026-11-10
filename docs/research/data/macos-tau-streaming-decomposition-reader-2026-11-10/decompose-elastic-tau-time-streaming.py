"""Restore archived default fields per phase; execute the original full tau-time decomposition."""
from pathlib import Path
import importlib.util,json,sys
b=Path(__file__).resolve().parent

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def make_study(fields):
 materializer=module('tau_volume_materializer',b/'streaming-volume-materialization.py')
 receipts={(b/f'elastic-s24-l1-n{n}').resolve():[b/f'archives/elastic-s24-l1-n{n}-volume-materialization.json'] for n in [400,800]}
 stores={};Original=fields.Study
 class StreamingStudy(Original):
  def frame(self,step):
   if self.work not in receipts:return super().frame(step)
   if self.work not in stores:stores[self.work]=materializer.Volumes(self.work,receipts[self.work])
   with stores[self.work].frame(self.paths[step]):return super().frame(step)
 return StreamingStudy,stores

def main():
 original=module('original_tau_decomposition',b/'decompose-elastic-tau-time.py')
 # Check actual completion before creating a restoration sidecar or reading archives.
 for option in ['--target','--control','--fine']:
  work=Path(sys.argv[sys.argv.index(option)+1]).resolve()
  path=work/('completion.json' if (work/'completion.json').exists() else 'completion-postflight.json')
  if not path.is_file():raise ValueError('Incomplete numerical study; no restoration started')
 output=Path(sys.argv[sys.argv.index('--output')+1]).resolve();proof=output.with_suffix('.materialization.json')
 if output.exists() or proof.exists():raise ValueError('Refuse overwrite')
 cls,stores=make_study(original.fields);old=original.fields.Study;original.fields.Study=cls
 try:original.main()
 finally:
  original.fields.Study=old
  for store in stores.values():store.close()
  data=dict(wrapper_sha256=original.sha(Path(__file__)),decomposition_sha256=original.sha(b/'decompose-elastic-tau-time.py'),materializer_sha256=original.sha(b/'streaming-volume-materialization.py'),stores={str(w):s.report() for w,s in stores.items()},scope='Original full400-phase decomposition and exact cross terms unchanged; restore each requested default field at original path and remove created copy after reading. Diagnostic control fields remain original.')
  with proof.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
if __name__=='__main__':main()
