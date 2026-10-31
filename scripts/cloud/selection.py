"""Explicit incremental CI policy. Planning needs only Python and a Git checkout."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'scripts/cloud/selection.json'
FINGERPRINT_PATHS = ('scripts/cloud/selection.json', 'scripts/cloud/selection.py',
                     'scripts/cloud/receipt.py', 'scripts/cloud/validate.py',
                     'scripts/cloud/run.sh', 'scripts/cloud/restore.sh',
                     '.github/workflows/core-numerics.yml', 'CMakeLists.txt',
                     'CMakePresets.json', 'environments/petsc-3.23.7-linux-64.lock')


def git(*args, root=ROOT):
    return subprocess.check_output(['git', *args], cwd=root).decode().strip()


def load_policy(path=POLICY):
    policy = json.loads(Path(path).read_text())
    if policy.get('schema') != 1 or not policy.get('tests'):
        raise ValueError('Unsupported or empty selection policy')
    for rule in policy['rules']:
        if not rule['paths'] or set(rule['tests']) - policy['tests'].keys():
            raise ValueError('Invalid path/test mapping: '+str(rule))
    return policy


def checked_names(names, catalog, allow_empty=False):
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError('Tests must be a list of names')
    if (not names and not allow_empty) or len(names) != len(set(names)):
        raise ValueError('Empty or duplicate test selection')
    unknown = set(names) - catalog.keys()
    if unknown:
        raise ValueError('Unknown tests: '+', '.join(sorted(unknown)))
    return sorted(names)


def classify(paths, policy):
    tests, python, reasons, ignored, unknown = set(), set(), {}, [], []
    for path in sorted(set(paths)):
        matching = [r for r in policy['rules'] if any(fnmatch.fnmatchcase(path, p) for p in r['paths'])]
        if matching:
            names = sorted({n for r in matching for n in r['tests']})
            tests.update(names)
            python.update(n for r in matching for n in r['python'])
            reasons[path] = names
        elif any(fnmatch.fnmatchcase(path, p) for p in policy['ignore']):
            ignored.append(path)
        else:
            unknown.append(path)
    if unknown:
        raise ValueError('Missing CI mapping (no full-suite fallback): '+', '.join(unknown))
    return dict(tests=sorted(tests), python=sorted(python), reasons=reasons, ignored=ignored)


def changed_paths(before, after, root=ROOT):
    # Disable rename detection: both the deleted and added path must be classified.
    raw = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', '-z',
                                   before, after, '--'], cwd=root)
    return [p.decode() for p in raw.split(b'\0') if p]


def fingerprint(root=ROOT):
    h = hashlib.sha256()
    for name in (*FINGERPRINT_PATHS, *sorted(p.relative_to(root).as_posix() for p in (root/'cmake').glob('*'))):
        h.update(name.encode()+b'\0'+(root/name).read_bytes()+b'\0')
    return h.hexdigest()


def reusable(previous, context, catalog, ancestor):
    """A receipt is reusable only after its Actions run was independently successful."""
    if not isinstance(previous, dict) or previous.get('schema') != 1 or previous.get('status') != 'passed':
        return False
    for key in ('repository', 'pr', 'base', 'fingerprint'):
        if previous.get(key) != context[key]:
            return False
    if not context['pr'] or not re.fullmatch(r'[0-9a-f]{40}', previous.get('head', '')):
        return False
    if not ancestor(previous['head'], context['head']):
        return False
    try:
        names = checked_names(previous['covered'], catalog, allow_empty=True)
        origins = previous['origins']
        if set(origins) != set(names):
            return False
        for name in names:
            if set(origins[name]) != {'debug', 'release'}:
                return False
            for origin in origins[name].values():
                if not isinstance(origin.get('run_id'), int) or origin['run_id'] <= 0:
                    return False
                if not re.fullmatch(r'[0-9a-f]{40}', origin.get('commit', '')):
                    return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def make_plan(context, policy, paths, changed_since_previous=None, previous=None):
    full = classify(paths, policy)
    affected = classify(changed_since_previous, policy) if previous is not None else full
    covered = set(previous['covered']) if previous else set()
    required = set(full['tests'])
    run = sorted((required - covered) | set(affected['tests']))
    # A reverted or deleted feature can still need regression checks even when
    # absent from the cumulative PR diff. Their evidence also belongs to this run.
    needed = required | set(run)
    reuse = sorted(needed - set(run))
    return dict(schema=1, **context, selection='explicit', requested='incremental',
                required=sorted(needed), tests=run, reused=reuse,
                origins={n: previous['origins'][n] for n in reuse},
                previous_run_id=previous['run_id'] if previous else None,
                python=affected['python'], changes=full['reasons'],
                delta=affected['reasons'], ignored=full['ignored'],
                disposition='run' if run else ('reused' if reuse else 'not_required'))


def validate_inventory(inventory, catalog, names):
    actual = [t['name'] for t in inventory]
    if len(actual) != len(set(actual)):
        raise ValueError('Duplicate CTest inventory')
    if set(actual) != set(catalog):
        raise ValueError('CTest catalog drift: missing='+str(sorted(set(catalog)-set(actual)))+
                         ', unmapped='+str(sorted(set(actual)-set(catalog))))
    names = checked_names(names, catalog)
    return [t for t in inventory if t['name'] in set(names)]


def targets_for(names, catalog):
    checked_names(names, catalog)
    return sorted({target for name in names for target in catalog[name]['targets']})


def test_filter(names):
    # CTest's CMake regex dialect supports this subset; match entire names only.
    return ['-R', '^('+'|'.join(re.escape(n) for n in names)+')$']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--base', help='Local/manual incremental comparison ref')
    ap.add_argument('--selection', choices=['incremental', 'explicit', 'all'], default='incremental')
    ap.add_argument('--tests', default='')
    ap.add_argument('--offline', action='store_true', help='Do not look up prior Actions receipts')
    a = ap.parse_args()
    policy = load_policy()
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text()) if os.environ.get('GITHUB_EVENT_PATH') else {}
    pr = event.get('pull_request')
    if pr and a.selection != 'incremental':
        raise ValueError('PRs only permit incremental selection')
    base = pr['base']['sha'] if pr else git('rev-parse', a.base or 'origin/main')
    head = pr['head']['sha'] if pr else git('rev-parse', 'HEAD')
    commit = git('rev-parse', 'HEAD')  # PR checkout is the merge preview actually tested.
    context = dict(repository=os.environ.get('GITHUB_REPOSITORY', 'local'),
                   pr=event.get('number', 0) if pr else 0, base=base, head=head,
                   commit=commit, tree=git('rev-parse', 'HEAD^{tree}'), fingerprint=fingerprint(),
                   run_id=int(os.environ.get('GITHUB_RUN_ID', '0')))
    previous = None
    if pr and not a.offline:
        from receipt import find_previous
        previous = find_previous(context, policy['tests'])
    if a.selection == 'incremental':
        paths = changed_paths(base, commit)
        delta = changed_paths(previous['head'], head) if previous else None
        plan = make_plan(context, policy, paths, delta, previous)
    else:
        names = sorted(policy['tests']) if a.selection == 'all' else checked_names(
            re.split(r'[\s,]+', a.tests.strip()) if a.tests.strip() else [], policy['tests'])
        plan = dict(schema=1, **context, selection='all' if a.selection == 'all' else 'explicit',
                    requested=a.selection, required=names, tests=names, reused=[], origins={},
                    previous_run_id=None, python=['tests/test_ci_selection.py', 'tests/test_cloud_evidence.py'],
                    changes={}, delta={}, ignored=[], disposition='run')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps(plan, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write('run_numerics='+str(bool(plan['tests'])).lower()+'\n')
    # Execute only the selected standard-library checks, once before the matrix.
    for script in plan['python']:
        subprocess.run([sys.executable, str(ROOT/script)], cwd=ROOT, check=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write('### Incremental selection\n\n'+
                    f"Disposition: **{plan['disposition']}**; new tests: {len(plan['tests'])}; reused: {len(plan['reused'])}.\n\n"+
                    '```json\n'+json.dumps(plan, indent=2)+'\n```\n')


if __name__ == '__main__':
    main()
