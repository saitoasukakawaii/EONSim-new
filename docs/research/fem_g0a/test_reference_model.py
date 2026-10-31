"""Run directly with python3 -B; only unittest and the stdlib reference model."""
from dataclasses import replace
from fractions import Fraction as F
import itertools
import unittest

from reference_model import (
    Node, Relation, acceptance_squares, elastic_fixture,
    materialize, matmul, matvec, numbering, partition, permutation, recipe,
    reduce_affine, residual, resolve, rigid_fixture, transpose, trial_map,
    validate_nested,
)


# Independent hand oracle, also printed and derived in the design document.
J = [[2, 1, -1, 3, 4], [5, 6, 2, 0, 1], [-2, 4, 7, 1, -3],
     [9, 8, 6, 5, 2], [1, 0, 3, 2, 4]]
B = [1, 2, 3, 4, 5]
K = [[1, 0], [0, 1], [0, 1], [0, 2], [0, 0]]
W = [[1, 0], [0, 1], [0, 1], [0, 0], [0, 0]]
G = [0, 0, 0, 3, 5]
OWNED = {
    1: [tuple(range(14))],
    2: [tuple(range(7)), tuple(range(7, 14))],
    4: [tuple(range(7)), tuple(range(7, 11)), tuple(range(11, 14)), ()],
}
PHYSICS = {"fluid": (0, 1, 2, 3, 7), "solid": (8, 9, 10, 11, 12, 13), "ale": (4, 5, 6)}
QUANTITY = {"velocity": (0, 1, 2, 8, 9, 10, 11, 12, 13), "pressure": (3, 7), "mesh_displacement": (4, 5, 6)}


class IdentityTests(unittest.TestCase):
    def test_identity_numbering_roundtrip_and_permutation(self):
        dofs = elastic_fixture()
        for order in [list(range(14)), list(reversed(range(14))), [3, 4, 5, 0, 1, 2, 13, 12, 11, 10, 9, 8, 7, 6]]:
            forward, backward = numbering(dofs, order)
            for d, i in zip(dofs, order):
                self.assertEqual(backward[forward[d.identity]], d.identity)
                self.assertEqual(forward[backward[i]], i)

    def test_semantic_identity_not_rank_row_or_interface_tags(self):
        dofs = elastic_fixture()
        key = dofs[8].identity
        self.assertEqual(key.entity_id, 20)
        self.assertEqual(dofs[8].tags, {"fluid_trace", "solid_trace", "mesh_trace"})
        self.assertNotEqual(key, replace(key, domain="fluid"))
        self.assertNotEqual(key, replace(key, mesh="new_mesh"))
        for owned in OWNED.values():
            partition(14, owned, [() for _ in owned])
            self.assertEqual(dofs[8].identity, key)

    def test_duplicate_identity_and_bad_numbering_rejected(self):
        dofs = elastic_fixture()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            numbering(dofs+(dofs[0],), range(15))
        for ids in [list(range(13)), [0]*14, list(range(1, 15))]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                numbering(dofs, ids)

    def test_interface_semantic_aliases_keep_distinct_keys(self):
        dofs = elastic_fixture()
        independent = [d.identity for d in dofs]
        relations = {}
        for d in dofs[8:11]:
            fluid_key = replace(d.identity, domain="fluid")
            mesh_key = replace(d.identity, domain="fluid_mesh", quantity="mesh_displacement")
            relations[fluid_key] = Relation(d.identity)
            relations[mesh_key] = Relation(d.identity, F(1, 4), F(3))
        fixed = replace(dofs[0].identity, entity_id=99)
        relations[fixed] = Relation(lift=F(0))
        mapping = resolve(independent, relations)
        self.assertEqual(len(mapping), 21)
        self.assertEqual(mapping[fixed], (None, F(0), F(0)))
        for d in dofs[8:11]:
            self.assertEqual(mapping[replace(d.identity, domain="fluid")], (d.identity, F(1), F(0)))
            self.assertEqual(mapping[replace(d.identity, domain="fluid_mesh", quantity="mesh_displacement")], (d.identity, F(1, 4), F(3)))


