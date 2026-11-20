"""Boundary flux, ALE volume and bore-area history from coupled pressure-step VTUs."""
import argparse
import json
from pathlib import Path

import study_hydrostatic_fsi as fsi
import study_lame_wall as wall
import study_rigid_tube as tube


def boundary_neighbors(cells,faces):
    opposite={}
    boundary={tuple(sorted(face)) for _,face in faces}
    for tet in cells:
        for i,node in enumerate(tet):
            face=tuple(sorted(tet[:i]+tet[i+1:]))
            if face in boundary:
                if face in opposite: raise ValueError('Duplicate fluid boundary adjacency')
                opposite[face]=node
    if opposite.keys()!=boundary:
        raise ValueError('Missing fluid boundary adjacency')
    return opposite


def boundary_fluxes(xyz,faces,opposite,state):
    flux={tag:0. for tag,_ in faces}
    for tag,face in faces:
        a,b,c=(xyz[n] for n in face)
        av=tube.cross(tube.sub(b,a),tube.sub(c,a))
        inward=tube.sub(xyz[opposite[tuple(sorted(face))]],a)
        sign=-1 if sum(x*y for x,y in zip(av,inward))>0 else 1
        flux[tag]+=sign*sum(av[j]*sum(state[n].velocity[j] for n in face)/3 for j in range(3))/2
    return flux


def audit(directory, ranks=1):
    result=fsi.analyze(directory,ranks)
    mesh=tube.read_mesh(directory/'fluid.msh')
    nodes,cells,faces=mesh
    opposite=boundary_neighbors(cells,faces)
    previous_volume=initial_volume=sum(tube.determinant(nodes,t)/6 for t in cells)
    previous_d={n:(0.,0.,0.) for n in nodes}
    dt=result['dt']
    end_outflow_integral=0.
    wall_ids={n for tag,face in faces if tag==3 for n in face}
    xlevels=sorted({nodes[n][0] for n in wall_ids})
    mid=xlevels[len(xlevels)//2]
    midring=[n for n in wall_ids if nodes[n][0]==mid]
    rows=[]
    for step in range(1,result['steps']+1):
        state=fsi.recovered_state(directory,f'tube_step{step}',mesh,False,ranks)
        displacement={n:v.displacement for n,v in state.items()}
        xyz={n:tuple(a+b for a,b in zip(p,displacement[n])) for n,p in nodes.items()}
        volumes=[tube.determinant(xyz,t)/6 for t in cells]
        if min(volumes)<=0: raise ValueError('Nonpositive deformed volume')
        volume=sum(volumes)
        flux=boundary_fluxes(xyz,faces,opposite,state)
        qends=flux[1]+flux[2]
        qsym=flux[5]+flux[6]
        rate=(volume-previous_volume)/dt
        end_outflow_integral+=dt*qends
        kinematic=max(abs(state[n].velocity[j]-(displacement[n][j]-previous_d[n][j])/dt)
                      for n in wall_ids for j in range(3))
        section=wall.bore_section(nodes,displacement,midring)
        rows.append(dict(step=step,time=step*dt,volume=volume,volume_secant_rate=rate,
                         ends_outward_flow=qends,moving_wall_outward_flow=flux[3],symmetry_flow=qsym,
                         euler_net_outward_flow=qends+flux[3]+qsym,ale_mass_rate=rate+qends+qsym,
                         kinematic_wall_velocity_difference=kinematic,midplane_x=mid,
                         midplane_linear_area_strain=section['linear_area_strain']))
        previous_volume,previous_d=volume,displacement
    volume_gain=previous_volume-initial_volume
    if volume_gain<=0: raise ValueError('Expected a positive final bore volume gain')
    return dict(dt=dt,steps=len(rows),initial_volume=initial_volume,final_volume=previous_volume,
                volume_gain=volume_gain,integrated_end_inflow=-end_outflow_integral,
                cumulative_end_balance_over_gain=(volume_gain+end_outflow_integral)/volume_gain,
                max_abs_euler_flux=max(abs(r['euler_net_outward_flow']) for r in rows),
                max_abs_ale_mass_rate=max(abs(r['ale_mass_rate']) for r in rows),
                max_abs_symmetry_flow=max(abs(r['symmetry_flow']) for r in rows),
                max_wall_kinematic_difference=max(r['kinematic_wall_velocity_difference'] for r in rows),
                history=rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--ranks',type=int,default=1)
    a=p.parse_args()
    print(json.dumps(audit(a.work,a.ranks),indent=2,allow_nan=False))


if __name__=='__main__':
    main()
