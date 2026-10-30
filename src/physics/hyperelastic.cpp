#include "eonsim/time_step.hpp"
#include "eonsim/hyperelastic.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
HyperelasticResponse neo_hookean(const Space3::Tensor<double>& F,double E,double nu,bool compute_tangent)
{
    if(!(E>0 && nu>-1 && nu<.5) || !std::isfinite(E+nu)) throw std::runtime_error("Invalid Neo-Hookean material");
    for(double value:F) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite deformation gradient");
    const double mu=E/(2*(1+nu)),lambda=E*nu/((1+nu)*(1-2*nu));
    HyperelasticResponse r;
    r.jacobian=F[Space3::index(0,0)]*(F[Space3::index(1,1)]*F[Space3::index(2,2)]-F[Space3::index(1,2)]*F[Space3::index(2,1)])-F[Space3::index(0,1)]*(F[Space3::index(1,0)]*F[Space3::index(2,2)]-F[Space3::index(1,2)]*F[Space3::index(2,0)])+F[Space3::index(0,2)]*(F[Space3::index(1,0)]*F[Space3::index(2,1)]-F[Space3::index(1,1)]*F[Space3::index(2,0)]);
    if(!(r.jacobian>0) || !std::isfinite(r.jacobian)) throw StepRejected("Nonpositive solid deformation Jacobian");
    Space3::Tensor<double> inverse_transpose;
    for(int i=0;i<Space3::dimension;++i) for(int J=0;J<Space3::dimension;++J)
        inverse_transpose[Space3::index(i,J)]=(F[Space3::index((i+1)%Space3::dimension,(J+1)%Space3::dimension)]*F[Space3::index((i+2)%Space3::dimension,(J+2)%Space3::dimension)]
            -F[Space3::index((i+1)%Space3::dimension,(J+2)%Space3::dimension)]*F[Space3::index((i+2)%Space3::dimension,(J+1)%Space3::dimension)])/r.jacobian;
    const double logJ=std::log(r.jacobian),c=lambda*logJ-mu;
    double invariant=0; for(double v:F) invariant+=v*v;
    r.energy=.5*mu*(invariant-Space3::dimension)-mu*logJ+.5*lambda*logJ*logJ;
    for(int i=0;i<Space3::dimension;++i) for(int J=0;J<Space3::dimension;++J) {
        r.first_piola[Space3::index(i,J)]=mu*F[Space3::index(i,J)]+c*inverse_transpose[Space3::index(i,J)];
        if(compute_tangent) for(int k=0;k<Space3::dimension;++k) for(int L=0;L<Space3::dimension;++L)
            r.tangent[Space3::derivative(i,J,k,L)]=(i==k&&J==L?mu:0)+lambda*inverse_transpose[Space3::index(i,J)]*inverse_transpose[Space3::index(k,L)]
                -c*inverse_transpose[Space3::index(i,L)]*inverse_transpose[Space3::index(k,J)];
    }
    for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) for(int J=0;J<Space3::dimension;++J)
        r.cauchy[Space3::index(i,j)]+=r.first_piola[Space3::index(i,J)]*F[Space3::index(j,J)]/r.jacobian;
    return r;
}
}
