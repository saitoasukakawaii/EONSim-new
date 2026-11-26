"""Validate archived profiling evidence and reject corrupted measurements; no MPI needed."""
import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from profile_multistep_setup import parse as multistep
from profile_schur_mesh import parse as steady
from benchmark_fsi_assembly import (TIMERS, JACOBIAN_COUNTERS, SOLVERS, check_execution,
                                   check_partition_unchanged, execution_options, expected_solvers,
                                   parse_log, partition_evidence, partition_preparations,
                                   partition_weights, solver_options)
from verify_hdf5_outputs import cell_records, grid_bindings, snapshot_grids

DATA = ROOT / 'docs/research/data'


def replace_field(text, key, value):
    return re.sub(r'\b' + key + r'=\S+', lambda _: key + '=' + value, text, count=1)


class ProfileValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transient = (DATA / 'transient-assembly-2026-10-30/fluid-r1-n0.log').read_text()
        cls.steady = (DATA / 'assembly-phase-2026-10-30/n2-r2-schur0.log').read_text()

    def test_archived_transient(self):
        for case, marker in [('fluid', 'fluid_step'), ('elastic', 'fsi_step')]:
            for ranks in (1, 2, 4):
                for repeat in range(3):
                    with self.subTest(case=case, ranks=ranks, repeat=repeat):
                        text = (DATA / f'transient-assembly-2026-10-30/{case}-r{ranks}-n{repeat}.log').read_text()
                        self.assertEqual(len(multistep(text, marker)), 10)

    def test_archived_overhead(self):
        logs = sorted((DATA / 'fluid-element-overhead-2026-10-30').glob('r*-n*-on*.log'))
        self.assertEqual(len(logs), 36)
        for log in logs:
            with self.subTest(log=log.name):
                self.assertEqual(len(multistep(log.read_text(), 'fluid_step')), 10)

    def test_zero_iterations_remain_valid(self):
        text = replace_field(self.transient, 'linear_iterations', '0')
        text = replace_field(text, 'snes_iterations', '0')
        self.assertEqual(multistep(text, 'fluid_step')[0]['linear_iterations'], 0)

    def test_archived_steady(self):
        for n in (2, 4, 6):
            for ranks in (1, 2):
                for repeat in range(3):
                    with self.subTest(n=n, ranks=ranks, repeat=repeat):
                        text = (DATA / f'assembly-phase-2026-10-30/n{n}-r{ranks}-schur{repeat}.log').read_text()
                        self.assertTrue(steady(text, ranks)[1])

    def test_transient_invalid_numbers(self):
        for key in ('snes_reason', 'ksp_reason', 'linear_iterations', 'snes_iterations'):
            for value in ('nan', 'inf', '-1', '1.5'):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    multistep(replace_field(self.transient, key, value), 'fluid_step')
        for key, value in [('snes_reason', '0'), ('ksp_reason', '0'), ('domain_rejections', '1'),
                           ('solve_seconds', 'nan'), ('solve_seconds', '-1'),
                           ('residual', 'inf'), ('residual', '-1'), ('callback_seconds', '100')]:
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                multistep(replace_field(self.transient, key, value), 'fluid_step')

    def test_transient_missing_field(self):
        text = re.sub(r'\blinear_iterations=\S+ ', '', self.transient, count=1)
        with self.assertRaises(RuntimeError):
            multistep(text, 'fluid_step')

    def test_transient_pairing(self):
        lines = self.transient.splitlines()
        report = next(i for i, line in enumerate(lines) if line.startswith('solver_report '))
        step = next(i for i, line in enumerate(lines) if line.startswith('fluid_step='))
        lines[report], lines[step] = lines[step], lines[report]
        with self.assertRaises(RuntimeError):
            multistep('\n'.join(lines), 'fluid_step')
        with self.assertRaises(RuntimeError):
            multistep(replace_field(self.transient, 'fluid_step', '2'), 'fluid_step')
        with self.assertRaises(RuntimeError):
            multistep('\n'.join(line for line in self.transient.splitlines() if not line.startswith('fluid_step=10 ')), 'fluid_step')

    def test_steady_missing_or_duplicate_root(self):
        root = next(line for line in self.steady.splitlines() if line.startswith('solver_node rank=1 path=root '))
        for text in (self.steady.replace(root, ''), self.steady + '\n' + root):
            with self.subTest(text_length=len(text)), self.assertRaises(RuntimeError):
                steady(text, 2)

    def test_steady_rank_mismatch(self):
        with self.assertRaises(RuntimeError):
            steady(replace_field(self.steady, 'ranks', '1'), 2)

    def test_steady_missing_metric(self):
        with self.assertRaises(RuntimeError):
            steady(re.sub(r'\bsolve_seconds=\S+ ', '', self.steady, count=1), 2)

    def test_steady_invalid_numbers(self):
        for key in ('snes_reason', 'ksp_reason', 'linear_iterations'):
            for value in ('nan', 'inf', '-1', '1.5'):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    steady(replace_field(self.steady, key, value), 2)


