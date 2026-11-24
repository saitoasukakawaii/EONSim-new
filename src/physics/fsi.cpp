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

// PETSc aggregates rank-local event counts and times along with PCSetUp and
// PCApply. An inactive event avoids both clock reads and PETSc calls.
struct FsiAssemblyEvents {
    PetscLogEvent fluid_residual=-1, fluid_ale_tangent=-1;
    PetscLogEvent solid_residual=-1, solid_tangent=-1, insert=-1, force_replay=-1;

    void register_for_log_view() {
        PetscBool enabled=PETSC_FALSE;
        EONSIM_PETSC(PetscOptionsHasName(nullptr,nullptr,"-log_view",&enabled));
        if(!enabled) return;
        EONSIM_PETSC(PetscLogEventRegister("FSIFluidRes",0,&fluid_residual));
        EONSIM_PETSC(PetscLogEventRegister("FSIFluidAleJac",0,&fluid_ale_tangent));
        EONSIM_PETSC(PetscLogEventRegister("FSISolidRes",0,&solid_residual));
        EONSIM_PETSC(PetscLogEventRegister("FSISolidJac",0,&solid_tangent));
        EONSIM_PETSC(PetscLogEventRegister("FSIInsert",0,&insert));
        EONSIM_PETSC(PetscLogEventRegister("FSIForceReplay",0,&force_replay));
    }
};

template<class Work> void measured(PetscLogEvent event,const Work& work) {
    if(event<0) { work(); return; }
    EONSIM_PETSC(PetscLogEventBegin(event,nullptr,nullptr,nullptr,nullptr));
    try { work(); }
    catch(...) {
        // A rejected geometric trial can resume in the same SNES solve.
        (void)PetscLogEventEnd(event,nullptr,nullptr,nullptr,nullptr);
        throw;
    }
    EONSIM_PETSC(PetscLogEventEnd(event,nullptr,nullptr,nullptr,nullptr));
}

struct TaggedPressureFace {
    std::size_t cell,tag_index;
    int opposite;
};

struct CellWallSupport {
    std::size_t cell;
    WallSupportFace face;
};

// The circular profile is radial within its own plane. Evaluate it once per
// node before normalizing the complete discrete face flux over all ranks.
double inlet_profile(const FsiFlowRate& flow,const Point& x,const Point& inward) {
    if(flow.circular) {
        Point offset{};
        double distance=0,scale=std::max(1.0,flow.radius);
        for(int j=0;j<3;++j) {
            offset[j]=x[j]-flow.center[j];
            distance+=offset[j]*inward[j];
            scale=std::max({scale,std::abs(x[j]),std::abs(flow.center[j])});
        }
        const double tolerance=std::max(1e-12,32*std::numeric_limits<double>::epsilon()*scale);
        if(std::abs(distance)>tolerance) throw std::runtime_error("FSI flow inlet outside circle plane");
        double radial_square=0;
        for(int j=0;j<3;++j) {
            const double radial=(offset[j]-distance*inward[j])/flow.radius;
            radial_square+=radial*radial;
        }
        if(!std::isfinite(radial_square)||radial_square>1+1e-12) throw std::runtime_error("FSI flow inlet outside circle");
        return std::max(0.,1-radial_square);
    }
    double shape=1;
    for(int j=0;j<3;++j) {
        if(x[j]<flow.lower[j]-1e-12||x[j]>flow.upper[j]+1e-12) throw std::runtime_error("FSI flow inlet outside rectangle");
        if(j!=flow.axis) {
            const double r=std::clamp((x[j]-flow.lower[j])/(flow.upper[j]-flow.lower[j]),0.,1.);
            shape*=r*(1-r);
        }
    }
    return shape;
}

struct OutletState {
    double capacitor=0,previous=0,rate=0;
};

