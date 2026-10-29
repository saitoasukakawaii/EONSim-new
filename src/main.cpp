#include "eonsim/config.hpp"
#include "eonsim/poisson.hpp"
#include "eonsim/vtu.hpp"

#include <array>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>

namespace {
std::optional<std::string> option(const char* name)
{
    std::array<char, PETSC_MAX_PATH_LEN> text{};
    PetscBool found = PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr, nullptr, name, text.data(), text.size(), &found));
    if (found) return std::string(text.data());
    return std::nullopt;
}
void default_threads(const char* name)
{
    if (std::getenv(name)) return;
#ifdef _WIN32
    if (_putenv_s(name, "1") != 0) throw std::runtime_error("Cannot set thread default");
#else
    if (setenv(name, "1", 0) != 0) throw std::runtime_error("Cannot set thread default");
#endif
}
} // namespace

int main(int argc, char* argv[])
{
    try {
        default_threads("OMP_NUM_THREADS");
        default_threads("OPENBLAS_NUM_THREADS");
        default_threads("MKL_NUM_THREADS");
    } catch (const std::exception& error) {
        std::cerr << "EONSim: " << error.what() << '\n';
        return 1;
    }
    if (PetscInitialize(&argc, &argv, nullptr,
        "EONSim P0: eonsim -case case.yaml [-mesh mesh.msh] [-output result.vtu] [-diagnostics basic|full]\n")) return 1;
    int status = 0, rank = 0, size = 0;
    if (MPI_Comm_rank(PETSC_COMM_WORLD, &rank) != MPI_SUCCESS || MPI_Comm_size(PETSC_COMM_WORLD, &size) != MPI_SUCCESS) {
        MPI_Abort(PETSC_COMM_WORLD, 1);
        return 1;
    }
    try {
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler, nullptr));
        // Reject before reading input: no full-grid replication masquerading as MPI support.
        if (size != 1) throw std::runtime_error("P0 currently supports exactly one MPI rank; P1 distributed input and assembly are not implemented");
        const auto case_file = option("-case");
        if (!case_file) {
            std::cout << "Usage: eonsim -case case.yaml [-mesh mesh.msh] [-output result.vtu]\n"
                         "       [-diagnostics basic|full] [PETSc -ksp_* / -pc_* options]\n";
        } else {
            using Clock = std::chrono::steady_clock;
            const auto begin = Clock::now();
            auto config = eonsim::read_config(*case_file);
            if (auto mesh = option("-mesh")) config.mesh = std::filesystem::absolute(*mesh);
            if (auto output = option("-output")) config.output = std::filesystem::absolute(*output);
            if (config.output.extension() != ".vtu") throw std::runtime_error("output must have a .vtu extension");
            const auto diagnostics = option("-diagnostics").value_or("basic");
            if (diagnostics != "basic" && diagnostics != "full") throw std::runtime_error("diagnostics must be basic or full");
            const auto mesh = eonsim::read_gmsh22(config.mesh);
            const double input_seconds = std::chrono::duration<double>(Clock::now()-begin).count();
            const auto result = eonsim::solve_poisson(PETSC_COMM_WORLD, mesh, config, diagnostics == "full");
            const auto output_begin = Clock::now();
            eonsim::write_vtu(config.output, mesh, result.linear.values, result.exact_values);
            const double output_seconds = std::chrono::duration<double>(Clock::now()-output_begin).count();
            char version[256]{};
            EONSIM_PETSC(PetscGetVersion(version, sizeof(version)));
            std::array<char, MPI_MAX_LIBRARY_VERSION_STRING> mpi_version{};
            int mpi_length = 0;
            if (MPI_Get_library_version(mpi_version.data(), &mpi_length) != MPI_SUCCESS)
                throw std::runtime_error("MPI_Get_library_version failed");
            std::cout << std::setprecision(16)
                << "EONSim P0 | build=" << EONSIM_BUILD_TYPE << " MHPC_DEBUG=" << MHPC_DEBUG << " ranks=" << size << '\n'
                << version << '\n' << mpi_version.data() << '\n'
                << "PETSc scalar=real-double index_bits=" << 8*sizeof(PetscInt)
                << " mesh_id_bits=" << 8*sizeof(eonsim::GlobalId) << '\n'
                << "thread_limits OMP=" << std::getenv("OMP_NUM_THREADS")
                << " OPENBLAS=" << std::getenv("OPENBLAS_NUM_THREADS") << " MKL=" << std::getenv("MKL_NUM_THREADS") << '\n'
                << "case=" << std::filesystem::absolute(*case_file) << " mesh=" << config.mesh << '\n'
                << "nodes=" << mesh.nodes.size() << " cells=" << mesh.cells.size() << " boundary_faces=" << mesh.boundary.size()
                << " owned=" << mesh.nodes.size() << " ghost=0 constrained=" << result.constrained_dofs
                << " nnz=" << result.linear.nonzeros << '\n'
                << "ksp=" << result.linear.ksp_type << " pc=" << result.linear.pc_type
                << " reason=" << result.linear.reason << " iterations=" << result.linear.iterations << '\n'
                << "rtol=" << result.linear.relative_tolerance << " atol=" << result.linear.absolute_tolerance
                << " true_residual=" << result.linear.true_residual << " rhs_norm=" << result.linear.rhs_norm << '\n'
                << "volume=" << result.volume << " solution_integral=" << result.solution_integral
                << " l2_error=" << result.l2_error << " h1_seminorm_error=" << result.h1_seminorm_error
                << " boundary_max_error=" << result.boundary_max_error << '\n'
                << "seconds input=" << input_seconds << " prepare=" << result.prepare_seconds
                << " assembly=" << result.assembly_seconds << " solve=" << result.solve_seconds
                << " error=" << result.error_seconds << " output=" << output_seconds << '\n'
                << "output=" << config.output << "\nstatus=success\n";
        }
    } catch (const std::exception& error) {
        if (rank == 0) std::cerr << "EONSim: " << error.what() << "\nstatus=failed\n";
        status = 1;
    }
    // All ranks take the same early rejection path; the solver only runs at size=1.
    if (PetscFinalize()) status = 1;
    return status;
}
