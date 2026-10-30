#include "eonsim/fsi_element.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/fluid_residual.hpp"
#include "eonsim/dual.hpp"
#include <cmath>
namespace eonsim {
FsiElementData::FsiElementData(const Tet4Topology::Nodal<Point>& coordinates)
    :reference(coordinates),reference_geometry(tet4_geometry(reference)),
     mesh_stiffness(poisson_element(reference_geometry,1,0).stiffness) {}
namespace {
template<class S>
Tet4Ale::State<S> residual(const FsiElementData& data,const Tet4Ale::State<S>& x,const SimplexGeometry<Tet4Topology,S>& geometry)
{
    Tet4Topology::Nodal<Space3::Vector<S>> current{},velocity{};
    Tet4Flow::State<S> fluid{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        for(int c=0;c<Space3::dimension;++c) {
            current[a][c]=data.reference[a][c]+x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)];
            velocity[a][c]=(x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)]-data.previous_mesh[a][c])/data.fluid.dt;
        }
        for(int c=0;c<Tet4Flow::components;++c) fluid[Tet4Flow::dof(a,c)]=x[Tet4Ale::dof(a,c)];
    }
    const auto r=fluid_residual(geometry,data.fluid,fluid,data.previous_fluid,velocity);
    Tet4Ale::State<S> result{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        for(int c=0;c<Tet4Flow::components;++c) result[Tet4Ale::dof(a,c)]=r[Tet4Flow::dof(a,c)];
        for(int c=0;c<Space3::dimension;++c) for(int b=0;b<Tet4Topology::nodes;++b)
            result[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)]+=data.mesh_stiffness[Tet4Scalar::matrix(a,b)]*x[Tet4Ale::dof(b,Tet4Ale::mesh_offset+c)];
    }
    for(const auto& face:data.inlet_faces) {
        int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
        Tri3Topology::Nodal<Point> coordinates{}; Point inside{};
        Space3::Vector<S> ab{},ac{},area_normal{};
        for(int c=0;c<Space3::dimension;++c) {
            inside[c]=primal(current[opposite][c]);
            for(int a=0;a<Tri3Topology::nodes;++a) coordinates[a][c]=primal(current[face[a]][c]);
            ab[c]=current[face[1]][c]-current[face[0]][c]; ac[c]=current[face[2]][c]-current[face[0]][c];
        }
        const auto surface=triangle_geometry(coordinates,inside);
        double orientation=0;
        for(int c=0;c<Space3::dimension;++c) {
            const int j=(c+1)%Space3::dimension,l=(c+2)%Space3::dimension;
            area_normal[c]=(ab[j]*ac[l]-ab[l]*ac[j])/2;
            orientation+=primal(area_normal[c])*surface.normal[c];
        }
        const double sign=orientation>0?1:-1;
        for(int a:face) for(int c=0;c<Space3::dimension;++c)
            result[Tet4Ale::dof(a,c)]+=data.inlet_pressure*sign*area_normal[c]*Tri3Topology::mean_weight;
    }
    return result;
}
Tet4Geometry current_geometry(const FsiElementData& data,const Tet4Ale::State<double>& x) {
    if(!(data.fluid.dt>0)) throw std::runtime_error("FSI requires positive dt");
    auto coordinates=data.reference;
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) coordinates[a][c]+=x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)];
    return tet4_geometry(coordinates);
}
}
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& x) {
    return residual(data,x,current_geometry(data,x));
}
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    using D=Dual<Tet4Ale::dofs>;
    const auto g=current_geometry(data,x);
    SimplexGeometry<Tet4Topology,D> geometry{}; geometry.volume=g.volume;
    Tet4Ale::State<D> trial{};
    for(int i=0;i<Tet4Ale::dofs;++i) { trial[i]=x[i]; trial[i].derivative[i]=1; }
    for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j) geometry.gradients[b][j]=g.gradients[b][j];
    // dV/dx_ai = V grad(Na)_i; d grad(Nb)_j/dx_ai = -grad(Nb)_i grad(Na)_j.
    // 仿射几何精确导数作为种子，普通求值和切线共享同一个残量表达。
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        const int column=Tet4Ale::dof(a,Tet4Ale::mesh_offset+i);
        geometry.volume.derivative[column]=g.volume*g.gradients[a][i];
        for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j)
            geometry.gradients[b][j].derivative[column]=-g.gradients[b][i]*g.gradients[a][j];
    }
    const auto r=residual(data,trial,geometry);
    Tet4Ale::Matrix<double> tangent{};
    for(int i=0;i<Tet4Ale::dofs;++i) for(int j=0;j<Tet4Ale::dofs;++j) tangent[Tet4Ale::matrix(i,j)]=r[i].derivative[j];
    return tangent;
}
Tet4Ale::Matrix<double> fsi_element_tangent_fd(const FsiElementData& data,const Tet4Ale::State<double>& x)
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
