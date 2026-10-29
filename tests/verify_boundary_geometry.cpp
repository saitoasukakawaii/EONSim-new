#include "eonsim/boundary_geometry.hpp"
#include "eonsim/quadrature.hpp"
#include "eonsim/tet4.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
void close(double a,double b) { if(std::abs(a-b)>2e-12*std::max(1.,std::abs(b))) throw std::runtime_error("Boundary geometry identity failed"); }
template<class F> void rejects(F test) { try { test(); } catch(const std::runtime_error&) { return; } throw std::runtime_error("Invalid boundary accepted"); }
int main() {
    // Proper rotation, translation and nonuniform scale; opposite faces have shuffled node order.
    const Point ex{.6,.8,0},ey{-.8,.6,0},ez{0,0,1},origin{2,-3,4};
    Tet4Topology::Nodal<Point> x{origin,origin,origin,origin};
    for(int d=0;d<Space3::dimension;++d) { x[1][d]+=2*ex[d]; x[2][d]+=3*ey[d]; x[3][d]+=4*ez[d]; }
    MeshPartition mesh;
    for(int a=0;a<Tet4Topology::nodes;++a) mesh.nodes.push_back({a+1,x[a]});
    mesh.cells.push_back({1,{0,1,2,3},10});
    mesh.boundary={{2,{1,3,2},11},{3,{3,0,2},22},{4,{0,3,1},33},{5,{2,1,0},44}};
    const auto facets=build_boundary_facets(mesh);
    Point sum{}; Space3::Tensor<double> moment{};
    const double volume=tet4_geometry(x).volume;
    for(std::size_t f=0;f<facets.size();++f) {
        const auto g=boundary_geometry(mesh,f,facets[f]);
        close(g.area,f==0?std::sqrt(61.):(f==1?6:(f==2?4:3)));
        auto reversed=mesh; std::swap(reversed.boundary[f].nodes[0],reversed.boundary[f].nodes[1]);
        const auto other=boundary_geometry(reversed,f,facets[f]);
        for(int d=0;d<Space3::dimension;++d) { close(g.normal[d],other.normal[d]); sum[d]+=g.area*g.normal[d]; }
        for(const auto& q:BoundaryQuadrature::points) {
            Point p{};
            for(int a=0;a<Tri3Topology::nodes;++a) for(int d=0;d<Space3::dimension;++d) p[d]+=q.shape[a]*mesh.nodes[mesh.boundary[f].nodes[a]].position[d];
            for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) moment[Space3::index(i,j)]+=g.area*q.weight*p[i]*g.normal[j];
        }
    }
    for(double v:sum) close(v,0);
    for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) close(moment[Space3::index(i,j)],i==j?volume:0);
    for(int a=0;a<Tri3Topology::nodes;++a) for(int b=0;b<Tri3Topology::nodes;++b) {
        double mass=0; for(const auto& q:BoundaryQuadrature::points) mass+=q.weight*q.shape[a]*q.shape[b];
        close(mass,Tri3Topology::mass_weight(a,b));
    }
    rejects([&]{auto m=mesh; m.boundary.push_back(m.boundary[0]); build_boundary_facets(m);});
    rejects([&]{auto m=mesh; m.cells.clear(); build_boundary_facets(m);});
    rejects([&]{auto m=mesh; m.cells.push_back(m.cells[0]); build_boundary_facets(m);});
    rejects([&]{triangle_geometry({x[0],x[1],x[1]},x[3]);});
    rejects([&]{triangle_geometry({x[0],x[1],x[2]},x[0]);});
    std::cout<<"Boundary orientation, moments and topology passed\n";
}
