#include "eonsim/scalar_p2_space.hpp"
#include "eonsim/scalar2d.hpp"
#include "eonsim/tri_p2.hpp"
#include "eonsim/element2d.hpp"
#include "eonsim/quadrature.hpp"
#include "eonsim/linear_system.hpp"
#include "eonsim/time_integration.hpp"
#include "eonsim/time_step.hpp"
#include "eonsim/checkpoint.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <algorithm>
#include <set>
namespace eonsim {
namespace {
struct ExactP2 {double u,dx,dy,lap;};
ExactP2 spatial_exact_p2(const std::string& kind,const Point& x) {
    if(kind=="sine") {const double p=std::acos(-1.),u=std::sin(p*x[0])*std::sin(p*x[1]);return {u,p*std::cos(p*x[0])*std::sin(p*x[1]),p*std::sin(p*x[0])*std::cos(p*x[1]),-2*p*p*u};}
    if(kind=="quadratic")return {1+x[0]+2*x[1]+x[0]*x[0]+2*x[1]*x[1],1+2*x[0],2+4*x[1],6};
    return {1+x[0]+2*x[1],1,2,0};
}
ExactP2 exact_p2(const Scalar2DConfig& c,const Point& x,double time) {
    auto e=spatial_exact_p2(c.manufactured,x);
    const double factor=std::exp(c.manufactured_rate*time);
    e.u*=factor;e.dx*=factor;e.dy*=factor;e.lap*=factor;
    if(!std::isfinite(e.u+e.dx+e.dy+e.lap))throw std::runtime_error("Non-finite P2 manufactured data");
    return e;
}
double evaluate(const ScalarFunction& f,const Point& x,double time) {
    const auto& c=f.polynomial;const double v=(c[0]+c[1]*x[0]+c[2]*x[1]+c[3]*x[0]*x[0]+c[4]*x[0]*x[1]+c[5]*x[1]*x[1])*std::exp(f.rate*time);
    if(!std::isfinite(v))throw std::runtime_error("Non-finite P2 input function");
    return v;
}
int boundary_tag(const MeshPartition& mesh,const std::string& name) {
    if(!name.empty()&&name.find_first_not_of("0123456789")==std::string::npos){auto n=std::stoll(name);if(n>0&&n<=std::numeric_limits<int>::max())return static_cast<int>(n);}
    int found=0;for(const auto& p:mesh.physical_names)if(p.first.first==1&&p.second==name){if(found)throw std::runtime_error("Ambiguous P2 boundary");found=p.first.second;}
    if(!found)throw std::runtime_error("Unknown P2 boundary");
    return found;
}
struct P2Point {Point x;double weight;TriP2Tabulation basis;};
std::vector<P2Point> quadrature(const MeshPartition& mesh,const Cell2D& cell) {
    if(cell.vertices!=3)throw std::runtime_error("P2 requires pure Tri3 geometry");
    std::array<Point,4> x{};for(int a=0;a<3;++a)x[a]=mesh.nodes.at(cell.nodes[a]).position;
    std::vector<P2Point> points;
    for(int i=0;i<4;++i)for(int j=0;j<4;++j){const double r=GaussLegendre<4>::points[i],s=(1-r)*GaussLegendre<4>::points[j];
        const auto map=map2d(x,3,r,s);auto basis=tabulate_tri_p2(r,s);
        for(auto& g:basis.gradient){const double dr=g[0],ds=g[1];g={dr*map.gradient[1][0]+ds*map.gradient[2][0],dr*map.gradient[1][1]+ds*map.gradient[2][1]};}
        points.push_back({map.position,GaussLegendre<4>::weights[i]*GaussLegendre<4>::weights[j]*(1-r)*map.determinant,basis});
    }return points;
}
// Only local work belongs in this stage. All ranks reach the same reduction
// before any following collective, including after a local read/write failure.
template<class Work> void local_stage(MPI_Comm comm,const char* phase,const Work& work) {
    int rank;MPI_Comm_rank(comm,&rank);
    std::string error;
    try {work();}catch(const std::exception& e){error=e.what();}
    int failed=error.empty()?std::numeric_limits<int>::max():rank,first;
    MPI_Allreduce(&failed,&first,1,MPI_INT,MPI_MIN,comm);
    if(first==std::numeric_limits<int>::max())return;
    int length=static_cast<int>(error.size());MPI_Bcast(&length,1,MPI_INT,first,comm);
    error.resize(length);MPI_Bcast(error.data(),length,MPI_CHAR,first,comm);
    throw std::runtime_error(std::string("P2 ")+phase+" failed on rank "+std::to_string(first)+": "+error);
}
std::string xml(const std::string& text) {
    std::string result;
    for(char c:text)switch(c){case '&':result+="&amp;";break;case '<':result+="&lt;";break;
        case '>':result+="&gt;";break;case '\"':result+="&quot;";break;case '\'':result+="&apos;";break;default:result+=c;}
    return result;
}
// Extend the geometry signature with exact integer space identities. Casting
// imported IDs to double would alias distinct IDs above 2^53.
std::uint64_t space_signature(std::uint64_t hash,const ScalarP2Space& s) {
    auto bytes=[&](const void* data,std::size_t count){const auto* p=static_cast<const unsigned char*>(data);
        for(std::size_t i=0;i<count;++i){hash^=p[i];hash*=1099511628211ULL;}};
    bytes(&s.global,sizeof(s.global));bytes(&s.begin,sizeof(s.begin));bytes(&s.owned,sizeof(s.owned));
    for(const auto& e:s.entities)bytes(e.data(),sizeof(GlobalId)*e.size());
    for(const auto& p:s.points)bytes(p.data(),sizeof(double)*p.size());
    bytes(s.algebra_ids.data(),sizeof(GlobalId)*s.algebra_ids.size());
    bytes(s.entity_ids.data(),sizeof(GlobalId)*s.entity_ids.size());
    for(const auto& tags:s.boundary_tags){const auto n=tags.size();bytes(&n,sizeof(n));bytes(tags.data(),sizeof(int)*n);}
    bytes(s.owners.data(),sizeof(int)*s.owners.size());
    for(const auto& c:s.cells)bytes(c.data(),sizeof(LocalId)*c.size());
    for(const auto& b:s.boundaries)bytes(b.data(),sizeof(LocalId)*b.size());
    return hash;
}
void write_p2(MPI_Comm comm,const MeshPartition& mesh,const ScalarP2Space& s,const Config& config,const std::vector<double>& u,const std::vector<double>* rate=nullptr) {
    const std::array<std::string,4> names{"u","entity_first","entity_second","owner"};
    local_stage(comm,"piece write",[&] {
    auto path=config.output;if(mesh.ranks>1)path=path.parent_path()/(path.stem().string()+"_rank"+std::to_string(mesh.rank)+".vtu");
    const auto temporary=path.string()+".tmp";
    std::ofstream out;out.exceptions(std::ios::badbit|std::ios::failbit);out.open(temporary);out<<std::setprecision(17);
    out<<"<VTKFile type=\"UnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\"><UnstructuredGrid><Piece NumberOfPoints=\""<<s.points.size()<<"\" NumberOfCells=\""<<s.cells.size()<<"\"><Points><DataArray type=\"Float64\" NumberOfComponents=\"3\" format=\"ascii\">\n";
    for(const auto& p:s.points)out<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';
    out<<"</DataArray></Points><Cells><DataArray type=\"Int64\" Name=\"connectivity\" format=\"ascii\">\n";
    for(const auto& c:s.cells){for(auto d:c)out<<d<<' ';out<<'\n';}
    out<<"</DataArray><DataArray type=\"Int64\" Name=\"offsets\" format=\"ascii\">\n";for(std::size_t i=1;i<=s.cells.size();++i)out<<6*i<<' ';
    out<<"</DataArray><DataArray type=\"UInt8\" Name=\"types\" format=\"ascii\">\n";for(std::size_t i=0;i<s.cells.size();++i)out<<"22 ";out<<"</DataArray></Cells><PointData>\n";
    for(int k=0;k<4;++k){out<<"<DataArray type=\""<<(k==0?"Float64":"Int64")<<"\" Name=\""<<names[k]<<"\" format=\"ascii\">\n";for(std::size_t i=0;i<u.size();++i){if(k==0)out<<u[i];else if(k<3)out<<s.entities[i][k-1];else out<<s.owners[i];out<<'\n';}out<<"</DataArray>\n";}
    if(rate){out<<"<DataArray type=\"Float64\" Name=\"algorithmic_rate\" format=\"ascii\">\n";
        for(double value:*rate)out<<value<<'\n';
        out<<"</DataArray>\n";}
    out<<"</PointData></Piece></UnstructuredGrid></VTKFile>\n";out.close();std::filesystem::rename(temporary,path);
    });
    local_stage(comm,"index publication",[&] {
    if(mesh.rank==0&&mesh.ranks>1){auto index=config.output;index.replace_extension(".pvtu");std::ofstream p;p.exceptions(std::ios::badbit|std::ios::failbit);p.open(index.string()+".tmp");
        p<<"<VTKFile type=\"PUnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\"><PUnstructuredGrid GhostLevel=\"0\"><PPoints><PDataArray type=\"Float64\" NumberOfComponents=\"3\"/></PPoints><PPointData>";
        for(int k=0;k<4;++k)p<<"<PDataArray type=\""<<(k==0?"Float64":"Int64")<<"\" Name=\""<<names[k]<<"\"/>";
        if(rate)p<<"<PDataArray type=\"Float64\" Name=\"algorithmic_rate\"/>";
        p<<"</PPointData>";for(int r=0;r<mesh.ranks;++r)p<<"<Piece Source=\""<<xml(config.output.stem().string())<<"_rank"<<r<<".vtu\"/>";
        p<<"</PUnstructuredGrid></VTKFile>";p.close();std::filesystem::rename(index.string()+".tmp",index);
    }
    });
}
}
void solve_scalar_p2(MPI_Comm comm,const MeshPartition& mesh,const ScalarP2Space& s,const Config& config) {
    const auto& c=config.scalar2d;
    if(!c.regions.empty()||mesh.topological_dimension!=2)throw std::runtime_error("P2 supports uniform-coefficient Tri3 scalar problems only");
    std::vector<GlobalId> counts(mesh.ranks);const GlobalId owned=s.owned;MPI_Allgather(&owned,1,MPI_INT64_T,counts.data(),1,MPI_INT64_T,comm);
    GlobalId total=0,begin=0;for(int r=0;r<mesh.ranks;++r){if(r==mesh.rank)begin=total;total+=counts[r];}
    if(total!=s.global||begin!=s.begin)throw std::runtime_error("Inconsistent P2 partition counts");
    for(std::size_t i=0;i<s.points.size();++i){GlobalId b=0;for(int r=0;r<s.owners[i];++r)b+=counts[r];if(s.algebra_ids[i]<b||s.algebra_ids[i]>=b+counts[s.owners[i]])throw std::runtime_error("P2 ghost owner mismatch");}
    if(s.global>std::numeric_limits<PetscInt>::max())throw std::runtime_error("P2 exceeds PETSc index range");
    AlgebraLayout layout;layout.global=s.global;layout.owned=s.owned;layout.begin=s.begin;
    for(auto id:s.algebra_ids)layout.local_to_global.push_back(id);
    for(std::size_t i=0;i<s.owned;++i){PetscInt diagonal=0,off=0;for(auto j=s.row_offsets[i];j<s.row_offsets[i+1];++j){auto col=s.row_columns[j];if(col>=s.begin&&col<s.begin+owned)++diagonal;else ++off;}layout.diagonal.push_back(diagonal);layout.off_diagonal.push_back(off);layout.fields["scalar"].push_back(s.algebra_ids[i]);}
    for(std::size_t i=0;i<s.owned;++i)layout.owned_semantics.push_back({s.entity_ids[i],DofDomain::scalar,DofQuantity::scalar_value,s.entities[i][0]==s.entities[i][1]?DofEntity::vertex:DofEntity::edge,0,0,3});
    std::map<int,ScalarBoundary> bc;bool anchored=false;
    for(const auto& b:c.boundaries){anchored|=b.type!=ScalarBoundary::Type::neumann;if(!bc.emplace(boundary_tag(mesh,b.region),b).second)throw std::runtime_error("Duplicate P2 boundary");}
    const bool nullspace=!c.transient&&!anchored;
    for(const auto& b:bc){int found=0,all=0;for(const auto& e:mesh.edges)found|=e.physical_tag==b.first;MPI_Allreduce(&found,&all,1,MPI_INT,MPI_MAX,comm);if(!all)throw std::runtime_error("P2 boundary absent from mesh");}
    std::vector<std::vector<P2Point>> points;
    local_stage(comm,"geometry",[&] {
        for(const auto& e:mesh.edges)if(!bc.count(e.physical_tag))throw std::runtime_error("Missing P2 boundary condition");
        for(const auto& cell:mesh.cells2)points.push_back(quadrature(mesh,cell));
    });
    const bool bdf=config.time_integration.scheme==TimeScheme::bdf2;
    const bool alpha=config.time_integration.scheme==TimeScheme::generalized_alpha;
    std::vector<double> accepted(s.points.size()),rate(s.points.size());
    local_stage(comm,"initial state",[&] {
        for(std::size_t i=0;i<accepted.size();++i)
            accepted[i]=c.manufactured.empty()?evaluate(c.initial,s.points[i],0):exact_p2(c,s.points[i],0).u;
    });
    TimeHistory history(accepted.size());TimeStepper clock(c.dt,c.steps,config.time_control);bool ready=false;
    std::vector<double> parameters{double(c.transient),c.diffusivity,c.capacity,c.dt,
        double(config.time_integration.scheme),config.time_integration.rho_infinity,c.manufactured_rate};
    auto append=[&](const ScalarFunction& f){parameters.insert(parameters.end(),f.polynomial.begin(),f.polynomial.end());parameters.push_back(f.rate);};
    append(c.source);append(c.initial);
    for(const auto& item:bc){parameters.insert(parameters.end(),{double(item.first),double(item.second.type),item.second.robin_coefficient});append(item.second.value);}
    parameters.push_back(config.time_control.events.size());parameters.insert(parameters.end(),config.time_control.events.begin(),config.time_control.events.end());
    parameters.push_back(config.time_control.step_sizes.size());parameters.insert(parameters.end(),config.time_control.step_sizes.begin(),config.time_control.step_sizes.end());
    const auto signature=space_signature(state_signature(mesh,"scalar-p2-v1-"+c.manufactured,parameters),s);
    if(!config.restart.empty()) {
        Checkpoint saved;
        local_stage(comm,"restart",[&] {
            if(!c.transient)throw std::runtime_error("P2 restart requires diffusion");
            std::map<std::string,std::size_t> sizes{{"scalar",accepted.size()}};
            if(bdf)sizes.insert({{"previous",accepted.size()},{"time_metadata",1}});
            if(alpha)sizes.insert({{"rate",accepted.size()},{"time_metadata",1}});
            saved=read_checkpoint(config.restart,mesh,signature,sizes);
            accepted=saved.fields.at("scalar");clock.restore(saved.step,saved.time,saved.next_dt);
            if(bdf){history.previous=saved.fields.at("previous");history.previous_dt=saved.fields.at("time_metadata")[0];
                if(history.previous_dt<0||history.previous_dt>saved.time||(history.previous_dt==0&&!clock.at_event()))throw std::runtime_error("Invalid P2 BDF2 history");}
            if(alpha){rate=saved.fields.at("rate");const double r=saved.fields.at("time_metadata")[0];
                if((r!=0&&r!=1)||(r==0&&!clock.at_event()))throw std::runtime_error("Invalid P2 alpha history");
                ready=r==1;}
        });
        double times[]{double(saved.step),saved.time,saved.next_dt,bdf?history.previous_dt:double(ready)},lo[4],hi[4];
        MPI_Allreduce(times,lo,4,MPI_DOUBLE,MPI_MIN,comm);MPI_Allreduce(times,hi,4,MPI_DOUBLE,MPI_MAX,comm);
        for(int i=0;i<4;++i)if(lo[i]!=hi[i])throw std::runtime_error("Inconsistent P2 restart clock/history across ranks");
    }
    auto series_path=config.output;
    if(!config.restart.empty())series_path=config.output.parent_path()/(config.output.stem().string()+"_restart"+std::to_string(clock.step)+".pvd");
    else series_path.replace_extension(".pvd");
    std::vector<std::pair<double,std::string>> series;
    bool steady_done=false;
    while(c.transient?clock.active(config.stop_after):!steady_done) {
        if(bdf&&history.previous_dt>0)clock.next_dt=std::min(clock.next_dt,2*history.previous_dt);
        const double h=clock.dt(),end=c.transient?clock.time+h:0;
        const bool stage=alpha&&ready&&c.transient;
        const AlphaStep alpha_map(h,config.time_integration.rho_infinity,false);
        const auto derivative=time_derivative(bdf?TimeScheme::bdf2:TimeScheme::backward_euler,h,history.previous_dt);
        const double af=stage?alpha_map.p.alpha_f:1;
        const double effective_dt=stage?alpha_map.effective_dt():derivative.effective_dt;
        const double evaluation_time=c.transient?clock.time+af*h:0;
        auto reference=bdf?history.reference(accepted,derivative):accepted;
        if(stage)for(std::size_t i=0;i<reference.size();++i)reference[i]=alpha_map.reference(accepted[i],rate[i]);
        // Evaluate all local data before entering PETSc insertion/collectives.
        // A rank-local invalid function or corner value cannot strand its peers.
        struct Contribution {int n;std::array<PetscInt,6> ids{};std::array<double,36> matrix{};std::array<double,6> rhs{};};
        std::vector<Contribution> contributions;
        std::vector<PetscInt> fixed;std::vector<double> values;
        local_stage(comm,"assembly data",[&] {
            for(std::size_t ci=0;ci<s.cells.size();++ci) {
                Contribution item{};item.n=6;
                for(int i=0;i<6;++i)item.ids[i]=s.algebra_ids[s.cells[ci][i]];
                for(const auto& q:points[ci]) {
                    const auto e=exact_p2(c,q.x,evaluation_time);
                    double f=c.manufactured.empty()?evaluate(c.source,q.x,evaluation_time):
                        (c.transient?c.capacity*c.manufactured_rate*e.u:0)-c.diffusivity*e.lap;
                    if(c.transient)for(int i=0;i<6;++i)f+=c.capacity/effective_dt*q.basis.value[i]*reference[s.cells[ci][i]];
                    for(int i=0;i<6;++i) {
                        item.rhs[i]+=q.weight*q.basis.value[i]*f;
                        for(int j=i;j<6;++j) {
                            const double v=q.weight*(c.diffusivity*(q.basis.gradient[i][0]*q.basis.gradient[j][0]+q.basis.gradient[i][1]*q.basis.gradient[j][1])+
                                (c.transient?c.capacity/effective_dt*q.basis.value[i]*q.basis.value[j]:0));
                            item.matrix[6*i+j]+=v;if(i!=j)item.matrix[6*j+i]+=v;
                        }
                    }
                }
                contributions.push_back(item);
            }
            for(std::size_t ei=0;ei<mesh.edges.size();++ei) {
                const auto& edge=mesh.edges[ei];const auto& data=bc.at(edge.physical_tag);
                if(data.type==ScalarBoundary::Type::dirichlet)continue;
                const auto& x=mesh.nodes[edge.nodes[0]].position;const auto& y=mesh.nodes[edge.nodes[1]].position;
                const double length=std::hypot(y[0]-x[0],y[1]-x[1]);
                Contribution item{};item.n=3;
                for(int i=0;i<3;++i)item.ids[i]=s.algebra_ids[s.boundaries[ei][i]];
                for(int j=0;j<4;++j) {
                    const double t=GaussLegendre<4>::points[j],w=length*GaussLegendre<4>::weights[j];
                    Point p{};for(int d=0;d<3;++d)p[d]=(1-t)*x[d]+t*y[d];
                    const auto e=exact_p2(c,p,evaluation_time);
                    const double g=c.manufactured.empty()?evaluate(data.value,p,evaluation_time):
                        c.diffusivity*(e.dx*(y[1]-x[1])-e.dy*(y[0]-x[0]))/length+data.robin_coefficient*e.u;
                    const std::array<double,3> shape{(1-t)*(1-2*t),t*(2*t-1),4*t*(1-t)};
                    for(int i=0;i<3;++i){item.rhs[i]+=w*shape[i]*g;
                        for(int k=i;k<3;++k){const double v=w*data.robin_coefficient*shape[i]*shape[k];item.matrix[3*i+k]+=v;if(i!=k)item.matrix[3*k+i]+=v;}}
                }
                contributions.push_back(item);
            }
            for(std::size_t i=0;i<s.owned;++i) {
                bool set=false;double v=0;
                for(int tag:s.boundary_tags[i]) {
                    const auto& b=bc.at(tag);if(b.type!=ScalarBoundary::Type::dirichlet)continue;
                    const double next=c.manufactured.empty()?evaluate(b.value,s.points[i],end):exact_p2(c,s.points[i],end).u;
                    if(set&&std::abs(v-next)>1e-12*std::max({1.,std::abs(v),std::abs(next)}))throw std::runtime_error("Conflicting P2 Dirichlet data");
                    v=next;set=true;
                }
                if(set){fixed.push_back(s.algebra_ids[i]);values.push_back(stage?(1-af)*accepted[i]+af*v:v);}
            }
            for(const auto& item:contributions) {
                for(double x:item.matrix)if(!std::isfinite(x))throw std::runtime_error("Non-finite P2 matrix");
                for(double x:item.rhs)if(!std::isfinite(x))throw std::runtime_error("Non-finite P2 load");
            }
        });
        LinearResult solution;
        try {
            LinearSystem system(comm,layout);
            for(const auto& item:contributions)system.add(item.n,item.ids.data(),item.matrix.data(),item.rhs.data());
            system.constrain(fixed,values);
            if(nullspace)system.constant_nullspace(1e-11);
            solution=system.solve(config.solver,true);
        }catch(const LinearSolveFailure& error) {
            if(!c.transient)throw;
            clock.reject(error.what());
            if(mesh.rank==0)std::cout<<"step_retry="<<clock.retries<<" time="<<clock.time<<" next_dt="<<clock.next_dt<<" reason="<<error.what()<<'\n';
            continue;
        }
        auto next=solution.values,next_rate=rate;
        if(alpha&&c.transient)for(std::size_t i=0;i<next.size();++i) {
            next_rate[i]=stage?alpha_map.endpoint_rate(accepted[i],rate[i],next[i]):(next[i]-accepted[i])/h;
            if(stage)next[i]=alpha_map.endpoint(accepted[i],next[i]);
        }
        local_stage(comm,"endpoint",[&] {
            for(double x:next)if(!std::isfinite(x))throw std::runtime_error("Non-finite P2 endpoint");
            for(double x:next_rate)if(!std::isfinite(x))throw std::runtime_error("Non-finite P2 rate");
        });
        double moments[3]{},total[3]{};
        for(std::size_t ci=0;ci<s.cells.size();++ci)for(const auto& q:points[ci]) {
            moments[0]+=q.weight;moments[2]+=q.weight*exact_p2(c,q.x,end).u;
            for(int i=0;i<6;++i)moments[1]+=q.weight*q.basis.value[i]*next[s.cells[ci][i]];
        }
        MPI_Allreduce(moments,total,3,MPI_DOUBLE,MPI_SUM,comm);
        if(!(total[0]>0))throw std::runtime_error("Empty P2 domain");
        // The transient mass term anchors constants. Only steady Neumann
        // solutions use a physical FE zero mean (never a nodal arithmetic mean).
        const double exact_shift=nullspace?total[2]/total[0]:0;
        if(nullspace)for(auto& u:next)u-=total[1]/total[0];
        double norms[2]{},all_norms[2]{};
        for(std::size_t ci=0;ci<s.cells.size();++ci)for(const auto& q:points[ci]) {
            double u=0,dx=0,dy=0;for(int i=0;i<6;++i){const double v=next[s.cells[ci][i]];u+=v*q.basis.value[i];dx+=v*q.basis.gradient[i][0];dy+=v*q.basis.gradient[i][1];}
            const auto e=exact_p2(c,q.x,end);norms[0]+=q.weight*std::pow(u-e.u+exact_shift,2);norms[1]+=q.weight*(std::pow(dx-e.dx,2)+std::pow(dy-e.dy,2));
        }
        MPI_Allreduce(norms,all_norms,2,MPI_DOUBLE,MPI_SUM,comm);
        if(c.transient) {
            if(bdf)history.commit(accepted,h);
            accepted=std::move(next);rate=std::move(next_rate);ready=true;clock.accept();
            if(clock.at_event()){history.previous_dt=0;ready=false;}
        }else {accepted=std::move(next);steady_done=true;}
        if(!config.checkpoint.empty()) {
            Checkpoint saved{clock.step,{{"scalar",accepted}},clock.time,clock.next_dt};
            if(bdf){saved.fields["previous"]=history.previous;saved.fields["time_metadata"]={history.previous_dt};}
            if(alpha){saved.fields["rate"]=rate;saved.fields["time_metadata"]={ready?1.:0.};}
            write_checkpoint(comm,config.checkpoint,mesh,signature,saved);
        }
        write_p2(comm,mesh,s,config,accepted,alpha?&rate:nullptr);
        if(c.transient) {
            auto output=config;output.output=config.output.parent_path()/(series_path.stem().string()+"_step"+std::to_string(clock.step)+".vtu");
            write_p2(comm,mesh,s,output,accepted,alpha?&rate:nullptr);
            local_stage(comm,"series publication",[&] {
                if(mesh.rank!=0)return;
                auto index=output.output;if(mesh.ranks>1)index.replace_extension(".pvtu");
                series.push_back({clock.time,index.filename().string()});
                std::ofstream out;out.exceptions(std::ios::badbit|std::ios::failbit);out.open(series_path.string()+".tmp");
                out<<std::setprecision(17)<<"<VTKFile type=\"Collection\" version=\"0.1\"><Collection>\n";
                for(const auto& item:series)out<<"<DataSet timestep=\""<<item.first<<"\" group=\"\" part=\"0\" file=\""<<xml(item.second)<<"\"/>\n";
                out<<"</Collection></VTKFile>\n";out.close();std::filesystem::rename(series_path.string()+".tmp",series_path);
            });
        }
        if(mesh.rank==0) {
            std::cout<<std::setprecision(17)<<"scalar_p2 degree=2 dofs="<<s.global<<" area="<<total[0]<<" integral="<<(nullspace?0:total[1])<<" true_residual="<<solution.true_residual
                <<" scalar_step="<<clock.step<<" time="<<end<<" accepted_dt="<<(c.transient?h:0)<<" evaluation_time="<<evaluation_time<<" time_order="<<(stage?2:derivative.order);
            if(!c.manufactured.empty())std::cout<<" l2_error="<<std::sqrt(all_norms[0])<<" h1_error="<<std::sqrt(all_norms[1]);
            std::cout<<'\n';
        }
    }
    if(mesh.rank==0)std::cout<<"status=success\n";
}
}