void assemble_outlet(const ReducedLayout& layout,const OutletTrace& trace,const RcrStage& stage,double outlet_pressure,
    const std::vector<double>& physical,bool owns_pressure,Vec residual,Mat jacobian) {
    const auto port=trace.pressure;
    double flux=0;
    for(const auto& [slot,weight]:trace.flux_weights) {
        flux+=weight*physical[slot];
        const auto row=layout.global[slot];
        if(row<0) continue;
        EONSIM_PETSC(VecSetValue(residual,row,weight*outlet_pressure,ADD_VALUES));
        if(jacobian) {
            EONSIM_PETSC(MatSetValue(jacobian,row,port,weight,ADD_VALUES));
            EONSIM_PETSC(MatSetValue(jacobian,port,row,-weight,ADD_VALUES));
        }
    }
    const double value=(owns_pressure?stage.flow(outlet_pressure):0)-flux;
    EONSIM_PETSC(VecSetValue(residual,port,value,ADD_VALUES));
    if(owns_pressure&&jacobian)
        EONSIM_PETSC(MatSetValue(jacobian,port,port,1/stage.total_impedance,ADD_VALUES));
}

struct OutletObservation {
    double stage_pressure,endpoint_pressure,stage_capacitor,stage_rate;
};

template<class Layout>
WallSupportBalance observe_wall_support(const MeshPartition& mesh,const CellWallSupport& support,
    const std::vector<double>& displacement,const std::vector<double>& state,double displacement_dt)
{
    Tet4Vector::State<double> d{},v{};
    const auto& cell=mesh.cells[support.cell];
    for(int a:support.face.nodes) for(int i=0;i<Space3::dimension;++i) {
        const auto node=cell.nodes[a];
        d[Tet4Vector::dof(a,i)]=displacement[Tet4Vector::dof(node,i)];
        v[Tet4Vector::dof(a,i)]=state[Layout::dof(node,Layout::structure_offset+i)];
    }
    return support.face.evaluate(d,v,displacement_dt);
}

