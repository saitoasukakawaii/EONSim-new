import csv
import json
import math
from pathlib import Path
import sys
root=Path.cwd();sys.path.insert(0,str(root/'scripts'))
from fsi_cycle_metrics import volume_budget
work=Path('/home/tfblab633/EONSim-next03-20261105')
results={}
def read(path):
    with path.open() as stream:return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(stream)]
for n in (2,4,8):
    for dt in ('001','0005'):
        label=f'fixed-n{n}-dt{dt}';source=work/label
        if not (source/'periodic-result.json').exists():continue
        saved=json.loads((source/'periodic-result.json').read_text())
        if not saved['converged']:continue
        cycle=saved['metrics'][-1]['cycle'];steps=round(.1/saved['config']['fsi']['dt'])
        initial=read(source/f'cycle{cycle}_restart{(cycle-1)*steps}.csv')[-1]
        for kind,name in (('tail','transient-result.json'),('sampling','sampling-result.json')):
            folder=work/(kind+'-'+label);path=folder/name
            if not path.exists():continue
            result=json.loads(path.read_text());previous=initial
            blocks=result['blocks'] if kind=='tail' else [dict(end_cycle=result['end_cycle'])]
            checks=[]
            for i,block in enumerate(blocks,1):
                end=block['end_cycle'];start_step=int(previous['step']);stem=f'block{i}' if kind=='tail' else 'dense'
                rows=read(folder/f'{stem}_restart{start_step}.csv')
                if len(rows)!=end*steps-start_step or abs(rows[-1]['time']-end*.1)>1e-10:
                    raise RuntimeError('Incomplete continuation history: '+str(folder))
                if any(not math.isfinite(v) for row in rows for v in row.values()):raise RuntimeError('Nonfinite continuation')
                if any(row['step']!=start_step+j for j,row in enumerate(rows,1)):raise RuntimeError('Skipped accepted step')
                budget=volume_budget(rows,initial_time=previous['time'],initial_volume=previous['endpoint_volume'],
                    initial_net_flow=previous['endpoint_inlet_flow']-previous['endpoint_outlet_flow'])
                balance=dict(stage_mass=max(abs(r['stage_mass_residual']) for r in rows),
                    surface_divergence=max(abs(r['stage_mass_residual']+r['stage_divergence']) for r in rows),
                    inlet_flow=max(abs(r['endpoint_inlet_flow']-r['target_endpoint_flow']) for r in rows),
                    minimum_j=min(v for r in rows for k,v in r.items() if k.endswith('_j')))
                if balance['stage_mass']>1e-9 or balance['surface_divergence']>1e-12 or balance['inlet_flow']>1e-12 or balance['minimum_j']<=0:
                    raise RuntimeError('Continuation flow/geometry gate failed: '+str(folder))
                checks.append(dict(accepted_rows=len(rows),end_cycle=end,flow_balance=balance,mass_budget=budget))
                previous=rows[-1]
            results[folder.name]=checks
output=root/'build/resume-20261105/continuation-history-audit.json'
output.write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(dict(continuations=len(results),accepted_rows=sum(c['accepted_rows'] for r in results.values() for c in r),
                     maximum_stage_mass=max(c['flow_balance']['stage_mass'] for r in results.values() for c in r))),flush=True)
