#include "eonsim/fsi.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/fsi_element.hpp"
#include "eonsim/reduced_layout.hpp"
#include "eonsim/motion.hpp"
#include "eonsim/solid_element.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
namespace eonsim {
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fsi;
    const auto reduced=f.elastic?make_elastic_fsi_layout(comm,mesh):make_rigid_fsi_layout(comm,mesh);
    const int nc=reduced.components;
    const auto& layout=reduced.algebra;
    std::map<std::array<LocalId,3>,int> boundary;
    for(const auto& face:mesh.boundary) {
        auto key=face.nodes; std::sort(key.begin(),key.end()); boundary[key]=face.physical_tag;
        const int tag=face.physical_tag;
        if(tag<1||tag>6) throw std::runtime_error("FSI requires unit-cube fluid tags 1..6");
        for(auto n:face.nodes) if(std::abs(mesh.nodes[n].position[(tag-1)/2]-(tag-1)%2)>1e-12)
            throw std::runtime_error("FSI reference boundary mismatch");
    }
    std::vector<bool> interface(mesh.nodes.size());
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        const auto& tags=mesh.node_boundary_tags[n];
        interface[n]=std::find(tags.begin(),tags.end(),2)!=tags.end();
    }
    std::vector<FsiElementData> data;
    std::vector<Tet4Geometry> solid_geometry;
    for(const auto& cell:mesh.cells) {
        FsiElementData e;
        std::array<Point,4> solid_xyz;
        for(int a=0;a<4;++a) {
            e.reference[a]=mesh.nodes[cell.nodes[a]].position;
            solid_xyz[a]=e.reference[a]; solid_xyz[a][0]=1+f.thickness*(1-solid_xyz[a][0]);
        }
        // 两网格拥有同一逻辑拓扑；固体位于 [1,1+thickness]，界面逻辑 x=1 共形。
        // x 反射改变定向，交换两个顶点求几何后恢复原局部梯度顺序。
        if(f.elastic) {
            std::swap(solid_xyz[1],solid_xyz[2]);
            auto g=tet4_geometry(solid_xyz); std::swap(g.gradients[1],g.gradients[2]); solid_geometry.push_back(g);
        }
        for(int skip=0;skip<4;++skip) {
            std::array<int,3> face; std::array<LocalId,3> key; int i=0;
            for(int a=0;a<4;++a) if(a!=skip) { face[i]=a; key[i++]=cell.nodes[a]; }
            std::sort(key.begin(),key.end());
            if(boundary.count(key)&&boundary.at(key)==1) e.inlet_faces.push_back(face);
        }
        e.inlet_pressure=f.pressure; data.push_back(e);
    }
    std::vector<double> accepted(layout.local_to_global.size(),0),physical(mesh.nodes.size()*nc,0);
    std::vector<double> solid_d(mesh.nodes.size()*3,0);
    RigidState body;
    FsiResult result; result.current_mesh=mesh;
    const auto signature=state_signature(mesh,"fsi",{double(f.elastic),double(f.neo_hookean),f.dt,f.mass,f.damping,
        f.stiffness,f.pressure,f.density,f.viscosity,f.young,f.poisson,f.solid_density,f.thickness});
    int first=1;
    const int last=config.stop_after?std::min(config.stop_after,f.steps):f.steps;
    if(!config.restart.empty()) {
        const auto saved=read_checkpoint(config.restart,mesh,signature,{{"reduced",accepted.size()},
            {"physical",physical.size()},{"solid_displacement",solid_d.size()},{"rigid",2}});
        accepted=saved.fields.at("reduced"); physical=saved.fields.at("physical"); solid_d=saved.fields.at("solid_displacement");
        body={saved.fields.at("rigid")[0],saved.fields.at("rigid")[1]}; first=saved.step+1;
        if(first>last) throw std::runtime_error("Restart must precede requested final step");
    }
    const auto expand=[&](const std::vector<double>& x) {
        std::vector<double> full(mesh.nodes.size()*nc,0);
        for(std::size_t i=0;i<full.size();++i) {
            const auto n=i/nc,c=i%nc;
            if(reduced.local[i]>=0) full[i]=x[reduced.local[i]];
            if(interface[n] && c>=4 && c<7) {
                if(f.elastic) full[i]=solid_d[3*n+c-4]+f.dt*full[i];
                else if(c==4) full[i]=body.position+f.dt*full[i];
            }
        }
        return full;
    };
    for(int step=first;step<=last;++step) {
        for(std::size_t e=0;e<data.size();++e) {
            double speed2=0;
            for(int a=0;a<4;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<4;++c) data[e].previous_fluid[4*a+c]=physical[nc*n+c];
                for(int c=0;c<3;++c) data[e].previous_mesh[a][c]=physical[nc*n+4+c];
                for(int c=0;c<3;++c) speed2+=physical[nc*n+c]*physical[nc*n+c]/4;
            }
            const double h=std::cbrt(6*tet4_geometry(data[e].reference).volume);
            const double tau=1/std::sqrt(4*f.density*f.density/(f.dt*f.dt)+4*f.density*f.density*speed2/(h*h)+16*f.viscosity*f.viscosity/(h*h*h*h));
            data[e].fluid={f.density,f.viscosity,f.dt,tau,true};
        }
        // 相同局部残量同时用于 SNES 装配和收敛后界面力检查。
        const auto local_residual=[&](std::size_t e,const std::vector<double>& full,bool tangent,
                                       std::vector<double>& r,std::vector<double>& j) {
            std::array<double,28> state;
            std::array<double,12> vs,dn,vn;
            const int nd=4*nc;
            r.assign(nd,0); if(tangent) j.assign(nd*nd,0);
            for(int a=0;a<4;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<7;++c) state[7*a+c]=full[nc*n+c];
                if(f.elastic) for(int c=0;c<3;++c) {
                    vs[3*a+c]=full[nc*n+7+c]; dn[3*a+c]=solid_d[3*n+c]; vn[3*a+c]=physical[nc*n+7+c];
                }
            }
            const auto fr=fsi_element_residual(data[e],state);
            for(int i=0;i<28;++i) r[nc*(i/7)+i%7]=fr[i];
            if(tangent) {
                const auto fj=fsi_element_tangent(data[e],state);
                for(int i=0;i<28;++i) for(int k=0;k<28;++k) j[(nc*(i/7)+i%7)*nd+nc*(k/7)+k%7]=fj[28*i+k];
            }
            if(f.elastic) {
                const auto sr=solid_element(solid_geometry[e],{f.young,f.poisson,f.solid_density,f.dt,f.neo_hookean},vs,dn,vn);
                for(int i=0;i<12;++i) r[nc*(i/3)+7+i%3]=sr.residual[i];
                if(tangent) for(int i=0;i<12;++i) for(int k=0;k<12;++k)
                    j[(nc*(i/3)+7+i%3)*nd+nc*(k/3)+7+k%3]=sr.tangent[12*i+k];
            }
        };
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            const auto full=expand(x);
            const int nd=4*nc;
            std::vector<double> residual,tangent,chain(nd);
            std::vector<PetscInt> rows(nd),cols(nd);
            for(std::size_t e=0;e<data.size();++e) {
                for(int a=0;a<4;++a) for(int c=0;c<nc;++c) {
                    const auto n=mesh.cells[e].nodes[a],i=nc*n+c;
                    rows[nc*a+c]=cols[nc*a+c]=reduced.global[i]; chain[nc*a+c]=1;
                    if(interface[n] && c>=4 && c<7) {
                        chain[nc*a+c]=f.dt;
                        rows[nc*a+c]=-1; // 人工网格界面力不属于刚体或结构动量。
                    }
                }
                local_residual(e,full,j!=nullptr,residual,tangent);
                EONSIM_PETSC(VecSetValues(r,nd,rows.data(),residual.data(),ADD_VALUES));
                if(j) {
                    for(int row=0;row<nd;++row) for(int col=0;col<nd;++col) tangent[nd*row+col]*=chain[col];
                    EONSIM_PETSC(MatSetValues(j,nd,rows.data(),nd,cols.data(),tangent.data(),ADD_VALUES));
                }
            }
            if(!f.elastic && mesh.rank==mesh.ranks-1) {
                const double v=x[reduced.body_local];
                const double rbody=rigid_residual({f.mass,f.damping,f.stiffness},body,f.dt,v,0);
                EONSIM_PETSC(VecSetValue(r,reduced.body,rbody,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,reduced.body,reduced.body,f.mass/f.dt+f.damping+f.dt*f.stiffness,ADD_VALUES));
            }
        };
        const auto solved=solve_nonlinear(comm,layout,config.solver,accepted,{}, {},assemble);
        const auto next=expand(solved.values);
        double local[2]{},global[2]{};
        for(std::size_t e=0;e<data.size();++e) {
            std::vector<double> r,j;
            local_residual(e,next,false,r,j);
            for(int a=0;a<4;++a) if(interface[mesh.cells[e].nodes[a]]) {
                local[0]-=r[nc*a];
                if(f.elastic) local[1]+=r[nc*a]+r[nc*a+7];
            }
        }
        MPI_Allreduce(local,global,2,MPI_DOUBLE,MPI_SUM,comm);
        result.fluid_force=global[0];
        if(f.elastic) {
            double average[3]{},sum[3]{};
            for(std::size_t n=0;n<mesh.nodes.size();++n) for(int c=0;c<3;++c) solid_d[3*n+c]+=f.dt*next[nc*n+7+c];
            for(std::size_t n=0;n<mesh.owned_nodes;++n) if(interface[n]) {
                average[0]+=solid_d[3*n]; average[1]+=next[nc*n+7]; average[2]+=1;
            }
            MPI_Allreduce(average,sum,3,MPI_DOUBLE,MPI_SUM,comm);
            result.position=sum[0]/sum[2]; result.velocity=sum[1]/sum[2]; result.balance=global[1];
        } else {
            const double v=solved.values[reduced.body_local];
            result.balance=rigid_residual({f.mass,f.damping,f.stiffness},body,f.dt,v,result.fluid_force);
            body={body.position+f.dt*v,v}; result.position=body.position; result.velocity=body.velocity;
        }
        accepted=solved.values; physical=next;
        if(!config.checkpoint.empty()) write_checkpoint(comm,config.checkpoint,mesh,signature,{step,
            {{"reduced",accepted},{"physical",physical},{"solid_displacement",solid_d},{"rigid",{body.position,body.velocity}}}});
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fsi_step=" << step << " time=" << step*f.dt
            << " position=" << result.position << " velocity=" << result.velocity << " fluid_force=" << result.fluid_force
            << " body_balance=" << result.balance << " snes_iterations=" << solved.iterations
            << " residual=" << solved.residual_norm << '\n';
    }
    result.fields={{"velocity",3,{}},{"pressure",1,{}},{"mesh_displacement",3,{}}};
    if(f.elastic) { result.solid_mesh=mesh; result.solid_fields={{"velocity",3,{}},{"displacement",3,solid_d}}; }
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<3;++c) {
            result.fields[0].values.push_back(physical[nc*n+c]); result.fields[2].values.push_back(physical[nc*n+4+c]);
            result.current_mesh.nodes[n].position[c]+=physical[nc*n+4+c];
            if(f.elastic) {
                result.solid_fields[0].values.push_back(physical[nc*n+7+c]);
                result.solid_mesh.nodes[n].position[c]=(c==0?1+f.thickness*(1-mesh.nodes[n].position[0]):mesh.nodes[n].position[c])+solid_d[3*n+c];
            }
        }
        result.fields[1].values.push_back(physical[nc*n+3]);
    }
    if(f.elastic) for(auto& cell:result.solid_mesh.cells) std::swap(cell.nodes[1],cell.nodes[2]);
    return result;
}
}
