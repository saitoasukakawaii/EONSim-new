"""Fully developed rigid-tube response to Im(G*exp(i*omega*t)).

Pande et al., arXiv:2304.00543v2, equations (27)-(28), with a/a0=1.
The dependency-free Bessel series is restricted to 0 <= alpha <= 4 here;
this is a low-frequency verification reference, not a general Bessel library.
"""
import cmath
import math


def bessel_j(order, z):
    if order not in (0, 1) or abs(z) > 4.0000001:
        raise ValueError('Reference series supports J0/J1 with |z| <= 4')
    term = (z/2)**order
    result = term
    for k in range(1, 100):
        term *= -(z*z/4)/(k*(k+order))
        result += term
        if abs(term) < 1e-17*max(1., abs(result)):
            return result
    raise ArithmeticError('Bessel series did not converge')


def velocity_amplitude(r, alpha, radius=1., viscosity=1., gradient=.01, bessel=bessel_j):
    if not 0 <= alpha <= 4 or not radius > 0 or not viscosity > 0:
        raise ValueError('Invalid low-frequency rigid-tube reference')
    if alpha == 0:
        return gradient*(radius*radius-r*r)/(4*viscosity)
    z = cmath.sqrt(-1j)*alpha
    return gradient*radius**2/(1j*viscosity*alpha**2)*(1-bessel(0,z*r/radius)/bessel(0,z))


def flow_amplitude(alpha, radius=1., viscosity=1., gradient=.01, bessel=bessel_j):
    if not 0 <= alpha <= 4 or not radius > 0 or not viscosity > 0:
        raise ValueError('Invalid low-frequency rigid-tube reference')
    if alpha == 0:
        return math.pi*radius**4*gradient/(8*viscosity)
    z = cmath.sqrt(-1j)*alpha
    return math.pi*radius**4*gradient/(1j*viscosity*alpha**2)*(1-2*bessel(1,z)/(z*bessel(0,z)))
