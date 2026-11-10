from pathlib import Path
import sys,json,subprocess,os,hashlib
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tests'))
from verify_fsi_lu_reuse import frames,compare
b=root/'build/recompute-20261109';summary=json.loads((b/'fsi-tau-debug-check.log').read_text());source=Path(summary['work']);w=b/'fsi-tau-debug-old-checkpoint';assert not w.exists();w.mkdir();cp=w/'checkpoint';cfg=json.loads((source/'new-default-generalized_alpha/case.json').read_text());commands=[]
for label,exe,extra in [('old-partial',root/'build/macos-release/eonsim',['-checkpoint',str(cp),'-stop_after','4']),('new-resumed',root/'build/macos-debug/eonsim',['-restart',str(cp)])]:
 d=w/label;d.mkdir();cfg['output']=str(d/'solution.vtu');p=d/'case.json';p.write_text(json.dumps(cfg,indent=2)+'\n');cmd=[str(exe),'-case',str(p),'-pc_factor_mat_solver_type','mumps',*extra];commands.append(cmd)
 result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120);(d/'solve.log').write_text(result.stdout);assert result.returncode==0 and 'status=success' in result.stdout
actual=frames(w/'new-resumed');expected={k:v for k,v in frames(source/'new-default-generalized_alpha').items() if k in actual};error=compare(expected,actual);assert error<2e-12
report=dict(passed=True,default_old_checkpoint_replay_difference=error,commands=commands,binary_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['build/macos-release/eonsim','build/macos-debug/eonsim']});(w/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
