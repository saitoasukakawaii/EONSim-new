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
// Integral mean of the quadratic relative transport speed on an affine P1 cell.
// The four barycentric gradient dyads give the same metric under any vertex order.
// Both coefficients remain functions of the current fluid and ALE Newton unknowns.
template<class S>
auto metric_fluid_residual(const FsiElementData& data,const SimplexGeometry<Tet4Topology,S>& geometry,
                           const Tet4Flow::State<S>& fluid,const Tet4Topology::Nodal<Space3::Vector<S>>& mesh_velocity) {
    static const double scale=std::cbrt(.25);
    Tet4Topology::Nodal<Space3::Vector<S>> relative{};
    Space3::Vector<S> sum{};
    if(data.fluid.convection) for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        relative[a][i]=fluid[Tet4Flow::dof(a,i)]-mesh_velocity[a][i];
        sum[i]+=relative[a][i];
    }
    S trace{},square{},advection{};
    for(int i=0;i<Space3::dimension;++i) for(int j=i;j<Space3::dimension;++j) {
        S metric{};
        S transport=sum[i]*sum[j];
        for(int a=0;a<Tet4Topology::nodes;++a) {
            metric+=geometry.gradients[a][i]*geometry.gradients[a][j];
            transport+=relative[a][i]*relative[a][j];
        }
        metric=scale*metric;
        const double multiplicity=i==j?1.:2.;
        if(i==j) trace+=metric;
        square+=multiplicity*metric*metric;
        advection+=multiplicity*metric*transport/20.;
    }
    const double frequency=2/data.regular_metric_dt;
    const double nu=data.fluid.viscosity/data.fluid.density;
    using std::sqrt;
    const S inverse_tau=data.fluid.density*sqrt(frequency*frequency+advection+36*nu*nu*square);
    const S tau=1/inverse_tau,grad_div=inverse_tau/trace;
    return fluid_residual(geometry,data.fluid,fluid,data.previous_fluid,mesh_velocity,tau,grad_div);
}

template<class S>
Tet4Flow::State<S> fluid_ale_residual(const FsiElementData& data,const Tet4Ale::State<S>& x,
                                    const SimplexGeometry<Tet4Topology,S>& geometry)
{
    Tet4Topology::Nodal<Space3::Vector<S>> velocity{};
    Tet4Flow::State<S> fluid{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        if(data.fluid.convection) for(int c=0;c<Space3::dimension;++c)
            velocity[a][c]=(x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)]-data.previous_mesh[a][c])/(data.mesh_dt>0?data.mesh_dt:data.fluid.dt);
        for(int c=0;c<Tet4Flow::components;++c) fluid[Tet4Flow::dof(a,c)]=x[Tet4Ale::dof(a,c)];
    }
    return data.regular_metric_dt>0 ? metric_fluid_residual(data,geometry,fluid,velocity) :
        fluid_residual(geometry,data.fluid,fluid,data.previous_fluid,velocity);
}

