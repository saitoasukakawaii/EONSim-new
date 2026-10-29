#include "eonsim/tet4.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace eonsim {
namespace {
Point cross(const Point& a, const Point& b)
{
    return {a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]};
}
double dot(const Point& a, const Point& b)
{
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
}
} // namespace

Tet4Geometry tet4_geometry(const std::array<Point, 4>& x)
{
    std::array<Point, 3> edges{};
    double scale = 0.0;
    for (int i = 0; i < 3; ++i) {
        for (int d = 0; d < 3; ++d) {
            edges[i][d] = x[i+1][d] - x[0][d];
            scale = std::max(scale, std::abs(edges[i][d]));
        }
    }
    if (!std::isfinite(scale) || scale == 0.0) throw std::runtime_error("Degenerate Tet4 geometry");
    for (auto& edge : edges) for (auto& component : edge) component /= scale;
    const auto c12 = cross(edges[1], edges[2]);
    const double determinant = dot(edges[0], c12);
    if (!std::isfinite(determinant) || determinant <= 128.0 * std::numeric_limits<double>::epsilon())
        throw std::runtime_error("Inverted or degenerate Tet4: positive Jacobian required");
    Tet4Geometry geometry{};
    geometry.volume = determinant * scale * scale * scale / 6.0;
    if (!std::isfinite(geometry.volume) || geometry.volume <= 0.0)
        throw std::runtime_error("Tet4 volume is not representable");
    geometry.gradients[1] = c12;
    geometry.gradients[2] = cross(edges[2], edges[0]);
    geometry.gradients[3] = cross(edges[0], edges[1]);
    for (int i = 1; i < 4; ++i) {
        for (int d = 0; d < 3; ++d) {
            geometry.gradients[i][d] /= determinant * scale;
            if (!std::isfinite(geometry.gradients[i][d])) throw std::runtime_error("Invalid Tet4 gradient");
            geometry.gradients[0][d] -= geometry.gradients[i][d];
        }
    }
    return geometry;
}

ElementSystem poisson_element(const Tet4Geometry& geometry, double diffusivity, double source)
{
    ElementSystem result{};
    for (int i = 0; i < 4; ++i) {
        result.load[i] = source * geometry.volume / 4.0;
        for (int j = 0; j < 4; ++j)
            result.stiffness[4*i+j] = diffusivity * geometry.volume * dot(geometry.gradients[i], geometry.gradients[j]);
    }
    return result;
}
} // namespace eonsim
