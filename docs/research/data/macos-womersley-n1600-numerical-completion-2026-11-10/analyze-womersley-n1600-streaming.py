"""Run the original complete Womersley analytic audit with bounded cycle4 and complete cycle5 interior restoration."""
from pathlib import Path
import importlib.util,json,hashlib,sys,argparse
ROOT=Path(__file__).resolve().parents[2]
b=ROOT/'build/recompute-20261109'
sys.path.insert(0,str(ROOT/'scripts'))
import analyze_womersley as original

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def make_study(original,b):
 spec=importlib.util.spec_from_file_location('hdf_materializer',b/'streaming-hdf-materialization.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 work=(b/'alpha2-s96-l1-n1600').resolve();receipts=sorted((b/'archives/alpha2-s96-l1-n1600-cycle4-chunks').glob('*.json'))
 assert len(receipts)==39
 extra=sorted((b/'archives/alpha2-s96-l1-n1600-cycle5-prefix7200-chunks').glob('*.json'));assert len(extra)==20
 receipts+=extra
 tail=sorted((b/'archives/alpha2-s96-l1-n1600-cycle5-tail7999-chunks').glob('*.json'));assert len(tail)==20
 receipts+=tail
 sixth=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-prefix8800-chunks').glob('*.json'));assert len(sixth)==20
 receipts+=sixth
 sixth_tail=sorted((b/'archives/alpha2-s96-l1-n1600-cycle6-tail9360-chunks').glob('*.json'));assert len(sixth_tail)==14
 receipts+=sixth_tail
 stores={}
 class StreamingStudy(original.Study):
  def __init__(self,path):
   if Path(path).resolve()!=work:raise ValueError('Only the recorded alpha2 fine N1600 study is supported')
   super().__init__(path)
  def state(self,step):
   if not (4800<step<6400 or 6401<=step<=7999 or 8001<=step<=9360):return super().state(step)
   if self.work not in stores:stores[self.work]=m.Volumes(self.work,receipts)
   path=self.generations[step][0]/'state_rank0.h5'
   with stores[self.work].frame([path]):return super().state(step)
 return StreamingStudy,stores

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--quadrature',type=int,default=4);args=parser.parse_args()
 work=b/'alpha2-s96-l1-n1600'
 if args.work.resolve()!=work.resolve() or args.output.exists() or args.quadrature!=4:raise ValueError('Need original study, quadrature4, and a fresh output')
 receipt=json.loads((work/'receipt.json').read_text())
 if receipt['step']!=9600:raise RuntimeError('Complete six-cycle receipt required before analysis')
 cls,stores=make_study(original,b);saved=original.Study;original.Study=cls
 proof=b/'alpha2-s96-l1-n1600-streaming-analysis-proof.json'
 if proof.exists():raise ValueError('Refuse to overwrite prior materialization proof')
 try:original.main()
 finally:
  original.Study=saved
  for store in stores.values():store.close()
  proof.write_text(json.dumps(dict(wrapper_sha256=sha(Path(__file__)),analyzer_sha256=sha(ROOT/'scripts/analyze_womersley.py'),materializer_sha256=sha(b/'streaming-hdf-materialization.py'),stores={str(w):s.report() for w,s in stores.items()}),indent=2)+'\n')
if __name__=='__main__':main()
