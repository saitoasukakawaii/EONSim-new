#include "eonsim/solid_element.hpp"
#include "eonsim/hyperelastic.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
SolidElement solid_element(const Tet4Geometry& g,const SolidParameters& p,
    const std::array<double,12>& x,const std::array<double,12>& dn,const std::array<double,12>& vn)
{
    if(!(p.young>0 && p.poisson>-1 && p.poisson<.5 && p.density>0 && p.dt>=0) ||
        !std::isfinite(p.young+p.poisson+p.density+p.dt)) throw std::runtime_error("Invalid solid material/time parameters");
    const double mu=p.young/(2*(1+p.poisson));
    const double lambda=p.young*p.poisson/((1+p.poisson)*(1-2*p.poisson));
    const double chain=p.dt>0?p.dt:1;
    double grad[3][3]{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) for(int j=0;j<3;++j)
        grad[i][j]+=(p.dt>0?dn[3*a+i]+p.dt*x[3*a+i]:x[3*a+i])*g.gradients[a][j];
    const double tr=grad[0][0]+grad[1][1]+grad[2][2];
    double stress[3][3]{};
    SolidElement e;
    for(int i=0;i<3;++i) for(int j=0;j<3;++j) {
        stress[i][j]=mu*(grad[i][j]+grad[j][i])+(i==j?lambda*tr:0);
        e.strain_energy+=.5*g.volume*stress[i][j]*grad[i][j];
    }
    HyperelasticResponse material;
    if(p.neo_hookean) {
        std::array<double,9> F;
        for(int i=0;i<3;++i) for(int j=0;j<3;++j) F[3*i+j]=grad[i][j]+(i==j?1:0);
        material=neo_hookean(F,p.young,p.poisson);
        e.strain_energy=g.volume*material.energy;
        for(int i=0;i<3;++i) for(int j=0;j<3;++j) stress[i][j]=material.first_piola[3*i+j];
    }
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
        for(int j=0;j<3;++j) e.residual[3*a+i]+=g.volume*stress[i][j]*g.gradients[a][j];
        for(int b=0;b<4;++b) {
            const double mass=p.density*g.volume*(a==b?2:1)/20;
            if(p.dt>0) {
                e.residual[3*a+i]+=mass*(x[3*b+i]-vn[3*b+i])/p.dt;
                e.kinetic_energy+=.5*mass*x[3*a+i]*x[3*b+i];
            }
            for(int k=0;k<3;++k) {
                double dot=0; for(int j=0;j<3;++j) dot+=g.gradients[a][j]*g.gradients[b][j];
                double stiffness=lambda*g.gradients[a][i]*g.gradients[b][k]
                    +mu*g.gradients[a][k]*g.gradients[b][i]+(i==k?mu*dot:0);
                if(p.neo_hookean) {
                    stiffness=0;
                    for(int J=0;J<3;++J) for(int L=0;L<3;++L)
                        stiffness+=g.gradients[a][J]*material.tangent[(3*i+J)*9+3*k+L]*g.gradients[b][L];
                }
                e.tangent[(3*a+i)*12+3*b+k]=chain*g.volume*stiffness+(p.dt>0&&i==k?mass/p.dt:0);
            }
        }
    }
    return e;
}
}
