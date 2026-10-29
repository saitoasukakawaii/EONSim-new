#include "eonsim/reduced_layout.hpp"
#include "eonsim/field_layout.hpp"
#include <algorithm>
#include <set>
#include <map>
#include <numeric>
#include <limits>
#include <stdexcept>
namespace eonsim {
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh)
{
    // kind: 0 independent, 1 fixed zero, 2 shared rigid velocity.
    std::vector<int> kind(mesh.nodes.size()*7,0);
    for(std::size_t n=0;n<mesh.nodes.size();++n) {
        const auto& tags=mesh.node_boundary_tags[n];
        auto has=[&](int t){return std::find(tags.begin(),tags.end(),t)!=tags.end();};
        if(has(2)) kind[7*n]=2;
        if(has(1)||has(2)||has(3)||has(4)) kind[7*n+1]=1;
        if(has(1)||has(2)||has(5)||has(6)) kind[7*n+2]=1;
        if(has(1)) kind[7*n+4]=1;
        if(has(2)) kind[7*n+4]=2;
        if(has(3)||has(4)) kind[7*n+5]=1;
        if(has(5)||has(6)) kind[7*n+6]=1;
    }
    ReducedLayout reduced;
    auto& l=reduced.algebra;
    const bool body_owner=mesh.rank==mesh.ranks-1;
    GlobalId owned=std::count(kind.begin(),kind.begin()+7*mesh.owned_nodes,0)+(body_owner?1:0);
    std::vector<GlobalId> counts(mesh.ranks);
    MPI_Allgather(&owned,1,MPI_INT64_T,counts.data(),1,MPI_INT64_T,comm);
    const GlobalId global=std::accumulate(counts.begin(),counts.end(),GlobalId{0});
    if(global>std::numeric_limits<PetscInt>::max()) throw std::runtime_error("Reduced layout exceeds PetscInt");
    l.owned=owned; l.global=global;
    l.begin=std::accumulate(counts.begin(),counts.begin()+mesh.rank,GlobalId{0});
    reduced.body=l.global-1;
    const auto nodal=make_field_layout(mesh,7,{{"node",{0,1,2,3,4,5,6}}});
    PetscOwner<Vec,VecDestroy> ids;
    EONSIM_PETSC(VecCreateGhost(comm,nodal.owned,nodal.global,nodal.local_to_global.size()-nodal.owned,
        nodal.local_to_global.data()+nodal.owned,ids.put()));
    PetscScalar* data;
    EONSIM_PETSC(VecGetArray(ids.get(),&data));
    PetscInt next=l.begin;
    for(std::size_t i=0;i<7*mesh.owned_nodes;++i) {
        data[i]=kind[i]==1?-1:(kind[i]==2?reduced.body:next++);
        if(kind[i]==0) l.fields[i%7<3?"velocity":(i%7==3?"pressure":"mesh")].push_back(static_cast<PetscInt>(data[i]));
    }
    if(body_owner) l.fields["rigid"].push_back(reduced.body);
    for(const auto* name:{"velocity","pressure","mesh","rigid"}) (void)l.fields[name];
    EONSIM_PETSC(VecRestoreArray(ids.get(),&data));
    EONSIM_PETSC(VecGhostUpdateBegin(ids.get(),INSERT_VALUES,SCATTER_FORWARD));
    EONSIM_PETSC(VecGhostUpdateEnd(ids.get(),INSERT_VALUES,SCATTER_FORWARD));
    Vec local; const PetscScalar* read;
    EONSIM_PETSC(VecGhostGetLocalForm(ids.get(),&local)); EONSIM_PETSC(VecGetArrayRead(local,&read));
    reduced.global.resize(kind.size());
    for(std::size_t i=0;i<kind.size();++i) reduced.global[i]=static_cast<PetscInt>(read[i]);
    EONSIM_PETSC(VecRestoreArrayRead(local,&read)); EONSIM_PETSC(VecGhostRestoreLocalForm(ids.get(),&local));
    std::set<PetscInt> ghosts;
    for(auto id:reduced.global) if(id>=0 && (id<l.begin||id>=l.begin+l.owned)) ghosts.insert(id);
    if(!body_owner) ghosts.insert(reduced.body);
    for(PetscInt i=0;i<l.owned;++i) l.local_to_global.push_back(l.begin+i);
    l.local_to_global.insert(l.local_to_global.end(),ghosts.begin(),ghosts.end());
    std::map<PetscInt,PetscInt> lookup;
    for(std::size_t i=0;i<l.local_to_global.size();++i) lookup[l.local_to_global[i]]=i;
    for(auto id:reduced.global) reduced.local.push_back(id<0?-1:lookup.at(id));
    reduced.body_local=lookup.at(reduced.body);
    // 单元列并集允许保守的块稀疏图；body 行的远程贡献也送到 owner。
    PetscOwner<Mat,MatDestroy> graph,pattern;
    EONSIM_PETSC(MatCreate(comm,graph.put()));
    EONSIM_PETSC(MatSetSizes(graph.get(),l.owned,l.owned,l.global,l.global));
    EONSIM_PETSC(MatSetType(graph.get(),MATPREALLOCATOR)); EONSIM_PETSC(MatSetUp(graph.get()));
    for(const auto& cell:mesh.cells) {
        std::set<PetscInt> unique;
        for(auto n:cell.nodes) for(int c=0;c<7;++c) if(reduced.global[7*n+c]>=0) unique.insert(reduced.global[7*n+c]);
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
}
