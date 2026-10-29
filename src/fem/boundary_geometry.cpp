#include "eonsim/time_step.hpp"
#include "eonsim/boundary_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <stdexcept>
namespace eonsim {
std::vector<BoundaryFacet> build_boundary_facets(const MeshPartition& mesh)
{
    std::map<Tri3Topology::Nodal<LocalId>,std::size_t> lookup;
    std::vector<BoundaryFacet> result(mesh.boundary.size());
    std::vector<int> count(result.size(),0);
    for(std::size_t f=0;f<mesh.boundary.size();++f) {
        auto key=mesh.boundary[f].nodes; std::sort(key.begin(),key.end());
        if(std::adjacent_find(key.begin(),key.end())!=key.end()||!lookup.emplace(key,f).second)
            throw std::runtime_error("Repeated boundary node or face");
    }
    for(std::size_t c=0;c<mesh.cells.size();++c) for(int omit=0;omit<Tet4Topology::nodes;++omit) {
        const auto& nodes=mesh.cells[c].nodes;
        Tri3Topology::Nodal<LocalId> key{}; int k=0;
        for(int a=0;a<Tet4Topology::nodes;++a) if(a!=omit) key[k++]=nodes[a];
        std::sort(key.begin(),key.end());
        const auto found=lookup.find(key); if(found==lookup.end()) continue;
        const auto f=found->second;
        if(++count[f]!=1) throw std::runtime_error("Tagged boundary has multiple adjacent cells");
        auto& facet=result[f]; facet.cell=c; facet.opposite=omit;
        for(int a=0;a<Tri3Topology::nodes;++a)
            facet.local_nodes[a]=std::find(nodes.begin(),nodes.end(),mesh.boundary[f].nodes[a])-nodes.begin();
    }
    for(int n:count) if(n!=1) throw std::runtime_error("Tagged boundary has no adjacent local cell");
    return result;
}
TriangleGeometry triangle_geometry(const Tri3Topology::Nodal<Point>& face,const Point& opposite)
{
    for(const auto& p:face) for(double x:p) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite boundary coordinate");
    for(double x:opposite) if(!std::isfinite(x)) throw std::runtime_error("Nonfinite opposite vertex");
    Point ab{},ac{},inside{}; double scale=0;
    for(int d=0;d<Space3::dimension;++d) {
        ab[d]=face[1][d]-face[0][d]; ac[d]=face[2][d]-face[0][d]; inside[d]=opposite[d]-face[0][d];
        scale=std::max({scale,std::abs(ab[d]),std::abs(ac[d]),std::abs(inside[d])});
    }
    if(!(scale>0)||!std::isfinite(scale)) throw std::runtime_error("Invalid boundary length scale");
    for(int d=0;d<Space3::dimension;++d) { ab[d]/=scale; ac[d]/=scale; inside[d]/=scale; }
    Point normal{ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]};
    double norm=0,orientation=0;
    for(int d=0;d<Space3::dimension;++d) { norm+=normal[d]*normal[d]; orientation+=normal[d]*inside[d]; }
    norm=std::sqrt(norm);
    const double tolerance=128*std::numeric_limits<double>::epsilon();
    if(!(norm>tolerance)||!(std::abs(orientation)>tolerance*norm)) throw StepRejected("Degenerate boundary face or cell");
    const double area=(norm/2)*scale*scale;
    if(!(area>0)||!std::isfinite(area)) throw std::runtime_error("Boundary area is not representable");
    for(double& x:normal) x*=(orientation>0?-1:1)/norm;
    return {area,normal};
}
TriangleGeometry boundary_geometry(const MeshPartition& mesh,std::size_t f,const BoundaryFacet& facet)
{
    Tri3Topology::Nodal<Point> coordinates;
    for(int a=0;a<Tri3Topology::nodes;++a) coordinates[a]=mesh.nodes.at(mesh.boundary.at(f).nodes[a]).position;
    return triangle_geometry(coordinates,mesh.nodes.at(mesh.cells.at(facet.cell).nodes[facet.opposite]).position);
}
}
