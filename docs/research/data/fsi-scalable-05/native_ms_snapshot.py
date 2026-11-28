"""Capture the first/fourth native MS equations of job 467 without changing solver inputs."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from native_mesh import digest, history, run, save


DECLARATIONS = """
      INTEGER(KIND=IKIND), SAVE :: msCaptureCount=0
      INTEGER(KIND=IKIND) msFile, msFace, msA, msI, msD, msCode
      REAL(KIND=RKIND), ALLOCATABLE :: msMask(:,:)
      CHARACTER(LEN=80) msName
"""

BEFORE = """
         IF (lEq%phys.EQ.phys_mesh) msCaptureCount=msCaptureCount+1
         IF (lEq%phys.EQ.phys_mesh.AND.
     2      (msCaptureCount.EQ.1.OR.msCaptureCount.EQ.4)) THEN
            WRITE(msName,'("ms-",I1,"-",I3.3,".raw")')
     2         msCaptureCount, lhs%commu%task
            OPEN(NEWUNIT=msFile,FILE=msName,ACCESS='STREAM',
     2         FORM='UNFORMATTED',STATUS='NEW')
            ALLOCATE(msMask(dof,tnNo))
            msMask=1._RKIND
            DO msFace=1,lhs%nFaces
               IF (incL(msFace).EQ.0) CYCLE
               IF (lhs%face(msFace)%bGrp.NE.BC_TYPE_Dir) CYCLE
               msD=MIN(dof,lhs%face(msFace)%dof)
               DO msA=1,lhs%face(msFace)%nNo
                  msI=lhs%face(msFace)%glob(msA)
                  msMask(1:msD,msI)=msMask(1:msD,msI)*
     2               lhs%face(msFace)%val(1:msD,msA)
               END DO
            END DO
            WRITE(msFile) tnNo,gtnNo,lhs%nnz,lhs%mynNo,dof
            WRITE(msFile) ltg,lhs%map,rowPtr,colPtr
            WRITE(msFile) msMask(:,lhs%map),R,Val
            DEALLOCATE(msMask)
            CLOSE(msFile)
         END IF
"""

AFTER = """
         IF (lEq%phys.EQ.phys_mesh.AND.
     2      (msCaptureCount.EQ.1.OR.msCaptureCount.EQ.4)) THEN
            WRITE(msName,'("ms-",I1,"-",I3.3,".returned")')
     2         msCaptureCount, lhs%commu%task
            OPEN(NEWUNIT=msFile,FILE=msName,ACCESS='STREAM',
     2         FORM='UNFORMATTED',STATUS='NEW')
            WRITE(msFile) lEq%FSILS%RI%itr,lEq%FSILS%RI%iNorm,
     2         lEq%FSILS%RI%fNorm,R,Val
            CLOSE(msFile)
            IF (msCaptureCount.EQ.4) THEN
               CALL MPI_BARRIER(lhs%commu%comm,msCode)
               CALL MPI_FINALIZE(msCode)
               STOP
            END IF
         END IF
"""


def instrument(stage, source, binary):
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    original = source/'Code/Source/svFSI/LS.f'
    if revision!='7bdb74cdd517310d6bf32c0bb7d42072aeac8658' or digest(original)!=(
            'a899d50de4b0398a936c9e1ea20e886f37e4aaffafc8f782f034e4efb05910af'):
        raise ValueError('Unrecognized pinned native source')
    build = source/'build/svFSI-build/Source/svFSI'
    target = build/'CMakeFiles/svFSI.dir'
    flags = [tok for line in (target/'flags.make').read_text().splitlines() if line.startswith('Fortran_')
             for tok in shlex.split(line.split(' =',1)[1])]
    link = shlex.split((target/'link.txt').read_text())
    link[link.index('-o')+1] = str(stage/'svFSI-control')
    subprocess.run(link,cwd=build,check=True)
    if digest(stage/'svFSI-control')!=digest(binary):
        raise ValueError('Unmodified relink differs from job 467 executable')
    text = original.read_text()
    start = '      REAL(KIND=RKIND), INTENT(IN) :: res(nFacesLS)\n'
    call = ('         CALL FSILS_SOLVE(lhs, lEq%FSILS, dof, R, Val,\n'
            '     2      lEq%ls%PREC_Type, incL=incL, res=res)\n')
    if text.count(start)!=1 or text.count(call)!=1:
        raise ValueError('Unrecognized native solver entry')
    replacement = stage/'LS.f'
    replacement.write_text(text.replace(start,start+DECLARATIONS).replace(call,BEFORE+call+AFTER))
    compiler = '/opt/software/gcc-11.3.0/bin/gfortran'
    cmd = [compiler,*flags,'-c',str(replacement),'-o',str(stage/'LS.f.o')]
    subprocess.run(cmd,cwd=build,check=True)
    link[link.index('CMakeFiles/svFSI.dir/LS.f.o')] = str(stage/'LS.f.o')
    link[link.index('-o')+1] = str(stage/'svFSI-observe')
    subprocess.run(link,cwd=build,check=True)
    return dict(revision=revision,original_source=digest(original),observed_source=digest(replacement),
                compiler=digest(Path(compiler)),object=digest(stage/'LS.f.o'),command=cmd,
                original_relink=digest(stage/'svFSI-control'),observed_binary=digest(stage/'svFSI-observe'),
                link_description=digest(target/'link.txt'),compiler_flags=digest(target/'flags.make'))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('stage',type=Path)
    args = cli.parse_args()
    stage = args.stage.resolve()
    if len(os.sched_getaffinity(0))!=32 or not os.getenv('SLURM_JOB_ID'):
        cli.error('requires 32 Slurm cores')
    prior = Path.home()/'workspace/fsi-scalable-05-runs/native-MS-467'
    old = json.loads((prior/'native-mesh.json').read_text())
    stage.mkdir(parents=True,exist_ok=False)
    row = dict(job=os.environ['SLURM_JOB_ID'],control_job=467,scope='paired MS correction snapshots only',
               inputs=old['inputs'],limits=dict(seconds=360,rss_bytes=8*2**30))
    try:
        for name,sha in old['inputs'].items():
            if digest(prior/name)!=sha:
                raise ValueError('Changed native job 467 input '+name)
            shutil.copyfile(prior/name,stage/name)
        cmd=old['command'].copy()
        binary=Path(cmd[-2])
        if digest(binary)!=old['source_binary_sha256']:
            raise ValueError('Native baseline binary differs')
        row['build']=instrument(stage,Path.home()/'software/svFSI/svFSI',binary)
        cmd[-2]=str(stage/'svFSI-observe')
        os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        run(stage,cmd,row,360,8*2**30)
        row['native']=history(stage)
        captured = sorted([*stage.glob('ms-*.raw'),*stage.glob('ms-*.returned')])
        if len(captured)!=128 or row['native']['completed_rcr_steps']!=0:
            raise ValueError('Incomplete diagnostic capture or unexpected completed step')
        row['artifacts']={p.name:digest(p) for p in captured}
        from native_ms_system import compare
        row['systems']=compare(stage)
    finally:
        save(stage/'ms-snapshot.json',row)


if __name__=='__main__':
    main()
