"""Inspect real inputs for the unlaunched extension; do not prepare a new run."""
import ast,hashlib,importlib.util,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[2]
path=root/'build/prod48-20261107/extend-length24-native6400.py'
ast.parse(path.read_text());spec=importlib.util.spec_from_file_location('extension',path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
before=mod.inspect();assert not before['ready'] and not any(before[k] for k in ('prepared','output_exists','execution_status_exists','adopted'))
original=mod.read(mod.D/mod.P.name/'case.json');proposed=mod.expected_case()
assert original['fsi']['steps']==6400 and proposed['fsi']['steps']==7200
restored=json.loads(json.dumps(proposed));restored['fsi']['steps']=6400;assert restored==original
assert proposed['fsi']['output_interval']==1 and proposed['fsi']['checkpoint_interval']==200
assert mod.numerical_command()==list(map(str,['/usr/bin/python3',mod.C/'execution-guard.py',mod.OUT/'eonsim','-case','case.json',
    '-checkpoint',mod.OUT/'checkpoint','-restart',mod.OUT/'checkpoint','-stop_after','7200','-solver_report',
    '-pc_factor_mat_solver_type','mumps','-snes_lag_jacobian','-2']))
assert mod.audit_command()==list(map(str,['/usr/bin/python3',mod.C/'execution-guard.py','/usr/bin/python3',mod.SOURCE/'scripts/audit_pressure_tube.py',
    '--case',mod.OUT/'case.json','--work',mod.OUT,'--first-step','6601','--output',mod.OUT/'eonsim-audit.json']))
rejected=False
try:mod.evidence()
except AssertionError as error:
    assert str(error)=='Complete numerical proof and separate raw review are both required';rejected=True
assert rejected
after=mod.inspect();assert before==after
record=dict(passed=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
    controller_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),only_physical_case_change={'fsi.steps':[6400,7200]},
    actual_inspection=after,incomplete_evidence_rejected=True,numerical_command=mod.numerical_command(),audit_command=mod.audit_command(),
    prepared=False,adopted=False,numerical_runs=0,scope='Real frozen input comparison and command checks only; no new directories/status, no numerical or completed restart proof.')
target=root/'build/prod48-20261107/length24-extension-static-check.json';assert not target.exists()
target.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
