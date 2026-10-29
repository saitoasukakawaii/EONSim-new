#include "eonsim/solid.hpp"
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
    const auto layout=make_field_layout(mesh,3,{{"structure",{0,1,2}}});
    std::vector<Tet4Geometry> geometry;
    for(const auto& cell:mesh.cells) {
        std::array<Point,4> xyz;
        for(int a=0;a<4;++a) xyz[a]=mesh.nodes[cell.nodes[a]].position;
        geometry.push_back(tet4_geometry(xyz));
    }
    std::vector<PetscInt> bc;
    for(std::size_t n=0;n<mesh.owned_nodes;++n) for(int c=0;c<3;++c) {
        if(std::abs(mesh.nodes[n].position[c])<1e-12) bc.push_back(layout.local_to_global[3*n+c]);
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
    for(int step=0;step<=(s.transient?s.steps:0);++step) {
        const double dt=step?s.dt:0;
        const SolidParameters parameters{s.young,s.poisson,s.density,dt};
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                std::array<double,12> state,dn,vn;
                std::array<PetscInt,12> ids;
                for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                    const auto n=3*mesh.cells[e].nodes[a]+c;
                    state[3*a+c]=x[n]; dn[3*a+c]=displacement[n]; vn[3*a+c]=velocity[n]; ids[3*a+c]=layout.local_to_global[n];
                }
                const auto local=solid_element(geometry[e],parameters,state,dn,vn);
                EONSIM_PETSC(VecSetValues(r,12,ids.data(),local.residual.data(),ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValues(j,12,ids.data(),12,ids.data(),local.tangent.data(),ADD_VALUES));
            }
            if(step==0) for(const auto& face:mesh.boundary) if(face.physical_tag==2) {
                const auto& a=mesh.nodes[face.nodes[0]].position;
                const auto& b=mesh.nodes[face.nodes[1]].position;
                const auto& c=mesh.nodes[face.nodes[2]].position;
                const double load=-s.traction*std::abs((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]))/6;
                for(auto n:face.nodes) {
                    const PetscInt id=layout.local_to_global[3*n];
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
            std::array<double,12> d,v;
            for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                const auto n=3*mesh.cells[e].nodes[a]+c;
                d[3*a+c]=displacement[n]; v[3*a+c]=velocity[n];
            }
            local[0]+=solid_element(geometry[e],{s.young,s.poisson,s.density,0},d,{},{}).strain_energy;
            // kinetic energy depends only on velocity; dt is irrelevant to that term.
            local[1]+=solid_element(geometry[e],{s.young,s.poisson,s.density,1},v,{},{}).kinetic_energy;
        }
        MPI_Allreduce(local,energy,2,MPI_DOUBLE,MPI_SUM,comm);
        result.strain_energy=energy[0]; result.kinetic_energy=energy[1];
        const double total=energy[0]+energy[1];
        if(step && total>previous_energy+1e-9*std::max(1.,previous_energy))
            throw std::runtime_error("Unloaded BE solid gained energy");
        previous_energy=total;
        if(mesh.rank==0) std::cout << std::setprecision(16) << "solid_step=" << step << " time=" << step*s.dt
            << " strain_energy=" << energy[0] << " kinetic_energy=" << energy[1]
            << " total_energy=" << total << " residual=" << result.nonlinear.residual_norm << '\n';
    }
    double local[3]{},global[3]{};
    double tip=0,global_tip=0;
    for(std::size_t n=0;n<mesh.owned_nodes;++n) {
        for(int c=0;c<3;++c) {
            const double exact=s.traction/s.young*(c==0?1:-s.poisson)*mesh.nodes[n].position[c];
            local[0]=std::max(local[0],std::abs(displacement[3*n+c]-exact));
        }
        if(std::abs(mesh.nodes[n].position[0])<1e-12) local[1]+=result.nonlinear.raw_residual[3*n];
        if(std::abs(mesh.nodes[n].position[0]-1)<1e-12) { tip+=displacement[3*n]; local[2]+=1; }
    }
    MPI_Allreduce(local,global,1,MPI_DOUBLE,MPI_MAX,comm);
    MPI_Allreduce(local+1,global+1,2,MPI_DOUBLE,MPI_SUM,comm);
    MPI_Allreduce(&tip,&global_tip,1,MPI_DOUBLE,MPI_SUM,comm);
    result.displacement_error=global[0]; result.reaction_x=global[1]; result.tip_displacement=global_tip/global[2];
    result.fields={{"displacement",3,displacement},{"velocity",3,velocity},{"acceleration",3,acceleration},
                   {"momentum_residual",3,result.nonlinear.raw_residual}};
    return result;
}
}
