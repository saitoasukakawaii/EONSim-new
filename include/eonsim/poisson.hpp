#pragma once

#include "eonsim/linear_system.hpp"
#include "eonsim/mesh.hpp"

namespace eonsim {

struct PoissonResult {
    LinearResult linear;
    std::vector<double> exact_values;
    std::size_t constrained_dofs = 0;
    double volume = 0.0;
    double solution_integral = 0.0;
    double l2_error = 0.0;
    double h1_seminorm_error = 0.0;
    double boundary_max_error = 0.0;
    double prepare_seconds = 0.0;
    double assembly_seconds = 0.0;
    double solve_seconds = 0.0;
    double error_seconds = 0.0;
};

PoissonResult solve_poisson(MPI_Comm communicator, const MeshPartition& mesh,
                            const Config& config, bool full_diagnostics);

} // namespace eonsim
