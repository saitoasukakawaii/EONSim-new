import os
from pathlib import Path
import re
import subprocess
registered=[int(m.group(1)) for p in Path('/dev/shm').glob('__KMP_REGISTERED_LIB_*') if (m:=re.search(r'LIB_(\d+)_',p.name))]
limit=max(registered,default=0)
if limit>20000:raise RuntimeError('PID isolation bound exceeded')
print('Existing registered PID maximum',limit,flush=True)
for attempt in range(20001):
    p=subprocess.Popen(['/bin/true']);p.wait()
    if p.pid>limit:break
else:raise RuntimeError('PID isolation failed')
os.environ.update(OMPI_ALLOW_RUN_AS_ROOT='1',OMPI_ALLOW_RUN_AS_ROOT_CONFIRM='1')
os.execvp('bash',['bash','scripts/cloud/run.sh','3.23.7','debug','explicit','/workspace/scratch/eonsim-cloud','build/tube-only.json'])
