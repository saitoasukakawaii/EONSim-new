#include "eonsim/fsi.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/fsi_domains.hpp"
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
template<bool Elastic>
FsiResult solve_fsi_impl(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fsi;
    const bool dual=!f.domains.solid_mesh.empty();
    const auto reduced=dual?make_dual_fsi_layout(comm,mesh,f.domains):Elastic?make_elastic_fsi_layout(comm,mesh):make_rigid_fsi_layout(comm,mesh);
    using Layout=CoupledLayout<Tet4Topology,Elastic>;
    constexpr int nc=Layout::components;
    const auto& layout=reduced.algebra;
    std::map<Tri3Topology::Nodal<LocalId>,int> boundary;
    for(const auto& face:mesh.boundary) {
        auto key=face.nodes; std::sort(key.begin(),key.end()); boundary[key]=face.physical_tag;
        const int tag=face.physical_tag;
        if(!dual&&(tag<1||tag>6)) throw std::runtime_error("FSI requires unit-cube fluid tags 1..6");
        if(!dual) for(auto n:face.nodes) if(std::abs(mesh.nodes[n].position[(tag-1)/2]-(tag-1)%2)>1e-12)
            throw std::runtime_error("FSI reference boundary mismatch");
    }
    std::vector<bool> interface(mesh.nodes.size());
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        const auto& tags=mesh.node_boundary_tags[n];
        interface[n]=dual?(node_in_region(mesh,n,f.domains.fluid_region)&&node_in_region(mesh,n,f.domains.solid_region)):(std::find(tags.begin(),tags.end(),2)!=tags.end());
    }
    std::vector<bool> fluid_cell,solid_cell;
    std::vector<FsiElementData> data;
    std::vector<Tet4Geometry> solid_geometry;
    for(const auto& cell:mesh.cells) {
        fluid_cell.push_back(!dual||cell.physical_tag==f.domains.fluid_region);
        solid_cell.push_back(Elastic&&(!dual||cell.physical_tag==f.domains.solid_region));
        FsiElementData e;
        Tet4Topology::Nodal<Point> solid_xyz;
        for(int a=0;a<Tet4Topology::nodes;++a) {
            e.reference[a]=mesh.nodes[cell.nodes[a]].position;
            solid_xyz[a]=e.reference[a]; if(!dual) solid_xyz[a][0]=1+f.thickness*(1-solid_xyz[a][0]);
        }
        // 两网格拥有同一逻辑拓扑；固体位于 [1,1+thickness]，界面逻辑 x=1 共形。
        // x 反射改变定向，交换两个顶点求几何后恢复原局部梯度顺序。
        if(solid_cell.back()) {
            if(!dual) std::swap(solid_xyz[1],solid_xyz[2]);
            auto g=tet4_geometry(solid_xyz); if(!dual) std::swap(g.gradients[1],g.gradients[2]); solid_geometry.push_back(g);
        } else solid_geometry.push_back({});
        for(int skip=0;skip<Tet4Topology::nodes;++skip) {
            Tri3Topology::Nodal<int> face; Tri3Topology::Nodal<LocalId> key; int i=0;
            for(int a=0;a<Tet4Topology::nodes;++a) if(a!=skip) { face[i]=a; key[i++]=cell.nodes[a]; }
            std::sort(key.begin(),key.end());
            if(fluid_cell.back()&&boundary.count(key)&&(dual?std::find(f.domains.pressure_tags.begin(),f.domains.pressure_tags.end(),boundary.at(key))!=f.domains.pressure_tags.end():boundary.at(key)==1)) e.inlet_faces.push_back(face);
        }
        e.inlet_pressure=f.pressure; data.push_back(e);
    }
    std::vector<double> accepted(layout.local_to_global.size(),0),physical(mesh.nodes.size()*nc,0);
    std::vector<double> solid_d(mesh.nodes.size()*Tet4Vector::components,0);
    RigidState body;
    FsiResult result; result.current_mesh=mesh;
    std::vector<double> signature_values{double(Elastic),double(f.neo_hookean),f.dt,f.mass,f.damping,
        f.stiffness,f.pressure,f.density,f.viscosity,f.young,f.poisson,f.solid_density,f.thickness};
    if(dual) {
        signature_values.insert(signature_values.end(),{double(f.domains.fluid_region),double(f.domains.solid_region)});
        for(int t:f.domains.pressure_tags) signature_values.push_back(t);
        for(const auto* list:{&f.domains.fluid_constraints,&f.domains.mesh_constraints,&f.domains.solid_constraints}) {
            signature_values.push_back(list->size());
            for(const auto& bc:*list) { signature_values.push_back(bc.tag); signature_values.push_back(bc.components.size()); for(int c:bc.components) signature_values.push_back(c); }
        }
    }
    const auto signature=state_signature(mesh,dual?"fsi_dual":"fsi",signature_values);
    TimeStepper clock(f.dt,f.steps,config.time_control);
    double current_dt=f.dt;
    if(!config.restart.empty()) {
        const auto saved=read_checkpoint(config.restart,mesh,signature,{{"reduced",accepted.size()},
            {"physical",physical.size()},{"solid_displacement",solid_d.size()},{"rigid",2}});
        accepted=saved.fields.at("reduced"); physical=saved.fields.at("physical"); solid_d=saved.fields.at("solid_displacement");
        body={saved.fields.at("rigid")[0],saved.fields.at("rigid")[1]}; clock.restore(saved.step,saved.time,saved.next_dt);
        if(!clock.active(config.stop_after)) throw std::runtime_error("Restart must precede requested final step");
    }
    const auto expand=[&](const std::vector<double>& x) {
        std::vector<double> full(mesh.nodes.size()*nc,0);
        for(std::size_t i=0;i<full.size();++i) {
            const auto n=i/nc,c=i%nc;
            if(reduced.local[i]>=0) full[i]=x[reduced.local[i]];
            if(interface[n] && Layout::is_mesh(c)) {
                if(Elastic) full[i]=solid_d[Tet4Vector::components*n+c-Layout::mesh_offset]+current_dt*full[i];
                else if(c==Layout::mesh_offset) full[i]=body.position+current_dt*full[i];
            }
        }
        return full;
    };
    while(clock.active(config.stop_after)) {
        const int step=clock.step+1; const double dt=clock.dt(),time=clock.time+dt; current_dt=dt;
        try {
        for(std::size_t e=0;e<data.size();++e) {
            if(!fluid_cell[e]) continue;
            double speed2=0;
            for(int a=0;a<Tet4Topology::nodes;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<Tet4Flow::components;++c) data[e].previous_fluid[Tet4Flow::components*a+c]=physical[nc*n+c];
                for(int c=0;c<Space3::dimension;++c) data[e].previous_mesh[a][c]=physical[Layout::dof(n,Layout::mesh_offset+c)];
                for(int c=0;c<Space3::dimension;++c) speed2+=physical[nc*n+c]*physical[nc*n+c]*Tet4Topology::mean_weight;
            }
            const double h=std::cbrt(Tet4Topology::jacobian_scale*tet4_geometry(data[e].reference).volume);
            const double tau=1/std::sqrt(4*f.density*f.density/(dt*dt)+4*f.density*f.density*speed2/(h*h)+16*f.viscosity*f.viscosity/(h*h*h*h));
            data[e].fluid={f.density,f.viscosity,dt,tau,true};
        }
        // 相同局部残量同时用于 SNES 装配和收敛后界面力检查。
        const auto local_residual=[&](std::size_t e,const std::vector<double>& full,bool tangent,
                                       std::vector<double>& r,std::vector<double>& j) {
            Tet4Ale::State<double> state;
            Tet4Vector::State<double> vs,dn,vn;
            constexpr int nd=Layout::dofs;
            r.assign(nd,0); if(tangent) j.assign(nd*nd,0);
            for(int a=0;a<Tet4Topology::nodes;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<Tet4Ale::components;++c) state[Tet4Ale::components*a+c]=full[nc*n+c];
                if(Elastic) for(int c=0;c<Space3::dimension;++c) {
                    vs[Tet4Vector::components*a+c]=full[Layout::dof(n,Layout::structure_offset+c)]; dn[Tet4Vector::components*a+c]=solid_d[Tet4Vector::components*n+c]; vn[Tet4Vector::components*a+c]=physical[Layout::dof(n,Layout::structure_offset+c)];
                }
            }
            if(fluid_cell[e]) {
            const auto fr=fsi_element_residual(data[e],state);
            for(int i=0;i<Tet4Ale::dofs;++i) r[Layout::dof(Tet4Ale::node(i),Tet4Ale::component(i))]=fr[i];
            if(tangent) {
                const auto fj=fsi_element_tangent(data[e],state);
                for(int i=0;i<Tet4Ale::dofs;++i) for(int k=0;k<Tet4Ale::dofs;++k) j[(Layout::dof(Tet4Ale::node(i),Tet4Ale::component(i)))*nd+Layout::dof(Tet4Ale::node(k),Tet4Ale::component(k))]=fj[Tet4Ale::matrix(i,k)];
            }
            }
            if(solid_cell[e]) {
                const auto sr=solid_element(solid_geometry[e],{f.young,f.poisson,f.solid_density,dt,f.neo_hookean},vs,dn,vn);
                for(int i=0;i<Tet4Vector::dofs;++i) r[Layout::dof(Tet4Vector::node(i),Layout::structure_offset+Tet4Vector::component(i))]=sr.residual[i];
                if(tangent) for(int i=0;i<Tet4Vector::dofs;++i) for(int k=0;k<Tet4Vector::dofs;++k)
                    j[(Layout::dof(Tet4Vector::node(i),Layout::structure_offset+Tet4Vector::component(i)))*nd+Layout::dof(Tet4Vector::node(k),Layout::structure_offset+Tet4Vector::component(k))]=sr.tangent[Tet4Vector::matrix(i,k)];
            }
        };
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            const auto full=expand(x);
            constexpr int nd=Layout::dofs;
            std::vector<double> residual,tangent,chain(nd);
            std::vector<PetscInt> rows(nd),cols(nd);
            for(std::size_t e=0;e<data.size();++e) {
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=0;c<nc;++c) {
                    const auto n=mesh.cells[e].nodes[a],i=nc*n+c;
                    rows[nc*a+c]=cols[nc*a+c]=reduced.global[i]; chain[nc*a+c]=1;
                    if(interface[n] && Layout::is_mesh(c)) {
                        chain[nc*a+c]=dt;
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
            if(!Elastic && mesh.rank==mesh.ranks-1) {
                const double v=x[reduced.body_local];
                const double rbody=rigid_residual({f.mass,f.damping,f.stiffness},body,dt,v,0);
                EONSIM_PETSC(VecSetValue(r,reduced.body,rbody,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,reduced.body,reduced.body,f.mass/dt+f.damping+dt*f.stiffness,ADD_VALUES));
            }
        };
        const auto solved=solve_nonlinear(comm,layout,config.solver,accepted,{}, {},assemble);
        const auto next=expand(solved.values);
        double local[2]{},global[2]{};
        for(std::size_t e=0;e<data.size();++e) {
            std::vector<double> r,j;
            local_residual(e,next,false,r,j);
            for(int a=0;a<Tet4Topology::nodes;++a) if(interface[mesh.cells[e].nodes[a]]) {
                local[0]-=r[nc*a];
                if(Elastic) local[1]+=r[nc*a]+r[Layout::dof(a,Layout::structure_offset)];
            }
        }
        MPI_Allreduce(local,global,2,MPI_DOUBLE,MPI_SUM,comm);
        result.fluid_force=global[0];
        if(Elastic) {
            double average[3]{},sum[3]{};
            for(std::size_t n=0;n<mesh.nodes.size();++n) for(int c=0;c<Space3::dimension;++c) solid_d[Tet4Vector::components*n+c]+=dt*next[Layout::dof(n,Layout::structure_offset+c)];
            for(std::size_t n=0;n<mesh.owned_nodes;++n) if(interface[n]) {
                average[0]+=solid_d[Tet4Vector::components*n]; average[1]+=next[Layout::dof(n,Layout::structure_offset)]; average[2]+=1;
            }
            MPI_Allreduce(average,sum,3,MPI_DOUBLE,MPI_SUM,comm);
            result.position=sum[0]/sum[2]; result.velocity=sum[1]/sum[2]; result.balance=global[1];
        } else {
            const double v=solved.values[reduced.body_local];
            result.balance=rigid_residual({f.mass,f.damping,f.stiffness},body,dt,v,result.fluid_force);
            body={body.position+dt*v,v}; result.position=body.position; result.velocity=body.velocity;
        }
        accepted=solved.values; physical=next;
        clock.accept();
        if(!config.checkpoint.empty()) write_checkpoint(comm,config.checkpoint,mesh,signature,{step,
            {{"reduced",accepted},{"physical",physical},{"solid_displacement",solid_d},{"rigid",{body.position,body.velocity}}},clock.time,clock.next_dt});
        if(mesh.rank==0) std::cout << std::setprecision(16) << "fsi_step=" << step << " time=" << time
            << " position=" << result.position << " velocity=" << result.velocity << " fluid_force=" << result.fluid_force
            << " body_balance=" << result.balance << " snes_iterations=" << solved.iterations
            << " residual=" << solved.residual_norm << '\n';
        } catch(const StepRejected& error) {
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
    }
    result.fields={{"velocity",Space3::dimension,{}},{"pressure",1,{}},{"mesh_displacement",Space3::dimension,{}}};
    if(Elastic) { result.solid_mesh=mesh; result.solid_fields={{"velocity",Space3::dimension,{}},{"displacement",Space3::dimension,solid_d}}; }
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        for(int c=0;c<Space3::dimension;++c) {
            result.fields[0].values.push_back(physical[nc*n+c]); result.fields[2].values.push_back(physical[Layout::dof(n,Layout::mesh_offset+c)]);
            result.current_mesh.nodes[n].position[c]+=physical[Layout::dof(n,Layout::mesh_offset+c)];
            if(Elastic) {
                result.solid_fields[0].values.push_back(physical[Layout::dof(n,Layout::structure_offset+c)]);
                result.solid_mesh.nodes[n].position[c]=(!dual&&c==0?1+f.thickness*(1-mesh.nodes[n].position[0]):mesh.nodes[n].position[c])+solid_d[Tet4Vector::components*n+c];
            }
        }
        result.fields[1].values.push_back(physical[Layout::dof(n,Layout::pressure)]);
    }
    if(Elastic&&!dual) for(auto& cell:result.solid_mesh.cells) std::swap(cell.nodes[1],cell.nodes[2]);
    if(dual) {
        auto filter=[&](MeshPartition& output,int region) {
            output.cells.erase(std::remove_if(output.cells.begin(),output.cells.end(),[&](const auto& c){return c.physical_tag!=region;}),output.cells.end());
            output.boundary.erase(std::remove_if(output.boundary.begin(),output.boundary.end(),[&](const auto& face){ for(auto n:face.nodes) if(!node_in_region(mesh,n,region)) return true; return false; }),output.boundary.end());
        };
        filter(result.current_mesh,f.domains.fluid_region); filter(result.solid_mesh,f.domains.solid_region);
    }
    return result;
}
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    return config.fsi.elastic?solve_fsi_impl<true>(comm,mesh,config):solve_fsi_impl<false>(comm,mesh,config);
}
}
