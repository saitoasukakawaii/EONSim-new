#include "eonsim/fsi_element.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/fluid_residual.hpp"
#include "eonsim/dual.hpp"
#include "eonsim/action_lanes.hpp"
#include <cmath>
namespace eonsim {
FsiElementData::FsiElementData(const Tet4Topology::Nodal<Point>& coordinates)
    :reference(coordinates),reference_geometry(tet4_geometry(reference)),
     mesh_stiffness(poisson_element(reference_geometry,1,0).stiffness) {}
namespace {
constexpr int kinematic_components=2*Space3::dimension;
constexpr int kinematic_dofs=Tet4Topology::nodes*kinematic_components;
constexpr int kinematic_column(int direction) {
    const int component=direction%kinematic_components;
    return Tet4Ale::dof(direction/kinematic_components,
        component<Space3::dimension?component:Tet4Ale::mesh_offset+component-Space3::dimension);
}
struct PressureColumnData {
    double tau=0;
    Point mean_transport{}; // Cell mean of rho (u-w), zero when convection is disabled.
};
// Integral mean of the quadratic relative transport speed on an affine P1 cell.
// The four barycentric gradient dyads give the same metric under any vertex order.
// Both coefficients remain functions of the current fluid and ALE Newton unknowns.
template<class S>
auto metric_fluid_residual(const FsiElementData& data,const SimplexGeometry<Tet4Topology,S>& geometry,
                           const Tet4Flow::State<S>& fluid,const Tet4Topology::Nodal<Space3::Vector<S>>& mesh_velocity,
                           double* evaluated_tau) {
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
            add_product(metric,geometry.gradients[a][i],geometry.gradients[a][j]);
            add_product(transport,relative[a][i],relative[a][j]);
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
    if(evaluated_tau) *evaluated_tau=primal(tau);
    return fluid_residual(geometry,data.fluid,fluid,data.previous_fluid,mesh_velocity,tau,grad_div);
}

template<class S>
Tet4Flow::State<S> fluid_ale_residual(const FsiElementData& data,const Tet4Ale::State<S>& x,
                                    const SimplexGeometry<Tet4Topology,S>& geometry,
                                    PressureColumnData* pressure_columns=nullptr)
{
    Tet4Topology::Nodal<Space3::Vector<S>> velocity{};
    Tet4Flow::State<S> fluid{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        if(data.fluid.convection) for(int c=0;c<Space3::dimension;++c) {
            velocity[a][c]=(x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)]-data.previous_mesh[a][c])/(data.mesh_dt>0?data.mesh_dt:data.fluid.dt);
            if(pressure_columns) pressure_columns->mean_transport[c]+=Tet4Topology::mean_weight*data.fluid.density*
                (primal(x[Tet4Ale::dof(a,c)])-primal(velocity[a][c]));
        }
        for(int c=0;c<Tet4Flow::components;++c) fluid[Tet4Flow::dof(a,c)]=x[Tet4Ale::dof(a,c)];
    }
    if(data.regular_metric_dt>0)
        return metric_fluid_residual(data,geometry,fluid,velocity,pressure_columns?&pressure_columns->tau:nullptr);
    if(pressure_columns) pressure_columns->tau=data.fluid.tau;
    return fluid_residual(geometry,data.fluid,fluid,data.previous_fluid,velocity);
}