class PartitionTreeTests(unittest.TestCase):
    def test_owned_ghost_roundtrip_and_empty_local_blocks(self):
        for count, owned in OWNED.items():
            ghosts = [tuple(i for i in (0, 8, 13) if i not in rows) for rows in owned]
            own, local = partition(14, owned, ghosts)
            for rows in local:
                inverse = {root: slot for slot, root in enumerate(rows)}
                for slot, root in enumerate(rows):
                    self.assertEqual(inverse[root], slot)
            blocks = materialize(recipe(elastic_fixture(), "hybrid"), own)
            for b in blocks.values():
                for rank, roots in enumerate(b.root_rows):
                    self.assertTrue(set(roots) <= set(own[rank]))
            self.assertEqual(sum(map(len, blocks["root/mesh"].parent_is)), 3)
            if count > 1:
                self.assertEqual(blocks["root/mesh"].parent_is[1], ())
            if count == 4:
                self.assertEqual(own[3], ())
                self.assertTrue(all(b.parent_is[3] == () for b in blocks.values()))

    def test_three_groupings_coverage_and_unique_interface(self):
        for count, owned in OWNED.items():
            for mode in ("physics", "quantity", "hybrid"):
                with self.subTest(partitions=count, mode=mode):
                    tree = recipe(elastic_fixture(), mode)
                    materialize(tree, owned)
                    leaves = []

                    def visit(n):
                        if not n.children:
                            leaves.extend(n.roots)
                        for child in n.children:
                            visit(child)
                    visit(tree)
                    self.assertEqual(sorted(leaves), list(range(14)))
                    for interface in (8, 9, 10):
                        self.assertEqual(leaves.count(interface), 1)
                    expected = PHYSICS if mode == "physics" else QUANTITY if mode == "quantity" else {"dynamics": (0, 1, 2, 3, 7, 8, 9, 10, 11, 12, 13), "mesh": (4, 5, 6)}
                    self.assertEqual({c.name: c.roots for c in tree.children}, expected)

    def test_two_level_parent_numbering_hand_oracle(self):
        blocks = materialize(recipe(elastic_fixture(), "physics"), OWNED[2])
        self.assertEqual(blocks["root/fluid"].parent_is, ((0, 1, 2, 3), (7,)))
        self.assertEqual(blocks["root/fluid/pressure"].parent_is, ((3,), (4,)))
        self.assertEqual(blocks["root/fluid/velocity"].parent_is, ((0, 1, 2), ()))
        self.assertEqual(blocks["root/fluid"].root_to_sub()[7], 4)

    def test_three_level_parent_numbering_hand_oracle(self):
        blocks = materialize(recipe(elastic_fixture(), "hybrid"), OWNED[4])
        self.assertEqual(blocks["root/dynamics"].parent_is,
                         ((0, 1, 2, 3), (7, 8, 9, 10), (11, 12, 13), ()))
        self.assertEqual(blocks["root/dynamics/pressure"].parent_is, ((3,), (4,), (), ()))
        self.assertEqual(blocks["root/dynamics/velocity"].parent_is,
                         ((0, 1, 2), (5, 6, 7), (8, 9, 10), ()))
        self.assertEqual(blocks["root/dynamics/velocity/structure"].parent_is,
                         ((), (3, 4, 5), (6, 7, 8), ()))
        self.assertEqual(blocks["root/dynamics/velocity"].root_to_sub()[8], 3)
        self.assertEqual(blocks["root/dynamics/velocity"].root_to_sub()[13], 8)
        for path, block in blocks.items():
            parent_path = path.rsplit("/", 1)[0]
            parent = OWNED[4] if parent_path == "root" else blocks[parent_path].root_rows
            validate_nested(parent, block.root_rows, block.parent_is)

    def test_root_indices_wrong_even_when_in_parent_range(self):
        blocks = materialize(recipe(elastic_fixture(), "hybrid"), OWNED[2])
        parent = blocks["root/dynamics"].root_rows
        child = blocks["root/dynamics/pressure"].root_rows
        # 7 is within rank 1's dynamics range [4,11), but refers to root 10.
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_nested(parent, child, ((3,), (7,)))
        with self.assertRaisesRegex(ValueError, "owned"):
            validate_nested(parent, child, ((3,), (14,)))

    def test_nested_submatrix_entries_without_solver(self):
        blocks = materialize(recipe(elastic_fixture(), "hybrid"), OWNED[4])
        matrix = [[100*i+j for j in range(14)] for i in range(14)]
        for path in ("root/dynamics", "root/dynamics/velocity", "root/dynamics/velocity/structure"):
            ids = [i for rows in blocks[path].parent_is for i in rows]
            matrix = [[matrix[i][j] for j in ids] for i in ids]
        self.assertEqual([len(matrix), len(matrix[0])], [6, 6])
        self.assertEqual([matrix[0][0], matrix[0][-1], matrix[-1][0], matrix[-1][-1]], [808, 813, 1308, 1313])

    def test_invalid_partition_rejected(self):
        bad = [([[0, 1], [1, 2]], [[], []]), ([[0], [2]], [[], []]),
               ([[0, 1, 2]], [[1]]), ([[0, 1, 2]], [[3]]),
               ([[0], [1, 2]], [[2, 2], []])]
        for own, ghosts in bad:
            with self.subTest(own=own, ghosts=ghosts), self.assertRaises(ValueError):
                partition(3, own, ghosts)

    def test_bad_trees_rejected(self):
        root = (0, 1, 2)
        cases = [
            (Node("a", (0, 1)), Node("b", (1, 2))),  # duplicate shared row
            (Node("a", (0,)), Node("b", (2,))),  # omitted row
            (Node("a", (0,)), Node("b", (1, 3))),  # illegal reference
            (Node("a", (0, 1, 2)), Node("b", ())),  # globally empty
            (Node("a", (0,)), Node("a", (1, 2))),
            (Node("a-b", (0,)), Node("b", (1, 2))),
            (Node("a", (0, 0)), Node("b", (1, 2))),
            (Node("a", (0, 1, 2)),),
        ]
        for children in cases:
            with self.subTest(children=children), self.assertRaises(ValueError):
                materialize(Node("root", root, children), [(0, 1, 2)])
        with self.assertRaisesRegex(ValueError, "prefix"):
            materialize(recipe(elastic_fixture(), "hybrid"), OWNED[1], "x"*120)

    def test_rigid_global_unknown_single_owner_and_aliases(self):
        dofs = rigid_fixture()
        for count in (1, 2, 4):
            own = [tuple(range(7))]+[() for _ in range(count-1)]
            own[-1] += (7,)
            ghosts = [(7,) if rank != count-1 else () for rank in range(count)]
            owned, local = partition(8, own, ghosts)
            self.assertEqual(sum(7 in rows for rows in owned), 1)
            self.assertTrue(all(7 in rows for rows in local))
            for mode in ("physics", "quantity", "hybrid"):
                blocks = materialize(recipe(dofs, mode), owned)
                body_block = "root/solid" if mode == "physics" else "root/velocity/structure" if mode == "quantity" else "root/dynamics/velocity/structure"
                self.assertEqual(sum(map(len, blocks[body_block].parent_is)), 1)
            body = dofs[-1].identity
            aliases = {"u1": Relation(body), "u2": Relation(body),
                       "dm1": Relation(body, F(1, 4), F(3)),
                       "dm2": Relation(body, F(1, 4), F(3))}
            expanded = resolve([body], aliases)
            self.assertEqual(expanded["u1"], (body, F(1), F(0)))
            self.assertEqual(expanded["dm2"], (body, F(1, 4), F(3)))
            self.assertEqual(expanded["dm1"][1]*8+expanded["dm1"][2], 5)


