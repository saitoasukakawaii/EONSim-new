"""Opt-in element timing must preserve fields and report each rank/time step."""
import argparse
import math
from pathlib import Path
import re
import subprocess
from verify_schur import fields, ROOT


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',required=True)
    p.add_argument('--mpiexec',required=True)
    p.add_argument('--work',type=Path,required=True)
    a=p.parse_args(); a.work.mkdir(parents=True,exist_ok=True)
    def run(cmd, label):
        result=subprocess.run(list(map(str,cmd)),text=True,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,timeout=60)
        (a.work/(label+'.log')).write_text(result.stdout)
        require(result.returncode==0,result.stdout)
        return result.stdout
    for name,steps in [('steady',1),('transient',10),('rotated_channel',1)]:
        case=ROOT/'cases/fluid'/f'{name}.yaml'
        serial=None
        for ranks in (1,2):
            stem=f'{name}-r{ranks}'; part=a.work/(stem+'-part')
            run([a.executable,'-case',case,'-prepare',part,'-parts',ranks],stem+'-prepare')
            base=[a.mpiexec,'-n',ranks,a.executable,'-case',case,'-partition',part]
            outputs=[]
            for enabled in (False,True):
                label=stem+('-on' if enabled else '-off');out=a.work/(label+'.vtu')
                text=run(base+['-output',out]+(['-fluid_element_report'] if enabled else []),label)
                output=fields(out,ranks);outputs.append(output)
                require(bool(output),'Missing physical output')
                require(all(math.isfinite(v) for values in output.values() for v in values),'Nonfinite output')
                reports=[dict(re.findall(r'(\w+)=([^\s]+)',line)) for line in text.splitlines()
                         if line.startswith('fluid_element_report ')]
                if not enabled:
                    require(not reports,'Opt-out emitted element reports')
                    continue
                expected={(rank,step) for rank in range(ranks) for step in range(1,steps+1)}
                require(len(reports)==len(expected) and
                        {(int(r['rank']),int(r['step'])) for r in reports}==expected,'Missing/duplicate reports')
                for r in reports:
                    cells=int(r['local_cells']);res=int(r['residual_elements']);jac=int(r['jacobian_elements'])
                    require(cells>0 and res>0 and jac>0,'Expected residual and Jacobian evaluations')
                    require(res%cells==0 and jac%cells==0,'Incomplete cell traversal')
                    for key in ('kernel_seconds','insert_seconds'):
                        require(math.isfinite(float(r[key])) and float(r[key])>=0,'Invalid timer')
            x,y=outputs
            require(x.keys()==y.keys(),'On/off node sets differ')
            require(all(len(x[node])==len(y[node]) and
                        all(abs(v-w)<1e-12 for v,w in zip(x[node],y[node])) for node in x),
                    'Timing changed velocity/pressure/reaction output')
            if serial is None:serial=x
            require(serial.keys()==x.keys(),'Rank node sets differ')
            require(all(len(serial[node])==len(x[node]) and
                        all(abs(v-w)<2e-8 for v,w in zip(serial[node],x[node])) for node in x),
                    'Rank output mismatch')
            print(name,ranks,'on/off fields, counts and timers passed',flush=True)


if __name__=='__main__':main()
