"""Bounded FSI-NEXT-02 temporal, spatial and multi-cycle mass study (not default CTest)."""
import argparse
import json
import csv
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from verify_fsi_inlet import Runner, generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',required=True)
    p.add_argument('--analyze-only',action='store_true',help='Read existing accepted CSVs; do not rerun solves')
    a=p.parse_args();work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=True)
    summary=[]
    for n,dt in ((2,.002),(2,.001),(2,.0005),(3,.001),(4,.001)):
        run=Runner(a.executable,a.mpiexec,work/f'n{n}-dt{dt}',timeout=1800)
        if a.analyze_only:
            with (run.work/'flow.csv').open() as stream: rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
            assert len(rows)==round(.62/dt) and abs(rows[-1]['time']-.62)<1e-12
        else:
            cfg=json.loads(generate(run.work,n=n,periodic_flow=True).read_text())
            cfg['fsi'].update(dt=dt,steps=round(.62/dt),output_interval=round(.1/dt))
            _,rows,_=run.solve('flow',cfg,2)
        steady=[r for r in rows if r['time']>.42-1e-10]
        cycle=round(.1/dt)
        drift=max(abs(rows[-cycle+i]['area_displacement_y']-rows[-2*cycle+i]['area_displacement_y']) for i in range(cycle))
        # Actual accepted-step rectangles at the solver's stage (not trapezoid or endpoint).
        accumulated=sum(r['accepted_dt']*r['secant_mass_residual'] for r in rows)
        trapezoid=0.;previous_net=0.
        for row in rows:
            net=row['endpoint_inlet_flow']-row['endpoint_outlet_flow']
            trapezoid+=.5*(net+previous_net)*row['accepted_dt'];previous_net=net
        trapezoid-=rows[-1]['endpoint_volume']-1
        assert abs(trapezoid)<1e-6
        result=dict(trapezoid_volume_error=trapezoid,n=n,dt=dt,steps=len(rows),max_mass_residual=max(abs(r['stage_mass_residual']) for r in rows),
                    max_secant_residual=max(abs(r['secant_mass_residual']) for r in steady),
                    volume_balance_error=accumulated,cycle_displacement_difference=drift,
                    final_displacement=rows[-1]['area_displacement_y'],
                    final_volume=rows[-1]['endpoint_volume'],
                    displacement_min=min(r['area_displacement_y'] for r in steady),displacement_max=max(r['area_displacement_y'] for r in steady))
        assert result['max_mass_residual']<1e-9,result
        summary.append(result);(work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    # For this smooth driven trajectory, secant/stage mismatch must diminish with dt.
    assert summary[1]['max_secant_residual']<.8*summary[0]['max_secant_residual']
    assert summary[2]['max_secant_residual']<.8*summary[1]['max_secant_residual']
    assert abs(summary[1]['trapezoid_volume_error'])<abs(summary[0]['trapezoid_volume_error'])
    assert abs(summary[2]['trapezoid_volume_error'])<abs(summary[1]['trapezoid_volume_error'])
    print('study analysis complete' if a.analyze_only else 'study complete',flush=True)
if __name__=='__main__':main()