// Pressure is affine in this residual: neither the fixed nor current-metric
// stabilization depends on p. Integrate its four columns directly, while its
// primal values remain in the AD expression for every velocity/ALE derivative.
void add_pressure_columns(const Tet4Geometry& geometry,const PressureColumnData& coefficients,
                          Tet4Ale::Matrix<double>& tangent)
{
    for(int a=0;a<Tet4Topology::nodes;++a) {
        const auto& ga=geometry.gradients[a];
        double streamline=0;
        if(coefficients.tau>0) for(int j=0;j<Space3::dimension;++j)
            streamline+=ga[j]*coefficients.mean_transport[j];
        for(int b=0;b<Tet4Topology::nodes;++b) {
            const auto& gb=geometry.gradients[b];
            const int column=Tet4Ale::dof(b,Tet4Flow::pressure);
            for(int i=0;i<Space3::dimension;++i) {
                double value=-geometry.volume*(Tet4Topology::mean_weight*ga[i]);
                if(coefficients.tau>0) value+=geometry.volume*coefficients.tau*streamline*gb[i];
                tangent[Tet4Ale::matrix(Tet4Ale::dof(a,i),column)]=value;
            }
            if(coefficients.tau>0) {
                double pspg=0;
                for(int j=0;j<Space3::dimension;++j) pspg+=coefficients.tau*ga[j]*gb[j];
                tangent[Tet4Ale::matrix(Tet4Ale::dof(a,Tet4Flow::pressure),column)]=geometry.volume*pspg;
            }
        }
    }
}

