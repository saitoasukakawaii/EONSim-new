/** @file @brief 小应变材料与 BE 链式切线方向导数、刚体平移检查。 */
#include "eonsim/solid_element.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
int main() {
    using namespace eonsim;
    const auto g=tet4_geometry({Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}});
    std::array<double,12> x{},dn{},vn{},direction{};
    for(int i=0;i<12;++i) { x[i]=.03*std::sin(i+1); dn[i]=.02*std::cos(i+1); vn[i]=.04*std::sin(2*i); direction[i]=std::sin(3*i+.7); }
    for(double dt:{0.,.03}) {
        const SolidParameters p{120,.28,1.3,dt};
        const auto e=solid_element(g,p,x,dn,vn);
        auto plus=x,minus=x;
        const double eps=1e-6;
        for(int i=0;i<12;++i) { plus[i]+=eps*direction[i]; minus[i]-=eps*direction[i]; }
        const auto rp=solid_element(g,p,plus,dn,vn),rm=solid_element(g,p,minus,dn,vn);
        double error=0,norm=0;
        for(int i=0;i<12;++i) {
            double jv=0; for(int j=0;j<12;++j) jv+=e.tangent[i*12+j]*direction[j];
            const double fd=(rp.residual[i]-rm.residual[i])/(2*eps);
            error+=(fd-jv)*(fd-jv); norm+=jv*jv;
        }
        const double relative=std::sqrt(error/norm);
        std::cout << "dt=" << dt << " jv_relative_error=" << relative << '\n';
        if(!std::isfinite(relative)||relative>2e-8) throw std::runtime_error("Solid Jacobian mismatch");
    }
    for(int a=0;a<4;++a) for(int c=0;c<3;++c) x[3*a+c]=.1*(c+1);
    const auto rigid=solid_element(g,{120,.28,1,0},x,{},{});
    if(std::abs(rigid.strain_energy)>1e-20) throw std::runtime_error("Rigid translation stores strain energy");
}
