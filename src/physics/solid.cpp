#include "eonsim/solid.hpp"
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
    std::vector<PetscInt> bc;
    for(std::size_t n=0;n<mesh.owned_nodes;++n) for(int c=0;c<Space3::dimension;++c) {
        if(std::abs(mesh.nodes[n].position[c])<1e-12) bc.push_back(layout.local_to_global[Tet4Vector::components*n+c]);
    }
    std::vector<double> prescribed(bc.size(),0),displacement(layout.local_to_global.size(),0),velocity(displacement),acceleration(displacement);
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
    SolidResult result;
    double previous_energy=0;
    const auto signature=state_signature(mesh,"solid",{double(s.neo_hookean),s.young,s.poisson,s.density,s.traction,s.dt});
    int first=0;
    const int last=s.transient?(config.stop_after?std::min(config.stop_after,s.steps):s.steps):0;
    if(!config.restart.empty()) {
        const auto saved=read_checkpoint(config.restart,mesh,signature,{{"displacement",displacement.size()},
            {"velocity",velocity.size()},{"acceleration",acceleration.size()},{"energy",1}});
        displacement=saved.fields.at("displacement"); velocity=saved.fields.at("velocity");
        acceleration=saved.fields.at("acceleration"); previous_energy=saved.fields.at("energy")[0]; first=saved.step+1;
        if(first>last) throw std::runtime_error("Restart must precede requested final step");
    }
    for(int step=first;step<=last;++step) {
        const double dt=step?s.dt:0;
        const SolidParameters parameters{s.young,s.poisson,s.density,dt,s.neo_hookean};
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Vector::State<double> state,dn,vn;
                Tet4Vector::State<PetscInt> ids;
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
                    const auto n=Tet4Vector::components*mesh.cells[e].nodes[a]+c;
                    state[Tet4Vector::components*a+c]=x[n]; dn[Tet4Vector::components*a+c]=displacement[n]; vn[Tet4Vector::components*a+c]=velocity[n]; ids[Tet4Vector::components*a+c]=layout.local_to_global[n];
                }
                const auto local=solid_element(geometry[e],parameters,state,dn,vn);
                EONSIM_PETSC(VecSetValues(r,Tet4Vector::dofs,ids.data(),local.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,Tet4Vector::dofs,ids.data(),Tet4Vector::dofs,ids.data(),local.tangent.data(),ADD_VALUES));
            }
            if(step==0) for(const auto& face:mesh.boundary) if(face.physical_tag==2) {
                const double load=-s.traction*surfaces[&face-mesh.boundary.data()].area*Tri3Topology::mean_weight;
                for(auto n:face.nodes) {
                    const PetscInt id=layout.local_to_global[Tet4Vector::components*n];
                    EONSIM_PETSC(VecSetValues(r,1,&id,&load,ADD_VALUES));
                }
            }
        };
        result.nonlinear=solve_nonlinear(comm,layout,config.solver,step?velocity:displacement,bc,prescribed,assemble);
        // 所有未知量收敛后统一接受；回调从不修改这些历史。
        if(step) {
            for(std::size_t n=0;n<displacement.size();++n) {
                acceleration[n]=(result.nonlinear.values[n]-velocity[n])/dt;
                displacement[n]+=dt*result.nonlinear.values[n];
            }
            velocity=result.nonlinear.values;
        } else displacement=result.nonlinear.values;
        double local[2]{},energy[2]{};
        for(std::size_t e=0;e<mesh.cells.size();++e) {
            Tet4Vector::State<double> d,v;
            for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) {
                const auto n=Tet4Vector::components*mesh.cells[e].nodes[a]+c;
                d[Tet4Vector::components*a+c]=displacement[n]; v[Tet4Vector::components*a+c]=velocity[n];
            }
            local[0]+=solid_element(geometry[e],{s.young,s.poisson,s.density,0,s.neo_hookean},d,{},{}).strain_energy;
            // kinetic energy depends only on velocity; dt is irrelevant to that term.
            local[1]+=solid_element(geometry[e],{s.young,s.poisson,s.density,1},v,{},{}).kinetic_energy;
        }
        MPI_Allreduce(local,energy,2,MPI_DOUBLE,MPI_SUM,comm);
        result.strain_energy=energy[0]; result.kinetic_energy=energy[1];
        const double total=energy[0]+energy[1];
        if(step && total>previous_energy+1e-9*std::max(1.,previous_energy))
            throw std::runtime_error("Unloaded BE solid gained energy");
        previous_energy=total;
        if(!config.checkpoint.empty()) write_checkpoint(comm,config.checkpoint,mesh,signature,{step,
            {{"displacement",displacement},{"velocity",velocity},{"acceleration",acceleration},{"energy",{total}}}});
        if(mesh.rank==0) std::cout << std::setprecision(16) << "solid_step=" << step << " time=" << step*s.dt
            << " strain_energy=" << energy[0] << " kinetic_energy=" << energy[1]
            << " total_energy=" << total << " residual=" << result.nonlinear.residual_norm << '\n';
    }
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
    result.displacement_error=global[0]; result.reaction_x=global[1]; result.tip_displacement=global_tip/global[2];
    result.fields={{"displacement",Space3::dimension,displacement},{"velocity",Space3::dimension,velocity},{"acceleration",Space3::dimension,acceleration},
                   {"momentum_residual",Space3::dimension,result.nonlinear.raw_residual}};
    return result;
}
}
