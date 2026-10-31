"""FEM-G0A design oracle: exact algebra and simulated partition indices only.

No FEM kernel, linear solve, PETSc, MPI, subprocess, or third-party dependency.
The global dictionaries are deliberately tiny reference data, not a distributed
production storage proposal. See the companion design for C++ contracts.
"""
from dataclasses import dataclass
from fractions import Fraction as F
import re


@dataclass(frozen=True, order=True)
class Identity:
    mesh: str
    domain: str
    space: str
    quantity: str
    entity_kind: str
    entity_id: int
    mode: int
    component: int


@dataclass(frozen=True)
class Dof:
    identity: Identity
    physics: str  # exclusive canonical representative, not all semantic tags
    quantity: str
    acceptance: str
    tags: frozenset = frozenset()


def numbering(dofs, indices):
    """Bijection of independent identities and root storage rows, not aliases."""
    identities = [d.identity for d in dofs]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate independent identity")
    if len(indices) != len(dofs) or set(indices) != set(range(len(dofs))):
        raise ValueError("root numbering must be a complete permutation")
    forward = dict(zip(identities, indices))
    return forward, {i: key for key, i in forward.items()}


@dataclass(frozen=True)
class Relation:
    target: object = None  # another semantic identity; None means prescribed
    factor: F = F(1)
    lift: F = F(0)


def resolve(independent, relations):
    """Flatten single-master affine relations; reject cycles and unknown refs.

    Returns semantic key -> (independent representative or None, factor, lift).
    This is enough for the current aliases; general MPC is outside this model.
    """
    independent = tuple(independent)
    if len(set(independent)) != len(independent) or set(independent) & set(relations):
        raise ValueError("independent identities overlap or are duplicated")
    result = {key: (key, F(1), F(0)) for key in independent}
    visiting = set()

    def visit(key):
        if key in result:
            return result[key]
        if key in visiting:
            raise ValueError("constraint cycle")
        if key not in relations:
            raise ValueError("illegal semantic reference")
        visiting.add(key)
        r = relations[key]
        if r.target is None:
            value = (None, F(0), F(r.lift))
        else:
            rep, factor, lift = visit(r.target)
            value = (rep, F(r.factor)*factor, F(r.factor)*lift + F(r.lift))
            if value[1] == 0:
                value = (None, F(0), value[2])
        result[key] = value
        visiting.remove(key)
        return value

    for key in relations:
        visit(key)
    return result


def trial_map(full, independent, relations):
    if len(set(full)) != len(full):
        raise ValueError("duplicate full identity")
    resolved = resolve(independent, relations)
    if set(full) != set(resolved):
        raise ValueError("full identities must cover independent and constrained slots")
    column = {key: i for i, key in enumerate(independent)}
    K, g = [], []
    for key in full:
        rep, factor, lift = resolved[key]
        row = [F(0)]*len(independent)
        if rep is not None:
            row[column[rep]] = factor
        K.append(row)
        g.append(lift)
    return K, g


def partition(n, owned, ghosts):
    """Check rank-contiguous owned ranges and unique local owned/ghost slots."""
    owned, ghosts = tuple(map(tuple, owned)), tuple(map(tuple, ghosts))
    if not owned or len(owned) != len(ghosts):
        raise ValueError("partition shape")
    if tuple(x for rows in owned for x in rows) != tuple(range(n)):
        raise ValueError("duplicate/missing/noncontiguous owned row")
    local = []
    for own, ghost in zip(owned, ghosts):
        if len(set(ghost)) != len(ghost) or set(own) & set(ghost):
            raise ValueError("duplicate ghost or ghost is owned")
        if any(i < 0 or i >= n for i in ghost):
            raise ValueError("illegal ghost reference")
        local.append(own + ghost)
    return owned, tuple(local)


@dataclass(frozen=True)
class Node:
    name: str
    roots: tuple  # exact independent root rows, not raw semantic occurrences
    children: tuple = ()


@dataclass(frozen=True)
class Block:
    path: str
    parent_is: tuple  # per-rank indices GLOBAL WITHIN THE IMMEDIATE PARENT
    root_rows: tuple  # per-rank root provenance; this also defines child order

    def root_to_sub(self):
        # Rank concatenation is the child matrix's distributed global numbering.
        return {root: i for i, root in enumerate(x for r in self.root_rows for x in r)}


def materialize(node, owned, prefix="fsi_"):
    """Validate nonoverlapping total trees and compute each parent-relative IS.

    Same communicator/rank ordering at every level; each child retains parent
    row order. Globally empty blocks are errors; locally empty blocks are kept.
    """
    n = sum(map(len, owned))
    partition(n, owned, [() for _ in owned])
    if node.name != "root" or set(node.roots) != set(range(n)):
        raise ValueError("root coverage")
    blocks = {}

    def descend(current, rows, path, opt_prefix):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", current.name):
            raise ValueError("invalid block name")
        if len(set(current.roots)) != len(current.roots):
            raise ValueError("duplicate block row")
        if not current.roots:
            raise ValueError("globally empty block: " + path)
        if not current.children:
            return
        if len(current.children) < 2:
            raise ValueError("internal block requires at least two children")
        names = [c.name for c in current.children]
        if len(names) != len(set(names)):
            raise ValueError("duplicate sibling name")
        covered = []
        for child in current.children:
            covered.extend(child.roots)
        if len(covered) != len(set(covered)):
            raise ValueError("overlapping children")
        if set(covered) != set(current.roots):
            raise ValueError("omitted row or illegal child reference")
        parent_lookup = {root: i for i, root in enumerate(x for r in rows for x in r)}
        for child in current.children:
            selected = set(child.roots)
            child_rows = tuple(tuple(i for i in r if i in selected) for r in rows)
            child_is = tuple(tuple(parent_lookup[i] for i in r) for r in child_rows)
            child_path = path + "/" + child.name
            child_prefix = opt_prefix + "fieldsplit_" + child.name + "_"
            # Conservative first-adapter bound for PETSc's legacy prefix buffer.
            if len(child_prefix.encode("ascii")) >= 128:
                raise ValueError("options prefix too long")
            blocks[child_path] = Block(child_path, child_is, child_rows)
            descend(child, child_rows, child_path, child_prefix)

    descend(node, tuple(map(tuple, owned)), "root", prefix)
    return blocks


