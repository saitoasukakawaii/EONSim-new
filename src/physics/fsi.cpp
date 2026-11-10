#include "eonsim/fsi.hpp"
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/fsi_diagnostics.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/fsi_domains.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/fsi_element.hpp"
#include "eonsim/reduced_layout.hpp"
#include "eonsim/motion.hpp"
#include "eonsim/solid_element.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <fstream>
#include <limits>
#include <stdexcept>
namespace eonsim {
namespace {
// Each phase contains only local work; propagate its first failure before peers
// enter another collective or publish an index. I/O is fatal, never StepRejected.
template<class Work> void output_stage(MPI_Comm comm,const char* phase,const Work& work) {
    int rank; MPI_Comm_rank(comm,&rank); std::string error;
    try {work();} catch(const std::exception& e) {error=e.what();}
    int failed=error.empty()?std::numeric_limits<int>::max():rank,first;
    MPI_Allreduce(&failed,&first,1,MPI_INT,MPI_MIN,comm);
    if(first==std::numeric_limits<int>::max()) return;
    int length=static_cast<int>(error.size()); MPI_Bcast(&length,1,MPI_INT,first,comm);
    error.resize(length); MPI_Bcast(error.data(),length,MPI_CHAR,first,comm);
    throw std::runtime_error(std::string("FSI ")+phase+" failed on rank "+std::to_string(first)+": "+error);
}
std::string xml_filename(const std::string& text) {
    std::string out;
    for(char c:text) switch(c) {
        case '&':out+="&amp;";break;case '<':out+="&lt;";break;case '>':out+="&gt;";break;
        case '\"':out+="&quot;";break;case '\'':out+="&apos;";break;default:out+=c;
    }
    return out;
}
void publish_series(const std::filesystem::path& path,const std::vector<std::pair<double,std::string>>& entries) {
    std::ofstream out; out.exceptions(std::ios::badbit|std::ios::failbit); out.open(path.string()+".tmp");
    out<<std::setprecision(17)<<"<VTKFile type=\"Collection\" version=\"0.1\" byte_order=\"LittleEndian\"><Collection>\n";
    for(const auto& e:entries) out<<"<DataSet timestep=\""<<e.first<<"\" file=\""<<xml_filename(e.second)<<"\"/>\n";
    out<<"</Collection></VTKFile>\n"; out.close(); std::filesystem::rename(path.string()+".tmp",path);
}
}
double fsi_pressure(const FsiConfig& config,double time) {
    if(!config.pressure_time) return config.pressure;
    return pressure_value(config.pressure,*config.pressure_time,time);
}
void write_fsi_fields(MPI_Comm comm,const std::filesystem::path& path,const FsiResult& result) {
    const auto solid=path.parent_path()/(path.stem().string()+"_solid.vtu");
    output_stage(comm,"piece write",[&] {
        write_fields(path,result.current_mesh,result.fields);
        if(!result.solid_fields.empty()) write_fields(solid,result.solid_mesh,result.solid_fields);
    });
    output_stage(comm,"index publication",[&] {
        if(result.current_mesh.rank!=0) return;
        write_field_index(path,result.current_mesh.ranks,result.fields);
        if(!result.solid_fields.empty()) write_field_index(solid,result.current_mesh.ranks,result.solid_fields);
    });
}

template<bool Elastic>
FsiResult solve_fsi_impl(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    const auto& f=config.fsi;
    const bool bdf2=config.time_integration.scheme==TimeScheme::bdf2;
    const bool alpha=config.time_integration.scheme==TimeScheme::generalized_alpha;
    bool alpha_ready=false;
    PetscBool finite_difference=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fsi_fd_tangent",&finite_difference,nullptr));
    PetscInt lu_reuse_window=0;
    EONSIM_PETSC(PetscOptionsGetInt(nullptr,nullptr,"-fsi_lu_pc_reuse_window",&lu_reuse_window,nullptr));
    const bool dual=!f.domains.solid_mesh.empty();
    auto domains=f.domains;
    if(f.inlet) {
        domains.fluid_constraints.push_back({f.inlet->tag,{0,1,2}});
        domains.mesh_constraints.push_back({f.inlet->tag,{0,1,2}});
    }
    const auto reduced=dual?make_dual_fsi_layout(comm,mesh,domains):Elastic?make_elastic_fsi_layout(comm,mesh):make_rigid_fsi_layout(comm,mesh);
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
    const auto& interface=reduced.interface_nodes;
    std::vector<Point> inlet_values(mesh.nodes.size());
    std::vector<bool> inlet_nodes(mesh.nodes.size());
    output_stage(comm,"inlet validation",[&] {
        if(!f.inlet) return;
        for(std::size_t n=0;n<mesh.nodes.size();++n) {
            const auto& tags=mesh.node_boundary_tags[n];
            const auto has=[&](int t){return std::find(tags.begin(),tags.end(),t)!=tags.end();};
            if(!has(f.inlet->tag)) continue;
            if(!node_in_region(mesh,n,f.domains.fluid_region)) throw std::runtime_error("FSI inlet must belong to fluid");
            inlet_nodes[n]=true;
            for(int c=0;c<3;++c) {
                double value=f.inlet->value[c];
                for(int j=0;j<3;++j) value+=f.inlet->gradient[3*c+j]*(mesh.nodes[n].position[j]-f.inlet->origin[j]);
                if(f.inlet_flow) {
                    const auto& q=*f.inlet_flow;
                    if(q.circular) {
                        double r2=0;
                        for(int j=0;j<3;++j) {
                            const double dx=mesh.nodes[n].position[j]-q.center[j];
                            if(j==q.axis) {
                                if(std::abs(dx)>1e-12) throw std::runtime_error("FSI flow inlet outside circle plane");
                            } else r2+=(dx/q.radius)*(dx/q.radius);
                        }
                        if(!std::isfinite(r2)||r2>1+1e-12) throw std::runtime_error("FSI flow inlet outside circle");
                        value*=std::max(0.,1-r2);
                    } else for(int j=0;j<3;++j) {
                        const double x=mesh.nodes[n].position[j];
                        if(x<q.lower[j]-1e-12||x>q.upper[j]+1e-12) throw std::runtime_error("FSI flow inlet outside rectangle");
                        if(j!=q.axis) {const double r=std::clamp((x-q.lower[j])/(q.upper[j]-q.lower[j]),0.,1.); value*=r*(1-r);}
                    }
                }
                if(!std::isfinite(value)) throw std::runtime_error("Nonfinite FSI inlet value");
                bool zero=interface[n];
                for(const auto& bc:f.domains.fluid_constraints)
                    if(has(bc.tag)&&std::find(bc.components.begin(),bc.components.end(),c)!=bc.components.end()) zero=true;
                if(zero&&std::abs(value)>1e-12) throw std::runtime_error("FSI inlet conflicts with homogeneous/interface constraint");
                inlet_values[n][c]=zero?0:value;
            }
        }
    });
    if(f.inlet_flow) {
        double local=0,total=0;
        output_stage(comm,"flow normalization",[&] {
            for(const auto& cell:mesh.cells) if(cell.physical_tag==f.domains.fluid_region)
                for(int skip=0;skip<4;++skip) {
                    Tri3Topology::Nodal<LocalId> nodes,key; int k=0;
                    for(int a=0;a<4;++a) if(a!=skip) nodes[k++]=cell.nodes[a];
                    key=nodes; std::sort(key.begin(),key.end());
                    if(!boundary.count(key)||boundary.at(key)!=f.inlet->tag) continue;
                    Tri3Topology::Nodal<Point> xyz;
                    for(int a=0;a<3;++a) xyz[a]=mesh.nodes[nodes[a]].position;
                    const auto g=triangle_geometry(xyz,mesh.nodes[cell.nodes[skip]].position);
                    if(std::abs(g.normal[f.inlet_flow->axis]+1)>1e-10) throw std::runtime_error("FSI flow inlet requires negative axis outward normal");
                    for(auto n:nodes) for(int c=0;c<3;++c) local-=g.area*g.normal[c]*inlet_values[n][c]/3;
                }
        });
        MPI_Allreduce(&local,&total,1,MPI_DOUBLE,MPI_SUM,comm);
        if(!(total>0)||!std::isfinite(total)) throw std::runtime_error("FSI flow inlet has zero discrete profile flux; refine inlet mesh");
        for(auto& value:inlet_values) for(auto& c:value) c/=total;
    }
    const auto inlet_scale=[&](double t) {
        const double x=f.inlet&&f.inlet->ramp_time>0?std::clamp(t/f.inlet->ramp_time,0.,1.):1.;
        double scale=x*x*x*(10+x*(-15+6*x));
        if(f.inlet_flow) {
            const auto& q=*f.inlet_flow;
            scale*=q.mean+q.amplitude*std::sin(2*std::acos(-1.)*(std::fmod(t,q.period)/q.period));
        }
        if(!std::isfinite(scale)) throw std::runtime_error("Nonfinite FSI inlet waveform");
        return scale;
    };
    const auto interface_faces=fsi_interface_faces(comm,mesh,interface,dual?f.domains.fluid_region:0);
    std::set<Tri3Topology::Nodal<LocalId>> interface_keys;
    for(auto face:interface_faces) {std::sort(face.begin(),face.end());interface_keys.insert(face);}
    std::vector<bool> fluid_cell,solid_cell;
    std::vector<FsiElementData> data;
    std::vector<Tet4Geometry> solid_geometry;
    for(const auto& cell:mesh.cells) {
        fluid_cell.push_back(!dual||cell.physical_tag==f.domains.fluid_region);
        solid_cell.push_back(Elastic&&(!dual||cell.physical_tag==f.domains.solid_region));
        Tet4Topology::Nodal<Point> reference,solid_xyz;
        for(int a=0;a<Tet4Topology::nodes;++a) {
            reference[a]=mesh.nodes[cell.nodes[a]].position;
            solid_xyz[a]=reference[a]; if(!dual) solid_xyz[a][0]=1+f.thickness*(1-solid_xyz[a][0]);
        }
        FsiElementData e(reference);
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
    // A zero-ramp inlet is present in the initial physical state as well.
    for(std::size_t n=0;n<mesh.nodes.size();++n) if(inlet_nodes[n])
        for(int c=0;c<3;++c) physical[nc*n+c]=inlet_scale(0)*inlet_values[n][c];
    RigidState body;
    std::vector<double> fluid_rate(alpha?solid_d.size():0,0),mesh_velocity(fluid_rate),mesh_acceleration(fluid_rate);
    std::vector<double> solid_acceleration(alpha&&Elastic?solid_d.size():0,0);
    double body_acceleration=0;
    TimeHistory physical_history(bdf2?physical.size():0),displacement_history(bdf2?solid_d.size():0),body_history(bdf2?2:0);
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
    if(bdf2) signature_values.insert(signature_values.end(),{20501.,2.});
    if(alpha) signature_values.insert(signature_values.end(),{20501.,3.,config.time_integration.rho_infinity});
    if(f.stabilization_tau) signature_values.insert(signature_values.end(),{20503.,*f.stabilization_tau});
    if(f.stabilization_time_scale) signature_values.insert(signature_values.end(),{20505.,*f.stabilization_time_scale});
    if(!config.time_control.events.empty()) {
        signature_values.push_back(20502.);
        signature_values.insert(signature_values.end(),config.time_control.events.begin(),config.time_control.events.end());
    }
    if(!config.time_control.step_sizes.empty()) {
        signature_values.insert(signature_values.end(),{20504.,double(config.time_control.step_sizes.size())});
        signature_values.insert(signature_values.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    }
    if(f.pressure_time) signature_values.insert(signature_values.end(),{20505.,f.pressure_time->amplitude,f.pressure_time->period,f.pressure_time->ramp_time});
    if(f.inlet) {
        signature_values.insert(signature_values.end(),{20506.,double(f.inlet->tag),f.inlet->ramp_time});
        for(const auto& a:{std::vector<double>(f.inlet->value.begin(),f.inlet->value.end()),std::vector<double>(f.inlet->origin.begin(),f.inlet->origin.end()),std::vector<double>(f.inlet->gradient.begin(),f.inlet->gradient.end())}) signature_values.insert(signature_values.end(),a.begin(),a.end());
    }
    if(f.inlet_flow) {
        const auto& q=*f.inlet_flow;
        signature_values.insert(signature_values.end(),{20507.,q.mean,q.amplitude,q.period,double(q.axis)});
        signature_values.insert(signature_values.end(),q.lower.begin(),q.lower.end());
        signature_values.insert(signature_values.end(),q.upper.begin(),q.upper.end());
        // Preserve old rectangle checkpoint signatures; circle geometry is additional physics.
        if(q.circular) {
            signature_values.insert(signature_values.end(),{20508.,q.radius});
            signature_values.insert(signature_values.end(),q.center.begin(),q.center.end());
        }
    }
    // Diagnostics use local owned cells and current geometry. Surface flux and
    // volume divergence are independently integrated; no global fields gathered.
    const auto mass_observation=[&](const std::vector<double>& state) {
        std::array<double,5> local{},global{}; // volume, inward inlet, outward outlet/wall, div(u)
        output_stage(comm,"mass observation",[&] {
            for(std::size_t e=0;e<mesh.cells.size();++e) if(fluid_cell[e]) {
                const auto& cell=mesh.cells[e]; Tet4Topology::Nodal<Point> xyz,u;
                for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                    const auto n=cell.nodes[a]; xyz[a][c]=mesh.nodes[n].position[c]+state[Layout::dof(n,Layout::mesh_offset+c)];
                    u[a][c]=state[Layout::dof(n,c)];
                }
                const auto observation=fsi_tet_mass_observation(xyz,u); local[0]+=observation[0]; local[4]+=observation[1];
                for(int skip=0;skip<4;++skip) {
                    Tri3Topology::Nodal<LocalId> key; int k=0;
                    for(int a=0;a<4;++a) if(a!=skip) {key[k++]=cell.nodes[a];}
                    std::sort(key.begin(),key.end());
                    const auto found=boundary.find(key);
                    if(found==boundary.end()&&!interface_keys.count(key)) continue;
                    const double flux=observation[2+skip];
                    const int tag=found==boundary.end()?0:found->second;
                    if(f.inlet&&tag==f.inlet->tag) local[1]-=flux;
                    else if(std::find(f.domains.pressure_tags.begin(),f.domains.pressure_tags.end(),tag)!=f.domains.pressure_tags.end()) local[2]+=flux;
                    else local[3]+=flux;
                }
            }
        });
        MPI_Allreduce(local.data(),global.data(),5,MPI_DOUBLE,MPI_SUM,comm);
        return global;
    };
    const auto signature=state_signature(mesh,dual?"fsi_dual":"fsi",signature_values);
    TimeStepper clock(f.dt,f.steps,config.time_control);
    if(!config.restart.empty()) {
        std::map<std::string,std::size_t> sizes{{"reduced",accepted.size()},
            {"physical",physical.size()},{"solid_displacement",solid_d.size()},{"rigid",2}};
        if(bdf2) { sizes["previous_physical"]=physical.size(); sizes["previous_displacement"]=solid_d.size(); sizes["previous_rigid"]=2; sizes["time_metadata"]=1; }
        if(alpha) {
            sizes["fluid_rate"]=fluid_rate.size(); sizes["mesh_velocity"]=mesh_velocity.size(); sizes["mesh_acceleration"]=mesh_acceleration.size(); sizes["time_metadata"]=2;
            if(Elastic) sizes["solid_acceleration"]=solid_acceleration.size();
        }
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);
        accepted=saved.fields.at("reduced"); physical=saved.fields.at("physical"); solid_d=saved.fields.at("solid_displacement");
        body={saved.fields.at("rigid")[0],saved.fields.at("rigid")[1]}; clock.restore(saved.step,saved.time,saved.next_dt,saved.time_correction);
        if(bdf2) {
            physical_history.previous=saved.fields.at("previous_physical");
            displacement_history.previous=saved.fields.at("previous_displacement");
            body_history.previous=saved.fields.at("previous_rigid");
            const double previous_dt=saved.fields.at("time_metadata")[0];
            if(previous_dt<0||previous_dt>saved.time||(previous_dt==0&&!clock.at_event())) throw std::runtime_error("Invalid BDF2 FSI history step");
            physical_history.previous_dt=displacement_history.previous_dt=body_history.previous_dt=previous_dt;
        }
        if(alpha) {
            fluid_rate=saved.fields.at("fluid_rate"); mesh_velocity=saved.fields.at("mesh_velocity"); mesh_acceleration=saved.fields.at("mesh_acceleration");
            if(Elastic) solid_acceleration=saved.fields.at("solid_acceleration");
            const auto& metadata=saved.fields.at("time_metadata");
            if((metadata[0]!=0&&metadata[0]!=1)||(metadata[0]==0&&!clock.at_event())) throw std::runtime_error("Invalid alpha FSI checkpoint history");
            alpha_ready=metadata[0]==1; body_acceleration=metadata[1];
        }
        if(!clock.active(config.stop_after)) throw std::runtime_error("Restart must precede requested final step");
    }
    const auto snapshot=[&] {
        result.current_mesh=mesh;
        result.fields={{"velocity",Space3::dimension,{}},{"pressure",1,{}},{"mesh_displacement",Space3::dimension,{}}};
        if(Elastic) { result.solid_mesh=mesh; result.solid_fields={{"velocity",Space3::dimension,{}},{"displacement",Space3::dimension,solid_d}}; }
        if(alpha) {
            result.fields.push_back({"mesh_velocity",Space3::dimension,mesh_velocity});
            result.fields.push_back({"fluid_algorithmic_acceleration",Space3::dimension,fluid_rate});
            result.fields.push_back({"mesh_algorithmic_acceleration",Space3::dimension,mesh_acceleration});
            if(Elastic) result.solid_fields.push_back({"algorithmic_acceleration",Space3::dimension,solid_acceleration});
        }
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
    };
    const std::string history_stem=config.output.stem().string()+(config.restart.empty()?"":"_restart"+std::to_string(clock.step));
    const auto history_path=[&](const std::string& suffix) {return config.output.parent_path()/(history_stem+suffix);};
    std::ofstream history;
    std::vector<std::pair<double,std::string>> fluid_series,solid_series;
    if(f.output_interval>0) output_stage(comm,"history open",[&] {
        if(mesh.rank!=0) return;
        if(!config.output.parent_path().empty()) std::filesystem::create_directories(config.output.parent_path());
        history.exceptions(std::ios::badbit|std::ios::failbit);
        history.open(history_path(".csv")); history<<std::setprecision(17);
        history<<"step,time,accepted_dt,evaluation_time,applied_pressure,endpoint_position,endpoint_velocity,evaluation_fluid_force,evaluation_body_balance,evaluation_interface_power,evaluation_body_power,evaluation_power_balance,snes_iterations,residual,time_order,reference_interface_area,current_interface_area,area_displacement_x,area_displacement_y,area_displacement_z,area_velocity_x,area_velocity_y,area_velocity_z,stage_min_fluid_j,stage_min_solid_j,endpoint_min_fluid_j,endpoint_min_solid_j";
        if(f.inlet_flow) history<<",stage_volume,stage_inlet_flow,stage_outlet_flow,stage_wall_flux,stage_divergence,endpoint_volume,endpoint_inlet_flow,endpoint_outlet_flow,endpoint_wall_flux,endpoint_divergence,volume_secant_rate,stage_mass_residual,secant_mass_residual,target_endpoint_flow";
        history<<'\n';
        history.flush();
    });
    NonlinearSystem system(comm,layout);
    std::array<double,3> last_lu_coefficients{};
    while(clock.active(config.stop_after)) {
        if(bdf2&&physical_history.previous_dt>0) clock.next_dt=std::min(clock.next_dt,2*physical_history.previous_dt);
        const int step=clock.step+1; const double dt=clock.dt(),time=clock.time+dt;
        const auto derivative=time_derivative(alpha?TimeScheme::backward_euler:config.time_integration.scheme,dt,physical_history.previous_dt);
        const bool alpha_step=alpha&&alpha_ready;
        const AlphaStep fluid_map(dt,config.time_integration.rho_infinity,false),solid_map(dt,config.time_integration.rho_infinity,true);
        const double af=alpha_step?fluid_map.p.alpha_f:1;
        const double evaluation_time=clock.time+af*dt;
        const double pressure=fsi_pressure(f,evaluation_time);
        const double integration_dt=alpha_step?fluid_map.effective_dt():derivative.effective_dt;
        const double solid_dt=alpha_step?solid_map.effective_dt():derivative.effective_dt;
        const double mesh_dt=alpha_step?solid_map.displacement_dt():derivative.effective_dt;
        const std::array<double,3> lu_coefficients{integration_dt,solid_dt,mesh_dt};
        auto effective_physical=bdf2?physical_history.reference(physical,derivative):std::vector<double>{};
        auto effective_d=bdf2?displacement_history.reference(solid_d,derivative):std::vector<double>{};
        if(alpha_step) {
            effective_physical=physical; effective_d=solid_d;
            for(std::size_t n=0;n<mesh.nodes.size();++n) for(int c=0;c<Space3::dimension;++c) {
                const auto vector=Tet4Vector::dof(n,c),flow=Layout::dof(n,c),grid=Layout::dof(n,Layout::mesh_offset+c);
                effective_physical[flow]=fluid_map.reference(physical[flow],fluid_rate[vector]);
                effective_physical[grid]=solid_map.displacement_reference(physical[grid],mesh_velocity[vector],mesh_acceleration[vector]);
                if(Elastic) {
                    const auto structure=Layout::dof(n,Layout::structure_offset+c);
                    effective_physical[structure]=solid_map.reference(physical[structure],solid_acceleration[vector]);
                    effective_d[vector]=solid_map.displacement_reference(solid_d[vector],physical[structure],solid_acceleration[vector]);
                }
            }
        }
        const auto& reference_physical=bdf2||alpha_step?effective_physical:physical;
        const auto& reference_d=bdf2||alpha_step?effective_d:solid_d;
        RigidState reference_body=body;
        if(bdf2) {
            const auto state=body_history.reference({body.position,body.velocity},derivative);
            reference_body={state[0],state[1]};
        }
        if(alpha_step) reference_body={solid_map.displacement_reference(body.position,body.velocity,body_acceleration),solid_map.reference(body.velocity,body_acceleration)};
        const auto expand=[&](const std::vector<double>& x) {
        std::vector<double> full(mesh.nodes.size()*nc,0);
        for(std::size_t i=0;i<full.size();++i) {
            const auto n=i/nc,c=i%nc;
            const double lifting=Layout::is_mesh(c)?
                (Elastic?reference_d[Tet4Vector::components*n+c-Layout::mesh_offset]:
                 (c==Layout::mesh_offset?reference_body.position:0)):0;
            full[i]=reduced.slot(i,mesh_dt,lifting).expand(x);
            if(c<3&&inlet_nodes[n]) full[i]=((1-af)*inlet_scale(clock.time)+af*inlet_scale(time))*inlet_values[n][c];
        }
        return full;
    };
        try {
        for(std::size_t e=0;e<data.size();++e) {
            if(!fluid_cell[e]) continue;
            double speed2=0;
            for(int a=0;a<Tet4Topology::nodes;++a) {
                const auto n=mesh.cells[e].nodes[a];
                for(int c=0;c<Tet4Flow::components;++c) data[e].previous_fluid[Tet4Flow::components*a+c]=reference_physical[nc*n+c];
                for(int c=0;c<Space3::dimension;++c) data[e].previous_mesh[a][c]=reference_physical[Layout::dof(n,Layout::mesh_offset+c)];
                for(int c=0;c<Space3::dimension;++c) speed2+=physical[nc*n+c]*physical[nc*n+c]*Tet4Topology::mean_weight;
            }
            const double h=std::cbrt(Tet4Topology::jacobian_scale*data[e].reference_geometry.volume);
            const double tau_dt=f.stabilization_time_scale.value_or(integration_dt);
            const double tau=f.stabilization_tau.value_or(1/std::sqrt(4*f.density*f.density/(tau_dt*tau_dt)+4*f.density*f.density*speed2/(h*h)+16*f.viscosity*f.viscosity/(h*h*h*h)));
            data[e].fluid={f.density,f.viscosity,integration_dt,tau,true};
            data[e].mesh_dt=mesh_dt;
            data[e].inlet_pressure=pressure;
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
                    vs[Tet4Vector::components*a+c]=full[Layout::dof(n,Layout::structure_offset+c)]; dn[Tet4Vector::components*a+c]=reference_d[Tet4Vector::components*n+c]; vn[Tet4Vector::components*a+c]=reference_physical[Layout::dof(n,Layout::structure_offset+c)];
                }
            }
            if(fluid_cell[e]) {
            const auto fr=fsi_element_residual(data[e],state);
            for(int i=0;i<Tet4Ale::dofs;++i) r[Layout::dof(Tet4Ale::node(i),Tet4Ale::component(i))]=fr[i];
            if(tangent) {
                const auto fj=finite_difference?fsi_element_tangent_fd(data[e],state):fsi_element_tangent(data[e],state);
                for(int i=0;i<Tet4Ale::dofs;++i) for(int k=0;k<Tet4Ale::dofs;++k) j[(Layout::dof(Tet4Ale::node(i),Tet4Ale::component(i)))*nd+Layout::dof(Tet4Ale::node(k),Tet4Ale::component(k))]=fj[Tet4Ale::matrix(i,k)];
            }
            }
            if(solid_cell[e]) {
                const auto sr=solid_element(solid_geometry[e],{f.young,f.poisson,f.solid_density,solid_dt,f.neo_hookean,mesh_dt},vs,dn,vn,tangent);
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
                    const auto mapping=reduced.slot(i,mesh_dt);
                    rows[nc*a+c]=mapping.test_row; cols[nc*a+c]=mapping.column;
                    chain[nc*a+c]=mapping.trial_weight;
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
                const double rbody=rigid_residual({f.mass,f.damping,f.stiffness},reference_body,solid_dt,v,0,mesh_dt);
                EONSIM_PETSC(VecSetValue(r,reduced.body,rbody,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,reduced.body,reduced.body,f.mass/solid_dt+f.damping+mesh_dt*f.stiffness,ADD_VALUES));
            }
        };
        // The fluid, structure and displacement maps have different alpha
        // coefficients. Retain only the preconditioner, never a previous
        // coupled operator; any coefficient change starts a fresh LU window.
        const bool refresh_lu=lu_reuse_window>0&&lu_coefficients!=last_lu_coefficients;
        const auto solved=system.solve(config.solver,accepted,{}, {},assemble,lu_reuse_window,refresh_lu);
        const auto next=expand(solved.values);
        double local[4]{},global[4]{};
        for(std::size_t e=0;e<data.size();++e) {
            std::vector<double> r,j;
            local_residual(e,next,false,r,j);
            for(int a=0;a<Tet4Topology::nodes;++a) if(interface[mesh.cells[e].nodes[a]]) {
                local[0]-=r[nc*a];
                if(Elastic&&reduced.global[Layout::dof(mesh.cells[e].nodes[a],Layout::structure_offset)]>=0)
                    local[1]+=r[nc*a]+r[Layout::dof(a,Layout::structure_offset)];
                for(int c=0;c<Space3::dimension;++c) {
                    const auto n=mesh.cells[e].nodes[a];
                    const double velocity=next[Layout::dof(n,c)];
                    local[2]-=r[Layout::dof(a,c)]*velocity;
                    if(Elastic) local[3]+=r[Layout::dof(a,Layout::structure_offset+c)]*velocity;
                }
            }
        }
        MPI_Allreduce(local,global,4,MPI_DOUBLE,MPI_SUM,comm);
        result.fluid_force=global[0];
        auto next_physical=next,next_reduced=solved.values,next_solid=solid_d;
        auto next_fluid_rate=fluid_rate,next_mesh_velocity=mesh_velocity,next_mesh_acceleration=mesh_acceleration,next_solid_acceleration=solid_acceleration;
        double next_body_acceleration=body_acceleration;
        RigidState next_body=body;
        if(alpha_step) {
            for(std::size_t i=0;i<next_physical.size();++i) next_physical[i]=fluid_map.endpoint(physical[i],next[i]);
            for(std::size_t i=0;i<next_reduced.size();++i) next_reduced[i]=fluid_map.endpoint(accepted[i],solved.values[i]);
        }
        for(std::size_t n=0;n<mesh.nodes.size();++n) for(int c=0;c<Space3::dimension;++c) {
            const auto vector=Tet4Vector::dof(n,c),flow=Layout::dof(n,c),grid=Layout::dof(n,Layout::mesh_offset+c);
            if(Elastic) {
                const auto structure=Layout::dof(n,Layout::structure_offset+c);
                const double stage_d=reference_d[vector]+mesh_dt*next[structure];
                next_solid[vector]=alpha_step?solid_map.endpoint(solid_d[vector],stage_d):stage_d;
                if(alpha) next_solid_acceleration[vector]=alpha_step?solid_map.endpoint_rate(physical[structure],solid_acceleration[vector],next[structure]):(next[structure]-physical[structure])/dt;
            }
            if(alpha) {
                next_fluid_rate[vector]=alpha_step?fluid_map.endpoint_rate(physical[flow],fluid_rate[vector],next[flow]):(next[flow]-physical[flow])/dt;
                // The shared trace is already a velocity unknown. Recovering it
                // by subtracting two displacements loses digits on small retries.
                const double stage_w=interface[n]?
                    (Elastic?next[Layout::dof(n,Layout::structure_offset+c)]:(c==0?solved.values[reduced.body_local]:0)):
                    (next[grid]-reference_physical[grid])/mesh_dt;
                next_mesh_velocity[vector]=alpha_step?solid_map.endpoint(mesh_velocity[vector],stage_w):stage_w;
                next_mesh_acceleration[vector]=alpha_step?solid_map.endpoint_rate(mesh_velocity[vector],mesh_acceleration[vector],stage_w):(stage_w-mesh_velocity[vector])/dt;
            }
        }
        if(!Elastic) {
            const double v=solved.values[reduced.body_local],position=reference_body.position+mesh_dt*v;
            result.balance=rigid_residual({f.mass,f.damping,f.stiffness},reference_body,solid_dt,v,result.fluid_force,mesh_dt);
            next_body={alpha_step?solid_map.endpoint(body.position,position):position,alpha_step?solid_map.endpoint(body.velocity,v):v};
            if(alpha) next_body_acceleration=alpha_step?solid_map.endpoint_rate(body.velocity,body_acceleration,v):(v-body.velocity)/dt;
        }
        // Both stage and extrapolated endpoint must be valid before any history commit.
        double quality[4]; std::fill(std::begin(quality),std::end(quality),std::numeric_limits<double>::infinity());
        int invalid=0,any_invalid=0; bool checking_endpoint=false;
        try {
            for(std::size_t e=0;e<mesh.cells.size();++e) {
                Tet4Topology::Nodal<Point> ref,stage_xyz,end_xyz;
                const auto& cell=mesh.cells[e];
                if(fluid_cell[e]) {
                    for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                        const auto n=cell.nodes[a]; ref[a][c]=mesh.nodes[n].position[c];
                        stage_xyz[a][c]=ref[a][c]+next[Layout::dof(n,Layout::mesh_offset+c)];
                        end_xyz[a][c]=ref[a][c]+next_physical[Layout::dof(n,Layout::mesh_offset+c)];
                    }
                    checking_endpoint=false;
                    quality[0]=std::min(quality[0],fsi_volume_ratio(ref,stage_xyz));
                    checking_endpoint=true;
                    quality[2]=std::min(quality[2],fsi_volume_ratio(ref,end_xyz));
                }
                if(solid_cell[e]) {
                    for(int a=0;a<4;++a) for(int c=0;c<3;++c) {
                        const auto n=cell.nodes[a];
                        ref[a][c]=(!dual&&c==0?1+f.thickness*(1-mesh.nodes[n].position[0]):mesh.nodes[n].position[c]);
                        stage_xyz[a][c]=ref[a][c]+reference_d[3*n+c]+mesh_dt*next[Layout::dof(n,Layout::structure_offset+c)];
                        end_xyz[a][c]=ref[a][c]+next_solid[3*n+c];
                    }
                    if(!dual) {std::swap(ref[1],ref[2]);std::swap(stage_xyz[1],stage_xyz[2]);std::swap(end_xyz[1],end_xyz[2]);}
                    checking_endpoint=false;
                    quality[1]=std::min(quality[1],fsi_volume_ratio(ref,stage_xyz));
                    checking_endpoint=true;
                    quality[3]=std::min(quality[3],fsi_volume_ratio(ref,end_xyz));
                }
            }
        } catch(const StepRejected&) {invalid=checking_endpoint?2:1;}
        MPI_Allreduce(&invalid,&any_invalid,1,MPI_INT,MPI_MAX,comm);
        if(any_invalid) throw StepRejected(any_invalid==2?"Invalid FSI endpoint geometry":"Invalid FSI stage geometry");
        if(!Elastic) quality[1]=quality[3]=1;
        double min_quality[4]; MPI_Allreduce(quality,min_quality,4,MPI_DOUBLE,MPI_MIN,comm);
        double local_surface[8]{},surface[8]{};
        output_stage(comm,"interface observation",[&] {
            for(const auto& face:interface_faces) {
                Tri3Topology::Nodal<Point> ref,current,displacement,velocity;
                for(int a=0;a<3;++a) for(int c=0;c<3;++c) {
                    const auto n=face[a]; ref[a][c]=mesh.nodes[n].position[c];
                    displacement[a][c]=next_physical[Layout::dof(n,Layout::mesh_offset+c)];
                    velocity[a][c]=next_physical[Layout::dof(n,c)]; current[a][c]=ref[a][c]+displacement[a][c];
                }
                const auto obs=fsi_surface_observation(ref,current,displacement,velocity);
                for(int i=0;i<8;++i) local_surface[i]+=obs[i];
            }
        });
        MPI_Allreduce(local_surface,surface,8,MPI_DOUBLE,MPI_SUM,comm);
        if(!(surface[0]>0)) throw std::runtime_error("Empty FSI observation interface");
        for(int i=2;i<8;++i) surface[i]/=surface[0];
        if(Elastic) {
            double average[3]{},sum[3]{};
            for(std::size_t n=0;n<mesh.owned_nodes;++n) if(interface[n]) {
                average[0]+=next_solid[Tet4Vector::components*n]; average[1]+=next_physical[Layout::dof(n,Layout::structure_offset)]; average[2]+=1;
            }
            MPI_Allreduce(average,sum,3,MPI_DOUBLE,MPI_SUM,comm);
            result.position=sum[0]/sum[2]; result.velocity=sum[1]/sum[2]; result.balance=global[1];
        } else {
            result.position=next_body.position; result.velocity=next_body.velocity;
        }
        std::array<double,5> stage_mass{},endpoint_mass{},old_mass{};
        if(f.inlet_flow) {stage_mass=mass_observation(next); endpoint_mass=mass_observation(next_physical); old_mass=mass_observation(physical);}
        const double body_power=Elastic?global[3]:(result.balance+result.fluid_force)*solved.values[reduced.body_local];
        if(bdf2) { physical_history.commit(physical,dt); displacement_history.commit(solid_d,dt); body_history.commit({body.position,body.velocity},dt); }
        accepted=std::move(next_reduced); physical=std::move(next_physical); solid_d=std::move(next_solid); body=next_body;
        if(alpha) {
            fluid_rate=std::move(next_fluid_rate); mesh_velocity=std::move(next_mesh_velocity); mesh_acceleration=std::move(next_mesh_acceleration);
            solid_acceleration=std::move(next_solid_acceleration); body_acceleration=next_body_acceleration; alpha_ready=true;
        }
        clock.accept();
        last_lu_coefficients=lu_coefficients;
        if(bdf2&&clock.at_event()) physical_history.previous_dt=displacement_history.previous_dt=body_history.previous_dt=0;
        if(alpha&&clock.at_event()) alpha_ready=false;
        if(!config.checkpoint.empty()&&(step%f.checkpoint_interval==0||!clock.active(config.stop_after))) {
            Checkpoint saved{step,{{"reduced",accepted},{"physical",physical},{"solid_displacement",solid_d},{"rigid",{body.position,body.velocity}}},clock.time,clock.next_dt,clock.correction()};
            if(bdf2) {
                saved.fields["previous_physical"]=physical_history.previous;
                saved.fields["previous_displacement"]=displacement_history.previous;
                saved.fields["previous_rigid"]=body_history.previous;
                saved.fields["time_metadata"]={physical_history.previous_dt};
            }
            if(alpha) {
                saved.fields["fluid_rate"]=fluid_rate; saved.fields["mesh_velocity"]=mesh_velocity; saved.fields["mesh_acceleration"]=mesh_acceleration;
                if(Elastic) saved.fields["solid_acceleration"]=solid_acceleration;
                saved.fields["time_metadata"]={alpha_ready?1.:0.,body_acceleration};
            }
            write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
        }
        if(f.output_interval>0) {
            if(step%f.output_interval==0||!clock.active(config.stop_after)) {
                output_stage(comm,"snapshot extraction",snapshot);
                const auto path=history_path("_step"+std::to_string(step)+".vtu");
                write_fsi_fields(comm,path,result);
                output_stage(comm,"series publication",[&] {
                    if(mesh.rank!=0) return;
                    const auto suffix=mesh.ranks>1?".pvtu":".vtu";
                    fluid_series.emplace_back(time,path.stem().string()+suffix);
                    publish_series(history_path(".pvd"),fluid_series);
                    if(Elastic) {
                        solid_series.emplace_back(time,path.stem().string()+"_solid"+suffix);
                        publish_series(history_path("_solid.pvd"),solid_series);
                    }
                });
            }
            output_stage(comm,"history row",[&] {
                if(mesh.rank!=0) return;
                history<<step<<','<<time<<','<<dt<<','<<evaluation_time<<','<<pressure<<','<<result.position<<','<<result.velocity<<','
                    <<result.fluid_force<<','<<result.balance<<','<<global[2]<<','<<body_power<<','<<body_power-global[2]<<','
                    <<solved.iterations<<','<<solved.residual_norm<<','<<(alpha_step?2:derivative.order);
                for(double value:surface) history<<','<<value;
                for(double value:min_quality) history<<','<<value;
                if(f.inlet_flow) {
                    for(double v:stage_mass) history<<','<<v;
                    for(double v:endpoint_mass) history<<','<<v;
                    const double rate=(endpoint_mass[0]-old_mass[0])/dt;
                    history<<','<<rate<<','<<stage_mass[1]-stage_mass[2]-stage_mass[3]
                        <<','<<stage_mass[1]-stage_mass[2]-rate<<','<<inlet_scale(time);
                }
                history<<'\n';
                history.flush();
            });
        }
        const std::string stage=alpha?"stage_":"";
        if(mesh.rank==0) std::cout << std::setprecision(17) << "fsi_step=" << step << " time=" << time << " accepted_dt=" << dt << " evaluation_time=" << evaluation_time << " applied_pressure=" << pressure
            << " position=" << result.position << " velocity=" << result.velocity << " " << stage << "fluid_force=" << result.fluid_force
            << " " << stage << "body_balance=" << result.balance << " snes_iterations=" << solved.iterations
            << " " << stage << "interface_power=" << global[2] << " " << stage << "body_power=" << body_power << " " << stage << "power_balance=" << body_power-global[2]
            << " area_displacement_x=" << surface[2] << " area_displacement_y=" << surface[3]
            << " endpoint_min_fluid_j=" << min_quality[2] << " endpoint_min_solid_j=" << min_quality[3]
            << " residual=" << solved.residual_norm << " time_order=" << (alpha_step?2:derivative.order) << '\n';
        } catch(const StepRejected& error) {
            // Endpoint geometry can reject an otherwise converged solve.
            // Its retained factor must not survive a retry at an older dt.
            last_lu_coefficients={};
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
    }
    if(f.output_interval>0) output_stage(comm,"history close",[&] {if(mesh.rank==0) history.close();});
    output_stage(comm,"final snapshot",snapshot);
    return result;
}
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    return config.fsi.elastic?solve_fsi_impl<true>(comm,mesh,config):solve_fsi_impl<false>(comm,mesh,config);
}
}
