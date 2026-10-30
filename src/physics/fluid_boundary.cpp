#include "eonsim/fluid_boundary.hpp"
#include "eonsim/quadrature.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <limits>
#include <stdexcept>
namespace eonsim {
namespace {
Point evaluate(const FluidBoundary& b,const Point& x) {
    Point v=b.value;
    for(int i=0;i<Space3::dimension;++i) for(int j=0;j<Space3::dimension;++j) v[i]+=b.gradient[Space3::index(i,j)]*(x[j]-b.origin[j]);
    for(double value:v) if(!std::isfinite(value)) throw std::runtime_error("Nonfinite evaluated boundary value");
    return v;
}
bool equal(double a,double b) { return std::abs(a-b)<=1e-12*std::max({1.,std::abs(a),std::abs(b)}); }
struct NodalBoundary {
    Space3::Vector<bool> fixed{};
    Point value{},ramp{};
};
NodalBoundary merged_boundary(const MeshPartition& mesh,std::size_t node,const std::vector<FluidBoundary>& boundaries,
                              const std::map<int,std::size_t>& lookup,bool transient) {
    NodalBoundary result;
    for(int tag:mesh.node_boundary_tags[node]) {
        const auto& b=boundaries.at(lookup.at(tag));
        if(b.type!=FluidBoundary::Type::velocity) continue;
        const auto value=evaluate(b,mesh.nodes[node].position);
        for(int c:b.components) {
            if(result.fixed[c]&&(!equal(value[c],result.value[c])||(transient&&value[c]!=0&&result.ramp[c]!=b.ramp_time)))
                throw std::runtime_error("Conflicting velocity/displacement conditions at mesh node "+std::to_string(mesh.nodes[node].global_id));
            result.fixed[c]=true; result.value[c]=value[c]; result.ramp[c]=b.ramp_time;
        }
    }
    return result;
}
}
double boundary_scale(double ramp_time,double t,bool transient) { return transient&&ramp_time>0?std::min(t/ramp_time,1.):1.; }
FluidBoundaryPlan prepare_vector_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const AlgebraLayout& layout,const std::vector<FluidBoundary>& boundaries,const std::vector<TriangleGeometry>& surfaces,
    int stride,bool transient,std::optional<PressureGauge> gauge)
{
    std::map<int,std::size_t> lookup;
    for(std::size_t i=0;i<boundaries.size();++i) lookup.emplace(boundaries[i].tag,i);
    std::vector<int> seen(lookup.size(),0),all(seen.size());
    for(const auto& f:mesh.boundary) {
        const auto b=lookup.find(f.physical_tag);
        if(b==lookup.end()) throw std::runtime_error("Missing condition for boundary tag "+std::to_string(f.physical_tag));
        seen[b->second]=1;
    }
    MPI_Allreduce(seen.data(),all.data(),static_cast<int>(all.size()),MPI_INT,MPI_MAX,comm);
    for(std::size_t i=0;i<all.size();++i) if(!all[i]) throw std::runtime_error("Configured boundary tag not found: "+std::to_string(boundaries[i].tag));
    FluidBoundaryPlan plan;
    if(stride==Tet4Flow::components) {
        double free_normal=0,total_free=0;
        for(std::size_t f=0;f<mesh.boundary.size();++f) for(auto n:mesh.boundary[f].nodes) {
            const auto b=merged_boundary(mesh,n,boundaries,lookup,transient);
            for(int c=0;c<Space3::dimension;++c) if(!b.fixed[c]) free_normal+=surfaces[f].area*surfaces[f].normal[c]*surfaces[f].normal[c];
        }
        MPI_Allreduce(&free_normal,&total_free,1,MPI_DOUBLE,MPI_SUM,comm);
        if(total_free<1e-20&&!gauge) throw std::runtime_error("Closed normal-velocity boundary requires pressure_gauge or mean normalization");
        if(total_free>=1e-20&&gauge) throw std::runtime_error("Pressure gauge conflicts with free normal boundary");
    }
    // 全速度边界的每个独立 ramp 分量都须满足不可压体积通量相容性。
    // 不能用替换一条压力方程的规范点掩盖不相容的净流入。
    if(gauge) {
        std::map<double,std::size_t> ramps;
        for(const auto& b:boundaries) ramps.emplace(transient?b.ramp_time:0,ramps.size());
        std::vector<double> local(2*ramps.size(),0),global(local.size());
        for(std::size_t f=0;f<mesh.boundary.size();++f) {
            for(auto n:mesh.boundary[f].nodes) {
                // 面节点的最终速度可能由相交标签共同约束；只能使用已合并的分量及各自 ramp。
                const auto b=merged_boundary(mesh,n,boundaries,lookup,transient);
                for(int c=0;c<Space3::dimension;++c) if(b.fixed[c]) {
                    const auto offset=2*ramps.at(transient?b.ramp[c]:0);
                    const double flux=surfaces[f].area*Tri3Topology::mean_weight*surfaces[f].normal[c]*b.value[c];
                    local[offset]+=flux; local[offset+1]+=std::abs(flux);
                }
            }
        }
        MPI_Allreduce(local.data(),global.data(),static_cast<int>(global.size()),MPI_DOUBLE,MPI_SUM,comm);
        for(std::size_t i=0;i<global.size();i+=2)
            if(std::abs(global[i])>1e-11*std::max(1.,global[i+1])) throw std::runtime_error("Incompatible prescribed net boundary flux");
    }
    int gauge_count=0,gauge_total=0;
    for(std::size_t n=0;n<mesh.owned_nodes;++n) {
        const auto b=merged_boundary(mesh,n,boundaries,lookup,transient);
        for(int c=0;c<Space3::dimension;++c) if(b.fixed[c])
            plan.constraints.push_back({layout.local_to_global[stride*n+c],b.value[c],b.ramp[c]});
        if(gauge&&mesh.nodes[n].global_id==gauge->node) {
            ++gauge_count;
            plan.constraints.push_back({layout.local_to_global[Tet4Flow::dof(n,Tet4Flow::pressure)],gauge->value,0});
        }
    }
    MPI_Allreduce(&gauge_count,&gauge_total,1,MPI_INT,MPI_SUM,comm);
    if(gauge_total!=(gauge?1:0)) throw std::runtime_error("Pressure gauge must name exactly one mesh node");
    for(std::size_t f=0;f<mesh.boundary.size();++f) {
        const auto& face=mesh.boundary[f]; const auto& g=surfaces[f];
        const auto& b=boundaries[lookup.at(face.physical_tag)];
        if(b.type==FluidBoundary::Type::velocity) continue;
        SurfaceLoad load{}; load.ramp_time=b.ramp_time;
        for(int a=0;a<Tri3Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c)
            load.ids[TriangleVector::dof(a,c)]=layout.local_to_global[stride*face.nodes[a]+c];
        for(const auto& q:BoundaryQuadrature::points) {
            Point x{},traction{};
            for(int a=0;a<Tri3Topology::nodes;++a) for(int c=0;c<Space3::dimension;++c) x[c]+=q.shape[a]*mesh.nodes[face.nodes[a]].position[c];
            if(b.type==FluidBoundary::Type::pressure) for(int c=0;c<Space3::dimension;++c) traction[c]=-b.pressure*g.normal[c];
            else traction=evaluate(b,x);
            for(int a=0;a<Tri3Topology::nodes;++a) for(int c:b.components)
                load.residual[TriangleVector::dof(a,c)]-=g.area*q.weight*q.shape[a]*traction[c];
        }
        plan.loads.push_back(load);
    }
    return plan;
}
FluidBoundaryPlan prepare_fluid_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const AlgebraLayout& layout,const FluidConfig& config,const std::vector<TriangleGeometry>& surfaces)
{
    auto gauge=config.pressure_gauge;
    if(config.mean_pressure) {
        GlobalId local=std::numeric_limits<GlobalId>::max(),global;
        for(std::size_t n=0;n<mesh.owned_nodes;++n) local=std::min(local,mesh.nodes[n].global_id);
        MPI_Allreduce(&local,&global,1,MPI_INT64_T,MPI_MIN,comm);
        gauge=PressureGauge{global,0};
    }
    return prepare_vector_boundaries(comm,mesh,layout,config.boundaries,surfaces,Tet4Flow::components,
        config.mode==FluidConfig::Mode::transient,gauge);
}
std::vector<double> fluid_boundary_signature(const FluidConfig& config)
{
    std::vector<double> values{double(config.boundaries.size())};
    for(const auto& b:config.boundaries) {
        values.insert(values.end(),{double(b.tag),double(b.type),b.pressure,b.ramp_time,double(b.components.size())});
        for(int c:b.components) values.push_back(c);
        values.insert(values.end(),b.value.begin(),b.value.end());
        values.insert(values.end(),b.origin.begin(),b.origin.end());
        values.insert(values.end(),b.gradient.begin(),b.gradient.end());
    }
    values.push_back(config.mean_pressure?1:0);
    values.push_back(config.pressure_gauge?1:0);
    if(config.pressure_gauge) {
        const auto id=static_cast<std::uint64_t>(config.pressure_gauge->node);
        values.insert(values.end(),{double(id>>32),double(id&0xffffffffULL),config.pressure_gauge->value});
    }
    return values;
}
std::vector<BoundarySummary> summarize_fluid_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const FluidConfig& config,const std::vector<TriangleGeometry>& surfaces,const std::vector<double>& state)
{
    std::vector<BoundarySummary> result;
    for(const auto& b:config.boundaries) {
        double local[3]{},sum[3]{};
        for(std::size_t f=0;f<mesh.boundary.size();++f) if(mesh.boundary[f].physical_tag==b.tag) {
            const auto& g=surfaces[f]; local[0]+=g.area;
            for(auto n:mesh.boundary[f].nodes) {
                for(int c=0;c<Space3::dimension;++c) local[1]+=g.area*Tri3Topology::mean_weight*g.normal[c]*state[Tet4Flow::dof(n,c)];
                local[2]+=g.area*Tri3Topology::mean_weight*state[Tet4Flow::dof(n,Tet4Flow::pressure)];
            }
        }
        MPI_Allreduce(local,sum,3,MPI_DOUBLE,MPI_SUM,comm);
        result.push_back({b.tag,sum[0],sum[1],sum[2]/sum[0]});
    }
    return result;
}
}
