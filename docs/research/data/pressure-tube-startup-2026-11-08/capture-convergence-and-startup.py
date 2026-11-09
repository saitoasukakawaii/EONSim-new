"""Capture completed reference convergence checks and startup attempts."""
import importlib.util,json,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('capture',Path(__file__).with_name('capture-first-coupled.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);root=c.root;work=c.work
observed=work/'reference-log-integration-c49c69c-attempt2/observed-unit-checks.json'
checks=[('tests/test_svfsi_export.py',6,.297),('tests/test_svfsi_convergence.py',4,.035),
    ('tests/test_pressure_tube_audit.py',7,.041),('tests/test_ci_selection.py',26,.423)]
observed.write_text(json.dumps(dict(provenance='Actual Codex tool execution receipts, not reruns or raw subprocess logs',
    checks=[dict(command=['/usr/bin/python3',name],passed=n,elapsed_seconds=t,source_sha256=c.sha(root/name)) for name,n,t in checks]),indent=2)+'\n')
names=['reference-tight-linear-c49c69c','reference-tight-linear-c49c69c-attempt2',
    'reference-tight-linear-n200-c49c69c','reference-log-audit-c49c69c',
    'reference-log-integration-c49c69c','reference-log-integration-c49c69c-attempt2']
c.capture('svfsi-convergence-2026-11-08',[(name,list((work/name).rglob('*'))) for name in names],
    [root/'scripts/audit_svfsi_convergence.py',root/'scripts/audit_pressure_tube.py',root/'scripts/export_svfsi_tube.py',
     root/'tests/test_svfsi_convergence.py',root/'tests/test_svfsi_export.py',
     root/'tests/test_pressure_tube_audit.py',root/'scripts/cloud/selection.json',
     Path(__file__).with_name('compare-pressure-audits.py'),Path(__file__)])
while json.loads((work/'elastic-reaudit-convergence-current.json').read_text())['state']!='completed':time.sleep(2)
names=['elastic-s12-l0-n100-c132-window','elastic-s12-l0-n100-ramp2-c12',
    'elastic-s12-l0-n100-ramp16-c32','elastic-convergence-reaudit-c49c69c']
c.capture('pressure-tube-startup-2026-11-08',[(name,list((work/name).rglob('*'))) for name in names],
    [work/'elastic-convergence-reaudit-c49c69c/startup-summary.json',Path(__file__).with_name('run-pressure-n200.py'),Path(__file__)])
