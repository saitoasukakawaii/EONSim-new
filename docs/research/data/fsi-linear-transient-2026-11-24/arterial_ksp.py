"""Run dimensioned elastic-tube KSP comparisons with true residuals on every correction."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


PROFILE_MODES=('cgs-never','cgs-ifneeded','cgs-always','mgs-profile')


def options(mode):
    if mode in PROFILE_MODES:
        flags=options('inner')
        if mode=='mgs-profile':
            flags.append('-ksp_gmres_modifiedgramschmidt')
        else:
            refinement=mode.split('-',1)[1]
            flags.extend(['-ksp_gmres_classicalgramschmidt','-ksp_gmres_cgs_refinement_type','refine_'+refinement])
        return [*flags,'-options_left','-log_view',':events.csv:ascii_csv']
    if mode=='preset':
        return ['-options_file','arterial-fieldsplit.opts']
    if mode=='direct':
        return []
    if mode=='default':
        return ['-pc_recipe','physics']
    outer=['-ksp_pc_side','right','-ksp_norm_type','unpreconditioned','-ksp_rtol','1e-10',
           '-ksp_atol','1e-23','-ksp_max_it','3000','-ksp_gmres_restart','100']
    if mode=='inner-tight':
        outer[outer.index('-ksp_rtol')+1]='1e-11'
        outer[outer.index('-ksp_atol')+1]='1e-24'
    if mode=='inner-mgs':
        outer+=['-ksp_gmres_modifiedgramschmidt']
    if mode=='asm':
        return outer+['-ksp_type','fgmres','-pc_type','asm','-pc_asm_overlap','1','-sub_ksp_type','preonly',
                      '-sub_pc_type','ilu','-sub_pc_factor_levels','2']
    outer+=['-pc_recipe','physics']
    if mode=='strict-short':
        return outer+['-ksp_max_it','500','-ksp_gmres_restart','30']
    if mode=='long':
        return outer
    if mode in ('inner','inner-tight','inner-mgs'):
        for prefix,limit in [('fieldsplit_fluid_fieldsplit_velocity',10),('fieldsplit_solid',12)]:
            outer+=['-'+prefix+'_ksp_type','gmres','-'+prefix+'_ksp_rtol','1e-4','-'+prefix+'_ksp_max_it',str(limit)]
    elif mode=='block-lu':
        for prefix in ('fluid_fieldsplit_velocity','fluid_fieldsplit_pressure','solid','mesh'):
            outer+=['-fieldsplit_'+prefix+'_pc_type','lu','-fieldsplit_'+prefix+'_pc_factor_mat_solver_type','mumps']
    return outer


@contextmanager
def exclusive(path):
    with path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        yield


def save_receipt(path,data):
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n')
    temporary.replace(path)


def prepare_partition(work,case,executable,ranks,env,metadata):
    part=work/f'parts-{ranks}'
    ready=work/f'prepare-{ranks}.json'
    with exclusive(work/f'prepare-{ranks}.lock'):
        if not ready.is_file():
            command=[executable,'-case',case/'case.json','-prepare',part,'-parts',str(ranks)]
            with (work/f'prepare-{ranks}.log').open('w') as stream:
                subprocess.run(command,cwd=work,env=env,stdout=stream,stderr=stream,check=True)
            save_receipt(ready,metadata)
        if json.loads(ready.read_text())!=metadata:
            raise ValueError('Existing partition was generated with other inputs')
    return part


def run_trajectory(target,case,part,executable,mpiexec,mode,env,metadata):
    target.mkdir(exist_ok=True)
    receipt=target/'run.json'
    flags=options(mode)
    signature=dict(**metadata,mode=mode,flags=flags)
    preset=Path(__file__).with_name('arterial-fieldsplit.opts')
    if mode=='preset':
        signature['options_file_sha256']=digest(preset)
    with exclusive(target/'run.lock'):
        if receipt.exists():
            old=json.loads(receipt.read_text())
            if any(old.get(k)!=v for k,v in signature.items()):
                raise ValueError('Changed input on resume')
            return
        if mode=='preset':
            shutil.copyfile(preset,target/preset.name)
        command=[mpiexec,'--map-by','core','--bind-to','core','--report-bindings','-n',str(metadata['ranks']),
                 executable,'-case',case/'case.json','-partition',part,'-output',target/'tube.vtu',
                 '-solver_report','-linear_report',*flags]
        start=time.monotonic()
        with (target/'solve.log').open('w') as stream:
            proc=subprocess.run(command,cwd=target,env=env,stdout=stream,stderr=stream)
        signature.update(exit_code=proc.returncode,seconds=time.monotonic()-start,log_sha256=digest(target/'solve.log'),
                         mpi_runtime={k:env[k] for k in ('OMPI_MCA_pml','OMPI_MCA_btl','OMPI_MCA_smsc','OMPI_MCA_mpi_yield_when_idle') if k in env},
                         launcher_sha256=digest(mpiexec))
        if mode in PROFILE_MODES and (target/'events.csv').is_file():
            signature['profile_sha256']=digest(target/'events.csv')
        save_receipt(receipt,signature)
        print(target.name,signature['exit_code'],round(signature['seconds'],2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for opt in ('work','case','executable','mpiexec'):
        p.add_argument('--'+opt,type=Path,required=True)
    p.add_argument('--ranks',nargs='+',type=int,default=[1,2,4])
    p.add_argument('--modes',nargs='+',choices=['direct','default','strict-short','long','inner','inner-tight','inner-mgs','asm','block-lu','preset',*PROFILE_MODES],
                   default=['direct','strict-short','inner','asm','block-lu'])
    a=p.parse_args()
    c=a.case.resolve()
    w=a.work.resolve()
    w.mkdir(exist_ok=True,parents=True)
    f=json.loads((c/'case.json').read_text())
    expected={'pressure':80.,'dt':1/32,'steps':32,'young':400000.,'poisson':.45,
              'density':1060.,'solid_density':1100.,'viscosity':.004,'output_interval':4,'stabilization_model':'volume'}
    if (any(f['fsi'].get(k)!=v for k,v in expected.items()) or
            f['time']!={'scheme':'generalized_alpha','rho_infinity':.5} or min(a.ranks)<1):
        raise ValueError('The measured benchmark requires the same 32-step dimensional input')
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OMPI_MCA_pml='ob1',OMPI_MCA_btl='self,sm,tcp')
    env.setdefault('OMPI_MCA_mpi_yield_when_idle','0')
    exe=a.executable.resolve()
    hashes={name:digest(c/name) for name in ('case.json','fluid.msh','solid.msh')}
    binary=digest(exe)
    for ranks in a.ranks:
        metadata=dict(inputs=hashes,executable=binary,ranks=ranks)
        part=prepare_partition(w,c,exe,ranks,env,metadata)
        for mode in a.modes:
            run_trajectory(w/f'r{ranks}-{mode}',c,part,exe,a.mpiexec.resolve(),mode,env,metadata)


if __name__=='__main__':
    main()
