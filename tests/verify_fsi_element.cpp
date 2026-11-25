/** @file @brief 全 ALE 局部耦合切线，独立方向扰动覆盖几何/压力面积/网格速度。 */
#include "eonsim/fsi_element.hpp"
#include "eonsim/fsi.hpp"
#include "eonsim/reduced_layout.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/time_step.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
namespace {
using namespace eonsim;

void verify_planar_area_tangent() {
    // A translated, sheared cap with nonzero normal velocities. Differentiate the
    // signed current area on both outward orientations and all coordinate planes.
    constexpr int nc=Tet4Ale::components;
    double worst=0;
    for(int axis=0;axis<3;++axis) for(int sign:{-1,1}) {
        PlanarOutletFace face{{1,3,0},{1.2,.3},{-.2,static_cast<double>(sign)*.9}};
        std::vector<double> state(4*nc);
        for(int a=0;a<3;++a) for(int t=0;t<2;++t)
            state[nc*face.nodes[a]+Tet4Ale::mesh_offset+(axis+1+t)%3]=1.1+t*.2+.04*a*(a+1+t);
        const auto geometry=face.geometry(state,nc,axis);
        if(sign*geometry.weight<=0) throw std::runtime_error("Incorrect signed moving port area");
        for(int a=0;a<3;++a) for(int t=0;t<2;++t) {
            const auto i=nc*face.nodes[a]+Tet4Ale::mesh_offset+(axis+t+1)%3;
            auto plus=state,minus=state;
            const double eps=1e-6;
            plus[i]+=eps;minus[i]-=eps;
            const double fd=(face.geometry(plus,nc,axis).weight-face.geometry(minus,nc,axis).weight)/(2*eps);
            worst=std::max(worst,std::abs(fd-geometry.gradient[a][t]));
        }
    }
    std::cout<<"moving_RCR_signed_area_derivative_error="<<worst<<'\n';
    if(worst>2e-10) throw std::runtime_error("Moving port geometry tangent differs from finite differences");
}

void verify_regular_metric() {
    const Tet4Topology::Nodal<Point> xyz{{{0,0,0},{1,0,0},{0,1,0},{0,0,1}}};
    FsiElementData cell(xyz);
    cell.fluid={1.7,.14,.053,0.,true,0.};
    cell.regular_metric_dt=.073;
    Tet4Ale::State<double> x{};
    Tet4Topology::Nodal<Point> rel{};
    for(int a=0;a<4;++a) {
        for(int i=0;i<3;++i) {
            const double u=.12*(a+1)*(i+2)-.44*i;
            const double w=.21*a-.13*i;
            x[Tet4Ale::dof(a,i)]=u;
            x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+i)]=.001*(i+1);
            cell.previous_mesh[a][i]=.001*(i+1)-cell.fluid.dt*w;
            rel[a][i]=u-w;
        }
        x[Tet4Ale::dof(a,Tet4Flow::pressure)]=.17*a;
    }
    // On the unit right tetrahedron G = c (I + 11^T), with eigenvalues c,c,4c.
    // Four symmetric degree-two quadrature points independently integrate the relative transport term.
    const double c=std::cbrt(.25),lo=(5-std::sqrt(5.))/20,hi=1-3*lo;
    double adv=0;
    for(int q=0;q<4;++q) {
        Point v{};
        for(int a=0;a<4;++a) for(int i=0;i<3;++i) v[i]+=(a==q?hi:lo)*rel[a][i];
        const double sum=v[0]+v[1]+v[2];
        adv+=.25*c*(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]+sum*sum);
    }
    auto frozen=cell;
    frozen.regular_metric_dt=0.;
    const double nu=cell.fluid.viscosity/cell.fluid.density;
    const double inv=cell.fluid.density*std::sqrt(4/std::pow(cell.regular_metric_dt,2)+adv+36*nu*nu*18*c*c);
    frozen.fluid.tau=1/inv;
    frozen.fluid.grad_div_viscosity=inv/(6*c);
    const auto expected=fsi_element_residual(frozen,x),actual=fsi_element_residual(cell,x);
    for(int i=0;i<Tet4Ale::dofs;++i) if(std::abs(actual[i]-expected[i])>2e-13)
        throw std::runtime_error("Regular-Tet4 stabilization disagrees with independent quadrature");
    const auto jac=fsi_element_tangent(cell,x);
    std::array<int,4> order{0,1,2,3};
    int positive=0;
    do {
        unsigned inversions=0;
        for(int i=0;i<4;++i) for(int j=i+1;j<4;++j) inversions+=order[i]>order[j];
        if(inversions%2) continue;
        ++positive;
        auto permuted_xyz=xyz;
        for(int a=0;a<4;++a) permuted_xyz[a]=xyz[order[a]];
        FsiElementData other(permuted_xyz);
        other.fluid=cell.fluid;
        other.regular_metric_dt=cell.regular_metric_dt;
        Tet4Ale::State<double> trial{};
        auto mapped=[&](int i){return Tet4Ale::dof(order[i/Tet4Ale::components],i%Tet4Ale::components);};
        for(int i=0;i<Tet4Ale::dofs;++i) trial[i]=x[mapped(i)];
        for(int a=0;a<4;++a) other.previous_mesh[a]=cell.previous_mesh[order[a]];
        const auto rp=fsi_element_residual(other,trial);
        const auto jp=fsi_element_tangent(other,trial);
        for(int i=0;i<Tet4Ale::dofs;++i) {
            if(std::abs(rp[i]-actual[mapped(i)])>2e-13) throw std::runtime_error("Vertex order changed the metric residual");
            for(int j=0;j<Tet4Ale::dofs;++j)
                if(std::abs(jp[Tet4Ale::matrix(i,j)]-jac[Tet4Ale::matrix(mapped(i),mapped(j))])>2e-12)
                    throw std::runtime_error("Vertex order changed the metric tangent");
        }
    } while(std::next_permutation(order.begin(),order.end()));
    if(positive!=12) throw std::runtime_error("Incomplete Tet4 permutation check");
}

