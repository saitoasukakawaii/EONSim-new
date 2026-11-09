"""Isolated C/D Git object proof; never changes the project object database."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback

root = Path(__file__).resolve().parents[2]
control = root / 'build/prod48-20261107/git-cross-drive-proof-224aad5'
fixture = control / 'fixture'
external = Path('D:/EONSim-prod48-20261107/git-object-proofs/224aad5')
store = external / 'objects'
clone = external / 'independent-clone'
archive_name = 'pressure-audit-bounded-memory-validation-2026-11-09'
metadata = root / 'docs/research/data' / archive_name
source = Path('D:/EONSim-prod48-20261107/repository-archives') / archive_name / 'part001.tar.xz'

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def dump(p, v):
    p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

commands = []
def call(args, *, env=None, cwd=None):
    started = time.monotonic()
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    commands.append(dict(argv=list(map(str, args)), returncode=p.returncode,
                         seconds=time.monotonic()-started,
                         stderr=p.stderr.decode('utf-8', errors='replace')))
    if p.returncode:
        raise RuntimeError(json.dumps(commands[-1], ensure_ascii=False))
    return p.stdout

def git(where, *args, env=None):
    return call(['git', '-c', 'safe.directory='+where.as_posix(),
                 '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
                 '-C', str(where), *args], env=env)

def linux(p):
    s = p.as_posix()
    assert s[1:3] == ':/'
    return '/mnt/'+s[0].lower()+'/'+s[3:]

def wsl_git(where, *args):
    q = linux(where)
    return call(['wsl.exe', '-d', 'Ubuntu-24.04', '--exec', '/usr/bin/git',
                 '-c', 'safe.directory='+q, '-c', 'gc.auto=0',
                 '-c', 'maintenance.auto=false', '-C', q, *args])

assert not control.exists() and not external.exists()
assert not any(k.startswith('GIT_') and k not in ('GIT_OPTIONAL_LOCKS',) for k in os.environ), 'Unexpected inherited Git overrides'
assert shutil.disk_usage(root).free > 4*1024**3 + 64*1024**2
assert shutil.disk_usage(external.parent.parent).free > 4*1024**3
project_head = git(root, 'rev-parse', 'HEAD').decode().strip()
assert project_head == '224aad53d012f8aa4c661b61089eb0b070ce16e9'
assert not git(root, 'status', '--porcelain').strip()
project_before = {n:sha(root/'.git'/n) for n in ('HEAD','index','config')}
assert not (root/'.git/objects/info/alternates').exists()
control.mkdir()
external.mkdir(parents=True)
shutil.copy2(__file__, control/'controller.py')
try:
    fixture.mkdir()
    git(fixture, 'init', '--initial-branch=proof')
    (store/'info').mkdir(parents=True)
    (store/'pack').mkdir()
    junction = fixture/'.git/objects/external-evidence'
    # Powershell creates only this new fixture junction; no source is moved.
    script = "New-Item -ItemType Junction -Path '"+str(junction).replace("'", "''")+"' -Target '"+str(store).replace("'", "''")+"' | Select-Object -ExpandProperty FullName"
    call(['powershell.exe','-NoProfile','-NonInteractive','-Command',script])
    assert junction.resolve() == store.resolve()
    (fixture/'.git/objects/info/alternates').write_bytes(b'./external-evidence\n')
    item = next(x for x in json.loads((metadata/'archives.json').read_text(encoding='utf-8'))['archives'] if x['file']==source.name)
    assert source.stat().st_size == item['bytes'] and sha(source)==item['sha256']
    before_source = (source.stat().st_size, source.stat().st_mtime_ns)
    env = os.environ.copy()
    env['GIT_OBJECT_DIRECTORY'] = str(junction)
    oid = git(fixture, 'hash-object', '-w', '--no-filters', str(source), env=env).decode().strip()
    assert (store/oid[:2]/oid[2:]).is_file()
    assert not (fixture/'.git/objects'/oid[:2]/oid[2:]).exists()
    relative = 'evidence/part001.tar.xz'
    git(fixture, 'update-index', '--add', '--cacheinfo', '100644,'+oid+','+relative)
    git(fixture, 'update-index', '--skip-worktree', '--', relative)
    git(fixture, '-c', 'user.name=EONSim isolated storage proof', '-c', 'user.email=storage-proof@invalid',
        'commit', '-m', 'Verify a complete ordinary archive blob with external object storage')
    fixture_head = git(fixture,'rev-parse','HEAD').decode().strip()
    for label, reader in [('windows-fixture',git),('wsl-fixture',wsl_git)]:
        raw=reader(fixture,'show','HEAD:'+relative)
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'], label
        fsck=reader(fixture,'fsck','--full','--strict')
        (control/(label+'-fsck.txt')).write_bytes(fsck)
    # --no-local transfers ordinary objects, not a shared/local clone dependency.
    call(['git','-c','gc.auto=0','-c','maintenance.auto=false','clone','--no-local','--no-checkout',str(fixture),str(clone)])
    assert not (clone/'.git/objects/info/alternates').exists()
    for label,reader in [('windows-independent-clone',git),('wsl-independent-clone',wsl_git)]:
        assert reader(clone,'rev-parse','HEAD').decode().strip()==fixture_head
        raw=reader(clone,'show','HEAD:'+relative)
        assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'], label
        (control/(label+'-fsck.txt')).write_bytes(reader(clone,'fsck','--full','--strict'))
    assert (source.stat().st_size,source.stat().st_mtime_ns)==before_source and sha(source)==item['sha256']
    assert git(root,'rev-parse','HEAD').decode().strip()==project_head
    assert project_before == {n:sha(root/'.git'/n) for n in project_before}
    assert not (root/'.git/objects/info/alternates').exists()
    assert not git(root,'status','--porcelain').strip()
    dump(control/'report.json',dict(passed=True,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
         project_head=project_head,project_before=project_before,project_unchanged=True,
         fixture=str(fixture),external_store=str(store),independent_clone=str(clone),
         fixture_head=fixture_head,blob_oid=oid,archive=item,
         ordinary_blob=True,independent_clone_has_no_alternates=True,
         windows_and_wsl_default_readback=True,scope='Isolated proof only; actual project storage not changed.',
         sources=['https://git-scm.com/docs/gitrepository-layout','https://git-scm.com/docs/git-clone']))
    print((control/'report.json').read_text(encoding='utf-8'))
except BaseException as e:
    dump(control/'failure.json',dict(error=str(e),traceback=traceback.format_exc(),project_storage_changed=False))
    raise
finally:
    dump(control/'commands.json',commands)
