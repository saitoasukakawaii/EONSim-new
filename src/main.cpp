#include "eonsim/config.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/poisson.hpp"
#include "eonsim/scalar2d.hpp"
#include "eonsim/scalar_p2_space.hpp"
#include "eonsim/fluid.hpp"
#include "eonsim/solid.hpp"
#include "eonsim/ale.hpp"
#include "eonsim/motion.hpp"
#include "eonsim/fsi.hpp"
#include "eonsim/fsi_domains.hpp"
#include "eonsim/vtu.hpp"

#include <array>
#include <charconv>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string_view>

namespace {
std::optional<std::string> option(const char* name)
{
    std::array<char, PETSC_MAX_PATH_LEN> text{};
    PetscBool found = PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetString(nullptr, nullptr, name, text.data(), text.size(), &found));
    if (found) return std::string(text.data());
    return std::nullopt;
}
std::map<int,int> partition_weights(std::string_view text)
{
    std::map<int,int> weights;
    const auto integer=[](std::string_view value) {
        int result=0;
        const auto [end,error]=std::from_chars(value.data(),value.data()+value.size(),result);
        if(value.empty() || error!=std::errc{} || end!=value.data()+value.size())
            throw std::runtime_error("-partition_cell_weights requires tag:positive_cost pairs separated by commas");
        return result;
    };
    do {
        const auto comma=text.find(',');
        const auto item=text.substr(0,comma);
        const auto colon=item.find(':');
        if(colon==std::string_view::npos || item.find(':',colon+1)!=std::string_view::npos)
            throw std::runtime_error("-partition_cell_weights requires tag:positive_cost pairs separated by commas");
        const int tag=integer(item.substr(0,colon)),cost=integer(item.substr(colon+1));
        if(cost<=0 || !weights.emplace(tag,cost).second)
            throw std::runtime_error("-partition_cell_weights requires positive costs and unique physical tags");
        if(comma==std::string_view::npos) break;
        text.remove_prefix(comma+1);
    } while(true);
    return weights;
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
                         "       [-partition_cell_weights tag:cost,...] [-partition_report]\n"
                         "       [-diagnostics basic|full] [-block_pc] [-solver_report] [-fluid_coo|-fsi_coo]\n"
                         "       [-solver_rank_report] [-nonlinear_initial_jacobian_reuse true|false]\n"
                         "       [-fsi_assembly_report] [-fsi_residual_coo true|false] [-fsi_threads N] [-fsi_overlap true|false]\n"
                         "       [-nonlinear_fused_reductions true|false] [-nonlinear_adaptive_pc true|false]\n"
                         "       [-vtu_format ascii|binary|hdf5] [-vtu_boundary true|false] [-vtu_compact_boundary true|false]\n"
                         "       [-checkpoint dir] [-restart dir] [-stop_after N] [PETSc options]\n";
        } else {
            using Clock = std::chrono::steady_clock;
            const auto begin = Clock::now();
            auto config = eonsim::read_config(*case_file);
            eonsim::VtuOptions vtu_options;
            const auto vtu_format=option("-vtu_format").value_or("ascii");
            if(vtu_format!="ascii" && vtu_format!="binary" && vtu_format!="hdf5")
                throw std::runtime_error("-vtu_format must be ascii, binary or hdf5");
            vtu_options.binary=vtu_format=="binary";
            vtu_options.hdf5=vtu_format=="hdf5";
            if(vtu_options.hdf5&&config.scalar2d_problem&&config.scalar2d.degree!=1)
                throw std::runtime_error("Parallel HDF5 output currently requires a P1 scalar space");
            PetscBool vtu_boundary=PETSC_TRUE,vtu_compact=PETSC_TRUE;
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-vtu_boundary",&vtu_boundary,nullptr));
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-vtu_compact_boundary",&vtu_compact,nullptr));
            vtu_options.boundary=vtu_boundary;
            vtu_options.compact_boundary=vtu_compact;
            eonsim::configure_vtu_output(vtu_options,PETSC_COMM_WORLD);
            const auto weight_text=option("-partition_cell_weights");
            PetscBool partition_report=PETSC_FALSE,partition_report_set=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-partition_report",&partition_report,&partition_report_set));
            if(!prepare && (weight_text || partition_report_set))
                throw std::runtime_error("-partition_cell_weights and -partition_report require offline -prepare");
            const auto weights=weight_text?partition_weights(*weight_text):std::map<int,int>{};
            if(rank==0)std::cout << "layout_policy semantic_order=" << config.semantic_order << " storage_order=" << config.storage_order << '\n';
            PetscBool fluid_coo=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fluid_coo",&fluid_coo,nullptr));
            if(fluid_coo&&(!config.fluid_problem||config.fsi_problem||config.motion_problem))
                throw std::runtime_error("-fluid_coo requires the standalone fixed-mesh fluid problem");
            PetscBool fsi_coo=PETSC_FALSE,fsi_assembly_report=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fsi_coo",&fsi_coo,nullptr));
            EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fsi_assembly_report",&fsi_assembly_report,nullptr));
            PetscBool fsi_residual_option=PETSC_FALSE,fsi_thread_option=PETSC_FALSE,fsi_overlap_option=PETSC_FALSE;
            EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-fsi_residual_coo",&fsi_residual_option));
            EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-fsi_threads",&fsi_thread_option));
            EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-fsi_overlap",&fsi_overlap_option));
            if((fsi_coo||fsi_assembly_report||fsi_residual_option||fsi_thread_option||fsi_overlap_option)&&!config.fsi_problem)
                throw std::runtime_error("FSI assembly options require the monolithic FSI problem");
            if(auto path=option("-checkpoint")) config.checkpoint=std::filesystem::absolute(*path);
            if(auto path=option("-restart")) config.restart=std::filesystem::absolute(*path);
            PetscInt stop=0;
            EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-stop_after",&stop,nullptr));
            if(stop<0 || stop>1000000000) throw std::runtime_error("Invalid -stop_after");
            config.stop_after=static_cast<int>(stop);
            if((!config.checkpoint.empty()||!config.restart.empty()||stop) &&
               !((config.scalar2d_problem&&config.scalar2d.transient)||config.fsi_problem || (config.solid_problem&&config.solid.transient) ||
                 (config.fluid_problem&&config.fluid.mode==eonsim::FluidConfig::Mode::transient)||
                 (config.motion_problem&&config.motion.mode!=eonsim::MotionConfig::Mode::rigid)))
                throw std::runtime_error("Checkpoint/restart/stop_after require transient fluid/solid, ALE or FSI");
            if (auto mesh = option("-mesh")) config.mesh = std::filesystem::absolute(*mesh);
            if (auto output = option("-output")) config.output = std::filesystem::absolute(*output);
            if (config.output.extension() != ".vtu" &&
                !(vtu_options.hdf5&&(config.output.extension()==".h5"||config.output.extension()==".xdmf")))
                throw std::runtime_error("output must have a .vtu extension (also .h5/.xdmf with -vtu_format hdf5)");
            const auto diagnostics = option("-diagnostics").value_or("basic");
            if (diagnostics != "basic" && diagnostics != "full") throw std::runtime_error("diagnostics must be basic or full");
            const auto read_mesh=[&] { if(config.scalar2d_problem)return eonsim::read_gmsh2d(config.mesh);return config.fsi_problem&&!config.fsi.domains.solid_mesh.empty()?eonsim::read_fsi_domains(config.mesh,config.fsi.domains):eonsim::read_gmsh22(config.mesh); };
            if (prepare) {
                PetscInt parts = 1;
                EONSIM_PETSC(PetscOptionsGetInt(nullptr, nullptr, "-parts", &parts, nullptr));
                if (parts < 1 || parts > 1000000) throw std::runtime_error("Invalid -parts");
                eonsim::PartitionReport report;
                eonsim::prepare_partitions(read_mesh(), static_cast<int>(parts), *prepare,
                    config.scalar2d_problem?config.scalar2d.degree:1,weights,partition_report?&report:nullptr);
                if(partition_report) {
                    std::cout << std::setprecision(16) << "partition_report ranks=" << parts
                        << " weighted=" << report.weighted << " total_weighted_cost=" << report.total_weighted_cost
                        << " metis_index_max=" << report.metis_index_max
                        << " total_seconds=" << report.total_seconds << " metis_seconds=" << report.metis_seconds
                        << " layout_seconds=" << report.layout_seconds << " write_seconds=" << report.write_seconds << '\n';
                    for(const auto& local:report.ranks) {
                        std::cout << "partition_rank rank=" << local.rank << " cells=" << local.cells
                            << " nodes=" << local.nodes << " owned=" << local.owned_nodes << " ghost=" << local.ghost_nodes
                            << " faces=" << local.faces << " weighted_cost=" << local.weighted_cost << '\n';
                        for(const auto& [tag,cells]:local.cells_by_tag)
                            std::cout << "partition_tag rank=" << local.rank << " tag=" << tag << " cells=" << cells << '\n';
                    }
                }
                std::cout << "Prepared " << parts << " HDF5 partitions in " << *prepare << "\nstatus=success\n";
            } else {
            const auto mesh = partition ? eonsim::read_partition(*partition, rank, size) : read_mesh();
            if(mesh.topological_dimension!=(config.scalar2d_problem?2:3))throw std::runtime_error("Partition topology does not match selected physics");
            std::vector<eonsim::GlobalId> counts(size);
            const eonsim::GlobalId owned = mesh.owned_nodes;
            MPI_Allgather(&owned, 1, MPI_INT64_T, counts.data(), 1, MPI_INT64_T, PETSC_COMM_WORLD);
            std::vector<eonsim::GlobalId> owner_offsets(size+1,0);
            for (int r = 0; r < size; ++r) owner_offsets[r+1]=owner_offsets[r]+counts[r];
            const eonsim::GlobalId owned_start=owner_offsets[rank],total=owner_offsets.back();
            const eonsim::GlobalId local_cells = mesh.topological_dimension==2?mesh.cells2.size():mesh.cells.size();
            eonsim::GlobalId total_cells = 0;
            MPI_Allreduce(&local_cells, &total_cells, 1, MPI_INT64_T, MPI_SUM, PETSC_COMM_WORLD);
            if (total_cells != mesh.global_cells) throw std::runtime_error("Incomplete cell partition");
            std::uint64_t min_hash = 0, max_hash = 0;
            MPI_Allreduce(&mesh.fingerprint, &min_hash, 1, MPI_UINT64_T, MPI_MIN, PETSC_COMM_WORLD);
            MPI_Allreduce(&mesh.fingerprint, &max_hash, 1, MPI_UINT64_T, MPI_MAX, PETSC_COMM_WORLD);
            if (owned_start != mesh.owned_begin || total != mesh.global_nodes || min_hash != max_hash)
                throw std::runtime_error("Inconsistent partition set");
            for (std::size_t n = 0; n < mesh.nodes.size(); ++n) {
                if(mesh.owners[n]<0 || mesh.owners[n]>=size)
                    throw std::runtime_error("Ghost node has an invalid owner");
                const auto owner_begin=owner_offsets[mesh.owners[n]];
                if (mesh.algebra_ids[n] < owner_begin || mesh.algebra_ids[n] >= owner_begin+counts[mesh.owners[n]])
                    throw std::runtime_error("Ghost ID does not belong to its declared owner");
            }
            const double input_seconds = std::chrono::duration<double>(Clock::now()-begin).count();
            if(config.scalar2d_problem) {
                if(config.scalar2d.degree==2) {
                    const auto space=partition?eonsim::read_scalar_p2_space(*partition,mesh):eonsim::prepare_scalar_p2_space(mesh,std::vector<int>(mesh.cells2.size(),0),mesh);
                    eonsim::solve_scalar_p2(PETSC_COMM_WORLD,mesh,space,config);
                } else eonsim::solve_scalar2d(PETSC_COMM_WORLD,mesh,config);
            } else if(config.fsi_problem) {
                const auto fsi=eonsim::solve_fsi(PETSC_COMM_WORLD,mesh,config);
                eonsim::write_fsi_fields(PETSC_COMM_WORLD,config.output,fsi);
                if(rank==0) std::cout << "status=success\n";
            } else if(config.motion_problem) {
                if(config.motion.mode==eonsim::MotionConfig::Mode::rigid) {
                    const auto& m=config.motion;
                    eonsim::RigidState state;
                    eonsim::TimeStepper clock(m.dt,m.steps,config.time_control);
                    while(clock.active()) {
                        state=eonsim::rigid_step({m.mass,m.damping,m.stiffness},state,clock.dt(),m.force); clock.accept();
                        const int step=clock.step;
                        if(rank==0) std::cout << std::setprecision(16) << "rigid_step=" << step
                            << " time=" << clock.time << " position=" << state.position << " velocity=" << state.velocity << '\n';
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
                    std::cout << std::setprecision(16);
                    if(config.solid.boundaries.empty()) {
                        std::cout << "tip_displacement=" << solid.tip_displacement << " reaction_x=" << solid.reaction_x;
                        if(!config.solid.transient && !config.solid.neo_hookean && config.solid.regions.empty())
                            std::cout << " displacement_max_error=" << solid.displacement_error;
                        std::cout << '\n';
                    } else {
                        constexpr char axes[]="xyz";
                        for(const auto& b:solid.boundaries) {
                            std::cout << "solid_boundary_tag=" << b.tag << " reference_area=" << b.reference_area;
                            for(int c=0;c<eonsim::Space3::dimension;++c)
                                std::cout << " mean_displacement_" << axes[c] << '=' << b.mean_displacement[c]
                                    << " mean_velocity_" << axes[c] << '=' << b.mean_velocity[c];
                            for(int c=0;c<eonsim::Space3::dimension;++c) if(b.constrained[c])
                                std::cout << " reaction_" << axes[c] << '=' << b.reaction[c];
                            std::cout << '\n';
                        }
                        for(int c=0;c<eonsim::Space3::dimension;++c)
                            std::cout << (c?" ":"") << "support_reaction_" << axes[c] << '=' << solid.support_reaction[c];
                        std::cout << '\n';
                    }
                    std::cout << "status=success\n";
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
