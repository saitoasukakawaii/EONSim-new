"""Archive the completed fixed-time study and manufactured window checks."""
import hashlib,importlib.util,json
from pathlib import Path
source=Path(__file__).with_name('capture-first-coupled.py')
spec=importlib.util.spec_from_file_location('capture',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
work=module.work;root=module.root
failed=work/'pressure-window-subset-2eabb47'
(failed/'failure.json').write_text(json.dumps(dict(error="KeyError: '3'",
    location='compare-pressure-audits.py:validate cycle_differences[str(cycle)]',
    cause='The manufacturing harness passed an in-memory dict with integer cycle keys instead of its serialized JSON report. Fixed only the harness; no PDE execution or gate change.',
    source_sha256=module.sha(failed/'original-failed-check.py')),indent=2)+'\n')
receipt=work/'pressure-window-subset-2eabb47-attempt2/observed-export-test.json'
receipt.write_text(json.dumps(dict(command=['python','tests/test_svfsi_export.py'],cwd=str(root),
    result='4 tests passed',elapsed_seconds=.388,
    provenance='Recorded from the actual Codex exec result at2026-11-07T18:01Z; this is a receipt, not a rerun or raw subprocess log',
    files={name:module.sha(root/name) for name in ('scripts/export_svfsi_tube.py','tests/test_svfsi_export.py')}),indent=2)+'\n')
fixed=work/'womersley-a2-s48-l0-n200-fixed-time-n100'
assert json.loads((fixed/'receipt.json').read_text())['step']==1000
fine=work/'womersley-a2-s48-l2-n200-chord-m200'
controller=work/'womersley-continuation-2eabb47'
module.capture('womersley-fixed-time-2026-11-08',[
    ('numerical',list(fixed.rglob('*'))),
    ('analysis',list((work/'womersley-fixed-time-analysis-2eabb47').rglob('*'))),
    ('continuation',[fine/n for n in ('definition.json','checkpoint-source.json','execution-probe.json','original-fork.py')]+
        [controller/n for n in ('original-controller.py','selection.json','coarse-tau-time-command.json',
         'coarse-tau-time.log','fork-fine-command.json','fork-fine.log')])],
    [work/'womersley-fixed-time-analysis-2eabb47/summary.json',Path(__file__),source])
module.capture('pressure-tube-window-2026-11-08',[
    (name,list((work/name).rglob('*'))) for name in (
        'pressure-window-check-2eabb47','pressure-window-subset-2eabb47','pressure-window-subset-2eabb47-attempt2')],
    [root/'scripts/audit_pressure_tube.py',root/'scripts/export_svfsi_tube.py',root/'tests/test_svfsi_export.py',
     work/'resource-observation-2eabb47.json',Path(__file__).with_name('continue-elastic-window.py'),Path(__file__),source])
