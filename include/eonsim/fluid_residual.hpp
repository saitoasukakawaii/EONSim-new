#pragma once
/** @file @brief 单一残量表达，double 求值与固定宽度几何链式求导共用。 */
#include "eonsim/fluid_element.hpp"
#include "eonsim/dual.hpp"
#include <cmath>
#include <stdexcept>
namespace eonsim {
template<class Scalar,class Coefficient>
Tet4Flow::State<Scalar> fluid_residual(const SimplexGeometry<Tet4Topology,Scalar>& g,const FluidParameters& p,
    const Tet4Flow::State<Scalar>& x,const Tet4Flow::State<double>& old,
    const Tet4Topology::Nodal<Space3::Vector<Scalar>>& w,const Coefficient& tau,const Coefficient& grad_div)
{
    if(!(p.density>0&&p.viscosity>0&&p.dt>=0&&primal(tau)>=0&&primal(grad_div)>=0)||!std::isfinite(p.density+p.viscosity+p.dt+primal(tau)+primal(grad_div))) throw std::runtime_error("Invalid fluid material/time/stabilization");
    Tet4Flow::State<Scalar> result{};
    Scalar grad[Space3::dimension][Space3::dimension]{},gradp[Space3::dimension]{},divergence{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int j=0;j<Space3::dimension;++j) {
        add_product(gradp[j],x[Tet4Flow::dof(a,Tet4Flow::pressure)],g.gradients[a][j]);
        for(int i=0;i<Space3::dimension;++i)
            add_product(grad[i][j],x[Tet4Flow::dof(a,i)],g.gradients[a][j]);
    }
    for(int i=0;i<Space3::dimension;++i) divergence+=grad[i][i];
    // On an affine P1 tetrahedron with cellwise viscosity, the viscous stress
    // and test gradients are constant. Keep the volume and gradients active
    // for the ALE geometry derivative.
    const Scalar viscous_weight=g.volume*p.viscosity;
    for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) {
        const Scalar integrated_stress=viscous_weight*(grad[i][j]+grad[j][i]);
        for(int a=0;a<Tet4Topology::nodes;++a)
            add_product(result[Tet4Flow::dof(a,i)],integrated_stress,g.gradients[a][j]);
    }
    // An affine P1 velocity has constant divergence on the current cell.
    if(primal(grad_div)>0) {
        const Scalar penalty=g.volume*grad_div*divergence;
        for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i)
            add_product(result[Tet4Flow::dof(a,i)],penalty,g.gradients[a][i]);
    }
    // For affine Tet4 with spatially constant cellwise tau, the advective velocity and
    // strong momentum residual are P1. Their products use the exact P1 mass
    // moments, integral(N_a N_b)/V = (1 + delta_ab)/20.
    const double mass=p.dt>0?p.density/p.dt:0;
    constexpr double mean_shape=Tet4Topology::mean_weight;
    constexpr double off_diagonal_mass=1.0/(Tet4Topology::nodes*(Tet4Topology::nodes+1));
    Tet4Topology::Nodal<Space3::Vector<Scalar>> transport{},momentum{};
    Space3::Vector<Scalar> momentum_sum{};
    Scalar mean_pressure{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        mean_pressure+=mean_shape*x[Tet4Flow::dof(a,Tet4Flow::pressure)];
        if(p.convection) for(int j=0;j<Space3::dimension;++j)
            transport[a][j]=p.density*(x[Tet4Flow::dof(a,j)]-w[a][j]);
        for(int i=0;i<Space3::dimension;++i) {
            const int row=Tet4Flow::dof(a,i);
            momentum[a][i]=mass*(x[row]-old[row]);
            if(p.convection) for(int j=0;j<Space3::dimension;++j)
                add_product(momentum[a][i],transport[a][j],grad[i][j]);
            momentum_sum[i]+=momentum[a][i];
        }
    }
    Space3::Vector<Scalar> mean_strong{};
    for(int i=0;i<Space3::dimension;++i) mean_strong[i]=mean_shape*momentum_sum[i]+gradp[i];
    Space3::Vector<Space3::Vector<Scalar>> supg_flux{};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int i=0;i<Space3::dimension;++i) {
        const Scalar tested_momentum=off_diagonal_mass*(momentum_sum[i]+momentum[a][i]);
        result[Tet4Flow::dof(a,i)]+=g.volume*(tested_momentum-mean_pressure*g.gradients[a][i]);
        if(p.convection && primal(tau)>0) {
            const Scalar tested_strong=tested_momentum+mean_shape*gradp[i];
            for(int j=0;j<Space3::dimension;++j) add_product(supg_flux[i][j],transport[a][j],tested_strong);
        }
    }
    for(int a=0;a<Tet4Topology::nodes;++a) {
        Scalar continuity=mean_shape*divergence;
        if(primal(tau)>0) {
            for(int j=0;j<Space3::dimension;++j) continuity+=tau*g.gradients[a][j]*mean_strong[j];
            if(p.convection) for(int i=0;i<Space3::dimension;++i) {
                Scalar streamline{};
                for(int j=0;j<Space3::dimension;++j) add_product(streamline,g.gradients[a][j],supg_flux[i][j]);
                result[Tet4Flow::dof(a,i)]+=g.volume*tau*streamline;
            }
        }
        result[Tet4Flow::dof(a,Tet4Flow::pressure)]+=g.volume*continuity;
    }
    return result;
}
template<class Scalar>
Tet4Flow::State<Scalar> fluid_residual(const SimplexGeometry<Tet4Topology,Scalar>& g,const FluidParameters& p,
    const Tet4Flow::State<Scalar>& x,const Tet4Flow::State<double>& old,
    const Tet4Topology::Nodal<Space3::Vector<Scalar>>& w)
{
    return fluid_residual(g,p,x,old,w,p.tau,p.grad_div_viscosity);
}

}
