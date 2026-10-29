/** @file @brief Neo-Hookean 能量/应力/切线、刚体旋转客观性及 Nanson 牵引映射。 */
#include "eonsim/hyperelastic.hpp"
#include "eonsim/solid_element.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
int main() {
    using namespace eonsim;
    std::array<double,9> F={1.2,.1,.03,.02,.9,.04,.01,.03,1.1},D;
    for(int i=0;i<9;++i) D[i]=std::sin(i+.4);
    const auto response=neo_hookean(F,120,.28);
    auto plus=F,minus=F;
    const double eps=1e-6;
    for(int i=0;i<9;++i) { plus[i]+=eps*D[i]; minus[i]-=eps*D[i]; }
    const auto rp=neo_hookean(plus,120,.28),rm=neo_hookean(minus,120,.28);
    double energy=0,error=0,norm=0;
    for(int i=0;i<9;++i) {
        energy+=response.first_piola[i]*D[i];
        double jv=0; for(int j=0;j<9;++j) jv+=response.tangent[i*9+j]*D[j];
        double delta=(rp.first_piola[i]-rm.first_piola[i])/(2*eps)-jv;
        error+=delta*delta; norm+=jv*jv;
    }
    if(std::abs((rp.energy-rm.energy)/(2*eps)-energy)>1e-7 || std::sqrt(error/norm)>1e-8)
        throw std::runtime_error("Hyperelastic derivative mismatch");
    const double c=std::cos(.7),s=std::sin(.7);
    const std::array<double,9> Q={c,-s,0,s,c,0,0,0,1};
    const auto rotation=neo_hookean(Q,120,.28);
    if(std::abs(rotation.energy)>1e-12) throw std::runtime_error("Rigid rotation stores energy");
    for(double value:rotation.first_piola) if(std::abs(value)>1e-12) throw std::runtime_error("Rigid rotation has stress");
    // N=e_x: deformed oriented area is cofactor(F)*N; sigma*area == P*N.
    std::array<double,3> area;
    for(int i=0;i<3;++i) area[i]=F[3*((i+1)%3)+1]*F[3*((i+2)%3)+2]-F[3*((i+1)%3)+2]*F[3*((i+2)%3)+1];
    for(int i=0;i<3;++i) {
        double traction=0; for(int j=0;j<3;++j) traction+=response.cauchy[3*i+j]*area[j];
        if(std::abs(traction-response.first_piola[3*i])>1e-11) throw std::runtime_error("Reference/current traction mismatch");
    }
    const std::array<Point,4> xyz={Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}};
    const auto g=tet4_geometry(xyz);
    std::array<double,12> x,dn,vn,direction;
    for(int i=0;i<12;++i) { x[i]=.03*std::sin(i+1); dn[i]=.02*std::cos(i+1); vn[i]=.04*std::sin(2*i); direction[i]=std::sin(3*i+.7); }
    for(double dt:{0.,.03}) {
        const SolidParameters p{120,.28,1.3,dt,true};
        const auto e=solid_element(g,p,x,dn,vn);
        auto xp=x,xm=x;
        for(int i=0;i<12;++i) { xp[i]+=eps*direction[i]; xm[i]-=eps*direction[i]; }
        const auto ep=solid_element(g,p,xp,dn,vn),em=solid_element(g,p,xm,dn,vn);
        error=norm=0;
        for(int i=0;i<12;++i) {
            double jv=0; for(int j=0;j<12;++j) jv+=e.tangent[12*i+j]*direction[j];
            const double delta=(ep.residual[i]-em.residual[i])/(2*eps)-jv;
            error+=delta*delta; norm+=jv*jv;
        }
        if(std::sqrt(error/norm)>1e-8) throw std::runtime_error("Neo-Hookean BE element tangent mismatch");
    }
    bool rejected=false;
    try { (void)neo_hookean({-1,0,0,0,1,0,0,0,1},120,.28); } catch(const std::runtime_error&) { rejected=true; }
    if(!rejected) throw std::runtime_error("Inverted deformation accepted");
    std::cout << "Neo-Hookean energy, objectivity, tangents and traction mapping passed\n";
}
