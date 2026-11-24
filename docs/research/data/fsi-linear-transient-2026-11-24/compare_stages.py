"""Check both Radau stage factorizations on the same singular fluid-wall mass matrix."""
import argparse
import json
from pathlib import Path
import numpy as np
from axisymmetric import MeridianTube, TubeParameters
from reference import A, integrate, radau_stage_solver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    cases=[]
    for full in (False,True):
        tube=MeridianTube(8,7,3,5,TubeParameters(),2,full,17)
        rng=np.random.default_rng(4321)
        physical_rhs=rng.normal(size=(2,tube.size))
        for h in (.05,.005):
            # A known state gives a consistent RHS including algebraic pressure rows.
            rhs=(tube.mass@physical_rhs.T).T+h*(A@(tube.operator@physical_rhs.T).T)
            stages=[radau_stage_solver(tube.mass,tube.operator,h,method)(rhs)
                    for method in ('real-block','complex-pair')]
            differences=[float(np.max(np.abs(s-physical_rhs))) for s in stages]
            mutual=float(np.max(np.abs(stages[0]-stages[1])))
            if max(differences+[mutual])>2e-8:raise ValueError('Inconsistent coupled stage fields')
            cases.append(dict(full_length=full,dt=h,unknowns=tube.size,
                              max_real_field_error=differences[0],max_complex_field_error=differences[1],max_stage_difference=mutual))
        for method in ('real-block','complex-pair'):
            error=integrate(tube,8,.02,manufactured=True,stage_solver=method)
            cases.append(dict(full_length=full,method=method,manufactured_quadratic_error=error))
    args.output.write_text(json.dumps(cases,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