// The reference mesh equation is linear and componentwise. Populate its exact
// block directly instead of propagating 28 derivative lanes through zero terms.
// The fluid rows still differentiate every current-geometry/velocity coefficient.
void add_mesh_and_pressure(const FsiElementData& data,const Tet4Ale::State<double>& x,
                          const Tet4Topology::Nodal<Point>& current,Tet4Ale::State<double>& r,
                          Tet4Ale::Matrix<double>* tangent)
{
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
        const int row=Tet4Ale::dof(a,Tet4Ale::mesh_offset+c);
        for(int b=0;b<Tet4Topology::nodes;++b) {
            const int column=Tet4Ale::dof(b,Tet4Ale::mesh_offset+c);
            const double stiffness=data.mesh_stiffness[Tet4Scalar::matrix(a,b)];
            r[row]+=stiffness*x[column];
            if(tangent) (*tangent)[Tet4Ale::matrix(row,column)]=stiffness;
        }
    }
    for(const auto& face:data.inlet_faces) {
        int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
        Tri3Topology::Nodal<Point> coordinates{};
        Point ab{},ac{},area_normal{};
        for(int c=0;c<Space3::dimension;++c) {
            for(int a=0;a<Tri3Topology::nodes;++a) coordinates[a][c]=current[face[a]][c];
            ab[c]=current[face[1]][c]-current[face[0]][c]; ac[c]=current[face[2]][c]-current[face[0]][c];
        }
        // Retain current face validity/orientation checks, including at zero load.
        const auto surface=triangle_geometry(coordinates,current[opposite]);
        double orientation=0;
        for(int c=0;c<Space3::dimension;++c) {
            const int j=(c+1)%Space3::dimension,l=(c+2)%Space3::dimension;
            area_normal[c]=(ab[j]*ac[l]-ab[l]*ac[j])/2;
            orientation+=area_normal[c]*surface.normal[c];
        }
        const double sign=orientation>0?1:-1;
        for(int a:face) for(int c=0;c<Space3::dimension;++c)
            r[Tet4Ale::dof(a,c)]+=data.inlet_pressure*sign*area_normal[c]*Tri3Topology::mean_weight;
        if(!tangent) continue;
        // d(ab x ac) = d(ab) x ac + ab x d(ac). Only the nine coordinates
        // on this face contribute; fluid columns and the opposite vertex do not.
        for(int b=0;b<Tri3Topology::nodes;++b) for(int k=0;k<Space3::dimension;++k) {
            const int column=Tet4Ale::dof(face[b],Tet4Ale::mesh_offset+k);
            const double dab=(b==1?1.:0.)-(b==0?1.:0.);
            const double dac=(b==2?1.:0.)-(b==0?1.:0.);
            for(int c=0;c<Space3::dimension;++c) {
                if(k==c) continue;
                const int j=(c+1)%Space3::dimension,l=(c+2)%Space3::dimension;
                const double area_derivative=(dab*(k==j?ac[l]:0.)+dac*(k==l?ab[j]:0.)
                                             -dab*(k==l?ac[j]:0.)-dac*(k==j?ab[l]:0.))/2;
                const double value=data.inlet_pressure*sign*area_derivative*Tri3Topology::mean_weight;
                for(int a:face) (*tangent)[Tet4Ale::matrix(Tet4Ale::dof(a,c),column)]+=value;
            }
        }
    }
}
Tet4Topology::Nodal<Point> current_coordinates(const FsiElementData& data,const Tet4Ale::State<double>& x) {
    if(!(data.fluid.dt>0)||!(data.mesh_dt>=0&&data.regular_metric_dt>=0)||!std::isfinite(data.mesh_dt+data.regular_metric_dt)) throw std::runtime_error("FSI requires valid inertia and mesh time coefficients");
    auto coordinates=data.reference;
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) coordinates[a][c]+=x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)];
    return coordinates;
}
}
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& x) {
    const auto coordinates=current_coordinates(data,x);
    const auto fluid=fluid_ale_residual(data,x,tet4_geometry(coordinates));
    Tet4Ale::State<double> result{};
    for(int i=0;i<Tet4Flow::dofs;++i)
        result[Tet4Ale::dof(Tet4Flow::node(i),Tet4Flow::component(i))]=fluid[i];
    add_mesh_and_pressure(data,x,coordinates,result,nullptr);
    return result;
}
FsiElementResult fsi_element(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    using D=Dual<Tet4Ale::dofs>;
    const auto coordinates=current_coordinates(data,x);
    const auto g=tet4_geometry(coordinates);
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
    const auto r=fluid_ale_residual(data,trial,geometry);
    FsiElementResult result;
    for(int i=0;i<Tet4Flow::dofs;++i) {
        const int row=Tet4Ale::dof(Tet4Flow::node(i),Tet4Flow::component(i));
        result.residual[row]=r[i].value;
        for(int j=0;j<Tet4Ale::dofs;++j) result.tangent[Tet4Ale::matrix(row,j)]=r[i].derivative[j];
    }
    add_mesh_and_pressure(data,x,coordinates,result.residual,&result.tangent);
    return result;
}
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    return fsi_element(data,x).tangent;
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
