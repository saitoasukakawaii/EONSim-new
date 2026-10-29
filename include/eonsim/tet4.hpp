#pragma once

#include "eonsim/mesh.hpp"

namespace eonsim {

struct Tet4Geometry {
    double volume;
    std::array<Point, 4> gradients;
};

// SI coordinates, positively oriented physical geometry, local node order 0..3.
// Pure local calculation: no PETSc/MPI, assembly, state mutation, or I/O.
Tet4Geometry tet4_geometry(const std::array<Point, 4>& coordinates);

struct ElementSystem {
    std::array<double, 16> stiffness; // row-major
    std::array<double, 4> load;
};

// -div(k grad u) = f; residual is K*u - load. Constant k and f per element.
ElementSystem poisson_element(const Tet4Geometry& geometry, double diffusivity, double source);

} // namespace eonsim
