#include "eonsim/fsi_diagnostics.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>
#include <stdexcept>
namespace eonsim {
std::vector<Tri3Topology::Nodal<LocalId>> fsi_interface_faces(MPI_Comm comm,
    const MeshPartition& mesh,const std::vector<bool>& trace,int fluid_region)
{
    using Face=Tri3Topology::Nodal<LocalId>;
    using Key=Tri3Topology::Nodal<GlobalId>;
    std::vector<Face> candidates;
    std::vector<std::vector<GlobalId>> buckets(mesh.ranks);
    for(const auto& cell:mesh.cells) if(fluid_region==0||cell.physical_tag==fluid_region)
        for(int skip=0;skip<4;++skip) {
            Face face{}; int k=0; bool shared=true;
            for(int a=0;a<4;++a) if(a!=skip) {face[k++]=cell.nodes[a];shared=shared&&trace[cell.nodes[a]];}
            if(!shared) continue;
            Key key; for(int a=0;a<3;++a) key[a]=mesh.nodes[face[a]].global_id;
            std::sort(key.begin(),key.end());
            // Stable routing; local cell ownership guarantees each incident cell sends once.
            std::uint64_t hash=1469598103934665603ULL;
            for(auto id:key) {hash^=static_cast<std::uint64_t>(id);hash*=1099511628211ULL;}
            auto& bucket=buckets[hash%mesh.ranks];
            bucket.insert(bucket.end(),key.begin(),key.end());bucket.push_back(candidates.size());
            candidates.push_back(face);
        }
    std::vector<int> send_count(mesh.ranks),recv_count(mesh.ranks),send_offset(mesh.ranks),recv_offset(mesh.ranks);
    for(int r=0;r<mesh.ranks;++r) send_count[r]=buckets[r].size();
    MPI_Alltoall(send_count.data(),1,MPI_INT,recv_count.data(),1,MPI_INT,comm);
    for(int r=1;r<mesh.ranks;++r) {send_offset[r]=send_offset[r-1]+send_count[r-1];recv_offset[r]=recv_offset[r-1]+recv_count[r-1];}
    std::vector<GlobalId> sent;for(const auto& b:buckets) sent.insert(sent.end(),b.begin(),b.end());
    std::vector<GlobalId> received(std::accumulate(recv_count.begin(),recv_count.end(),0));
    MPI_Alltoallv(sent.data(),send_count.data(),send_offset.data(),MPI_INT64_T,received.data(),recv_count.data(),recv_offset.data(),MPI_INT64_T,comm);
    std::map<Key,int> incidence;
    for(std::size_t i=0;i<received.size();i+=4) ++incidence[{received[i],received[i+1],received[i+2]}];
    for(std::size_t i=0;i<received.size();i+=4) received[i]=incidence.at({received[i],received[i+1],received[i+2]})==1?1:0;
    std::vector<GlobalId> reply(sent.size());
    MPI_Alltoallv(received.data(),recv_count.data(),recv_offset.data(),MPI_INT64_T,reply.data(),send_count.data(),send_offset.data(),MPI_INT64_T,comm);
    std::vector<Face> result;
    for(std::size_t i=0;i<reply.size();i+=4) if(reply[i]) result.push_back(candidates.at(reply[i+3]));
    return result;
}
double fsi_volume_ratio(const Tet4Topology::Nodal<Point>& reference,const Tet4Topology::Nodal<Point>& current) {
    return tet4_geometry(current).volume/tet4_geometry(reference).volume;
}
std::array<double,8> fsi_surface_observation(const Tri3Topology::Nodal<Point>& reference,
    const Tri3Topology::Nodal<Point>& current,const Tri3Topology::Nodal<Point>& displacement,
    const Tri3Topology::Nodal<Point>& velocity)
{
    const auto area=[](const auto& x) {
        Point u{},v{},cross{};
        for(int c=0;c<3;++c){u[c]=x[1][c]-x[0][c];v[c]=x[2][c]-x[0][c];}
        for(int c=0;c<3;++c) cross[c]=u[(c+1)%3]*v[(c+2)%3]-u[(c+2)%3]*v[(c+1)%3];
        const double a=.5*std::sqrt(cross[0]*cross[0]+cross[1]*cross[1]+cross[2]*cross[2]);
        if(!(a>0)||!std::isfinite(a)) throw std::runtime_error("Invalid FSI observation face");
        return a;
    };
    std::array<double,8> result{};result[0]=area(reference);result[1]=area(current);
    for(int a=0;a<3;++a) for(int c=0;c<3;++c) {
        result[2+c]+=result[0]*displacement[a][c]/3;
        result[5+c]+=result[0]*velocity[a][c]/3;
    }
    return result;
}
}
