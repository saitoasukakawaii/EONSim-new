#include "eonsim/fsi.hpp"
#include "eonsim/fsi_element.hpp"
#include "eonsim/reduced_layout.hpp"
#include "eonsim/motion.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
namespace eonsim {
FsiResult solve_rigid_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fsi;
    const auto reduced=make_rigid_fsi_layout(comm,mesh);
    const auto& layout=reduced.algebra;
    std::map<std::array<LocalId,3>,int> boundary;
    for(const auto& face:mesh.boundary) {
        auto key=face.nodes; std::sort(key.begin(),key.end()); boundary[key]=face.physical_tag;
        const int tag=face.physical_tag;
        if(tag<1||tag>6) throw std::runtime_error("Piston requires unit-cube tags 1..6");
        for(auto n:face.nodes) if(std::abs(mesh.nodes[n].position[(tag-1)/2]-(tag-1)%2)>1e-12)
            throw std::runtime_error("Piston reference boundary mismatch");
    }
    std::vector<FsiElementData> data;
    for(const auto& cell:mesh.cells) {
        FsiElementData e;
        for(int a=0;a<4;++a) e.reference[a]=mesh.nodes[cell.nodes[a]].position;
        for(int skip=0;skip<4;++skip) {
            std::array<int,3> face; std::array<LocalId,3> key; int i=0;
            for(int a=0;a<4;++a) if(a!=skip) { face[i]=a; key[i++]=cell.nodes[a]; }
            std::sort(key.begin(),key.end());
            if(boundary.count(key)&&boundary.at(key)==1) e.inlet_faces.push_back(face);
        }
        e.inlet_pressure=f.pressure; data.push_back(e);
    }
    std::vector<double> accepted(layout.local_to_global.size(),0),physical(mesh.nodes.size()*7,0);
    RigidState body;
    FsiResult result; result.current_mesh=mesh;
    const auto expand=[&](const std::vector<double>& x) {
        std::vector<double> full(mesh.nodes.size()*7,0);
        for(std::size_t i=0;i<full.size();++i) if(reduced.local[i]>=0) {
            full[i]=x[reduced.local[i]];
            if(reduced.global[i]==reduced.body && i%7==4) full[i]=body.position+f.dt*full[i];
        }
        return full;
    };
    for(int step=1;step<=f.steps;++step) {
        for(std::size_t e=0;e<data.size();++e) {
            double speed2=0;
            for(int a=0;a<4;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<4;++c) data[e].previous_fluid[4*a+c]=physical[7*n+c];
                for(int c=0;c<3;++c) data[e].previous_mesh[a][c]=physical[7*n+4+c];
                for(int c=0;c<3;++c) speed2+=physical[7*n+c]*physical[7*n+c]/4;
            }
            const double h=std::cbrt(6*tet4_geometry(data[e].reference).volume);
            const double tau=1/std::sqrt(4*f.density*f.density/(f.dt*f.dt)+4*f.density*f.density*speed2/(h*h)+16*f.viscosity*f.viscosity/(h*h*h*h));
            data[e].fluid={f.density,f.viscosity,f.dt,tau,true};
        }
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            const auto full=expand(x);
            for(std::size_t e=0;e<data.size();++e) {
                std::array<double,28> state;
                std::array<PetscInt,28> rows,cols;
                std::array<double,28> chain;
                for(int a=0;a<4;++a) for(int c=0;c<7;++c) {
                    const auto i=7*mesh.cells[e].nodes[a]+c;
                    state[7*a+c]=full[i]; rows[7*a+c]=cols[7*a+c]=reduced.global[i]; chain[7*a+c]=1;
                    if(reduced.global[i]==reduced.body && c==4) {
                        chain[7*a+c]=f.dt;
                        rows[7*a+c]=-1; // 人工网格界面力绝不能投影到刚体动量。
                    }
                }
                const auto residual=fsi_element_residual(data[e],state);
                EONSIM_PETSC(VecSetValues(r,28,rows.data(),residual.data(),ADD_VALUES));
                if(j) {
                    auto tangent=fsi_element_tangent(data[e],state);
                    for(int row=0;row<28;++row) for(int col=0;col<28;++col) tangent[28*row+col]*=chain[col];
                    EONSIM_PETSC(MatSetValues(j,28,rows.data(),28,cols.data(),tangent.data(),ADD_VALUES));
                }
            }
            if(mesh.rank==mesh.ranks-1) {
                const double v=x[reduced.body_local];
                const double rbody=rigid_residual({f.mass,f.damping,f.stiffness},body,f.dt,v,0);
                EONSIM_PETSC(VecSetValue(r,reduced.body,rbody,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,reduced.body,reduced.body,f.mass/f.dt+f.damping+f.dt*f.stiffness,ADD_VALUES));
            }
        };
        const auto solved=solve_nonlinear(comm,layout,config.solver,accepted,{}, {},assemble);
        const auto next=expand(solved.values);
        double local_force=0,force=0;
        for(std::size_t e=0;e<data.size();++e) {
            std::array<double,28> state;
            for(int a=0;a<4;++a) for(int c=0;c<7;++c) state[7*a+c]=next[7*mesh.cells[e].nodes[a]+c];
            const auto residual=fsi_element_residual(data[e],state);
            for(int a=0;a<4;++a) if(reduced.global[7*mesh.cells[e].nodes[a]]==reduced.body) local_force-=residual[7*a];
        }
        MPI_Allreduce(&local_force,&force,1,MPI_DOUBLE,MPI_SUM,comm);
        const double v=solved.values[reduced.body_local];
        result.balance=rigid_residual({f.mass,f.damping,f.stiffness},body,f.dt,v,force);
        body={body.position+f.dt*v,v}; accepted=solved.values; physical=next;
        result.position=body.position; result.velocity=body.velocity; result.fluid_force=force;
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fsi_step=" << step << " time=" << step*f.dt
            << " position=" << body.position << " velocity=" << body.velocity << " fluid_force=" << force
            << " body_balance=" << result.balance << " snes_iterations=" << solved.iterations
            << " residual=" << solved.residual_norm << '\n';
    }
    result.fields={{"velocity",3,{}},{"pressure",1,{}},{"mesh_displacement",3,{}}};
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<3;++c) {
            result.fields[0].values.push_back(physical[7*n+c]); result.fields[2].values.push_back(physical[7*n+4+c]);
            result.current_mesh.nodes[n].position[c]+=physical[7*n+4+c];
        }
        result.fields[1].values.push_back(physical[7*n+3]);
    }
    return result;
}
}
