#include "eonsim/solid_element.hpp"
#include "eonsim/hyperelastic.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
SolidElement solid_element(const Tet4Geometry& g,const SolidParameters& p,
    const Tet4Vector::State<double>& x,const Tet4Vector::State<double>& dn,const Tet4Vector::State<double>& vn,bool compute_tangent)
{
    if(!(p.young>0 && p.poisson>-1 && p.poisson<.5 && p.density>0 && p.dt>=0) ||
        !std::isfinite(p.young+p.poisson+p.density+p.dt)) throw std::runtime_error("Invalid solid material/time parameters");
    const double mu=p.young/(2*(1+p.poisson));
    const double lambda=p.young*p.poisson/((1+p.poisson)*(1-2*p.poisson));
    const double chain=p.dt>0?p.dt:1;
    double grad[Space3::dimension][Space3::dimension]{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j)
        grad[i][j]+=(p.dt>0?dn[Tet4Vector::components*a+i]+p.dt*x[Tet4Vector::components*a+i]:x[Tet4Vector::components*a+i])*g.gradients[a][j];
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
