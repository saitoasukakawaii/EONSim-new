"""Seal only unlaunched orchestration code and its actual guard checks."""
import hashlib
import json
from pathlib import Path
import shutil
import time

root = Path(__file__).resolve().parents[2]
helpers = root/'build/prod48-20261107'
w = Path('/home/tfblab633/EONSim-prod48-20261107')
d = Path('/mnt/d/EONSim-prod48-20261107')
out = root/'docs/research/data/alpha1-s96-execution-preparation-2026-11-09'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
assert not out.exists()
report = read(helpers/'alpha1-s96-execution-controller-checks.json')
assert report['passed'] and len(report['checks']) == 22
assert report['numerical_runs'] == 0 and report['prepared'] is False and report['adopted'] is False
assert report['controller_sha256'] == sha(helpers/'run-alpha1-s96-fine-family.py')
assert report['preparer_sha256'] == sha(helpers/'prepare-alpha1-s96-fine-family.py')
assert not (w/'alpha1-s96-fine-family-plan-b0fd881').exists()
assert not (w/'alpha1-s96-fine-family-current.json').exists()
states = {name:read(w/(name+'-current.json')) for name in
          ('alpha1-native200-lu32-recovery','alpha1-s96-coarse-n400',
           'alpha1-s96-fine-execution-screen','alpha1-s96-fine-execution-review')}
assert states['alpha1-s96-fine-execution-screen']['state'] == 'waiting_for_existing_families'
assert states['alpha1-s96-fine-execution-review']['state'] == 'waiting_for_completed_screen'
screen = d/'alpha1-s96-fine-execution-screen-a341bc6'
coarse = w/'alpha1-s96-coarse-n400-fcc2956'
a,b = read(screen/'definition.json')['source_hashes'],read(coarse/'definition.json')['source_hashes']
assert a == b
for name,digest in a.items():
    assert sha(screen/'source'/name) == sha(coarse/'source'/name) == digest
out.mkdir()
inventory = {}
for name in ('prepare-alpha1-s96-fine-family.py','run-alpha1-s96-fine-family.py',
             'check-alpha1-s96-fine-controller.py','alpha1-s96-execution-controller-checks.json',
             'capture-alpha1-execution-preparation.py'):
    original = helpers/name
    shutil.copy2(original,out/name)
    assert sha(original) == sha(out/name)
    inventory[name] = dict(source=str(original),sha256=sha(original),bytes=original.stat().st_size)
manifest = dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),files=inventory,
    frozen_analysis_source_hashes=a,actual_dependency_states=states,
    prepared=False,adopted=False,numerical_runs=0,checks=22,
    scope='Unlaunched controller and actual static guard checks only. Existing running/waiting producers are unmodified; no numerical preparation directory or execution status exists. No field, cost, physical, budget, or project qualification claimed.')
(out/'source.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(completed=True,files=len(inventory),prepared=False,adopted=False,out=str(out))))
