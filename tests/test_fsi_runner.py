"""FSI tests retain the observed solver output when a child fails or times out."""
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from verify_fsi_inlet import Runner
from verify_fsi_coo import check_batch_injection
import verify_fsi_multigrid as multigrid
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from benchmark_fsi_block_scaling import rank_placement, spool_fields, compare_spools


class PressureSupremizerEvidenceTests(unittest.TestCase):
    def test_supremizer_only_adds_the_requested_option_to_the_strict_v_mode(self):
        for ports in (False, True):
            prefix = '-rcr_bulk_monolithic_mg_' if ports else '-monolithic_mg_'
            wrong = '-monolithic_mg_' if ports else '-rcr_bulk_monolithic_mg_'
            with self.subTest(ports=ports):
                options = multigrid.flags('mono_supremizer', ports)
                index = options.index(prefix + 'pressure_supremizers')
                self.assertEqual(options[index + 1], 'true')
                self.assertNotIn(wrong + 'pressure_supremizers', options)
                self.assertEqual(options[:index] + options[index + 2:], multigrid.flags('mono_optimized', ports))
                self.assertNotIn('-nonlinear_inexact_newton', options)
                combined = multigrid.flags('mono_all', ports)
                self.assertEqual(combined[combined.index(prefix + 'pressure_supremizers') + 1], 'true')
                self.assertEqual(combined[combined.index(prefix + 'cycle') + 1], 'k')

    @staticmethod
    def transfer(level=0):
        return dict(level=str(level), pressure_supremizer_modes='4' if level == 0 else '0',
                    pressure_paired_aggregates='3' if level == 0 else '0',
                    pressure_pair_min_singular='0.2' if level == 0 else '0',
                    pressure_pair_relative_change='1e-13' if level == 0 else '0')

    def test_each_setup_requires_actual_fine_level_pairs(self):
        hierarchy = [dict(pressure_supremizers='1')] * 2
        transfers = [self.transfer(), self.transfer(1)] * 2
        evidence = multigrid.pressure_supremizer_evidence(hierarchy, transfers)
        self.assertEqual(len(evidence['fine_level_records']), 2)
        invalid = (
            [],
            transfers[1:],
            [self.transfer(1)] * 4,
            [dict(self.transfer(), pressure_supremizer_modes='0')],
            [dict(self.transfer(), pressure_paired_aggregates='0')],
            [dict(self.transfer(), pressure_pair_min_singular='0')],
            [dict(self.transfer(), pressure_supremizer_modes='7')],
            [dict(self.transfer(), pressure_paired_aggregates='5')],
            [self.transfer(), dict(self.transfer(), level='1')],
        )
        for records in invalid:
            with self.subTest(records=records), self.assertRaises(ValueError):
                multigrid.pressure_supremizer_evidence(hierarchy, records)
        for setups in ([], [{}], [dict(pressure_supremizers='0')]):
            with self.subTest(setups=setups), self.assertRaises(ValueError):
                multigrid.pressure_supremizer_evidence(setups, [self.transfer()])

    def test_pair_audit_rejects_missing_nonfinite_or_changed_evidence(self):
        invalid = []
        for key in self.transfer():
            invalid.append({name: value for name, value in self.transfer().items() if name != key})
        for key in ('pressure_pair_min_singular', 'pressure_pair_relative_change'):
            for value in ('nan', 'inf', '-0.1'):
                invalid.append(dict(self.transfer(), **{key: value}))
        invalid.append(dict(self.transfer(), pressure_pair_relative_change='1.0001e-10'))
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                multigrid.pressure_supremizer_evidence([dict(pressure_supremizers='1')], [row])