void verify_mesh_and_pressure_blocks() {
    FsiElementData data({Point{0,0,0},Point{1,0,0},Point{0,1,0},Point{0,0,1}});
    data.fluid={1.3,.6,.07,.02,true};
    data.regular_metric_dt=.011;
    data.mesh_dt=.043;
    data.inlet_pressure=1.7;
    Tet4Ale::State<double> state{};
    for(int i=0;i<Tet4Ale::dofs;++i) state[i]=.021*std::sin(i+.3);
    const auto unloaded=fsi_element(data,state);
    // Independent exact stiffness on the unit right tetrahedron; artificial
    // mesh rows must remain constant and have no cross-component/fluid columns.
    const double stiffness[4][4]={{3,-1,-1,-1},{-1,1,0,0},{-1,0,1,0},{-1,0,0,1}};
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
        const int row=Tet4Ale::dof(a,Tet4Ale::mesh_offset+c);
        double expected=0;
        for(int b=0;b<Tet4Topology::nodes;++b)
            expected+=stiffness[a][b]/6*state[Tet4Ale::dof(b,Tet4Ale::mesh_offset+c)];
        if(std::abs(unloaded.residual[row]-expected)>1e-15)
            throw std::runtime_error("Reference mesh residual differs from the exact affine oracle");
        for(int j=0;j<Tet4Ale::dofs;++j) {
            const double value=Tet4Ale::component(j)==Tet4Ale::mesh_offset+c?stiffness[a][Tet4Ale::node(j)]/6:0.;
            if(std::abs(unloaded.tangent[Tet4Ale::matrix(row,j)]-value)>1e-15)
                throw std::runtime_error("Analytical reference mesh block contains an incorrect entry");
        }
    }
    // Independently integrate area*normal in double precision, then perturb it.
    // All 24 face permutations exercise both outward orientation signs; the
    // opposite node and all fluid/mesh-test rows have the appropriate zero block.
    auto pressure_load=[&](const Tet4Ale::State<double>& x) {
        auto coordinates=data.reference;
        for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c)
            coordinates[a][c]+=x[Tet4Ale::dof(a,Tet4Ale::mesh_offset+c)];
        Tet4Ale::State<double> load{};
        for(const auto& face:data.inlet_faces) {
            int opposite=0; while(opposite==face[0]||opposite==face[1]||opposite==face[2]) ++opposite;
            Tri3Topology::Nodal<Point> points{};
            for(int a=0;a<Tri3Topology::nodes;++a) points[a]=coordinates[face[a]];
            const auto surface=triangle_geometry(points,coordinates[opposite]);
            for(int a:face) for(int c=0;c<Space3::dimension;++c)
                load[Tet4Ale::dof(a,c)]+=data.inlet_pressure*surface.area*surface.normal[c]/3;
        }
        return load;
    };
    double worst=0;
    int permutations=0;
    for(int opposite=0;opposite<Tet4Topology::nodes;++opposite) {
        Tri3Topology::Nodal<int> face{};
        for(int a=0,b=0;a<Tet4Topology::nodes;++a) if(a!=opposite) face[b++]=a;
        do {
            ++permutations;
            data.inlet_faces={face};
            const auto loaded=fsi_element(data,state);
            const auto expected=pressure_load(state);
            for(int i=0;i<Tet4Ale::dofs;++i) {
                const double difference=loaded.residual[i]-unloaded.residual[i]-expected[i];
                if(!std::isfinite(difference)||std::abs(difference)>2e-14)
                    throw std::runtime_error("Pressure face residual differs from independent surface integration");
            }
            for(int j=0;j<Tet4Ale::dofs;++j) {
                auto plus=state,minus=state;
                constexpr double eps=2e-7;
                plus[j]+=eps; minus[j]-=eps;
                const auto rp=pressure_load(plus),rm=pressure_load(minus);
                for(int i=0;i<Tet4Ale::dofs;++i) {
                    const double actual=loaded.tangent[Tet4Ale::matrix(i,j)]-unloaded.tangent[Tet4Ale::matrix(i,j)];
                    const double expected=(rp[i]-rm[i])/(2*eps);
                    if(!std::isfinite(actual+expected)) throw std::runtime_error("Nonfinite pressure-area derivative");
                    worst=std::max(worst,std::abs(actual-expected));
                }
            }
        } while(std::next_permutation(face.begin(),face.end()));
    }
    std::cout<<"pressure_face_permutations="<<permutations<<" pressure_area_derivative_error="<<worst<<'\n';
    if(permutations!=24||!std::isfinite(worst)||worst>2e-9)
        throw std::runtime_error("Analytical pressure-area block differs from independent finite differences");
    // Moving the affine blocks out of Dual must retain both geometry gates.
    data.inlet_faces.clear();
    state[Tet4Ale::dof(3,Tet4Ale::mesh_offset+2)]=-2;
    for(bool tangent:{false,true}) {
        bool rejected=false;
        try { if(tangent) (void)fsi_element(data,state); else (void)fsi_element_residual(data,state); }
        catch(const StepRejected&) { rejected=true; }
        if(!rejected) throw std::runtime_error("Inverted trial geometry was not rejected");
    }
    state.fill(0);
    data.inlet_faces={{0,0,1}};
    data.inlet_pressure=0;
    for(bool tangent:{false,true}) {
        bool rejected=false;
        try { if(tangent) (void)fsi_element(data,state); else (void)fsi_element_residual(data,state); }
        catch(const StepRejected&) { rejected=true; }
        if(!rejected) throw std::runtime_error("Degenerate pressure face bypassed validation at zero load");
    }
}
}

