/** @file @brief 全 ALE 局部耦合切线，独立方向扰动覆盖几何/压力面积/网格速度。 */
#include "eonsim/fsi_element.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
int main() {
    using namespace eonsim;
    FsiElementData data({Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}});
    data.inlet_faces={{0,2,3}}; data.fluid={1.3,.6,.07,.02,true}; data.inlet_pressure=.8;
    Tet4Ale::State<double> x{},direction{};
    for(int i=0;i<Tet4Ale::dofs;++i) { x[i]=.015*std::sin(i+1); direction[i]=std::sin(3*i+.7); }
    for(int i=0;i<Tet4Flow::dofs;++i) data.previous_fluid[i]=.03*std::cos(i+.2);
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) data.previous_mesh[a][c]=.002*std::sin(a+c+.1);
    const auto jac=fsi_element_tangent(data,x);
    for(int field=0;field<2;++field) {
        auto plus=x,minus=x;
        const double eps=2e-7;
        for(int i=0;i<Tet4Ale::dofs;++i) { const double d=(i%Tet4Ale::components<Tet4Flow::components)==(field==0)?direction[i]:0; plus[i]+=eps*d; minus[i]-=eps*d; }
        const auto rp=fsi_element_residual(data,plus),rm=fsi_element_residual(data,minus);
        double error=0,norm=0;
        for(int i=0;i<Tet4Ale::dofs;++i) {
            double jv=0; for(int j=0;j<Tet4Ale::dofs;++j) if((j%Tet4Ale::components<Tet4Flow::components)==(field==0)) jv+=jac[Tet4Ale::matrix(i,j)]*direction[j];
            const double fd=(rp[i]-rm[i])/(2*eps);
            error+=(fd-jv)*(fd-jv); norm+=jv*jv;
        }
        const double relative=std::sqrt(error/norm);
        std::cout << "field=" << field << " jv_relative_error=" << relative << '\n';
        if(!std::isfinite(relative)||relative>2e-8) throw std::runtime_error("FSI coupled Jacobian mismatch");
    }
}
