#include "eonsim/fsi_domains.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/tet4.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
namespace eonsim {
bool node_in_region(const MeshPartition& mesh,std::size_t node,int tag) {
    const auto& tags=mesh.node_cell_tags.at(node); return std::find(tags.begin(),tags.end(),tag)!=tags.end();
}
MeshPartition read_fsi_domains(const std::filesystem::path& path,const FsiDomains& config)
{
    const auto fluid=read_gmsh22(path),solid=read_gmsh22(config.solid_mesh);
    const auto ff=build_boundary_facets(fluid),sf=build_boundary_facets(solid);
    std::set<LocalId> fn,sn;
    std::set<int> ft,st;
    for(const auto& f:fluid.boundary) { ft.insert(f.physical_tag); if(f.physical_tag==config.fluid_interface) fn.insert(f.nodes.begin(),f.nodes.end()); }
    for(const auto& f:solid.boundary) { st.insert(f.physical_tag); if(f.physical_tag==config.solid_interface) sn.insert(f.nodes.begin(),f.nodes.end()); }
    if(fn.empty()||fn.size()!=sn.size()) throw std::runtime_error("FSI interface node count mismatch");
    for(int t:ft) if(st.count(t)) throw std::runtime_error("Independent FSI boundary tags must be disjoint");
    for(int t:config.pressure_tags) if(!ft.count(t)) throw std::runtime_error("FSI pressure tag missing");
    auto check_tags=[](const auto& entries,const auto& tags) { for(const auto& c:entries) if(!tags.count(c.tag)) throw std::runtime_error("FSI constraint tag missing"); };
    check_tags(config.fluid_constraints,ft); check_tags(config.mesh_constraints,ft); check_tags(config.solid_constraints,st);
    using Bin=Space3::Vector<long long>;
    auto bin=[&](const Point& p) { Bin b{}; for(int c=0;c<Space3::dimension;++c) {
        const double v=std::floor(p[c]/config.match_tolerance);
        if(!std::isfinite(v)||std::abs(v)>double(std::numeric_limits<long long>::max()/2)) throw std::runtime_error("Interface coordinates/tolerance exceed search index range");
        b[c]=static_cast<long long>(v);
    } return b; };
    std::map<Bin,std::vector<LocalId>> bins;
    for(auto n:fn) bins[bin(fluid.nodes[n].position)].push_back(n);
    std::vector<LocalId> mapping(solid.nodes.size(),-1); std::set<LocalId> used;
    for(auto n:sn) {
        const auto& x=solid.nodes[n].position; const auto center=bin(x); LocalId match=-1;
        for(int i=-1;i<=1;++i) for(int j=-1;j<=1;++j) for(int k=-1;k<=1;++k) {
            const auto found=bins.find({center[0]+i,center[1]+j,center[2]+k}); if(found==bins.end()) continue;
            for(auto m:found->second) {
                double distance=0; for(int c=0;c<Space3::dimension;++c) distance=std::max(distance,std::abs(x[c]-fluid.nodes[m].position[c]));
                if(distance<=config.match_tolerance) { if(match>=0) throw std::runtime_error("Ambiguous FSI interface match"); match=m; }
            }
        }
        if(match<0||!used.insert(match).second) throw std::runtime_error("Unmatched or non-bijective FSI interface");
        mapping[n]=match;
    }
    std::map<Tri3Topology::Nodal<LocalId>,TriangleGeometry> faces;
    for(std::size_t f=0;f<fluid.boundary.size();++f) if(fluid.boundary[f].physical_tag==config.fluid_interface) {
        auto key=fluid.boundary[f].nodes; std::sort(key.begin(),key.end()); faces.emplace(key,boundary_geometry(fluid,f,ff[f]));
    }
    std::set<Tri3Topology::Nodal<LocalId>> matched;
    for(std::size_t f=0;f<solid.boundary.size();++f) if(solid.boundary[f].physical_tag==config.solid_interface) {
        auto key=solid.boundary[f].nodes; for(auto& n:key) n=mapping[n]; std::sort(key.begin(),key.end());
        const auto found=faces.find(key); if(found==faces.end()||!matched.insert(key).second) throw std::runtime_error("Nonconforming FSI interface triangulation");
        const auto g=boundary_geometry(solid,f,sf[f]); double dot=0;
        for(int c=0;c<Space3::dimension;++c) dot+=g.normal[c]*found->second.normal[c];
        if(dot> -1+1e-8 || std::abs(g.area-found->second.area)>1e-8*std::max(g.area,found->second.area)) throw std::runtime_error("FSI interface normals/areas mismatch");
    }
    if(matched.size()!=faces.size()) throw std::runtime_error("Incomplete FSI interface faces");
    MeshPartition joined; joined.nodes=fluid.nodes;
    for(std::size_t n=0;n<solid.nodes.size();++n) if(mapping[n]<0) {
        if(joined.nodes.size()>=static_cast<std::size_t>(std::numeric_limits<LocalId>::max())) throw std::runtime_error("Joined mesh exceeds local index range");
        mapping[n]=joined.nodes.size(); joined.nodes.push_back(solid.nodes[n]);
    }
    for(std::size_t n=0;n<joined.nodes.size();++n) joined.nodes[n].global_id=n+1;
    for(bool is_solid:{false,true}) {
        const auto& mesh=is_solid?solid:fluid;
        for(auto cell:mesh.cells) {
            if(cell.physical_tag!=(is_solid?config.solid_region:config.fluid_region)) throw std::runtime_error("Unexpected independent FSI volume tag");
            Tet4Topology::Nodal<Point> x; for(int a=0;a<Tet4Topology::nodes;++a) x[a]=mesh.nodes[cell.nodes[a]].position;
            (void)tet4_geometry(x);
            if(is_solid) for(auto& n:cell.nodes) n=mapping[n];
            cell.global_id=joined.cells.size()+1; joined.cells.push_back(cell);
        }
        for(auto f:mesh.boundary) if(f.physical_tag!=(is_solid?config.solid_interface:config.fluid_interface)) {
            if(is_solid) for(auto& n:f.nodes) n=mapping[n];
            f.global_id=joined.boundary.size()+1; joined.boundary.push_back(f);
        }
    }
    initialize_serial_partition(joined); return joined;
}
}
