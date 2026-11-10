"""Independent native-record review and raw binding for the normal-path probe."""
from pathlib import Path
import struct,json,hashlib
b=Path(__file__).resolve().parent;w=b/'reference-strict-increment-equivalence'
r=json.loads((w/'report.json').read_text());assert r['passed'] and not r['adopted']
inputs={};rows=[]
def bind(p):
 raw=p.read_bytes();inputs[str(p.relative_to(b))]=hashlib.sha256(raw).hexdigest();return raw
def actual(folder,kind,step):
 matches=[p for p in folder.glob(kind+'_*') if p.stem.rsplit('_',1)[-1].isdigit() and int(p.stem.rsplit('_',1)[-1])==step]
 assert len(matches)==1;return matches[0]
for name,baseline,first,last in [('startup-increment','startup-old',1,20),('loaded-increment','loaded-old',12401,12420),('loaded-replay','loaded-increment',12411,12420)]:
 maximum=0.;pairs=0
 for step in range(first,last+1):
  folders=[w/baseline/'results',w/name/'results'];raw=[bind(actual(p,'stFile',step)) for p in folders]
  for p in folders:bind(actual(p,'result',step))
  assert len(raw[0])==len(raw[1]);stamp=[struct.unpack_from('<8i',v) for v in raw];assert stamp[0]==stamp[1] and stamp[0][-1]==step
  n=stamp[0][3];assert len(raw[0])==64+3*7*n*8
  assert raw[0][32:40]==raw[1][32:40] and raw[0][48:64]==raw[1][48:64]
  values=[struct.unpack_from('<'+str(21*n)+'d',v,64) for v in raw]
  maximum=max(maximum,max(abs(x-y) for x,y in zip(*values)));pairs+=1
  if name=='loaded-replay':assert raw[0][:40]+raw[0][48:]==raw[1][:40]+raw[1][48:]
 assert maximum<r['definition']['history_limit'];assert maximum==r['comparisons'][name]['maximum_native_history_delta']
 rows.append(dict(name=name,pairs=pairs,maximum_native_history_delta=maximum,exact_time_and_saved_norms=True))
for p in [w/'candidate-svFSI',w/'original-svFSI',w/'report.json',Path(__file__)]:bind(p)
for name,run in r['runs'].items():
 export=json.loads((w/name/'export.json').read_text())
 for rel,digest in export['files'].items():assert hashlib.sha256(bind(w/name/rel)).hexdigest()==digest
 convergence=json.loads(bind(w/name/'convergence.json'));assert convergence['passed']
 assert hashlib.sha256(bind(w/name/'solve.log')).hexdigest()==convergence['log_sha256']
result=dict(passed=True,comparisons=rows,consumed_sha256=inputs,scope='Independent struct-decoded native state/time/norm review plus field-file hashes; P1 field metrics remain the primary report evidence; no production adoption')
(w/'independent-review.json').write_text(json.dumps(result,indent=2)+'\n');print(rows)