template<class Layout>
void write_pressure_faces(MPI_Comm comm,const MeshPartition& mesh,const std::vector<int>& tags,
    const std::vector<TaggedPressureFace>& faces,const std::vector<double>& stage,
    const std::vector<double>& endpoint,bool distinct_stage,double viscosity,
    int step,double time,double dt,double stage_time,const std::vector<std::array<double,2>>& pressures,std::ostream& out)
{
    constexpr std::size_t integrals_per_face=4;
    const std::size_t stride=tags.size()*integrals_per_face;
    const int samples=distinct_stage?2:1;
    std::vector<double> local(samples*stride,0.),total(local.size());
    output_stage(comm,"pressure face integration",[&] {
        for(int s=0;s<samples;++s) {
            const auto& state=s==0?stage:endpoint;
            for(const auto& face:faces) {
                const auto& cell=mesh.cells[face.cell];
                Tet4Topology::Nodal<Point> current,velocity;
                Tet4Topology::Nodal<double> pressure;
                for(int a=0;a<Tet4Topology::nodes;++a) {
                    const auto n=cell.nodes[a];
                    for(int c=0;c<Space3::dimension;++c) {
                        current[a][c]=mesh.nodes[n].position[c]+state[Layout::dof(n,Layout::mesh_offset+c)];
                        velocity[a][c]=state[Layout::dof(n,c)];
                    }
                    pressure[a]=state[Layout::dof(n,Layout::pressure)];
                }
                const auto values=fsi_pressure_face_integrals(current,velocity,pressure,face.opposite,viscosity);
                const auto offset=s*stride+integrals_per_face*face.tag_index;
                for(std::size_t i=0;i<values.size();++i) local[offset+i]+=values[i];
            }
        }
    });
    MPI_Reduce(local.data(),total.data(),static_cast<int>(total.size()),MPI_DOUBLE,MPI_SUM,0,comm);
    output_stage(comm,"pressure face history row",[&] {
        if(mesh.rank!=0) return;
        for(std::size_t i=0;i<tags.size();++i) {
            out<<step<<','<<time<<','<<dt<<','<<stage_time<<','<<tags[i];
            for(int s=0;s<2;++s) {
                const auto offset=(distinct_stage?s*stride:0)+i*integrals_per_face;
                const double area=total[offset],flow=total[offset+3];
                if(!(area>0)) throw std::runtime_error("Empty FSI pressure face tag "+std::to_string(tags[i]));
                const double load=pressures[i][s];
                for(double value:{area,total[offset+1]/area,total[offset+2]/area,flow,load,-load*flow}) {
                    if(!std::isfinite(value)) throw std::runtime_error("Nonfinite FSI pressure face observation");
                    out<<','<<value;
                }
            }
            out<<'\n';
        }
        out.flush();
    });
}
}
double fsi_pressure(const FsiConfig& config,double time) {
    return config.pressure_time?config.pressure_time->value_at(config.pressure,time):config.pressure;
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
    const auto& outlets=f.domains.rcr_outlets;
    std::map<int,std::size_t> outlet_by_tag;
    for(std::size_t i=0;i<outlets.size();++i) outlet_by_tag.emplace(outlets[i].tag,i);
    const bool bdf2=config.time_integration.scheme==TimeScheme::bdf2;
    const bool alpha=config.time_integration.scheme==TimeScheme::generalized_alpha;
    bool alpha_ready=false;
    PetscBool finite_difference=PETSC_FALSE;
    EONSIM_PETSC(PetscOptionsGetBool(nullptr,nullptr,"-fsi_fd_tangent",&finite_difference,nullptr));
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
            const double shape=f.inlet_flow ? inlet_profile(*f.inlet_flow,mesh.nodes[n].position,f.inlet->value) : 1.;
            for(int c=0;c<3;++c) {
                double value=f.inlet->value[c];
                for(int j=0;j<3;++j) value+=f.inlet->gradient[3*c+j]*(mesh.nodes[n].position[j]-f.inlet->origin[j]);
                value*=shape;
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
                    double dot=0;
                    for(int c=0;c<3;++c) dot+=g.normal[c]*f.inlet->value[c];
                    if(std::abs(dot+1)>1e-10) throw std::runtime_error("FSI flow inlet direction must oppose the outward normal");
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
    const std::vector<int> pressure_tags=dual?f.domains.pressure_tags:std::vector<int>{1};
    std::vector<TaggedPressureFace> pressure_faces;
    const auto& supports=domains.wall_supports;
    std::vector<std::size_t> support_offsets;
    std::vector<CellWallSupport> support_faces;
    std::set<int> local_support_tags;
    bool support_on_fluid=false;
    if(!supports.empty()) support_offsets.reserve(mesh.cells.size()+1);
    for(const auto& cell:mesh.cells) {
        if(!supports.empty()) support_offsets.push_back(support_faces.size());
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
            const auto boundary_face=boundary.find(key);
            if(boundary_face==boundary.end()) continue;
            if(!supports.empty()) {
                const auto support=supports.find(boundary_face->second);
                if(support!=supports.end()) {
                    if(!solid_cell.back()) support_on_fluid=true;
                    else {
                        local_support_tags.insert(support->first);
                        Tri3Topology::Nodal<Point> points;
                        for(int a=0;a<Tri3Topology::nodes;++a) points[a]=reference[face[a]];
                        support_faces.push_back({data.size(),{face,triangle_geometry(points,reference[skip]),
                                                            support->second.stiffness,support->second.damping}});
                    }
                }
            }
            if(!fluid_cell.back()) continue;
            const auto tag=std::find(pressure_tags.begin(),pressure_tags.end(),boundary_face->second);
            if(tag==pressure_tags.end()) continue;
            if(!outlet_by_tag.count(*tag)) e.inlet_faces.push_back(face);
            if(f.pressure_face_history)
                pressure_faces.push_back({data.size(),static_cast<std::size_t>(tag-pressure_tags.begin()),skip});
        }
        e.inlet_pressure=f.pressure; data.push_back(e);
    }
    if(!supports.empty()) {
        support_offsets.push_back(support_faces.size());
        std::vector<int> local{int(support_on_fluid)};
        for(const auto& support:supports) local.push_back(local_support_tags.count(support.first)?1:0);
        std::vector<int> global(local.size());
        MPI_Allreduce(local.data(),global.data(),static_cast<int>(local.size()),MPI_INT,MPI_MAX,comm);
        if(global[0]||std::find(global.begin()+1,global.end(),0)!=global.end())
            throw std::runtime_error("FSI wall support requires a solid exterior tag on the partition");
    }
    std::vector<double> accepted(layout.local_to_global.size(),0),physical(mesh.nodes.size()*nc,0);
    std::vector<OutletState> outlet_state;
    for(std::size_t i=0;i<outlets.size();++i) {
        const double initial=outlets[i].initial_capacitor_pressure;
        outlet_state.push_back({initial,initial,0});
        accepted[reduced.outlets[i].local]=initial;
    }
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
    if(f.stabilization_time_scale) signature_values.insert(signature_values.end(),{20512.,*f.stabilization_time_scale});
    if(f.grad_div_viscosity>0) signature_values.insert(signature_values.end(),{20509.,f.grad_div_viscosity});
    for(const auto& outlet:outlets) signature_values.insert(signature_values.end(),{20511.,double(outlet.tag),outlet.proximal_resistance,
        outlet.distal_resistance,outlet.compliance,outlet.distal_pressure,outlet.initial_capacitor_pressure});
    for(const auto& [tag,support]:supports)
        if(support.stiffness>0||support.damping>0)
            signature_values.insert(signature_values.end(),{20510.,double(tag),support.stiffness,support.damping});
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
        if(!outlets.empty()) sizes["rcr_capacitor"]=3*outlets.size();
        if(bdf2) { sizes["previous_physical"]=physical.size(); sizes["previous_displacement"]=solid_d.size(); sizes["previous_rigid"]=2; sizes["time_metadata"]=1; }
        if(alpha) {
            sizes["fluid_rate"]=fluid_rate.size(); sizes["mesh_velocity"]=mesh_velocity.size(); sizes["mesh_acceleration"]=mesh_acceleration.size(); sizes["time_metadata"]=2;
            if(Elastic) sizes["solid_acceleration"]=solid_acceleration.size();
        }
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);
        accepted=saved.fields.at("reduced"); physical=saved.fields.at("physical"); solid_d=saved.fields.at("solid_displacement");
        if(!outlets.empty()) {
            const auto& values=saved.fields.at("rcr_capacitor");
            for(std::size_t i=0;i<outlets.size();++i) outlet_state[i]={values[3*i],values[3*i+1],values[3*i+2]};
        }
        body={saved.fields.at("rigid")[0],saved.fields.at("rigid")[1]}; clock.restore(saved.step,saved.time,saved.next_dt);
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
    std::ofstream pressure_history;
    std::vector<std::pair<double,std::string>> fluid_series,solid_series;
    if(f.output_interval>0||f.pressure_face_history) output_stage(comm,"history open",[&] {
        if(mesh.rank!=0) return;
        if(!config.output.parent_path().empty()) std::filesystem::create_directories(config.output.parent_path());
        if(f.pressure_face_history) {
            pressure_history.exceptions(std::ios::badbit|std::ios::failbit);
            pressure_history.open(history_path("_pressure_faces.csv"));
            pressure_history<<std::setprecision(17)<<"step,time,accepted_dt,evaluation_time,tag";
            for(const auto* sample:{"stage","endpoint"})
                for(const auto* name:{"area","mean_pressure","mean_normal_traction","outward_flow","prescribed_pressure","pressure_power"})
                    pressure_history<<','<<sample<<'_'<<name;
            pressure_history<<'\n';
        }
        if(f.output_interval==0) return;
        history.exceptions(std::ios::badbit|std::ios::failbit);
        history.open(history_path(".csv")); history<<std::setprecision(17);
        history<<"step,time,accepted_dt,evaluation_time,applied_pressure,endpoint_position,endpoint_velocity,evaluation_fluid_force,evaluation_body_balance,evaluation_interface_power,evaluation_body_power,evaluation_power_balance,snes_iterations,residual,time_order,reference_interface_area,current_interface_area,area_displacement_x,area_displacement_y,area_displacement_z,area_velocity_x,area_velocity_y,area_velocity_z,stage_min_fluid_j,stage_min_solid_j,endpoint_min_fluid_j,endpoint_min_solid_j";
        if(f.inlet_flow) history<<",stage_volume,stage_inlet_flow,stage_outlet_flow,stage_wall_flux,stage_divergence,endpoint_volume,endpoint_inlet_flow,endpoint_outlet_flow,endpoint_wall_flux,endpoint_divergence,volume_secant_rate,stage_mass_residual,secant_mass_residual,target_endpoint_flow";
        if(!supports.empty()) history<<",stage_support_spring_energy,stage_support_dissipation,stage_support_power,endpoint_support_spring_energy,step_support_work";
        for(const auto& outlet:outlets) {
            const auto suffix=outlets.size()==1?std::string{}:"_"+std::to_string(outlet.tag);
            for(const char* key:{"rcr_tag","stage_rcr_flow","stage_rcr_pressure","stage_capacitor_pressure",
                                 "stage_capacitor_rate","endpoint_rcr_flow","endpoint_rcr_pressure","endpoint_capacitor_pressure"})
                history<<','<<key<<suffix;
        }
        history<<'\n';
        history.flush();
    });
    NonlinearSystem system(comm,layout);
    FsiAssemblyEvents events;
    events.register_for_log_view();
    const FsiAssemblyEvents unmeasured;
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
        const double stabilization_dt=f.stabilization_time_scale.value_or(integration_dt);
        const double solid_dt=alpha_step?solid_map.effective_dt():derivative.effective_dt;
        const double mesh_dt=alpha_step?solid_map.displacement_dt():derivative.effective_dt;
        std::vector<RcrStage> outlet_stages;
        outlet_stages.reserve(outlets.size());
        for(std::size_t i=0;i<outlets.size();++i) {
            const auto& state=outlet_state[i];
            const double reference=alpha_step?fluid_map.reference(state.capacitor,state.rate):
                derivative.reference(state.capacitor,state.previous);
            outlet_stages.emplace_back(outlets[i],reference,integration_dt);
        }
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
            const double tau=f.stabilization_tau.value_or(1/std::sqrt(4*f.density*f.density/(stabilization_dt*stabilization_dt)
                +4*f.density*f.density*speed2/(h*h)+16*f.viscosity*f.viscosity/(h*h*h*h)));
            data[e].fluid={f.density,f.viscosity,integration_dt,tau,true,f.grad_div_viscosity};
            data[e].mesh_dt=mesh_dt;
            data[e].inlet_pressure=pressure;
        }
        // 相同局部残量同时用于 SNES 装配和收敛后界面力检查。
        const auto local_residual=[&](std::size_t e,const std::vector<double>& full,bool tangent,
                                       FsiCellComponents active,std::vector<double>& r,std::vector<double>& j,const FsiAssemblyEvents& log) {
            Tet4Ale::State<double> state;
            Tet4Vector::State<double> vs,dn,vn;
            const int nd=active.dofs();
            r.assign(nd,0); if(tangent) j.assign(nd*nd,0);
            for(int a=0;a<Tet4Topology::nodes;++a) {
                const auto n=mesh.cells[e].nodes[a];
                if(fluid_cell[e]) for(int c=0;c<Tet4Ale::components;++c)
                    state[Tet4Ale::dof(a,c)]=full[Layout::dof(n,c)];
                if(solid_cell[e]) for(int c=0;c<Space3::dimension;++c) {
                    vs[Tet4Vector::dof(a,c)]=full[Layout::dof(n,Layout::structure_offset+c)];
                    dn[Tet4Vector::dof(a,c)]=reference_d[Tet4Vector::dof(n,c)];
                    vn[Tet4Vector::dof(a,c)]=reference_physical[Layout::dof(n,Layout::structure_offset+c)];
                }
            }
            if(fluid_cell[e]) {
                measured(log.fluid_residual,[&] {
                    const auto fr=fsi_element_residual(data[e],state);
                    if(active.count==Tet4Ale::components) std::copy(fr.begin(),fr.end(),r.begin());
                    else for(int i=0;i<Tet4Ale::dofs;++i)
                        r[active.index(Tet4Ale::node(i),Tet4Ale::component(i))]=fr[i];
                });
                if(tangent) measured(log.fluid_ale_tangent,[&] {
                    const auto fj=finite_difference?fsi_element_tangent_fd(data[e],state):fsi_element_tangent(data[e],state);
                    if(active.count==Tet4Ale::components) std::copy(fj.begin(),fj.end(),j.begin());
                    else for(int i=0;i<Tet4Ale::dofs;++i) for(int k=0;k<Tet4Ale::dofs;++k)
                        j[active.index(Tet4Ale::node(i),Tet4Ale::component(i))*nd+active.index(Tet4Ale::node(k),Tet4Ale::component(k))]=fj[Tet4Ale::matrix(i,k)];
                });
            }
            if(solid_cell[e]) measured(tangent?log.solid_tangent:log.solid_residual,[&] {
                auto sr=solid_element(solid_geometry[e],{f.young,f.poisson,f.solid_density,solid_dt,f.neo_hookean,mesh_dt},vs,dn,vn,tangent);
                if(!supports.empty())
                    for(std::size_t i=support_offsets[e];i<support_offsets[e+1];++i)
                        support_faces[i].face.evaluate(dn,vs,mesh_dt,&sr,tangent);
                if(active.count==Tet4Vector::components) {
                    std::copy(sr.residual.begin(),sr.residual.end(),r.begin());
                    if(tangent) std::copy(sr.tangent.begin(),sr.tangent.end(),j.begin());
                } else {
                    const auto slot=[&](int i) { return active.index(Tet4Vector::node(i),Layout::structure_offset+Tet4Vector::component(i)); };
                    for(int i=0;i<Tet4Vector::dofs;++i) r[slot(i)]=sr.residual[i];
                    if(tangent) for(int i=0;i<Tet4Vector::dofs;++i) for(int k=0;k<Tet4Vector::dofs;++k)
                        j[slot(i)*nd+slot(k)]=sr.tangent[Tet4Vector::matrix(i,k)];
                }
            });
        };
        const auto assemble=[&](const std::vector<double>& x,Vec r,Mat j) {
            const auto full=expand(x);
            std::vector<double> residual,tangent;
            typename Layout::template State<double> chain;
            typename Layout::template State<PetscInt> rows,cols;
            for(std::size_t e=0;e<data.size();++e) {
                const auto active=fsi_cell_components(nc,dual?&domains:nullptr,mesh.cells[e].physical_tag);
                const int nd=active.dofs();
                for(int a=0;a<Tet4Topology::nodes;++a) for(int c=active.first;c<active.first+active.count;++c) {
                    const auto mapping=reduced.slot(Layout::dof(mesh.cells[e].nodes[a],c),mesh_dt);
                    const int slot=active.index(a,c);
                    rows[slot]=mapping.test_row; cols[slot]=mapping.column; chain[slot]=mapping.trial_weight;
                }
                local_residual(e,full,j!=nullptr,active,residual,tangent,events);
                measured(events.insert,[&] {
                    EONSIM_PETSC(VecSetValues(r,nd,rows.data(),residual.data(),ADD_VALUES));
                    if(j) {
                        for(int row=0;row<nd;++row) for(int col=0;col<nd;++col) tangent[nd*row+col]*=chain[col];
                        EONSIM_PETSC(MatSetValues(j,nd,rows.data(),nd,cols.data(),tangent.data(),ADD_VALUES));
                    }
                });
            }
            for(std::size_t i=0;i<outlets.size();++i) {
                const auto& port=reduced.outlets[i];
                assemble_outlet(reduced,port,outlet_stages[i],x[port.local],full,mesh.rank==mesh.ranks-1,r,j);
            }
            if(!Elastic && mesh.rank==mesh.ranks-1) {
                const double v=x[reduced.body_local];
                const double rbody=rigid_residual({f.mass,f.damping,f.stiffness},reference_body,solid_dt,v,0,mesh_dt);
                EONSIM_PETSC(VecSetValue(r,reduced.body,rbody,ADD_VALUES));
                if(j) EONSIM_PETSC(MatSetValue(j,reduced.body,reduced.body,f.mass/solid_dt+f.damping+mesh_dt*f.stiffness,ADD_VALUES));
            }
        };
        const auto solved=system.solve(config.solver,accepted,{}, {},assemble);
        const auto next=expand(solved.values);
        double local[4]{},global[4]{};
        measured(events.force_replay,[&] {
            for(std::size_t e=0;e<data.size();++e) {
                std::vector<double> r,j;
                local_residual(e,next,false,{0,nc},r,j,unmeasured);
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
        });
        for(const auto& port:reduced.outlets) for(const auto& [slot,weight]:port.flux_weights) {
            if(!interface[slot/nc]) continue;
            const double force=weight*solved.values[port.local];
            if(slot%nc==0) local[0]-=force;
            local[2]-=force*next[slot];
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
        std::vector<double> outlet_flow(2*outlets.size());
        std::vector<OutletObservation> port_values;
        auto next_outlet_state=outlet_state;
        for(std::size_t i=0;i<outlets.size();++i) {
            const auto& port=reduced.outlets[i];
            const auto& state=outlet_state[i];
            const double pb=solved.values[port.local];
            const double pc=outlet_stages[i].capacitor_pressure(pb);
            const double stage_rate=outlet_stages[i].capacitor_rate(pb);
            const double rate=alpha_step?state.rate+(stage_rate-state.rate)/fluid_map.p.alpha_m:stage_rate;
            const double endpoint=alpha_step?std::fma(dt,(1-fluid_map.p.gamma)*state.rate+fluid_map.p.gamma*rate,state.capacitor):pc;
            next_outlet_state[i]={endpoint,state.capacitor,rate};
            port_values.push_back({pb,next_reduced[port.local],pc,stage_rate});
            if(f.output_interval>0) for(const auto& [slot,weight]:port.flux_weights) {
                outlet_flow[2*i]+=weight*next[slot];
                outlet_flow[2*i+1]+=weight*next_physical[slot];
            }
        }
        if(!outlets.empty()&&f.output_interval>0)
            MPI_Allreduce(MPI_IN_PLACE,outlet_flow.data(),static_cast<int>(outlet_flow.size()),MPI_DOUBLE,MPI_SUM,comm);
        if(f.inlet_flow) {stage_mass=mass_observation(next); endpoint_mass=mass_observation(next_physical); old_mass=mass_observation(physical);}
        std::array<double,5> support_history{};
        if(!supports.empty()&&f.output_interval>0) {
            std::array<double,5> local_work{};
            for(const auto& face:support_faces) {
                const auto stage=observe_wall_support<Layout>(mesh,face,reference_d,next,mesh_dt);
                const auto old=observe_wall_support<Layout>(mesh,face,solid_d,physical,0);
                const auto end=observe_wall_support<Layout>(mesh,face,next_solid,next_physical,0);
                local_work[0]+=stage.spring_energy;
                local_work[1]+=stage.dissipation;
                local_work[2]+=stage.power_on_wall;
                local_work[3]+=end.spring_energy;
                local_work[4]+=old.spring_energy-end.spring_energy-dt*stage.dissipation;
            }
            MPI_Allreduce(local_work.data(),support_history.data(),5,MPI_DOUBLE,MPI_SUM,comm);
            for(double value:support_history) if(!std::isfinite(value))
                throw std::runtime_error("Nonfinite FSI wall support history");
        }
        const double body_power=Elastic?global[3]:(result.balance+result.fluid_force)*solved.values[reduced.body_local];
        if(bdf2) { physical_history.commit(physical,dt); displacement_history.commit(solid_d,dt); body_history.commit({body.position,body.velocity},dt); }
        accepted=std::move(next_reduced); physical=std::move(next_physical); solid_d=std::move(next_solid); body=next_body;
        outlet_state=std::move(next_outlet_state);
        if(alpha) {
            fluid_rate=std::move(next_fluid_rate); mesh_velocity=std::move(next_mesh_velocity); mesh_acceleration=std::move(next_mesh_acceleration);
            solid_acceleration=std::move(next_solid_acceleration); body_acceleration=next_body_acceleration; alpha_ready=true;
        }
        clock.accept();
        if(bdf2&&clock.at_event()) physical_history.previous_dt=displacement_history.previous_dt=body_history.previous_dt=0;
        if(alpha&&clock.at_event()) alpha_ready=false;
        if(!config.checkpoint.empty()&&(step%f.checkpoint_interval==0||!clock.active(config.stop_after))) {
            Checkpoint saved{step,{{"reduced",accepted},{"physical",physical},{"solid_displacement",solid_d},{"rigid",{body.position,body.velocity}}},clock.time,clock.next_dt};
            if(!outlets.empty()) {
                auto& values=saved.fields["rcr_capacitor"];
                for(const auto& state:outlet_state) values.insert(values.end(),{state.capacitor,state.previous,state.rate});
            }
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
        const double applied=outlets.size()==1&&pressure_tags.size()==1?port_values.front().stage_pressure:pressure;
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
                history<<step<<','<<time<<','<<dt<<','<<evaluation_time<<','<<applied<<','<<result.position<<','<<result.velocity<<','
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
                if(!supports.empty()) for(double value:support_history) history<<','<<value;
                for(std::size_t i=0;i<outlets.size();++i) {
                    const auto& v=port_values[i];
                    history<<','<<outlets[i].tag<<','<<outlet_flow[2*i]<<','<<v.stage_pressure<<','<<v.stage_capacitor
                           <<','<<v.stage_rate<<','<<outlet_flow[2*i+1]<<','<<v.endpoint_pressure<<','<<outlet_state[i].capacitor;
                }
                history<<'\n';
                history.flush();
            });
        }
        if(f.pressure_face_history) {
            std::vector<std::array<double,2>> loads(pressure_tags.size(),{pressure,fsi_pressure(f,time)});
            for(std::size_t i=0;i<pressure_tags.size();++i) {
                const auto found=outlet_by_tag.find(pressure_tags[i]);
                if(found==outlet_by_tag.end()) continue;
                const auto& port=port_values[found->second];
                loads[i]={port.stage_pressure,port.endpoint_pressure};
            }
            write_pressure_faces<Layout>(comm,mesh,pressure_tags,pressure_faces,next,physical,alpha_step,f.viscosity,
                step,time,dt,evaluation_time,loads,pressure_history);
        }
        const std::string stage=alpha?"stage_":"";
        if(mesh.rank==0) std::cout << std::setprecision(17) << "fsi_step=" << step << " time=" << time << " accepted_dt=" << dt << " evaluation_time=" << evaluation_time << " applied_pressure=" << applied
            << " position=" << result.position << " velocity=" << result.velocity << " " << stage << "fluid_force=" << result.fluid_force
            << " " << stage << "body_balance=" << result.balance << " snes_iterations=" << solved.iterations
            << " " << stage << "interface_power=" << global[2] << " " << stage << "body_power=" << body_power << " " << stage << "power_balance=" << body_power-global[2]
            << " area_displacement_x=" << surface[2] << " area_displacement_y=" << surface[3]
            << " endpoint_min_fluid_j=" << min_quality[2] << " endpoint_min_solid_j=" << min_quality[3]
            << " residual=" << solved.residual_norm << " time_order=" << (alpha_step?2:derivative.order) << '\n';
        } catch(const StepRejected& error) {
            clock.reject(error.what());
            if(mesh.rank==0) std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << '\n';
        }
    }
    if(f.output_interval>0||f.pressure_face_history) output_stage(comm,"history close",[&] {
        if(history.is_open()) history.close();
        if(pressure_history.is_open()) pressure_history.close();
    });
    output_stage(comm,"final snapshot",snapshot);
    return result;
}
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config)
{
    return config.fsi.elastic?solve_fsi_impl<true>(comm,mesh,config):solve_fsi_impl<false>(comm,mesh,config);
}
}
