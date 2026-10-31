#include "eonsim/fluid.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/regions.hpp"
#include "eonsim/fluid_boundary.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/quadrature.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/fluid_element.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <stdexcept>
namespace eonsim {
FluidResult solve_fluid(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fluid;
    PetscBool element_report=PETSC_FALSE,coo=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fluid_element_report",&element_report,nullptr));
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fluid_coo",&coo,nullptr));
    const bool tagged=!f.boundaries.empty();
    const auto materials=cell_materials(comm,mesh,f.regions,FluidMaterial{f.density,f.viscosity});
    const auto layout=make_field_layout(mesh,Tet4Flow::components,{{"velocity",{0,1,2}},{"pressure",{Tet4Flow::pressure}}},
        {{DofDomain::fluid,DofQuantity::velocity,0},{DofDomain::fluid,DofQuantity::velocity,1},
         {DofDomain::fluid,DofQuantity::velocity,2},{DofDomain::fluid,DofQuantity::pressure,0}});
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
    const bool bdf2=config.time_integration.scheme==TimeScheme::bdf2;
    if(bdf2&&!transient) throw std::runtime_error("BDF2 requires transient fluid");
    TimeHistory history(bdf2?accepted.size():0);
    const int steps=transient ? f.steps : 1;
    std::vector<double> signature_parameters{double(f.mode),f.density,f.viscosity,f.pressure_drop,f.dt,f.ramp_time,double(f.traction_outlet)};
    if(tagged) {
        const auto boundary_parameters=fluid_boundary_signature(f);
        signature_parameters.insert(signature_parameters.end(),boundary_parameters.begin(),boundary_parameters.end());
    }
    for(const auto& r:f.regions) signature_parameters.insert(signature_parameters.end(),{double(r.first),r.second.density,r.second.viscosity});
    if(bdf2) signature_parameters.insert(signature_parameters.end(),{20501.,2.});
    if(f.stabilization_tau) signature_parameters.insert(signature_parameters.end(),{20503.,*f.stabilization_tau});
    if(!config.time_control.events.empty()) {
        signature_parameters.push_back(20502.);
        signature_parameters.insert(signature_parameters.end(),config.time_control.events.begin(),config.time_control.events.end());
    }
    if(!config.time_control.step_sizes.empty()) {
        signature_parameters.insert(signature_parameters.end(),{20504.,double(config.time_control.step_sizes.size())});
        signature_parameters.insert(signature_parameters.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    }
    const auto signature=state_signature(mesh,tagged?"fluid_tagged":"fluid",signature_parameters);
    TimeStepper clock(f.dt,steps,config.time_control);
    if(!config.restart.empty()) {
        std::map<std::string,std::size_t> sizes{{"fluid",accepted.size()}};
        if(bdf2) { sizes["time_previous"]=accepted.size(); sizes["time_metadata"]=1; }
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);
        accepted=saved.fields.at("fluid"); clock.restore(saved.step,saved.time,saved.next_dt);
        if(bdf2) {
            history.previous=saved.fields.at("time_previous"); history.previous_dt=saved.fields.at("time_metadata")[0];
            if(history.previous_dt<0||history.previous_dt>saved.time||
               (history.previous_dt==0&&!clock.at_event()))
                throw std::runtime_error("Invalid BDF2 checkpoint history step");
        }
        if(!clock.active(config.stop_after)) throw std::runtime_error("Restart must precede requested final step");
    }
    NonlinearSystem system(comm,layout);
    if(coo) {
        const auto begin=std::chrono::steady_clock::now();
        std::vector<PetscInt> rows,columns;
        // One immutable local-cell contribution order, reused across Newton steps and retries.
        // Duplicate and off-process row contributions are summed by PETSc's COO plan.
        for(const auto& cell:mesh.cells) {
            Tet4Flow::State<PetscInt> ids;
            for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Tet4Flow::components;++c)
                ids[Tet4Flow::dof(a,c)]=layout.local_to_global[Tet4Flow::dof(cell.nodes[a],c)];
            for(auto row:ids) for(auto column:ids) { rows.push_back(row); columns.push_back(column); }
        }
        system.set_jacobian_coo(rows,columns);
        const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
        EONSIM_PETSC(PetscSynchronizedPrintf(comm,
            "fluid_coo_plan rank=%d local_cells=%zu entries=%zu value_bytes=%zu setup_seconds=%.17g\n",
            mesh.rank,mesh.cells.size(),rows.size(),(rows.size()+static_cast<std::size_t>(layout.owned))*sizeof(PetscScalar),seconds));
        EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
    }
    while(clock.active(config.stop_after)) {
        if(bdf2&&history.previous_dt>0) clock.next_dt=std::min(clock.next_dt,2*history.previous_dt);
        const int step=clock.step+1; const double dt=clock.dt(),time=clock.time+dt;
        const auto derivative=time_derivative(config.time_integration.scheme,dt,history.previous_dt);
        const auto effective_previous=bdf2?history.reference(accepted,derivative):std::vector<double>{};
        const auto& previous=bdf2?effective_previous:accepted;
        const double integration_dt=derivative.effective_dt;
        try {
        const double scale=transient ? std::min(time/f.ramp_time,1.0) : 1;
        std::vector<PetscInt> bc;
        std::vector<double> prescribed;
        if(tagged) {
            for(const auto& c:boundary_plan.constraints) {
                bc.push_back(c.id); prescribed.push_back(c.value*boundary_scale(c.ramp_time,time,transient));
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
            const auto& material=materials[e];
            double speed2=0;
            for(int c=0;c<Space3::dimension;++c) { double u=0; for(auto n:mesh.cells[e].nodes) u+=accepted[Tet4Flow::components*n+c]*Tet4Topology::mean_weight; speed2+=u*u; }
            const double h=std::cbrt(Tet4Topology::jacobian_scale*geometry[e].volume);
            const double time=transient ? 2*material.density/integration_dt : 0;
            const double adv=f.mode==FluidConfig::Mode::stokes ? 0 : 2*material.density*std::sqrt(speed2)/h;
            const double visc=4*material.viscosity/(h*h);
            parameters.push_back({material.density,material.viscosity,transient?integration_dt:0,
                f.stabilization_tau.value_or(1/std::sqrt(time*time+adv*adv+visc*visc)),f.mode!=FluidConfig::Mode::stokes});
        }
        using Timer=std::chrono::steady_clock;
        double kernel_seconds=0,insert_seconds=0;
        PetscInt residual_elements=0,jacobian_elements=0;
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Flow::State<double> state,old;
                Tet4Flow::State<PetscInt> ids;
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Tet4Flow::components;++c) {
                    const auto local=Tet4Flow::components*mesh.cells[e].nodes[a]+c;
                    state[Tet4Flow::components*a+c]=x[local]; old[Tet4Flow::components*a+c]=previous[local]; ids[Tet4Flow::components*a+c]=layout.local_to_global[local];
                }
                const auto kernel_begin=element_report?Timer::now():Timer::time_point{};
                const auto element=fluid_element(geometry[e],parameters[e],state,old,{},j!=nullptr);
                const auto insert_begin=element_report?Timer::now():Timer::time_point{};
                EONSIM_PETSC(VecSetValues(r,Tet4Flow::dofs,ids.data(),element.residual.data(),ADD_VALUES));
                if(j) {
                    if(coo) std::copy(element.tangent.begin(),element.tangent.end(),
                        system.jacobian_coo_values()+e*Tet4Flow::dofs*Tet4Flow::dofs);
                    else EONSIM_PETSC(MatSetValues(j,Tet4Flow::dofs,ids.data(),Tet4Flow::dofs,ids.data(),element.tangent.data(),ADD_VALUES));
                }
                if(element_report) {
                    const auto insert_end=Timer::now();
                    kernel_seconds+=std::chrono::duration<double>(insert_begin-kernel_begin).count();
                    insert_seconds+=std::chrono::duration<double>(insert_end-insert_begin).count();
                    if(j) ++jacobian_elements; else ++residual_elements;
                }
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
                for(double& value:residual) value*=boundary_scale(load.ramp_time,time,transient);
                EONSIM_PETSC(VecSetValues(r,TriangleVector::dofs,load.ids.data(),residual.data(),ADD_VALUES));
            }
        };
        result.nonlinear=system.solve(config.solver,accepted,bc,prescribed,assemble);
        if(element_report) {
            // Rank-local totals for this completed solve, including final acceptance/reaction callbacks.
            EONSIM_PETSC(PetscSynchronizedPrintf(comm,
                "fluid_element_report rank=%d step=%d local_cells=%zu residual_elements=%" PetscInt_FMT
                " jacobian_elements=%" PetscInt_FMT " kernel_seconds=%.17g insert_seconds=%.17g\n",
                mesh.rank,step,mesh.cells.size(),residual_elements,jacobian_elements,kernel_seconds,insert_seconds));
            EONSIM_PETSC(PetscSynchronizedFlush(comm,PETSC_STDOUT));
        }
        if(bdf2) history.commit(accepted,dt);
        accepted=result.nonlinear.values;
        if(f.mean_pressure) {
            double local[2]{},global[2]{};
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                local[1]+=geometry[e].volume;
                for(auto n:mesh.cells[e].nodes) local[0]+=geometry[e].volume*Tet4Topology::mean_weight*accepted[Tet4Flow::dof(n,Tet4Flow::pressure)];
            }
            MPI_Allreduce(local,global,2,MPI_DOUBLE,MPI_SUM,comm);
            const double mean=global[0]/global[1];
            for(std::size_t n=0;n<mesh.nodes.size();++n) accepted[Tet4Flow::dof(n,Tet4Flow::pressure)]-=mean;
            // 压力平移也改变受约束动量行的反力：ΔR_ai = mean * ∫ grad(Na)_i。
            // 远程单元贡献先装配到 owner，再同步 ghost，使反力与输出压力基准一致。
            PetscOwner<Vec,VecDestroy> reaction;
            const auto ghosts=layout.local_to_global.size()-layout.owned;
            EONSIM_PETSC(VecCreateGhost(comm,layout.owned,layout.global,ghosts,layout.local_to_global.data()+layout.owned,reaction.put()));
            PetscScalar* values;
            EONSIM_PETSC(VecGetArray(reaction.get(),&values));
            std::copy_n(result.nonlinear.raw_residual.begin(),layout.owned,values);
            EONSIM_PETSC(VecRestoreArray(reaction.get(),&values));
            for(std::size_t e=0;e<mesh.cells.size();++e) for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
                const auto id=layout.local_to_global[Tet4Flow::dof(mesh.cells[e].nodes[a],c)];
                const double delta=mean*geometry[e].volume*geometry[e].gradients[a][c];
                EONSIM_PETSC(VecSetValue(reaction.get(),id,delta,ADD_VALUES));
            }
            EONSIM_PETSC(VecAssemblyBegin(reaction.get())); EONSIM_PETSC(VecAssemblyEnd(reaction.get()));
            EONSIM_PETSC(VecGhostUpdateBegin(reaction.get(),INSERT_VALUES,SCATTER_FORWARD)); EONSIM_PETSC(VecGhostUpdateEnd(reaction.get(),INSERT_VALUES,SCATTER_FORWARD));
            Vec local_reaction; const PetscScalar* raw;
            EONSIM_PETSC(VecGhostGetLocalForm(reaction.get(),&local_reaction)); EONSIM_PETSC(VecGetArrayRead(local_reaction,&raw));
            result.nonlinear.raw_residual.assign(raw,raw+layout.local_to_global.size());
            EONSIM_PETSC(VecRestoreArrayRead(local_reaction,&raw)); EONSIM_PETSC(VecGhostRestoreLocalForm(reaction.get(),&local_reaction));
            result.nonlinear.values=accepted;
        }
        clock.accept();
        if(bdf2&&clock.at_event()) history.previous_dt=0;
        if(!config.checkpoint.empty()) {
            Checkpoint saved{step,{{"fluid",accepted}},clock.time,clock.next_dt};
            if(bdf2) { saved.fields["time_previous"]=history.previous; saved.fields["time_metadata"]={history.previous_dt}; }
            write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
        }
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fluid_step=" << step << " time=" << (transient?time:0)
            << " snes_iterations=" << result.nonlinear.iterations << " residual=" << result.nonlinear.residual_norm
            << " time_order=" << derivative.order << '\n';
        } catch(const StepRejected& error) {
            if(!transient) throw;
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
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