// The reference mesh equation is linear and componentwise. Populate its exact
// block directly instead of propagating derivative lanes through zero terms.
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
    using D=Dual<kinematic_dofs>;
    const auto coordinates=current_coordinates(data,x);
    const auto g=tet4_geometry(coordinates);
    SimplexGeometry<Tet4Topology,D> geometry{}; geometry.volume=g.volume;
    Tet4Ale::State<D> trial{};
    for(int i=0;i<Tet4Ale::dofs;++i) trial[i]=x[i];
    for(int i=0;i<kinematic_dofs;++i) trial[kinematic_column(i)].derivative[i]=1;
    for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j) geometry.gradients[b][j]=g.gradients[b][j];
    // dV/dx_ai = V grad(Na)_i; d grad(Nb)_j/dx_ai = -grad(Nb)_i grad(Na)_j.
    // 仿射几何精确导数作为种子，普通求值和切线共享同一个残量表达。
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        const int column=a*kinematic_components+Space3::dimension+i;
        geometry.volume.derivative[column]=g.volume*g.gradients[a][i];
        for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j)
            geometry.gradients[b][j].derivative[column]=-g.gradients[b][i]*g.gradients[a][j];
    }
    PressureColumnData pressure_columns;
    const auto r=fluid_ale_residual(data,trial,geometry,&pressure_columns);
    FsiElementResult result;
    for(int i=0;i<Tet4Flow::dofs;++i) {
        const int row=Tet4Ale::dof(Tet4Flow::node(i),Tet4Flow::component(i));
        result.residual[row]=r[i].value;
        for(int j=0;j<kinematic_dofs;++j) result.tangent[Tet4Ale::matrix(row,kinematic_column(j))]=r[i].derivative[j];
    }
    add_pressure_columns(g,pressure_columns,result.tangent);
    add_mesh_and_pressure(data,x,coordinates,result.residual,&result.tangent);
    return result;
}
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    return fsi_element(data,x).tangent;
}
FsiElementResult fsi_element_reduced_preconditioner(const FsiElementData& data,const Tet4Ale::State<double>& x)
{
    using D=Dual<Tet4Vector::dofs>;
    const auto coordinates=current_coordinates(data,x);
    const auto g=tet4_geometry(coordinates);
    SimplexGeometry<Tet4Topology,D> geometry{};
    geometry.volume=g.volume;
    for(int a=0;a<Tet4Topology::nodes;++a) for(int j=0;j<Space3::dimension;++j)
        geometry.gradients[a][j]=g.gradients[a][j];
    Tet4Ale::State<D> trial{};
    for(int i=0;i<Tet4Ale::dofs;++i) trial[i]=x[i];
    for(int a=0;a<Tet4Topology::nodes;++a) for(int j=0;j<Space3::dimension;++j)
        trial[Tet4Ale::dof(a,j)].derivative[Tet4Vector::dof(a,j)]=1.;
    PressureColumnData pressure_columns;
    const auto fluid=fluid_ale_residual(data,trial,geometry,&pressure_columns);
    FsiElementResult result;
    for(int i=0;i<Tet4Flow::dofs;++i) {
        const int row=Tet4Ale::dof(Tet4Flow::node(i),Tet4Flow::component(i));
        result.residual[row]=fluid[i].value;
        for(int k=0;k<Tet4Vector::dofs;++k)
            result.tangent[Tet4Ale::matrix(row,Tet4Ale::dof(Tet4Vector::node(k),Tet4Vector::component(k)))]=fluid[i].derivative[k];
    }
    add_pressure_columns(g,pressure_columns,result.tangent);
    add_mesh_and_pressure(data,x,coordinates,result.residual,nullptr);
    for(int a=0;a<Tet4Topology::nodes;++a) for(int b=0;b<Tet4Topology::nodes;++b)
        for(int j=0;j<Space3::dimension;++j)
            result.tangent[Tet4Ale::matrix(Tet4Ale::dof(a,Tet4Ale::mesh_offset+j),Tet4Ale::dof(b,Tet4Ale::mesh_offset+j))]
                =data.mesh_stiffness[Tet4Scalar::matrix(a,b)];
    return result;
}
Tet4Ale::State<double> fsi_element_action(const FsiElementData& data,
    const Tet4Ale::State<double>& x,const Tet4Ale::State<double>& direction)
{
    using D=Dual<1>;
    const auto coordinates=current_coordinates(data,x);
    const auto g=tet4_geometry(coordinates);
    SimplexGeometry<Tet4Topology,D> geometry{};
    geometry.volume=g.volume;
    Tet4Ale::State<D> trial{};
    for(int i=0;i<Tet4Ale::dofs;++i) {
        trial[i]=x[i]; trial[i].derivative[0]=direction[i];
    }
    for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j)
        geometry.gradients[b][j]=g.gradients[b][j];
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        const double change=direction[Tet4Ale::dof(a,Tet4Ale::mesh_offset+i)];
        geometry.volume.derivative[0]+=g.volume*g.gradients[a][i]*change;
        for(int b=0;b<Tet4Topology::nodes;++b) for(int j=0;j<Space3::dimension;++j)
            geometry.gradients[b][j].derivative[0]-=g.gradients[b][i]*g.gradients[a][j]*change;
    }
    const auto fluid=fluid_ale_residual(data,trial,geometry);
    Tet4Ale::State<double> action{};
    for(int i=0;i<Tet4Flow::dofs;++i)
        action[Tet4Ale::dof(Tet4Flow::node(i),Tet4Flow::component(i))]=fluid[i].derivative[0];
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c)
        for(int b=0;b<Tet4Topology::nodes;++b)
            action[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)]+=
                data.mesh_stiffness[Tet4Scalar::matrix(a,b)]*direction[Tet4Ale::dof(b,Tet4Ale::mesh_offset+c)];
    for(const auto& face:data.inlet_faces) {
        int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
        Tri3Topology::Nodal<Point> points{};
        Point ab{},ac{},dab{},dac{};
        for(int c=0;c<Space3::dimension;++c) {
            for(int a=0;a<Tri3Topology::nodes;++a) points[a][c]=coordinates[face[a]][c];
            ab[c]=points[1][c]-points[0][c]; ac[c]=points[2][c]-points[0][c];
            dab[c]=direction[Tet4Ale::dof(face[1],Tet4Ale::mesh_offset+c)]-
                   direction[Tet4Ale::dof(face[0],Tet4Ale::mesh_offset+c)];
            dac[c]=direction[Tet4Ale::dof(face[2],Tet4Ale::mesh_offset+c)]-
                   direction[Tet4Ale::dof(face[0],Tet4Ale::mesh_offset+c)];
        }
        const auto surface=triangle_geometry(points,coordinates[opposite]);
        double orientation=0;
        for(int c=0;c<Space3::dimension;++c) {
            const int j=(c+1)%Space3::dimension,k=(c+2)%Space3::dimension;
            orientation+=(ab[j]*ac[k]-ab[k]*ac[j])*surface.normal[c];
        }
        const double factor=data.inlet_pressure*(orientation>0?1.:-1.)*Tri3Topology::mean_weight/2.;
        for(int c=0;c<Space3::dimension;++c) {
            const int j=(c+1)%Space3::dimension,k=(c+2)%Space3::dimension;
            const double change=factor*(dab[j]*ac[k]+ab[j]*dac[k]-dab[k]*ac[j]-ab[k]*dac[j]);
            for(int a:face) action[Tet4Ale::dof(a,c)]+=change;
        }
    }
    return action;
}
namespace {
// Flat coefficient storage permits a bounded SoA transpose without aliasing
// structs as double arrays. No entry stores a nodal Jacobian coefficient.
enum ActionCoefficient : int {
    volume=0,gradient=1,fluid_value=13,velocity_gradient=29,pressure_gradient=38,
    transport=41,momentum=53,momentum_sum=65,strong=68,supg=71,mean_pressure=80,
    divergence=81,tau=82,grad_div=83,adv_density=84,viscosity=85,mass=86,
    inverse_mesh_dt=87,metric=88,relative=97,relative_sum=109,metric_factor=112,
    inverse_trace=113,trace_factor=114,viscous_metric_factor=115,mesh_stiffness=116
};

template<class S>
Tet4Ale::State<S> cached_fluid_action(const std::array<S,132>& c,const Tet4Ale::State<S>& direction) {
    std::array<S,12> dg{},dt{},dm{};
    std::array<S,9> du{},dsupg{};
    Space3::Vector<S> dp{},dsum{},dstrong{},drsum{};
    S dv{},ddiv{},dpmean{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        const auto delta=direction[Tet4Ale::dof(a,Tet4Ale::mesh_offset+i)];
        dv+=c[volume]*c[gradient+3*a+i]*delta;
        for(int b=0;b<4;++b) for(int j=0;j<3;++j)
            dg[3*b+j]-=c[gradient+3*b+i]*c[gradient+3*a+j]*delta;
    }
    for(int a=0;a<4;++a) {
        dpmean+=.25*direction[Tet4Ale::dof(a,3)];
        for(int j=0;j<3;++j) {
            dp[j]+=direction[Tet4Ale::dof(a,3)]*c[gradient+3*a+j]+c[fluid_value+4*a+3]*dg[3*a+j];
            for(int i=0;i<3;++i)
                du[3*i+j]+=direction[Tet4Ale::dof(a,i)]*c[gradient+3*a+j]+c[fluid_value+4*a+i]*dg[3*a+j];
            dt[3*a+j]=c[adv_density]*(direction[Tet4Ale::dof(a,j)]-
                c[inverse_mesh_dt]*direction[Tet4Ale::dof(a,Tet4Ale::mesh_offset+j)]);
        }
    }
    for(int i=0;i<3;++i) ddiv+=du[3*i+i];
    // The current regular-Tet metric is differentiated at the frozen state.
    // Fixed-tau cells have metric_factor=inverse_trace=trace_factor=0.
    std::array<S,12> dr{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        // For Stokes, all cached relative velocities are zero, so the
        // quadratic advection derivative below vanishes as required.
        dr[3*a+i]=direction[Tet4Ale::dof(a,i)]-
            c[inverse_mesh_dt]*direction[Tet4Ale::dof(a,Tet4Ale::mesh_offset+i)];
        drsum[i]+=dr[3*a+i];
    }
    S dadvection{},dsquare{},dtrace{};
    const double metric_scale=std::cbrt(.25);
    for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
        S dmetric{},moment=c[relative_sum+i]*c[relative_sum+j];
        S dmoment=drsum[i]*c[relative_sum+j]+c[relative_sum+i]*drsum[j];
        for(int a=0;a<4;++a) {
            dmetric+=metric_scale*(dg[3*a+i]*c[gradient+3*a+j]+c[gradient+3*a+i]*dg[3*a+j]);
            moment+=c[relative+3*a+i]*c[relative+3*a+j];
            dmoment+=dr[3*a+i]*c[relative+3*a+j]+c[relative+3*a+i]*dr[3*a+j];
        }
        dadvection+=(dmetric*moment+c[metric+3*i+j]*dmoment)/20.;
        dsquare+=2.*c[metric+3*i+j]*dmetric;
        if(i==j) dtrace+=dmetric;
    }
    const S dinverse=c[metric_factor]*(dadvection+c[viscous_metric_factor]*dsquare);
    const S dtau=(0.-c[tau]*c[tau])*dinverse;
    const S dgraddiv=c[inverse_trace]*dinverse+c[trace_factor]*dtrace;
    Tet4Ale::State<S> out{};
    for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
        const auto stress=c[viscosity]*(c[velocity_gradient+3*i+j]+c[velocity_gradient+3*j+i]);
        const auto dstress=c[viscosity]*(du[3*i+j]+du[3*j+i]);
        for(int a=0;a<4;++a)
            out[Tet4Ale::dof(a,i)]+=(dv*stress+c[volume]*dstress)*c[gradient+3*a+j]+c[volume]*stress*dg[3*a+j];
    }
    const auto penalty=c[volume]*c[grad_div]*c[divergence];
    const auto dpenalty=dv*c[grad_div]*c[divergence]+c[volume]*(dgraddiv*c[divergence]+c[grad_div]*ddiv);
    for(int a=0;a<4;++a) for(int i=0;i<3;++i)
        out[Tet4Ale::dof(a,i)]+=dpenalty*c[gradient+3*a+i]+penalty*dg[3*a+i];
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        dm[3*a+i]=c[mass]*direction[Tet4Ale::dof(a,i)];
        for(int j=0;j<3;++j)
            dm[3*a+i]+=dt[3*a+j]*c[velocity_gradient+3*i+j]+c[transport+3*a+j]*du[3*i+j];
        dsum[i]+=dm[3*a+i];
    }
    for(int i=0;i<3;++i) dstrong[i]=.25*dsum[i]+dp[i];
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        const auto tested=(c[momentum_sum+i]+c[momentum+3*a+i])/20.;
        const auto dtested=(dsum[i]+dm[3*a+i])/20.;
        out[Tet4Ale::dof(a,i)]+=dv*(tested-c[mean_pressure]*c[gradient+3*a+i])+
            c[volume]*(dtested-dpmean*c[gradient+3*a+i]-c[mean_pressure]*dg[3*a+i]);
        const auto tested_strong=tested+.25*c[pressure_gradient+i];
        const auto dtested_strong=dtested+.25*dp[i];
        for(int j=0;j<3;++j)
            dsupg[3*i+j]+=dt[3*a+j]*tested_strong+c[transport+3*a+j]*dtested_strong;
    }
    for(int a=0;a<4;++a) {
        S continuity=.25*c[divergence],dcontinuity=.25*ddiv;
        for(int j=0;j<3;++j) {
            continuity+=c[tau]*c[gradient+3*a+j]*c[strong+j];
            dcontinuity+=dtau*c[gradient+3*a+j]*c[strong+j]+
                c[tau]*(dg[3*a+j]*c[strong+j]+c[gradient+3*a+j]*dstrong[j]);
        }
        out[Tet4Ale::dof(a,3)]+=dv*continuity+c[volume]*dcontinuity;
        for(int i=0;i<3;++i) {
            S streamline{},dstreamline{};
            for(int j=0;j<3;++j) {
                streamline+=c[gradient+3*a+j]*c[supg+3*i+j];
                dstreamline+=dg[3*a+j]*c[supg+3*i+j]+c[gradient+3*a+j]*dsupg[3*i+j];
            }
            out[Tet4Ale::dof(a,i)]+=(dv*c[tau]+c[volume]*dtau)*streamline+c[volume]*c[tau]*dstreamline;
            for(int b=0;b<4;++b)
                out[Tet4Ale::dof(a,Tet4Ale::mesh_offset+i)]+=c[mesh_stiffness+4*a+b]*direction[Tet4Ale::dof(b,Tet4Ale::mesh_offset+i)];
        }
    }
    return out;
}

