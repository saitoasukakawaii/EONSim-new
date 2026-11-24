/** @file @brief 稳态/瞬态、移动网格速度输入下的解析 Jacobian 方向导数验证。 */
#include "eonsim/fluid_element.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
int main() {
    using namespace eonsim;
    const Tet4Topology::Nodal<Point> coordinates{Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}};
    const auto g=tet4_geometry(coordinates);
    // Simple shear gives a known nodal force. Setting u_y = -shear*x
    // together with u_x = shear*y gives rigid rotation and zero viscous stress.
    const FluidParameters stokes{1.0,.6,0.0,0.0,false};
    const double shear=1.7;
    for(double y_slope:{0.0,-shear}) {
        Tet4Flow::State<double> state{};
        for(int a=0;a<Tet4Topology::nodes;++a) {
            state[Tet4Flow::dof(a,0)]=shear*coordinates[a][1];
            state[Tet4Flow::dof(a,1)]=y_slope*coordinates[a][0];
        }
        const auto element=fluid_element(g,stokes,state,{},{});
        const double stress_integral=g.volume*stokes.viscosity*(shear+y_slope);
        for(int a=0;a<Tet4Topology::nodes;++a) {
            const std::array<double,4> expected{
                stress_integral*g.gradients[a][1],stress_integral*g.gradients[a][0],0.0,0.0};
            for(int i=0;i<Tet4Flow::components;++i) {
                const int row=Tet4Flow::dof(a,i);
                double action=0.0;
                for(int col=0;col<Tet4Flow::dofs;++col)
                    action+=element.tangent[Tet4Flow::matrix(row,col)]*state[col];
                if(!(std::abs(element.residual[row]-expected[i])<2e-13 &&
                     std::abs(action-expected[i])<2e-13))
                    throw std::runtime_error("Affine Stokes shear or rigid rotation mismatch");
            }
        }
    }
    // A representable one-ULP velocity increment over the same dt gives unit
    // acceleration everywhere, including at quadrature points.
    const Tet4Topology::Nodal<Point> unit{Point{0,0,0},Point{1,0,0},Point{0,1,0},Point{0,0,1}};
    const auto unit_geometry=tet4_geometry(unit);
    const double initial=1.5,updated=std::nextafter(initial,2.);
    Tet4Flow::State<double> uniform{},previous{};
    for(int a=0;a<Tet4Topology::nodes;++a) {
        uniform[Tet4Flow::dof(a,0)]=updated;
        previous[Tet4Flow::dof(a,0)]=initial;
    }
    const auto inertia=fluid_element(unit_geometry,{1.,1.,updated-initial,0.,false},uniform,previous,{},false);
    for(int a=0;a<Tet4Topology::nodes;++a)
        if(!(std::abs(inertia.residual[Tet4Flow::dof(a,0)]-unit_geometry.volume/4)<1e-15))
            throw std::runtime_error("Uniform small-step inertia mismatch");
    std::array<double,16> x{},old{},direction{};
    std::array<Point,4> w{};
    for(int i=0;i<16;++i) { x[i]=.3*std::sin(i+1); old[i]=.2*std::cos(i+1); direction[i]=std::sin(3*i+.7); }
    for(int a=0;a<4;++a) for(int c=0;c<3;++c) w[a][c]=.03*std::cos(a+c);
    // Manufactured affine field with div u = 3. Verify the weak sign, the
    // zero pressure rows, and the work V * gamma * (div u)^2 independently.
    Tet4Flow::State<double> dilation{};
    for(int a=0;a<4;++a) for(int i=0;i<3;++i) dilation[Tet4Flow::dof(a,i)]=unit[a][i];
    const auto base=fluid_element(unit_geometry,{1.,1.,0.,0.,false},dilation,{},{});
    const auto penalized=fluid_element(unit_geometry,{1.,1.,0.,0.,false,.7},dilation,{},{});
    double work=0;
    for(int a=0;a<4;++a) {
        if(base.residual[Tet4Flow::dof(a,3)]!=penalized.residual[Tet4Flow::dof(a,3)])
            throw std::runtime_error("Grad-div changed the continuity equation");
        for(int i=0;i<3;++i) {
            const auto row=Tet4Flow::dof(a,i);
            const double added=penalized.residual[row]-base.residual[row];
            if(std::abs(added-unit_geometry.volume*.7*3*unit_geometry.gradients[a][i])>1e-14)
                throw std::runtime_error("Incorrect grad-div force on affine flow");
            work+=dilation[row]*added;
        }
    }
    if(std::abs(work-unit_geometry.volume*.7*9)>1e-14) throw std::runtime_error("Incorrect grad-div work");
    for(bool convection:{false,true}) for(double dt:{0.,.07}) for(double gd:{0.,.7}) {
        const FluidParameters p{1.3,.6,dt,.02,convection,gd};
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
