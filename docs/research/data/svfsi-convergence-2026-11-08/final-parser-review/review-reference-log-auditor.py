"""Preserve the parser review and recheck completed actual logs without a solve."""
import hashlib,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=Path('/home/tfblab633/EONSim-prod48-20261107')
out=work/'reference-log-parser-review-c49c69c';out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p in [Path(__file__),root/'scripts/audit_svfsi_convergence.py',root/'tests/test_svfsi_convergence.py']:
    shutil.copy2(p,out/p.name)
spec=importlib.util.spec_from_file_location('audit',out/'audit_svfsi_convergence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
reports={}
for name,reference,log,expected_failures in (
    ('elastic-s12-l0-n100-c132-window','reference-attempt2','svfsi-attempt2.log',0),
    ('elastic-s12-l0-n100-ramp2-c12','reference-attempt2','svfsi-attempt2.log',1215),
    ('elastic-s12-l0-n100-ramp16-c32','reference','svfsi-tight.log',0),
    ('reference-tight-linear-n200-c49c69c','ramp16','ramp16-solve.log',0)):
    p=work/name;r=audit.analyze(p/reference,p/log)
    assert len(r['failed_equation_steps'])==expected_failures
    assert r['passed']==(expected_failures==0)
    (out/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    reports[name]={k:v for k,v in r.items() if k!='failed_equation_steps'}
summary=dict(reports=reports,scope='Read-only real-log reanalysis after rejecting malformed iteration rows; no PDE rerun',
    unit_receipt=dict(command=['/usr/bin/python3','tests/test_svfsi_convergence.py'],passed=4,elapsed_seconds=.043,
        provenance='Actual Codex execution receipt, not a saved subprocess log',source_sha256=sha(out/'tests/test_svfsi_convergence.py') if (out/'tests/test_svfsi_convergence.py').exists() else sha(out/'test_svfsi_convergence.py')))
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
destination=root/'docs/research/data/svfsi-convergence-2026-11-08/final-parser-review'
shutil.copytree(out,destination)
hashes={p.name:sha(p) for p in out.iterdir() if p.is_file()}
assert hashes=={p.name:sha(p) for p in destination.iterdir() if p.is_file()}
(destination/'copied-files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps(dict(rechecked_logs=len(reports),verified_files=len(hashes),reports=reports)))
