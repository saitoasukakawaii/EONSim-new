#include "eonsim/solid.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/regions.hpp"
#include "eonsim/fluid_boundary.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/solid_element.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
namespace eonsim {
SolidResult solve_solid(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& s=config.solid;
    const bool bdf2=config.time_integration.scheme==TimeScheme::bdf2;
    if(bdf2&&!s.transient) throw std::runtime_error("BDF2 requires transient solid");
    const bool tagged=!s.boundaries.empty();
    const auto materials=cell_materials(comm,mesh,s.regions,SolidMaterial{s.young,s.poisson,s.density,s.neo_hookean});
    const auto layout=make_field_layout(mesh,Tet4Vector::components,{{"structure",{0,1,2}}});
    const auto facets=build_boundary_facets(mesh);
    std::vector<TriangleGeometry> surfaces;
    for(std::size_t f=0;f<facets.size();++f) surfaces.push_back(boundary_geometry(mesh,f,facets[f]));
    std::vector<Tet4Geometry> geometry;
    for(const auto& cell:mesh.cells) {
        Tet4Topology::Nodal<Point> xyz;
        for(int a=0;a<Tet4Topology::nodes;++a) xyz[a]=mesh.nodes[cell.nodes[a]].position;
        geometry.push_back(tet4_geometry(xyz));
    }
    const auto boundary_plan=tagged?prepare_vector_boundaries(comm,mesh,layout,s.boundaries,surfaces,Tet4Vector::components,false):FluidBoundaryPlan{};
    std::vector<PetscInt> bc;
    if(!tagged) for(std::size_t n=0;n<mesh.owned_nodes;++n) for(int c=0;c<Space3::dimension;++c) {
        if(std::abs(mesh.nodes[n].position[c])<1e-12) bc.push_back(layout.local_to_global[Tet4Vector::components*n+c]);
    }
    std::vector<double> prescribed(bc.size(),0),displacement(layout.local_to_global.size(),0),velocity(displacement),acceleration(displacement);
    if(tagged) { for(const auto& c:boundary_plan.constraints) { bc.push_back(c.id); prescribed.push_back(c.value); } }
    if(!tagged) {
    // 仅接受单位立方体标签，外力沿参考面积积分；后续材料扩展仍使用该参考网格。
    int tags[6]{},global_tags[6]{};
    for(const auto& face:mesh.boundary) {
        const int t=face.physical_tag;
        if(t<1 || t>6) throw std::runtime_error("Solid block requires unit-cube tags 1..6");
        tags[t-1]=1;
        for(auto n:face.nodes) if(std::abs(mesh.nodes[n].position[(t-1)/2]-(t-1)%2)>1e-12)
            throw std::runtime_error("Solid boundary tag/geometry mismatch");
    }
    MPI_Allreduce(tags,global_tags,6,MPI_INT,MPI_MAX,comm);
    for(int v:global_tags) if(!v) throw std::runtime_error("Solid boundary missing");
    }
    SolidResult result;
    TimeHistory displacement_history(bdf2?displacement.size():0),velocity_history(bdf2?velocity.size():0);
    double previous_energy=0;
    std::vector<double> signature_parameters{double(s.neo_hookean),s.young,s.poisson,s.density,s.traction,s.dt};
    for(const auto& r:s.regions) signature_parameters.insert(signature_parameters.end(),{double(r.first),r.second.young,r.second.poisson,r.second.density,double(r.second.neo_hookean)});
    if(tagged) { FluidConfig f; f.boundaries=s.boundaries; const auto values=fluid_boundary_signature(f); signature_parameters.insert(signature_parameters.end(),values.begin(),values.end()); }
    if(bdf2) signature_parameters.insert(signature_parameters.end(),{20501.,2.});
    if(!config.time_control.events.empty()) {
        signature_parameters.push_back(20502.);
        signature_parameters.insert(signature_parameters.end(),config.time_control.events.begin(),config.time_control.events.end());
    }
    if(!config.time_control.step_sizes.empty()) {
        signature_parameters.insert(signature_parameters.end(),{20504.,double(config.time_control.step_sizes.size())});
        signature_parameters.insert(signature_parameters.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    }
    const auto signature=state_signature(mesh,tagged?"solid_tagged":"solid",signature_parameters);
    int first=0;
    TimeStepper clock(s.dt,s.steps,config.time_control);
    if(!config.restart.empty()) {
        std::map<std::string,std::size_t> sizes{{"displacement",displacement.size()},
            {"velocity",velocity.size()},{"acceleration",acceleration.size()},{"energy",1}};
        if(bdf2) { sizes["previous_displacement"]=displacement.size(); sizes["previous_velocity"]=velocity.size(); sizes["time_metadata"]=1; }
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);
        displacement=saved.fields.at("displacement"); velocity=saved.fields.at("velocity");
        acceleration=saved.fields.at("acceleration"); previous_energy=saved.fields.at("energy")[0]; first=saved.step+1;
        clock.restore(saved.step,saved.time,saved.next_dt);
        if(bdf2) {
            displacement_history.previous=saved.fields.at("previous_displacement");
            velocity_history.previous=saved.fields.at("previous_velocity");
            const double previous_dt=saved.fields.at("time_metadata")[0];
            if(previous_dt<0||previous_dt>saved.time||(previous_dt==0&&saved.step>0&&!clock.at_event()))
                throw std::runtime_error("Invalid BDF2 solid checkpoint history step");
            displacement_history.previous_dt=velocity_history.previous_dt=previous_dt;
        }
        if(!clock.active(config.stop_after)) throw std::runtime_error("Restart must precede requested final step");
    }
    int step=first;
    NonlinearSystem system(comm,layout);
    while(step==0 || (s.transient&&clock.active(config.stop_after))) {
        if(bdf2&&velocity_history.previous_dt>0) clock.next_dt=std::min(clock.next_dt,2*velocity_history.previous_dt);
        const double dt=step?clock.dt():0,time=clock.time+dt;
        const auto derivative=step?time_derivative(config.time_integration.scheme,dt,velocity_history.previous_dt):TimeDerivative{};
        const auto effective_d=bdf2&&step?displacement_history.reference(displacement,derivative):std::vector<double>{};
        const auto effective_v=bdf2&&step?velocity_history.reference(velocity,derivative):std::vector<double>{};
        const auto& reference_d=bdf2&&step?effective_d:displacement;
        const auto& reference_v=bdf2&&step?effective_v:velocity;
        try {
        const auto parameters=[&](std::size_t e) { const auto& m=materials[e]; return SolidParameters{m.young,m.poisson,m.density,derivative.effective_dt,m.neo_hookean}; };
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Vector::State<double> state,dn,vn;
                Tet4Vector::State<PetscInt> ids;
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
                    const auto n=Tet4Vector::components*mesh.cells[e].nodes[a]+c;
                    state[Tet4Vector::components*a+c]=x[n]; dn[Tet4Vector::components*a+c]=reference_d[n]; vn[Tet4Vector::components*a+c]=reference_v[n]; ids[Tet4Vector::components*a+c]=layout.local_to_global[n];
                }
                const auto local=solid_element(geometry[e],parameters(e),state,dn,vn,j!=nullptr);
                EONSIM_PETSC(VecSetValues(r,Tet4Vector::dofs,ids.data(),local.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,Tet4Vector::dofs,ids.data(),Tet4Vector::dofs,ids.data(),local.tangent.data(),ADD_VALUES));
            }
            if(step==0&&!tagged) for(const auto& face:mesh.boundary) if(face.physical_tag==2) {
                const double load=-s.traction*surfaces[&face-mesh.boundary.data()].area*Tri3Topology::mean_weight;
                for(auto n:face.nodes) {
                    const PetscInt id=layout.local_to_global[Tet4Vector::components*n];
                    EONSIM_PETSC(VecSetValues(r,1,&id,&load,ADD_VALUES));
                }
            }
            if(step==0) for(const auto& load:boundary_plan.loads)
                EONSIM_PETSC(VecSetValues(r,TriangleVector::dofs,load.ids.data(),load.residual.data(),ADD_VALUES));
        };
        const auto step_values=step?std::vector<double>(prescribed.size(),0):prescribed;
        result.nonlinear=system.solve(config.solver,step?velocity:displacement,bc,step_values,assemble);
        // 所有未知量收敛后统一接受；回调从不修改这些历史。
        auto next_d=displacement,next_v=velocity,next_a=acceleration;
        if(step) {
            for(std::size_t n=0;n<displacement.size();++n) {
                next_a[n]=(result.nonlinear.values[n]-reference_v[n])/derivative.effective_dt;
                next_d[n]=reference_d[n]+derivative.effective_dt*result.nonlinear.values[n];
            }
            next_v=result.nonlinear.values;
        } else next_d=result.nonlinear.values;
        double local[2]{},energy[2]{};
        for(std::size_t e=0;e<mesh.cells.size();++e) {
            Tet4Vector::State<double> d,v;
            for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
                const auto n=Tet4Vector::components*mesh.cells[e].nodes[a]+c;
                d[Tet4Vector::components*a+c]=next_d[n]; v[Tet4Vector::components*a+c]=next_v[n];
            }
            const auto& m=materials[e];
            local[0]+=solid_element(geometry[e],{m.young,m.poisson,m.density,0,m.neo_hookean},d,{},{},false).strain_energy;
            // kinetic energy depends only on velocity; dt is irrelevant to that term.
            local[1]+=solid_element(geometry[e],{m.young,m.poisson,m.density,1},v,{},{},false).kinetic_energy;
        }
        MPI_Allreduce(local,energy,2,MPI_DOUBLE,MPI_SUM,comm);
        result.strain_energy=energy[0]; result.kinetic_energy=energy[1];
        const double total=energy[0]+energy[1];
        if(!std::isfinite(total)||energy[0]<-1e-12||energy[1]<-1e-12) throw StepRejected("Invalid solid energy");
        // BE has monotone physical energy for the unloaded problem. BDF2's
        // stability is in a history-dependent norm, not this instantaneous sum.
        if(step && !bdf2 && total>previous_energy+1e-9*std::max(1.,previous_energy))
            throw StepRejected("Unloaded BE solid gained energy");
        if(bdf2&&step) { displacement_history.commit(displacement,dt); velocity_history.commit(velocity,dt); }
        displacement=std::move(next_d); velocity=std::move(next_v); acceleration=std::move(next_a);
        previous_energy=total;
        if(step) clock.accept();
        if(bdf2&&clock.at_event()) displacement_history.previous_dt=velocity_history.previous_dt=0;
        if(!config.checkpoint.empty()) {
            Checkpoint saved{step,{{"displacement",displacement},{"velocity",velocity},{"acceleration",acceleration},{"energy",{total}}},clock.time,clock.next_dt};
            if(bdf2) {
                saved.fields["previous_displacement"]=displacement_history.previous;
                saved.fields["previous_velocity"]=velocity_history.previous;
                saved.fields["time_metadata"]={velocity_history.previous_dt};
            }
            write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
        }
        if(mesh.rank==0) std::cout << std::setprecision(16) << "solid_step=" << step << " time=" << time
            << " strain_energy=" << energy[0] << " kinetic_energy=" << energy[1]
            << " total_energy=" << total << " residual=" << result.nonlinear.residual_norm << '\n';
        step=clock.step+1;
        } catch(const StepRejected& error) {
            if(step==0) throw;
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
    }
    if(tagged) {
        // 每标签依次存面积、位移积分、速度积分、反力；尾部为去重后的总支座反力。
        constexpr int width=1+3*Space3::dimension;
        const auto total_offset=width*s.boundaries.size();
        std::vector<double> local(total_offset+Space3::dimension,0),global(local.size());
        for(std::size_t i=0;i<s.boundaries.size();++i) {
            const auto& b=s.boundaries[i];
            auto* sum=local.data()+width*i;
            for(std::size_t f=0;f<mesh.boundary.size();++f) if(mesh.boundary[f].physical_tag==b.tag) {
                const double area=surfaces[f].area;
                sum[0]+=area;
                for(auto n:mesh.boundary[f].nodes) for(int c=0;c<Space3::dimension;++c) {
                    const auto dof=Tet4Vector::dof(n,c);
                    sum[1+c]+=area*Tri3Topology::mean_weight*displacement[dof];
                    sum[1+Space3::dimension+c]+=area*Tri3Topology::mean_weight*velocity[dof];
                }
            }
            // 面由单元 owner 积分；反力由节点 owner 求和，不能沿面遍历重复计边缘节点。
            if(b.type==FluidBoundary::Type::velocity) for(std::size_t n=0;n<mesh.owned_nodes;++n) {
                const auto& tags=mesh.node_boundary_tags[n];
                if(std::find(tags.begin(),tags.end(),b.tag)!=tags.end()) for(int c:b.components)
                    sum[1+2*Space3::dimension+c]+=result.nonlinear.raw_residual[Tet4Vector::dof(n,c)];
            }
        }
        for(const auto& c:boundary_plan.constraints) {
            const auto dof=c.id-layout.begin;
            local[total_offset+dof%Space3::dimension]+=result.nonlinear.raw_residual[dof];
        }
        MPI_Allreduce(local.data(),global.data(),static_cast<int>(global.size()),MPI_DOUBLE,MPI_SUM,comm);
        for(std::size_t i=0;i<s.boundaries.size();++i) {
            const auto& b=s.boundaries[i];
            const auto* sum=global.data()+width*i;
            SolidBoundarySummary summary;
            summary.tag=b.tag; summary.reference_area=sum[0];
            for(int c=0;c<Space3::dimension;++c) {
                summary.mean_displacement[c]=sum[1+c]/sum[0];
                summary.mean_velocity[c]=sum[1+Space3::dimension+c]/sum[0];
                summary.reaction[c]=sum[1+2*Space3::dimension+c];
            }
            if(b.type==FluidBoundary::Type::velocity) for(int c:b.components) summary.constrained[c]=true;
            result.boundaries.push_back(summary);
        }
        for(int c=0;c<Space3::dimension;++c) result.support_reaction[c]=global[total_offset+c];
    } else {
    double local[3]{},global[3]{};
    double tip=0,global_tip=0;
    for(std::size_t n=0;n<mesh.owned_nodes;++n) {
        for(int c=0;c<Space3::dimension;++c) {
            const double exact=s.traction/s.young*(c==0?1:-s.poisson)*mesh.nodes[n].position[c];
            local[0]=std::max(local[0],std::abs(displacement[Tet4Vector::components*n+c]-exact));
        }
        if(std::abs(mesh.nodes[n].position[0])<1e-12) local[1]+=result.nonlinear.raw_residual[Tet4Vector::components*n];
        if(std::abs(mesh.nodes[n].position[0]-1)<1e-12) { tip+=displacement[Tet4Vector::components*n]; local[2]+=1; }
    }
    MPI_Allreduce(local,global,1,MPI_DOUBLE,MPI_MAX,comm);
    MPI_Allreduce(local+1,global+1,2,MPI_DOUBLE,MPI_SUM,comm);
    MPI_Allreduce(&tip,&global_tip,1,MPI_DOUBLE,MPI_SUM,comm);
    result.displacement_error=global[0]; result.reaction_x=global[1]; result.tip_displacement=global[2]>0?global_tip/global[2]:0;
    }
    result.fields={{"displacement",Space3::dimension,displacement},{"velocity",Space3::dimension,velocity},{"acceleration",Space3::dimension,acceleration},
                   {"momentum_residual",Space3::dimension,result.nonlinear.raw_residual}};
    return result;
}
}
