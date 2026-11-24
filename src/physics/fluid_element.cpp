#include "eonsim/fluid_element.hpp"
#include "eonsim/fluid_residual.hpp"
#include "eonsim/quadrature.hpp"

namespace eonsim {
FluidElement fluid_element(const Tet4Geometry& g, const FluidParameters& p,
    const Tet4Flow::State<double>& x, const Tet4Flow::State<double>& old,
    const Tet4Topology::Nodal<Point>& w, bool compute_tangent)
{
    FluidElement e;
    e.residual=fluid_residual(g,p,x,old,w);
    if(!compute_tangent) return e;
    // Integral of 2 mu eps(N_b e_k) : eps(N_a e_i) on this affine Tet4.
    const double viscous_weight=g.volume*p.viscosity;
    for(int a=0;a<Tet4Topology::nodes;++a) for(int b=0;b<Tet4Topology::nodes;++b) {
        const auto& ga=g.gradients[a];
        const auto& gb=g.gradients[b];
        double dot=0;
        for(int j=0;j<Space3::dimension;++j) dot+=ga[j]*gb[j];
        for(int i=0;i<Space3::dimension;++i) for(int k=0;k<Space3::dimension;++k)
            e.tangent[Tet4Flow::matrix(Tet4Flow::dof(a,i),Tet4Flow::dof(b,k))]=
                viscous_weight*(ga[k]*gb[i]+(i==k?dot:0.0));
    }
    if(p.grad_div_viscosity>0) {
        const double weight=g.volume*p.grad_div_viscosity;
        for(int a=0;a<Tet4Topology::nodes;++a) for(int b=0;b<Tet4Topology::nodes;++b)
            for(int i=0;i<Space3::dimension;++i) for(int k=0;k<Space3::dimension;++k)
                e.tangent[Tet4Flow::matrix(Tet4Flow::dof(a,i),Tet4Flow::dof(b,k))]+=
                    weight*g.gradients[a][i]*g.gradients[b][k];
    }
    double grad[Space3::dimension][Space3::dimension]{}, gradp[Space3::dimension]{};
    for (int a=0;a<Tet4Topology::nodes;++a) for (int j=0;j<Space3::dimension;++j) {
        gradp[j] += x[Tet4Flow::dof(a,Tet4Flow::pressure)]*g.gradients[a][j];
        for (int i=0;i<Space3::dimension;++i) grad[i][j] += x[Tet4Flow::dof(a,i)]*g.gradients[a][j];
    }
    const double mass=p.dt>0 ? p.density/p.dt : 0;
    // 对称四点积分精确积分本核固定 tau 下的三次以下被积项中的二次项；
    // SUPG 的三次对流项用四点规则近似，残量与切线使用完全相同规则。
    for (const auto& point:FluidQuadrature::points) {
        const auto& N=point.shape;
        double velocity_increment[Space3::dimension]{},c[Space3::dimension]{},rm[Space3::dimension]{};
        for (int a=0;a<Tet4Topology::nodes;++a) for (int i=0;i<Space3::dimension;++i) {
            velocity_increment[i]+=N[a]*(x[Tet4Flow::dof(a,i)]-old[Tet4Flow::dof(a,i)]);
            if(p.convection) c[i]+=N[a]*(x[Tet4Flow::dof(a,i)]-w[a][i]);
        }
        for(int i=0;i<Space3::dimension;++i) {
            rm[i]=mass*velocity_increment[i]+gradp[i];
            for(int j=0;j<Space3::dimension;++j) rm[i]+=p.density*c[j]*grad[i][j];
        }
        const double weight=g.volume*point.weight;
        for(int a=0;a<Tet4Topology::nodes;++a) {
            double streamline=0;
            for(int j=0;j<Space3::dimension;++j) streamline+=p.density*c[j]*g.gradients[a][j];
            for(int b=0;b<Tet4Topology::nodes;++b) for(int k=0;k<Tet4Flow::components;++k) {
                double drm[Space3::dimension]{};
                for(int i=0;i<Space3::dimension;++i) {
                    if(k==Tet4Flow::pressure) drm[i]=g.gradients[b][i];
                    else {
                        if(i==k) {
                            drm[i]=mass*N[b];
                            for(int j=0;j<Space3::dimension;++j) drm[i]+=p.density*c[j]*g.gradients[b][j];
                        }
                        if(p.convection) drm[i]+=p.density*N[b]*grad[i][k];
                    }
                }
                for(int i=0;i<Space3::dimension;++i) {
                    double v=N[a]*(drm[i]-(k==Tet4Flow::pressure ? g.gradients[b][i] : 0));
                    if(k==Tet4Flow::pressure) v-=N[b]*g.gradients[a][i];
                    v+=p.tau*streamline*drm[i];
                    if(k<Space3::dimension && p.convection) v+=p.tau*p.density*N[b]*g.gradients[a][k]*rm[i];
                    e.tangent[Tet4Flow::matrix(Tet4Flow::dof(a,i),Tet4Flow::dof(b,k))]+=weight*v;
                }
                double v=k<Space3::dimension ? N[a]*g.gradients[b][k] : 0;
                for(int i=0;i<Space3::dimension;++i) v+=p.tau*g.gradients[a][i]*drm[i];
                e.tangent[Tet4Flow::matrix(Tet4Flow::dof(a,Tet4Flow::pressure),Tet4Flow::dof(b,k))]+=weight*v;
            }
        }
    }
    return e;
}
}
