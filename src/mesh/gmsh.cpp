#include "eonsim/mesh.hpp"
#include "eonsim/mesh_import.hpp"
#include "eonsim/element2d.hpp"

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
void validate_topology(const MeshPartition& mesh)
{
    if (mesh.nodes.empty() || mesh.cells.empty()) throw std::runtime_error("Mesh must contain nodes and Tet4 cells");
    std::map<Tri3Topology::Nodal<LocalId>, int> faces;
    std::set<Tet4Topology::Nodal<LocalId>> cells;
    std::vector<bool> used(mesh.nodes.size(), false);
    for (const auto& cell : mesh.cells) {
        auto key = cell.nodes;
        std::sort(key.begin(), key.end());
        if (std::adjacent_find(key.begin(), key.end()) != key.end() || !cells.insert(key).second)
            throw std::runtime_error("Repeated node or duplicate Tet4 cell");
        for (auto node : cell.nodes) used[node] = true;
        for (int omitted = 0; omitted < Tet4Topology::faces; ++omitted) {
            Tri3Topology::Nodal<LocalId> face{};
            int j = 0;
            for (int i = 0; i < Tet4Topology::nodes; ++i) if (i != omitted) face[j++] = cell.nodes[i];
            std::sort(face.begin(), face.end());
            if (++faces[face] > 2) throw std::runtime_error("Non-manifold tetrahedral face");
        }
    }
    if (std::find(used.begin(), used.end(), false) != used.end())
        throw std::runtime_error("Mesh contains nodes not used by any Tet4");
    std::set<Tri3Topology::Nodal<LocalId>> boundary;
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
    const auto input=read_gmsh(path);
    if(input.topological_dimension!=3) throw std::runtime_error("Tet4 solver requires a three-dimensional mesh");
    MeshPartition mesh; mesh.nodes=input.nodes; mesh.physical_names=input.physical_names;
    for(const auto& e:input.elements) {
        if(e.type==CellType::point1||e.type==CellType::line2) continue;
        if(e.physical_tags.size()!=1) throw std::runtime_error("Tet4 and boundary triangles require exactly one positive physical tag");
        if(e.type==CellType::tet4) mesh.cells.push_back({e.source_id,{e.nodes[0],e.nodes[1],e.nodes[2],e.nodes[3]},e.physical_tags[0]});
        else if(e.type==CellType::tri3) mesh.boundary.push_back({e.source_id,{e.nodes[0],e.nodes[1],e.nodes[2]},e.physical_tags[0]});
        else throw std::runtime_error("Unsupported topology in Tet4 volume mesh");
    }
    validate_topology(mesh);
    initialize_serial_partition(mesh);
    return mesh;
}
MeshPartition read_gmsh2d(const std::filesystem::path& path) {
    const auto input=read_gmsh(path);
    if(input.topological_dimension!=2) throw std::runtime_error("Scalar 2D requires Tri3/Quad4 domain cells");
    MeshPartition mesh; mesh.topological_dimension=2; mesh.nodes=input.nodes; mesh.physical_names=input.physical_names;
    const double z=mesh.nodes.front().position[2];
    for(const auto& n:mesh.nodes) if(std::abs(n.position[2]-z)>1e-12)
        throw std::runtime_error("Scalar 2D currently requires a constant-z XY plane");
    std::map<std::array<LocalId,2>,std::vector<std::array<LocalId,2>>> edges;
    std::set<std::vector<LocalId>> cells;
    std::vector<bool> used(mesh.nodes.size(),false);
    for(const auto& e:input.elements) {
        if(e.type==CellType::point1) continue;
        if(e.physical_tags.size()!=1) throw std::runtime_error("Scalar cells and boundary edges require exactly one physical group");
        const int tag=e.physical_tags[0];
        if(e.type==CellType::line2) { mesh.edges.push_back({e.source_id,{e.nodes[0],e.nodes[1]},tag}); continue; }
        Cell2D c{e.source_id,{},tag,cell_vertices(e.type)};
        std::copy(e.nodes.begin(),e.nodes.end(),c.nodes.begin());
        auto key=e.nodes; std::sort(key.begin(),key.end());
        if(!cells.insert(key).second) throw std::runtime_error("Duplicate 2D cell");
        // Normalize clockwise input without changing the cell type or splitting it.
        double area=0;
        for(int i=0;i<c.vertices;++i) {
            const auto& a=mesh.nodes[c.nodes[i]].position; const auto& b=mesh.nodes[c.nodes[(i+1)%c.vertices]].position;
            const auto& o=mesh.nodes[c.nodes[0]].position;
            area+=(a[0]-o[0])*(b[1]-o[1])-(b[0]-o[0])*(a[1]-o[1]);
        }
        if(area<0) std::reverse(c.nodes.begin()+1,c.nodes.begin()+c.vertices);
        std::array<Point,4> xyz{};
        for(int i=0;i<c.vertices;++i) { xyz[i]=mesh.nodes[c.nodes[i]].position; used[c.nodes[i]]=true; }
        validate2d(xyz,c.vertices);
        for(int i=0;i<c.vertices;++i) {
            std::array<LocalId,2> edge{c.nodes[i],c.nodes[(i+1)%c.vertices]},sorted=edge;
            std::sort(sorted.begin(),sorted.end()); auto& adjacent=edges[sorted];
            adjacent.push_back(edge);
            if(adjacent.size()>2||(adjacent.size()==2&&adjacent[0]==adjacent[1]))
                throw std::runtime_error("Non-manifold or overlapping 2D edge");
        }
        mesh.cells2.push_back(c);
    }
    if(mesh.cells2.empty()||std::find(used.begin(),used.end(),false)!=used.end()) throw std::runtime_error("Unused node or empty 2D domain");
    std::set<std::array<LocalId,2>> boundary;
    for(auto& e:mesh.edges) {
        auto key=e.nodes; std::sort(key.begin(),key.end()); const auto it=edges.find(key);
        if(it==edges.end()||it->second.size()!=1||!boundary.insert(key).second)
            throw std::runtime_error("Boundary edge is duplicate or not exterior");
        e.nodes=it->second.front(); // CCW cell edge: outward normal is (dy,-dx).
    }
    for(const auto& e:edges) if(e.second.size()==1&&!boundary.count(e.first))
        throw std::runtime_error("Every exterior 2D edge needs a boundary tag; nonconforming interfaces are unsupported");
    // One connected scalar domain gives the advertised one-dimensional pure
    // Neumann nullspace. Disconnected components need separate nullspace modes.
    std::vector<std::vector<LocalId>> adjacent(mesh.nodes.size());
    for(const auto& edge:edges) { adjacent[edge.first[0]].push_back(edge.first[1]);adjacent[edge.first[1]].push_back(edge.first[0]); }
    std::vector<LocalId> pending{0};std::vector<bool> visited(mesh.nodes.size(),false);visited[0]=true;
    for(std::size_t i=0;i<pending.size();++i)for(auto n:adjacent[pending[i]])if(!visited[n]) {visited[n]=true;pending.push_back(n);}
    if(pending.size()!=mesh.nodes.size())throw std::runtime_error("Scalar 2D currently requires one connected domain");
    initialize_serial_partition(mesh);
    return mesh;
}
} // namespace eonsim
