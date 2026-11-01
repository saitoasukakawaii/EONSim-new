#include "eonsim/scalar_p2_space.hpp"
#include <algorithm>
#include <limits>
#include <set>
#include <stdexcept>
namespace eonsim {
ScalarP2Space prepare_scalar_p2_space(const MeshPartition& mesh,const std::vector<int>& cell_owners,const MeshPartition& local) {
    using Key=std::array<GlobalId,2>;
    if(mesh.topological_dimension!=2||cell_owners.size()!=mesh.cells2.size()||local.rank<0||local.rank>=local.ranks)
        throw std::runtime_error("Invalid P2 preparation input");
    struct Entity {Point point{};int owner;GlobalId algebra=0;std::set<int> tags;std::set<Key> neighbors;};
    std::map<Key,Entity> entities;
    auto key=[&](LocalId a,LocalId b) {Key k{mesh.nodes.at(a).global_id,mesh.nodes.at(b).global_id};std::sort(k.begin(),k.end());return k;};
    std::map<GlobalId,std::array<Key,6>> cells;
    std::map<GlobalId,std::array<Key,3>> boundaries;
    for(std::size_t ci=0;ci<mesh.cells2.size();++ci) {
        const auto& c=mesh.cells2[ci];const int owner=cell_owners[ci];
        if(c.vertices!=3||owner<0||owner>=local.ranks)throw std::runtime_error("P2 requires Tri3 cells and valid owners");
        std::array<Key,6> keys;
        for(int a=0;a<3;++a){keys[a]=key(c.nodes[a],c.nodes[a]);keys[a+3]=key(c.nodes[a],c.nodes[(a+1)%3]);}
        if(!cells.emplace(c.global_id,keys).second)throw std::runtime_error("Duplicate P2 cell ID");
        for(int a=0;a<6;++a) {
            Point point{};const int u=a<3?a:a-3,v=a<3?a:(a-2)%3;
            for(int d=0;d<3;++d)point[d]=.5*mesh.nodes.at(c.nodes[u]).position[d]+.5*mesh.nodes.at(c.nodes[v]).position[d];
            auto entry=entities.emplace(keys[a],Entity{point,owner,0,{},{}}).first;
            entry->second.owner=std::min(entry->second.owner,owner);
            entry->second.neighbors.insert(keys.begin(),keys.end());
        }
    }
    for(const auto& b:mesh.edges) {
        const std::array<Key,3> keys{key(b.nodes[0],b.nodes[0]),key(b.nodes[1],b.nodes[1]),key(b.nodes[0],b.nodes[1])};
        if(!boundaries.emplace(b.global_id,keys).second)throw std::runtime_error("Duplicate P2 boundary ID");
        for(const auto& k:keys)entities.at(k).tags.insert(b.physical_tag);
    }
    std::map<Key,GlobalId> stable_ids;GlobalId edge_id=0;
    for(const auto& e:entities)stable_ids[e.first]=e.first[0]==e.first[1]?e.first[0]:edge_id++;
    ScalarP2Space result;
    for(int rank=0;rank<local.ranks;++rank) {
        if(rank==local.rank)result.begin=result.global;
        for(auto& e:entities)if(e.second.owner==rank){e.second.algebra=result.global++;if(rank==local.rank)++result.owned;}
    }
    std::set<Key> needed;
    for(const auto& c:local.cells2){const auto& keys=cells.at(c.global_id);needed.insert(keys.begin(),keys.end());}
    for(const auto& e:entities)if(e.second.owner==local.rank)needed.insert(e.first);
    if(needed.size()>static_cast<std::size_t>(std::numeric_limits<LocalId>::max()))throw std::runtime_error("P2 local index overflow");
    std::map<Key,LocalId> indices;
    for(bool owned:{true,false})for(const auto& k:needed) {
        const auto& e=entities.at(k);if((e.owner==local.rank)!=owned)continue;
        indices[k]=static_cast<LocalId>(result.points.size());result.entities.push_back(k);result.entity_ids.push_back(stable_ids.at(k));result.points.push_back(e.point);
        result.owners.push_back(e.owner);result.algebra_ids.push_back(e.algebra);result.boundary_tags.emplace_back(e.tags.begin(),e.tags.end());
    }
    for(const auto& c:local.cells2) {std::array<LocalId,6> dofs{};const auto& keys=cells.at(c.global_id);for(int i=0;i<6;++i)dofs[i]=indices.at(keys[i]);result.cells.push_back(dofs);}
    for(const auto& b:local.edges) {std::array<LocalId,3> dofs{};const auto& keys=boundaries.at(b.global_id);for(int i=0;i<3;++i)dofs[i]=indices.at(keys[i]);result.boundaries.push_back(dofs);}
    result.row_offsets={0};
    for(std::size_t i=0;i<result.owned;++i) {
        std::vector<GlobalId> columns;
        for(const auto& k:entities.at(result.entities[i]).neighbors)columns.push_back(entities.at(k).algebra);
        std::sort(columns.begin(),columns.end());result.row_columns.insert(result.row_columns.end(),columns.begin(),columns.end());result.row_offsets.push_back(result.row_columns.size());
    }
    return result;
}
}
