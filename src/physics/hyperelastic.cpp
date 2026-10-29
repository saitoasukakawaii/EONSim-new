#include "eonsim/hyperelastic.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
HyperelasticResponse neo_hookean(const std::array<double,9>& F,double E,double nu)
{
    if(!(E>0 && nu>-1 && nu<.5) || !std::isfinite(E+nu)) throw std::runtime_error("Invalid Neo-Hookean material");
    for(double value:F) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deformation gradient");
    const double mu=E/(2*(1+nu)),lambda=E*nu/((1+nu)*(1-2*nu));
    HyperelasticResponse r;
    r.jacobian=F[0]*(F[4]*F[8]-F[5]*F[7])-F[1]*(F[3]*F[8]-F[5]*F[6])+F[2]*(F[3]*F[7]-F[4]*F[6]);
    if(!(r.jacobian>0) || !std::isfinite(r.jacobian)) throw std::runtime_error("Nonpositive solid deformation Jacobian");
    std::array<double,9> inverse_transpose;
    for(int i=0;i<3;++i) for(int J=0;J<3;++J)
        inverse_transpose[3*i+J]=(F[3*((i+1)%3)+(J+1)%3]*F[3*((i+2)%3)+(J+2)%3]
            -F[3*((i+1)%3)+(J+2)%3]*F[3*((i+2)%3)+(J+1)%3])/r.jacobian;
    const double logJ=std::log(r.jacobian),c=lambda*logJ-mu;
    double invariant=0; for(double v:F) invariant+=v*v;
    r.energy=.5*mu*(invariant-3)-mu*logJ+.5*lambda*logJ*logJ;
    for(int i=0;i<3;++i) for(int J=0;J<3;++J) {
        r.first_piola[3*i+J]=mu*F[3*i+J]+c*inverse_transpose[3*i+J];
        for(int k=0;k<3;++k) for(int L=0;L<3;++L)
            r.tangent[(3*i+J)*9+3*k+L]=(i==k&&J==L?mu:0)+lambda*inverse_transpose[3*i+J]*inverse_transpose[3*k+L]
                -c*inverse_transpose[3*i+L]*inverse_transpose[3*k+J];
    }
    for(int i=0;i<3;++i) for(int j=0;j<3;++j) for(int J=0;J<3;++J)
        r.cauchy[3*i+j]+=r.first_piola[3*i+J]*F[3*j+J]/r.jacobian;
    return r;
}
}
