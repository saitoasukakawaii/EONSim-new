#pragma once

#include "eonsim/mesh.hpp"

namespace eonsim {
// Writes volume solution and a companion *_boundary.vtu containing physical tags.
void write_vtu(const std::filesystem::path& path, const MeshPartition& mesh,
               const std::vector<double>& values, const std::vector<double>& exact);
} // namespace eonsim
