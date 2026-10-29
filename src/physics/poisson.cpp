#include "eonsim/poisson.hpp"
#include "eonsim/tet4.hpp"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <limits>
#include <numeric>
#include <set>
#include <stdexcept>

namespace eonsim {
namespace {
using Clock = std::chrono::steady_clock;
double seconds(Clock::time_point begin) { return std::chrono::duration<double>(Clock::now()-begin).count(); }

double exact_value(ExactSolution solution, const Point& x)
{
    double value = 1.0 + x[0] + 2.0*x[1] + 3.0*x[2];
    if (solution == ExactSolution::quadratic) value += x[0]*x[0] + 2.0*x[1]*x[1] + 3.0*x[2]*x[2];
    return value;
}
Point exact_gradient(ExactSolution solution, const Point& x)
{
    if (solution == ExactSolution::quadratic) return {1.0+2.0*x[0], 2.0+4.0*x[1], 3.0+6.0*x[2]};
    return {1.0, 2.0, 3.0};
}

ScalarDofMap make_dofs(const MeshPartition& mesh, const Config& config)
{
    if (mesh.nodes.size() > static_cast<std::size_t>(std::numeric_limits<PetscInt>::max()))
        throw std::runtime_error("Mesh exceeds the index range of this PETSc build");
    ScalarDofMap dofs;
    dofs.local_to_algebra.resize(mesh.nodes.size());
    std::iota(dofs.local_to_algebra.begin(), dofs.local_to_algebra.end(), GlobalId{0});
    std::set<int> available;
    std::set<int> requested(config.dirichlet_tags.begin(), config.dirichlet_tags.end());
    std::vector<bool> constrained(mesh.nodes.size(), false);
    for (const auto& face : mesh.boundary) {
        available.insert(face.physical_tag);
        if (!requested.count(face.physical_tag))
            throw std::runtime_error("P0 manufactured cases require Dirichlet data on every exterior face");
        for (auto node : face.nodes) constrained[node] = true;
    }
    for (int tag : requested)
        if (!available.count(tag)) throw std::runtime_error("Dirichlet physical tag absent from mesh: " + std::to_string(tag));
    for (std::size_t i = 0; i < constrained.size(); ++i) {
        if (constrained[i]) {
            dofs.dirichlet_nodes.push_back(static_cast<LocalId>(i));
            dofs.dirichlet_values.push_back(exact_value(config.exact_solution, mesh.nodes[i].position));
            if (!std::isfinite(dofs.dirichlet_values.back())) throw std::runtime_error("Non-finite boundary value");
        }
    }
    return dofs;
}

void evaluate_errors(const MeshPartition& mesh, const std::vector<Tet4Geometry>& geometry,
                     ExactSolution solution, PoissonResult& result)
{
    // Tensor Gauss-4 under a Duffy map to the reference tetrahedron. This
    // integrates the squared quadratic error exactly (including the Jacobian).
    constexpr double q[] = {0.06943184420297371, 0.33000947820757187, 0.6699905217924281, 0.9305681557970262};
    constexpr double w[] = {0.17392742256872692, 0.32607257743127307, 0.32607257743127307, 0.17392742256872692};
    double l2_squared = 0.0, h1_squared = 0.0;
    for (std::size_t cell_index = 0; cell_index < mesh.cells.size(); ++cell_index) {
        const auto& cell = mesh.cells[cell_index];
        const auto& geo = geometry[cell_index];
        Point gradient{};
        double average = 0.0;
        for (int a = 0; a < 4; ++a) {
            const double value = result.linear.values[cell.nodes[a]];
            average += value / 4.0;
            for (int d = 0; d < 3; ++d) gradient[d] += value * geo.gradients[a][d];
        }
        result.volume += geo.volume;
        result.solution_integral += geo.volume * average;
        for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) for (int k = 0; k < 4; ++k) {
            const double r = q[i], s = q[j], t = q[k];
            const double shape[] = {(1-r)*(1-s)*(1-t), r, (1-r)*s, (1-r)*(1-s)*t};
            Point x{};
            double value = 0.0;
            for (int a = 0; a < 4; ++a) {
                value += shape[a] * result.linear.values[cell.nodes[a]];
                for (int d = 0; d < 3; ++d) x[d] += shape[a] * mesh.nodes[cell.nodes[a]].position[d];
            }
            const double weight = 6.0 * geo.volume * w[i]*w[j]*w[k] * (1-r)*(1-r)*(1-s);
            const double error = value - exact_value(solution, x);
            l2_squared += weight * error * error;
            const auto exact_grad = exact_gradient(solution, x);
            for (int d = 0; d < 3; ++d) h1_squared += weight * (gradient[d]-exact_grad[d])*(gradient[d]-exact_grad[d]);
        }
    }
    result.l2_error = std::sqrt(l2_squared);
    result.h1_seminorm_error = std::sqrt(h1_squared);
    if (!std::isfinite(result.volume) || !std::isfinite(result.solution_integral) ||
        !std::isfinite(result.l2_error) || !std::isfinite(result.h1_seminorm_error))
        throw std::runtime_error("Non-finite manufactured-solution diagnostic");
}
} // namespace

