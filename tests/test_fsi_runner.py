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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from benchmark_fsi_block_scaling import rank_placement, spool_fields, compare_spools


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
