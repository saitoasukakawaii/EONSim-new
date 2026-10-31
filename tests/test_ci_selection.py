"""Incremental CI selection/receipts: standard library only, no numerical builds."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/cloud'))
import selection as s
import receipt as r

POLICY = s.load_policy()
CONTEXT = dict(repository='owner/repo', pr=1, base='a'*40, head='b'*40,
               commit='c'*40, tree='d'*40, fingerprint='policy', run_id=20)


def receipt(names=('poisson_verification',)):
    return dict(schema=1, **{**CONTEXT, 'run_id': 10}, status='passed', covered=list(names),
                origins={n: {m: dict(run_id=10, commit='c'*40) for m in ('debug','release')} for n in names})


def summary(mode, names=('poisson_verification',)):
    return dict(status='passed', commit=CONTEXT['commit'], dirty=False, mode=mode,
                petsc='3.23.7', lock_sha256='lock', tests=[dict(name=n, status='passed',
                exit_code=0, timeout=False) for n in names])


class SelectionTests(unittest.TestCase):
    def test_docs_and_website_do_not_run_numerics(self):
        got=s.classify(['README.md','docs/development/CODEX_PROGRESS.md','website/package.json'],POLICY)
        self.assertEqual(got['tests'],[])
        self.assertEqual(got['python'],[])

    def test_ci_pipeline_uses_one_smoke_case_and_script_checks(self):
        got=s.classify(['scripts/cloud/validate.py','.github/workflows/core-numerics.yml'],POLICY)
        self.assertEqual(got['tests'],['poisson_verification'])
        self.assertEqual(got['python'],['tests/test_ci_selection.py','tests/test_cloud_evidence.py'])

    def test_scalar_does_not_run_unrelated_fsi(self):
        got=s.classify(['src/physics/scalar2d.cpp'],POLICY)['tests']
        self.assertEqual(set(got),{'element2d_oracles','scalar2d_space','scalar2d_time','scalar2d_failure'})

    def test_shared_fluid_kernel_includes_coupled_users(self):
        got=s.classify(['src/physics/fluid_element.cpp'],POLICY)['tests']
        self.assertTrue({'fluid_element_jacobian','domains_verification','fsi_element_jacobian','ale_time_verification'} <= set(got))
        self.assertNotIn('scalar2d_space',got)

    def test_cpp_and_python_test_files_select_all_registered_variants(self):
        self.assertEqual(s.classify(['tests/verify_pc_plan.cpp'],POLICY)['tests'],
                         ['pc_plan_mpi1','pc_plan_mpi2','pc_plan_mpi4'])
        self.assertEqual(s.classify(['tests/verify_fsi_time.py'],POLICY)['tests'],
                         ['fsi_alpha_verification','fsi_time_verification'])

    def test_unknown_never_falls_back_to_all(self):
        for path in ('src/physics/new_model.cpp','tests/verify_new.py','scripts/cloud/new_runner.py'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError,'Missing CI mapping'):
                s.classify([path],POLICY)

    def test_existing_production_paths_have_mappings(self):
        paths=subprocess.check_output(['git','ls-files','src','include','cases','cmake','scripts','tests','environments','.github'],cwd=ROOT,text=True).splitlines()
        s.classify(paths,POLICY)

    def test_declared_targets_and_ranks(self):
        self.assertEqual(s.targets_for(['poisson_verification'],POLICY['tests']),['eonsim'])
        self.assertEqual(s.targets_for(['pc_plan_mpi1','pc_plan_mpi2'],POLICY['tests']),['verify_pc_plan'])
        for entry in POLICY['tests'].values():
            self.assertTrue(entry['ranks'])
            self.assertTrue(set(entry['ranks']) <= {1,2,4})
            for target in entry['targets']:
                self.assertTrue(target=='eonsim' or (ROOT/'tests'/f'{target}.cpp').exists(),target)

    def test_exact_names_reject_empty_duplicate_and_unknown(self):
        for names in ([], ['poisson_verification']*2, ['poisson.*'], 'poisson_verification'):
            with self.subTest(names=names), self.assertRaises(ValueError):
                s.checked_names(names,POLICY['tests'])
        self.assertEqual(s.test_filter(['a','b']),['-R','^(a|b)$'])

    def test_inventory_drift_and_missing_selected_name(self):
        catalog={'a':{},'b':{}}
        self.assertEqual(s.validate_inventory([dict(name='a'),dict(name='b')],catalog,['b']),[dict(name='b')])
        for inventory in ([dict(name='a')], [dict(name='a'),dict(name='a')], [dict(name='a'),dict(name='c')]):
            with self.assertRaises(ValueError):s.validate_inventory(inventory,catalog,['a'])
        with self.assertRaises(ValueError):s.validate_inventory([dict(name='a'),dict(name='b')],catalog,['c'])

    def test_docs_followup_reuses_prior_coverage(self):
        plan=s.make_plan(CONTEXT,POLICY,['scripts/cloud/validate.py','README.md'],['README.md'],receipt())
        self.assertEqual(plan['tests'],[])
        self.assertEqual(plan['reused'],['poisson_verification'])
        self.assertEqual(plan['python'],[])
        self.assertEqual(plan['disposition'],'reused')

    def test_changed_relevant_code_is_retested(self):
        plan=s.make_plan(CONTEXT,POLICY,['src/physics/poisson.cpp'],['src/physics/poisson.cpp'],receipt())
        self.assertEqual(plan['tests'],['poisson_parallel','poisson_verification'])
        self.assertEqual(plan['reused'],[])

    def test_new_coverage_and_reverted_paths(self):
        plan=s.make_plan(CONTEXT,POLICY,['src/physics/poisson.cpp'],['README.md'],receipt())
        self.assertEqual(plan['tests'],['poisson_parallel'])
        self.assertEqual(plan['reused'],['poisson_verification'])
        # Reverting an earlier source edit can still affect an executed path.
        plan=s.make_plan(CONTEXT,POLICY,['README.md'],['src/physics/poisson.cpp'],receipt())
        self.assertEqual(plan['tests'],['poisson_parallel','poisson_verification'])

    def test_no_receipt_selects_pr_subset_not_all(self):
        plan=s.make_plan(CONTEXT,POLICY,['scripts/cloud/validate.py'])
        self.assertEqual(plan['tests'],['poisson_verification'])
        self.assertEqual(plan['reused'],[])

    def test_rename_classifies_deleted_and_added_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
            git('init','-q');git('config','user.name','CI');git('config','user.email','ci@example.invalid')
            (root/'old.cpp').write_text('unchanged\n');git('add','.');git('commit','-qm','before')
            before=git('rev-parse','HEAD')
            (root/'old.cpp').rename(root/'new.cpp');git('add','-A');git('commit','-qm','after')
            self.assertEqual(set(s.changed_paths(before,'HEAD',root)),{'old.cpp','new.cpp'})


class ReceiptTests(unittest.TestCase):
    def test_matching_receipt_is_reusable(self):
        self.assertTrue(s.reusable(receipt(),CONTEXT,POLICY['tests'],lambda *_:True))

    def test_receipt_mismatch_or_incomplete_evidence_is_not_reusable(self):
        mutations=[('base','e'*40),('pr',2),('repository','other/repo'),('fingerprint','old'),
                   ('status','failed'),('status','cancelled'),('schema',0),('head','bad'),
                   ('covered',['not-a-test']),('covered',['poisson_verification']*2),('origins',{})]
        for key,value in mutations:
            old=receipt();old[key]=value
            with self.subTest(key=key,value=value):
                self.assertFalse(s.reusable(old,CONTEXT,POLICY['tests'],lambda *_:True))
        self.assertFalse(s.reusable(receipt(),CONTEXT,POLICY['tests'],lambda *_:False))
        old=receipt();del old['origins']['poisson_verification']['release']
        self.assertFalse(s.reusable(old,CONTEXT,POLICY['tests'],lambda *_:True))

    def test_finish_requires_both_modes_and_exact_results(self):
        plan=s.make_plan(CONTEXT,POLICY,['scripts/cloud/validate.py'])
        result=r.finish(plan,{m:summary(m) for m in ('debug','release')},POLICY['tests'],'lock')
        self.assertEqual(result['executed'],['poisson_verification'])
        self.assertEqual(result['origins']['poisson_verification']['debug']['run_id'],20)
        for modes in ({}, {'debug':summary('debug')}):
            with self.assertRaises(ValueError):r.finish(plan,modes,POLICY['tests'],'lock')
        for field,value in [('status','failed'),('commit','f'*40),('dirty',True),('mode','wrong'),
                            ('petsc','3.19.6'),('lock_sha256','other'),('tests',[]),
                            ('tests',summary('debug')['tests']*2)]:
            modes={m:summary(m) for m in ('debug','release')};modes['debug'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                r.finish(plan,modes,POLICY['tests'],'lock')
        for field,value in [('status','skipped'),('status','failed'),('exit_code',1),('timeout',True)]:
            modes={m:summary(m) for m in ('debug','release')};modes['debug']['tests'][0][field]=value
            with self.assertRaises(ValueError):r.finish(plan,modes,POLICY['tests'],'lock')

    def test_reuse_preserves_original_provenance(self):
        plan=s.make_plan(CONTEXT,POLICY,['scripts/cloud/validate.py'],['README.md'],receipt())
        result=r.finish(plan,{},POLICY['tests'],'lock')
        self.assertEqual(result['executed'],[])
        self.assertEqual(result['origins'],receipt()['origins'])
        self.assertEqual(result['disposition'],'reused')
        with self.assertRaises(ValueError):r.finish(plan,{'debug':summary('debug')},POLICY['tests'],'lock')

    def test_doc_only_receipt_does_not_claim_numerical_pass(self):
        result=r.finish(s.make_plan(CONTEXT,POLICY,['README.md']),{},POLICY['tests'],'lock')
        self.assertEqual(result['covered'],[])
        self.assertEqual(result['disposition'],'not_required')

    def test_archive_is_read_without_extracting_paths(self):
        def archive(name):
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as z:z.writestr(name,json.dumps(receipt()))
            return stream.getvalue()
        self.assertEqual(r.read_archive(archive('receipt.json')),receipt())
        with self.assertRaises(ValueError):r.read_archive(archive('../receipt.json'))

    def test_cross_host_redirect_drops_token(self):
        req=urllib.request.Request('https://api.github.com/source',headers={'Authorization':'Bearer secret'})
        redirected=r.SafeRedirect().redirect_request(req,None,302,'',{},'https://storage.example/artifact')
        self.assertIsNone(redirected.get_header('Authorization'))

    def test_missing_or_expired_artifacts_do_not_reuse(self):
        run=dict(id=10,conclusion='success',pull_requests=[dict(number=1)],head_sha='b'*40)
        for artifacts in ([],[dict(name='incremental-receipt',expired=True,id=1)]):
            with patch.dict(os.environ,GH_TOKEN='fake'),patch.object(r,'api',side_effect=[{'workflow_runs':[run]},{'artifacts':artifacts}]):
                self.assertIsNone(r.find_previous(CONTEXT,POLICY['tests']))

    def test_successful_run_and_receipt_identity_are_checked(self):
        run=dict(id=10,conclusion='success',pull_requests=[dict(number=1)],head_sha='b'*40)
        artifact=dict(name='incremental-receipt',expired=False,id=1)
        for number in (10,11):
            prior=receipt();prior['run_id']=number
            with patch.dict(os.environ,GH_TOKEN='fake'),patch.object(r,'api',side_effect=[{'workflow_runs':[run]},{'artifacts':[artifact]},b'data']),patch.object(r,'read_archive',return_value=prior),patch.object(r.subprocess,'run') as ancestry:
                ancestry.return_value.returncode=0
                result=r.find_previous(CONTEXT,POLICY['tests'])
                self.assertEqual(result is not None,number==10)


if __name__=='__main__':
    unittest.main()
