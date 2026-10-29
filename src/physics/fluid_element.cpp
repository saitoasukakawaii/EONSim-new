#include "eonsim/fluid_element.hpp"
#include <cmath>
#include <stdexcept>

namespace eonsim {
FluidElement fluid_element(const Tet4Geometry& g, const FluidParameters& p,
    const std::array<double,16>& x, const std::array<double,16>& old,
    const std::array<Point,4>& w, bool compute_tangent)
{
    if (!(p.density>0 && p.viscosity>0 && p.dt>=0 && p.tau>=0) ||
        !std::isfinite(p.density+p.viscosity+p.dt+p.tau))
        throw std::runtime_error("Invalid fluid material/time/stabilization");
    FluidElement e;
    double grad[3][3]{}, gradp[3]{};
    for (int a=0;a<4;++a) for (int j=0;j<3;++j) {
        gradp[j] += x[4*a+3]*g.gradients[a][j];
        for (int i=0;i<3;++i) grad[i][j] += x[4*a+i]*g.gradients[a][j];
    }
    const double divergence=grad[0][0]+grad[1][1]+grad[2][2];
    const double mass=p.dt>0 ? p.density/p.dt : 0;
    // 对称四点积分精确积分本核固定 tau 下的三次以下被积项中的二次项；
    // SUPG 的三次对流项用四点规则近似，残量与切线使用完全相同规则。
    for (int q=0;q<4;++q) {
        double N[4],u[3]{},un[3]{},c[3]{},rm[3]{};
        for (int a=0;a<4;++a) N[a]=a==q ? .5854101966249685 : .1381966011250105;
        for (int a=0;a<4;++a) for (int i=0;i<3;++i) {
            u[i]+=N[a]*x[4*a+i]; un[i]+=N[a]*old[4*a+i];
            if(p.convection) c[i]+=N[a]*(x[4*a+i]-w[a][i]);
        }
        for(int i=0;i<3;++i) {
            rm[i]=mass*(u[i]-un[i])+gradp[i];
            for(int j=0;j<3;++j) rm[i]+=p.density*c[j]*grad[i][j];
        }
        const double weight=g.volume/4;
        double pressure=0;
        for(int a=0;a<4;++a) pressure+=N[a]*x[4*a+3];
        for(int a=0;a<4;++a) {
            double streamline=0;
            for(int j=0;j<3;++j) streamline+=p.density*c[j]*g.gradients[a][j];
            for(int i=0;i<3;++i) {
                double r=N[a]*(rm[i]-gradp[i])-pressure*g.gradients[a][i]+p.tau*streamline*rm[i];
                for(int j=0;j<3;++j) r+=p.viscosity*(grad[i][j]+grad[j][i])*g.gradients[a][j];
                e.residual[4*a+i]+=weight*r;
            }
            double rp=N[a]*divergence;
            for(int i=0;i<3;++i) rp+=p.tau*g.gradients[a][i]*rm[i];
            e.residual[4*a+3]+=weight*rp;
            if(compute_tangent) for(int b=0;b<4;++b) for(int k=0;k<4;++k) {
                double drm[3]{};
                for(int i=0;i<3;++i) {
                    if(k==3) drm[i]=g.gradients[b][i];
                    else {
                        if(i==k) {
                            drm[i]=mass*N[b];
                            for(int j=0;j<3;++j) drm[i]+=p.density*c[j]*g.gradients[b][j];
                        }
                        if(p.convection) drm[i]+=p.density*N[b]*grad[i][k];
                    }
                }
                for(int i=0;i<3;++i) {
                    double v=N[a]*(drm[i]-(k==3 ? g.gradients[b][i] : 0));
                    if(k==3) v-=N[b]*g.gradients[a][i];
                    else {
                        for(int j=0;j<3;++j) v+=p.viscosity*((i==k ? g.gradients[b][j] : 0)
                            +(j==k ? g.gradients[b][i] : 0))*g.gradients[a][j];
                    }
                    v+=p.tau*streamline*drm[i];
                    if(k<3 && p.convection) v+=p.tau*p.density*N[b]*g.gradients[a][k]*rm[i];
                    e.tangent[(4*a+i)*16+4*b+k]+=weight*v;
                }
                double v=k<3 ? N[a]*g.gradients[b][k] : 0;
                for(int i=0;i<3;++i) v+=p.tau*g.gradients[a][i]*drm[i];
                e.tangent[(4*a+3)*16+4*b+k]+=weight*v;
            }
        }
    }
    return e;
}
}
