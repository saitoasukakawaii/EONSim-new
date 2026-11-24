"""Axisymmetric Q2/Q1 fluid and Q2 wall reference for the two-ended pressure ramp."""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu

from reference import integrate


@dataclass(frozen=True)
class TubeParameters:
    radius: float = 1.0
    outer_radius: float = 1.2
    length: float = 2.0
    fluid_density: float = 1.0
    solid_density: float = 1.0
    viscosity: float = 1.0
    young: float = 100.0
    poisson: float = 0.3
    support_stiffness: float = 0.0
    support_damping: float = 0.0

    def lame_area_strain(self, pressure):
        a, b = self.radius, self.outer_radius
        factor = (1 + self.poisson) / (self.young * (b*b - a*a))
        u_due_inner = factor * b * a*a * (2 - 2*self.poisson) * pressure
        u_due_unit_outer = -factor * b * ((1 - 2*self.poisson)*b*b + a*a)
        outer = self.support_stiffness * u_due_inner / (1 - self.support_stiffness*u_due_unit_outer)
        return 2 * factor * ((1 - 2*self.poisson)*(a*a*pressure-b*b*outer) + b*b*(pressure-outer))


def quadratic(s):
    return np.array([(1-s)*(1-2*s), 4*s*(1-s), s*(2*s-1)])


def derivative(s):
    return np.array([4*s-3, 4-8*s, 4*s-1])


def number(mask, start):
    indices = np.full(mask.shape, -1, dtype=np.int64)
    count = int(np.count_nonzero(mask))
    indices[mask] = np.arange(start, start + count)
    return indices, start + count


class SparseAssembly:
    """Assemble repeated element matrices over one axial column of cells at a time."""

    def __init__(self, size):
        self.size = size
        self.blocks = []

    def add(self, row_dofs, col_dofs, matrix):
        row, col = np.nonzero(matrix)
        rows = row_dofs[:, row]
        cols = col_dofs[:, col]
        keep = (rows >= 0) & (cols >= 0)
        values = np.broadcast_to(matrix[row, col], rows.shape)
        self.blocks.append((rows[keep], cols[keep], values[keep]))

    def finish(self):
        rows, cols, values = (np.concatenate(entry) for entry in zip(*self.blocks))
        result = sparse.coo_matrix((values, (rows, cols)), shape=(self.size, self.size)).tocsc()
        result.eliminate_zeros()
        self.blocks.clear()
        return result


def element(radial_start, dr, dx, quadrature, solid, material):
    """Matrices per radian. Local Q2 indices run first along r, then along x."""
    mass = np.zeros((18, 18))
    stiffness = np.zeros_like(mass)
    divergence = np.zeros((4, 18))
    shear = material.young / (2 * (1 + material.poisson)) if solid else material.viscosity
    lame = 2 * shear * material.poisson / (1 - 2 * material.poisson) if solid else 0.0
    density = material.solid_density if solid else material.fluid_density
    for x, wx in quadrature:
        for r, wr in quadrature:
            radius = radial_start + r * dr
            weight = wx * wr * dx * dr * radius
            q2 = np.outer(quadratic(x), quadratic(r)).ravel()
            grad_x = np.outer(derivative(x), quadratic(r)).ravel() / dx
            grad_r = np.outer(quadratic(x), derivative(r)).ravel() / dr
            hoop = q2 / radius
            strain = np.zeros((4, 18))
            strain[0, 0::2] = grad_x
            strain[1, 1::2] = grad_r
            strain[2, 1::2] = hoop
            strain[3, 0::2] = grad_r / np.sqrt(2)
            strain[3, 1::2] = grad_x / np.sqrt(2)
            div = strain[:3].sum(axis=0)
            scalar_mass = density * weight * np.outer(q2, q2)
            mass[0::2, 0::2] += scalar_mass
            mass[1::2, 1::2] += scalar_mass
            stiffness += 2 * shear * weight * (strain.T @ strain)
            if solid:
                stiffness += lame * weight * np.outer(div, div)
            else:
                q1 = np.outer([1-x, x], [1-r, r]).ravel()
                divergence += weight * np.outer(q1, div)
    return mass, stiffness, divergence


def graded_widths(length, count, corner_levels):
    """Split the first interval towards its end at coordinate zero."""
    h = length/count
    first = [h/2**corner_levels, *(h/2**i for i in range(corner_levels,0,-1))]
    return np.array(first + [h]*(count-1))


