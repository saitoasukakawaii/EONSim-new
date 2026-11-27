#include "eonsim/solid_element.hpp"
#include "eonsim/hyperelastic.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/action_lanes.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
WallSupportBalance WallSupportFace::evaluate(const Tet4Vector::State<double>& reference_displacement,
    const Tet4Vector::State<double>& velocity,double displacement_dt,SolidElement* assembly,bool compute_tangent) const
{
    Tri3Topology::Nodal<double> d{},v{};
    for(int a=0;a<Tri3Topology::nodes;++a) {
        for(int i=0;i<Space3::dimension;++i) {
            const int row=Tet4Vector::dof(nodes[a],i);
            d[a]+=geometry.normal[i]*reference_displacement[row];
            v[a]+=geometry.normal[i]*velocity[row];
        }
        d[a]+=displacement_dt*v[a];
    }
    WallSupportBalance balance;
    const double derivative=stiffness*displacement_dt+damping;
    for(int a=0;a<Tri3Topology::nodes;++a) for(int b=0;b<Tri3Topology::nodes;++b) {
        const double mass=geometry.area*Tri3Topology::mass_weight(a,b);
        const double force=mass*(stiffness*d[b]+damping*v[b]);
        balance.spring_energy+=.5*stiffness*mass*d[a]*d[b];
        balance.dissipation+=damping*mass*v[a]*v[b];
        balance.power_on_wall-=v[a]*force;
        if(!assembly) continue;
        for(int i=0;i<Space3::dimension;++i) {
            const int row=Tet4Vector::dof(nodes[a],i);
            assembly->residual[row]+=geometry.normal[i]*force;
            if(compute_tangent) for(int j=0;j<Space3::dimension;++j)
                assembly->tangent[Tet4Vector::matrix(row,Tet4Vector::dof(nodes[b],j))]
                    +=mass*derivative*geometry.normal[i]*geometry.normal[j];
        }
    }
    return balance;
}
Tet4Vector::State<double> WallSupportFace::action(const Tet4Vector::State<double>& direction,
    double displacement_dt) const
{
    if(!(geometry.area>0)||!std::isfinite(geometry.area))
        throw std::runtime_error("Invalid wall support reference area");
    Tri3Topology::Nodal<double> normal_direction{};
    for(int a=0;a<Tri3Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i)
        normal_direction[a]+=geometry.normal[i]*direction[Tet4Vector::dof(nodes[a],i)];
    Tet4Vector::State<double> result{};
    const double derivative=stiffness*displacement_dt+damping;
    for(int a=0;a<Tri3Topology::nodes;++a) {
        double force=0;
        for(int b=0;b<Tri3Topology::nodes;++b)
            force+=geometry.area*Tri3Topology::mass_weight(a,b)*derivative*normal_direction[b];
        for(int i=0;i<Space3::dimension;++i)
            result[Tet4Vector::dof(nodes[a],i)]+=geometry.normal[i]*force;
    }
    for(double value:result) if(!std::isfinite(value))
        throw std::runtime_error("Nonfinite wall support tangent action");
    return result;
}
Tet4Vector::State<double> solid_element_action(const Tet4Geometry& g,const SolidParameters& p,
    const Tet4Vector::State<double>& x,const Tet4Vector::State<double>& direction,
    const Tet4Vector::State<double>& dn)
{
    if(!(p.young>0 && p.poisson>-1 && p.poisson<.5 && p.density>0 && p.dt>=0&&p.displacement_dt>=0) ||
        !std::isfinite(p.young+p.poisson+p.density+p.dt+p.displacement_dt)) throw std::runtime_error("Invalid solid material/time parameters");
    if(!(g.volume>0)||!std::isfinite(g.volume)) throw std::runtime_error("Invalid solid reference volume");
    const double mu=p.young/(2*(1+p.poisson));
    const double lambda=p.young*p.poisson/((1+p.poisson)*(1-2*p.poisson));
    const double chain=p.dt>0?(p.displacement_dt>0?p.displacement_dt:p.dt):1;
    Space3::Tensor<double> change{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i)
        for(int J=0;J<Space3::dimension;++J)
            change[Space3::index(i,J)]+=chain*direction[Tet4Vector::dof(a,i)]*g.gradients[a][J];
    Space3::Tensor<double> stress_change{};
    if(p.neo_hookean) {
        Space3::Tensor<double> F{};
        for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i)
            for(int J=0;J<Space3::dimension;++J)
                F[Space3::index(i,J)]+=(p.dt>0?dn[Tet4Vector::dof(a,i)]+chain*x[Tet4Vector::dof(a,i)]:x[Tet4Vector::dof(a,i)])*g.gradients[a][J];
        for(int i=0;i<Space3::dimension;++i) F[Space3::index(i,i)]+=1;
        for(double value:F) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deformation gradient");
        const double jacobian=F[Space3::index(0,0)]*(F[Space3::index(1,1)]*F[Space3::index(2,2)]-F[Space3::index(1,2)]*F[Space3::index(2,1)])
            -F[Space3::index(0,1)]*(F[Space3::index(1,0)]*F[Space3::index(2,2)]-F[Space3::index(1,2)]*F[Space3::index(2,0)])
            +F[Space3::index(0,2)]*(F[Space3::index(1,0)]*F[Space3::index(2,1)]-F[Space3::index(1,1)]*F[Space3::index(2,0)]);
        if(!(jacobian>0)||!std::isfinite(jacobian)) throw StepRejected("Nonpositive solid deformation Jacobian");
        Space3::Tensor<double> inverse_transpose{};
        for(int i=0;i<Space3::dimension;++i) for(int J=0;J<Space3::dimension;++J)
            inverse_transpose[Space3::index(i,J)]=(F[Space3::index((i+1)%Space3::dimension,(J+1)%Space3::dimension)]*F[Space3::index((i+2)%Space3::dimension,(J+2)%Space3::dimension)]
                -F[Space3::index((i+1)%Space3::dimension,(J+2)%Space3::dimension)]*F[Space3::index((i+2)%Space3::dimension,(J+1)%Space3::dimension)])/jacobian;
        double log_change=0;
        for(std::size_t i=0;i<change.size();++i) log_change+=inverse_transpose[i]*change[i];
        // d(F^-T)=-F^-T dF^T F^-T. Contract the direction before forming
        // nodal forces, avoiding both the 9x9 and 12x12 dense tangents.
        Space3::Tensor<double> inverse_change{};
        for(int i=0;i<Space3::dimension;++i) for(int k=0;k<Space3::dimension;++k)
            for(int L=0;L<Space3::dimension;++L)
                inverse_change[Space3::index(i,k)]+=inverse_transpose[Space3::index(i,L)]*change[Space3::index(k,L)];
        const double coefficient=lambda*std::log(jacobian)-mu;
        for(int i=0;i<Space3::dimension;++i) for(int J=0;J<Space3::dimension;++J) {
            const auto slot=Space3::index(i,J);
            double product=0;
            for(int k=0;k<Space3::dimension;++k) product+=inverse_change[Space3::index(i,k)]*inverse_transpose[Space3::index(k,J)];
            stress_change[slot]=mu*change[slot]+lambda*log_change*inverse_transpose[slot]-coefficient*product;
        }
    } else {
        double trace=0;
        for(int i=0;i<Space3::dimension;++i) trace+=change[Space3::index(i,i)];
        for(int i=0;i<Space3::dimension;++i) for(int J=0;J<Space3::dimension;++J)
            stress_change[Space3::index(i,J)]=mu*(change[Space3::index(i,J)]+change[Space3::index(J,i)])+(i==J?lambda*trace:0);
    }
    Tet4Vector::State<double> result{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        const auto row=Tet4Vector::dof(a,i);
        for(int J=0;J<Space3::dimension;++J) result[row]+=g.volume*stress_change[Space3::index(i,J)]*g.gradients[a][J];
        if(p.dt>0) for(int b=0;b<Tet4Topology::nodes;++b)
            result[row]+=p.density*g.volume*Tet4Topology::mass_weight(a,b)*direction[Tet4Vector::dof(b,i)]/p.dt;
        if(!std::isfinite(result[row])) throw std::runtime_error("Nonfinite solid tangent action");
    }
    return result;
}
namespace {
template<class S>
Tet4Vector::State<S> cached_solid_action(const std::array<S,27>& c,const Tet4Vector::State<S>& direction) {
    Space3::Tensor<S> change{},left{},stress{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) for(int j=0;j<3;++j)
        change[3*i+j]+=c[15]*direction[Tet4Vector::dof(a,i)]*c[1+3*a+j];
    S log_change{};
    for(int i=0;i<9;++i) log_change+=c[17+i]*change[i];
    for(int i=0;i<3;++i) for(int k=0;k<3;++k) for(int j=0;j<3;++j)
        left[3*i+k]+=c[17+3*i+j]*change[3*k+j];
    for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
        S product{};
        for(int k=0;k<3;++k) product+=left[3*i+k]*c[17+3*k+j];
        stress[3*i+j]=c[13]*change[3*i+j]+c[14]*log_change*c[17+3*i+j]-c[26]*product;
    }
    Tet4Vector::State<S> out{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        const int row=Tet4Vector::dof(a,i);
        for(int j=0;j<3;++j) out[row]+=c[0]*stress[3*i+j]*c[1+3*a+j];
        for(int b=0;b<4;++b) out[row]+=c[0]*c[16]*Tet4Topology::mass_weight(a,b)*direction[Tet4Vector::dof(b,i)];
    }
    return out;
}
void validate_cached_solid_action(const Tet4Vector::State<double>& values) {
    for(double value:values) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite cached solid tangent action");
}
}

