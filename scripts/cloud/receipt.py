"""Read same-PR successful Actions evidence and publish a bounded coverage receipt."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from selection import ROOT, checked_names, load_policy, reusable


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header('Authorization')
        return redirected


def api(path, binary=False):
    url = 'https://api.github.com'+path
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer '+os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'EONSim-incremental-ci'})
    with urllib.request.build_opener(SafeRedirect()).open(request, timeout=30) as response:
        data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Receipt API response exceeds limit')
    return data if binary else json.loads(data)


def read_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != 'receipt.json' or entries[0].file_size > 1024 * 1024:
            raise ValueError('Invalid receipt artifact contents')
        return json.loads(archive.read(entries[0]))


def find_previous(context, catalog):
    """No artifacts or API access means fresh PR-scoped selection, never full suite."""
    if not os.environ.get('GH_TOKEN'):
        print('No Actions credential; use full PR diff for incremental selection.')
        return None
    repo = context['repository']
    def ancestor(old, new):
        return subprocess.run(['git', 'merge-base', '--is-ancestor', old, new], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    try:
        for page in range(1, 4):
            runs = api(f'/repos/{repo}/actions/workflows/core-numerics.yml/runs?event=pull_request&status=success&per_page=30&page={page}')['workflow_runs']
            for run in runs:
                if run['id'] == context['run_id'] or run['conclusion'] != 'success':
                    continue
                if not any(p['number'] == context['pr'] for p in run['pull_requests']):
                    continue
                artifacts = api(f'/repos/{repo}/actions/runs/{run["id"]}/artifacts?name=incremental-receipt&per_page=100')['artifacts']
                artifacts = [a for a in artifacts if a['name'] == 'incremental-receipt' and not a['expired']]
                if len(artifacts) != 1:
                    continue
                try:
                    receipt = read_archive(api(f'/repos/{repo}/actions/artifacts/{artifacts[0]["id"]}/zip', binary=True))
                    if receipt.get('run_id') != run['id'] or receipt.get('head') != run['head_sha']:
                        continue
                    if reusable(receipt, context, catalog, ancestor):
                        print(f'Reusing successful same-PR receipt from run {run["id"]}')
                        return receipt
                except (ValueError, KeyError, TypeError, zipfile.BadZipFile):
                    print(f'Invalid receipt in run {run["id"]}; not reused.')
            if len(runs) < 30:
                break
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
        # Never print headers or credentials. A missing baseline only costs a
        # PR-scoped check; it cannot manufacture a successful test result.
        print('Prior receipt unavailable ('+type(error).__name__+'); selecting from PR diff.')
    return None


def finish(plan, summaries, catalog, lock_sha256):
    selected = checked_names(plan['tests'], catalog, allow_empty=True)
    reused = checked_names(plan['reused'], catalog, allow_empty=True)
    required = checked_names(plan['required'], catalog, allow_empty=True)
    if set(selected) & set(reused) or set(selected) | set(reused) != set(required):
        raise ValueError('Invalid executed/reused partition')
    if set(plan['origins']) != set(reused):
        raise ValueError('Missing inherited origins')
    origins = json.loads(json.dumps(plan['origins']))
    if selected:
        if set(summaries) != {'debug', 'release'}:
            raise ValueError('Both selected mode summaries are required')
        for mode, summary in summaries.items():
            if (summary.get('status') != 'passed' or summary.get('commit') != plan['commit'] or
                    summary.get('mode') != mode or summary.get('petsc') != '3.23.7' or
                    summary.get('lock_sha256') != lock_sha256 or summary.get('dirty') is not False):
                raise ValueError('Invalid validation provenance: '+mode)
            results = summary.get('tests', [])
            names = [t['name'] for t in results]
            if len(names) != len(set(names)) or set(names) != set(selected):
                raise ValueError('Incomplete/duplicate/unexpected results: '+mode)
            if any(t.get('status') != 'passed' or t.get('exit_code') != 0 or t.get('timeout') for t in results):
                raise ValueError('Unsuccessful test results: '+mode)
            for name in names:
                origins.setdefault(name, {})[mode] = dict(run_id=plan['run_id'], commit=plan['commit'])
    elif summaries:
        raise ValueError('Unexpected numerical summary for no-run plan')
    return {**{k: plan[k] for k in ('schema', 'repository', 'pr', 'base', 'head', 'commit', 'tree', 'fingerprint', 'run_id')},
            'status': 'passed', 'covered': required, 'executed': selected, 'reused': reused,
            'origins': origins, 'previous_run_id': plan['previous_run_id'],
            'disposition': plan['disposition']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text())
    summaries = {}
    for path in a.evidence.glob('**/summary.json'):
        summary = json.loads(path.read_text())
        mode = summary['mode']
        if mode in summaries:
            raise ValueError('Duplicate mode summary')
        summaries[mode] = summary
    result = finish(plan, summaries, load_policy()['tests'],
                    hashlib.sha256((ROOT/'environments/petsc-3.23.7-linux-64.lock').read_bytes()).hexdigest())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write('### Validation evidence\n\n'+
                    f"Executed this run: {len(result['executed'])} tests per mode; "
                    f"reused: {len(result['reused'])}; disposition: {result['disposition']}.\n\n"+
                    'Reused results are historical evidence, not new numerical passes.\n')


if __name__ == '__main__':
    main()
