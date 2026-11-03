"""Guard against false periodicity from offsets, row alignment and truncated cycles."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from fsi_cycle_metrics import compare_cycles,volume_budget


class Cycles(unittest.TestCase):
    def test_periodic_with_offset(self):
        t=[i/128 for i in range(257)]
        r=compare_cycles(t,[1e3+math.sin(2*math.pi*x) for x in t],1,2,1)
        self.assertLess(r['relative_max'],1e-12)

    def test_mean_drift_cannot_hide_in_offset(self):
        t=[i/128 for i in range(257)]
        r=compare_cycles(t,[1e3+.01*x+math.sin(2*math.pi*x) for x in t],1,2,1)
        self.assertAlmostEqual(r['relative_mean_drift'],.01)

    def test_actual_time_interpolation(self):
        t=[0,.13,.2,.7,1.01,1.3,1.8,2]
        r=compare_cycles(t,[3*x for x in t],1,2,3)
        self.assertAlmostEqual(r['relative_rms'],1)

    def test_reject_bad_histories(self):
        for t,v in [([0,1],[0,1]),([0,1,1,2],[0,0,0,0]),
                    ([0,1,2],[0,float('nan'),0]),([.01,1,2],[0,0,0])]:
            with self.assertRaises(ValueError):compare_cycles(t,v,1,2,1)

    def test_variable_step_volume_budget(self):
        times=[.1,.13,.4,1.];previous=0.;rows=[]
        for t in times:
            rows.append(dict(time=t,accepted_dt=t-previous,endpoint_inlet_flow=2*t,
                             endpoint_outlet_flow=0.,endpoint_volume=1+t*t));previous=t
        self.assertLess(volume_budget(rows)['max_absolute_defect'],1e-14)
        rows[1]['accepted_dt']=.1
        with self.assertRaisesRegex(ValueError,'Gap'):volume_budget(rows)

    def test_cubic_moving_volume_quadrature_order(self):
        errors=[]
        for n in (10,20,40):
            rows=[]
            for i in range(1,n+1):
                t=i/n
                volume=(1+t)*(1+2*t)*(1+3*t)/6
                rate=((1+2*t)*(1+3*t)+2*(1+t)*(1+3*t)+3*(1+t)*(1+2*t))/6
                rows.append(dict(time=t,accepted_dt=1/n,endpoint_inlet_flow=rate,endpoint_outlet_flow=0.,endpoint_volume=volume))
            errors.append(abs(volume_budget(rows,initial_volume=1/6,initial_net_flow=1.)['final_defect']))
        self.assertAlmostEqual(errors[0]/errors[1],4.,places=9)
        self.assertAlmostEqual(errors[1]/errors[2],4.,places=9)


if __name__=='__main__':unittest.main()
