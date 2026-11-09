import hashlib,json,shutil,time
from pathlib import Path
root=Path('/mnt/c/Users/tfblab633/Documents/ChatGPT/数值计算/EONSim-new-current')
w=Path('/home/tfblab633/EONSim-prod48-20261107')
c=w/'length24-native-proof-review-b002c06'
folder=root/'docs/research/data/length24-periodic-audit-and-native-proof-plan-2026-11-09'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
definition=json.loads((c/'definition.json').read_text())
assert sha(c/'controller.py')==definition['controller_sha256']
assert sha(folder/'controller.py')==definition['proof_controller_sha256']
assert sha(folder/'definition.json')==definition['proof_definition_sha256']
assert sha(folder/'bounded_cgroup_job_2g.py')==definition['cap_sha256']
assert sha(folder/'execution-guard.py')==definition['guard_sha256']
records={}
for name,src in {'raw-review-controller.py':c/'controller.py','raw-review-definition.json':c/'definition.json',
                 'capture-length24-review-queue.py':Path(__file__)}.items():
    dst=folder/name;assert not dst.exists();before=sha(src);shutil.copy2(src,dst);assert sha(dst)==before==sha(src)
    records[name]=dict(source=str(src),sha256=before,bytes=src.stat().st_size)
receipt=folder/'review-queue-source.json';assert not receipt.exists()
receipt.write_text(json.dumps(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),files=records,
    queued_pid=44493,proof_pid=44437,adopted=False,review_completed=False,
    scope='Immutable queued verifier and definition only; mutable status/log/output excluded. All210 field pairs and11 native boundaries must be recomputed after actual proof completion. No automatic extension.'),indent=2)+'\n')
print(json.dumps(dict(files=len(records)+1,proof_pid=44437,review_pid=44493,adopted=False)))
