#!/usr/bin/env python3
"""Exact-arithmetic checks for the proposed scaling contract, not a PETSc test."""
from fractions import Fraction as Q


def matvec(a, x):
    return [sum(v*w for v, w in zip(row, x)) for row in a]


def solve(a, b):
    """Small dense reference solve with exact pivoting; no production use."""
    rows = [list(map(Q, row)) + [Q(rhs)] for row, rhs in zip(a, b)]
    n = len(b)
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v/divisor for v in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [v-factor*w for v, w in zip(rows[i], rows[col])]
    return [row[-1] for row in rows]


def residual(x):
    u, v, z = x
    return [u*u + v + z - 7, u + 3*v - z - 2, z - 3]


def tangent(x):
    return [[2*x[0], 1, 1], [1, 3, -1], [0, 0, 1]]


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    checks = 0
    for sx, sr in [([1, 1, 1], [1, 1, 1]),
                   ([Q(1, 100), 100, 7], [1000, Q(1, 10), 11])]:
        sx, sr = list(map(Q, sx)), list(map(Q, sr))
        x = list(map(Q, [2, -1, 4]))  # Deliberately violate the prescribed z=3.
        y = [v/s for v, s in zip(x, sx)]
        r, j = residual(x), tangent(x)
        scaled_j = [[v*sx[k]/sr[i] for k, v in enumerate(row)] for i, row in enumerate(j)]
        scaled_r = [v/s for v, s in zip(r, sr)]
        dx = solve(j, [-v for v in r])
        dy = solve(scaled_j, [-v for v in scaled_r])
        check(dx == [s*v for s, v in zip(sx, dy)], 'Newton increment mapping')
        check(scaled_j[2][2] == sx[2]/sr[2], 'Constraint diagonal')
        check(x[2] + sx[2]*dy[2] == 3, 'Nonzero prescribed value')
        direction = list(map(Q, [1, -2, 3]))
        h = Q(1, 1000)
        plus = residual([s*(v+h*d) for s, v, d in zip(sx, y, direction)])
        minus = residual([s*(v-h*d) for s, v, d in zip(sx, y, direction)])
        fd = [(p-m)/(2*h*s) for p, m, s in zip(plus, minus, sr)]
        check(fd == matvec(scaled_j, direction), 'Scaled directional derivative')
        for alpha in [Q(1), Q(1, 2), Q(1, 8)]:
            physical = [v+alpha*d for v, d in zip(x, dx)]
            mapped = [s*(v+alpha*d) for s, v, d in zip(sx, y, dy)]
            check(physical == mapped, 'Line-search trial point mapping')
            check(sum((v/s)**2 for v, s in zip(residual(physical), sr)) ==
                  sum((v/s)**2 for v, s in zip(residual(mapped), sr)), 'Weighted merit')
        # Exact preconditioner action transformation: P_hat^-1 = Sx^-1 P^-1 Sr.
        p = [[4, 1, 0], [0, 3, 0], [0, 0, 2]]
        q = list(map(Q, [2, -3, 5]))
        scaled_p = [[v*sx[k]/sr[i] for k, v in enumerate(row)] for i, row in enumerate(p)]
        expected = [v/s for v, s in zip(solve(p, [s*v for s, v in zip(sr, q)]), sx)]
        check(solve(scaled_p, q) == expected, 'Inverse preconditioner mapping')
        a, b, c, d = Q(4), Q(2), Q(3), Q(7)
        ah, bh = a*sx[0]/sr[0], b*sx[1]/sr[0]
        ch, dh = c*sx[0]/sr[1], d*sx[1]/sr[1]
        check(dh-ch*bh/ah == (d-c*b/a)*sx[1]/sr[1], 'Schur mapping')
        if sx != [1, 1, 1]:
            wrong = solve(j, [-v for v in scaled_r])
            check(dx != [s*v for s, v in zip(sx, wrong)], 'Detect residual-only scaling')
            wrong_j = [row[:] for row in scaled_j]
            wrong_j[2][2] = 1
            wrong_dy = solve(wrong_j, [-v for v in scaled_r])
            check(x[2]+sx[2]*wrong_dy[2] != 3, 'Detect unit constraint diagonal')
        checks += 1
    print(f'PASS: {checks} scale sets; Newton, Jv, constraints, trial points, merit, PC and Schur identities; 2 negative controls')


if __name__ == '__main__':
    main()
