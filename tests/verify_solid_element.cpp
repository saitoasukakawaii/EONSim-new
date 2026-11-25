/** @file @brief 小应变材料与 BE 链式切线方向导数、刚体平移检查。 */
#include "eonsim/solid_element.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
namespace {
void verify_normal_support() {
    using namespace eonsim;
    // Oblique facet and nonconsecutive local nodes exercise the projection and indexing.
    const WallSupportFace face{{3,0,2},{2.4,{1./3,2./3,2./3}},8.,1.7};
    const Point tangent{0,1,-1};
    Tet4Vector::State<double> d{},v{},direction{};
    for(int a=0;a<3;++a) for(int c=0;c<3;++c) {
        const auto i=Tet4Vector::dof(face.nodes[a],c);
        d[i]=(.1+a*.03)*face.geometry.normal[c]+a*tangent[c];
        v[i]=(-.04+a*.01)*face.geometry.normal[c]-.7*tangent[c];
        direction[i]=std::sin(.5+i);
    }
    constexpr double dt=.13;
    SolidElement assembled;
    const auto actual=face.evaluate(d,v,dt,&assembled,true);
    // Independent degree-two three-point quadrature.
    SolidElement expected;
    WallSupportBalance balance;
    for(int q=0;q<3;++q) {
        double displacement=0,velocity=0;
        for(int a=0;a<3;++a) {
            const double shape=q==a?2./3:1./6;
            displacement+=shape*(.1+a*.03+dt*(-.04+a*.01));
            velocity+=shape*(-.04+a*.01);
        }
        const double weight=face.geometry.area/3;
        const double traction=face.stiffness*displacement+face.damping*velocity;
        balance.spring_energy+=weight*.5*face.stiffness*displacement*displacement;
        balance.dissipation+=weight*face.damping*velocity*velocity;
        balance.power_on_wall-=weight*traction*velocity;
        for(int a=0;a<3;++a) for(int c=0;c<3;++c)
            expected.residual[Tet4Vector::dof(face.nodes[a],c)]+=weight*(q==a?2./3:1./6)*traction*face.geometry.normal[c];
    }
    const auto close=[](double x,double y,double tol) {
        if(!std::isfinite(x)||std::abs(x-y)>tol) throw std::runtime_error("Reference-normal wall support mismatch");
    };
    close(actual.spring_energy,balance.spring_energy,2e-15);
    close(actual.dissipation,balance.dissipation,2e-15);
    close(actual.power_on_wall,balance.power_on_wall,2e-15);
    auto plus=v,minus=v;
    constexpr double eps=1e-6;
    for(int i=0;i<12;++i) {plus[i]+=eps*direction[i];minus[i]-=eps*direction[i];}
    SolidElement rp,rm;
    face.evaluate(d,plus,dt,&rp);face.evaluate(d,minus,dt,&rm);
    double virtual_power=0;
    for(int i=0;i<12;++i) {
        close(assembled.residual[i],expected.residual[i],3e-15);
        double jv=0;
        for(int j=0;j<12;++j) jv+=assembled.tangent[Tet4Vector::matrix(i,j)]*direction[j];
        close(jv,(rp.residual[i]-rm.residual[i])/(2*eps),3e-10);
        virtual_power-=v[i]*assembled.residual[i];
    }
    close(virtual_power,actual.power_on_wall,3e-15);
    Tet4Vector::State<double> sliding{};
    for(int a:face.nodes) for(int c=0;c<3;++c) sliding[Tet4Vector::dof(a,c)]=tangent[c];
    SolidElement free;
    const auto slip=face.evaluate(sliding,sliding,dt,&free);
    close(slip.spring_energy+slip.dissipation,0,1e-30);
    for(double force:free.residual) close(force,0,1e-15);
}
}
int main() {
    using namespace eonsim;
    verify_normal_support();
    const auto g=tet4_geometry({Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}});
    std::array<double,12> x{},dn{},vn{},direction{};
    for(int i=0;i<12;++i) { x[i]=.03*std::sin(i+1); dn[i]=.02*std::cos(i+1); vn[i]=.04*std::sin(2*i); direction[i]=std::sin(3*i+.7); }
    for(const auto p:{SolidParameters{120,.28,1.3,0},SolidParameters{120,.28,1.3,.03},
                     SolidParameters{120,.28,1.3,.03,false,.017},SolidParameters{120,.28,1.3,.03,true,.017}}) {
        const auto e=solid_element(g,p,x,dn,vn);
        const auto residual_only=solid_element(g,p,x,dn,vn,false);
        if(residual_only.residual!=e.residual || residual_only.strain_energy!=e.strain_energy || residual_only.kinetic_energy!=e.kinetic_energy)
            throw std::runtime_error("Residual-only solid response changed");
        for(double value:residual_only.tangent) if(value!=0) throw std::runtime_error("Residual-only solid computed a tangent");
        auto plus=x,minus=x;
        const double eps=1e-6;
        for(int i=0;i<12;++i) { plus[i]+=eps*direction[i]; minus[i]-=eps*direction[i]; }
        const auto rp=solid_element(g,p,plus,dn,vn,false),rm=solid_element(g,p,minus,dn,vn,false);
        double error=0,norm=0;
        for(int i=0;i<12;++i) {
            double jv=0; for(int j=0;j<12;++j) jv+=e.tangent[i*12+j]*direction[j];
            const double fd=(rp.residual[i]-rm.residual[i])/(2*eps);
            error+=(fd-jv)*(fd-jv); norm+=jv*jv;
        }
        const double relative=std::sqrt(error/norm);
        std::cout << "dt=" << p.dt << " displacement_dt=" << p.displacement_dt << " jv_relative_error=" << relative << '\n';
        if(!std::isfinite(relative)||relative>2e-8) throw std::runtime_error("Solid Jacobian mismatch");
    }
    for(int a=0;a<4;++a) for(int c=0;c<3;++c) x[3*a+c]=.1*(c+1);
    const auto rigid=solid_element(g,{120,.28,1,0},x,{},{});
    if(std::abs(rigid.strain_energy)>1e-20) throw std::runtime_error("Rigid translation stores strain energy");
}
