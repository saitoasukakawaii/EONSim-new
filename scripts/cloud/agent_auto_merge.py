"""Merge only current, verified agent PRs; execute from trusted main, never PR code."""
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode

CORE_JOBS = {'Select affected checks', 'PETSc 3.23.7 / debug',
             'PETSc 3.23.7 / release', 'Record incremental evidence'}
SITE_JOBS = {'Build VitePress'}
REQUIRED_JOBS = CORE_JOBS | SITE_JOBS
HOLD_LABELS = {'manual-review', 'do-not-merge', 'no-automerge'}


class GitHub:
    def __init__(self, repository):
        self.repository = repository

    def api(self, path, method='GET', data=None):
        command = ['gh', 'api', '--method', method,
                   f'repos/{self.repository}/{path}']
        if data is not None:
            command += ['--input', '-']
        result = subprocess.run(command, input=json.dumps(data) if data is not None else None,
                                text=True, capture_output=True, check=True, timeout=60)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def pages(self, path, key=None):
        result = []
        for page in range(1, 101):
            separator = '&' if '?' in path else '?'
            data = self.api(f'{path}{separator}per_page=100&page={page}')
            items = data[key] if key else data
            result.extend(items)
            if len(items) < 100:
                return result
        raise RuntimeError('Pagination limit reached; refusing incomplete evidence')


def hold_reason(pr, files, repository):
    if pr.get('state') != 'open' or pr.get('draft'):
        return 'closed or draft PR'
    if pr.get('base', {}).get('ref') != 'main':
        return 'target is not main'
    head = pr.get('head', {})
    if (head.get('repo') or {}).get('full_name') != repository:
        return 'fork or missing source repository'
    if not head.get('ref', '').startswith('codex/'):
        return 'not a codex/* branch'
    if HOLD_LABELS & {label['name'].lower() for label in pr.get('labels', [])}:
        return 'manual hold label'
    if not files or len(files) != pr.get('changed_files'):
        return 'empty or incomplete changed-file list'
    for item in files:
        # Renames must be checked at both ends, including moves into drafts.
        for path in (item['filename'], item.get('previous_filename', '')):
            if not path:
                continue
            if (path == 'AGENTS.md' or path.endswith('/AGENTS.md') or
                    path.startswith(('.github/', '.agents/', 'scripts/cloud/')) or
                    path == 'tests/test_agent_auto_merge.py'):
                return 'CI, permissions, or agent-policy change requires human review'
            if path.startswith('website/') and not path.startswith(
                    ('website/drafts/', 'website/templates/')):
                return 'public website change requires human review'
    return None


def branch_ready(branch):
    checks = branch.get('protection', {}).get('required_status_checks', {})
    contexts = set(checks.get('contexts', []))
    contexts.update(item['context'] for item in checks.get('checks', []))
    return branch.get('protected') is True and REQUIRED_JOBS <= contexts


def run_passed(run, jobs, pr, required, repository):
    if (run.get('event') != 'pull_request' or run.get('status') != 'completed' or
            run.get('conclusion') != 'success' or
            run.get('head_sha') != pr['head']['sha'] or
            run.get('head_branch') != pr['head']['ref'] or
            (run.get('head_repository') or {}).get('full_name') != repository):
        return False
    for name in required:
        matches = [job for job in jobs if job.get('name') == name]
        if len(matches) != 1 or matches[0].get('status') != 'completed' or \
                matches[0].get('conclusion') != 'success':
            return False
    return True


def ci_passed(client, pr):
    for workflow, required in [('core-numerics.yml', CORE_JOBS),
                               ('website-build.yml', SITE_JOBS)]:
        query = urlencode({'event': 'pull_request', 'head_sha': pr['head']['sha'],
                           'branch': pr['head']['ref']})
        runs = client.pages(f'actions/workflows/{workflow}/runs?{query}', 'workflow_runs')
        if not runs:
            return False
        # Do not accept an older successful run when the newest run failed/is pending.
        run = max(runs, key=lambda item: item['id'])
        jobs = client.pages(f"actions/runs/{run['id']}/jobs?filter=latest", 'jobs')
        if not run_passed(run, jobs, pr, required, client.repository):
            return False
    return True


def merge_one(client, number):
    pr = client.api(f'pulls/{number}')
    files = client.pages(f'pulls/{number}/files')
    reason = hold_reason(pr, files, client.repository)
    if reason:
        print(f'PR #{number}: held: {reason}')
        return False
    if not branch_ready(client.api('branches/main')):
        print(f'PR #{number}: held: protect main and require all five documented checks')
        return False
    if not ci_passed(client, pr):
        print(f'PR #{number}: waiting for successful checks on current head')
        return False
    # Re-fetch mutable PR policy and SHA immediately before the atomic merge request.
    current = client.api(f'pulls/{number}')
    current_files = client.pages(f'pulls/{number}/files')
    if (current['head']['sha'] != pr['head']['sha'] or
            current['base']['sha'] != pr['base']['sha'] or
            hold_reason(current, current_files, client.repository) or
            current.get('mergeable') is not True or
            current.get('mergeable_state') != 'clean' or
            not branch_ready(client.api('branches/main'))):
        print(f'PR #{number}: changed or blocked; no merge')
        return False
    # No admin bypass, auto-approval, force push, or queued merge on a future head.
    result = client.api(f'pulls/{number}/merge', method='PUT',
                        data={'merge_method': 'squash', 'sha': current['head']['sha']})
    if not result or not result.get('merged'):
        raise RuntimeError(f'PR #{number}: GitHub did not confirm merge')
    print(f"PR #{number}: merged as {result['sha']}")
    # Branch cleanup is delegated to GitHub's Automatically delete head branches.
    return True


def candidates(client, event, requested=''):
    if requested:
        number = int(requested)
        if number <= 0:
            raise ValueError('PR number must be positive')
        return [number]
    if event.get('pull_request'):
        return [int(event['pull_request']['number'])]
    run = event.get('workflow_run', {})
    if (run.get('event') != 'pull_request' or run.get('conclusion') != 'success' or
            (run.get('head_repository') or {}).get('full_name') != client.repository):
        return []
    # GitHub can return an empty workflow_run.pull_requests array for same-repo PRs.
    # Resolve by the exact source branch; merge_one independently revalidates SHA/CI.
    query = urlencode({'state': 'open', 'base': 'main',
                       'head': client.repository.split('/')[0] + ':' + run['head_branch']})
    return [int(pr['number']) for pr in client.pages('pulls?' + query)]


def main():
    client = GitHub(os.environ['GITHUB_REPOSITORY'])
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    for number in candidates(client, event, os.environ.get('PR_NUMBER', '')):
        merge_one(client, number)


if __name__ == '__main__':
    main()