PoissonResult solve_poisson(MPI_Comm communicator, const MeshPartition& mesh,
                            const Config& config, bool full_diagnostics)
{
    PoissonResult result;
    auto start = Clock::now();
    const auto dofs = make_dofs(mesh, config);
    result.constrained_dofs = dofs.dirichlet_nodes.size();
    std::vector<std::vector<LocalId>> graph(mesh.nodes.size());
    std::vector<Tet4Geometry> geometry;
    geometry.reserve(mesh.cells.size());
    for (const auto& cell : mesh.cells) {
        std::array<Point, 4> coordinates{};
        for (int a = 0; a < 4; ++a) {
            const auto local = cell.nodes[a];
#if MHPC_DEBUG
            assert(local >= 0 && static_cast<std::size_t>(local) < mesh.nodes.size());
#endif
            coordinates[a] = mesh.nodes[local].position;
            graph[local].insert(graph[local].end(), cell.nodes.begin(), cell.nodes.end());
        }
        try { geometry.push_back(tet4_geometry(coordinates)); }
        catch (const std::exception& error) {
            throw std::runtime_error("Tet4 " + std::to_string(cell.global_id) + ": " + error.what());
        }
    }
    std::vector<PetscInt> row_nonzeros;
    row_nonzeros.reserve(graph.size());
    for (auto& row : graph) {
        std::sort(row.begin(), row.end());
        row.erase(std::unique(row.begin(), row.end()), row.end());
        row_nonzeros.push_back(static_cast<PetscInt>(row.size()));
    }
    LinearSystem system(communicator, row_nonzeros);
    result.prepare_seconds = seconds(start);
    start = Clock::now();
    const double source = config.exact_solution == ExactSolution::quadratic ? -12.0 * config.diffusivity : 0.0;
    if (!std::isfinite(source)) throw std::runtime_error("Non-finite Poisson source");
    for (std::size_t c = 0; c < mesh.cells.size(); ++c) {
        std::array<PetscInt, 4> indices{};
        for (int a = 0; a < 4; ++a) indices[a] = static_cast<PetscInt>(dofs.local_to_algebra[mesh.cells[c].nodes[a]]);
        const auto element = poisson_element(geometry[c], config.diffusivity, source);
        for (double value : element.stiffness)
            if (!std::isfinite(value)) throw std::runtime_error("Non-finite element stiffness");
        for (double value : element.load)
            if (!std::isfinite(value)) throw std::runtime_error("Non-finite element load");
        system.add(4, indices.data(), element.stiffness.data(), element.load.data());
    }
    std::vector<PetscInt> boundary_ids;
    for (auto local : dofs.dirichlet_nodes) boundary_ids.push_back(static_cast<PetscInt>(dofs.local_to_algebra[local]));
    system.constrain(boundary_ids, dofs.dirichlet_values);
    result.assembly_seconds = seconds(start);
    start = Clock::now();
    result.linear = system.solve(config.solver, full_diagnostics);
    result.solve_seconds = seconds(start);
    start = Clock::now();
    result.exact_values.reserve(mesh.nodes.size());
    for (const auto& node : mesh.nodes) result.exact_values.push_back(exact_value(config.exact_solution, node.position));
    for (std::size_t i = 0; i < dofs.dirichlet_nodes.size(); ++i)
        result.boundary_max_error = std::max(result.boundary_max_error,
            std::abs(result.linear.values[dofs.dirichlet_nodes[i]] - dofs.dirichlet_values[i]));
    evaluate_errors(mesh, geometry, config.exact_solution, result);
    result.error_seconds = seconds(start);
    return result;
}
} // namespace eonsim
