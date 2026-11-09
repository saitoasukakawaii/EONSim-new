"""Exercise new orchestration guards without running or preparing numerics."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

folder = Path(__file__).resolve().parent
controller = folder/'run-alpha1-s96-fine-family.py'
preparer = folder/'prepare-alpha1-s96-fine-family.py'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('execution',controller)
execution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(execution)
assert sha(preparer) == execution.PREPARER
text = preparer.read_text()
start = text.index("source=out/'source';commands={}")
end = text.index("dump(out/'commands.json'",start)
command_source = text[start:end]
ast.parse(command_source)
results = []


def rejected(label, function):
    try:
        function()
    except AssertionError:
        results.append(dict(label=label,rejected=True))
    else:
        raise AssertionError('Accepted invalid orchestration: '+label)


for selected, ranks in [('native32',1),('four32',4)]:
    plan = dict(prepared=True,adopted=False,selected=selected,ranks=ranks,
        cpus=[0] if ranks == 1 else list(range(8)),coarse=str(execution.COARSE),
        fine=str(execution.D/('womersley-a1-s96-r8-a8-l1-n400-'+selected+'-b0fd881')),
        time_control=str(execution.D/('womersley-a1-s96-r8-a8-l1-n800-'+selected+'-b0fd881')),
        steps_per_cycle=[400,400,800],phases=[400,400,800],cycles=6,warmup=2,window=32,
        memory_max_bytes=6*execution.GIB,swap_max_bytes=0,admission_bytes=22*execution.GIB,
        global_floor_bytes=8*execution.GIB,
        required_locks=['womersley-direct-memory.lock','mpi-queue.lock'],
        independent_run_review_required=True,numerical_kernel_byte_identical=True,
        coarse_flow_amplitude_failed=True)
    execution.check_configuration(plan)
    namespace = dict(out=execution.C,fine=Path(plan['fine']),time_control=Path(plan['time_control']),
                     coarse=execution.COARSE,ranks=ranks,wrapper=execution.C/'mpiexec-fixed',sys=sys)
    exec(compile(command_source,str(preparer),'exec'),namespace)
    commands = {name:list(map(str,command)) for name,command in namespace['commands'].items()}
    execution.check_commands(plan,commands)
    results.append(dict(label=selected+'-actual-preparer-commands',passed=True))
    for field, value in [('cycles',5),('cpus',[21]),('memory_max_bytes',14*execution.GIB),
                         ('swap_max_bytes',execution.GIB),('global_floor_bytes',0),
                         ('required_locks',['mpi-queue.lock','womersley-direct-memory.lock']),
                         ('coarse_flow_amplitude_failed',False)]:
        changed = copy.deepcopy(plan)
        changed[field] = value
        rejected(selected+'-'+field,lambda p=changed: execution.check_configuration(p))
    changed = copy.deepcopy(commands)
    i = changed['fine-n400'].index('--alpha')
    changed['fine-n400'][i+1] = '2'
    rejected(selected+'-changed-alpha',lambda: execution.check_commands(plan,changed))
    changed = copy.deepcopy(commands)
    i = changed['fine-n800'].index('--cycles-per-solve')
    del changed['fine-n800'][i:i+2]
    rejected(selected+'-missing-cycle-segmentation',lambda: execution.check_commands(plan,changed))
    changed = dict(reversed(list(commands.items())))
    rejected(selected+'-changed-job-order',lambda: execution.check_commands(plan,changed))

before = {str(path):path.exists() for path in (execution.C,execution.STATUS)}
result = subprocess.run([sys.executable,controller,'inspect'],capture_output=True,text=True,check=True)
state = json.loads(result.stdout)
assert not state['ready'] and not state['adopted'] and state['pending']
after = {str(path):path.exists() for path in (execution.C,execution.STATUS)}
assert before == after and not any(after.values())
output = folder/'alpha1-s96-execution-controller-checks.json'
record = dict(passed=True,controller_sha256=sha(controller),preparer_sha256=sha(preparer),
    copied_command_fragment_sha256=hashlib.sha256(command_source.encode()).hexdigest(),
    checks=results,actual_readonly_inspection=state,paths_before=before,paths_after=after,
    numerical_runs=0,prepared=False,adopted=False,
    scope='Static orchestration and rejection fixtures only. The actual pending screen/review prevents preparation and execution. No performance, field, budget, or physical qualification evidence.')
output.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(passed=True,checks=len(results),prepared=False,adopted=False,report=str(output))))
