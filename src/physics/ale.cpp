#include "eonsim/ale.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/motion.hpp"
#include "eonsim/fluid_element.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <limits>
#include <stdexcept>
namespace eonsim {
AleResult solve_ale(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& m=config.motion;
    if(m.mode==MotionConfig::Mode::rigid) throw std::runtime_error("Rigid ODE is not an ALE fluid case");
    const bool shear=m.mode==MotionConfig::Mode::shear;
    const bool bdf2=config.time_integration.scheme==TimeScheme::bdf2;
    const auto layout=make_field_layout(mesh,Tet4Flow::components,{{"velocity",{0,1,2}},{"pressure",{Tet4Flow::pressure}}});
    const auto ml=make_field_layout(mesh,Tet4Vector::components,{{"mesh",{0,1,2}}});
    std::vector<double> accepted(layout.local_to_global.size(),0),dn(mesh.nodes.size()*Tet4Vector::components,0),w(dn);
    for(std::size_t n=0;n<mesh.nodes.size();++n) accepted[Tet4Flow::components*n]=m.speed*(shear?mesh.nodes[n].position[1]:1);
    AleResult result; result.current_mesh=mesh;
    TimeStepper clock(m.dt,m.steps,config.time_control);
    TimeHistory fluid_history(bdf2?accepted.size():0),mesh_history(bdf2?dn.size():0);
    std::vector<double> signature_values{double(m.mode),m.speed,m.amplitude,m.dt,double(config.time_integration.scheme),double(config.time_control.events.size())};
    signature_values.insert(signature_values.end(),config.time_control.events.begin(),config.time_control.events.end());
    signature_values.push_back(config.time_control.step_sizes.size());
    signature_values.insert(signature_values.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    const auto signature=state_signature(mesh,"ale",signature_values);
    if(!config.restart.empty()) {
        std::map<std::string,std::size_t> sizes{{"fluid",accepted.size()},{"mesh",dn.size()}};
        if(bdf2) { sizes["previous_fluid"]=accepted.size(); sizes["previous_mesh"]=dn.size(); sizes["time_metadata"]=1; }
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);
        accepted=saved.fields.at("fluid"); dn=saved.fields.at("mesh");
        clock.restore(saved.step,saved.time,saved.next_dt);
        if(bdf2) {
            fluid_history.previous=saved.fields.at("previous_fluid"); mesh_history.previous=saved.fields.at("previous_mesh");
            const double previous_dt=saved.fields.at("time_metadata")[0];
            if(previous_dt<0||previous_dt>saved.time||(previous_dt==0&&!clock.at_event())) throw std::runtime_error("Invalid BDF2 ALE history step");
            fluid_history.previous_dt=mesh_history.previous_dt=previous_dt;
        }
        if(!clock.active(config.stop_after)) throw std::runtime_error("Restart must precede requested final step");
    }
    NonlinearSystem system(comm,layout);
    while(clock.active(config.stop_after)) {
        if(bdf2&&fluid_history.previous_dt>0) clock.next_dt=std::min(clock.next_dt,2*fluid_history.previous_dt);
        const int step=clock.step+1; const double dt=clock.dt(),time=clock.time+dt;
        const auto derivative=time_derivative(config.time_integration.scheme,dt,fluid_history.previous_dt);
        const double integration_dt=derivative.effective_dt;
        const auto effective_fluid=bdf2?fluid_history.reference(accepted,derivative):std::vector<double>{};
        const auto effective_mesh=bdf2?mesh_history.reference(dn,derivative):std::vector<double>{};
        const auto& reference_fluid=bdf2?effective_fluid:accepted;
        const auto& reference_mesh=bdf2?effective_mesh:dn;
        try {
        std::vector<PetscInt> mesh_bc,fluid_bc;
        std::vector<double> mesh_values,fluid_values;
        int anchor=0,all_anchor=0,gauge=0,all_gauge=0;
        for(std::size_t n=0;n<mesh.owned_nodes;++n) {
            const auto& xyz=mesh.nodes[n].position;
            const bool boundary=!mesh.node_boundary_tags[n].empty();
            const bool center=std::abs(xyz[0]-.5)+std::abs(xyz[1]-.5)+std::abs(xyz[2]-.5)<1e-12;
            if(center) ++anchor;
            if(boundary||(!shear&&center)) for(int c=0;c<Space3::dimension;++c) {
                mesh_bc.push_back(ml.local_to_global[Tet4Vector::components*n+c]);
                const double dx=shear?m.speed*time*xyz[1]:(center?m.amplitude*std::sin(time):0);
                mesh_values.push_back(c==0?dx:0);
            }
            if(boundary) for(int c=0;c<Space3::dimension;++c) {
                fluid_bc.push_back(layout.local_to_global[Tet4Flow::components*n+c]);
                fluid_values.push_back(c==0?m.speed*(shear?xyz[1]:1):0);
            }
            if(std::abs(xyz[0])+std::abs(xyz[1])+std::abs(xyz[2])<1e-12) {
                fluid_bc.push_back(layout.local_to_global[Tet4Flow::dof(n,Tet4Flow::pressure)]); fluid_values.push_back(0); ++gauge;
            }
        }
        MPI_Allreduce(&anchor,&all_anchor,1,MPI_INT,MPI_SUM,comm);
        MPI_Allreduce(&gauge,&all_gauge,1,MPI_INT,MPI_SUM,comm);
        if((!shear&&all_anchor!=1)||all_gauge!=1) throw std::runtime_error("ALE cube needs center anchor and origin pressure gauge");
        const auto d=extend_mesh(comm,mesh,mesh_bc,mesh_values,config.solver);
        std::vector<Tet4Geometry> geometry;
        for(std::size_t n=0;n<mesh.nodes.size();++n) for(int c=0;c<Space3::dimension;++c) {
            result.current_mesh.nodes[n].position[c]=mesh.nodes[n].position[c]+d[Tet4Vector::components*n+c];
            w[Tet4Vector::components*n+c]=(d[Tet4Vector::components*n+c]-reference_mesh[Tet4Vector::components*n+c])/integration_dt;
        }
        int invalid=0,any_invalid=0;
        try { for(const auto& cell:mesh.cells) {
            Tet4Topology::Nodal<Point> xyz;
            for(int a=0;a<Tet4Topology::nodes;++a) xyz[a]=result.current_mesh.nodes[cell.nodes[a]].position;
            geometry.push_back(tet4_geometry(xyz));
        }
        } catch(const StepRejected&) { invalid=1; }
        MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,comm);
        if(any_invalid) throw StepRejected("Invalid trial ALE geometry");
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Flow::State<double> state,old; Tet4Topology::Nodal<Point> mesh_velocity;
                Tet4Flow::State<PetscInt> ids;
                for(int a=0;a<Tet4Topology::nodes;++a) {
                    const auto n=mesh.cells[e].nodes[a];
                    for(int c=0;c<Tet4Flow::components;++c) { state[Tet4Flow::components*a+c]=x[Tet4Flow::components*n+c]; old[Tet4Flow::components*a+c]=reference_fluid[Tet4Flow::components*n+c]; ids[Tet4Flow::components*a+c]=layout.local_to_global[Tet4Flow::components*n+c]; }
                    for(int c=0;c<Space3::dimension;++c) mesh_velocity[a][c]=w[Tet4Vector::components*n+c];
                }
                const double h=std::cbrt(Tet4Topology::jacobian_scale*geometry[e].volume);
                const double tau=1/std::sqrt(4/(integration_dt*integration_dt)+16/(h*h*h*h)+4*m.speed*m.speed/(h*h));
                const auto element=fluid_element(geometry[e],{1,1,integration_dt,tau,true},state,old,mesh_velocity,j!=nullptr);
                EONSIM_PETSC(VecSetValues(r,Tet4Flow::dofs,ids.data(),element.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,Tet4Flow::dofs,ids.data(),Tet4Flow::dofs,ids.data(),element.tangent.data(),ADD_VALUES));
            }
        };
        auto solved=system.solve(config.solver,accepted,fluid_bc,fluid_values,assemble);
        if(bdf2) { fluid_history.commit(accepted,dt); mesh_history.commit(dn,dt); }
        accepted=std::move(solved.values); dn=d; clock.accept();
        if(bdf2&&clock.at_event()) fluid_history.previous_dt=mesh_history.previous_dt=0;
        if(!config.checkpoint.empty()) {
            Checkpoint saved{step,{{"fluid",accepted},{"mesh",dn}},clock.time,clock.next_dt};
            if(bdf2) { saved.fields["previous_fluid"]=fluid_history.previous; saved.fields["previous_mesh"]=mesh_history.previous; saved.fields["time_metadata"]={fluid_history.previous_dt}; }
            write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
        }
        double error=0,mesh_error=0,min_volume=std::numeric_limits<double>::max();
        for(std::size_t n=0;n<mesh.owned_nodes;++n) {
            for(int c=0;c<Space3::dimension;++c) error=std::max(error,std::abs(accepted[Tet4Flow::components*n+c]-(c==0?m.speed*(shear?mesh.nodes[n].position[1]:1):0)));
            if(shear) mesh_error=std::max(mesh_error,std::abs(dn[Tet4Vector::components*n]-m.speed*time*mesh.nodes[n].position[1]));
        }
        for(const auto& g:geometry) min_volume=std::min(min_volume,g.volume);
        MPI_Allreduce(&error,&result.velocity_error,1,MPI_DOUBLE,MPI_MAX,comm);
        MPI_Allreduce(&mesh_error,&result.mesh_error,1,MPI_DOUBLE,MPI_MAX,comm);
        MPI_Allreduce(&min_volume,&result.min_volume,1,MPI_DOUBLE,MPI_MIN,comm);
        if(mesh.rank==0) std::cout << std::setprecision(16) << "ale_step=" << step << " time=" << time
            << " velocity_max_error=" << result.velocity_error << " mesh_max_error=" << result.mesh_error
            << " min_volume=" << result.min_volume << " time_order=" << derivative.order << '\n';
        } catch(const StepRejected& error) {
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
    }
    result.fields={{"velocity",Space3::dimension,{}},{"pressure",1,{}},{"mesh_displacement",Space3::dimension,dn},{"mesh_velocity",Space3::dimension,w}};
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<Space3::dimension;++c) result.fields[0].values.push_back(accepted[Tet4Flow::components*n+c]);
        result.fields[1].values.push_back(accepted[Tet4Flow::dof(n,Tet4Flow::pressure)]);
    }
    return result;
}
}
