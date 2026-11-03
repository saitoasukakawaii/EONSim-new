#include "eonsim/fsi_diagnostics.hpp"
#include "eonsim/time_step.hpp"
#include <petscsys.h>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace eonsim;
int main(int argc,char** argv) {
    PetscInitialize(&argc,&argv,nullptr,nullptr);
    try {
        auto check=[](bool ok){if(!ok) throw std::runtime_error("FSI diagnostic oracle failed");};
        Tet4Topology::Nodal<Point> ref{Point{0,0,0},Point{1,0,0},Point{0,1,0},Point{0,0,1}},current=ref;
        for(auto& x:current){x[0]*=2;x[1]*=3;x[2]*=4;}
        check(std::abs(fsi_volume_ratio(ref,current)-24)<1e-12);
        auto stage=ref,endpoint=ref;stage[1][0]=.25;endpoint[1][0]=-.5;
        check(fsi_volume_ratio(ref,stage)>0);bool rejected=false;
        try{(void)fsi_volume_ratio(ref,endpoint);}catch(const StepRejected&){rejected=true;}check(rejected);
        Tri3Topology::Nodal<Point> face{Point{0,0,0},Point{2,0,0},Point{0,3,0}},moved=face,d{},v{};
        for(int a=0;a<3;++a){d[a]={face[a][0],2*face[a][1],1};v[a]={2,3,4};for(int c=0;c<3;++c)moved[a][c]+=d[a][c];}
        auto obs=fsi_surface_observation(face,moved,d,v);
        check(std::abs(obs[0]-3)<1e-12&&std::abs(obs[1]-18)<1e-12);
        check(std::abs(obs[2]-2)<1e-12&&std::abs(obs[3]-6)<1e-12&&std::abs(obs[7]-12)<1e-12);
        MeshPartition mesh;MPI_Comm_rank(PETSC_COMM_WORLD,&mesh.rank);MPI_Comm_size(PETSC_COMM_WORLD,&mesh.ranks);
        check(mesh.ranks<=2);mesh.nodes.resize(5);for(int i=0;i<5;++i)mesh.nodes[i].global_id=i+1;
        if(mesh.rank==0) mesh.cells.push_back({1,{0,1,2,3},10});
        if(mesh.ranks==1||mesh.rank==1) mesh.cells.push_back({2,{0,2,1,4},10});
        auto faces=fsi_interface_faces(PETSC_COMM_WORLD,mesh,std::vector<bool>(5,true),0);
        int count=faces.size(),total;MPI_Allreduce(&count,&total,1,MPI_INT,MPI_SUM,PETSC_COMM_WORLD);check(total==6);
        for(auto& c:mesh.cells) if(c.global_id==2) c.physical_tag=20;
        faces=fsi_interface_faces(PETSC_COMM_WORLD,mesh,std::vector<bool>(5,true),10);
        count=faces.size();MPI_Allreduce(&count,&total,1,MPI_INT,MPI_SUM,PETSC_COMM_WORLD);check(total==1);
        if(mesh.rank==0)std::cout<<"FSI geometry, affine surface and distributed face cancellation passed\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';MPI_Abort(PETSC_COMM_WORLD,1);}
    PetscFinalize();
}
