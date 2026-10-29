#include "eonsim/fluid.hpp"
#include "eonsim/fluid_boundary.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/quadrature.hpp"
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
    const bool tagged=!f.boundaries.empty();
    const auto layout=make_field_layout(mesh,Tet4Flow::components,{{"velocity",{0,1,2}},{"pressure",{Tet4Flow::pressure}}});
    const auto facets=build_boundary_facets(mesh);
    std::vector<TriangleGeometry> surfaces;
    for(std::size_t f=0;f<facets.size();++f) surfaces.push_back(boundary_geometry(mesh,f,facets[f]));
    std::vector<Tet4Geometry> geometry;
    for(const auto& cell:mesh.cells) {
        Tet4Topology::Nodal<Point> coordinates;
        for(int a=0;a<Tet4Topology::nodes;++a) coordinates[a]=mesh.nodes[cell.nodes[a]].position;
        geometry.push_back(tet4_geometry(coordinates));
    }
    if(!tagged) {
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
    }
    const auto boundary_plan=tagged?prepare_fluid_boundaries(comm,mesh,layout,f,surfaces):FluidBoundaryPlan{};
    std::vector<double> accepted(layout.local_to_global.size(),0);
    FluidResult result;
    const bool transient=f.mode==FluidConfig::Mode::transient;
    const int steps=transient ? f.steps : 1;
    std::vector<double> signature_parameters{double(f.mode),f.density,f.viscosity,f.pressure_drop,f.dt,f.ramp_time,double(f.traction_outlet)};
    if(tagged) {
        const auto boundary_parameters=fluid_boundary_signature(f);
        signature_parameters.insert(signature_parameters.end(),boundary_parameters.begin(),boundary_parameters.end());
    }
    const auto signature=state_signature(mesh,tagged?"fluid_tagged":"fluid",signature_parameters);
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
        if(tagged) {
            for(const auto& c:boundary_plan.constraints) {
                bc.push_back(c.id); prescribed.push_back(c.value*boundary_scale(c.ramp_time,step*f.dt,transient));
            }
        } else {
            int gauge=0,total_gauge=0;
            for(std::size_t n=0;n<mesh.owned_nodes;++n) {
                const auto& tags=mesh.node_boundary_tags[n];
                auto has=[&](int tag){return std::find(tags.begin(),tags.end(),tag)!=tags.end();};
                const auto& xyz=mesh.nodes[n].position;
                for(int c=0;c<Space3::dimension;++c) if(has(1)||(has(2)&&!f.traction_outlet)||has(3)||has(4)||(c==2&&(has(5)||has(6)))) {
                    bc.push_back(layout.local_to_global[Tet4Flow::components*n+c]);
                    prescribed.push_back(c==0 ? scale*f.pressure_drop/(2*f.viscosity)*xyz[1]*(1-xyz[1]) : 0);
                }
                if(!f.traction_outlet && std::abs(xyz[0])+std::abs(xyz[1])+std::abs(xyz[2])<1e-12) {
                    bc.push_back(layout.local_to_global[Tet4Flow::dof(n,Tet4Flow::pressure)]); prescribed.push_back(scale*f.pressure_drop); ++gauge;
                }
            }
            MPI_Allreduce(&gauge,&total_gauge,1,MPI_INT,MPI_SUM,comm);
            if(total_gauge!=(f.traction_outlet?0:1)) throw std::runtime_error("Channel needs exactly one pressure gauge at origin");
        }
        std::vector<FluidParameters> parameters;
        for(std::size_t e=0;e<mesh.cells.size();++e) {
            double speed2=0;
            for(int c=0;c<Space3::dimension;++c) { double u=0; for(auto n:mesh.cells[e].nodes) u+=accepted[Tet4Flow::components*n+c]*Tet4Topology::mean_weight; speed2+=u*u; }
            const double h=std::cbrt(Tet4Topology::jacobian_scale*geometry[e].volume);
            const double time=transient ? 2*f.density/f.dt : 0;
            const double adv=f.mode==FluidConfig::Mode::stokes ? 0 : 2*f.density*std::sqrt(speed2)/h;
            const double visc=4*f.viscosity/(h*h);
            parameters.push_back({f.density,f.viscosity,transient?f.dt:0,
                1/std::sqrt(time*time+adv*adv+visc*visc),f.mode!=FluidConfig::Mode::stokes});
        }
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Flow::State<double> state,old;
                Tet4Flow::State<PetscInt> ids;
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Tet4Flow::components;++c) {
                    const auto local=Tet4Flow::components*mesh.cells[e].nodes[a]+c;
                    state[Tet4Flow::components*a+c]=x[local]; old[Tet4Flow::components*a+c]=accepted[local]; ids[Tet4Flow::components*a+c]=layout.local_to_global[local];
                }
                const auto element=fluid_element(geometry[e],parameters[e],state,old,{});
                EONSIM_PETSC(VecSetValues(r,Tet4Flow::dofs,ids.data(),element.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,Tet4Flow::dofs,ids.data(),Tet4Flow::dofs,ids.data(),element.tangent.data(),ADD_VALUES));
            }
            // x=1 处解析通道牵引 sigma*n=(0, mu*du_x/dy, 0)，压力基准由此确定。
            // 一致三角形质量矩阵积分线性牵引，独立于 trial，无额外切线。
            if(!tagged&&f.traction_outlet) for(const auto& face:mesh.boundary) if(face.physical_tag==2) {
                const double area=surfaces[&face-mesh.boundary.data()].area;
                for(int i=0;i<Space3::dimension;++i) {
                    double load=0;
                    for(int k=0;k<Space3::dimension;++k) load+=area*Tri3Topology::mass_weight(i,k)*scale*f.pressure_drop/2
                        *(1-2*mesh.nodes[face.nodes[k]].position[1]);
                    const PetscInt id=layout.local_to_global[Tet4Flow::components*face.nodes[i]+1];
                    load=-load;
                    EONSIM_PETSC(VecSetValues(r,1,&id,&load,ADD_VALUES));
                }
            }
            for(const auto& load:boundary_plan.loads) {
                auto residual=load.residual;
                for(double& value:residual) value*=boundary_scale(load.ramp_time,step*f.dt,transient);
                EONSIM_PETSC(VecSetValues(r,TriangleVector::dofs,load.ids.data(),residual.data(),ADD_VALUES));
            }
        };
        result.nonlinear=solve_nonlinear(comm,layout,config.solver,accepted,bc,prescribed,assemble);
        accepted=result.nonlinear.values;
        if(!config.checkpoint.empty()) write_checkpoint(comm,config.checkpoint,mesh,signature,{step,{{"fluid",accepted}}});
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fluid_step=" << step << " time=" << (transient?step*f.dt:0)
            << " snes_iterations=" << result.nonlinear.iterations << " residual=" << result.nonlinear.residual_norm << '\n';
    }
    result.fields={{"velocity",Space3::dimension,{}},{"pressure",1,{}},{"momentum_residual",Space3::dimension,{}}};
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<Space3::dimension;++c) {
            result.fields[0].values.push_back(accepted[Tet4Flow::components*n+c]);
            result.fields[2].values.push_back(result.nonlinear.raw_residual[Tet4Flow::components*n+c]);
        }
        result.fields[1].values.push_back(accepted[Tet4Flow::dof(n,Tet4Flow::pressure)]);
    }
    double metrics[8]{},global[8]{};
    if(!tagged) for(const auto& face:mesh.boundary) if(face.physical_tag<=2) {
        const double area=surfaces[&face-mesh.boundary.data()].area;
        const int side=face.physical_tag-1;
        metrics[4+side]+=area;
        for(auto n:face.nodes) { metrics[side]+=area*accepted[Tet4Flow::components*n]*Tri3Topology::mean_weight; metrics[2+side]+=area*accepted[Tet4Flow::dof(n,Tet4Flow::pressure)]*Tri3Topology::mean_weight; }
    }
    for(std::size_t e=0;e<mesh.cells.size();++e) {
        double div=0;
        for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) div+=accepted[Tet4Flow::components*mesh.cells[e].nodes[a]+c]*geometry[e].gradients[a][c];
        metrics[7]+=geometry[e].volume*div*div;
        if(!tagged) for(const auto& point:FluidQuadrature::points) {
            double y=0,u[Space3::dimension]{};
            for(int a=0;a<Tet4Topology::nodes;++a) {
                const double N=point.shape[a];
                auto n=mesh.cells[e].nodes[a]; y+=N*mesh.nodes[n].position[1];
                for(int c=0;c<Space3::dimension;++c) u[c]+=N*accepted[Tet4Flow::components*n+c];
            }
            u[0]-=f.pressure_drop/(2*f.viscosity)*y*(1-y);
            for(double v:u) metrics[6]+=geometry[e].volume*v*v*point.weight;
        }
    }
    MPI_Allreduce(metrics,global,8,MPI_DOUBLE,MPI_SUM,comm);
    result.inlet_flow=global[0]; result.outlet_flow=global[1];
    if(!tagged) result.pressure_drop=global[2]/global[4]-global[3]/global[5];
    else result.boundaries=summarize_fluid_boundaries(comm,mesh,f,surfaces,accepted);
    result.velocity_error=std::sqrt(global[6]); result.divergence=std::sqrt(global[7]);
    return result;
}
}
