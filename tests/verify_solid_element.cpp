/** @file @brief Solid tangents/direct actions, time-map derivatives and wall supports. */
#include "eonsim/solid_element.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
using namespace eonsim;
using State=Tet4Vector::State<double>;
const Tet4Topology::Nodal<Point> coordinates={Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}};
State multiply(const SolidElement& element,const State& direction) {
    State result{};
    for(int i=0;i<Tet4Vector::dofs;++i) for(int j=0;j<Tet4Vector::dofs;++j)
        result[i]+=element.tangent[Tet4Vector::matrix(i,j)]*direction[j];
    return result;
}
double difference(const State& actual,const State& reference) {
    double error=0,norm=0;
    for(std::size_t i=0;i<actual.size();++i) {
        if(!std::isfinite(actual[i])||!std::isfinite(reference[i]))
            throw std::runtime_error("Nonfinite solid action oracle");
        error+=(actual[i]-reference[i])*(actual[i]-reference[i]);norm+=reference[i]*reference[i];
    }
    return std::sqrt(error/std::max(1.,norm));
}
struct ActionAudit { int cases=0; double tangent_error=0,fd_error=0; };
void check_action(const Tet4Geometry& geometry,const SolidParameters& parameters,const State& state,
    const State& direction,const State& dn,const State& vn,ActionAudit& audit) {
    const auto action=solid_element_action(geometry,parameters,state,direction,dn);
    const auto reference=multiply(solid_element(geometry,parameters,state,dn,vn,true),direction);
    const double direct_error=difference(action,reference);
    auto plus=state,minus=state;
    constexpr double eps=1e-6;
    for(std::size_t i=0;i<state.size();++i) { plus[i]+=eps*direction[i];minus[i]-=eps*direction[i]; }
    const auto rp=solid_element(geometry,parameters,plus,dn,vn,false);
    const auto rm=solid_element(geometry,parameters,minus,dn,vn,false);
    State fd{};
    for(std::size_t i=0;i<state.size();++i) fd[i]=(rp.residual[i]-rm.residual[i])/(2*eps);
    const double fd_error=difference(action,fd);
    if(direct_error>2e-12||fd_error>2e-8) throw std::runtime_error("Direct solid action disagrees with independent tangent/residual");
    const auto zero=solid_element_action(geometry,parameters,state,{},dn);
    for(double value:zero) if(value!=0.) throw std::runtime_error("Zero solid direction produced a nonzero action");
    ++audit.cases;audit.tangent_error=std::max(audit.tangent_error,direct_error);audit.fd_error=std::max(audit.fd_error,fd_error);
}
void verify_direct_actions() {
    const auto geometry=tet4_geometry(coordinates);
    State state{},dn{},vn{},direction{};
    for(int i=0;i<12;++i) {
        state[i]=.03*std::sin(i+1);dn[i]=.02*std::cos(i+1);vn[i]=.04*std::sin(2*i);
        direction[i]=std::sin(3*i+.7);
    }
    ActionAudit audit;
    // The static map ignores both time-reference displacement and displacement_dt.
    // The last two dynamic maps distinguish inertia from the displacement chain.
    for(bool nonlinear:{false,true}) for(const auto time:std::array<std::array<double,2>,4>{{{0.,.017},{.03,0.},{.03,.017},{.08,.12}}}) {
        SolidParameters p{120,.28,1.3,time[0],nonlinear,time[1]};
        check_action(geometry,p,state,direction,dn,vn,audit);
    }
    const double c=std::cos(.7),s=std::sin(.7);
    const std::array<Space3::Tensor<double>,3> gradients={
        Space3::Tensor<double>{1.,0.,0.,0.,1.,0.,0.,0.,1.},
        Space3::Tensor<double>{c,-s,0.,s,c,0.,0.,0.,1.},
        Space3::Tensor<double>{.70,.17,-.05,.08,1.15,.12,.02,-.06,.85}};
    for(const auto& F:gradients) for(const auto time:std::array<std::array<double,2>,2>{{{0.,.2},{.03,.017}}}) {
        const SolidParameters p{240,.32,2.1,time[0],true,time[1]};
        const double chain=p.dt>0?p.displacement_dt:1.;
        State affine{};
        for(int a=0;a<4;++a) for(int i=0;i<3;++i) {
            double displacement=.04*(i+1);
            for(int j=0;j<3;++j) displacement+=(F[3*i+j]-(i==j?1.:0.))*coordinates[a][j];
            affine[3*a+i]=(displacement-(p.dt>0?dn[3*a+i]:0.))/chain;
        }
        check_action(geometry,p,affine,direction,dn,vn,audit);
    }
    const SolidParameters nonlinear{120,.28,1.,0.,true};
    State inverted{};
    for(int a=0;a<4;++a) inverted[3*a]=-2.*coordinates[a][0];
    bool old_rejected=false,new_rejected=false;
    try { (void)solid_element(geometry,nonlinear,inverted,{},{}); }
    catch(const StepRejected&) { old_rejected=true; }
    try { (void)solid_element_action(geometry,nonlinear,inverted,{},{}); }
    catch(const StepRejected&) { new_rejected=true; }
    if(!old_rejected||!new_rejected) throw std::runtime_error("Inverted zero-direction solid action lost recoverable rejection");
    auto nonfinite=state;nonfinite[1]=std::numeric_limits<double>::infinity();
    old_rejected=new_rejected=false;
    try { (void)solid_element(geometry,nonlinear,nonfinite,{},{}); }
    catch(const StepRejected&) { throw std::runtime_error("Nonfinite deformation changed to recoverable failure"); }
    catch(const std::runtime_error&) { old_rejected=true; }
    try { (void)solid_element_action(geometry,nonlinear,nonfinite,{},{}); }
    catch(const StepRejected&) { throw std::runtime_error("Nonfinite action deformation changed to recoverable failure"); }
    catch(const std::runtime_error&) { new_rejected=true; }
    if(!old_rejected||!new_rejected) throw std::runtime_error("Nonfinite zero-direction solid action lost fatal rejection");
    std::cout<<"solid_direct_action cases="<<audit.cases<<" tangent_error="<<audit.tangent_error
             <<" residual_fd_error="<<audit.fd_error<<" invalid_zero_direction=passed\n";
}
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
    const auto direct=face.action(direction,dt);
    double virtual_power=0;
    for(int i=0;i<12;++i) {
        close(assembled.residual[i],expected.residual[i],3e-15);
        double jv=0;
        for(int j=0;j<12;++j) jv+=assembled.tangent[Tet4Vector::matrix(i,j)]*direction[j];
        close(jv,(rp.residual[i]-rm.residual[i])/(2*eps),3e-10);
        close(direct[i],jv,3e-14);
        virtual_power-=v[i]*assembled.residual[i];
    }
    close(virtual_power,actual.power_on_wall,3e-15);
    Tet4Vector::State<double> sliding{};
    for(int a:face.nodes) for(int c=0;c<3;++c) sliding[Tet4Vector::dof(a,c)]=tangent[c];
    SolidElement free;
    const auto slip=face.evaluate(sliding,sliding,dt,&free);
    close(slip.spring_energy+slip.dissipation,0,1e-30);
    for(double force:free.residual) close(force,0,1e-15);
    for(double force:face.action(sliding,dt)) close(force,0,1e-15);
}