class MeridianTube:
    def __init__(self, nx, fluid_radial, wall_radial, quadrature_order, material, corner_levels=0, full_length=False, section_count=7):
        self.material = material
        self.full_length = full_length
        widths = graded_widths(material.length/2, nx, corner_levels)
        if full_length:
            widths = np.concatenate((widths, widths[::-1]))
        self.x_bounds = np.concatenate(([0.], np.cumsum(widths)))
        nx = len(widths)
        fluid_widths = graded_widths(material.radius, fluid_radial, corner_levels)[::-1]
        wall_widths = graded_widths(material.outer_radius-material.radius, wall_radial, corner_levels)
        radial_widths = np.concatenate((fluid_widths,wall_widths))
        bounds = np.concatenate(([0.],np.cumsum(radial_widths)))
        fluid_radial = len(fluid_widths)
        bore = self.bore = 2 * fluid_radial
        shape = (2*nx+1, 2*(len(bounds)-1)+1, 2)
        free = np.ones(shape, dtype=bool)
        free[:, 0, 1] = False          # Regularity on the rotation axis.
        free[-1, bore if full_length else 0:, 0] = False  # Roller or midplane axial symmetry.
        free[0, bore:, 0] = False      # Axial wall roller at the loaded end.
        velocity, self.nv = number(free, 0)
        pressure, start = number(np.ones((nx+1, fluid_radial+1), dtype=bool), self.nv)
        free[:, :bore, :] = False
        displacement, self.size = number(free, start)
        self.displacement = displacement
        self.solid_d = displacement[free]
        self.solid_v = velocity[free]
        self.pressure = pressure.ravel()
        gauss, weights = np.polynomial.legendre.leggauss(quadrature_order)
        quadrature = list(zip((gauss+1)/2, weights/2))
        m = SparseAssembly(self.size)
        k = SparseAssembly(self.size)
        self.load = np.zeros(self.size)
        self.wall_load = np.zeros(self.size)
        xs = 2*np.arange(nx)[:, None, None] + np.arange(3)[None, :, None]
        px = np.arange(nx)[:, None, None] + np.arange(2)[None, :, None]
        for j, dr in enumerate(radial_widths):
            rs = 2*j + np.arange(3)[None, None, :]
            v = velocity[xs, rs].reshape(nx, 18)
            solid = j >= fluid_radial
            if solid:
                d = displacement[xs, rs].reshape(nx, 18)
            else:
                pr = j + np.arange(2)[None, None, :]
                p = pressure[px, pr].reshape(nx, 4)
                ends = ((0, 1), (-1,-1)) if full_length else ((0, 1),)
                for end, sign in ends:
                    ids = velocity[end, 2*j:2*j+3, 0]
                    for r, w in quadrature:
                        nodal_force = quadratic(r) * (bounds[j] + dr*r) * dr * w
                        np.add.at(self.load, ids[ids >= 0], sign*nodal_force[ids >= 0])
            for dx in np.unique(widths):
                group = widths == dx
                mass, stiffness, divergence = element(bounds[j], dr, dx, quadrature, solid, material)
                m.add(v[group],v[group],mass)
                if solid:
                    k.add(v[group],d[group],stiffness)
                else:
                    k.add(v[group],v[group],stiffness)
                    k.add(p[group],v[group],divergence)
                    k.add(v[group],p[group],-divergence.T)
        for i in range(nx):
            ids = velocity[2*i:2*i+3, bore, 1]
            for x, w in quadrature:
                np.add.at(self.wall_load, ids, material.radius*widths[i]*w*quadratic(x))
        if material.support_stiffness or material.support_damping:
            outer_v = velocity[xs[:,:,0], -1, 1]
            outer_d = displacement[xs[:,:,0], -1, 1]
            face_mass = sum(w*np.outer(quadratic(x),quadratic(x)) for x,w in quadrature)
            for dx in np.unique(widths):
                group = widths == dx
                matrix = dx * material.outer_radius * face_mass
                k.add(outer_v[group],outer_d[group],material.support_stiffness*matrix)
                k.add(outer_v[group],outer_v[group],material.support_damping*matrix)
        self.mass = m.finish()
        self.operator = k.finish()
        shape = (self.size, self.size)
        ones = np.ones(len(self.solid_d))
        self.mass += sparse.csc_matrix((ones, (self.solid_d, self.solid_d)), shape=shape)
        self.operator -= sparse.csc_matrix((ones, (self.solid_d, self.solid_v)), shape=shape)
        self.kinetic_mass = self.mass[:self.nv, :self.nv]
        self.viscous = self.operator[:self.nv, :self.nv]
        self.elastic = self.operator[self.solid_v][:, self.solid_d].tocsc()
        self.positions = np.linspace(0, material.length, section_count).tolist()

    def sections(self, state):
        result = []
        ids = self.displacement[:, self.bore, 1]
        for x in self.positions:
            if not self.full_length:
                x = min(x,self.material.length-x)
            i = np.clip(np.searchsorted(self.x_bounds,x,side="right")-1,0,len(self.x_bounds)-2)
            local = (x-self.x_bounds[i])/(self.x_bounds[i+1]-self.x_bounds[i])
            radial = quadratic(local) @ state[ids[2*i:2*i+3]]
            result.append(float(2*radial/self.material.radius))
        return result

    def hydrostatic_check(self):
        field = np.zeros(self.size)
        field[self.pressure] = 1.0
        field[self.solid_d] = splu(self.elastic).solve(self.wall_load[self.solid_v])
        residual = float(np.linalg.norm(self.operator @ field - self.load, np.inf))
        exact = self.material.lame_area_strain(1.0)
        area_error = float(np.max(np.abs(np.array(self.sections(field))/exact - 1)))
        if residual > 5e-10 or area_error > 1e-3:
            raise ValueError(f"Hydrostatic equilibrium failed: residual={residual}, area error={area_error}")
        return dict(equilibrium_residual=residual, relative_lame_area_error=area_error)


