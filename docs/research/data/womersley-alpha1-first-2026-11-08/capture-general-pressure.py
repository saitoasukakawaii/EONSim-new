"""Archive the completed General-input and startup analysis checks."""
import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-first-coupled.py'))
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
root=capture.root;work=capture.work
source=work/'reference-general-pressure-0b9e980'
assert all(v['passed'] for v in json.loads((source/'summary.json').read_text()).values())
checks=work/'pressure-startup-check-0b9e980'
receipt=dict(provenance='Actual Codex execution receipts, not reruns or raw subprocess logs',checks=[
    dict(command=['/usr/bin/python3','tests/test_svfsi_export.py'],passed=5,elapsed_seconds=.205,
        sha256={name:capture.sha(root/name) for name in ('scripts/export_svfsi_tube.py','tests/test_svfsi_export.py')}),
    dict(command=['/usr/bin/python3','tests/test_pressure_tube_audit.py'],passed=7,elapsed_seconds=.033,
        sha256={name:capture.sha(root/name) for name in ('scripts/audit_pressure_tube.py','tests/test_pressure_tube_audit.py')})])
(checks/'observed-unit-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
capture.capture('pressure-general-input-2026-11-08',[
    ('uniform-input',list(source.rglob('*'))),('startup-checks',list(checks.rglob('*')))],
    [source/'summary.json',root/'scripts/export_svfsi_tube.py',root/'scripts/analyze_svfsi_uniform_pressure.py',
     root/'scripts/audit_pressure_tube.py',root/'tests/test_svfsi_export.py',root/'tests/test_pressure_tube_audit.py',
     Path(__file__).with_name('compare-pressure-fields.py'),Path(__file__)])
study=work/'womersley-a1-s48-l0-n100';controller=work/'womersley-alpha1-0b9e980'
assert json.loads((study/'receipt.json').read_text())['step']==600
capture.capture('womersley-alpha1-first-2026-11-08',[
    ('numerical',list(study.rglob('*'))),
    ('analysis-and-controller',list((controller/'source').rglob('*'))+[controller/n for n in (
        'womersley-a1-s48-l0-n100-analysis.json','womersley-a1-s48-l0-n100-analysis-command.json',
        'womersley-a1-s48-l0-n100-analysis.log','womersley-a1-s48-l0-n100-command.json',
        'womersley-a1-s48-l0-n100.log','affinity-preflight.json','provenance.json','original-controller.py','mpiexec-cpus10-17')])],
    [controller/'womersley-a1-s48-l0-n100-analysis.json',Path(__file__)])
