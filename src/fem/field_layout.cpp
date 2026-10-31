#include "eonsim/field_layout.hpp"
#include <limits>
#include <set>
#include <stdexcept>

namespace eonsim {
AlgebraLayout make_field_layout(const MeshPartition& mesh, int components,
                               const std::map<std::string, std::vector<int>>& groups,
                               const std::vector<ComponentMeaning>& meanings) {
    if(!meanings.empty() && meanings.size()!=static_cast<std::size_t>(components))
        throw std::runtime_error("Semantic component count differs from field layout");
    if (components < 1 || mesh.global_nodes > std::numeric_limits<PetscInt>::max()/components)
        throw std::runtime_error("Field size exceeds PETSc index range");
    std::set<int> seen;
    for (const auto& group : groups) for (int c : group.second)
        if (c < 0 || c >= components || !seen.insert(c).second) throw std::runtime_error("Invalid field component grouping");
    if (seen.size() != static_cast<std::size_t>(components)) throw std::runtime_error("Field groups must cover every component");
    AlgebraLayout layout;
    layout.owned = mesh.owned_nodes*components; layout.global = mesh.global_nodes*components; layout.begin = mesh.owned_begin*components;
    for (auto id : mesh.algebra_ids) for (int c = 0; c < components; ++c) layout.local_to_global.push_back(id*components+c);
    for (std::size_t i = 0; i < mesh.owned_nodes; ++i) {
        PetscInt diagonal = 0, other = 0;
        for (GlobalId j = mesh.row_offsets[i]; j < mesh.row_offsets[i+1]; ++j) {
            auto col = mesh.row_columns[j];
            if (col >= mesh.owned_begin && col < mesh.owned_begin+static_cast<GlobalId>(mesh.owned_nodes)) diagonal += components;
            else other += components;
        }
        for (int c = 0; c < components; ++c) { layout.diagonal.push_back(diagonal); layout.off_diagonal.push_back(other); }
    }
    for (const auto& group : groups) {
        auto& ids = layout.fields[group.first];
        for (std::size_t n = 0; n < mesh.owned_nodes; ++n) for (int c : group.second) ids.push_back(mesh.algebra_ids[n]*components+c);
    }
    for(std::size_t n=0;n<mesh.owned_nodes;++n) for(const auto& meaning:meanings)
        layout.owned_semantics.push_back({mesh.nodes[n].global_id,meaning.domain,meaning.quantity,
            DofEntity::vertex,meaning.component,0,meaning.space});
    return layout;
}
} // namespace eonsim
