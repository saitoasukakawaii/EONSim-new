#pragma once

#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

namespace eonsim {

using GlobalId = std::int64_t;
using LocalId = std::int32_t;
using Point = std::array<double, 3>;

struct Node { GlobalId global_id; Point position; };
struct Tet4 { GlobalId global_id; std::array<LocalId, 4> nodes; int physical_tag; };
struct BoundaryTriangle { GlobalId global_id; std::array<LocalId, 3> nodes; int physical_tag; };

// P0: one rank owns every entity. P1 will supply genuinely local partition input.
// Connectivity uses compact local IDs; original Gmsh IDs remain stable and separate.
struct MeshPartition {
    std::vector<Node> nodes;
    std::vector<Tet4> cells;
    std::vector<BoundaryTriangle> boundary;
    std::map<std::pair<int, int>, std::string> physical_names;
};

MeshPartition read_gmsh22(const std::filesystem::path& path);

struct ScalarDofMap {
    // Compact scalar algebra numbering, distinct from original node global_id.
    std::vector<GlobalId> local_to_algebra;
    std::vector<LocalId> dirichlet_nodes;
    std::vector<double> dirichlet_values;
};

} // namespace eonsim
