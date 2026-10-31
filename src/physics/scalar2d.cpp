#include "eonsim/scalar2d.hpp"
#include "eonsim/element2d.hpp"
#include "eonsim/quadrature.hpp"
#include "eonsim/field_layout.hpp"
#include "eonsim/linear_system.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/checkpoint.hpp"
#include "eonsim/vtu.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <set>
namespace eonsim {
namespace {
double value(const ScalarFunction& f,const Point& x,double t) {
    const auto& c=f.polynomial;
    const double v=(c[0]+c[1]*x[0]+c[2]*x[1]+c[3]*x[0]*x[0]+c[4]*x[0]*x[1]+c[5]*x[1]*x[1])*std::exp(f.rate*t);
    if(!std::isfinite(v))throw std::runtime_error("Non-finite scalar function");
    return v;
}
struct Exact { double u=0,laplace=0; std::array<double,2> gradient{}; };
Exact exact(const Scalar2DConfig& c,const Point& x,double t) {
    Exact e; const double factor=std::exp(c.manufactured_rate*t);
    if(c.manufactured=="sine") {
        const double pi=std::acos(-1.);
        e.u=std::sin(pi*x[0])*std::sin(pi*x[1]); e.laplace=-2*pi*pi*e.u;
        e.gradient={pi*std::cos(pi*x[0])*std::sin(pi*x[1]),pi*std::sin(pi*x[0])*std::cos(pi*x[1])};
    } else {
        e.u=1+x[0]+2*x[1]; e.gradient={1,2};
        if(c.manufactured=="quadratic") { e.u+=x[0]*x[0]+2*x[1]*x[1];e.gradient[0]+=2*x[0];e.gradient[1]+=4*x[1];e.laplace=6; }
    }
    e.u*=factor;e.laplace*=factor;for(auto& g:e.gradient)g*=factor;
    return e;
}
int tag(const MeshPartition& m,const std::string& name,int dim) {
    if(!name.empty()&&name.find_first_not_of("0123456789")==std::string::npos) {
        const auto n=std::stoll(name);if(n>0&&n<=std::numeric_limits<int>::max())return static_cast<int>(n);
    }
    int found=0;
    for(const auto& p:m.physical_names)if(p.first.first==dim&&p.second==name) {
        if(found)throw std::runtime_error("Ambiguous physical name: "+name);
        found=p.first.second;
    }
    if(!found)throw std::runtime_error("Unknown physical region: "+name);
    return found;
}
struct Quadrature { Point2DMapping map;double weight; };
struct CellData { std::vector<Quadrature> points; std::array<Point,4> xyz{};double k; };
double boundary_value(const Scalar2DConfig& c,const ScalarBoundary& b,const Point& x,
                      const std::array<double,2>& normal,double k,double t) {
    if(c.manufactured.empty())return value(b.value,x,t);
    const auto e=exact(c,x,t);
    if(b.type==ScalarBoundary::Type::dirichlet)return e.u;
    return k*(e.gradient[0]*normal[0]+e.gradient[1]*normal[1])+b.robin_coefficient*e.u;
}
}
void solve_scalar2d(MPI_Comm comm,const MeshPartition& mesh,const Config& config) {
    if(mesh.topological_dimension!=2)throw std::runtime_error("scalar2d requires a two-dimensional partition");
    const auto& c=config.scalar2d;
    std::map<int,ScalarBoundary> boundaries;
    for(const auto& b:c.boundaries)if(!boundaries.emplace(tag(mesh,b.region,1),b).second)throw std::runtime_error("Duplicate scalar boundary tag/name");
    std::map<int,double> materials;
    for(const auto& p:c.regions)if(!materials.emplace(tag(mesh,p.first,2),p.second).second)throw std::runtime_error("Duplicate scalar material tag/name");
    // Every requested region must exist globally; empty local regions are valid.
    for(const auto& p:boundaries) {
        int local=0,global=0;for(const auto& e:mesh.edges)if(e.physical_tag==p.first)local=1;
        MPI_Allreduce(&local,&global,1,MPI_INT,MPI_MAX,comm);if(!global)throw std::runtime_error("Scalar boundary tag absent from mesh");
    }
    for(const auto& p:materials) {
        int local=0,global=0;for(const auto& e:mesh.cells2)if(e.physical_tag==p.first)local=1;
        MPI_Allreduce(&local,&global,1,MPI_INT,MPI_MAX,comm);if(!global)throw std::runtime_error("Scalar material tag absent from mesh");
    }
    std::vector<CellData> geometry;
    std::map<std::array<LocalId,2>,std::pair<std::size_t,int>> edge_cell;
    for(std::size_t ci=0;ci<mesh.cells2.size();++ci) {
        const auto& cell=mesh.cells2[ci]; CellData data;
        data.k=materials.count(cell.physical_tag)?materials.at(cell.physical_tag):c.diffusivity;
        for(int a=0;a<cell.vertices;++a)data.xyz[a]=mesh.nodes[cell.nodes[a]].position;
        validate2d(data.xyz,cell.vertices);
        for(int i=0;i<4;++i)for(int j=0;j<4;++j) {
            double r=GaussLegendre<4>::points[i],s=GaussLegendre<4>::points[j];
            double w=GaussLegendre<4>::weights[i]*GaussLegendre<4>::weights[j];
            if(cell.vertices==3) { w*=1-r;s*=1-r; }
            auto q=map2d(data.xyz,cell.vertices,r,s);data.points.push_back({q,w*q.determinant});
        }
        for(int a=0;a<cell.vertices;++a) {
            std::array<LocalId,2> e{cell.nodes[a],cell.nodes[(a+1)%cell.vertices]};std::sort(e.begin(),e.end());edge_cell[e]={ci,a};
        }
        geometry.push_back(std::move(data));
    }
    for(const auto& e:mesh.edges)if(!boundaries.count(e.physical_tag))throw std::runtime_error("Every scalar exterior edge requires a boundary condition");
    bool anchored=false;for(const auto& p:boundaries)anchored|=p.second.type!=ScalarBoundary::Type::neumann;
    const bool nullspace=!c.transient&&!anchored;
    const auto layout=make_field_layout(mesh,1,{{"scalar",{0}}},{{DofDomain::scalar,DofQuantity::scalar_value,0,2}});
    std::vector<double> accepted(mesh.nodes.size()),rate(mesh.nodes.size());
    for(std::size_t n=0;n<accepted.size();++n)accepted[n]=c.manufactured.empty()?value(c.initial,mesh.nodes[n].position,0):exact(c,mesh.nodes[n].position,0).u;
    const bool bdf=config.time_integration.scheme==TimeScheme::bdf2,alpha=config.time_integration.scheme==TimeScheme::generalized_alpha;
    bool ready=false;TimeHistory history(accepted.size());TimeStepper clock(c.dt,c.steps,config.time_control);
    std::vector<double> signature_values{double(c.transient),c.diffusivity,c.capacity,c.dt,double(config.time_integration.scheme),config.time_integration.rho_infinity,c.manufactured_rate};
    auto append_function=[&](const ScalarFunction& f) { signature_values.insert(signature_values.end(),f.polynomial.begin(),f.polynomial.end());signature_values.push_back(f.rate); };
    append_function(c.source);append_function(c.initial);
    for(const auto& p:boundaries) {signature_values.insert(signature_values.end(),{double(p.first),double(p.second.type),p.second.robin_coefficient});append_function(p.second.value);}
    for(const auto& p:materials)signature_values.insert(signature_values.end(),{double(p.first),p.second});
    signature_values.push_back(config.time_control.events.size());signature_values.insert(signature_values.end(),config.time_control.events.begin(),config.time_control.events.end());
    signature_values.push_back(config.time_control.step_sizes.size());signature_values.insert(signature_values.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    const auto signature=state_signature(mesh,"scalar2d-"+c.manufactured,signature_values);
    if(!config.restart.empty()) {
        std::map<std::string,std::size_t> sizes{{"scalar",accepted.size()}};
        if(bdf)sizes.insert({{"previous",accepted.size()},{"time_metadata",1}});
        if(alpha)sizes.insert({{"rate",rate.size()},{"time_metadata",1}});
        const auto saved=read_checkpoint(config.restart,mesh,signature,sizes);accepted=saved.fields.at("scalar");clock.restore(saved.step,saved.time,saved.next_dt);
        if(bdf) {history.previous=saved.fields.at("previous");history.previous_dt=saved.fields.at("time_metadata")[0];if(history.previous_dt<0||history.previous_dt>saved.time||(history.previous_dt==0&&!clock.at_event()))throw std::runtime_error("Invalid scalar BDF2 history");}
        if(alpha) {rate=saved.fields.at("rate");const double r=saved.fields.at("time_metadata")[0];if((r!=0&&r!=1)||(r==0&&!clock.at_event()))throw std::runtime_error("Invalid scalar alpha history");ready=r==1;}
    }
    std::vector<std::pair<double,std::string>> series;
    auto series_path=config.output;
    if(!config.restart.empty())series_path=config.output.parent_path()/(config.output.stem().string()+"_restart"+std::to_string(clock.step)+".pvd");
    else series_path.replace_extension(".pvd");
    bool steady_done=false;
    while(c.transient?clock.active(config.stop_after):!steady_done) {
        if(bdf&&history.previous_dt>0)clock.next_dt=std::min(clock.next_dt,2*history.previous_dt);
        const double h=clock.dt(),end=c.transient?clock.time+h:0;
        const bool stage=alpha&&ready&&c.transient;
        const AlphaStep alpha_map(h,config.time_integration.rho_infinity,false);
        const auto derivative=time_derivative(bdf?TimeScheme::bdf2:TimeScheme::backward_euler,h,history.previous_dt);
        const double af=stage?alpha_map.p.alpha_f:1,q=stage?alpha_map.effective_dt():derivative.effective_dt,t=clock.time+af*h;
        auto reference=bdf?history.reference(accepted,derivative):accepted;
        if(stage)for(std::size_t i=0;i<reference.size();++i)reference[i]=alpha_map.reference(accepted[i],rate[i]);
        try {
            LinearSystem system(comm,layout);
            for(std::size_t ci=0;ci<mesh.cells2.size();++ci) {
                const auto& cell=mesh.cells2[ci];const int n=cell.vertices;std::array<double,16> a{};std::array<double,4> b{};std::array<PetscInt,4> ids{};
                for(int i=0;i<n;++i)ids[i]=layout.local_to_global[cell.nodes[i]];
                for(const auto& point:geometry[ci].points) {
                    const auto& m=point.map;const double k=geometry[ci].k;
                    const auto e=exact(c,m.position,c.transient?t:0);
                    double source=c.manufactured.empty()?value(c.source,m.position,c.transient?t:0):((c.transient?c.capacity*c.manufactured_rate*e.u:0)-k*e.laplace);
                    if(c.transient)for(int j=0;j<n;++j)source+=c.capacity/q*m.shape[j]*reference[cell.nodes[j]];
                    for(int i=0;i<n;++i) {
                        b[i]+=point.weight*m.shape[i]*source;
                        for(int j=i;j<n;++j) {
                            const double entry=point.weight*(k*(m.gradient[i][0]*m.gradient[j][0]+m.gradient[i][1]*m.gradient[j][1])+(c.transient?c.capacity/q*(m.shape[i]*m.shape[j]):0));
                            a[n*i+j]+=entry;if(i!=j)a[n*j+i]+=entry;
                        }
                    }
                }
                system.add(n,ids.data(),a.data(),b.data());
            }
            for(const auto& edge:mesh.edges) {
                const auto& bc=boundaries.at(edge.physical_tag);if(bc.type==ScalarBoundary::Type::dirichlet)continue;
                const auto& x=mesh.nodes[edge.nodes[0]].position;const auto& y=mesh.nodes[edge.nodes[1]].position;
                const double length=std::hypot(y[0]-x[0],y[1]-x[1]);const std::array<double,2> normal{(y[1]-x[1])/length,(x[0]-y[0])/length};
                auto key=edge.nodes;std::sort(key.begin(),key.end());const double k=geometry.at(edge_cell.at(key).first).k;
                std::array<double,4> a{};std::array<double,2> b{};const std::array<PetscInt,2> ids{layout.local_to_global[edge.nodes[0]],layout.local_to_global[edge.nodes[1]]};
                for(int j=0;j<4;++j) {
                    const double s=GaussLegendre<4>::points[j],weight=length*GaussLegendre<4>::weights[j];const std::array<double,2> shape{1-s,s};Point point{};
                    for(int d=0;d<3;++d)point[d]=(1-s)*x[d]+s*y[d];
                    const double g=boundary_value(c,bc,point,normal,k,c.transient?t:0);
                    for(int i=0;i<2;++i) {b[i]+=weight*shape[i]*g;for(int l=0;l<2;++l)a[2*i+l]+=weight*bc.robin_coefficient*shape[i]*shape[l];}
                }
                system.add(2,ids.data(),a.data(),b.data());
            }
            std::vector<PetscInt> constraints;std::vector<double> values;
            for(std::size_t i=0;i<mesh.owned_nodes;++i) {
                bool prescribed=false;double g=0;
                for(int boundary:mesh.node_boundary_tags[i]) {
                    const auto& bc=boundaries.at(boundary);if(bc.type!=ScalarBoundary::Type::dirichlet)continue;
                    double next=boundary_value(c,bc,mesh.nodes[i].position,{},0,end);
                    if(prescribed&&std::abs(g-next)>1e-12*std::max({1.,std::abs(g),std::abs(next)}))throw std::runtime_error("Conflicting Dirichlet corner values");
                    prescribed=true;g=next;
                }
                if(prescribed) {constraints.push_back(layout.local_to_global[i]);values.push_back(stage?(1-af)*accepted[i]+af*g:g);}
            }
            system.constrain(constraints,values);
            if(nullspace)system.constant_nullspace(1e-11);
            auto solved=system.solve(config.solver,true);
            auto next=solved.values,next_rate=rate;
            if(alpha&&c.transient)for(std::size_t i=0;i<next.size();++i) {
                next_rate[i]=stage?alpha_map.endpoint_rate(accepted[i],rate[i],next[i]):(next[i]-accepted[i])/h;
                if(stage)next[i]=alpha_map.endpoint(accepted[i],next[i]);
            }
            double mean=0,exact_mean=0,area=0;
            for(std::size_t ci=0;ci<geometry.size();++ci)for(const auto& p:geometry[ci].points) {
                area+=p.weight;exact_mean+=p.weight*exact(c,p.map.position,end).u;
                for(int i=0;i<mesh.cells2[ci].vertices;++i)mean+=p.weight*p.map.shape[i]*next[mesh.cells2[ci].nodes[i]];
            }
            double local[3]{area,mean,exact_mean},global[3]{};MPI_Allreduce(local,global,3,MPI_DOUBLE,MPI_SUM,comm);
            if(!(global[0]>0))throw std::runtime_error("Empty scalar domain");
            if(nullspace)for(auto& u:next)u-=global[1]/global[0];
            const double exact_shift=nullspace?global[2]/global[0]:0;
            double norms[2]{},all_norms[2]{};
            for(std::size_t ci=0;ci<geometry.size();++ci)for(const auto& p:geometry[ci].points) {
                const auto e=exact(c,p.map.position,end);double u=0,gx=0,gy=0;
                for(int i=0;i<mesh.cells2[ci].vertices;++i) {const double v=next[mesh.cells2[ci].nodes[i]];u+=p.map.shape[i]*v;gx+=p.map.gradient[i][0]*v;gy+=p.map.gradient[i][1]*v;}
                norms[0]+=p.weight*std::pow(u-e.u+exact_shift,2);norms[1]+=p.weight*(std::pow(gx-e.gradient[0],2)+std::pow(gy-e.gradient[1],2));
            }
            MPI_Allreduce(norms,all_norms,2,MPI_DOUBLE,MPI_SUM,comm);
            // Independently integrate the FE boundary gradient, rather than
            // calling the assembled residual sum a flux-conservation oracle.
            double balance[3]{},all_balance[3]{};
            for(std::size_t ci=0;ci<geometry.size();++ci)for(const auto& p:geometry[ci].points) {
                const auto e=exact(c,p.map.position,c.transient?t:0);
                balance[1]+=p.weight*(c.manufactured.empty()?value(c.source,p.map.position,c.transient?t:0):((c.transient?c.capacity*c.manufactured_rate*e.u:0)-geometry[ci].k*e.laplace));
                if(c.transient)for(int i=0;i<mesh.cells2[ci].vertices;++i) {
                    const auto node=mesh.cells2[ci].nodes[i];
                    balance[0]+=p.weight*c.capacity*p.map.shape[i]*(solved.values[node]-reference[node])/q;
                }
            }
            for(const auto& edge:mesh.edges) {
                auto key=edge.nodes;std::sort(key.begin(),key.end());const auto adjacent=edge_cell.at(key);
                const auto& cell=mesh.cells2[adjacent.first];const auto& data=geometry[adjacent.first];
                const auto& x=mesh.nodes[edge.nodes[0]].position;const auto& y=mesh.nodes[edge.nodes[1]].position;
                const std::array<std::array<double,2>,4> vertices=cell.vertices==3?
                    std::array<std::array<double,2>,4>{{{0,0},{1,0},{0,1},{0,0}}}:
                    std::array<std::array<double,2>,4>{{{0,0},{1,0},{1,1},{0,1}}};
                const auto a=vertices[adjacent.second],b=vertices[(adjacent.second+1)%cell.vertices];
                for(int j=0;j<4;++j) {
                    const double s=GaussLegendre<4>::points[j];const auto m=map2d(data.xyz,cell.vertices,(1-s)*a[0]+s*b[0],(1-s)*a[1]+s*b[1]);
                    for(int i=0;i<cell.vertices;++i)balance[2]+=GaussLegendre<4>::weights[j]*data.k*solved.values[cell.nodes[i]]*(m.gradient[i][0]*(y[1]-x[1])-m.gradient[i][1]*(y[0]-x[0]));
                }
            }
            MPI_Allreduce(balance,all_balance,3,MPI_DOUBLE,MPI_SUM,comm);
            if(c.transient) {if(bdf)history.commit(accepted,h);accepted=std::move(next);rate=std::move(next_rate);ready=true;clock.accept();if(clock.at_event()){history.previous_dt=0;ready=false;}}
            else {accepted=std::move(next);steady_done=true;}
            if(!config.checkpoint.empty()) {
                Checkpoint saved{clock.step,{{"scalar",accepted}},clock.time,clock.next_dt};
                if(bdf){saved.fields["previous"]=history.previous;saved.fields["time_metadata"]={history.previous_dt};}
                if(alpha){saved.fields["rate"]=rate;saved.fields["time_metadata"]={ready?1.:0.};}
                write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
            }
            std::vector<PointField> fields{{"u",1,accepted}};
            if(!c.manufactured.empty()) {std::vector<double> oracle(accepted.size());for(std::size_t i=0;i<oracle.size();++i)oracle[i]=exact(c,mesh.nodes[i].position,end).u-exact_shift;fields.push_back({"u_exact",1,std::move(oracle)});}
            if(alpha)fields.push_back({"algorithmic_rate",1,rate});
            write_fields(config.output,mesh,fields);MPI_Barrier(comm);if(mesh.rank==0)write_field_index(config.output,mesh.ranks,fields);
            if(c.transient) {
                const auto path=config.output.parent_path()/(series_path.stem().string()+"_step"+std::to_string(clock.step)+".vtu");
                write_fields(path,mesh,fields);MPI_Barrier(comm);
                if(mesh.rank==0) {
                    write_field_index(path,mesh.ranks,fields);auto index=path; if(mesh.ranks>1)index.replace_extension(".pvtu");series.push_back({clock.time,index.filename().string()});
                    std::ofstream out(series_path);out.exceptions(std::ios::badbit|std::ios::failbit);
                    out << std::setprecision(17) << "<VTKFile type=\"Collection\" version=\"0.1\"><Collection>\n";
                    for(const auto& item:series)out << "<DataSet timestep=\"" << item.first << "\" group=\"\" part=\"0\" file=\"" << item.second << "\"/>\n";
                    out << "</Collection></VTKFile>\n";out.close();
                }
            }
            if(mesh.rank==0) {
                std::cout << std::setprecision(17) << "scalar_step=" << clock.step << " time=" << end << " accepted_dt=" << (c.transient?h:0) << " evaluation_time=" << (c.transient?t:0) << " time_order=" << (stage?2:derivative.order)
                          << " area=" << global[0] << " integral=" << (nullspace?0:global[1]) << " true_residual=" << solved.true_residual
                          << " stage_rate_integral=" << all_balance[0] << " stage_source_integral=" << all_balance[1] << " stage_boundary_flux=" << all_balance[2]
                          << " stage_flux_balance=" << all_balance[0]-all_balance[1]-all_balance[2];
                if(!c.manufactured.empty())std::cout << " l2_error=" << std::sqrt(all_norms[0]) << " h1_error=" << std::sqrt(all_norms[1]);
                std::cout << '\n';
            }
        } catch(const LinearSolveFailure& error) {
            if(!c.transient)throw;
            clock.reject(error.what());
            if(mesh.rank==0)std::cout << "step_retry=" << clock.retries << " time=" << clock.time << " next_dt=" << clock.next_dt << " reason=" << error.what() << '\n';
        }
    }
    if(mesh.rank==0)std::cout << "status=success\n";
}
}