void cached_face_action(const FsiElementLinearization& cache,const Tet4Ale::State<double>& direction,Tet4Ale::State<double>& out) {
    for(const auto& face:cache.faces) {
        Point dab{},dac{};
        for(int i=0;i<3;++i) {
            dab[i]=direction[Tet4Ale::dof(face.nodes[1],Tet4Ale::mesh_offset+i)]-direction[Tet4Ale::dof(face.nodes[0],Tet4Ale::mesh_offset+i)];
            dac[i]=direction[Tet4Ale::dof(face.nodes[2],Tet4Ale::mesh_offset+i)]-direction[Tet4Ale::dof(face.nodes[0],Tet4Ale::mesh_offset+i)];
        }
        for(int i=0;i<3;++i) {
            const int j=(i+1)%3,k=(i+2)%3;
            const double value=face.factor*(dab[j]*face.edge2[k]+face.edge1[j]*dac[k]-dab[k]*face.edge2[j]-face.edge1[k]*dac[j]);
            for(int a:face.nodes) out[Tet4Ale::dof(a,i)]+=value;
        }
    }
    for(double value:out) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite cached FSI action");
}
}

FsiElementLinearization fsi_prepare_action(const FsiElementData& data,const Tet4Ale::State<double>& x) {
    const auto coordinates=current_coordinates(data,x);
    const auto g=tet4_geometry(coordinates);
    // Exercise the ordinary material and current-metric gates before publishing
    // a cache. This one setup evaluation is never repeated per Krylov vector.
    (void)fluid_ale_residual(data,x,g);
    FsiElementLinearization out;
    auto& c=out.coefficients;
    const auto& p=data.fluid;
    c[volume]=g.volume; c[viscosity]=p.viscosity; c[mass]=p.dt>0?p.density/p.dt:0.;
    c[inverse_mesh_dt]=1./(data.mesh_dt>0?data.mesh_dt:p.dt);
    c[adv_density]=p.convection?p.density:0.; c[tau]=p.tau; c[grad_div]=p.grad_div_viscosity;
    for(int a=0;a<4;++a) {
        c[mean_pressure]+=.25*x[Tet4Ale::dof(a,3)];
        for(int i=0;i<4;++i) c[fluid_value+4*a+i]=x[Tet4Ale::dof(a,i)];
        for(int j=0;j<3;++j) {
            c[gradient+3*a+j]=g.gradients[a][j];
            c[pressure_gradient+j]+=x[Tet4Ale::dof(a,3)]*g.gradients[a][j];
            for(int i=0;i<3;++i) c[velocity_gradient+3*i+j]+=x[Tet4Ale::dof(a,i)]*g.gradients[a][j];
            if(p.convection) c[relative+3*a+j]=x[Tet4Ale::dof(a,j)]-
                (x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+j)]-data.previous_mesh[a][j])*c[inverse_mesh_dt];
            c[relative_sum+j]+=c[relative+3*a+j];
            c[transport+3*a+j]=p.density*c[relative+3*a+j];
        }
    }
    for(int i=0;i<3;++i) c[divergence]+=c[velocity_gradient+3*i+i];
    if(data.regular_metric_dt>0) {
        double trace=0,square=0,advection=0;
        const double scale=std::cbrt(.25),nu=p.viscosity/p.density;
        for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
            double value=0,moment=c[relative_sum+i]*c[relative_sum+j];
            for(int a=0;a<4;++a) {
                value+=scale*g.gradients[a][i]*g.gradients[a][j];
                moment+=c[relative+3*a+i]*c[relative+3*a+j];
            }
            c[metric+3*i+j]=value; square+=value*value; advection+=value*moment/20.;
            if(i==j) trace+=value;
        }
        const double inverse=p.density*std::sqrt(4./(data.regular_metric_dt*data.regular_metric_dt)+advection+36*nu*nu*square);
        c[tau]=1./inverse; c[grad_div]=inverse/trace;
        c[metric_factor]=.5*p.density*p.density/inverse;
        c[inverse_trace]=1./trace; c[trace_factor]=-inverse/(trace*trace); c[viscous_metric_factor]=36*nu*nu;
    }
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        c[momentum+3*a+i]=c[mass]*(x[Tet4Ale::dof(a,i)]-data.previous_fluid[Tet4Flow::dof(a,i)]);
        for(int j=0;j<3;++j) c[momentum+3*a+i]+=c[transport+3*a+j]*c[velocity_gradient+3*i+j];
        c[momentum_sum+i]+=c[momentum+3*a+i];
    }
    for(int i=0;i<3;++i) c[strong+i]=.25*c[momentum_sum+i]+c[pressure_gradient+i];
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) for(int j=0;j<3;++j)
        c[supg+3*i+j]+=c[transport+3*a+j]*((c[momentum_sum+i]+c[momentum+3*a+i])/20.+.25*c[pressure_gradient+i]);
    for(int i=0;i<16;++i) c[mesh_stiffness+i]=data.mesh_stiffness[i];
    for(const auto& nodes:data.inlet_faces) {
        int opposite=0; while(opposite==nodes[0]||opposite==nodes[1]||opposite==nodes[2]) ++opposite;
        Tri3Topology::Nodal<Point> points{};
        for(int a=0;a<3;++a) points[a]=coordinates[nodes[a]];
        const auto surface=triangle_geometry(points,coordinates[opposite]);
        FsiElementLinearization::Face face{nodes,{},{},0.};
        for(int i=0;i<3;++i) {face.edge1[i]=points[1][i]-points[0][i];face.edge2[i]=points[2][i]-points[0][i];}
        double orientation=0;
        for(int i=0;i<3;++i) orientation+=(face.edge1[(i+1)%3]*face.edge2[(i+2)%3]-face.edge1[(i+2)%3]*face.edge2[(i+1)%3])*surface.normal[i];
        face.factor=data.inlet_pressure*(orientation>0?1.:-1.)/6.;
        out.faces.push_back(face);
    }
    for(double value:c) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite FSI partial assembly coefficient");
    return out;
}

