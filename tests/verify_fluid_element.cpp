/** @file @brief 稳态/瞬态、移动网格速度输入下的解析 Jacobian 方向导数验证。 */
#include "eonsim/fluid_element.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
int main() {
    using namespace eonsim;
    const auto g=tet4_geometry({Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}});
    std::array<double,16> x{},old{},direction{};
    std::array<Point,4> w{};
    for(int i=0;i<16;++i) { x[i]=.3*std::sin(i+1); old[i]=.2*std::cos(i+1); direction[i]=std::sin(3*i+.7); }
    for(int a=0;a<4;++a) for(int c=0;c<3;++c) w[a][c]=.03*std::cos(a+c);
    for(bool convection:{false,true}) for(double dt:{0.,.07}) {
        const FluidParameters p{1.3,.6,dt,.02,convection};
        const auto e=fluid_element(g,p,x,old,w);
        const auto residual_only=fluid_element(g,p,x,old,w,false);
        if(residual_only.residual!=e.residual) throw std::runtime_error("Residual-only fluid response changed");
        for(double value:residual_only.tangent) if(value!=0) throw std::runtime_error("Residual-only fluid computed a tangent");
        auto plus=x,minus=x;
        const double eps=1e-6;
        for(int i=0;i<16;++i) { plus[i]+=eps*direction[i]; minus[i]-=eps*direction[i]; }
        const auto rp=fluid_element(g,p,plus,old,w,false),rm=fluid_element(g,p,minus,old,w,false);
        double error=0,norm=0;
        for(int i=0;i<16;++i) {
            double jv=0; for(int j=0;j<16;++j) jv+=e.tangent[i*16+j]*direction[j];
            const double fd=(rp.residual[i]-rm.residual[i])/(2*eps);
            error+=(fd-jv)*(fd-jv); norm+=jv*jv;
        }
        const double relative=std::sqrt(error/norm);
        std::cout << "convection=" << convection << " dt=" << dt << " jv_relative_error=" << relative << '\n';
        if(!std::isfinite(relative)||relative>2e-8) throw std::runtime_error("Fluid Jacobian mismatch");
    }
}
