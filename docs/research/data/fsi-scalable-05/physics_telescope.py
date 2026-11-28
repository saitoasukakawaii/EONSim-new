"""B32 GAMG coarse solves on the single rank owning their operators."""
import math
from tube_protocol import records


EXPERIMENT='single-rank-v1'
# These are the four actual field-PC prefixes and measured B20 coarse sizes.
COARSE_FIELDS={
    'fieldsplit_fluid_fieldsplit_velocity_mg_coarse_':42,
    'fieldsplit_fluid_fieldsplit_pressure_mg_coarse_':12,
    'fieldsplit_solid_mg_coarse_':39,
    'fieldsplit_mesh_mg_coarse_':10,
}


def solver_flags(ranks):
    flags=[]
    for prefix in COARSE_FIELDS:
        options={'ksp_type':'preonly','ksp_norm_type':'none','pc_type':'telescope',
                 'pc_telescope_reduction_factor':str(ranks),'pc_telescope_ignore_dm':'true',
                 'telescope_ksp_type':'gmres','telescope_pc_type':'jacobi',
                 'telescope_ksp_rtol':'1e-10','telescope_ksp_max_it':'200',
                 'telescope_ksp_norm_type':'unpreconditioned'}
        for key,value in options.items():
            flags.extend(['-'+prefix+key,value])
    return flags


def coarse_receipt(log,ranks,steps,wrapped):
    """Verify all owner ranges and every reported last coarse solve on each step."""
    nodes=records(log.splitlines(),'solver_node ')
    result={}
    for prefix,expected_rows in COARSE_FIELDS.items():
        parent=[n for n in nodes if n['prefix']==prefix]
        owner=[n for n in parent if int(n['rank'])==0]
        rank_counts=[0]*ranks
        for n in parent:
            rank=int(n['rank'])
            expected_type=('preonly','telescope') if wrapped else ('gmres','jacobi')
            if (not 0<=rank<ranks or int(n['comm_size'])!=ranks or
                    (n['ksp'],n['pc'])!=expected_type or int(n['ksp_reason'])<=0 or int(n['pc_reason'])!=0 or
                    int(n['operator_rows'])!=expected_rows or
                    int(n['operator_local_rows'])!=(expected_rows if rank==0 else 0)):
                raise ValueError('Field coarse solver/ownership differs from B32 declaration: '+prefix)
            rank_counts[rank]+=1
        if rank_counts!=[steps]*ranks:
            raise ValueError('Missing coarse parent per rank and accepted step: '+prefix)
        solvers=[n for n in nodes if n['prefix']==prefix+'telescope_'] if wrapped else owner
        if len(solvers)!=steps:
            raise ValueError('Missing effective coarse Krylov solve: '+prefix)
        for n in solvers:
            if (int(n['rank'])!=0 or int(n['comm_size'])!=(1 if wrapped else ranks) or
                    (n['ksp'],n['pc'])!=('gmres','jacobi') or int(n['norm_type'])!=2 or
                    int(n['operator_local_rows'])!=expected_rows or int(n['operator_rows'])!=expected_rows or
                    int(n['pc_reason'])!=0 or int(n['ksp_reason'])<=0 or
                    not 0<=int(n['last_iterations'])<=200 or not math.isfinite(float(n['reported_norm']))):
                raise ValueError('Actual coarse GMRES/Jacobi differs from the qualified solver: '+prefix)
        result[prefix]=dict(rows=expected_rows,owner=0,krylov_communicator=int(solvers[0]['comm_size']),
            last_iterations=[int(n['last_iterations']) for n in solvers],
            last_reported_norms=[float(n['reported_norm']) for n in solvers],
            last_ksp_reasons=[int(n['ksp_reason']) for n in solvers])
    return result