class AlgebraTests(unittest.TestCase):
    def test_affine_constraint_alias_and_nonzero_lift(self):
        relations = {"uf_gamma": Relation("vs"), "dm_gamma": Relation("vs", F(2), F(3)), "fixed": Relation(lift=F(5))}
        k, g = trial_map(["uf", "uf_gamma", "vs", "dm_gamma", "fixed"], ["uf", "vs"], relations)
        self.assertEqual(k, K)
        self.assertEqual(g, G)
        self.assertEqual([v+g0 for v, g0 in zip(matvec(k, [1, 2]), g)], [1, 2, 2, 7, 5])
        r, j = reduce_affine(J, B, k, W, g, [1, 2])
        self.assertEqual(j, [[2, 6], [3, 21]])
        self.assertEqual(r, [42, 33])
        self.assertEqual(residual(J, B, [1, 2, 2, 7, 5]), [42, 24, 9, 78, 36])
        self.assertEqual(reduce_affine(J, B, k, W, g, [0, 0])[0], [28, -12])

    def test_W_equal_K_counterexample(self):
        wrong_r, wrong_j = reduce_affine(J, B, K, K, G, [1, 2])
        self.assertEqual(wrong_r, [42, 189])
        self.assertEqual(wrong_j, [[2, 6], [21, 69]])
        self.assertNotEqual(wrong_r, [42, 33])

    def test_exact_directional_derivative(self):
        q, direction, h = [F(1, 3), F(-2, 5)], [F(2), F(-3)], F(1, 7)
        r, j = reduce_affine(J, B, K, W, G, q)
        shifted = [v+h*d for v, d in zip(q, direction)]
        after = reduce_affine(J, B, K, W, G, shifted)[0]
        self.assertEqual([(a-b)/h for a, b in zip(after, r)], matvec(j, direction))

    def test_independent_permutation_nonsymmetric_oracle(self):
        P = permutation([1, 0])  # q = P y, y=[2,1]
        q = matvec(P, [2, 1])
        r, j = reduce_affine(J, B, K, W, G, q)
        self.assertEqual(matvec(transpose(P), r), [33, 42])
        self.assertEqual(matmul(matmul(transpose(P), j), P), [[21, 3], [6, 2]])
        new = reduce_affine(J, B, matmul(K, P), matmul(W, P), G, [2, 1])
        self.assertEqual(new, ([F(33), F(42)], [[F(21), F(3)], [F(6), F(2)]]))
        for order in itertools.permutations(range(2)):
            p = permutation(order)
            self.assertEqual(matmul(transpose(p), p), [[1, 0], [0, 1]])
        with self.assertRaises(ValueError):
            permutation([0, 0])

    def test_dt_changes_coefficients_not_alias_support(self):
        def mappings(dt):
            return trial_map(["uf", "uf_gamma", "vs", "dm_gamma", "fixed"], ["uf", "vs"],
                             {"uf_gamma": Relation("vs"), "dm_gamma": Relation("vs", dt, F(3)), "fixed": Relation(lift=F(5))})
        first, lift = mappings(F(2))
        retry, retry_lift = mappings(F(1, 2))
        self.assertEqual([[v != 0 for v in r] for r in first], [[v != 0 for v in r] for r in retry])
        self.assertEqual(lift, retry_lift)
        self.assertEqual(reduce_affine(J, B, retry, W, lift, [1, 2]), ([F(33), F(30)], [[F(2), F(3, 2)], [F(3), F(39, 2)]]))

    def test_bad_constraints_and_dimensions_rejected(self):
        for independent, relations in [(["u"], {"a": Relation("missing")}),
                                       (["u"], {"a": Relation("b"), "b": Relation("a")}),
                                       (["u"], {"u": Relation(lift=F(3))})]:
            with self.subTest(relations=relations), self.assertRaises(ValueError):
                resolve(independent, relations)
        with self.assertRaises(ValueError):
            trial_map(["u"], ["u"], {"g": Relation(lift=F(1))})
        with self.assertRaises(ValueError):
            reduce_affine(J, B, K, [[1]], G, [1, 2])
        # Transitive affine lifting is not merely an index alias.
        self.assertEqual(resolve(["u"], {"a": Relation("u", F(2), F(3)), "b": Relation("a", F(4), F(5))})["b"], ("u", F(8), F(17)))

    def test_acceptance_unaffected_by_PC_grouping_or_permutation(self):
        dofs = elastic_fixture()
        r = list(range(1, 15))
        scales = {"velocity": 1, "pressure": 2, "mesh": 3, "structure": 4}
        expected = {"velocity": F(14, 3), "pressure": F(10), "mesh": F(110, 27), "structure": F(811, 96)}
        # structure: (9²+10²+11²+12²+13²+14²)/(6*16)=811/96.
        self.assertEqual(acceptance_squares(dofs, r, scales), expected)
        for mode in ("physics", "quantity", "hybrid"):
            materialize(recipe(dofs, mode), OWNED[4])
            self.assertEqual(acceptance_squares(dofs, r, scales), expected)
        order = list(reversed(range(14)))
        self.assertEqual(acceptance_squares([dofs[i] for i in order], [r[i] for i in order], scales), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
