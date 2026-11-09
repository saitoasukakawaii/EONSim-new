import os,sys,time
from pathlib import Path
os.sched_setaffinity(0,{14})
p=Path("/sys/fs/cgroup")/Path("/proc/self/cgroup").read_text().strip().split("::",1)[1].lstrip("/")
deadline=time.monotonic()+5
while ((p/"memory.max").read_text().strip()!=str(2*1024**3) or (p/"memory.swap.max").read_text().strip()!="0") and time.monotonic()<deadline: time.sleep(.05)
assert int((p/"memory.max").read_text())==2*1024**3 and int((p/"memory.swap.max").read_text())==0
os.execv(sys.argv[1],sys.argv[1:])
