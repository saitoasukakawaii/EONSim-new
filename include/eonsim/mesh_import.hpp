#pragma once
/** @file Format-independent first-order mesh input; no ownership or FE DoFs. */
#include "eonsim/mesh.hpp"
namespace eonsim {
enum class CellType { point1=15, line2=1, tri3=2, quad4=3, tet4=4 };
int cell_dimension(CellType type);
int cell_vertices(CellType type);
struct ImportElement {
    GlobalId source_id=0;
    CellType type=CellType::point1;
    int entity_tag=0;
    std::vector<int> physical_tags;
    std::vector<LocalId> nodes;
};
/** Coordinates have three components; topology dimension is independent.
 * Connectivity indexes nodes, never external tags. Element vertex ordering is
 * Gmsh's first-order reference ordering. Periodic/parametric/partitioned input
 * and higher-order geometry are explicitly rejected by this reader.
 */
struct MeshImportData {
    std::vector<Node> nodes;
    std::vector<ImportElement> elements;
    std::map<std::pair<int,int>,std::string> physical_names;
    int topological_dimension=0;
    int coordinate_dimension=3;
};
MeshImportData read_gmsh(const std::filesystem::path& path);
}
