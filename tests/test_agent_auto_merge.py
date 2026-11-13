"""Offline regression tests for the privileged auto-merge policy."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('agent_auto_merge', ROOT/'scripts/cloud/agent_auto_merge.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
REPO = 'owner/EONSim-new'


def pull():
    return {'number': 7, 'state': 'open', 'draft': False, 'labels': [],
            'changed_files': 1, 'base': {'ref': 'main', 'sha': 'b'*40},
            'head': {'ref': 'codex/example', 'sha': 'a'*40, 'repo': {'full_name': REPO}},
            'mergeable': True, 'mergeable_state': 'clean'}


def branch():
    return {'protected': True, 'protection': {'required_status_checks':
            {'contexts': sorted(m.REQUIRED_JOBS)}}}


def run(identifier=10):
    return {'id': identifier, 'event': 'pull_request', 'status': 'completed',
            'conclusion': 'success', 'head_sha': 'a'*40,
            'head_branch': 'codex/example', 'head_repository': {'full_name': REPO}}


def jobs(names):
    return [{'name': name, 'status': 'completed', 'conclusion': 'success'} for name in names]


class Client:
    repository = REPO

    def __init__(self):
        self.pr = pull()
        self.current = None
        self.reads = 0
        self.files = [{'filename': 'src/physics/fluid.cpp'}]
        self.branch = branch()
        self.runs = [run()]
        self.core_jobs = jobs(m.CORE_JOBS)
        self.site_jobs = jobs(m.SITE_JOBS)
        self.mutations = []

    def api(self, path, method='GET', data=None):
        if method != 'GET':
            self.mutations.append((path, method, data))
            return {'merged': True, 'sha': 'c'*40}
        if path == 'pulls/7':
            self.reads += 1
            return copy.deepcopy(self.current if self.current and self.reads > 1 else self.pr)
        if path == 'branches/main':
            return copy.deepcopy(self.branch)
        raise AssertionError(path)

    def pages(self, path, key=None):
        if path == 'pulls/7/files':
            return copy.deepcopy(self.files)
        if path.startswith('actions/workflows/'):
            result = copy.deepcopy(self.runs)
            if 'website-build.yml' in path:
                for item in result:
                    item['id'] += 100
            return result
        if path.startswith('actions/runs/'):
            identifier = int(path.split('/')[2])
            return copy.deepcopy(self.site_jobs if identifier >= 100 else self.core_jobs)
        if path.startswith('pulls?'):
            return [self.pr]
        raise AssertionError(path)


class PolicyTests(unittest.TestCase):
    def reason(self, path, previous=None):
        item = {'filename': path}
        if previous:
            item['previous_filename'] = previous
        return m.hold_reason(pull(), [item], REPO)

    def test_code_allowed(self):
        self.assertIsNone(self.reason('src/physics/fluid.cpp'))

    def test_drafts_allowed(self):
        self.assertIsNone(self.reason('website/drafts/learning.md'))
        self.assertIsNone(self.reason('website/templates/template.md'))

    def test_published_content_blocked(self):
        for path in ['website/index.md', 'website/knowledge/fsi.md',
                     'website/.vitepress/config.ts', 'website/package.json']:
            with self.subTest(path=path):
                self.assertIsNotNone(self.reason(path))

    def test_policy_changes_blocked(self):
        for path in ['AGENTS.md', 'src/AGENTS.md', '.github/workflows/a.yml',
                     '.agents/skills/a.md', 'scripts/cloud/selection.py',
                     'tests/test_agent_auto_merge.py']:
            with self.subTest(path=path):
                self.assertIsNotNone(self.reason(path))

    def test_renames_check_both_ends(self):
        self.assertIsNotNone(self.reason('website/drafts/a.md', 'website/knowledge/a.md'))
        self.assertIsNotNone(self.reason('docs/old.md', 'AGENTS.md'))
        self.assertIsNotNone(self.reason('website/knowledge/a.md', 'website/drafts/a.md'))

    def test_metadata_restrictions(self):
        for changed in [dict(draft=True), dict(state='closed'), dict(changed_files=2),
                        dict(labels=[{'name': 'NO-AUTOMERGE'}]),
                        dict(base={'ref': 'develop'}),
                        dict(head={'ref': 'codex/a', 'repo': {'full_name': 'fork/repo'}}),
                        dict(head={'ref': 'feature/a', 'repo': {'full_name': REPO}})]:
            pr = pull()
            pr.update(changed)
            with self.subTest(changed=changed):
                self.assertIsNotNone(m.hold_reason(pr, [{'filename': 'src/main.cpp'}], REPO))

    def test_incomplete_files_blocked(self):
        self.assertIsNotNone(m.hold_reason(pull(), [], REPO))

    def test_branch_requires_all_checks(self):
        self.assertEqual(len(m.REQUIRED_JOBS), 4)
        self.assertNotIn('PETSc 3.23.7 / debug', m.REQUIRED_JOBS)
        self.assertTrue(m.branch_ready(branch()))
        for name in m.REQUIRED_JOBS:
            data = branch()
            data['protection']['required_status_checks']['contexts'].remove(name)
            self.assertFalse(m.branch_ready(data))
        self.assertFalse(m.branch_ready({'protected': False}))
        legacy = branch()
        legacy['protection']['required_status_checks']['contexts'].append('PETSc 3.23.7 / debug')
        self.assertFalse(m.branch_ready(legacy))

    def test_successful_current_jobs(self):
        self.assertTrue(m.run_passed(run(), jobs(m.CORE_JOBS), pull(), m.CORE_JOBS, REPO))

    def test_stale_wrong_or_failed_runs(self):
        for key, value in [('head_sha', 'd'*40), ('event', 'push'),
                           ('head_branch', 'codex/other'), ('status', 'in_progress'),
                           ('conclusion', 'failure'), ('head_repository', None)]:
            candidate = run()
            candidate[key] = value
            with self.subTest(key=key):
                self.assertFalse(m.run_passed(candidate, jobs(m.CORE_JOBS), pull(), m.CORE_JOBS, REPO))

    def test_skipped_missing_and_duplicate_jobs_blocked(self):
        candidates = [jobs(m.CORE_JOBS)[:-1], jobs(m.CORE_JOBS)*2]
        for status in ['skipped', 'neutral', 'cancelled', 'failure', 'timed_out', None]:
            candidate = jobs(m.CORE_JOBS)
            candidate[0]['conclusion'] = status
            candidates.append(candidate)
        for candidate in candidates:
            self.assertFalse(m.run_passed(run(), candidate, pull(), m.CORE_JOBS, REPO))

    def test_verified_merge_is_head_locked_squash(self):
        client = Client()
        self.assertTrue(m.merge_one(client, 7))
        self.assertEqual(client.mutations, [('pulls/7/merge', 'PUT',
                         {'merge_method': 'squash', 'sha': 'a'*40})])

    def test_no_merge_without_branch_protection(self):
        client = Client()
        client.branch['protected'] = False
        self.assertFalse(m.merge_one(client, 7))
        self.assertEqual(client.mutations, [])

    def test_failed_or_pending_latest_run_blocks_old_success(self):
        for status, conclusion in [('completed', 'failure'), ('in_progress', None)]:
            client = Client()
            newer = run(11)
            newer.update(status=status, conclusion=conclusion)
            client.runs.append(newer)
            self.assertFalse(m.merge_one(client, 7))
            self.assertEqual(client.mutations, [])

    def test_missing_runs_or_site_job_blocks_merge(self):
        for mode in ['runs', 'site']:
            client = Client()
            if mode == 'runs':
                client.runs = []
            else:
                client.site_jobs = []
            self.assertFalse(m.merge_one(client, 7))
            self.assertEqual(client.mutations, [])

    def test_changes_before_merge_blocked(self):
        for mode in ['head', 'base', 'hold', 'draft', 'conflict', 'behind']:
            client = Client()
            client.current = pull()
            if mode in ('head', 'base'):
                client.current[mode]['sha'] = 'd'*40
            elif mode == 'hold':
                client.current['labels'] = [{'name': 'manual-review'}]
            elif mode == 'draft':
                client.current['draft'] = True
            elif mode == 'conflict':
                client.current['mergeable'] = False
            else:
                client.current['mergeable_state'] = 'behind'
            self.assertFalse(m.merge_one(client, 7))
            self.assertEqual(client.mutations, [])

    def test_workflow_run_empty_pr_array_fallback(self):
        event = {'workflow_run': dict(run(), pull_requests=[])}
        self.assertEqual(m.candidates(Client(), event), [7])

    def test_fork_and_non_pr_events_rejected(self):
        for changed in [{'event': 'push'}, {'conclusion': 'failure'},
                        {'head_repository': {'full_name': 'fork/repo'}}]:
            candidate = dict(run(), **changed)
            self.assertEqual(m.candidates(Client(), {'workflow_run': candidate}), [])

    def test_manual_pr_number_validation(self):
        self.assertEqual(m.candidates(Client(), {}, '7'), [7])
        for value in ['0', '-1', '7; echo unsafe', 'not-a-number']:
            with self.assertRaises(ValueError):
                m.candidates(Client(), {}, value)


if __name__ == '__main__':
    unittest.main()