class KCycleEvidenceTests(unittest.TestCase):
    def test_kcycle_and_rcr_prefix_keep_the_v_comparison_explicit(self):
        for ports in (False, True):
            prefix = '-rcr_bulk_monolithic_mg_' if ports else '-monolithic_mg_'
            wrong = '-monolithic_mg_' if ports else '-rcr_bulk_monolithic_mg_'
            for mode in ('mono_kcycle', 'mono_all'):
                with self.subTest(ports=ports, mode=mode):
                    options = multigrid.flags(mode, ports)
                    self.assertEqual(options[options.index(prefix + 'cycle') + 1], 'k')
                    self.assertNotIn(wrong + 'cycle', options)
                    for name in ('field_scaling', 'fsi_candidates', 'adaptive_patches', 'native_fp32'):
                        self.assertEqual(options[options.index(prefix + name) + 1], 'true')
            comparison = multigrid.flags('mono_optimized', ports)
            self.assertEqual(comparison[comparison.index(prefix + 'cycle') + 1], 'v')
            self.assertNotIn('kcycle', multigrid.features('mono_optimized'))
            strict = multigrid.flags('mono_kcycle', ports)
            self.assertNotIn('-nonlinear_inexact_newton', strict)
            self.assertIn('-nonlinear_inexact_newton', multigrid.flags('mono_all', ports))
            for option in ('-ksp_rtol', '-ksp_atol', '-ksp_norm_type'):
                self.assertEqual(strict[strict.index(option)+1], comparison[comparison.index(option)+1])

    @staticmethod
    def snapshot(generation=1, multiplier=1, path='root'):
        rows = [f'solver_report solver_generation={generation} linear_iterations=2']
        for rank in range(2):
            rows.append(f'monolithic_mg_stats rank={rank} path={path} levels=3 cycle=k '
                        f'applications={3*multiplier} level_matvecs={20*multiplier} '
                        f'zero_start_skips={8*multiplier} coarse_revisits={multiplier} '
                        f'coarse_solves={8*multiplier} coarse_iterations={8*multiplier} '
                        f'smoother_applications={12*multiplier} coarse_krylov_directions={4*multiplier} '
                        f'coarse_krylov_rank_drops=0 coarse_krylov_rejections=0 '
                        f'coarse_krylov_reductions={6*multiplier} coarse_krylov_max_residual_ratio=0.9')
        return '\n'.join(rows) + '\n'

    def test_kcycle_requires_actual_work_and_complete_rank_evidence(self):
        valid = self.snapshot()
        self.assertEqual(len(multigrid.kcycle_evidence(valid, [{'cycle': 'k'}], 2)['snapshots']), 2)
        invalid = (
            '',
            valid.splitlines()[0] + '\n',
            '\n'.join(valid.splitlines()[:-1]),
            valid + valid.splitlines()[1] + '\n',
            valid.replace(' coarse_krylov_directions=4', ''),
            valid.replace('coarse_krylov_directions=4', 'coarse_krylov_directions=0'),
            valid.replace('coarse_solves=8', 'coarse_solves=0'),
            valid.replace('level_matvecs=20', 'level_matvecs=0'),
            valid.replace('cycle=k', 'cycle=v'),
            valid.replace('coarse_krylov_max_residual_ratio=0.9', 'coarse_krylov_max_residual_ratio=nan'),
            valid.replace('coarse_krylov_max_residual_ratio=0.9', 'coarse_krylov_max_residual_ratio=1.0001'),
        )
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                multigrid.kcycle_evidence(text, [{'cycle': 'k'}], 2)
        with self.assertRaises(ValueError):
            multigrid.kcycle_evidence(valid, [{'cycle': 'v'}], 2)

    def test_cumulative_work_is_retained_by_generation_not_summed(self):
        # RCR response applies may exceed outer iterations. A new reusable
        # solver generation resets work, whereas numeric refreshes do not.
        log = (self.snapshot(1, 1, 'root/rcr_bulk') + self.snapshot(1, 3, 'root/rcr_bulk') +
               self.snapshot(2, 1, 'root/rcr_bulk'))
        result = multigrid.kcycle_evidence(log, [{'cycle': 'k'}], 2)
        self.assertEqual(len(result['snapshots']), 6)
        last = {(int(row['rank']), row['solver_generation']): int(row['coarse_krylov_directions'])
                for row in result['last_by_rank_path_generation']}
        self.assertEqual(last, {(0, 1): 12, (1, 1): 12, (0, 2): 4, (1, 2): 4})
        with self.assertRaises(ValueError):
            multigrid.kcycle_evidence(self.snapshot(1, 3) + self.snapshot(1, 1), [{'cycle': 'k'}], 2)

    @staticmethod
    def cases(values, mode='mono_kcycle'):
        return [dict(name=f'scaling-n{n}-r2', ranks=2,
                     runs=[dict(mode=mode, status='passed', dofs=n**3,
                                iterations_per_correction=value)])
                for n, value in zip(multigrid.SCALING_SUBDIVISIONS, values)]

    def test_finite_window_target_does_not_rewrite_physical_acceptance(self):
        met = multigrid.mesh_convergence_goal(self.cases((12, 10, 13)), ('mono_kcycle',))
        self.assertEqual(met['maximum_ratio'], 1.3)
        self.assertEqual(met['modes']['mono_kcycle']['status'], 'met')
        cases = self.cases((12, 10, 14))
        unmet = multigrid.mesh_convergence_goal(cases, ('mono_kcycle',))
        self.assertEqual(unmet['modes']['mono_kcycle']['status'], 'open')
        self.assertTrue(all(case['runs'][0]['status'] == 'passed' for case in cases))
        self.assertTrue(unmet['physical_acceptance_independent'])

    def test_incomplete_or_inexact_window_cannot_claim_strict_target(self):
        incomplete = multigrid.mesh_convergence_goal(self.cases((10, 10)), ('mono_kcycle',))
        self.assertEqual(incomplete['modes']['mono_kcycle']['status'], 'incomplete')
        inexact = multigrid.mesh_convergence_goal(self.cases((1, 1, 1), 'mono_all'), ('mono_all',))
        self.assertEqual(inexact['modes']['mono_all']['status'], 'not_applicable_inexact')