Tet4Ale::State<double> fsi_element_action(const FsiElementLinearization& cache,const Tet4Ale::State<double>& direction) {
    auto out=cached_fluid_action(cache.coefficients,direction);
    cached_face_action(cache,direction,out);
    return out;
}

void fsi_element_action_batch(const FsiElementLinearization* const* data,const Tet4Ale::State<double>* directions,
    Tet4Ale::State<double>* result,std::size_t count) {
    if(count==0||count>ActionLanes::width) throw std::runtime_error("FSI action batch needs 1..4 cells");
    std::array<ActionLanes,132> coefficients;
    Tet4Ale::State<ActionLanes> direction;
    for(std::size_t lane=0;lane<ActionLanes::width;++lane) {
        const auto source=lane<count?lane:0;
        for(std::size_t i=0;i<coefficients.size();++i) coefficients[i].values[lane]=data[source]->coefficients[i];
        for(std::size_t i=0;i<direction.size();++i) direction[i].values[lane]=lane<count?directions[lane][i]:0.;
    }
    const auto out=cached_fluid_action(coefficients,direction);
    for(std::size_t lane=0;lane<count;++lane) {
        for(std::size_t i=0;i<out.size();++i) result[lane][i]=out[i].values[lane];
        cached_face_action(*data[lane],directions[lane],result[lane]);
    }
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
