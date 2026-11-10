from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).resolve().parent;r=b.parents[1];old=r/'docs/research/data/prod48-user-stop-2026-11-09/n800-family/source/build/prod48-20261107/s24-n800-budget-kernel.py';new=b/'elastic-refined-budget-kernel.py'
s=new.read_text();s=s.replace('def analyze(solver,plan,receipts,target_n=800):\n    assert target_n in (800,1600)','def analyze(solver,plan,receipts):').replace('left.n==fine.n==target_n and temporal.n==target_n//2','left.n==fine.n==800 and temporal.n==400').replace('dense_phases=fine.n,reconstruction_phases=fine.n//2','dense_phases=800,reconstruction_phases=400').replace("scope=f'Independent S24 level1/N{target_n} numerical error budget;","scope='Independent S24 level1/N800 numerical error budget;").replace("method=f'Linear reconstruction of actual every-other states, with the real cycle31 endpoint; norms on actual{fine.n} dense states'","method='Linear reconstruction of actual every-other states, with the real cycle31 endpoint; norms on actual800 dense states'")
assert s==old.read_text(),'Unexpected numerical/gate change beyond explicit target indexing/report strings'
# Recompute decisions from the original actual reports, preserving the failed result.
w=b/'elastic-n800-budgets/eonsim';reports={k:json.loads((w/(k+'.json')).read_text()) for k in ['space','time','tail','sampling']};budget=json.loads((w/'budget.json').read_text());decisions={}
for key,v in budget['field_budgets'].items():
 denominator=reports['space']['relative_rms'][key];assert denominator==v['space_relative_rms']
 decisions[key]={}
 for term in ['time','tail','sampling']:
  numerator=reports[term]['relative_rms'][key];passed=denominator>0 and numerator<.1*denominator;assert passed==v['terms'][term]['passed'];decisions[key][term]=passed
assert budget['passed'] is False and not all(all(v.values()) for v in decisions.values())
output=b/'elastic-n1600-budgets';assert not output.exists()
cmd=['python3',str(b/'analyze-elastic-n1600-budget.py'),'--solver','eonsim','--output',str(output)];p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode!=0 and 'Incomplete coarse' in p.stderr and not output.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(passed=True,original_kernel_sha256=sha(old),generalized_kernel_sha256=sha(new),index_and_report_changes_only=True,original_failed_budget_decisions_recomputed=decisions,incomplete_command=cmd,incomplete_exit_code=p.returncode,incomplete_stderr=p.stderr,no_output_created=True,scope='Source-equivalence check outside target indices/report labels and replay of original actual budget decisions; not a new N1600 numerical result or rerun of original fields.')
(b/'elastic-refined-budget-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['incomplete_stderr','incomplete_command']}))
