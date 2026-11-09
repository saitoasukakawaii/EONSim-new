import hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
base=Path('/home/tfblab633/EONSim-prod48-20261107/reference')
base.mkdir(exist_ok=True)
source=base/'svFSI-7bdb74c'
revision='7bdb74cdd517310d6bf32c0bb7d42072aeac8658'
if not source.exists():
    data=subprocess.check_output(['git','-C','/home/tfblab633/svFSI-old','archive',revision])
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(source,filter='data')
    (base/'source.json').write_text(json.dumps(dict(repository='https://github.com/SimVascular/svFSI.git',
        commit=revision,archive_sha256=hashlib.sha256(data).hexdigest()),indent=2)+'\n')
env=os.environ.copy()
for key in ('LD_LIBRARY_PATH','LIBRARY_PATH','CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','CMAKE_PREFIX_PATH','CC','CXX','FC'):
    env.pop(key,None)
env['PATH']='/usr/bin:/bin'
commands=[['/usr/bin/cmake','-S',str(source/'Code'),'-B',str(base/'build'),'-DCMAKE_BUILD_TYPE=Release',
           '-DCMAKE_C_COMPILER=/usr/bin/gcc','-DCMAKE_CXX_COMPILER=/usr/bin/g++','-DCMAKE_Fortran_COMPILER=/usr/bin/gfortran',
           '-DCMAKE_Fortran_FLAGS=-fallow-argument-mismatch','-DSV_USE_TRILINOS=OFF','-DSV_USE_SYSTEM_ZLIB=ON'],
          ['/usr/bin/cmake','--build',str(base/'build'),'--parallel','2']]
(base/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
for name,command in zip(('configure','build'),commands):
    with (base/(name+'.log')).open('w') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    print(name,result.returncode,flush=True)
    if result.returncode:
        print('\n'.join((base/(name+'.log')).read_text().splitlines()[-35:]),flush=True)
        raise SystemExit(result.returncode)