def assembly_log(solver='direct', ranks=2, counters=True, reuse=True):
    """Independent complete two-step evidence; corruptions target the verifier."""
    lines = []
    def emit(marker, row):
        lines.append(marker+' '+' '.join(f'{key}={value}' for key, value in row.items()))
    for step in (1, 2):
        emit('linear_residual', dict(solve=1, norm=1e-13, rhs_norm=1))
        for name in ('velocity', 'pressure', 'mesh', 'structure'):
            emit('field_residual', dict(name=name, accepted=1, rms=1e-13, limit=1e-10))
        report = dict(ranks=ranks, dofs=12, domain_rejections=0, snes_reason=2, ksp_reason=2,
                      ksp='preonly' if solver == 'direct' else 'fgmres',
                      pc='lu' if solver == 'direct' else 'fieldsplit',
                      linear_iterations=1 if solver == 'direct' else 3,
                      linear_started=1, linear_completed=1, nnz=100,
                      peak_rss_max_bytes=1024, peak_rss_sum_bytes=1024*ranks,
                      solver_reused=int(step == 2), solver_generation=1)
        report.update({key: .1 for key in TIMERS})
        report.update(assembly_seconds=2, callback_seconds=1, solve_seconds=3)
        if counters:
            initial = int(solver != 'direct' and (not reuse or step == 1))
            reused = int(solver != 'direct' and reuse and step == 1)
            assembled = initial+1-reused
            report.update(jacobian_assemblies=assembled, jacobian_callbacks=1,
                          initial_jacobian_assemblies=initial, initial_jacobian_reuses=reused,
                          initial_jacobian_deferred=int(solver != 'direct' and reuse and step == 2),
                          user_schur_updates=assembled if solver != 'direct' else 0)
        emit('solver_report', report)
        # State the required real prefixes independently of the production
        # expectation helper, so an accidental helper weakening fails this test.
        required = [('-', report['ksp'], report['pc'])]
        if solver == 'hybrid':
            required.append(('fieldsplit_dynamics_fieldsplit_velocity_', 'gmres', 'asm'))
        elif solver == 'twolevel':
            required.append(('fieldsplit_dynamics_fieldsplit_velocity_', 'preonly', 'mg'))
        elif solver == 'added_mass':
            required += [('fieldsplit_dynamics_fieldsplit_fluid_', 'preonly', 'fieldsplit'),
                         ('fieldsplit_dynamics_fieldsplit_structure_', 'fgmres', 'gamg')]
        for rank in range(ranks):
            for index, (prefix, ksp, pc) in enumerate(required):
                emit('solver_node', dict(rank=rank, path='root' if index == 0 else f'root/field{index}',
                     prefix=prefix, ksp=ksp, pc=pc, ksp_reason=2, pc_reason=0,
                     last_iterations=1, reported_norm=1e-13, norm_type=2 if ksp == 'fgmres' else 0))
        emit(f'fsi_step={step}', dict(time=step*.02, accepted_dt=.02, residual=1e-13,
             endpoint_min_fluid_j=1, endpoint_min_solid_j=1, body_balance=0, power_balance=0, snes_iterations=1))
    lines.append('status=success')
    return '\n'.join(lines)+'\n'


