#include "eonsim/mesh_import.hpp"
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
int cell_dimension(CellType t) {
    switch(t) { case CellType::point1:return 0; case CellType::line2:return 1;
        case CellType::tri3:case CellType::quad4:return 2; case CellType::tet4:return 3; }
    throw std::runtime_error("Unknown cell topology");
}
int cell_vertices(CellType t) {
    switch(t) { case CellType::point1:return 1; case CellType::line2:return 2;
        case CellType::tri3:return 3; case CellType::quad4:case CellType::tet4:return 4; }
    throw std::runtime_error("Unknown cell topology");
}
namespace {
template<class T> T take(std::istream& in) {
    T value{}; if(!(in>>value)) throw std::runtime_error("Malformed or truncated Gmsh input"); return value;
}
std::size_t count(std::istream& in) {
    const auto n=take<GlobalId>(in);
    if(n<0||n>std::numeric_limits<LocalId>::max()) throw std::runtime_error("Gmsh count exceeds local index range");
    return static_cast<std::size_t>(n);
}
void expect(std::istream& in,const std::string& marker) {
    if(take<std::string>(in)!=marker) throw std::runtime_error("Expected Gmsh marker "+marker);
}
CellType topology(int code) {
    switch(code) { case 15:return CellType::point1; case 1:return CellType::line2;
        case 2:return CellType::tri3; case 3:return CellType::quad4; case 4:return CellType::tet4; }
    throw std::runtime_error("Unsupported Gmsh topology/order: element type "+std::to_string(code));
}
}
MeshImportData read_gmsh(const std::filesystem::path& path) {
    std::ifstream in(path); if(!in) throw std::runtime_error("Cannot open mesh: "+path.string());
    expect(in,"$MeshFormat"); const auto version=take<std::string>(in);
    const int binary=take<int>(in),width=take<int>(in);
    if((version!="2.2"&&version!="4.1")||binary!=0||width!=8)
        throw std::runtime_error("Supported Gmsh formats: 2.2/4.1 ASCII, data size 8");
    expect(in,"$EndMeshFormat"); const bool v4=version=="4.1";
    MeshImportData mesh;
    std::unordered_map<GlobalId,LocalId> lookup;
    std::map<std::pair<int,int>,std::vector<int>> entities;
    std::set<std::string> sections;
    std::set<GlobalId> element_ids;
    const auto node=[&](GlobalId id) {
        Node n{id,{}};
        for(auto& x:n.position) { x=take<double>(in); if(!std::isfinite(x)) throw std::runtime_error("Non-finite coordinate"); }
        if(id<=0||!lookup.emplace(id,mesh.nodes.size()).second) throw std::runtime_error("Invalid or duplicate node ID");
        mesh.nodes.push_back(n);
    };
    const auto element=[&](GlobalId id,CellType type,int entity,const std::vector<int>& tags) {
        if(id<=0||!element_ids.insert(id).second) throw std::runtime_error("Invalid or duplicate element ID");
        ImportElement e{id,type,entity,tags,{}};
        for(int a=0;a<cell_vertices(type);++a) {
            const auto external=take<GlobalId>(in); const auto it=lookup.find(external);
            if(it==lookup.end()) throw std::runtime_error("Unknown Gmsh node reference");
            e.nodes.push_back(it->second);
        }
        auto unique=e.nodes; std::sort(unique.begin(),unique.end());
        if(std::adjacent_find(unique.begin(),unique.end())!=unique.end()) throw std::runtime_error("Repeated cell vertex");
        mesh.topological_dimension=std::max(mesh.topological_dimension,cell_dimension(type));
        mesh.elements.push_back(std::move(e));
    };
    while(in>>std::ws&&in.peek()!=std::char_traits<char>::eof()) {
        const auto section=take<std::string>(in);
        if(!sections.insert(section).second) throw std::runtime_error("Duplicate Gmsh section: "+section);
        if(section=="$PhysicalNames") {
            const auto n=count(in);
            for(std::size_t i=0;i<n;++i) {
                const int dim=take<int>(in),tag=take<int>(in); std::string name;
                if(!(in>>std::quoted(name))||dim<0||dim>3||tag<=0||name.empty()||
                   !mesh.physical_names.emplace(std::make_pair(dim,tag),name).second)
                    throw std::runtime_error("Invalid physical name");
            }
            expect(in,"$EndPhysicalNames");
        } else if(section=="$Entities"&&v4) {
            std::array<std::size_t,4> numbers{}; for(auto& n:numbers)n=count(in);
            for(int dim=0;dim<4;++dim) for(std::size_t i=0;i<numbers[dim];++i) {
                const int tag=take<int>(in);
                for(int k=0;k<(dim==0?3:6);++k) if(!std::isfinite(take<double>(in))) throw std::runtime_error("Non-finite entity bounds");
                std::vector<int> physical; const auto n=count(in);
                for(std::size_t k=0;k<n;++k) { int p=take<int>(in); if(p<=0) throw std::runtime_error("Invalid physical tag"); physical.push_back(p); }
                std::sort(physical.begin(),physical.end());
                if(std::adjacent_find(physical.begin(),physical.end())!=physical.end()||tag<=0||
                   !entities.emplace(std::make_pair(dim,tag),physical).second) throw std::runtime_error("Invalid or duplicate entity");
                if(dim>0) { const auto b=count(in); for(std::size_t k=0;k<b;++k) (void)take<int>(in); }
            }
            expect(in,"$EndEntities");
        } else if(section=="$Nodes") {
            if(!v4) { const auto n=count(in); for(std::size_t i=0;i<n;++i)node(take<GlobalId>(in)); }
            else {
                const auto blocks=count(in),n=count(in); const auto low=take<GlobalId>(in),high=take<GlobalId>(in);
                for(std::size_t b=0;b<blocks;++b) {
                    const int dim=take<int>(in),entity=take<int>(in),parametric=take<int>(in); const auto size=count(in);
                    if(dim<0||dim>3||entity<=0||parametric!=0) throw std::runtime_error("Unsupported parametric nodes or invalid node block");
                    if(!entities.empty()&&!entities.count({dim,entity})) throw std::runtime_error("Unknown node entity");
                    if(size>n-mesh.nodes.size()) throw std::runtime_error("Node block count mismatch");
                    std::vector<GlobalId> tags(size); for(auto& id:tags)id=take<GlobalId>(in);
                    for(auto id:tags)node(id);
                }
                if(mesh.nodes.size()!=n||n==0) throw std::runtime_error("Node count mismatch");
                GlobalId actual_low=mesh.nodes[0].global_id,actual_high=actual_low;
                for(const auto& p:mesh.nodes) { actual_low=std::min(actual_low,p.global_id); actual_high=std::max(actual_high,p.global_id); }
                if(actual_low!=low||actual_high!=high) throw std::runtime_error("Node tag bounds mismatch");
            }
            expect(in,"$EndNodes");
        } else if(section=="$Elements") {
            if(mesh.nodes.empty()) throw std::runtime_error("Elements require preceding nodes");
            if(!v4) {
                const auto n=count(in);
                for(std::size_t i=0;i<n;++i) {
                    const auto id=take<GlobalId>(in); const auto type=topology(take<int>(in)); const auto nt=count(in);
                    if(nt>2) throw std::runtime_error("Gmsh 2.2 partition/extra element tags are unsupported");
                    int entity=0; std::vector<int> physical;
                    for(std::size_t k=0;k<nt;++k) { const int t=take<int>(in); if(k==0&&t>0)physical.push_back(t); if(k==1)entity=t; }
                    element(id,type,entity,physical);
                }
            } else {
                const auto blocks=count(in),n=count(in); const auto low=take<GlobalId>(in),high=take<GlobalId>(in);
                for(std::size_t b=0;b<blocks;++b) {
                    const int dim=take<int>(in),entity=take<int>(in); const auto type=topology(take<int>(in)); const auto size=count(in);
                    if(dim!=cell_dimension(type)||entity<=0) throw std::runtime_error("Element block dimension mismatch");
                    const auto found=entities.find({dim,entity});
                    if(found==entities.end()) throw std::runtime_error("Gmsh 4.1 elements require declared Entities and physical groups");
                    if(size>n-mesh.elements.size()) throw std::runtime_error("Element block count mismatch");
                    for(std::size_t i=0;i<size;++i)element(take<GlobalId>(in),type,entity,found->second);
                }
                if(element_ids.size()!=n||n==0||*element_ids.begin()!=low||*element_ids.rbegin()!=high)
                    throw std::runtime_error("Element count/tag bounds mismatch");
            }
            expect(in,"$EndElements");
        } else throw std::runtime_error("Unsupported Gmsh section: "+section);
    }
    if(mesh.nodes.empty()||mesh.elements.empty()) throw std::runtime_error("Empty Gmsh mesh");
    return mesh;
}
}
