#include "eonsim/scalar_p2_space.hpp"
#include <algorithm>
#include <iostream>
#include <set>
#include <stdexcept>
using namespace eonsim;
void require(bool ok){if(!ok)throw std::runtime_error("P2 ownership/adjacency oracle failed");}
int main(){try {
    MeshPartition m;m.topological_dimension=2;
    m.nodes={{17,{0,0,0}},{91,{1,0,0}},{53,{1,1,0}},{29,{0,1,0}}};
    m.cells2={{100,{0,1,2,0},1,3},{200,{0,2,3,0},1,3}};
    m.edges={{1,{0,1},11},{2,{1,2},12},{3,{2,3},13},{4,{3,0},14}};
    auto serial=prepare_scalar_p2_space(m,{0,0},m);require(serial.global==9&&serial.owned==9);
    std::set<GlobalId> owned;
    for(int r=0;r<2;++r){auto local=m;local.rank=r;local.ranks=2;local.cells2={m.cells2[r]};local.edges=r==0?std::vector<BoundaryEdge>{m.edges[0],m.edges[1]}:std::vector<BoundaryEdge>{m.edges[2],m.edges[3]};
        auto s=prepare_scalar_p2_space(m,{0,1},local);require(s.global==9&&s.cells.size()==1&&s.boundaries.size()==2);
        for(std::size_t i=0;i<s.owned;++i){require(s.algebra_ids[i]==s.begin+static_cast<GlobalId>(i));require(owned.insert(s.algebra_ids[i]).second);}
        for(std::size_t i=0;i<s.entities.size();++i)if(s.entities[i]==std::array<GlobalId,2>{17,53}){
            require(s.owners[i]==0);if(r==0)require(s.row_offsets[i+1]-s.row_offsets[i]==9);
        }
        // Vertex 17 carries a boundary tag from the other rank's exterior edge.
        for(std::size_t i=0;i<s.entities.size();++i)if(s.entities[i]==std::array<GlobalId,2>{17,17})require(s.boundary_tags[i]==std::vector<int>({11,14}));
    }
    require(owned.size()==9);
    std::reverse(m.cells2.begin(),m.cells2.end());auto reordered=prepare_scalar_p2_space(m,{0,0},m);
    require(reordered.entities==serial.entities&&reordered.algebra_ids==serial.algebra_ids);
    std::cout<<"P2 entity identities, shared owners, remote adjacency and boundary tags passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