class FsiAssemblyValidation(unittest.TestCase):
    def validated(self, text, solver, requested=None, ranks=2):
        row = parse_log(text, 2, ranks, .02, solver)
        flags = [] if requested is None else ['-nonlinear_initial_jacobian_reuse', str(requested).lower()]
        check_execution(row, execution_options(flags), False)
        return row

    def test_pinned_semantic_presets_and_complete_rank_evidence(self):
        for solver in SOLVERS:
            for ranks in (1, 2):
                for reuse in (False, True):
                    with self.subTest(solver=solver, ranks=ranks, reuse=reuse):
                        row = self.validated(assembly_log(solver, ranks, reuse=reuse), solver, reuse, ranks)
                        self.assertEqual(len(row['steps']), 2)
                        self.assertEqual(len(row['solver_nodes']), 2*ranks*len(expected_solvers(solver)))
                        self.assertTrue(row['jacobian_accounting_available'])
                        self.assertLessEqual(row['max_linear_residual_ratio'], 1)

    def test_solver_budget_cannot_be_overridden_by_execution_flags(self):
        for solver in SOLVERS[1:]:
            flags = solver_options(solver)
            for option, expected in [('-ksp_type', 'fgmres'), ('-ksp_pc_side', 'right'),
                    ('-ksp_norm_type', 'unpreconditioned'), ('-ksp_rtol', '1e-11'),
                    ('-ksp_atol', '1e-13'), ('-ksp_max_it', '3000'), ('-ksp_gmres_restart', '100'),
                    ('-pc_plan_schur_approx', 'nodal')]:
                self.assertEqual(flags[flags.index(option)+1], expected)
        for flags in (['-ksp_rtol', '1e-5'], ['-pc_recipe', 'physics'],
                      ['-partition_cell_weights', '10:5,20:1'],
                      ['-nonlinear_initial_jacobian_reuse'], ['-nonlinear_initial_jacobian_reuse', '1'],
                      ['-nonlinear_initial_jacobian_reuse', 'true', '-nonlinear_initial_jacobian_reuse', 'false']):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                execution_options(flags)

    def test_old_version_counts_optional_only_without_explicit_request(self):
        text = assembly_log('hybrid', counters=False)
        self.assertFalse(self.validated(text, 'hybrid')['jacobian_accounting_available'])
        for value in (True, False):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.validated(text, 'hybrid', value)
        for key in JACOBIAN_COUNTERS:
            text = re.sub(r'\b'+key+r'=\S+ ?', '', assembly_log('hybrid'), count=1)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.validated(text, 'hybrid')

    def test_initial_accounting_rejects_stale_or_repeated_work(self):
        for key in JACOBIAN_COUNTERS:
            for value in ('nan', 'inf', '-1', '1.5'):
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    self.validated(replace_field(assembly_log('hybrid'), key, value), 'hybrid', True)
        for key, value in [('initial_jacobian_reuses', '0'), ('initial_jacobian_deferred', '1'),
                           ('user_schur_updates', '0'), ('user_schur_updates', '2'), ('jacobian_callbacks', '2')]:
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                self.validated(replace_field(assembly_log('hybrid'), key, value), 'hybrid', True)
        with self.assertRaises(RuntimeError):
            self.validated(assembly_log('hybrid', reuse=False), 'hybrid', True)
        with self.assertRaises(RuntimeError):
            self.validated(assembly_log('hybrid', reuse=True), 'hybrid', False)

    def test_each_step_and_rank_must_match_actual_preset(self):
        for solver in SOLVERS:
            text = assembly_log(solver)
            root = next(line for line in text.splitlines() if line.startswith('solver_node rank=1 path=root '))
            cases = [text.replace(root+'\n', '', 1), text.replace(root+'\n', root+'\n'+root+'\n', 1),
                     text.replace(root, replace_field(root, 'ksp', 'cg'), 1)]
            if solver != 'direct':
                response = next(line for line in text.splitlines() if line.startswith('solver_node ') and
                                'prefix=fieldsplit_dynamics_' in line)
                cases += [text.replace(response+'\n', '', 1),
                          text.replace(response, replace_field(response, 'pc', 'lu'), 1),
                          text.replace(root, replace_field(root, 'norm_type', '1'), 1)]
            for index, broken in enumerate(cases):
                with self.subTest(solver=solver, index=index), self.assertRaises(RuntimeError):
                    self.validated(broken, solver)

    def test_true_linear_gate_is_unchanged_for_every_solver(self):
        for solver in SOLVERS:
            for value in ('1e-6', 'nan', 'inf', '-1'):
                with self.subTest(solver=solver, value=value), self.assertRaises(RuntimeError):
                    self.validated(replace_field(assembly_log(solver), 'norm', value), solver)

    def test_corrections_cannot_move_between_steps(self):
        text = assembly_log('twolevel')
        correction = next(line for line in text.splitlines() if line.startswith('linear_residual '))
        shifted = text.replace(correction+'\n', '', 1)
        shifted = shifted.replace(correction+'\n', correction+'\n'+correction+'\n', 1)
        with self.assertRaises(RuntimeError):
            self.validated(shifted, 'twolevel')

    def test_partition_weights_are_explicit_positive_unique_integers(self):
        self.assertEqual(partition_weights('20:1,10:5'), {10: 5, 20: 1})
        self.assertEqual(partition_weights('10:2147483647'), {10: 2147483647})
        for text in ('', '10', '10:0', '0:5', '10:-1', '-10:5', '+10:5', '010:5',
                     '10:1.5', '10:5 ', '10 :5', '10:5,', '10:5,,20:1', '10:5,10:1',
                     '10:2147483648', '2147483648:1'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                partition_weights(text)

    def test_partition_commands_keep_the_shared_default_and_isolate_weights(self):
        binaries = {'baseline': Path('/baseline/eonsim'), 'candidate': Path('/candidate/eonsim')}
        work, case = Path('/measurement'), Path('/measurement/input/case.yaml')
        shared = partition_preparations(binaries, case, work, 'n8-r2', 2)
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]['modes'], ['baseline', 'candidate'])
        self.assertEqual(shared[0]['command'], ['/baseline/eonsim', '-case', str(case),
                         '-prepare', '/measurement/n8-r2-partition', '-parts', '2'])
        self.assertIsNone(shared[0]['cell_weights'])
        separate = partition_preparations(binaries, case, work, 'n8-r2', 2, partition_weights('20:1,10:5'))
        routes = {mode: job for job in separate for mode in job['modes']}
        self.assertEqual(len(separate), 2)
        self.assertEqual(routes['baseline']['command'], shared[0]['command'])
        self.assertNotEqual(routes['baseline']['directory'], routes['candidate']['directory'])
        self.assertEqual(routes['candidate']['command'], ['/candidate/eonsim', '-case', str(case),
                         '-prepare', '/measurement/n8-r2-candidate-partition', '-parts', '2',
                         '-partition_cell_weights', '10:5,20:1'])
        self.assertEqual(routes['candidate']['cell_weights'], {10: 5, 20: 1})

    def test_partition_metadata_binds_actual_files_and_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            directory = work/'partition'
            directory.mkdir()
            # Snapshot validation needs exact bytes; numerical solves remain
            # responsible for decoding and validating the real HDF5 shards.
            originals = {'manifest.yaml': b'version: 1\nranks: 2\nglobal_nodes: 12\nglobal_cells: 7\n',
                         'rank_0.h5': b'first rank bytes', 'rank_1.h5': b'second rank bytes'}
            for name, data in originals.items():
                (directory/name).write_bytes(data)
            evidence = partition_evidence(directory, 2, work)
            self.assertEqual(evidence['manifest'], dict(version=1, ranks=2, global_nodes=12, global_cells=7))
            self.assertEqual(evidence['manifest_text'], originals['manifest.yaml'].decode())
            files = {row['path']: row for row in evidence['files']}
            self.assertEqual(set(files), {'partition/'+name for name in originals})
            for name, data in originals.items():
                self.assertEqual(files['partition/'+name]['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(files['partition/'+name]['bytes'], len(data))
            check_partition_unchanged(evidence, work)
            changes = {'manifest.yaml': originals['manifest.yaml'].replace(b'12', b'13'),
                       'rank_1.h5': b'Second rank bytes'}
            for name, changed in changes.items():
                (directory/name).write_bytes(changed)
                with self.subTest(changed=name), self.assertRaises(RuntimeError):
                    check_partition_unchanged(evidence, work)
                (directory/name).write_bytes(originals[name])
            for name in ('manifest.yaml', 'rank_1.h5'):
                (directory/name).unlink()
                with self.subTest(missing=name), self.assertRaises(RuntimeError):
                    partition_evidence(directory, 2, work)
                (directory/name).write_bytes(originals[name])
            (directory/'rank_2.h5').write_bytes(b'unexpected rank')
            with self.assertRaises(RuntimeError):
                partition_evidence(directory, 2, work)
            (directory/'rank_2.h5').unlink()
            for old, new in ((b'version: 1', b'version: 2'), (b'ranks: 2', b'ranks: 1'),
                             (b'global_cells: 7', b'global_cells: 0'),
                             (b'global_cells: 7', b'global_nodes: 7')):
                (directory/'manifest.yaml').write_bytes(originals['manifest.yaml'].replace(old, new))
                with self.subTest(manifest_field=new), self.assertRaises(RuntimeError):
                    partition_evidence(directory, 2, work)


class SharedOutputValidation(unittest.TestCase):
    """Corruptions that otherwise survive zip, dict overwrite or Python indexing."""

    @staticmethod
    def topology(kind='Tetrahedron', count=1):
        item = ET.Element('Topology', TopologyType=kind, NumberOfElements=str(count))
        if kind == 'Polyline':
            item.set('NodesPerElement', '2')
        return item

    def records(self, identifiers=None, tags=None, rows=None, shape=None, topology=None):
        identifiers = [2001] if identifiers is None else identifiers
        tags = [10] if tags is None else tags
        rows = [[0, 1, 2, 3]] if rows is None else rows
        return cell_records('Volume', self.topology() if topology is None else topology,
                            (1, 4) if shape is None else shape, identifiers, tags, rows,
                            [1001, 1002, 1003, 1004])

    def test_valid_fixed_and_mixed_topologies_keep_cell_types(self):
        self.assertEqual(self.records(), {2001: (10, (1001, 1002, 1003, 1004), 10)})
        mixed = self.records(identifiers=[2001, 2002], tags=[10, 20],
                             rows=[4, 0, 1, 2, 5, 0, 1, 3, 2], shape=(9,), topology=self.topology('Mixed', 2))
        self.assertEqual(mixed, {2001: (10, (1001, 1002, 1003), 5),
                                 2002: (20, (1001, 1002, 1004, 1003), 9)})
        self.assertEqual(self.records(identifiers=[], tags=[], rows=[], shape=(0, 4),
                                      topology=self.topology(count=0)), {})

    def test_duplicate_cell_id_cannot_disappear_in_dictionary(self):
        with self.assertRaisesRegex(RuntimeError, 'Duplicate HDF5 cell ID'):
            self.records(identifiers=[2001, 2001], tags=[10, 10], rows=[[0, 1, 2, 3]] * 2,
                         shape=(2, 4), topology=self.topology(count=2))

    def test_cell_lengths_and_shapes_cannot_be_silently_truncated(self):
        for changes in ({'tags': []}, {'tags': [10, 20]}, {'shape': (2, 4)},
                        {'shape': (1, 3)}, {'topology': self.topology(count=2)},
                        {'topology': self.topology('Triangle')}):
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                self.records(**changes)

    def test_connectivity_must_not_use_python_negative_indexing(self):
        for invalid in (-1, 4):
            with self.subTest(index=invalid), self.assertRaisesRegex(RuntimeError, 'Invalid HDF5 point index'):
                self.records(rows=[[0, 1, 2, invalid]])

    def test_cell_indices_ids_and_tags_must_be_integers(self):
        for changes in ({'identifiers': [2001.1]}, {'tags': [10.1]},
                        {'rows': [[0, 1, 2, 3.1]]}, {'rows': [[0, 1, 2, 3.0]]},
                        {'rows': [4.1, 0, 1, 2], 'shape': (4,), 'topology': self.topology('Mixed')}):
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'Non-integer HDF5 cell data'):
                self.records(**changes)

    def test_mixed_connectivity_is_consumed_exactly(self):
        for rows in ([4, 0, 1, 2, 5], [5, 0, 1, 2], [], [4, 0, 1, -1], [10, 0, 1, 2, 3]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                self.records(rows=rows, shape=(len(rows),), topology=self.topology('Mixed'))
        self.assertEqual(self.records(identifiers=[], tags=[], rows=[], shape=(0,),
                                      topology=self.topology('Mixed', 0)), {})

    def test_missing_or_duplicate_domain_is_rejected(self):
        for names, datasets in ((['Boundary'], ['Boundary/connectivity']),
                                (['Volume', 'Volume'], ['Volume/connectivity']),
                                (['Volume'], ['Volume/connectivity', 'Boundary/connectivity']),
                                ([], ['Volume/connectivity'])):
            grid = ET.Element('Grid')
            for name in names:
                ET.SubElement(grid, 'Grid', Name=name, GridType='Uniform')
            with self.subTest(names=names), self.assertRaisesRegex(RuntimeError, 'XDMF grid'):
                snapshot_grids(grid, datasets)
        grid = ET.fromstring('<Grid><Grid Name="Volume" GridType="Uniform"/></Grid>')
        self.assertEqual(len(snapshot_grids(grid, ['Volume/connectivity'])), 1)

    @staticmethod
    def grid():
        return ET.fromstring('''<Grid Name="Volume" GridType="Uniform">
          <Topology TopologyType="Tetrahedron" NumberOfElements="1"><DataItem>result.h5:/Volume/connectivity</DataItem></Topology>
          <Geometry GeometryType="XYZ"><DataItem>result.h5:/Mesh/coordinates</DataItem></Geometry>
          <Attribute Name="pressure" Center="Node" AttributeType="Scalar"><DataItem>result.h5:/Fields/pressure</DataItem></Attribute>
          <Attribute Name="mesh_node_id" Center="Node" AttributeType="Scalar"><DataItem>result.h5:/Mesh/mesh_node_id</DataItem></Attribute>
          <Attribute Name="algebra_node_id" Center="Node" AttributeType="Scalar"><DataItem>result.h5:/Mesh/algebra_node_id</DataItem></Attribute>
          <Attribute Name="owner" Center="Node" AttributeType="Scalar"><DataItem>result.h5:/Mesh/owner</DataItem></Attribute>
          <Attribute Name="physical_tag" Center="Cell" AttributeType="Scalar"><DataItem>result.h5:/Volume/physical_tag</DataItem></Attribute>
          <Attribute Name="mesh_element_id" Center="Cell" AttributeType="Scalar"><DataItem>result.h5:/Volume/mesh_element_id</DataItem></Attribute>
        </Grid>''')

    def test_equal_shape_dataset_references_cannot_be_swapped(self):
        grid_bindings(self.grid(), {'pressure': 1})
        for element, replacement in (('./Attribute[@Name="pressure"]/DataItem', 'Mesh/mesh_node_id'),
                                     ('./Geometry/DataItem', 'Fields/velocity'),
                                     ('./Topology/DataItem', 'Boundary/connectivity')):
            grid = self.grid()
            grid.find(element).text = 'result.h5:/' + replacement
            with self.subTest(element=element), self.assertRaisesRegex(RuntimeError, 'dataset binding'):
                grid_bindings(grid, {'pressure': 1})

    def test_attribute_metadata_and_presence_are_required(self):
        for key, value in (('Center', 'Cell'), ('AttributeType', 'Vector'), ('Name', 'wrong')):
            grid = self.grid()
            grid.find('./Attribute[@Name="pressure"]').set(key, value)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                grid_bindings(grid, {'pressure': 1})
        for mutation in ('missing', 'duplicate'):
            grid = self.grid()
            attribute = grid.find('./Attribute[@Name="pressure"]')
            if mutation == 'missing':
                grid.remove(attribute)
            else:
                grid.append(attribute)
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                grid_bindings(grid, {'pressure': 1})


if __name__ == '__main__':
    unittest.main()
