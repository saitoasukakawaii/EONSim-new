#include "eonsim/reduced_layout.hpp"
#include "eonsim/fsi_domains.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <set>
#include <map>
#include <numeric>
#include <limits>
#include <stdexcept>
namespace eonsim {
namespace {
template<bool Elastic>
ReducedLayout build_layout(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains* domains=nullptr)
{
    using Layout=CoupledLayout<Tet4Topology,Elastic>;
    constexpr int nc=Layout::components;
    // alias 为同一 rank 的节点主分量索引；-1 固定，-2 为唯一刚体速度。
    std::vector<PetscInt> alias(mesh.nodes.size()*nc);
    std::iota(alias.begin(),alias.end(),0);
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        const auto& tags=mesh.node_boundary_tags[n];
        auto has=[&](int t){return std::find(tags.begin(),tags.end(),t)!=tags.end();};
        if(domains) {
            const bool fluid=node_in_region(mesh,n,domains->fluid_region),solid=node_in_region(mesh,n,domains->solid_region);
            if(!fluid) for(int c=0;c<Layout::structure_offset;++c) alias[nc*n+c]=-1;
            if(!solid) for(int c=Layout::structure_offset;c<nc;++c) alias[nc*n+c]=-1;
            auto constrain=[&](const auto& entries,int offset) { for(const auto& bc:entries) if(has(bc.tag)) for(int c:bc.components) alias[nc*n+offset+c]=-1; };
            if(fluid) { constrain(domains->fluid_constraints,0); constrain(domains->mesh_constraints,Layout::mesh_offset); }
            if(solid) constrain(domains->solid_constraints,Layout::structure_offset);
            if(fluid&&solid) for(int c=0;c<Space3::dimension;++c) {
                const auto master=alias[nc*n+Layout::structure_offset+c];
                if(master>=0&&(alias[nc*n+c]<0||alias[nc*n+Layout::mesh_offset+c]<0)) throw std::runtime_error("Interface constraints conflict with free structure component");
                alias[nc*n+c]=alias[nc*n+Layout::mesh_offset+c]=master;
            }
            continue;
        }
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
    ReducedLayout reduced;
    reduced.components=nc;
    auto& l=reduced.algebra;
    const bool body_owner=!Elastic && mesh.rank==mesh.ranks-1;
    GlobalId owned=body_owner?1:0;
    for(std::size_t i=0;i<nc*mesh.owned_nodes;++i) if(alias[i]==static_cast<PetscInt>(i)) ++owned;
    std::vector<GlobalId> counts(mesh.ranks);
    MPI_Allgather(&owned,1,MPI_INT64_T,counts.data(),1,MPI_INT64_T,comm);
    const GlobalId global=std::accumulate(counts.begin(),counts.end(),GlobalId{0});
    if(global>std::numeric_limits<PetscInt>::max()) throw std::runtime_error("Reduced layout exceeds PetscInt");
    l.owned=owned; l.global=global;
    l.begin=std::accumulate(counts.begin(),counts.begin()+mesh.rank,GlobalId{0});
    reduced.body=Elastic?-1:l.global-1;
    std::vector<int> components(nc); std::iota(components.begin(),components.end(),0);
    const auto nodal=make_field_layout(mesh,nc,{{"node",components}});
    PetscOwner<Vec,VecDestroy> ids;
    EONSIM_PETSC(VecCreateGhost(comm,nodal.owned,nodal.global,nodal.local_to_global.size()-nodal.owned,
        nodal.local_to_global.data()+nodal.owned,ids.put()));
    PetscScalar* data;
    EONSIM_PETSC(VecGetArray(ids.get(),&data));
    PetscInt next=l.begin;
    std::vector<PetscInt> independent(nc*mesh.owned_nodes,-1);
    for(std::size_t i=0;i<independent.size();++i) if(alias[i]==static_cast<PetscInt>(i)) {
        independent[i]=next++;
        const int c=i%nc;
        l.fields[c<Layout::dimension?"velocity":(c==Layout::pressure?"pressure":(c<Layout::structure_offset?"mesh":"structure"))].push_back(independent[i]);
    }
    for(std::size_t i=0;i<independent.size();++i)
        data[i]=alias[i]==-1?-1:(alias[i]==-2?reduced.body:independent.at(alias[i]));
    if(body_owner) l.fields["rigid"].push_back(reduced.body);
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
    std::set<PetscInt> ghosts;
    for(auto id:reduced.global) if(id>=0 && (id<l.begin||id>=l.begin+l.owned)) ghosts.insert(id);
    if(!Elastic&&!body_owner) ghosts.insert(reduced.body);
    for(PetscInt i=0;i<l.owned;++i) l.local_to_global.push_back(l.begin+i);
    l.local_to_global.insert(l.local_to_global.end(),ghosts.begin(),ghosts.end());
    std::map<PetscInt,PetscInt> lookup;
    for(std::size_t i=0;i<l.local_to_global.size();++i) lookup[l.local_to_global[i]]=i;
    for(auto id:reduced.global) reduced.local.push_back(id<0?-1:lookup.at(id));
    if(!Elastic) reduced.body_local=lookup.at(reduced.body);
    // 单元列并集允许保守的块稀疏图；body 行的远程贡献也送到 owner。
    PetscOwner<Mat,MatDestroy> graph,pattern;
    EONSIM_PETSC(MatCreate(comm,graph.put()));
    EONSIM_PETSC(MatSetSizes(graph.get(),l.owned,l.owned,l.global,l.global));
    EONSIM_PETSC(MatSetType(graph.get(),MATPREALLOCATOR)); EONSIM_PETSC(MatSetUp(graph.get()));
    for(const auto& cell:mesh.cells) {
        std::set<PetscInt> unique;
        for(auto n:cell.nodes) for(int c=0;c<nc;++c) if(reduced.global[nc*n+c]>=0) unique.insert(reduced.global[nc*n+c]);
        std::vector<PetscInt> dofs(unique.begin(),unique.end());
        EONSIM_PETSC(MatSetValues(graph.get(),dofs.size(),dofs.data(),dofs.size(),dofs.data(),nullptr,INSERT_VALUES));
    }
    if(body_owner) EONSIM_PETSC(MatSetValue(graph.get(),reduced.body,reduced.body,0,INSERT_VALUES));
    EONSIM_PETSC(MatAssemblyBegin(graph.get(),MAT_FINAL_ASSEMBLY)); EONSIM_PETSC(MatAssemblyEnd(graph.get(),MAT_FINAL_ASSEMBLY));
    EONSIM_PETSC(MatCreate(comm,pattern.put())); EONSIM_PETSC(MatSetSizes(pattern.get(),l.owned,l.owned,l.global,l.global));
    EONSIM_PETSC(MatSetType(pattern.get(),MATAIJ));
    EONSIM_PETSC(MatPreallocatorPreallocate(graph.get(),PETSC_TRUE,pattern.get()));
    l.diagonal.resize(l.owned); l.off_diagonal.resize(l.owned);
    for(PetscInt row=l.begin;row<l.begin+l.owned;++row) {
        PetscInt n; const PetscInt* cols;
        EONSIM_PETSC(MatGetRow(pattern.get(),row,&n,&cols,nullptr));
        for(PetscInt i=0;i<n;++i) ++(cols[i]>=l.begin&&cols[i]<l.begin+l.owned?l.diagonal[row-l.begin]:l.off_diagonal[row-l.begin]);
        EONSIM_PETSC(MatRestoreRow(pattern.get(),row,&n,&cols,nullptr));
    }
    return reduced;
}
} // namespace
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh) { return build_layout<false>(comm,mesh); }
ReducedLayout make_elastic_fsi_layout(MPI_Comm comm,const MeshPartition& mesh) { return build_layout<true>(comm,mesh); }
ReducedLayout make_dual_fsi_layout(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains& domains) {
    int counts[3]{},all[3]{};
    for(const auto& c:mesh.cells) {
        if(c.physical_tag==domains.fluid_region) ++counts[0];
        else if(c.physical_tag==domains.solid_region) ++counts[1];
        else throw std::runtime_error("Unexpected FSI partition region");
    }
    for(std::size_t n=0;n<mesh.owned_nodes;++n) if(node_in_region(mesh,n,domains.fluid_region)&&node_in_region(mesh,n,domains.solid_region)) ++counts[2];
    MPI_Allreduce(counts,all,3,MPI_INT,MPI_SUM,comm);
    for(int n:all) if(n==0) throw std::runtime_error("FSI partition missing domain or shared interface");
    std::set<int> required(domains.pressure_tags.begin(),domains.pressure_tags.end());
    for(const auto* list:{&domains.fluid_constraints,&domains.mesh_constraints,&domains.solid_constraints}) for(const auto& c:*list) required.insert(c.tag);
    for(int tag:required) {
        int local=0,global=0; for(const auto& face:mesh.boundary) if(face.physical_tag==tag) local=1;
        MPI_Allreduce(&local,&global,1,MPI_INT,MPI_MAX,comm);
        if(!global) throw std::runtime_error("FSI partition boundary tag missing");
    }
    return build_layout<true>(comm,mesh,&domains);
}
}
