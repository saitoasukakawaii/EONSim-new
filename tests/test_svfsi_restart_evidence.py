"""Independent native-record and segmented-log acceptance/rejection examples."""
import json
from pathlib import Path
import struct
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_svfsi_convergence import analyze, PIN
from svfsi_restart_evidence import analyze_chain, native_checkpoint, sha


class RestartEvidence(unittest.TestCase):
    @staticmethod
    def parallel_bytes():
        # Unequal local node counts, fixed maximum RECL, non-state padding.
        records = []
        for nodes in (2, 1):
            state = [.2, 19.+nodes, 1e-8, 2e-8]+[.003]*(21*nodes)
            records.append(struct.pack('<8i'+str(len(state))+'d', 2, 2, 2, nodes, 0, 7, 1, 2, *state))
        return records[0]+records[1]+bytes([0xFF])*(len(records[0])-len(records[1]))

    @staticmethod
    def rows(step, ratio='2e-12'):
        return ''.join(f' {name} {step}-1 0.1 [ -200 {ratio} 3e-12 1e-12]\n'
                       for name in ('FS', 'MS'))

    def fixture(self, root):
        original, resumed = root/'original', root/'resumed'
        for work in (original, resumed):
            (work/'results').mkdir(parents=True)
            (work/'source-case.json').write_text(json.dumps({'fsi':{'steps':4, 'dt':.1}}))
            (work/'pressure.txt').write_text('fixed pressure history\n')
        # Two global nodes,2 equation norms and all3*7*2 state values.
        state = [.2, 19., 1e-8, 2e-8]+[.003]*42
        saved = original/'results/stFile_2.bin'
        saved.write_bytes(struct.pack('<8i46d', 1, 2, 2, 2, 0, 7, 1, 2, *state))
        (original/'results/result_2.vtu').write_bytes(b'original immutable endpoint')
        (resumed/'restart-seed.bin').write_bytes(saved.read_bytes())
        base = ('Number of time steps: 4\nTime step size: 0.1\n'
                'Continue previous simulation: 0\nSave results in folder: results\n'
                'Increment in saving restart files: 100\n')
        for name in ('FSI', 'mesh'):
            base += f'Add equation: {name} {{\n  Min iterations: 1\n  Max iterations: 2\n  Tolerance: 1e-10\n}}\n'
        for work in (original, resumed):
            text = base
            if work == resumed:
                text = text.replace('Continue previous simulation: 0',
                    'Continue previous simulation: 1\nSimulation initialization file path: restart-seed.bin')
            (work/'svFSI.inp').write_text(text)
            manifest = dict(svfsi_commit=PIN, mode='linear elastic pressure tube', files={
                name:sha(work/name) for name in ('svFSI.inp', 'source-case.json', 'pressure.txt')})
            if work == resumed:
                manifest['files']['restart-seed.bin'] = sha(work/'restart-seed.bin')
                manifest['restart_provenance'] = dict(native_checkpoint(work/'restart-seed.bin'),
                    layout='svFSI-7bdb74c-serial-linear-fsi-i32-f64')
            (work/'export.json').write_text(json.dumps(manifest))
        # Step3 is a real but incomplete failed tail, deliberately outside the
        # selected original prefix. It must remain visible, never called passed.
        (original/'solve.log').write_text(self.rows(1)+self.rows(2)+
            ' FS 3-1 0.1 [ 0 1.0 1.0 1e-12]\n')
        (resumed/'solve.log').write_text('Initializing from restart-seed.bin\n'+self.rows(3)+self.rows(4))
        chain = dict(schema='svfsi-native-restart-chain-v1', final_step=4, target_work='resumed',
            segments=[dict(work='original', log='original/solve.log', first_step=1, last_step=2),
                      dict(work='resumed', log='resumed/solve.log', first_step=3, last_step=4)])
        path = root/'chain.json'
        path.write_text(json.dumps(chain))
        return path, original, resumed

    @staticmethod
    def rehash(work, name):
        path = work/'export.json'
        data = json.loads(path.read_text())
        data['files'][name] = sha(work/name)
        path.write_text(json.dumps(data))

    def test_contiguous_chain_keeps_failed_tail_and_exact_native_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, original, resumed = self.fixture(Path(tmp))
            result = analyze_chain(path, expected_work=resumed, expected_steps=4)
            self.assertTrue(result['passed'])
            self.assertTrue(result['full_source_study'])
            self.assertEqual(result['final_equation_rows'], 8)
            self.assertEqual(result['iteration_rows'], 8)
            self.assertEqual(result['input_manifest_sha256'], sha(resumed/'export.json'))
            self.assertEqual(result['maximum_final_relative_ratio'], {'FS':2e-12, 'MS':2e-12})
            self.assertEqual(result['segments'][0]['excluded_tail']['final_equation_rows'], 1)
            self.assertEqual(result['segments'][0]['excluded_tail']['last_observed_step'], 3)
            self.assertEqual(result['segments'][1]['restart']['time'], .2)
            self.assertEqual(result['boundaries'][0]['output_sha256'], sha(original/'results/result_2.vtu'))
            with self.assertRaisesRegex(ValueError, 'Missing or unexpected'):
                analyze(original, original/'solve.log')

    def test_native_midnight_elapsed_is_diagnostic_for_every_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,original,resumed=self.fixture(Path(tmp))
            serial=original/'results/stFile_2.bin'
            before=native_checkpoint(serial)
            raw=bytearray(serial.read_bytes());struct.pack_into('<d',raw,40,-86381.)
            serial.write_bytes(raw);after=native_checkpoint(serial)
            self.assertEqual({k:v for k,v in before.items() if k!='sha256'},
                             {k:v for k,v in after.items() if k!='sha256'})
            parallel=Path(tmp)/'parallel.bin';raw=bytearray(self.parallel_bytes())
            record_bytes=len(raw)//2
            for rank in range(2):struct.pack_into('<d',raw,rank*record_bytes+40,-86380.+rank)
            parallel.write_bytes(raw);record=native_checkpoint(parallel)
            self.assertEqual(record['time'],.2);self.assertEqual(len(record['rank_records']),2)

    def test_midnight_native_record_keeps_physical_time_norm_and_finiteness_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'parallel.bin';original=self.parallel_bytes();record_bytes=len(original)//2
            for rank in range(2):
                for offset,value in [(32,-.2),(48,-1e-8),(56,-2e-8),(40,float('nan')),
                                     (40,float('inf')),(64,float('nan'))]:
                    with self.subTest(rank=rank,offset=offset,value=value):
                        raw=bytearray(original);struct.pack_into('<d',raw,rank*record_bytes+40,-86380.)
                        struct.pack_into('<d',raw,rank*record_bytes+offset,value);path.write_bytes(raw)
                        with self.assertRaisesRegex(ValueError,'Invalid native'):
                            native_checkpoint(path)

    def test_native_chain_with_midnight_wrap_keeps_exact_seed_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,original,resumed=self.fixture(Path(tmp))
            saved=original/'results/stFile_2.bin';raw=bytearray(saved.read_bytes())
            struct.pack_into('<d',raw,40,-86381.);saved.write_bytes(raw)
            seed=resumed/'restart-seed.bin';seed.write_bytes(raw)
            manifest=json.loads((resumed/'export.json').read_text())
            manifest['files']['restart-seed.bin']=sha(seed)
            manifest['restart_provenance']=dict(native_checkpoint(seed),layout='svFSI-7bdb74c-serial-linear-fsi-i32-f64')
            (resumed/'export.json').write_text(json.dumps(manifest))
            log=resumed/'solve.log';log.write_text(log.read_text().replace(' 0.1 [',' -86380.1 ['))
            result=analyze_chain(path,expected_work=resumed,expected_steps=4)
            self.assertTrue(result['passed']);self.assertEqual(result['segments'][1]['restart']['time'],.2)
            self.assertEqual(result['boundaries'][0]['checkpoint_sha256'],sha(seed))
            struct.pack_into('<d',raw,40,-86380.);seed.write_bytes(raw)
            self.rehash(resumed,'restart-seed.bin')
            with self.assertRaisesRegex(ValueError,'differs from provenance'):
                analyze_chain(path)

    def test_resumed_rows_need_explicit_initialized_seed_and_complete_convergence(self):
        for mutation in ('missing_banner', 'missing_seed', 'missing_row', 'cap_only', 'duplicate', 'nan'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path, _, resumed = self.fixture(Path(tmp))
                log = resumed/'solve.log'
                text = log.read_text()
                if mutation == 'missing_banner':
                    text = text.replace('Initializing from restart-seed.bin\n', '')
                elif mutation == 'missing_seed':
                    manifest = json.loads((resumed/'export.json').read_text())
                    del manifest['restart_provenance']
                    (resumed/'export.json').write_text(json.dumps(manifest))
                elif mutation == 'missing_row':
                    text = text.replace(self.rows(4), '')
                elif mutation == 'cap_only':
                    text = text.replace(self.rows(4), self.rows(4, '1.0').replace('3e-12', '1.0')+
                        self.rows(4, '1.0').replace('4-1', '4-2').replace('3e-12', '1.0'))
                elif mutation == 'duplicate':
                    text += self.rows(4)
                else:
                    text = text.replace('2e-12', 'nan')
                log.write_text(text)
                if mutation == 'cap_only':
                    self.assertFalse(analyze_chain(path)['passed'])
                else:
                    with self.assertRaises(ValueError):
                        analyze_chain(path)

    def test_chain_rejects_gap_overlap_wrong_target_and_incomplete_final_range(self):
        for mutation in ('gap', 'overlap', 'target', 'final'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path, _, resumed = self.fixture(Path(tmp))
                chain = json.loads(path.read_text())
                if mutation == 'gap':chain['segments'][1]['first_step'] = 4
                elif mutation == 'overlap':chain['segments'][1]['first_step'] = 2
                elif mutation == 'target':chain['target_work'] = 'original'
                else:chain['segments'][1]['last_step'] = 3
                path.write_text(json.dumps(chain))
                with self.assertRaises(ValueError):
                    analyze_chain(path, expected_work=resumed, expected_steps=4)

    def test_input_changes_cannot_be_hidden_by_rehashing_manifest(self):
        for name in ('pressure.txt', 'svFSI.inp', 'source-case.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path, _, resumed = self.fixture(Path(tmp))
                p = resumed/name
                if name == 'svFSI.inp':text = p.read_text().replace('1e-10', '1e-9')
                elif name == 'source-case.json':text = p.read_text().replace('0.1', '0.2')
                else:text = 'different pressure history\n'
                p.write_text(text)
                self.rehash(resumed, name)
                with self.assertRaisesRegex(ValueError, 'differ across restart'):
                    analyze_chain(path)

    def test_seed_must_match_previous_checkpoint_even_if_manifest_is_self_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _, resumed = self.fixture(Path(tmp))
            p = resumed/'restart-seed.bin'
            data = bytearray(p.read_bytes())
            data[-8:] = struct.pack('<d', .004)
            p.write_bytes(data)
            manifest = json.loads((resumed/'export.json').read_text())
            manifest['files'][p.name] = sha(p)
            manifest['restart_provenance'].update(native_checkpoint(p))
            (resumed/'export.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'preceding segment checkpoint'):
                analyze_chain(path)

    def test_native_record_rejects_bad_layout_truncation_nonfinite_and_wrong_time(self):
        for mutation in ('truncated', 'stamp', 'nan', 'time'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path, _, resumed = self.fixture(Path(tmp))
                p = resumed/'restart-seed.bin'
                data = bytearray(p.read_bytes())
                if mutation == 'truncated':data = data[:-8]
                elif mutation == 'stamp':data[:4] = struct.pack('<i', 2)
                elif mutation == 'nan':data[-8:] = struct.pack('<d', float('nan'))
                else:data[32:40] = struct.pack('<d', 1.2)
                p.write_bytes(data)
                self.rehash(resumed, p.name)
                with self.assertRaises(ValueError):
                    analyze_chain(path)

    def test_two_rank_records_preserve_unequal_counts_and_ignore_only_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'parallel.bin'; path.write_bytes(self.parallel_bytes())
            result = native_checkpoint(path)
            self.assertEqual(result['step'], 2)
            self.assertEqual(result['time'], .2)
            self.assertEqual(result['record_bytes'], 400)
            self.assertEqual(result['serialized_values'], 46+25)
            self.assertEqual([row['stamp'][3] for row in result['rank_records']], [2, 1])
            self.assertEqual([row['payload_bytes'] for row in result['rank_records']], [400, 232])

    def test_two_rank_records_reject_corruption_and_rank_disagreement(self):
        for mutation in ('truncated', 'extra_padding', 'rank_count', 'nodes', 'step', 'time', 'norm', 'history'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'parallel.bin'; data = bytearray(self.parallel_bytes()); offset = 400
                if mutation == 'truncated':data = data[:-8]
                elif mutation == 'extra_padding':data += bytes(8)
                elif mutation == 'rank_count':struct.pack_into('<i', data, offset, 1)
                elif mutation == 'nodes':struct.pack_into('<i', data, offset+12, 3)
                elif mutation == 'step':struct.pack_into('<i', data, offset+28, 3)
                elif mutation == 'time':struct.pack_into('<d', data, offset+32, .3)
                elif mutation == 'norm':struct.pack_into('<d', data, offset+48, 9e-8)
                else:struct.pack_into('<d', data, offset+224, float('nan'))
                path.write_bytes(data)
                with self.assertRaises(ValueError):native_checkpoint(path)

    def test_two_rank_chain_requires_explicit_complete_parallel_provenance(self):
        for mutation in ('none', 'serial_layout', 'missing_rank_records', 'wrong_record_size'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path, original, resumed = self.fixture(Path(tmp))
                (original/'results/stFile_2.bin').write_bytes(self.parallel_bytes())
                seed = resumed/'restart-seed.bin'; seed.write_bytes(self.parallel_bytes())
                manifest = json.loads((resumed/'export.json').read_text())
                manifest['files'][seed.name] = sha(seed)
                provenance = dict(native_checkpoint(seed), layout='svFSI-7bdb74c-two-rank-linear-fsi-i32-f64')
                if mutation == 'serial_layout':provenance['layout'] = 'svFSI-7bdb74c-serial-linear-fsi-i32-f64'
                elif mutation == 'missing_rank_records':del provenance['rank_records']
                elif mutation == 'wrong_record_size':provenance['record_bytes'] += 8
                manifest['restart_provenance'] = provenance
                (resumed/'export.json').write_text(json.dumps(manifest))
                if mutation == 'none':
                    result = analyze_chain(path, expected_work=resumed, expected_steps=4)
                    self.assertTrue(result['passed'])
                    self.assertEqual(len(result['segments'][1]['restart']['rank_records']), 2)
                else:
                    with self.assertRaises(ValueError):analyze_chain(path)


class ReviewedBackendEvidence(unittest.TestCase):
    """Contract fixtures model review provenance; they are not numerical proofs."""
    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data))

    def fixture(self, root):
        path, original, resumed = RestartEvidence().fixture(root)
        cfg = {'fsi': {'steps': 104, 'dt': .1}}
        for directory in (original, resumed):
            self.write(directory/'source-case.json', cfg)
            inp = (directory/'svFSI.inp').read_text().replace('steps: 4', 'steps: 104')
            inp = inp.replace('  Min iterations: 1', '    Preconditioner: FSILS\n  Min iterations: 1')
            inp = inp.replace('Add equation: FSI', 'Start saving after time step: 1\nAdd equation: FSI')
            if directory == resumed:
                inp = inp.replace('Preconditioner: FSILS', 'Preconditioner: Trilinos-ILUT\n    Use Trilinos for assembly: 0', 1)
            (directory/'svFSI.inp').write_text(inp)
            for name in ('svFSI.inp', 'source-case.json'):
                RestartEvidence.rehash(directory, name)
        (resumed/'solve.log').write_text('Initializing from restart-seed.bin\n'+''.join(RestartEvidence.rows(i) for i in range(3,105)))
        screen, review = root/'screen', root/'review'
        screen.mkdir(); review.mkdir()
        for directory in (screen, review):
            (directory/'source').mkdir()
            (directory/'source/analyzer.py').write_text('frozen analysis fixture\n')
            (directory/'controller.py').write_text('frozen controller fixture\n')
        self.write(screen/'case.json', cfg)
        for name in ('geometry.json', 'fluid.msh', 'solid.msh', 'scales.json'):
            (screen/name).write_text('immutable '+name+'\n')
        def native(step):
            values = [step*.1, 19., 1e-8, 2e-8]+[.003]*42
            return struct.pack('<8i46d', 1, 2, 2, 2, 0, 7, 1, step, *values)
        evidence = {}
        for label, begin in (('old', 3), ('ilut', 3), ('replay', 93)):
            directory = screen/label; directory.mkdir(); (directory/'results').mkdir()
            source = original if label == 'old' else resumed
            inp = (source/'svFSI.inp').read_text().replace('steps: 104', 'steps: 102')
            inp = inp.replace('Start saving after time step: 1', f'Start saving after time step: {begin}')
            if label == 'old':
                inp = inp.replace('Continue previous simulation: 0', 'Continue previous simulation: 1\nSimulation initialization file path: restart-seed.bin')
            (directory/'svFSI.inp').write_text(inp)
            for name in ('source-case.json', 'pressure.txt'):
                shutil.copy2(source/name, directory/name)
            seed = directory/'restart-seed.bin'; seed.write_bytes(native(begin-1))
            manifest = dict(svfsi_commit=PIN, mode='linear elastic pressure tube', files={
                name: sha(directory/name) for name in ('svFSI.inp','source-case.json','pressure.txt','restart-seed.bin')},
                restart_provenance=dict(native_checkpoint(seed), layout='svFSI-7bdb74c-serial-linear-fsi-i32-f64'))
            self.write(directory/'export.json', manifest)
            log = screen/(label+'.log'); log.write_text('Initializing from restart-seed.bin\n'+''.join(RestartEvidence.rows(i) for i in range(begin,103)))
            for step in range(begin,103):
                (directory/'results'/f'stFile_{step}.bin').write_bytes(native(step))
                (directory/'results'/f'result_{step}.vtu').write_text(f'reviewed field fixture {step}\n')
            for p in [*directory.rglob('*'), log]:
                if p.is_file(): evidence[str(p)] = sha(p)
        definition = dict(controller_sha256=sha(screen/'controller.py'), source_hashes={'analyzer.py':sha(screen/'source/analyzer.py')},
            binary_hashes={'old':'a'*64, 'ilut':'b'*64}, ranks=1, first_step=3, last_step=102,
            seeds={'2':native_checkpoint(original/'results/stFile_2.bin')})
        self.write(screen/'definition.json', definition)
        self.write(review/'static-input-check.json', dict(passed=True, screen_definition_sha256=sha(screen/'definition.json'),
            matched_original_files={name:sha(screen/name) for name in ('case.json','geometry.json','fluid.msh','solid.msh')},
            scales_sha256=sha(screen/'scales.json')))
        metric = dict(maximum_absolute_nodal=0.,maximum_normalized_mass_rms=0.,maximum_native_history_difference=0.,
            maximum_saved_equation_norm_difference=0.,exact_native_time=True)
        comparisons = {name:dict(metric, passed=True, states=states,bitwise_algorithm_except_elapsed_and_padding=True)
            for name,states in [('backend',100),('candidate-replay',10)]}
        receipt = dict(returncode=0,remaining_scope_members=[],scope_seen=True,memory_events='low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n',
            memory_max_bytes=2*1024**3,memory_swap_max_bytes=0,wall_seconds=100.)
        report = dict(passed=True,eligible=True,binary_hashes=definition['binary_hashes'],comparisons=comparisons,
            original_restoration=dict(metric,bitwise_algorithm_except_elapsed_and_padding=True),
            resources={name:dict(receipt,wall_seconds=seconds) for name,seconds in [('old',100.),('ilut',80.),('replay',8.)]},cost_ratio=.8)
        self.write(screen/'report.json', report); self.write(review/'review.resource.json', receipt)
        checked = dict(passed=True,bounded_eligible=True,original_restoration_exact=True,screen_report_sha256=sha(screen/'report.json'),
            controller_sha256=sha(review/'controller.py'),source_hashes=definition['source_hashes'],binary_hashes=definition['binary_hashes'],
            pairs={name:dict(metric,states=states,bitwise_algorithm_except_elapsed_and_nonstate_padding=True)
                   for name,states in [('backend',100),('candidate-replay',10)]},cost_ratio=.8,evidence_hashes=evidence)
        self.write(review/'review.json', checked)
        chain = json.loads(path.read_text()); chain.update(schema='svfsi-native-restart-chain-v2',final_step=104)
        chain['segments'][0]['binary_sha256']='a'*64
        chain['segments'][1].update(last_step=104,binary_sha256='b'*64,execution_transition=dict(kind='svfsi-fsi-ilut-reviewed-v1',
            screen='screen',review='review',screen_report_sha256=sha(screen/'report.json'),review_sha256=sha(review/'review.json')))
        self.write(path, chain)
        return path, original, resumed, screen, review

    def test_reviewed_transition_preserves_full_chain_and_failed_original_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _, resumed, _, _ = self.fixture(Path(tmp))
            report = analyze_chain(path, expected_work=resumed, expected_steps=104)
            self.assertTrue(report['passed']); self.assertTrue(report['full_source_study'])
            self.assertEqual(report['final_equation_rows'], 208)
            self.assertEqual(report['segments'][0]['excluded_tail']['final_equation_rows'], 1)
            self.assertEqual(report['execution_transitions'][0]['step'], 2)
            self.assertEqual(report['execution_transitions'][0]['cost_ratio'], .8)

    def test_unreviewed_binary_or_implicit_v1_transition_is_rejected(self):
        for change in ('v1', 'no_proof', 'wrong_binary', 'missing_binary'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                path, _, _, _, _ = self.fixture(Path(tmp)); chain=json.loads(path.read_text())
                if change=='v1':chain['schema']='svfsi-native-restart-chain-v1'
                elif change=='no_proof':del chain['segments'][1]['execution_transition']
                elif change=='wrong_binary':chain['segments'][1]['binary_sha256']='c'*64
                else:del chain['segments'][0]['binary_sha256']
                self.write(path,chain)
                with self.assertRaises(ValueError):analyze_chain(path)

    def test_review_cannot_authorize_other_physics_mesh_backend_or_output_grid(self):
        for before,after in [('Time step size: 0.1','Time step size: 0.2'),('Tolerance: 1e-10','Tolerance: 1e-9'),
                ('Preconditioner: FSILS','Preconditioner: Trilinos-IC'),('Start saving after time step: 1','Start saving after time step: 2')]:
            with self.subTest(change=after), tempfile.TemporaryDirectory() as tmp:
                path, _, resumed, _, _ = self.fixture(Path(tmp)); p=resumed/'svFSI.inp'
                p.write_text(p.read_text().replace(before,after)); RestartEvidence.rehash(resumed,p.name)
                with self.assertRaises(ValueError):analyze_chain(path)

    def test_rehashed_review_cannot_hide_missing_states_failed_replay_or_dirty_resources(self):
        for change in ('missing_state','field','replay','oom','source','rank','log'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                path, _, _, screen, review = self.fixture(Path(tmp))
                checked=json.loads((review/'review.json').read_text())
                if change=='missing_state':del checked['evidence_hashes'][str(screen/'old/results/stFile_51.bin')]
                elif change=='field':(screen/'ilut/results/result_61.vtu').write_text('different field')
                elif change=='replay':checked['pairs']['candidate-replay']['bitwise_algorithm_except_elapsed_and_nonstate_padding']=False
                elif change=='oom':
                    receipt=json.loads((review/'review.resource.json').read_text());receipt['memory_events']='oom_kill 1\n'
                    self.write(review/'review.resource.json',receipt)
                elif change=='source':(review/'source/analyzer.py').write_text('different analyzer')
                elif change=='rank':
                    d=json.loads((screen/'definition.json').read_text());d['ranks']=2;self.write(screen/'definition.json',d)
                    s=json.loads((review/'static-input-check.json').read_text());s['screen_definition_sha256']=sha(screen/'definition.json');self.write(review/'static-input-check.json',s)
                else:
                    log=screen/'ilut.log';log.write_text(log.read_text().replace(RestartEvidence.rows(50),RestartEvidence.rows(50,'1.0').replace('3e-12','1.0')))
                    checked['evidence_hashes'][str(log)]=sha(log)
                self.write(review/'review.json',checked)
                chain=json.loads(path.read_text());chain['segments'][1]['execution_transition']['review_sha256']=sha(review/'review.json');self.write(path,chain)
                with self.assertRaises(ValueError):analyze_chain(path)


if __name__ == '__main__':
    unittest.main()
