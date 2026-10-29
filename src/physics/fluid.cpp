#include "eonsim/fluid.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/fluid_element.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <stdexcept>
namespace eonsim {
FluidResult solve_fluid(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fluid;
    const auto layout=make_field_layout(mesh,4,{{"velocity",{0,1,2}},{"pressure",{3}}});
    std::vector<Tet4Geometry> geometry;
    for(const auto& cell:mesh.cells) {
        std::array<Point,4> coordinates;
        for(int a=0;a<4;++a) coordinates[a]=mesh.nodes[cell.nodes[a]].position;
        geometry.push_back(tet4_geometry(coordinates));
    }
    // 本算例契约严格限制单位立方体；拒绝把任意网格静默解释为通道。
    for(const auto& node:mesh.nodes) for(double v:node.position)
        if(v < -1e-12 || v>1+1e-12) throw std::runtime_error("Channel requires unit cube geometry");
    int seen[6]{},all[6]{};
    for(const auto& face:mesh.boundary) {
        if(face.physical_tag<1 || face.physical_tag>6) throw std::runtime_error("Channel requires boundary tags 1..6");
        const int axis=(face.physical_tag-1)/2,side=(face.physical_tag-1)%2;
        for(auto n:face.nodes) if(std::abs(mesh.nodes[n].position[axis]-side)>1e-12)
            throw std::runtime_error("Channel tag does not match its coordinate plane");
        seen[face.physical_tag-1]=1;
    }
    MPI_Allreduce(seen,all,6,MPI_INT,MPI_MAX,comm);
    for(int v:all) if(!v) throw std::runtime_error("Channel boundary tag missing");
    std::vector<double> accepted(layout.local_to_global.size(),0);
    FluidResult result;
    const bool transient=f.mode==FluidConfig::Mode::transient;
    const int steps=transient ? f.steps : 1;
    const auto signature=state_signature(mesh,"fluid",{double(f.mode),f.density,f.viscosity,f.pressure_drop,f.dt,f.ramp_time,double(f.traction_outlet)});
    int first=1;
    const int last=config.stop_after?std::min(config.stop_after,steps):steps;
    if(!config.restart.empty()) {
        const auto saved=read_checkpoint(config.restart,mesh,signature,{{"fluid",accepted.size()}});
        accepted=saved.fields.at("fluid"); first=saved.step+1;
        if(first>last) throw std::runtime_error("Restart must precede requested final step");
    }
    for(int step=first;step<=last;++step) {
        const double scale=transient ? std::min(step*f.dt/f.ramp_time,1.0) : 1;
        std::vector<PetscInt> bc;
        std::vector<double> prescribed;
        int gauge=0,total_gauge=0;
        for(std::size_t n=0;n<mesh.owned_nodes;++n) {
            const auto& tags=mesh.node_boundary_tags[n];
            auto has=[&](int tag){return std::find(tags.begin(),tags.end(),tag)!=tags.end();};
            const auto& xyz=mesh.nodes[n].position;
            for(int c=0;c<3;++c) if(has(1)||(has(2)&&!f.traction_outlet)||has(3)||has(4)||(c==2&&(has(5)||has(6)))) {
                bc.push_back(layout.local_to_global[4*n+c]);
                prescribed.push_back(c==0 ? scale*f.pressure_drop/(2*f.viscosity)*xyz[1]*(1-xyz[1]) : 0);
            }
            if(!f.traction_outlet && std::abs(xyz[0])+std::abs(xyz[1])+std::abs(xyz[2])<1e-12) {
                bc.push_back(layout.local_to_global[4*n+3]); prescribed.push_back(scale*f.pressure_drop); ++gauge;
            }
        }
        MPI_Allreduce(&gauge,&total_gauge,1,MPI_INT,MPI_SUM,comm);
        if(total_gauge!=(f.traction_outlet?0:1)) throw std::runtime_error("Channel needs exactly one pressure gauge at origin");
        std::vector<FluidParameters> parameters;
        for(std::size_t e=0;e<mesh.cells.size();++e) {
            double speed2=0;
            for(int c=0;c<3;++c) { double u=0; for(auto n:mesh.cells[e].nodes) u+=accepted[4*n+c]/4; speed2+=u*u; }
            const double h=std::cbrt(6*geometry[e].volume);
            const double time=transient ? 2*f.density/f.dt : 0;
            const double adv=f.mode==FluidConfig::Mode::stokes ? 0 : 2*f.density*std::sqrt(speed2)/h;
            const double visc=4*f.viscosity/(h*h);
            parameters.push_back({f.density,f.viscosity,transient?f.dt:0,
                1/std::sqrt(time*time+adv*adv+visc*visc),f.mode!=FluidConfig::Mode::stokes});
        }
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                std::array<double,16> state,old;
                std::array<PetscInt,16> ids;
                for(int a=0;a<4;++a) for(int c=0;c<4;++c) {
                    const auto local=4*mesh.cells[e].nodes[a]+c;
                    state[4*a+c]=x[local]; old[4*a+c]=accepted[local]; ids[4*a+c]=layout.local_to_global[local];
                }
                const auto element=fluid_element(geometry[e],parameters[e],state,old,{});
                EONSIM_PETSC(VecSetValues(r,16,ids.data(),element.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,16,ids.data(),16,ids.data(),element.tangent.data(),ADD_VALUES));
            }
            // x=1 处解析通道牵引 sigma*n=(0, mu*du_x/dy, 0)，压力基准由此确定。
            // 一致三角形质量矩阵积分线性牵引，独立于 trial，无额外切线。
            if(f.traction_outlet) for(const auto& face:mesh.boundary) if(face.physical_tag==2) {
                const auto& a=mesh.nodes[face.nodes[0]].position;
                const auto& b=mesh.nodes[face.nodes[1]].position;
                const auto& c=mesh.nodes[face.nodes[2]].position;
                const double area=std::abs((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]))/2;
                for(int i=0;i<3;++i) {
                    double load=0;
                    for(int k=0;k<3;++k) load+=area*(i==k?2:1)/12*scale*f.pressure_drop/2
                        *(1-2*mesh.nodes[face.nodes[k]].position[1]);
                    const PetscInt id=layout.local_to_global[4*face.nodes[i]+1];
                    load=-load;
                    EONSIM_PETSC(VecSetValues(r,1,&id,&load,ADD_VALUES));
                }
            }
        };
        result.nonlinear=solve_nonlinear(comm,layout,config.solver,accepted,bc,prescribed,assemble);
        accepted=result.nonlinear.values;
        if(!config.checkpoint.empty()) write_checkpoint(comm,config.checkpoint,mesh,signature,{step,{{"fluid",accepted}}});
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fluid_step=" << step << " time=" << (transient?step*f.dt:0)
            << " snes_iterations=" << result.nonlinear.iterations << " residual=" << result.nonlinear.residual_norm << '\n';
    }
    result.fields={{"velocity",3,{}},{"pressure",1,{}},{"momentum_residual",3,{}}};
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<3;++c) {
            result.fields[0].values.push_back(accepted[4*n+c]);
            result.fields[2].values.push_back(result.nonlinear.raw_residual[4*n+c]);
        }
        result.fields[1].values.push_back(accepted[4*n+3]);
    }
    double metrics[8]{},global[8]{};
    for(const auto& face:mesh.boundary) if(face.physical_tag<=2) {
        const auto& a=mesh.nodes[face.nodes[0]].position;
        const auto& b=mesh.nodes[face.nodes[1]].position;
        const auto& c=mesh.nodes[face.nodes[2]].position;
        const double area=std::abs((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]))/2;
        const int side=face.physical_tag-1;
        metrics[4+side]+=area;
        for(auto n:face.nodes) { metrics[side]+=area*accepted[4*n]/3; metrics[2+side]+=area*accepted[4*n+3]/3; }
    }
    for(std::size_t e=0;e<mesh.cells.size();++e) {
        double div=0;
        for(int a=0;a<4;++a) for(int c=0;c<3;++c) div+=accepted[4*mesh.cells[e].nodes[a]+c]*geometry[e].gradients[a][c];
        metrics[7]+=geometry[e].volume*div*div;
        for(int q=0;q<4;++q) {
            double y=0,u[3]{};
            for(int a=0;a<4;++a) {
                const double N=a==q?.5854101966249685:.1381966011250105;
                auto n=mesh.cells[e].nodes[a]; y+=N*mesh.nodes[n].position[1];
                for(int c=0;c<3;++c) u[c]+=N*accepted[4*n+c];
            }
            u[0]-=f.pressure_drop/(2*f.viscosity)*y*(1-y);
            for(double v:u) metrics[6]+=geometry[e].volume*v*v/4;
        }
    }
    MPI_Allreduce(metrics,global,8,MPI_DOUBLE,MPI_SUM,comm);
    result.inlet_flow=global[0]; result.outlet_flow=global[1];
    result.pressure_drop=global[2]/global[4]-global[3]/global[5];
    result.velocity_error=std::sqrt(global[6]); result.divergence=std::sqrt(global[7]);
    return result;
}
}
