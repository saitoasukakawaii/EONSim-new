"""Copy complete reports and unlaunched extension preparation; raw trajectories remain separate."""
import hashlib,json,shutil,time
from pathlib import Path
root=Path('/mnt/c/Users/tfblab633/Documents/ChatGPT/数值计算/EONSim-new-current')
w=Path('/home/tfblab633/EONSim-prod48-20261107');d=Path('/mnt/d/EONSim-prod48-20261107')
sc=w/'elastic-n200-native1600-handoff-32fb313';lc=w/'length24-bounded-postprocess-handoff-e771355'
short=d/'elastic-s24-l1-n200-mumps-chord-native1600-32fb313';long=d/'elastic-s24-l1-n200-L24-bounded-postprocess-e771355'
folder=root/'docs/research/data/elastic-n200-audit-and-length-summary-2026-11-09'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not folder.exists()
assert read(w/'elastic-n200-native1600-current.json')['state']=='completed'
assert read(w/'elastic-length24-bounded-postprocess-current.json')['state']=='completed'
sa=read(short/'eonsim-audit.json');la=read(long/'eonsim-audit.json');comp=read(long/'length-comparison.json')
assert sa['periodic'] and not la['periodic'] and sa['sampled_steps']==la['sampled_steps']==600
assert sa['analysis_script_sha256']==la['analysis_script_sha256']=='6fdd2a4a8d82c4a40a51235c51129f1c4bc0a26d2609793540ee4402849e5e3d'
assert read(lc/'completion.json')['length_comparison_sha256']==sha(long/'length-comparison.json')
for path,h in comp['input_audits'].items():assert sha(Path(path))==h
checks=read(root/'build/prod48-20261107/length24-extension-static-check.json')
assert checks['passed'] and not checks['prepared'] and not checks['adopted'] and not checks['actual_inspection']['ready']
folder.mkdir();sources={
    'l12-audit.json':short/'eonsim-audit.json','l24-audit.json':long/'eonsim-audit.json',
    'l12-completion.json':sc/'completion.json','l24-completion.json':lc/'completion.json',
    'length-comparison.json':long/'length-comparison.json','original-length-kernel.py':lc/'original-length-kernel.py',
    'l12-definition.json':sc/'definition.json','l24-definition.json':lc/'definition.json',
    'l12-case.json':short/'case.json','l12-geometry.json':short/'geometry.json',
    'l24-case.json':long/'case.json','l24-geometry.json':long/'geometry.json',
    'extend-length24-native6400.py':root/'build/prod48-20261107/extend-length24-native6400.py',
    'check-length24-extension-static.py':root/'build/prod48-20261107/check-length24-extension-static.py',
    'length24-extension-static-check.json':root/'build/prod48-20261107/length24-extension-static-check.json',
    'capture-length24-native-proof.py':w/'length24-native-proof-capture-98ee0f9/controller.py',
    'proof-capture-definition.json':w/'length24-native-proof-capture-98ee0f9/definition.json',
    'capture-n200-audit-and-length-summary.py':Path(__file__)}
records={}
for name,p in sources.items():
    before=sha(p);shutil.copy2(p,folder/name);assert sha(folder/name)==before==sha(p)
    records[name]=dict(source=str(p),sha256=before,bytes=p.stat().st_size)
record=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),base='98ee0f93d04537b7cf8a9a5045c501ac6dcce806',
    l12_completed=True,l24_completed=True,l12_periodic=True,l24_periodic=False,
    comparison_is_dynamic_length_sensitivity=True,pure_end_error_claim=False,extended_production_prepared=False,
    extended_production_adopted=False,full_qualification=False,files=records,
    scope='Complete matched-analyzer reports and original arithmetic, plus unlaunched extension and queued proof capture static evidence. Full raw L24/L12/cross archives are still being captured by43422; no raw-field substitute or whole-project acceptance.')
(folder/'source.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(files=len(records)+1,full_qualification=False)))
