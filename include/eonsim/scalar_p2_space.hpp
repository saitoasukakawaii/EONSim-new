#pragma once
#include "eonsim/mesh.hpp"
namespace eonsim {
/** A nodal field space on straight triangles; geometry remains in MeshPartition.
 * Entity endpoints use imported vertex IDs. Equal endpoints denote a vertex;
 * unequal sorted endpoints denote one edge midpoint. No coordinate matching.
 */
struct ScalarP2Space {
    GlobalId global=0,begin=0;
    std::size_t owned=0;
    std::vector<std::array<GlobalId,2>> entities;
    std::vector<Point> points;
    std::vector<int> owners;
    std::vector<GlobalId> algebra_ids, entity_ids;
    std::vector<std::vector<int>> boundary_tags;
    std::vector<std::array<LocalId,6>> cells;
    std::vector<std::array<LocalId,3>> boundaries;
    std::vector<GlobalId> row_offsets,row_columns;
};
/** Offline preparation only. cell_owners aligns with global.cells2; local cell
 * and boundary ordering follows local. Full remote-cell adjacency is retained
 * for owned rows even when that cell is integrated by another rank.
 */
ScalarP2Space prepare_scalar_p2_space(const MeshPartition& global,
                                    const std::vector<int>& cell_owners,
                                    const MeshPartition& local);
void save_scalar_p2_space(const std::filesystem::path& directory,const MeshPartition& mesh,const ScalarP2Space& space);
ScalarP2Space read_scalar_p2_space(const std::filesystem::path& directory,const MeshPartition& mesh);
}