void verify_support_actions() {
    State dn{},velocity{},direction{};
    for(int i=0;i<12;++i) {dn[i]=.03*std::cos(i+.2);velocity[i]=.07*std::sin(i+.4);direction[i]=std::cos(2*i+.6);}
    double max_error=0,max_fd=0;int cases=0;
    for(const auto coefficients:std::array<std::array<double,2>,4>{{{8.,0.},{0.,1.7},{8.,1.7},{0.,0.}}})
        for(double chain:{0.,.017,.13}) {
            const std::array<WallSupportFace,2> faces={
                WallSupportFace{{3,0,2},{2.4,{1./3,2./3,2./3}},coefficients[0],coefficients[1]},
                WallSupportFace{{2,1,3},{.9,{-.8,.6,0.}},coefficients[0],coefficients[1]}};
            SolidElement full,rp,rm;State action{},plus=velocity,minus=velocity;
            constexpr double eps=1e-6;
            for(int i=0;i<12;++i) {plus[i]+=eps*direction[i];minus[i]-=eps*direction[i];}
            for(const auto& face:faces) {
                face.evaluate(dn,velocity,chain,&full,true);
                face.evaluate(dn,plus,chain,&rp);face.evaluate(dn,minus,chain,&rm);
                const auto contribution=face.action(direction,chain);
                for(int i=0;i<12;++i) action[i]+=contribution[i];
            }
            State fd{};for(int i=0;i<12;++i) fd[i]=(rp.residual[i]-rm.residual[i])/(2*eps);
            const double error=difference(action,multiply(full,direction)),fd_error=difference(action,fd);
            if(error>2e-13||fd_error>2e-9) throw std::runtime_error("Direct multiple-face wall support action mismatch");
            max_error=std::max(max_error,error);max_fd=std::max(max_fd,fd_error);++cases;
        }
    std::cout<<"support_direct_action cases="<<cases<<" tangent_error="<<max_error<<" residual_fd_error="<<max_fd<<'\n';
}

