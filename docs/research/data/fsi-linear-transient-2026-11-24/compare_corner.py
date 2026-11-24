"""Replay 97 directly coincident tube sections, identity-block condensation and unsuccessful grid receipts."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path


def pack(root):
    accepted=[]
    rejected=[]
    for time in sorted([*root.glob('axisym-corner-x*.json.time'),*root.glob('condensed-x*.time')]):
        resource=json.loads(time.read_text())
        key=time.name.removesuffix('.time').removesuffix('.json')
        source=root/(key+'.json')
        if resource['exit_code']!=0:
            rejected.append(dict(case=key,resource=resource))
            continue
        raw=source.read_bytes()
        accepted.append(dict(case=key,sha256=hashlib.sha256(raw).hexdigest(),resource=resource,reference=json.loads(raw)))
    return dict(completed=accepted,rejected=rejected)


def compare(data):
    refs=[r['reference'] for r in data['completed']]
    if not refs:raise ValueError('No successful meridian calculations')
    fine=max(refs,key=lambda d:(d['unknowns'],d['corner_levels'],d['stage_solver']=='condensed-pair',d.get('pivot_threshold') is None))
    if len(fine['sections'])!=97 or not math.isclose(fine['sections'][48],1.):raise ValueError('Incorrect physical sections')
    m=fine['parameters']
    a,b,nu,e=m['radius'],m['outer_radius'],m['poisson'],m['young']
    static=fine['pressure']*2*(1+nu)*((1-2*nu)*a*a+b*b)/(e*(b*b-a*a))
    rows=[]
    def run(d,n):
        found=[v for v in d['runs'] if v['steps']==n]
        if len(found)!=1:raise ValueError('Missing Radau resolution')
        return found[0]
    def phases(v):
        if [s['time'] for s in v['samples']]!=[.5,1.]:raise ValueError('Mismatched sample time')
        return [s['section_area_strain'] for s in v['samples']]
    def difference(x,y):
        if len(x)!=97 or len(y)!=97 or not all(math.isfinite(z) for z in x+y):
            raise ValueError('Incomplete or nonfinite meridian sections')
        return [100*(a-b)/static for a,b in zip(x,y)]
    for r in data['completed']:
        d=r['reference']
        for field in ('parameters','sections','pressure','quadrature','full_length'):
            if d[field]!=fine[field]:raise ValueError('Different problem, quadrature or axial coordinates')
        if d['static']['equilibrium_residual']>1e-8 or d['static']['relative_lame_area_error']>1e-5:
            raise ValueError('Failed static Lamé check')
        v=run(d,256);old=run(d,128)
        alternate = ('condensed-pair' if d.get('pivot_threshold') is not None or d['stage_solver']=='complex-pair' else 'complex-pair')
        same=[x for x in refs if x['mesh']==d['mesh'] and x['corner_levels']==d['corner_levels']
              and x.get('pivot_threshold') is None and x['stage_solver']==alternate]
        if len(same)>1:raise ValueError('Ambiguous paired stage solver')
        for step in (old,v):
            if max(step['max_power_residual_over_peak'],step['max_flux_residual_over_peak'])>1e-7 or step['stage_residual_max']>1e-9:
                raise ValueError(f'Unbalanced Radau stage in {r["case"]}')
        stats=v.get('stage_factor',{})
        for i,t in enumerate((.5,1.)):
            y=phases(v)[i];time_change=max(map(abs,difference(y,phases(old)[i])))
            dx=difference(y,phases(run(fine,256))[i]);j=max(range(97),key=lambda k:abs(dx[k]))
            paired=None
            if same:
                paired=max(max(map(abs,difference(phases(run(d,n))[i],phases(run(same[0],n))[i]))) for n in (128,256))
                if paired>1e-5:raise ValueError('Stage condensation changed a measured area above numerical roundoff')
            q=r['resource']
            rows.append(dict(case=r['case'],axial_per_half=d['mesh'][0],radial_fluid=d['mesh'][1],radial_wall=d['mesh'][2],
                        corner_levels=d['corner_levels'],solver=d['stage_solver'],pivot_threshold=d.get('pivot_threshold'),full_unknowns=d['unknowns'],
                        factored_unknowns=stats.get('factored_size'),superlu_reported_nnz=stats.get('superlu_reported_nnz'),
                        time=t,end_pct_initial_area=100*y[0],mid_pct_initial_area=100*y[48],
                        max_difference_to_finest_pct_static=abs(dx[j]),worst_station_m=d['sections'][j],
                        temporal_128_to_256_pct_static=time_change,paired_solver_max_change_pct_static=paired,
                        max_power_defect=v['max_power_residual_over_peak'],max_mass_defect=v['max_flux_residual_over_peak'],
                        peak_rss_mib=q['max_rss_kib']/1024,cpu_seconds=q['user_seconds']+q['sys_seconds'],elapsed_seconds=q['seconds']))
    return rows,fine


def main():
    p=argparse.ArgumentParser(description=__doc__)
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--runs',type=Path);inputs.add_argument('--archive',type=Path)
    p.add_argument('--write-archive',type=Path);p.add_argument('--finest',type=Path,required=True);p.add_argument('--csv',type=Path,required=True)
    a=p.parse_args()
    d=pack(a.runs) if a.runs else json.loads(lzma.decompress(a.archive.read_bytes()))
    rows,fine=compare(d)
    if a.write_archive:a.write_archive.write_bytes(lzma.compress(json.dumps(d,separators=(',',':'),allow_nan=False).encode()))
    with a.csv.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    a.finest.write_text(json.dumps(fine,indent=2,allow_nan=False)+'\n')
    print(len(rows)//2,'accepted runs;',len(d['rejected']),'unsuccessful controls;',fine['unknowns'],'finest unknowns')


if __name__=='__main__':main()
