#include "eonsim/fsi_element.hpp"
#include "eonsim/boundary_geometry.hpp"
#include <cmath>
namespace eonsim {
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    Tet4Topology::Nodal<Point> current,velocity;
    Tet4Flow::State<double> fluid;
    for(int a=0;a<Tet4Topology::nodes;++a) {
        for(int c=0;c<Space3::dimension;++c) {
            current[a][c]=data.reference[a][c]+x[Tet4Ale::components*a+Tet4Ale::mesh_offset+c];
            velocity[a][c]=(x[Tet4Ale::components*a+Tet4Ale::mesh_offset+c]-data.previous_mesh[a][c])/data.fluid.dt;
        }
        for(int c=0;c<Tet4Flow::components;++c) fluid[Tet4Flow::components*a+c]=x[Tet4Ale::components*a+c];
    }
    const auto r=fluid_element(tet4_geometry(current),data.fluid,fluid,data.previous_fluid,velocity,false);
    const auto k=poisson_element(tet4_geometry(data.reference),1,0);
    Tet4Ale::State<double> result{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        for(int c=0;c<Tet4Flow::components;++c) result[Tet4Ale::components*a+c]=r.residual[Tet4Flow::components*a+c];
        for(int c=0;c<Space3::dimension;++c) for(int b=0;b<Tet4Topology::nodes;++b) result[Tet4Ale::components*a+Tet4Ale::mesh_offset+c]+=k.stiffness[Tet4Scalar::matrix(a,b)]*x[Tet4Ale::components*b+Tet4Ale::mesh_offset+c];
    }
    for(const auto& face:data.inlet_faces) {
        Tri3Topology::Nodal<Point> coordinates;
        for(int a=0;a<Tri3Topology::nodes;++a) coordinates[a]=current[face[a]];
        int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
        const auto surface=triangle_geometry(coordinates,current[opposite]);
        for(int node:face) for(int i=0;i<Space3::dimension;++i)
            result[Tet4Ale::dof(node,i)]+=data.inlet_pressure*surface.area*surface.normal[i]*Tri3Topology::mean_weight;
    }
    return result;
}
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    Tet4Ale::Matrix<double> tangent{};
    for(int c=0;c<Tet4Ale::dofs;++c) {
        const double eps=1e-6*std::max(1.,std::abs(x[c]));
        auto plus=x,minus=x; plus[c]+=eps; minus[c]-=eps;
        const auto rp=fsi_element_residual(data,plus),rm=fsi_element_residual(data,minus);
        for(int r=0;r<Tet4Ale::dofs;++r) tangent[Tet4Ale::matrix(r,c)]=(rp[r]-rm[r])/(2*eps);
    }
    return tangent;
}
}