SolidElementLinearization solid_prepare_action(const Tet4Geometry& g,const SolidParameters& p,
    const Tet4Vector::State<double>& x,const Tet4Vector::State<double>& dn) {
    if(!(p.young>0&&p.poisson>-1&&p.poisson<.5&&p.density>0&&p.dt>=0&&p.displacement_dt>=0)||
        !std::isfinite(p.young+p.poisson+p.density+p.dt+p.displacement_dt)) throw std::runtime_error("Invalid solid material/time parameters");
    if(!(g.volume>0)||!std::isfinite(g.volume)) throw std::runtime_error("Invalid solid reference volume");
    SolidElementLinearization out;
    auto& c=out.coefficients;
    c[0]=g.volume; c[13]=p.young/(2*(1+p.poisson)); c[14]=p.young*p.poisson/((1+p.poisson)*(1-2*p.poisson));
    c[15]=p.dt>0?(p.displacement_dt>0?p.displacement_dt:p.dt):1.;
    c[16]=p.dt>0?p.density/p.dt:0.; c[26]=-c[13];
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) c[1+3*a+i]=g.gradients[a][i];
    for(int i=0;i<3;++i) c[17+3*i+i]=1.;
    if(p.neo_hookean) {
        Space3::Tensor<double> F{};
        for(int a=0;a<4;++a) for(int i=0;i<3;++i) for(int j=0;j<3;++j)
            F[3*i+j]+=(p.dt>0?dn[Tet4Vector::dof(a,i)]+c[15]*x[Tet4Vector::dof(a,i)]:x[Tet4Vector::dof(a,i)])*g.gradients[a][j];
        for(int i=0;i<3;++i) F[3*i+i]+=1.;
        for(double value:F) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deformation gradient");
        const double determinant=F[0]*(F[4]*F[8]-F[5]*F[7])-F[1]*(F[3]*F[8]-F[5]*F[6])+F[2]*(F[3]*F[7]-F[4]*F[6]);
        if(!(determinant>0)||!std::isfinite(determinant)) throw StepRejected("Nonpositive solid deformation Jacobian");
        for(int i=0;i<3;++i) for(int j=0;j<3;++j)
            c[17+3*i+j]=(F[3*((i+1)%3)+(j+1)%3]*F[3*((i+2)%3)+(j+2)%3]-
                F[3*((i+1)%3)+(j+2)%3]*F[3*((i+2)%3)+(j+1)%3])/determinant;
        c[26]=c[14]*std::log(determinant)-c[13];
    }
    for(double value:c) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite solid partial assembly coefficient");
    return out;
}

