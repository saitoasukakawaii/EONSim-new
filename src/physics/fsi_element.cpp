#include "eonsim/fsi_element.hpp"
#include <cmath>
namespace eonsim {
std::array<double,28> fsi_element_residual(const FsiElementData& data,const std::array<double,28>& x)
{
    std::array<Point,4> current,velocity;
    std::array<double,16> fluid;
    for(int a=0;a<4;++a) {
        for(int c=0;c<3;++c) {
            current[a][c]=data.reference[a][c]+x[7*a+4+c];
            velocity[a][c]=(x[7*a+4+c]-data.previous_mesh[a][c])/data.fluid.dt;
        }
        for(int c=0;c<4;++c) fluid[4*a+c]=x[7*a+c];
    }
    const auto r=fluid_element(tet4_geometry(current),data.fluid,fluid,data.previous_fluid,velocity,false);
    const auto k=poisson_element(tet4_geometry(data.reference),1,0);
    std::array<double,28> result{};
    for(int a=0;a<4;++a) {
        for(int c=0;c<4;++c) result[7*a+c]=r.residual[4*a+c];
        for(int c=0;c<3;++c) for(int b=0;b<4;++b) result[7*a+4+c]+=k.stiffness[4*a+b]*x[7*b+4+c];
    }
    for(const auto& face:data.inlet_faces) {
        const auto& a=current[face[0]]; const auto& b=current[face[1]]; const auto& c=current[face[2]];
        Point ab,ac,n;
        for(int i=0;i<3;++i) { ab[i]=b[i]-a[i]; ac[i]=c[i]-a[i]; }
        for(int i=0;i<3;++i) n[i]=(ab[(i+1)%3]*ac[(i+2)%3]-ab[(i+2)%3]*ac[(i+1)%3])/2;
        int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
        double dot=0; for(int i=0;i<3;++i) dot+=n[i]*(current[opposite][i]-a[i]);
        if(dot>0) for(double& v:n) v=-v;
        for(int node:face) for(int i=0;i<3;++i) result[7*node+i]+=data.inlet_pressure*n[i]/3;
    }
    return result;
}
std::array<double,784> fsi_element_tangent(const FsiElementData& data,const std::array<double,28>& x)
{
    std::array<double,784> tangent{};
    for(int c=0;c<28;++c) {
        const double eps=1e-6*std::max(1.,std::abs(x[c]));
        auto plus=x,minus=x; plus[c]+=eps; minus[c]-=eps;
        const auto rp=fsi_element_residual(data,plus),rm=fsi_element_residual(data,minus);
        for(int r=0;r<28;++r) tangent[28*r+c]=(rp[r]-rm[r])/(2*eps);
    }
    return tangent;
}
}
