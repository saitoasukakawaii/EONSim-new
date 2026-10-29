#include "eonsim/config.hpp"
#include "eonsim/poisson.hpp"
#include "eonsim/fluid.hpp"
#include "eonsim/solid.hpp"
#include "eonsim/ale.hpp"
#include "eonsim/motion.hpp"
#include "eonsim/fsi.hpp"
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
        "EONSim: eonsim -case case.yaml [-mesh mesh.msh] [-output result.vtu] [-diagnostics basic|full]\n")) return 1;
    int status = 0, rank = 0, size = 0;
    if (MPI_Comm_rank(PETSC_COMM_WORLD, &rank) != MPI_SUCCESS || MPI_Comm_size(PETSC_COMM_WORLD, &size) != MPI_SUCCESS) {
        MPI_Abort(PETSC_COMM_WORLD, 1);
        return 1;
    }
    try {
        EONSIM_PETSC(PetscPushErrorHandler(PetscReturnErrorHandler, nullptr));
        const auto partition = option("-partition");
        const auto prepare = option("-prepare");
        if (size != 1 && (!partition || prepare))
            throw std::runtime_error("Multi-rank solve requires -partition; offline -prepare requires one rank");
        const auto case_file = option("-case");
        if (!case_file) {
            std::cout << "Usage: eonsim -case case.yaml [-mesh mesh.msh] [-output result.vtu]\n"
                         "       [-partition directory] [-prepare directory -parts N]\n"
                         "       [-diagnostics basic|full] [-block_pc] [-solver_report]\n"
                         "       [-checkpoint dir] [-restart dir] [-stop_after N] [PETSc options]\n";
        } else {
            using Clock = std::chrono::steady_clock;
            const auto begin = Clock::now();
            auto config = eonsim::read_config(*case_file);
            if(auto path=option("-checkpoint")) config.checkpoint=std::filesystem::absolute(*path);
            if(auto path=option("-restart")) config.restart=std::filesystem::absolute(*path);
            PetscInt stop=0;
            EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-stop_after",&stop,nullptr));
            if(stop<0 || stop>1000000000) throw std::runtime_error("Invalid -stop_after");
            config.stop_after=static_cast<int>(stop);
            if((!config.checkpoint.empty()||!config.restart.empty()||stop) &&
               !(config.fsi_problem || (config.solid_problem&&config.solid.transient) ||
                 (config.fluid_problem&&config.fluid.mode==eonsim::FluidConfig::Mode::transient)))
                throw std::runtime_error("Checkpoint/restart/stop_after require transient fluid/solid or FSI");
            if (auto mesh = option("-mesh")) config.mesh = std::filesystem::absolute(*mesh);
            if (auto output = option("-output")) config.output = std::filesystem::absolute(*output);
            if (config.output.extension() != ".vtu") throw std::runtime_error("output must have a .vtu extension");
            const auto diagnostics = option("-diagnostics").value_or("basic");
            if (diagnostics != "basic" && diagnostics != "full") throw std::runtime_error("diagnostics must be basic or full");
            if (prepare) {
                PetscInt parts = 1;
                EONSIM_PETSC(PetscOptionsGetInt(nullptr, nullptr, "-parts", &parts, nullptr));
                if (parts < 1 || parts > 1000000) throw std::runtime_error("Invalid -parts");
                eonsim::prepare_partitions(eonsim::read_gmsh22(config.mesh), static_cast<int>(parts), *prepare);
                std::cout << "Prepared " << parts << " HDF5 partitions in " << *prepare << "\nstatus=success\n";
            } else {
            const auto mesh = partition ? eonsim::read_partition(*partition, rank, size) : eonsim::read_gmsh22(config.mesh);
            std::vector<eonsim::GlobalId> counts(size);
            const eonsim::GlobalId owned = mesh.owned_nodes;
            MPI_Allgather(&owned, 1, MPI_INT64_T, counts.data(), 1, MPI_INT64_T, PETSC_COMM_WORLD);
            eonsim::GlobalId owned_start = 0, total = 0;
            for (int r = 0; r < size; ++r) { if (r < rank) owned_start += counts[r]; total += counts[r]; }
            const eonsim::GlobalId local_cells = mesh.cells.size();
            eonsim::GlobalId total_cells = 0;
            MPI_Allreduce(&local_cells, &total_cells, 1, MPI_INT64_T, MPI_SUM, PETSC_COMM_WORLD);
            if (total_cells != mesh.global_cells) throw std::runtime_error("Incomplete cell partition");
            std::uint64_t min_hash = 0, max_hash = 0;
            MPI_Allreduce(&mesh.fingerprint, &min_hash, 1, MPI_UINT64_T, MPI_MIN, PETSC_COMM_WORLD);
            MPI_Allreduce(&mesh.fingerprint, &max_hash, 1, MPI_UINT64_T, MPI_MAX, PETSC_COMM_WORLD);
            if (owned_start != mesh.owned_begin || total != mesh.global_nodes || min_hash != max_hash)
                throw std::runtime_error("Inconsistent partition set");
            for (std::size_t n = 0; n < mesh.nodes.size(); ++n) {
                eonsim::GlobalId owner_begin = 0;
                for (int r = 0; r < mesh.owners[n]; ++r) owner_begin += counts[r];
                if (mesh.algebra_ids[n] < owner_begin || mesh.algebra_ids[n] >= owner_begin+counts[mesh.owners[n]])
                    throw std::runtime_error("Ghost ID does not belong to its declared owner");
            }
            const double input_seconds = std::chrono::duration<double>(Clock::now()-begin).count();
            if(config.fsi_problem) {
                const auto fsi=eonsim::solve_fsi(PETSC_COMM_WORLD,mesh,config);
                eonsim::write_fields(config.output,fsi.current_mesh,fsi.fields);
                const auto solid_path=config.output.parent_path()/(config.output.stem().string()+"_solid.vtu");
                if(config.fsi.elastic) eonsim::write_fields(solid_path,fsi.solid_mesh,fsi.solid_fields);
                MPI_Barrier(PETSC_COMM_WORLD);
                if(rank==0) {
                    eonsim::write_field_index(config.output,size,fsi.fields);
                    if(config.fsi.elastic) eonsim::write_field_index(solid_path,size,fsi.solid_fields);
                    std::cout << "status=success\n";
                }
            } else if(config.motion_problem) {
                if(config.motion.mode==eonsim::MotionConfig::Mode::rigid) {
                    const auto& m=config.motion;
                    eonsim::RigidState state;
                    for(int step=1;step<=m.steps;++step) {
                        state=eonsim::rigid_step({m.mass,m.damping,m.stiffness},state,m.dt,m.force);
                        if(rank==0) std::cout << std::setprecision(16) << "rigid_step=" << step
                            << " time=" << step*m.dt << " position=" << state.position << " velocity=" << state.velocity << '\n';
                    }
                    if(rank==0) std::cout << "status=success\n";
                } else {
                    const auto ale=eonsim::solve_ale(PETSC_COMM_WORLD,mesh,config);
                    eonsim::write_fields(config.output,ale.current_mesh,ale.fields);
                    MPI_Barrier(PETSC_COMM_WORLD);
                    if(rank==0) { eonsim::write_field_index(config.output,size,ale.fields); std::cout << "status=success\n"; }
                }
            } else if(config.solid_problem) {
                const auto solid=eonsim::solve_solid(PETSC_COMM_WORLD,mesh,config);
                eonsim::write_fields(config.output,mesh,solid.fields);
                MPI_Barrier(PETSC_COMM_WORLD);
                if(rank==0) {
                    eonsim::write_field_index(config.output,size,solid.fields);
                    std::cout << std::setprecision(16) << "tip_displacement=" << solid.tip_displacement
                        << " reaction_x=" << solid.reaction_x;
                    if(!config.solid.transient && !config.solid.neo_hookean && config.solid.boundaries.empty() && config.solid.regions.empty()) std::cout << " displacement_max_error=" << solid.displacement_error;
                    std::cout << "\nstatus=success\n";
                }
            } else if(config.fluid_problem) {
                const auto fluid=eonsim::solve_fluid(PETSC_COMM_WORLD,mesh,config);
                eonsim::write_fields(config.output,mesh,fluid.fields);
                MPI_Barrier(PETSC_COMM_WORLD);
                if(rank==0) {
                    eonsim::write_field_index(config.output,size,fluid.fields);
                    std::cout << std::setprecision(16);
                    if(config.fluid.boundaries.empty()) {
                        std::cout << std::setprecision(16) << "inlet_flow=" << fluid.inlet_flow
                            << " outlet_flow=" << fluid.outlet_flow << " pressure_drop=" << fluid.pressure_drop
                            << " velocity_l2_error=" << fluid.velocity_error << " divergence_l2=" << fluid.divergence
                            << "\nstatus=success\n";
                    } else {
                        double net=0;
                        for(const auto& b:fluid.boundaries) {
                            net+=b.flow;
                            std::cout << "boundary_tag=" << b.tag << " area=" << b.area << " outward_flow=" << b.flow
                                << " mean_pressure=" << b.pressure << '\n';
                        }
                        std::cout << "net_outward_flow=" << net << " divergence_l2=" << fluid.divergence << "\nstatus=success\n";
                    }
                }
            } else {
            const auto result = eonsim::solve_poisson(PETSC_COMM_WORLD, mesh, config, diagnostics == "full");
            const auto output_begin = Clock::now();
            eonsim::write_vtu(config.output, mesh, result.linear.values, result.exact_values);
            MPI_Barrier(PETSC_COMM_WORLD);
            if (rank == 0) eonsim::write_pvtu(config.output, size);
            const double output_seconds = std::chrono::duration<double>(Clock::now()-output_begin).count();
            char version[256]{};
            EONSIM_PETSC(PetscGetVersion(version, sizeof(version)));
            std::array<char, MPI_MAX_LIBRARY_VERSION_STRING> mpi_version{};
            int mpi_length = 0;
            if (MPI_Get_library_version(mpi_version.data(), &mpi_length) != MPI_SUCCESS)
                throw std::runtime_error("MPI_Get_library_version failed");
            EONSIM_PETSC(PetscSynchronizedPrintf(PETSC_COMM_WORLD, "rank=%d local_nodes=%zu local_cells=%zu owned=%zu ghost=%zu\n",
                rank, mesh.nodes.size(), mesh.cells.size(), mesh.owned_nodes, mesh.nodes.size()-mesh.owned_nodes));
            EONSIM_PETSC(PetscSynchronizedFlush(PETSC_COMM_WORLD, PETSC_STDOUT));
            eonsim::GlobalId boundary_faces = mesh.boundary.size(), total_faces = 0;
            MPI_Allreduce(&boundary_faces, &total_faces, 1, MPI_INT64_T, MPI_SUM, PETSC_COMM_WORLD);
            double local_times[] = {input_seconds, result.prepare_seconds, result.assembly_seconds, result.solve_seconds, result.error_seconds, output_seconds};
            double max_times[6]{};
            MPI_Allreduce(local_times, max_times, 6, MPI_DOUBLE, MPI_MAX, PETSC_COMM_WORLD);
            if (rank == 0) std::cout << std::setprecision(16)
                << "EONSim P1 | build=" << EONSIM_BUILD_TYPE << " MHPC_DEBUG=" << MHPC_DEBUG << " ranks=" << size << '\n'
                << version << '\n' << mpi_version.data() << '\n'
                << "PETSc scalar=real-double index_bits=" << 8*sizeof(PetscInt)
                << " mesh_id_bits=" << 8*sizeof(eonsim::GlobalId) << '\n'
                << "thread_limits OMP=" << std::getenv("OMP_NUM_THREADS")
                << " OPENBLAS=" << std::getenv("OPENBLAS_NUM_THREADS") << " MKL=" << std::getenv("MKL_NUM_THREADS") << '\n'
                << "case=" << std::filesystem::absolute(*case_file) << " mesh=" << config.mesh << '\n'
                << "nodes=" << mesh.global_nodes << " cells=" << mesh.global_cells << " boundary_faces=" << total_faces
                << " owned=" << mesh.global_nodes << " constrained=" << result.constrained_dofs
                << " nnz=" << result.linear.nonzeros << '\n'
                << "ksp=" << result.linear.ksp_type << " pc=" << result.linear.pc_type
                << " reason=" << result.linear.reason << " iterations=" << result.linear.iterations << '\n'
                << "rtol=" << result.linear.relative_tolerance << " atol=" << result.linear.absolute_tolerance
                << " true_residual=" << result.linear.true_residual << " rhs_norm=" << result.linear.rhs_norm << '\n'
                << "volume=" << result.volume << " solution_integral=" << result.solution_integral
                << " l2_error=" << result.l2_error << " h1_seminorm_error=" << result.h1_seminorm_error
                << " boundary_max_error=" << result.boundary_max_error << '\n'
                << "seconds(max_rank) input=" << max_times[0] << " prepare=" << max_times[1]
                << " assembly=" << max_times[2] << " solve=" << max_times[3]
                << " error=" << max_times[4] << " output=" << max_times[5] << '\n'
                << "output=" << config.output << "\nstatus=success\n";
            }
            }
        }
    } catch (const std::exception& error) {
        std::cerr << "EONSim rank " << rank << ": " << error.what() << "\nstatus=failed\n";
        status = 1;
        if (size > 1) MPI_Abort(PETSC_COMM_WORLD, status);
    }
    // Successful ranks finalize together; unrecoverable distributed failures abort the job.
    if (PetscFinalize()) status = 1;
    return status;
}