Tet4Vector::State<double> solid_element_action(const SolidElementLinearization& cache,const Tet4Vector::State<double>& direction) {
    const auto out=cached_solid_action(cache.coefficients,direction);
    validate_cached_solid_action(out);
    return out;
}
void solid_element_action_batch(const SolidElementLinearization* const* data,const Tet4Vector::State<double>* directions,
    Tet4Vector::State<double>* result,std::size_t count) {
    if(count==0||count>ActionLanes::width) throw std::runtime_error("Solid action batch needs 1..4 cells");
    std::array<ActionLanes,27> coefficients;
    Tet4Vector::State<ActionLanes> direction;
    for(std::size_t lane=0;lane<ActionLanes::width;++lane) {
        const auto source=lane<count?lane:0;
        for(std::size_t i=0;i<coefficients.size();++i) coefficients[i].values[lane]=data[source]->coefficients[i];
        for(std::size_t i=0;i<direction.size();++i) direction[i].values[lane]=lane<count?directions[lane][i]:0.;
    }
    const auto out=cached_solid_action(coefficients,direction);
    for(std::size_t lane=0;lane<count;++lane) {
        for(std::size_t i=0;i<out.size();++i) result[lane][i]=out[i].values[lane];
        validate_cached_solid_action(result[lane]);
    }
}

