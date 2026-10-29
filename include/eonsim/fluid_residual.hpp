#pragma once
/** @file @brief 单一残量表达，double 求值与固定宽度几何链式求导共用。 */
#include "eonsim/fluid_element.hpp"
#include "eonsim/quadrature.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
template<class Scalar>
Tet4Flow::State<Scalar> fluid_residual(const SimplexGeometry<Tet4Topology,Scalar>& g,const FluidParameters& p,
    const Tet4Flow::State<Scalar>& x,const Tet4Flow::State<double>& old,
    const Tet4Topology::Nodal<Space3::Vector<Scalar>>& w)
{
    if(!(p.density>0&&p.viscosity>0&&p.dt>=0&&p.tau>=0)||!std::isfinite(p.density+p.viscosity+p.dt+p.tau)) throw std::runtime_error("Invalid fluid material/time/stabilization");
    Tet4Flow::State<Scalar> result{};
    Scalar grad[Space3::dimension][Space3::dimension]{},gradp[Space3::dimension]{},divergence{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int j=0;j<Space3::dimension;++j) {
        gradp[j]+=x[Tet4Flow::dof(a,Tet4Flow::pressure)]*g.gradients[a][j];
        for(int i=0;i<Space3::dimension;++i) grad[i][j]+=x[Tet4Flow::dof(a,i)]*g.gradients[a][j];
    }
    for(int i=0;i<Space3::dimension;++i) divergence+=grad[i][i];
    const double mass=p.dt>0?p.density/p.dt:0;
    for(const auto& q:FluidQuadrature::points) {
        const auto& N=q.shape;
        Scalar u[Space3::dimension]{},c[Space3::dimension]{},rm[Space3::dimension]{},pressure{};
        double un[Space3::dimension]{};
        for(int a=0;a<Tet4Topology::nodes;++a) {
            pressure+=N[a]*x[Tet4Flow::dof(a,Tet4Flow::pressure)];
            for(int i=0;i<Space3::dimension;++i) {
                u[i]+=N[a]*x[Tet4Flow::dof(a,i)]; un[i]+=N[a]*old[Tet4Flow::dof(a,i)];
                if(p.convection) c[i]+=N[a]*(x[Tet4Flow::dof(a,i)]-w[a][i]);
            }
        }
        for(int i=0;i<Space3::dimension;++i) {
            rm[i]=mass*(u[i]-un[i])+gradp[i];
            for(int j=0;j<Space3::dimension;++j) rm[i]+=p.density*c[j]*grad[i][j];
        }
        for(int a=0;a<Tet4Topology::nodes;++a) {
            Scalar streamline{};
            for(int j=0;j<Space3::dimension;++j) streamline+=p.density*c[j]*g.gradients[a][j];
            for(int i=0;i<Space3::dimension;++i) {
                Scalar r=N[a]*(rm[i]-gradp[i])-pressure*g.gradients[a][i]+p.tau*streamline*rm[i];
                for(int j=0;j<Space3::dimension;++j) r+=p.viscosity*(grad[i][j]+grad[j][i])*g.gradients[a][j];
                result[Tet4Flow::dof(a,i)]+=g.volume*q.weight*r;
            }
            Scalar r=N[a]*divergence;
            for(int i=0;i<Space3::dimension;++i) r+=p.tau*g.gradients[a][i]*rm[i];
            result[Tet4Flow::dof(a,Tet4Flow::pressure)]+=g.volume*q.weight*r;
        }
    }
    return result;
}
}
