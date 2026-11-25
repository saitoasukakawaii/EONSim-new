#include "eonsim/reduced_layout.hpp"
#include "eonsim/fsi_domains.hpp"
#include "eonsim/boundary_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <set>
#include <map>
#include <numeric>
#include <limits>
#include <stdexcept>
namespace eonsim {
PlanarOutletFace::Geometry PlanarOutletFace::geometry(const std::vector<double>& state,int components,int axis) const {
    auto e1=edge1,e2=edge2;
    for(int t=0;t<2;++t) {
        const int component=Tet4Ale::mesh_offset+(axis+1+t)%3;
        const double d0=state[components*nodes[0]+component];
        e1[t]+=state[components*nodes[1]+component]-d0;
        e2[t]+=state[components*nodes[2]+component]-d0;
    }
    Geometry g{};
    g.weight=(e1[0]*e2[1]-e1[1]*e2[0])/6;
    g.gradient[0]={(e1[1]-e2[1])/6,(e2[0]-e1[0])/6};
    g.gradient[1]={e2[1]/6,-e2[0]/6};
    g.gradient[2]={-e1[1]/6,e1[0]/6};
    return g;
}
namespace {
void build_outlet_traces(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains& domains,ReducedLayout& reduced) {
    const auto count=reduced.outlets.size();
    std::map<int,std::size_t> by_tag;
    for(std::size_t i=0;i<count;++i) by_tag.emplace(domains.rcr_outlets[i].tag,i);
    std::vector<std::map<std::size_t,double>> weights(count);
    std::vector<int> local(count+2),global(count+2);
    bool any_moving=false;
    for(std::size_t i=0;i<count;++i) {
        reduced.outlets[i].normal_axis=domains.rcr_outlets[i].moving_plane_axis;
        any_moving|=reduced.outlets[i].normal_axis>=0;
    }
    // Min/max checks include empty partitions and disallow opposite facing or disjoint parallel planes.
    const double inf=std::numeric_limits<double>::infinity();
    std::vector<double> low(2*count,inf),high(2*count,-inf);
    try {
        const auto facets=build_boundary_facets(mesh);
        for(std::size_t i=0;i<mesh.boundary.size();++i) {
            const auto& face=mesh.boundary[i];
            const auto found=by_tag.find(face.physical_tag);
            if(found==by_tag.end()) continue;
            const auto index=found->second;
            auto& port=reduced.outlets[index];
            const auto g=boundary_geometry(mesh,i,facets[i]);
            const bool fluid=mesh.cells[facets[i].cell].physical_tag==domains.fluid_region;
            if(port.normal_axis<0) {
                if(!fluid) local[count]=1;
                for(auto node:face.nodes) for(int c=0;c<Space3::dimension;++c) {
                    const auto offset=static_cast<std::size_t>(node)*reduced.components;
                    if(reduced.global[offset+Tet4Ale::mesh_offset+c]>=0) local[count]=1;
                    weights[index][offset+c]+=g.area*Tri3Topology::mean_weight*g.normal[c];
                }
                continue;
            }
            const int axis=port.normal_axis,s=(axis+1)%3,t=(axis+2)%3;
            if(!fluid||std::hypot(g.normal[s],g.normal[t])>1e-12) local[count+1]=1;
            for(auto node:face.nodes) {
                const auto offset=static_cast<std::size_t>(node)*reduced.components;
                if(reduced.global[offset+Tet4Ale::mesh_offset+axis]>=0) local[count+1]=1;
                if(reduced.global[offset+axis]>=0) local[index]=1;
                const double position=mesh.nodes[node].position[axis];
                low[2*index]=std::min(low[2*index],position);
                high[2*index]=std::max(high[2*index],position);
            }
            low[2*index+1]=std::min(low[2*index+1],g.normal[axis]);
            high[2*index+1]=std::max(high[2*index+1],g.normal[axis]);
            auto nodes=face.nodes;
            const auto edge=[&](LocalId n) {
                const auto& a=mesh.nodes[nodes[0]].position;
                const auto& b=mesh.nodes[n].position;
                return std::array<double,2>{b[s]-a[s],b[t]-a[t]};
            };
            auto e1=edge(nodes[1]),e2=edge(nodes[2]);
            if((e1[0]*e2[1]-e1[1]*e2[0])*g.normal[axis]<0) {
                std::swap(e1,e2);
                std::swap(nodes[1],nodes[2]);
            }
            port.moving_faces.push_back({nodes,e1,e2});
        }
        for(std::size_t i=0;i<count;++i) for(const auto& entry:weights[i]) if(entry.second!=0) {
            reduced.outlets[i].flux_weights.push_back(entry);
            if(reduced.global[entry.first]>=0) local[i]=1;
        }
    } catch(const std::exception&) { local[count]=1; }
    MPI_Allreduce(local.data(),global.data(),static_cast<int>(global.size()),MPI_INT,MPI_MAX,comm);
    if(global[count]) throw std::runtime_error("RCR outlet needs a stationary fluid exterior with free normal flow");
    if(any_moving) {
        MPI_Allreduce(MPI_IN_PLACE,low.data(),static_cast<int>(low.size()),MPI_DOUBLE,MPI_MIN,comm);
        MPI_Allreduce(MPI_IN_PLACE,high.data(),static_cast<int>(high.size()),MPI_DOUBLE,MPI_MAX,comm);
        for(std::size_t i=0;i<count;++i) if(reduced.outlets[i].normal_axis>=0) {
            const auto a=low[2*i],b=high[2*i];
            const double tolerance=64*std::numeric_limits<double>::epsilon()*std::max({1.,std::abs(a),std::abs(b)});
            if(global[count+1]||!global[i]||b-a>tolerance||low[2*i+1]*high[2*i+1]<=0)
                throw std::runtime_error("RCR moving plane requires one oriented fluid exterior plane, fixed normal mesh displacement and free normal flow");
        }
    }
    if(std::find(global.begin(),global.begin()+count,0)!=global.begin()+count)
        throw std::runtime_error("RCR outlet needs a stationary fluid exterior with free normal flow");
}

template<bool Elastic>
ReducedLayout build_layout(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains* domains=nullptr,bool build_pattern=true)
{
    using Layout=CoupledLayout<Tet4Topology,Elastic>;
    constexpr int nc=Layout::components;
    // alias 为同一 rank 的节点主分量索引；-1 固定，-2 为唯一刚体速度。
    int conflict=0,any_conflict=0;
    std::vector<bool> interface_nodes(mesh.nodes.size());
    std::vector<PetscInt> alias(mesh.nodes.size()*nc);
    std::iota(alias.begin(),alias.end(),0);
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        const auto& tags=mesh.node_boundary_tags[n];
        auto has=[&](int t){return std::find(tags.begin(),tags.end(),t)!=tags.end();};
        if(domains) {
            const bool fluid=node_in_region(mesh,n,domains->fluid_region),solid=node_in_region(mesh,n,domains->solid_region);
            interface_nodes[n]=fluid&&solid;
            if(!fluid) for(int c=0;c<Layout::structure_offset;++c) alias[nc*n+c]=-1;
            if(!solid) for(int c=Layout::structure_offset;c<nc;++c) alias[nc*n+c]=-1;
            // The joined mesh stores the shared interface through region incidence.
            // Its two original face tags are absent from the exterior boundary list.
            auto constrain=[&](const auto& entries,int offset,int interface_tag) {
                for(const auto& bc:entries) if(has(bc.tag)||(interface_nodes[n]&&bc.tag==interface_tag))
                    for(int c:bc.components) alias[nc*n+offset+c]=-1;
            };
            if(fluid) {
                constrain(domains->fluid_constraints,0,domains->fluid_interface);
                constrain(domains->mesh_constraints,Layout::mesh_offset,domains->fluid_interface);
            }
            if(solid) constrain(domains->solid_constraints,Layout::structure_offset,domains->solid_interface);
            if(fluid&&solid) for(int c=0;c<Space3::dimension;++c) {
                const auto master=alias[nc*n+Layout::structure_offset+c];
                if(master>=0&&(alias[nc*n+c]<0||alias[nc*n+Layout::mesh_offset+c]<0)) conflict=1;
                alias[nc*n+c]=alias[nc*n+Layout::mesh_offset+c]=master;
            }
            continue;
        }
        interface_nodes[n]=has(2);
        if(Elastic) {
            if(has(1)) for(int c=Layout::structure_offset;c<Layout::components;++c) alias[nc*n+c]=-1;
            if(has(3)||has(4)) alias[nc*n+Layout::structure_offset+1]=-1;
            if(has(5)||has(6)) alias[nc*n+Layout::structure_offset+2]=-1;
        }
        if(has(1)||has(2)||has(3)||has(4)) alias[nc*n+1]=-1;
        if(has(1)||has(2)||has(5)||has(6)) alias[nc*n+2]=-1;
        if(has(1)) alias[nc*n+Layout::mesh_offset]=-1;
        if(has(3)||has(4)) alias[nc*n+Layout::mesh_offset+1]=-1;
        if(has(5)||has(6)) alias[nc*n+Layout::mesh_offset+2]=-1;
        if(has(2)) {
            if(Elastic) for(int c=0;c<Layout::dimension;++c) {
                alias[nc*n+c]=alias[nc*n+Layout::structure_offset+c];
                alias[nc*n+Layout::mesh_offset+c]=alias[nc*n+Layout::structure_offset+c];
            } else { alias[nc*n]=-2; alias[nc*n+Layout::mesh_offset]=-2; alias[nc*n+Layout::mesh_offset+1]=-1; alias[nc*n+Layout::mesh_offset+2]=-1; }
        }
    }
    MPI_Allreduce(&conflict,&any_conflict,1,MPI_INT,MPI_MAX,comm);
    if(any_conflict) throw std::runtime_error("Interface constraints conflict with free structure component");
    ReducedLayout reduced;
    reduced.components=nc;
    reduced.interface_nodes=std::move(interface_nodes);
    auto& l=reduced.algebra;
    const bool body_owner=!Elastic && mesh.rank==mesh.ranks-1;
    const GlobalId port_count=domains?static_cast<GlobalId>(domains->rcr_outlets.size()):0;
    const bool outlet_owner=port_count&&mesh.rank==mesh.ranks-1;
    GlobalId owned=(body_owner?1:0)+(outlet_owner?port_count:0);
    for(std::size_t i=0;i<nc*mesh.owned_nodes;++i) if(alias[i]==static_cast<PetscInt>(i)) ++owned;
    std::vector<GlobalId> counts(mesh.ranks);
    MPI_Allgather(&owned,1,MPI_INT64_T,counts.data(),1,MPI_INT64_T,comm);
    const GlobalId global=std::accumulate(counts.begin(),counts.end(),GlobalId{0});
    if(global>std::numeric_limits<PetscInt>::max()) throw std::runtime_error("Reduced layout exceeds PetscInt");
    l.owned=owned; l.global=global;
    l.begin=std::accumulate(counts.begin(),counts.begin()+mesh.rank,GlobalId{0});
    reduced.body=Elastic?-1:l.global-1;
    reduced.outlets.resize(port_count);
    for(GlobalId i=0;i<port_count;++i) reduced.outlets[i].pressure=static_cast<PetscInt>(global-port_count+i);
    // Only the temporary physical-slot ghost exchange uses nodal numbering.
    // Do not build the unused full nodal sparsity/field layout for this Vec.
    if(mesh.global_nodes>std::numeric_limits<PetscInt>::max()/nc)
        throw std::runtime_error("Field size exceeds PETSc index range");
    std::vector<PetscInt> nodal_ghosts;
    nodal_ghosts.reserve(nc*(mesh.algebra_ids.size()-mesh.owned_nodes));
    for(std::size_t n=mesh.owned_nodes;n<mesh.algebra_ids.size();++n)
        for(int c=0;c<nc;++c) nodal_ghosts.push_back(nc*mesh.algebra_ids[n]+c);
    PetscOwner<Vec,VecDestroy> ids;
    EONSIM_PETSC(VecCreateGhost(comm,nc*mesh.owned_nodes,nc*mesh.global_nodes,nodal_ghosts.size(),
        nodal_ghosts.data(),ids.put()));
    PetscScalar* data;
    EONSIM_PETSC(VecGetArray(ids.get(),&data));
    PetscInt next=l.begin;
    std::vector<PetscInt> independent(nc*mesh.owned_nodes,-1);
    for(std::size_t i=0;i<independent.size();++i) if(alias[i]==static_cast<PetscInt>(i)) {
        independent[i]=next++;
        const int c=i%nc;
        const auto domain=c<Layout::mesh_offset?DofDomain::fluid:
            (c<Layout::structure_offset?DofDomain::mesh:DofDomain::solid);
        const auto quantity=c==Layout::pressure?DofQuantity::pressure:
            (domain==DofDomain::mesh?DofQuantity::displacement:DofQuantity::velocity);
        const auto component=static_cast<std::uint16_t>(c==Layout::pressure?0:
            (domain==DofDomain::mesh?c-Layout::mesh_offset:
             (domain==DofDomain::solid?c-Layout::structure_offset:c)));
        l.owned_semantics.push_back({mesh.nodes[i/nc].global_id,domain,quantity,DofEntity::vertex,component,0,1});
        l.fields[c<Layout::dimension?"velocity":(c==Layout::pressure?"pressure":(c<Layout::structure_offset?"mesh":"structure"))].push_back(independent[i]);
    }
    for(std::size_t i=0;i<independent.size();++i)
        data[i]=alias[i]==-1?-1:(alias[i]==-2?reduced.body:independent.at(alias[i]));
    if(body_owner) {
        l.fields["rigid"].push_back(reduced.body);
        l.owned_semantics.push_back({0,DofDomain::solid,DofQuantity::velocity,DofEntity::body,0,0,0});
    }
    if(outlet_owner) for(std::size_t i=0;i<reduced.outlets.size();++i) {
        l.fields["pressure"].push_back(reduced.outlets[i].pressure);
        l.owned_semantics.push_back({domains->rcr_outlets[i].tag,DofDomain::fluid,DofQuantity::pressure,
                                     DofEntity::boundary,0,0,0});
    }
    for(const auto* name:{"velocity","pressure","mesh"}) (void)l.fields[name];
    (void)l.fields[Elastic?"structure":"rigid"];
    EONSIM_PETSC(VecRestoreArray(ids.get(),&data));
    EONSIM_PETSC(VecGhostUpdateBegin(ids.get(),INSERT_VALUES,SCATTER_FORWARD));
    EONSIM_PETSC(VecGhostUpdateEnd(ids.get(),INSERT_VALUES,SCATTER_FORWARD));
    Vec local; const PetscScalar* read;
    EONSIM_PETSC(VecGhostGetLocalForm(ids.get(),&local)); EONSIM_PETSC(VecGetArrayRead(local,&read));
    reduced.global.resize(alias.size());
    for(std::size_t i=0;i<alias.size();++i) reduced.global[i]=static_cast<PetscInt>(read[i]);
    EONSIM_PETSC(VecRestoreArrayRead(local,&read)); EONSIM_PETSC(VecGhostRestoreLocalForm(ids.get(),&local));
    std::vector<PetscInt> ghosts;
    ghosts.reserve(nodal_ghosts.size()+(!Elastic)+reduced.outlets.size());
    for(auto id:reduced.global) if(id>=0 && (id<l.begin||id>=l.begin+l.owned)) ghosts.push_back(id);
    if(!Elastic&&!body_owner) ghosts.push_back(reduced.body);
    if(!outlet_owner) for(const auto& port:reduced.outlets) ghosts.push_back(port.pressure);
    std::sort(ghosts.begin(),ghosts.end());
    ghosts.erase(std::unique(ghosts.begin(),ghosts.end()),ghosts.end());
    l.local_to_global.reserve(l.owned+ghosts.size());
    for(PetscInt i=0;i<l.owned;++i) l.local_to_global.push_back(l.begin+i);
    l.local_to_global.insert(l.local_to_global.end(),ghosts.begin(),ghosts.end());
    const auto local_id=[&](PetscInt id) -> PetscInt {
        if(id>=l.begin&&id<l.begin+l.owned) return id-l.begin;
        const auto found=std::lower_bound(ghosts.begin(),ghosts.end(),id);
        if(found==ghosts.end()||*found!=id) throw std::logic_error("Missing reduced ghost index");
        return l.owned+static_cast<PetscInt>(found-ghosts.begin());
    };
    reduced.local.reserve(reduced.global.size());
    for(auto id:reduced.global) reduced.local.push_back(id<0?-1:local_id(id));
    if(!Elastic) reduced.body_local=local_id(reduced.body);
    for(auto& port:reduced.outlets) port.local=local_id(port.pressure);
    if(port_count) build_outlet_traces(comm,mesh,*domains,reduced);
    if(!build_pattern) return reduced;
    // 单元列并集允许保守的块稀疏图；body 行的远程贡献也送到 owner。
    PetscOwner<Mat,MatDestroy> graph;
    EONSIM_PETSC(MatCreate(comm,graph.put()));
    EONSIM_PETSC(MatSetSizes(graph.get(),l.owned,l.owned,l.global,l.global));
    EONSIM_PETSC(MatSetType(graph.get(),MATPREALLOCATOR)); EONSIM_PETSC(MatSetUp(graph.get()));
    for(const auto& cell:mesh.cells) {
        std::array<PetscInt,Layout::dofs> dofs;
        PetscInt count=0;
        const auto active=fsi_cell_components(nc,domains,cell.physical_tag);
        for(auto n:cell.nodes) for(int c=active.first;c<active.first+active.count;++c) {
            const auto id=reduced.global[nc*n+c];
            if(id>=0) dofs[count++]=id;
        }
        std::sort(dofs.begin(),dofs.begin()+count);
        count=static_cast<PetscInt>(std::unique(dofs.begin(),dofs.begin()+count)-dofs.begin());
        EONSIM_PETSC(MatSetValues(graph.get(),count,dofs.data(),count,dofs.data(),nullptr,INSERT_VALUES));
    }
    if(body_owner) EONSIM_PETSC(MatSetValue(graph.get(),reduced.body,reduced.body,0,INSERT_VALUES));
    for(const auto& port:reduced.outlets) {
        const auto pressure=port.pressure;
        for(const auto& entry:port.flux_weights) {
            const auto velocity=reduced.global[entry.first];
            if(velocity<0) continue;
            EONSIM_PETSC(MatSetValue(graph.get(),velocity,pressure,0,INSERT_VALUES));
            EONSIM_PETSC(MatSetValue(graph.get(),pressure,velocity,0,INSERT_VALUES));
        }
        for(const auto& face:port.moving_faces) for(auto node:face.nodes) {
            const auto offset=static_cast<std::size_t>(node)*nc;
            const auto normal=reduced.global[offset+port.normal_axis];
            if(normal>=0) {
                EONSIM_PETSC(MatSetValue(graph.get(),normal,pressure,0,INSERT_VALUES));
                EONSIM_PETSC(MatSetValue(graph.get(),pressure,normal,0,INSERT_VALUES));
            }
            for(int t=1;t<=2;++t) {
                const auto geometry=reduced.global[offset+Tet4Ale::mesh_offset+(port.normal_axis+t)%3];
                if(geometry>=0) EONSIM_PETSC(MatSetValue(graph.get(),pressure,geometry,0,INSERT_VALUES));
            }
        }
        if(outlet_owner) EONSIM_PETSC(MatSetValue(graph.get(),pressure,pressure,0,INSERT_VALUES));
    }
    EONSIM_PETSC(MatAssemblyBegin(graph.get(),MAT_FINAL_ASSEMBLY)); EONSIM_PETSC(MatAssemblyEnd(graph.get(),MAT_FINAL_ASSEMBLY));
    // Keep this matrix: the preallocator already knows the column locations.
    // Converting it back to row counts and recreating AIJ discards that work.
    auto& pattern=reduced.jacobian_pattern;
    EONSIM_PETSC(MatCreate(comm,pattern.put())); EONSIM_PETSC(MatSetSizes(pattern.get(),l.owned,l.owned,l.global,l.global));
    EONSIM_PETSC(MatSetType(pattern.get(),MATAIJ));
    EONSIM_PETSC(MatPreallocatorPreallocate(graph.get(),PETSC_TRUE,pattern.get()));
    return reduced;
}
} // namespace
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh,bool build_pattern) { return build_layout<false>(comm,mesh,nullptr,build_pattern); }
ReducedLayout make_elastic_fsi_layout(MPI_Comm comm,const MeshPartition& mesh,bool build_pattern) { return build_layout<true>(comm,mesh,nullptr,build_pattern); }
ReducedLayout make_dual_fsi_layout(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains& domains,bool build_pattern) {
    int counts[4]{},all[4]{};
    for(const auto& c:mesh.cells) {
        if(c.physical_tag==domains.fluid_region) ++counts[0];
        else if(c.physical_tag==domains.solid_region) ++counts[1];
        else counts[3]=1;
    }
    for(std::size_t n=0;n<mesh.owned_nodes;++n) if(node_in_region(mesh,n,domains.fluid_region)&&node_in_region(mesh,n,domains.solid_region)) ++counts[2];
    MPI_Allreduce(counts,all,4,MPI_INT,MPI_SUM,comm);
    if(all[3]) throw std::runtime_error("Unexpected FSI partition region");
    for(int i=0;i<3;++i) if(all[i]==0) throw std::runtime_error("FSI partition missing domain or shared interface");
    std::set<int> required(domains.pressure_tags.begin(),domains.pressure_tags.end());
    auto require_exterior=[&](const auto& entries,int interface_tag) {
        for(const auto& bc:entries) if(bc.tag!=interface_tag) required.insert(bc.tag);
    };
    require_exterior(domains.fluid_constraints,domains.fluid_interface);
    require_exterior(domains.mesh_constraints,domains.fluid_interface);
    require_exterior(domains.solid_constraints,domains.solid_interface);
    for(int tag:required) {
        int local=0,global=0; for(const auto& face:mesh.boundary) if(face.physical_tag==tag) local=1;
        MPI_Allreduce(&local,&global,1,MPI_INT,MPI_MAX,comm);
        if(!global) throw std::runtime_error("FSI partition boundary tag missing");
    }
    return build_layout<true>(comm,mesh,&domains,build_pattern);
}
}