def validate_nested(parent_rows, child_roots, supplied):
    """Validate provenance as well as range: wrong root indices can be in range."""
    parent = [i for rows in parent_rows for i in rows]
    if len(supplied) != len(parent_rows) or len(child_roots) != len(parent_rows):
        raise ValueError("nested partition shape")
    offset = 0
    for own, expected, ids in zip(parent_rows, child_roots, supplied):
        if len(set(ids)) != len(ids) or any(i < offset or i >= offset+len(own) for i in ids):
            raise ValueError("nested IS is not owned in parent numbering")
        if tuple(parent[i] for i in ids) != tuple(expected):
            raise ValueError("wrong nested numbering/provenance")
        offset += len(own)


def elastic_fixture():
    """14 retained scalar rows: F10 (7), interface I20 (4), solid S30 (3)."""
    dofs = []

    def add(node, domain, quantity, physics, acceptance, components, interface=False):
        for c in components:
            key = Identity("joined_mesh_v1", domain, "Tet4_P1", quantity, "vertex", node, 0, c)
            tags = frozenset({"fluid_trace", "solid_trace", "mesh_trace"}) if interface and quantity == "velocity" else frozenset()
            dofs.append(Dof(key, physics, quantity, acceptance, tags))

    add(10, "fluid", "velocity", "fluid", "velocity", range(3))
    add(10, "fluid", "pressure", "fluid", "pressure", [0])
    add(10, "fluid_mesh", "mesh_displacement", "ale", "mesh", range(3))
    add(20, "fluid", "pressure", "fluid", "pressure", [0])
    add(20, "solid", "velocity", "solid", "structure", range(3), True)
    add(30, "solid", "velocity", "solid", "structure", range(3))
    return tuple(dofs)


def rigid_fixture():
    """A separate rigid case: F10's seven slots plus one body-wide velocity."""
    body = Identity("body_registry_v1", "body_1", "single_axis", "velocity", "global", 1, 0, 0)
    return elastic_fixture()[:7] + (Dof(body, "solid", "velocity", "rigid", frozenset({"fluid_trace", "mesh_trace"})),)


def recipe(dofs, mode):
    def select(attr, value):
        return tuple(i for i, d in enumerate(dofs) if getattr(d, attr) == value)

    velocity, pressure = select("quantity", "velocity"), select("quantity", "pressure")
    mesh = select("quantity", "mesh_displacement")
    fluid_v = tuple(i for i in velocity if dofs[i].physics == "fluid")
    solid_v = tuple(i for i in velocity if dofs[i].physics == "solid")
    root = tuple(range(len(dofs)))
    if mode == "physics":
        fluid = select("physics", "fluid")
        return Node("root", root, (Node("fluid", fluid, (Node("velocity", fluid_v), Node("pressure", pressure))), Node("solid", solid_v), Node("ale", mesh)))
    v = Node("velocity", velocity, (Node("fluid_interior", fluid_v), Node("structure", solid_v)))
    if mode == "quantity":
        return Node("root", root, (v, Node("pressure", pressure), Node("mesh_displacement", mesh)))
    if mode == "hybrid":
        return Node("root", root, (Node("dynamics", tuple(sorted(velocity+pressure)), (v, Node("pressure", pressure))), Node("mesh", mesh)))
    raise ValueError("unknown grouping mode")


def transpose(a):
    if not a or not a[0] or any(len(row) != len(a[0]) for row in a):
        raise ValueError("empty or ragged matrix")
    return [list(col) for col in zip(*a)]


def matmul(a, b):
    bt = transpose(b)
    transpose(a)
    if len(a[0]) != len(b):
        raise ValueError("matrix dimensions")
    return [[sum((F(x)*F(y) for x, y in zip(row, col)), F(0)) for col in bt] for row in a]


def matvec(a, x):
    return [row[0] for row in matmul(a, [[v] for v in x])]


def residual(J, b, x):
    values = matvec(J, x)
    if len(values) != len(b):
        raise ValueError("residual dimensions")
    return [v-F(load) for v, load in zip(values, b)]


def reduce_affine(J, b, K, W, g, q):
    """Fixed K/W only; caller supplies W independently from the trial map."""
    kq = matvec(K, q)
    if len(kq) != len(g):
        raise ValueError("lifting dimensions")
    x = [v+F(lift) for v, lift in zip(kq, g)]
    return matvec(transpose(W), residual(J, b, x)), matmul(matmul(transpose(W), J), K)


def permutation(new_to_old):
    n = len(new_to_old)
    if set(new_to_old) != set(range(n)):
        raise ValueError("invalid permutation")
    return [[F(new_to_old[j] == i) for j in range(n)] for i in range(n)]


def acceptance_squares(dofs, r, scales):
    """Exact mean-square sufficient statistic; no PC grouping parameter."""
    if len(dofs) != len(r):
        raise ValueError("acceptance dimensions")
    groups = {}
    for d, value in zip(dofs, r):
        scale = F(scales[d.acceptance])
        if scale <= 0:
            raise ValueError("nonpositive physical scale")
        groups.setdefault(d.acceptance, []).append((F(value)/scale)**2)
    return {name: sum(values, F(0))/len(values) for name, values in groups.items()}
