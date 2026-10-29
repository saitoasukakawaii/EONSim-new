#include "eonsim/mesh.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace eonsim {
namespace {
std::string line(std::istream& input)
{
    std::string text;
    while (std::getline(input, text)) {
        const auto first = text.find_first_not_of(" \t\r");
        if (first == std::string::npos) continue;
        const auto last = text.find_last_not_of(" \t\r");
        return text.substr(first, last-first+1);
    }
    throw std::runtime_error("Unexpected end of Gmsh file");
}
void expect(std::istream& input, const std::string& wanted)
{
    if (line(input) != wanted) throw std::runtime_error("Expected Gmsh section marker " + wanted);
}
void end_record(std::istringstream& record)
{
    if (!record) throw std::runtime_error("Malformed Gmsh record");
    std::string extra;
    if (record >> extra) throw std::runtime_error("Unexpected data in Gmsh record: " + extra);
}
std::size_t count(std::istream& input)
{
    std::istringstream record(line(input));
    GlobalId value = -1;
    record >> value;
    end_record(record);
    if (value < 0 || value > std::numeric_limits<LocalId>::max())
        throw std::runtime_error("Gmsh count exceeds supported local index range");
    return static_cast<std::size_t>(value);
}

void validate_topology(const MeshPartition& mesh)
{
    if (mesh.nodes.empty() || mesh.cells.empty()) throw std::runtime_error("Mesh must contain nodes and Tet4 cells");
    std::map<std::array<LocalId, 3>, int> faces;
    std::set<std::array<LocalId, 4>> cells;
    std::vector<bool> used(mesh.nodes.size(), false);
    for (const auto& cell : mesh.cells) {
        auto key = cell.nodes;
        std::sort(key.begin(), key.end());
        if (std::adjacent_find(key.begin(), key.end()) != key.end() || !cells.insert(key).second)
            throw std::runtime_error("Repeated node or duplicate Tet4 cell");
        for (auto node : cell.nodes) used[node] = true;
        for (int omitted = 0; omitted < 4; ++omitted) {
            std::array<LocalId, 3> face{};
            int j = 0;
            for (int i = 0; i < 4; ++i) if (i != omitted) face[j++] = cell.nodes[i];
            std::sort(face.begin(), face.end());
            if (++faces[face] > 2) throw std::runtime_error("Non-manifold tetrahedral face");
        }
    }
    if (std::find(used.begin(), used.end(), false) != used.end())
        throw std::runtime_error("Mesh contains nodes not used by any Tet4");
    std::set<std::array<LocalId, 3>> boundary;
    for (const auto& triangle : mesh.boundary) {
        auto face = triangle.nodes;
        std::sort(face.begin(), face.end());
        const auto found = faces.find(face);
        if (found == faces.end() || found->second != 1 || !boundary.insert(face).second)
            throw std::runtime_error("Boundary triangle is duplicate or is not an exterior Tet4 face");
    }
    for (const auto& face : faces)
        if (face.second == 1 && !boundary.count(face.first))
            throw std::runtime_error("Every exterior Tet4 face must have a tagged boundary triangle");
}
} // namespace

MeshPartition read_gmsh22(const std::filesystem::path& path)
{
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot open mesh: " + path.string());
    expect(input, "$MeshFormat");
    std::istringstream format(line(input));
    std::string version;
    int binary = -1, width = 0;
    format >> version >> binary >> width;
    end_record(format);
    if (version != "2.2" || binary != 0 || width != 8)
        throw std::runtime_error("Only Gmsh 2.2 ASCII (2.2 0 8) is supported");
    expect(input, "$EndMeshFormat");
    MeshPartition mesh;
    std::unordered_map<GlobalId, LocalId> local_ids;
    bool have_nodes = false, have_elements = false, have_names = false;
    while (input >> std::ws && input.peek() != std::char_traits<char>::eof()) {
        const auto section = line(input);
        if (section == "$PhysicalNames") {
            if (have_names) throw std::runtime_error("Duplicate PhysicalNames section");
            have_names = true;
            const auto n = count(input);
            for (std::size_t i = 0; i < n; ++i) {
                std::istringstream record(line(input));
                int dimension = -1, tag = 0;
                std::string name;
                record >> dimension >> tag >> std::quoted(name);
                end_record(record);
                if (dimension < 0 || dimension > 3 || tag <= 0 ||
                    !mesh.physical_names.emplace(std::make_pair(dimension, tag), name).second)
                    throw std::runtime_error("Invalid or duplicate physical name");
            }
            expect(input, "$EndPhysicalNames");
        } else if (section == "$Nodes") {
            if (have_nodes) throw std::runtime_error("Duplicate Nodes section");
            have_nodes = true;
            const auto n = count(input);
            mesh.nodes.reserve(n);
            for (std::size_t i = 0; i < n; ++i) {
                std::istringstream record(line(input));
                Node node{};
                record >> node.global_id >> node.position[0] >> node.position[1] >> node.position[2];
                end_record(record);
                if (node.global_id <= 0 || !local_ids.emplace(node.global_id, static_cast<LocalId>(i)).second)
                    throw std::runtime_error("Invalid or duplicate Gmsh node ID");
                for (double coordinate : node.position)
                    if (!std::isfinite(coordinate)) throw std::runtime_error("Non-finite mesh coordinate");
                mesh.nodes.push_back(node);
            }
            expect(input, "$EndNodes");
        } else if (section == "$Elements") {
            if (!have_nodes || have_elements) throw std::runtime_error("Elements must follow one Nodes section");
            have_elements = true;
            const auto n = count(input);
            std::set<GlobalId> element_ids;
            for (std::size_t i = 0; i < n; ++i) {
                std::istringstream record(line(input));
                GlobalId id = 0;
                int type = 0, tag_count = -1;
                record >> id >> type >> tag_count;
                if (!record || id <= 0 || tag_count < 0 || !element_ids.insert(id).second)
                    throw std::runtime_error("Invalid element header or duplicate ID");
                int physical = 0;
                for (int j = 0; j < tag_count; ++j) {
                    int tag = 0;
                    if (!(record >> tag)) throw std::runtime_error("Missing Gmsh element tag");
                    if (j == 0) physical = tag;
                }
                // First-order points/lines may accompany a 3D Gmsh mesh; they carry no volume contribution.
                const int arity = type == 4 ? 4 : type == 2 ? 3 : type == 1 ? 2 : type == 15 ? 1 : 0;
                if (!arity) throw std::runtime_error("Unsupported Gmsh element type " + std::to_string(type));
                std::array<LocalId, 4> connectivity{};
                for (int j = 0; j < arity; ++j) {
                    GlobalId node = 0;
                    if (!(record >> node) || !local_ids.count(node)) throw std::runtime_error("Unknown Gmsh node reference");
                    connectivity[j] = local_ids.at(node);
                }
                end_record(record);
                if ((type == 4 || type == 2) && physical <= 0)
                    throw std::runtime_error("Tet4 and boundary triangles require positive physical tags");
                if (type == 4) mesh.cells.push_back({id, connectivity, physical});
                else if (type == 2) mesh.boundary.push_back({id, {connectivity[0], connectivity[1], connectivity[2]}, physical});
            }
            expect(input, "$EndElements");
        } else throw std::runtime_error("Unsupported Gmsh section: " + section);
    }
    if (!have_elements) throw std::runtime_error("Missing Gmsh Elements section");
    validate_topology(mesh);
    return mesh;
}
} // namespace eonsim