int main(int argc,char** argv) {
    using namespace eonsim;
    FsiConfig load; load.pressure=2; load.pressure_time=FsiPressureTime{1,4,1};
    for(const auto& sample: {std::pair<double,double>{0,0},{1,3},{2,2},{3,1},{5,3}})
        if(std::abs(fsi_pressure(load,sample.first)-sample.second)>1e-14)
            throw std::runtime_error("FSI pressure startup/period mismatch");
    load.pressure_time->ramp_time=2;
    if(std::abs(fsi_pressure(load,1)-1.5)>1e-14) throw std::runtime_error("FSI pressure ramp midpoint mismatch");
    FsiElementData data({Point{0,0,0},Point{1.1,.1,0},Point{.2,.9,.1},Point{.1,.2,1.2}});
    data.inlet_faces={{0,2,3}}; data.fluid={1.3,.6,.07,.02,true}; data.inlet_pressure=fsi_pressure(load,.7);
    Tet4Ale::State<double> x{},direction{};
    for(int i=0;i<Tet4Ale::dofs;++i) { x[i]=.015*std::sin(i+1); direction[i]=std::sin(3*i+.7); }
    for(int i=0;i<Tet4Flow::dofs;++i) data.previous_fluid[i]=.03*std::cos(i+.2);
    for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) data.previous_mesh[a][c]=.002*std::sin(a+c+.1);
    if(argc!=1) {
        const std::string option=argv[1];
        if(argc!=3 || (option!="--kernel-samples"&&option!="--metric-kernel-samples"))
            throw std::runtime_error("Expected --kernel-samples count or --metric-kernel-samples count");
        if(option=="--metric-kernel-samples") data.regular_metric_dt=.011;
        const std::string count=argv[2];
        std::size_t consumed=0;
        const int samples=std::stoi(count,&consumed);
        if(samples<1 || consumed!=count.size()) throw std::runtime_error("Expected a positive kernel sample count");
        for(bool pressure_face:{false,true}) {
            data.inlet_faces.clear();
            if(pressure_face) data.inlet_faces.push_back({0,2,3});
            double checksum=0;
            auto sample=x;
            const std::clock_t cpu=std::clock();
            const auto start=std::chrono::steady_clock::now();
            for(int iteration=0;iteration<samples;++iteration) {
                sample[0]=x[0]+1e-6*(iteration%97);
                const auto jac=fsi_element_tangent(data,sample);
                checksum+=jac[static_cast<std::size_t>(iteration)%jac.size()];
            }
            const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            const double cpu_seconds=static_cast<double>(std::clock()-cpu)/CLOCKS_PER_SEC;
            std::cout<<std::setprecision(17)<<"pressure_face="<<pressure_face<<" samples="<<samples
                     <<" cpu_seconds="<<cpu_seconds<<" wall_seconds="<<seconds<<" checksum="<<checksum<<'\n';
        }
        return 0;
    }
    verify_regular_metric();
    verify_planar_area_tangent();
    verify_mesh_and_pressure_blocks();
    for(bool convection:{false,true}) for(bool pressure_face:{false,true})
    for(double mesh_dt:{0.,.043}) for(auto [gd,metric_dt]:{std::pair{0.,0.},std::pair{.7,0.},std::pair{0.,.011}}) {
    data.fluid.convection=convection;
    data.inlet_faces.clear();
    if(pressure_face) data.inlet_faces.push_back({0,2,3});
    data.regular_metric_dt=metric_dt;
    data.fluid.grad_div_viscosity=gd;
    data.mesh_dt=mesh_dt;
    // The fused value must agree with the independent double evaluation on a
    // deformed cell, including metric coefficients and moving pressure faces.
    // Directional differences below check the derivative of that double path.
    const auto element=fsi_element(data,x);
    const auto expected=fsi_element_residual(data,x);
    for(int i=0;i<Tet4Ale::dofs;++i)
        if(!std::isfinite(element.residual[i]) || std::abs(element.residual[i]-expected[i])>2e-13*(1+std::abs(expected[i])))
            throw std::runtime_error("Fused FSI residual differs from the double evaluation");
    const auto& jac=element.tangent;
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
        std::cout << "convection=" << convection << " pressure_face=" << pressure_face
                  << " mesh_dt=" << mesh_dt << " metric_dt=" << metric_dt << " grad_div=" << gd
                  << " field=" << field << " jv_relative_error=" << relative << '\n';
        if(!std::isfinite(relative)||relative>2e-8) throw std::runtime_error("FSI coupled Jacobian mismatch");
    }
    }
}
