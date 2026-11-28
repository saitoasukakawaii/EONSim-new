// Recover the storage identities for a captured cold-start, dual-domain tube system.
#include "eonsim/config.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/reduced_layout.hpp"
#include <petscsys.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
std::ofstream open_output(const std::filesystem::path& directory, const std::string& name) {
    std::ofstream stream;
    stream.exceptions(std::ios::badbit | std::ios::failbit);
    stream.open(directory / name);
    stream << std::setprecision(17);
    return stream;
}

void export_layout(const char* input, const char* partition, const char* output, int rank, int size) {
    auto config = eonsim::read_config(input);
    auto domains = config.fsi.domains;
    if (!config.fsi.inlet || domains.solid_mesh.empty() || domains.rcr_outlets.size() != 1)
        throw std::runtime_error("Expected the frozen elastic tube with one inlet and one RCR port");
    // Match the inlet lifting in the time-step driver before constructing the production layout.
    const int inlet = config.fsi.inlet->tag;
    domains.fluid_constraints.push_back({inlet, {0, 1, 2}});
    domains.mesh_constraints.push_back({inlet, {0, 1, 2}});
    const auto mesh = eonsim::read_partition(partition, rank, size);
    const auto reduced = eonsim::make_dual_fsi_layout(PETSC_COMM_WORLD, mesh, domains, false);
    const auto& algebra = reduced.algebra;
    const std::string suffix = "-" + std::to_string(rank) + ".csv";
    auto rows = open_output(output, "rows" + suffix);
    rows << "row,field,entity,kind,component,interface\n";
    for (const auto& field : algebra.fields) {
        for (const auto row : field.second) {
            const auto offset = row - algebra.begin;
            const auto& key = algebra.owned_semantics.at(offset);
            rows << row << ',' << field.first << ',' << key.entity << ',' << int(key.kind)
                 << ',' << key.component << ',' << int(algebra.owned_interface.at(offset)) << '\n';
        }
    }
    rows.close();
    auto slots = open_output(output, "slots" + suffix);
    slots << "joined_node,owner,interface,u,v,w,p,mesh_x,mesh_y,mesh_z,solid_vx,solid_vy,solid_vz\n";
    if (reduced.components != 10) throw std::runtime_error("Unexpected active component layout");
    for (std::size_t n = 0; n < mesh.nodes.size(); ++n) {
        slots << mesh.nodes[n].global_id << ',' << mesh.owners[n] << ',' << int(reduced.interface_nodes[n]);
        for (int k = 0; k < reduced.components; ++k)
            slots << ',' << reduced.global.at(n * reduced.components + k);
        slots << '\n';
    }
    slots.close();
    if (rank == 0) {
        auto port = open_output(output, "port.csv");
        port << "rows,pressure_row,tag,initial_capacitor_pressure,dt\n"
             << algebra.global << ',' << reduced.outlets.front().pressure << ',' << domains.rcr_outlets.front().tag
             << ',' << domains.rcr_outlets.front().initial_capacitor_pressure << ',' << config.fsi.dt << '\n';
        port.close();
    }
}
}

int main(int argc, char** argv) {
    if (argc != 4) return 2;
    if (PetscInitialize(&argc, &argv, nullptr, nullptr)) return 1;
    int rank, size;
    MPI_Comm_rank(PETSC_COMM_WORLD, &rank);
    MPI_Comm_size(PETSC_COMM_WORLD, &size);
    try {
        export_layout(argv[1], argv[2], argv[3], rank, size);
    } catch (const std::exception& error) {
        std::cerr << "layout rank " << rank << ": " << error.what() << '\n';
        MPI_Abort(PETSC_COMM_WORLD, 1);
    }
    return PetscFinalize();
}
