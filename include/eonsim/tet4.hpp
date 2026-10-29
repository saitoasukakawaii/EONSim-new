#pragma once

#include "eonsim/mesh.hpp"

namespace eonsim {

template<class Element,class Scalar=double> struct SimplexGeometry {
    Scalar volume;
    typename Element::template Nodal<typename Element::Space::template Vector<Scalar>> gradients;
};
using Tet4Geometry=SimplexGeometry<Tet4Topology>;

// SI coordinates, positively oriented physical geometry, local node order 0..3.
// Pure local calculation: no PETSc/MPI, assembly, state mutation, or I/O.
Tet4Geometry tet4_geometry(const Tet4Topology::Nodal<Point>& coordinates);

template<class Layout> struct LinearElementSystem {
    typename Layout::template Matrix<double> stiffness{};
    typename Layout::template State<double> load{};
};
using ElementSystem=LinearElementSystem<Tet4Scalar>;

// -div(k grad u) = f; residual is K*u - load. Constant k and f per element.
ElementSystem poisson_element(const Tet4Geometry& geometry, double diffusivity, double source);

} // namespace eonsim