SolidElement solid_element(const Tet4Geometry& g,const SolidParameters& p,
    const Tet4Vector::State<double>& x,const Tet4Vector::State<double>& dn,const Tet4Vector::State<double>& vn,bool compute_tangent)
{
    if(!(p.young>0 && p.poisson>-1 && p.poisson<.5 && p.density>0 && p.dt>=0&&p.displacement_dt>=0) ||
        !std::isfinite(p.young+p.poisson+p.density+p.dt+p.displacement_dt)) throw std::runtime_error("Invalid solid material/time parameters");
    const double mu=p.young/(2*(1+p.poisson));
    const double lambda=p.young*p.poisson/((1+p.poisson)*(1-2*p.poisson));
    const double chain=p.dt>0?(p.displacement_dt>0?p.displacement_dt:p.dt):1;
    double grad[Space3::dimension][Space3::dimension]{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j)
        grad[i][j]+=(p.dt>0?dn[Tet4Vector::components*a+i]+chain*x[Tet4Vector::components*a+i]:x[Tet4Vector::components*a+i])*g.gradients[a][j];
    double tr=0;
    for(int i=0;i<Space3::dimension;++i) tr+=grad[i][i];
    double stress[Space3::dimension][Space3::dimension]{};
    SolidElement e;
    for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) {
        stress[i][j]=mu*(grad[i][j]+grad[j][i])+(i==j?lambda*tr:0);
        e.strain_energy+=.5*g.volume*stress[i][j]*grad[i][j];
    }
    HyperelasticResponse material;
    if(p.neo_hookean) {
        Space3::Tensor<double> F;
        for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) F[Space3::index(i,j)]=grad[i][j]+(i==j?1:0);
        material=neo_hookean(F,p.young,p.poisson,compute_tangent);
        e.strain_energy=g.volume*material.energy;
        for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) stress[i][j]=material.first_piola[Space3::index(i,j)];
    }
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        for(int j=0;j<Space3::dimension;++j) e.residual[Tet4Vector::components*a+i]+=g.volume*stress[i][j]*g.gradients[a][j];
        for(int b=0;b<Tet4Topology::nodes;++b) {
            const double mass=p.density*g.volume*Tet4Topology::mass_weight(a,b);
            if(p.dt>0) {
                e.residual[Tet4Vector::components*a+i]+=mass*(x[Tet4Vector::components*b+i]-vn[Tet4Vector::components*b+i])/p.dt;
                e.kinetic_energy+=.5*mass*x[Tet4Vector::components*a+i]*x[Tet4Vector::components*b+i];
            }
            if(compute_tangent) for(int k=0;k<Space3::dimension;++k) {
                double dot=0; for(int j=0;j<Space3::dimension;++j) dot+=g.gradients[a][j]*g.gradients[b][j];
                double stiffness=lambda*g.gradients[a][i]*g.gradients[b][k]
                    +mu*g.gradients[a][k]*g.gradients[b][i]+(i==k?mu*dot:0);
                if(p.neo_hookean) {
                    stiffness=0;
                    for(int J=0;J<Space3::dimension;++J) for(int L=0;L<Space3::dimension;++L)
                        stiffness+=g.gradients[a][J]*material.tangent[Space3::derivative(i,J,k,L)]*g.gradients[b][L];
                }
                e.tangent[Tet4Vector::matrix(Tet4Vector::dof(a,i),Tet4Vector::dof(b,k))]=chain*g.volume*stiffness+(p.dt>0&&i==k?mass/p.dt:0);
            }
        }
    }
    return e;
}
}
