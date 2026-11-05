import json
from pathlib import Path
import sys
root = Path.cwd()
sys.path.insert(0,str(root/'scripts'))
from analyze_fsi_error_budget import dense_cycles
from analyze_fsi_space import cycle_distance,cross_mesh_cycles
work=Path('/home/tfblab633/EONSim-next03-20261105')
fields={}
summary={'periodic':{},'temporal':{},'spatial':{}}
for n in (2,4,8):
    for dt in ('001','0005'):
        label=f'fixed-n{n}-dt{dt}'
        source=work/label
        receipt=source/'periodic-result.json'
        if receipt.exists():
            data=json.loads(receipt.read_text())
            summary['periodic'][label]={'cycle':data['metrics'][-1]['cycle'],'converged':data['converged']}
        sample=work/('sampling-'+label)/'sampling-result.json'
        if sample.exists():fields[(n,dt)]=dense_cycles(sample,source)
    if all((n,dt) in fields for dt in ('001','0005')):
        summary['temporal'][str(n)]=cycle_distance(fields[(n,'001')],fields[(n,'0005')])
for n in (2,4):
    if all((k,'001') in fields for k in (n,2*n)):
        summary['spatial'][f'{n}-{2*n}']=cross_mesh_cycles(fields[(n,'001')],fields[(2*n,'001')],n)
output=root/'build/resume-20261105/progress-analysis.json'
output.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
