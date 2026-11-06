import hashlib
import json
from pathlib import Path
import sys
import tarfile

root = Path.cwd()
sys.path.insert(0, str(root / 'scripts'))
from analyze_fsi_error_budget import audit_cycle

archive = root / 'docs/research/data/fsi-next-03/fixed-operator/n2-dt001.tar.gz'
index = json.loads(archive.with_suffix('.gz.manifest.json').read_text())
destination = Path('/home/tfblab633/EONSim-next03-20261105/fixed-n2-dt001')
if destination.exists():
    raise RuntimeError('Refusing to overwrite an existing baseline')
with tarfile.open(archive) as stream:
    members = stream.getmembers()
    if len({m.name for m in members}) != len(members):
        raise RuntimeError('Duplicate archive members')
    if {m.name for m in members} != set(index['files']):
        raise RuntimeError('Archive and manifest file sets differ')
    for member in members:
        if not member.isfile():
            raise RuntimeError('Expected only regular evidence files')
        content = stream.extractfile(member).read()
        expected = index['files'][member.name]
        if len(content) != expected['bytes'] or hashlib.sha256(content).hexdigest() != expected['sha256']:
            raise RuntimeError('Archive checksum mismatch: ' + member.name)
    destination.mkdir(parents=True)
    stream.extractall(destination, filter='data')
definition = json.loads((destination / 'study-definition.json').read_text())
for name, digest in definition['source_sha256'].items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Study source changed: ' + name)
result = dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
              restored_to=str(destination), files_verified=len(members),
              source_fingerprints_match=True, audit=audit_cycle(destination))
output = root / 'build/resume-20261105/restored-n2.json'
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