class StageBalance:
    """Check mass conservation and the power balance at every collocation stage."""

    def __init__(self, tube, pressure):
        self.tube = tube
        self.pressure = pressure
        self.power = self.power_error = 0.0
        self.flux = self.flux_error = 0.0

    def __call__(self, time, state, rate):
        t = self.tube
        v, acceleration = state[:t.nv], rate[:t.nv]
        wall_d, wall_rate = state[t.solid_d], rate[t.solid_d]
        influx = float(t.load[:t.nv] @ v)
        expansion_rate = float(t.wall_load[:t.nv] @ v)
        load = self.pressure * time**3 * (10-15*time+6*time**2)
        power = load * influx
        rate_energy = v @ (t.kinetic_mass @ acceleration) + wall_rate @ (t.elastic @ wall_d)
        viscous_power = v @ (t.viscous @ v)
        self.power = max(self.power, abs(power))
        self.power_error = max(self.power_error, abs(rate_energy + viscous_power - power))
        self.flux = max(self.flux, abs(influx))
        self.flux_error = max(self.flux_error, abs(influx - expansion_rate))

    def report(self):
        power = self.power_error / self.power
        mass = self.flux_error / self.flux
        if not np.all(np.isfinite([power, mass])) or max(power, mass) > 1e-7:
            raise ValueError(f"Stage balance failed: relative power={power}, relative flux={mass}")
        return dict(peak_pressure_power_per_radian=self.power, peak_influx_per_radian=self.flux,
                    max_power_residual_over_peak=power, max_flux_residual_over_peak=mass)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--mesh", nargs=3, type=int, metavar=("AXIAL_HALF", "FLUID_RADIAL", "WALL_RADIAL"), required=True)
    cli.add_argument("--quadrature", type=int, default=5)
    cli.add_argument("--corner-levels",type=int,default=0,
                     help="Dyadically split the end cell and cells adjoining the fluid-wall interface")
    cli.add_argument("--section-count",type=int,default=7,help="Number of equally spaced output stations, including both end caps")
    cli.add_argument("--full-length",action="store_true",help="Solve both loaded ends without imposing midplane symmetry")
    cli.add_argument("--support",type=float,nargs=2,metavar=("STIFFNESS","DAMPING"),default=(0.,0.))
    cli.add_argument("--steps", nargs="+", type=int, required=True)
    cli.add_argument("--pressure", type=float, default=0.02)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--stage-solver",choices=("real-block","complex-pair"),default="real-block")
    args = cli.parse_args()
    if min(args.mesh) < 1 or args.quadrature < 3 or any(n < 2 or n % 2 for n in args.steps):
        cli.error("Positive mesh counts, quadrature of at least order 3, and positive even step counts required")
    if not np.isfinite(args.pressure) or args.pressure <= 0:
        cli.error("Peak pressure must be finite and positive")
    if args.section_count<3 or args.section_count%2!=1:
        cli.error("Use an odd number of at least three stations to retain the midplane")
    if args.corner_levels < 0 or not np.all(np.isfinite(args.support)) or min(args.support)<0:
        cli.error("Corner subdivision levels and both support coefficients must be nonnegative")
    material = TubeParameters(support_stiffness=args.support[0],support_damping=args.support[1])
    tube = MeridianTube(*args.mesh, args.quadrature, material,args.corner_levels,args.full_length,args.section_count)
    result = dict(parameters=asdict(material), mesh=args.mesh, quadrature=args.quadrature,
                  corner_levels=args.corner_levels,full_length=args.full_length,stage_solver=args.stage_solver,stage_refinement_steps=int(args.stage_solver=="complex-pair"),
                  unknowns=tube.size, pressure=args.pressure, sections=tube.positions,
                  static=tube.hydrostatic_check(), runs=[])
    for n in args.steps:
        balance = StageBalance(tube, args.pressure)
        row = integrate(tube, n, args.pressure, observe=balance,stage_solver=args.stage_solver)
        row.update(balance.report())
        result["runs"].append(row)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
        print(n, row["samples"][-1]["section_area_strain"], flush=True)


if __name__ == "__main__":
    main()
