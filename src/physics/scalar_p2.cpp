#include "eonsim/scalar_p2_space.hpp"
#include "eonsim/scalar2d.hpp"
#include "eonsim/tri_p2.hpp"
#include "eonsim/element2d.hpp"
#include "eonsim/quadrature.hpp"
#include "eonsim/linear_system.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <algorithm>
#include <set>
namespace eonsim {
namespace {
struct ExactP2 {double u,dx,dy,lap;};
ExactP2 exact_p2(const std::string& kind,const Point& x) {
    if(kind=="sine") {const double p=std::acos(-1.),u=std::sin(p*x[0])*std::sin(p*x[1]);return {u,p*std::cos(p*x[0])*std::sin(p*x[1]),p*std::sin(p*x[0])*std::cos(p*x[1]),-2*p*p*u};}
    if(kind=="quadratic")return {1+x[0]+2*x[1]+x[0]*x[0]+2*x[1]*x[1],1+2*x[0],2+4*x[1],6};
    return {1+x[0]+2*x[1],1,2,0};
}
double evaluate(const ScalarFunction& f,const Point& x) {
    const auto& c=f.polynomial;const double v=c[0]+c[1]*x[0]+c[2]*x[1]+c[3]*x[0]*x[0]+c[4]*x[0]*x[1]+c[5]*x[1]*x[1];
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
void write_p2(MPI_Comm comm,const MeshPartition& mesh,const ScalarP2Space& s,const Config& config,const std::vector<double>& u) {
    auto path=config.output;if(mesh.ranks>1)path=path.parent_path()/(path.stem().string()+"_rank"+std::to_string(mesh.rank)+".vtu");
    const auto temporary=path.string()+".tmp";
    std::ofstream out;out.exceptions(std::ios::badbit|std::ios::failbit);out.open(temporary);out<<std::setprecision(17);
    out<<"<VTKFile type=\"UnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\"><UnstructuredGrid><Piece NumberOfPoints=\""<<s.points.size()<<"\" NumberOfCells=\""<<s.cells.size()<<"\"><Points><DataArray type=\"Float64\" NumberOfComponents=\"3\" format=\"ascii\">\n";
    for(const auto& p:s.points)out<<p[0]<<' '<<p[1]<<' '<<p[2]<<'\n';
    out<<"</DataArray></Points><Cells><DataArray type=\"Int64\" Name=\"connectivity\" format=\"ascii\">\n";
    for(const auto& c:s.cells){for(auto d:c)out<<d<<' ';out<<'\n';}
    out<<"</DataArray><DataArray type=\"Int64\" Name=\"offsets\" format=\"ascii\">\n";for(std::size_t i=1;i<=s.cells.size();++i)out<<6*i<<' ';
    out<<"</DataArray><DataArray type=\"UInt8\" Name=\"types\" format=\"ascii\">\n";for(std::size_t i=0;i<s.cells.size();++i)out<<"22 ";out<<"</DataArray></Cells><PointData>\n";
    const std::array<std::string,4> names{"u","entity_first","entity_second","owner"};
    for(int k=0;k<4;++k){out<<"<DataArray type=\""<<(k==0?"Float64":"Int64")<<"\" Name=\""<<names[k]<<"\" format=\"ascii\">\n";for(std::size_t i=0;i<u.size();++i){if(k==0)out<<u[i];else if(k<3)out<<s.entities[i][k-1];else out<<s.owners[i];out<<'\n';}out<<"</DataArray>\n";}
    out<<"</PointData></Piece></UnstructuredGrid></VTKFile>\n";out.close();std::filesystem::rename(temporary,path);
    MPI_Barrier(comm);
    if(mesh.rank==0&&mesh.ranks>1){auto index=config.output;index.replace_extension(".pvtu");std::ofstream p;p.exceptions(std::ios::badbit|std::ios::failbit);p.open(index.string()+".tmp");
        p<<"<VTKFile type=\"PUnstructuredGrid\" version=\"0.1\" byte_order=\"LittleEndian\"><PUnstructuredGrid GhostLevel=\"0\"><PPoints><PDataArray type=\"Float64\" NumberOfComponents=\"3\"/></PPoints><PPointData>";
        for(int k=0;k<4;++k)p<<"<PDataArray type=\""<<(k==0?"Float64":"Int64")<<"\" Name=\""<<names[k]<<"\"/>";
        p<<"</PPointData>";for(int r=0;r<mesh.ranks;++r)p<<"<Piece Source=\""<<config.output.stem().string()<<"_rank"<<r<<".vtu\"/>";
        p<<"</PUnstructuredGrid></VTKFile>";p.close();std::filesystem::rename(index.string()+".tmp",index);
    }
}
}
void solve_scalar_p2(MPI_Comm comm,const MeshPartition& mesh,const ScalarP2Space& s,const Config& config) {
    const auto& c=config.scalar2d;
    if(c.transient||!c.regions.empty()||mesh.topological_dimension!=2)throw std::runtime_error("P2 supports steady uniform-coefficient Tri3 Poisson only");
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
    const bool nullspace=!anchored;
    for(const auto& b:bc){int found=0,all=0;for(const auto& e:mesh.edges)found|=e.physical_tag==b.first;MPI_Allreduce(&found,&all,1,MPI_INT,MPI_MAX,comm);if(!all)throw std::runtime_error("P2 boundary absent from mesh");}
    for(const auto& e:mesh.edges)if(!bc.count(e.physical_tag))throw std::runtime_error("Missing P2 boundary condition");
    std::vector<std::vector<P2Point>> points;for(const auto& cell:mesh.cells2)points.push_back(quadrature(mesh,cell));
    LinearSystem system(comm,layout);
    for(std::size_t ci=0;ci<s.cells.size();++ci){std::array<PetscInt,6> ids;for(int a=0;a<6;++a)ids[a]=s.algebra_ids[s.cells[ci][a]];std::array<double,36> a{};std::array<double,6> b{};
        for(const auto& q:points[ci]){const double f=c.manufactured.empty()?evaluate(c.source,q.x):-c.diffusivity*exact_p2(c.manufactured,q.x).lap;
            for(int i=0;i<6;++i){b[i]+=q.weight*q.basis.value[i]*f;for(int j=i;j<6;++j){const double v=q.weight*c.diffusivity*(q.basis.gradient[i][0]*q.basis.gradient[j][0]+q.basis.gradient[i][1]*q.basis.gradient[j][1]);a[6*i+j]+=v;if(i!=j)a[6*j+i]+=v;}}}
        system.add(6,ids.data(),a.data(),b.data());
    }
    for(std::size_t ei=0;ei<mesh.edges.size();++ei){const auto& edge=mesh.edges[ei];const auto& data=bc.at(edge.physical_tag);if(data.type==ScalarBoundary::Type::dirichlet)continue;
        const auto& x=mesh.nodes[edge.nodes[0]].position;const auto& y=mesh.nodes[edge.nodes[1]].position;const double length=std::hypot(y[0]-x[0],y[1]-x[1]);
        std::array<PetscInt,3> ids;for(int i=0;i<3;++i)ids[i]=s.algebra_ids[s.boundaries[ei][i]];std::array<double,9> zero{};std::array<double,3> b{};
        for(int j=0;j<4;++j){const double t=GaussLegendre<4>::points[j];Point p{};for(int d=0;d<3;++d)p[d]=(1-t)*x[d]+t*y[d];const auto e=exact_p2(c.manufactured,p);const double g=c.manufactured.empty()?evaluate(data.value,p):c.diffusivity*(e.dx*(y[1]-x[1])-e.dy*(y[0]-x[0]))/length+data.robin_coefficient*e.u;
            const std::array<double,3> shape{(1-t)*(1-2*t),t*(2*t-1),4*t*(1-t)};for(int i=0;i<3;++i){b[i]+=length*GaussLegendre<4>::weights[j]*shape[i]*g;
                for(int l=i;l<3;++l){const double entry=length*GaussLegendre<4>::weights[j]*data.robin_coefficient*shape[i]*shape[l];zero[3*i+l]+=entry;if(i!=l)zero[3*l+i]+=entry;}}}
        system.add(3,ids.data(),zero.data(),b.data());
    }
    std::vector<PetscInt> fixed;std::vector<double> values;
    for(std::size_t i=0;i<s.owned;++i){bool set=false;double v=0;for(int tag:s.boundary_tags[i]){const auto& b=bc.at(tag);if(b.type!=ScalarBoundary::Type::dirichlet)continue;double next=c.manufactured.empty()?evaluate(b.value,s.points[i]):exact_p2(c.manufactured,s.points[i]).u;if(set&&std::abs(v-next)>1e-12*std::max({1.,std::abs(v),std::abs(next)}))throw std::runtime_error("Conflicting P2 Dirichlet data");v=next;set=true;}if(set){fixed.push_back(s.algebra_ids[i]);values.push_back(v);}}
    system.constrain(fixed,values);
    if(nullspace)system.constant_nullspace(1e-11);
    auto solution=system.solve(config.solver,true);
    // Normalize with the physical FE volume integral, not the nodal mean:
    // P2 vertex shape integrals vanish on affine triangles.
    double exact_shift=0;
    if(nullspace) {
        double moments[3]{},total_moments[3]{};
        for(std::size_t ci=0;ci<s.cells.size();++ci)for(const auto& q:points[ci]) {
            double u=0;for(int i=0;i<6;++i)u+=solution.values[s.cells[ci][i]]*q.basis.value[i];
            moments[0]+=q.weight;moments[1]+=q.weight*u;moments[2]+=q.weight*exact_p2(c.manufactured,q.x).u;
        }
        MPI_Allreduce(moments,total_moments,3,MPI_DOUBLE,MPI_SUM,comm);
        if(!(total_moments[0]>0))throw std::runtime_error("Empty P2 domain");
        for(auto& u:solution.values)u-=total_moments[1]/total_moments[0];
        exact_shift=total_moments[2]/total_moments[0];
    }
    double local[4]{},global[4]{};
    for(std::size_t ci=0;ci<s.cells.size();++ci)for(const auto& q:points[ci]){double u=0,dx=0,dy=0;for(int i=0;i<6;++i){const auto v=solution.values[s.cells[ci][i]];u+=v*q.basis.value[i];dx+=v*q.basis.gradient[i][0];dy+=v*q.basis.gradient[i][1];}const auto e=exact_p2(c.manufactured,q.x);local[0]+=q.weight;local[1]+=q.weight*u;local[2]+=q.weight*(u-e.u+exact_shift)*(u-e.u+exact_shift);local[3]+=q.weight*((dx-e.dx)*(dx-e.dx)+(dy-e.dy)*(dy-e.dy));}
    MPI_Allreduce(local,global,4,MPI_DOUBLE,MPI_SUM,comm);write_p2(comm,mesh,s,config,solution.values);
    if(mesh.rank==0){std::cout<<std::setprecision(17)<<"scalar_p2 degree=2 dofs="<<s.global<<" area="<<global[0]<<" integral="<<global[1]<<" true_residual="<<solution.true_residual;if(!c.manufactured.empty())std::cout<<" l2_error="<<std::sqrt(global[2])<<" h1_error="<<std::sqrt(global[3]);std::cout<<"\nstatus=success\n";}
}
}
