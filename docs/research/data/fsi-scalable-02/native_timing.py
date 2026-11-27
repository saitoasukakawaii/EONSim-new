"""Relink a diagnostic copy of native svFSI with an outer-loop clock in MAIN.f."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for key in ('main','build','output'):
        cli.add_argument('--'+key,type=Path,required=True)
    args=cli.parse_args()
    folder=args.output.resolve(); folder.mkdir(parents=True,exist_ok=False)
    cwd=args.build.resolve()/'Source/svFSI'
    target=cwd/'CMakeFiles/svFSI.dir'
    flags=(target/'flags.make').read_text().splitlines()
    compiler=next(line.split()[-1] for line in flags if line.startswith('# compile Fortran with '))
    args_by_name={line.split(' =',1)[0]:line.split(' =',1)[1].strip() for line in flags if ' =' in line}
    text=args.main.read_text(); sha=hashlib.sha256(text.encode()).hexdigest()
    for old,new in [ ('      REAL(KIND=RKIND) timeP(3)', '      REAL(KIND=RKIND) timeP(3)\n      INTEGER(KIND=8) bench0, benchNow, benchRate'),
        ('      IF (cTS .LE. nITS) dt = dt/10._RKIND','      CALL SYSTEM_CLOCK(bench0,benchRate)\n      IF (cTS .LE. nITS) dt = dt/10._RKIND'),
        ('!     Exiting outer loop if l1', "      IF (cm%mas()) THEN\n         CALL SYSTEM_CLOCK(benchNow)\n         WRITE(*,'(A,I8,1X,F16.9)') 'svfsi_step_timing ',cTS,\n     2      DBLE(benchNow-bench0)/DBLE(benchRate)\n      END IF\n!     Exiting outer loop if l1")]:
        if text.count(old)!=1:raise ValueError('Unexpected MAIN.f structure at '+old)
        text=text.replace(old,new)
    src=folder/'MAIN.f'; src.write_text(text)
    obj=folder/'MAIN.f.o'; exe=folder/'svFSI'
    compile_cmd=[compiler]
    for key in ('Fortran_DEFINES','Fortran_INCLUDES','Fortran_FLAGS'):compile_cmd.extend(shlex.split(args_by_name[key]))
    compile_cmd.extend(['-c',str(src),'-o',str(obj)])
    link_cmd=shlex.split((target/'link.txt').read_text()); link_cmd[link_cmd.index('CMakeFiles/svFSI.dir/MAIN.f.o')]=str(obj)
    link_cmd[link_cmd.index('-o')+1]=str(exe)
    for command in (compile_cmd,link_cmd):subprocess.run(command,cwd=cwd,check=True)
    (folder/'build.json').write_text(json.dumps(dict(source_sha256=sha,commands=[compile_cmd,link_cmd],
        binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),source_binary_sha256=
        hashlib.sha256((args.build/'bin/svFSI').read_bytes()).hexdigest()),indent=2)+'\n')


if __name__=='__main__':main()