// Opt-in kernel timing: CTest never turns a noisy wall-clock comparison into a
// numerical acceptance gate. The retained full tangent is the old FSI path.
void benchmark_actions() {
    const auto geometry=tet4_geometry(coordinates);
    constexpr std::size_t state_count=32;
    std::array<State,state_count> states{},directions{},history{},old_velocity{};
    for(std::size_t sample=0;sample<state_count;++sample) for(int i=0;i<12;++i) {
        states[sample][i]=.05*std::sin(i+sample*.17);
        directions[sample][i]=std::cos(.4*i+sample*.23);
        history[sample][i]=.03*std::cos(.7*i+sample*.11);
        old_velocity[sample][i]=.04*std::sin(.2*i+sample*.3);
    }
    const WallSupportFace face{{3,0,2},{2.4,{1./3,2./3,2./3}},8.,1.7};
    constexpr int samples=7,calls=20000;
    volatile double sink=0.;
    for(bool nonlinear:{false,true}) for(bool support:{false,true}) {
        const SolidParameters p{120,.28,1.3,.03,nonlinear,.017};
        const auto evaluate=[&](bool direct,std::size_t slot) {
            State result{};
            if(direct) {
                result=solid_element_action(geometry,p,states[slot],directions[slot],history[slot]);
                if(support) {
                    const auto correction=face.action(directions[slot],p.displacement_dt);
                    for(int i=0;i<12;++i) result[i]+=correction[i];
                }
            } else {
                auto element=solid_element(geometry,p,states[slot],history[slot],old_velocity[slot],true);
                if(support) face.evaluate(history[slot],states[slot],p.displacement_dt,&element,true);
                result=multiply(element,directions[slot]);
            }
            double checksum=0;for(int i=0;i<12;++i) checksum+=(i+1)*result[i];
            return checksum;
        };
        for(std::size_t slot=0;slot<state_count;++slot) {sink+=evaluate(false,slot);sink+=evaluate(true,slot);}
        std::vector<double> original,direct,ratios;
        for(int sample=0;sample<samples;++sample) {
            double times[2]{},checksums[2]{};
            // Alternating order avoids assigning all first-use bias to one path.
            for(int pass=0;pass<2;++pass) {
                const int path=(sample+pass)%2;
                const auto start=std::chrono::steady_clock::now();double checksum=0;
                for(int call=0;call<calls;++call) checksum+=evaluate(path!=0,static_cast<std::size_t>(call)%state_count);
                const auto stop=std::chrono::steady_clock::now();sink+=checksum;
                times[path]=std::chrono::duration<double,std::nano>(stop-start).count()/calls;
                checksums[path]=checksum;
            }
            if(!std::isfinite(checksums[0]+checksums[1])||
               std::abs(checksums[0]-checksums[1])>2e-11*std::max(1.,std::abs(checksums[0])))
                throw std::runtime_error("Solid action benchmark checksum mismatch");
            original.push_back(times[0]);direct.push_back(times[1]);ratios.push_back(times[1]/times[0]);
            std::cout<<"solid_action_benchmark_sample model="<<(nonlinear?"neo_hookean":"linear")
                <<" support="<<support<<" sample="<<sample<<" calls="<<calls<<" tangent_ns="<<times[0]
                <<" direct_ns="<<times[1]<<" ratio="<<ratios.back()<<" checksum="<<checksums[1]<<'\n';
        }
        const auto median=[](std::vector<double> data) {std::sort(data.begin(),data.end());return data[data.size()/2];};
        std::cout<<"solid_action_benchmark model="<<(nonlinear?"neo_hookean":"linear")<<" support="<<support
            <<" samples="<<samples<<" calls_per_sample="<<calls<<" tangent_median_ns="<<median(original)
            <<" direct_median_ns="<<median(direct)<<" paired_ratio_median="<<median(ratios)
            <<" paired_ratio_min="<<*std::min_element(ratios.begin(),ratios.end())
            <<" paired_ratio_max="<<*std::max_element(ratios.begin(),ratios.end())<<'\n';
    }
    if(!std::isfinite(sink)) throw std::runtime_error("Nonfinite benchmark checksum");
}
}
int main(int argc,char** argv) {
    using namespace eonsim;
    const bool benchmark=argc==2&&std::string(argv[1])=="--benchmark-actions";
    if(argc!=1&&!benchmark) throw std::runtime_error("Usage: verify_solid_element [--benchmark-actions]");
    std::cout<<std::setprecision(17);
    verify_normal_support();
    verify_support_actions();
    verify_direct_actions();
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
    if(benchmark) benchmark_actions();
}
