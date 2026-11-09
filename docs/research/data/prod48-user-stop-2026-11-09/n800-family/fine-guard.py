import os,sys,time
from pathlib import Path
os.sched_setaffinity(0,{22})
g=Path("/sys/fs/cgroup")/Path("/proc/self/cgroup").read_text().strip().split("::",1)[1].lstrip("/")
end=time.monotonic()+5
while (g/"memory.max").read_text().strip()=="max" and time.monotonic()<end:time.sleep(.05)
assert int((g/"memory.max").read_text())==2*1024**3 and int((g/"memory.swap.max").read_text())==0
os.execv(sys.argv[1],sys.argv[1:])
