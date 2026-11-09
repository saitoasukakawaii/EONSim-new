"""Stage manifest-listed D-drive archives as ordinary, sparse Git blobs.

No file is moved or deleted, and no refs or repository configuration change.
The archive capture's byte verification remains separate from this Git check.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
args = parser.parse_args()
assert re.fullmatch(r'[a-z0-9-]+', args.name)
root = Path(__file__).resolve().parents[2]
metadata = root/'docs/research/data'/args.name
record = json.loads((metadata/'archives.json').read_text())
store = Path('D:/EONSim-prod48-20261107/repository-archives')/args.name
assert record['local_archive_store'] == '/mnt/d/EONSim-prod48-20261107/repository-archives/'+args.name
assert store.is_dir() and metadata.is_dir()
reserve = 4*1024**3
remaining_archive_bytes = sum(item['bytes'] for item in record['archives'])
# These compressed archives can cost almost their full size as new Git blobs.
# Reserve the whole batch before the first index write, not just a free-space
# check that a multi-gigabyte batch could consume below the existing floor.
assert shutil.disk_usage(root).free > reserve+remaining_archive_bytes+64*1024**2
base = ['git', '-c', 'safe.directory='+root.as_posix(), '-c', 'gc.auto=0',
        '-c', 'maintenance.auto=false', '-C', str(root)]
commands = []

def git(*items):
    command = base+list(items)
    commands.append(command)
    return subprocess.check_output(command, stderr=subprocess.PIPE)

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

head = git('rev-parse', 'HEAD').decode().strip()
branch = git('branch', '--show-current').decode().strip()
assert branch == 'codex/fsi-production-48h-20261107'
results = []
for item in record['archives']:
    name = item['file']
    assert re.fullmatch(r'part[0-9]{3}\.tar\.xz', name)
    source = store/name
    relative = (metadata/name).relative_to(root).as_posix()
    assert not (root/relative).exists()
    assert not git('ls-files', '--', relative).strip(), 'Refusing to overwrite an existing index entry'
    before = source.stat()
    assert before.st_size == item['bytes'] and digest(source) == item['sha256']
    assert shutil.disk_usage(root).free > reserve+item['bytes']+64*1024**2
    oid = git('hash-object', '-w', '--no-filters', str(source)).decode().strip()
    assert re.fullmatch(r'[0-9a-f]{40}', oid)
    git('update-index', '--add', '--cacheinfo', '100644,'+oid+','+relative)
    git('update-index', '--skip-worktree', '--', relative)
    flags = git('ls-files', '-v', '--', relative).decode().strip()
    assert flags == 'S '+relative
    stage = git('ls-files', '--stage', '--', relative).decode().strip()
    assert stage == '100644 '+oid+' 0\t'+relative
    indexed = git('show', ':'+relative)
    assert len(indexed) == item['bytes'] and hashlib.sha256(indexed).hexdigest() == item['sha256']
    del indexed
    after = source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    assert not (root/relative).exists()
    git('diff', '--exit-code', '--', relative)
    results.append(dict(**item, blob_oid=oid, index_path=relative, index_flags=flags,
                        indexed_bytes_match_manifest=True, local_source_retained=True,
                        archive_absent_from_sparse_worktree=True))
assert git('rev-parse', 'HEAD').decode().strip() == head
summary = dict(passed=True, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               source_checkpoint=head, branch=branch, archives=results,
               archives_json_sha256=digest(metadata/'archives.json'), commands=commands,
               scope='Actual project index readback. Every archive is a regular100644 Git blob, not an external pointer. D originals retained; no ref update, push, move, deletion, or physics change.')
(metadata/'index-staging.json').write_text(json.dumps(summary, indent=2)+'\n')
shutil.copy2(__file__, metadata/Path(__file__).name)
print(json.dumps({k:v for k,v in summary.items() if k!='commands'}, indent=2))