class ScalingEvidenceTests(unittest.TestCase):
    def test_real_node_count_requires_complete_unique_ranks(self):
        def row(rank, host):
            return (f'solver_rank_report rank={rank} host={host} owned=3 ghosts=1 '
                    'rss_bytes=100 peak_rss_bytes=120 linear_seconds=0.1\n')
        first, second = row(0, 'node-a'), row(1, 'node-b')
        self.assertEqual(rank_placement((first+second)*2, 2, 2, 2)['nodes'], 2)
        for text in (first+first, first, first+row(1, 'node-a')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                rank_placement(text, 2, 1, 2)
        with self.assertRaises(RuntimeError):
            rank_placement(first+second+first+row(1, 'node-c'), 2, 2)

    @staticmethod
    def fixture(directory, swap_owners=False, corrupt_ghost=False, duplicate_cell=False):
        directory.mkdir()
        output = directory/'solution.vtu'
        for domain in ('', '_solid'):
            for rank in (0, 1):
                ids = [11, 17, 23, 29] if rank == 0 else [29, 23, 17, 11]
                owns = {11: 0, 17: 1, 23: 0, 29: 1}
                if swap_owners:
                    owns = {node: 1-owner for node, owner in owns.items()}
                has_cell = rank == 0 or duplicate_cell
                tree = ET.Element('VTKFile')
                piece = ET.SubElement(tree, 'Piece', NumberOfPoints='4', NumberOfCells=str(int(has_cell)))
                point = ET.SubElement(piece, 'PointData')

                def array(parent, name, values, width=1):
                    item = ET.SubElement(parent, 'DataArray', Name=name, NumberOfComponents=str(width), format='ascii')
                    item.text = ' '.join(map(str, values))
                array(point, 'mesh_node_id', ids)
                array(point, 'owner', [owns[node] for node in ids])
                values = [node/100 for node in ids]
                if corrupt_ghost and rank == 1:
                    values[ids.index(11)] += .01
                array(point, 'pressure', values)
                array(point, 'velocity', [node/1000 + axis for node in ids for axis in range(3)], 3)
                points = ET.SubElement(piece, 'Points')
                array(points, 'coordinates', [node/100 + axis for node in ids for axis in range(3)], 3)
                cells, data = ET.SubElement(piece, 'Cells'), ET.SubElement(piece, 'CellData')
                array(cells, 'connectivity', list(range(4)) if has_cell else [])
                array(cells, 'offsets', [4] if has_cell else [])
                array(cells, 'types', [10] if has_cell else [])
                array(data, 'mesh_element_id', [2] if has_cell else [])
                array(data, 'physical_tag', [20 if domain else 10] if has_cell else [])
                ET.ElementTree(tree).write(directory/f'solution{domain}_rank{rank}.vtu')
        return output

    def test_disk_audit_is_independent_of_owners_and_rank_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            reference = self.fixture(work/'reference')
            candidate = self.fixture(work/'candidate', swap_owners=True)
            for path in (reference, candidate):
                checked = spool_fields(path, 2, path.parent/'fields.sqlite')
                self.assertEqual(checked['nodes'], 8)
                self.assertEqual(checked['ghost_max_difference'], 0)
            self.assertEqual(compare_spools(reference.parent/'fields.sqlite', candidate.parent/'fields.sqlite'), 0)
            with sqlite3.connect(candidate.parent/'fields.sqlite') as db:
                db.execute("UPDATE cells SET tag=99 WHERE domain='' ")
            with self.assertRaises(RuntimeError):
                compare_spools(reference.parent/'fields.sqlite', candidate.parent/'fields.sqlite')

    def test_disk_audit_rejects_ghost_corruption_and_duplicate_cells(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            corrupt = self.fixture(work/'corrupt', corrupt_ghost=True)
            with self.assertRaises(RuntimeError):
                spool_fields(corrupt, 2, corrupt.parent/'fields.sqlite')
            duplicate = self.fixture(work/'duplicate', duplicate_cell=True)
            with self.assertRaises(sqlite3.IntegrityError):
                spool_fields(duplicate, 2, duplicate.parent/'fields.sqlite')


class BatchInjectionLogTests(unittest.TestCase):
    marker = 'fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1'

    def test_valid_injection_modes(self):
        for mode in ('worker', 'insert', 'worker_fatal', 'insert_fatal'):
            with self.subTest(mode=mode):
                thread = 1 if mode.startswith('worker') else 0
                record = f'fsi_batch_failure mode={mode} thread={thread} team=2 batch=1\n'
                self.assertEqual(check_batch_injection(record, mode)['thread'], str(thread))

    def test_mpi_interleaved_error_prefix(self):
        # Exact interleaving from the preserved CI worker_fatal log: rank one's
        # partial error prefix reached the launcher before rank zero's marker.
        text = ('EONSim rank fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1\n'
                'EONSim rank 1: callback phase=jacobian origin_rank=0: Injected fatal FSI batch failure\n'
                'status=failed\n'
                '0: callback phase=jacobian origin_rank=0: Injected fatal FSI batch failure\n'
                'status=failed\n\x00')
        self.assertEqual(check_batch_injection(text, 'worker_fatal'),
                         dict(mode='worker_fatal', thread='1', team='2', batch='1'))

    def test_duplicate_markers_are_not_hidden(self):
        for text in (self.marker+'\n'+self.marker, self.marker+' '+self.marker,
                     self.marker+'\nfsi_batch_failure mode=worker_fatal'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')

    def test_missing_or_malformed_records(self):
        for text in ('', self.marker.replace(' thread=1', ''),
                     self.marker.replace(' batch=1', ''),
                     self.marker.replace('team=2', 'team=NaN'),
                     self.marker.replace('batch=1', 'batch=1.5'),
                     self.marker+' batch=0', self.marker+' thread=0',
                     self.marker+' batch=1', self.marker+' thread=1'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')

    def test_wrong_team_or_thread(self):
        for text, mode in ((self.marker.replace('team=2', 'team=1'), 'worker_fatal'),
                           (self.marker.replace('thread=1', 'thread=0'), 'worker_fatal'),
                           (self.marker.replace('thread=1', 'thread=2'), 'worker_fatal'),
                           (self.marker.replace('worker_fatal', 'insert_fatal'), 'insert_fatal')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, mode)

    def test_wrong_mode_or_batch(self):
        for text in (self.marker.replace('worker_fatal', 'worker'),
                     self.marker.replace('batch=1', 'batch=0')):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                check_batch_injection(text, 'worker_fatal')


class RunnerLogTests(unittest.TestCase):
    def test_output_and_expected_failure(self):
        with tempfile.TemporaryDirectory() as path:
            work = Path(path)
            runner = Runner(sys.executable, None, work)
            out = runner.command([sys.executable, '-c', "print('accepted')"], 'accepted')
            self.assertEqual(out, 'accepted\n')
            self.assertEqual((work/'accepted.log').read_text(), out)
            command = [sys.executable, '-c', "import sys; sys.exit('known failure')"]
            self.assertIn('known failure', runner.command(command, 'rejected', fail='known failure'))

    def test_timeout_keeps_partial_output(self):
        with tempfile.TemporaryDirectory() as path:
            work = Path(path)
            runner = Runner(sys.executable, None, work, timeout=1)
            command = [sys.executable, '-c', "import time; print('step 1', flush=True); time.sleep(30)"]
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                runner.command(command, 'interrupted')
            self.assertEqual((work/'interrupted.log').read_bytes(), b'step 1\n')
            self.assertEqual(caught.exception.output, b'step 1\n')


if __name__ == '__main__':
    unittest.main()
