// Apply the existing semantic preconditioner to the captured operator without reassembly.
#include "eonsim/config.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/pc_plan.hpp"
#include "eonsim/reduced_layout.hpp"
#include <cmath>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using namespace eonsim;

void replay(const char* snapshot, const char* partition, const std::string& recipe, const char* output) {
    MPI_Comm comm = PETSC_COMM_WORLD;
    int rank, size;
    MPI_Comm_rank(comm,&rank);
    MPI_Comm_size(comm,&size);
    const auto root = std::filesystem::path(snapshot);
    const auto cfg = read_config((root/"case.json").string());
    auto domains = cfg.fsi.domains;
    if (size != 64 || !cfg.fsi.inlet || domains.rcr_outlets.size() != 1) {
        throw std::runtime_error("Expected the captured 64-rank C problem");
    }
    const int inlet = cfg.fsi.inlet->tag;
    domains.fluid_constraints.push_back({inlet,{0,1,2}});
    domains.mesh_constraints.push_back({inlet,{0,1,2}});
    const auto mesh = read_partition(partition,rank,size);
    const auto reduced = make_dual_fsi_layout(comm,mesh,domains,false);
    const auto& layout = reduced.algebra;
    PetscOwner<Mat,MatDestroy> a;
    EONSIM_PETSC(MatCreate(comm,a.put()));
    EONSIM_PETSC(MatSetSizes(a.get(),layout.owned,layout.owned,layout.global,layout.global));
    EONSIM_PETSC(MatSetType(a.get(),MATAIJ));
    {
        PetscOwner<PetscViewer,PetscViewerDestroy> viewer;
        EONSIM_PETSC(PetscViewerBinaryOpen(comm,(root/"operator.petsc").c_str(),FILE_MODE_READ,viewer.put()));
        EONSIM_PETSC(MatLoad(a.get(),viewer.get()));
    }
    PetscInt begin,end;
    EONSIM_PETSC(MatGetOwnershipRange(a.get(),&begin,&end));
    if (layout.global!=924953 || begin!=layout.begin || end-begin!=layout.owned) {
        throw std::runtime_error("Replayed ownership differs from semantic rows");
    }
    PetscOwner<Vec,VecDestroy> x,b,residual;
    EONSIM_PETSC(MatCreateVecs(a.get(),x.put(),b.put()));
    {
        PetscOwner<PetscViewer,PetscViewerDestroy> viewer;
        EONSIM_PETSC(PetscViewerBinaryOpen(comm,(root/"rhs.petsc").c_str(),FILE_MODE_READ,viewer.put()));
        EONSIM_PETSC(VecLoad(b.get(),viewer.get()));
    }
    EONSIM_PETSC(VecSet(x.get(),0.));
    EONSIM_PETSC(VecDuplicate(b.get(),residual.put()));
    const auto plan = make_pc_plan(comm,layout,recipe);
    PcSchurUpdates updates;
    PetscOwner<KSP,KSPDestroy> ksp;
    EONSIM_PETSC(KSPCreate(comm,ksp.put()));
    EONSIM_PETSC(KSPSetType(ksp.get(),KSPFGMRES));
    EONSIM_PETSC(KSPSetFromOptions(ksp.get()));
    configure_pc_plan(comm,ksp.get(),a.get(),plan,&updates);
    EONSIM_PETSC(KSPSolve(ksp.get(),b.get(),x.get()));
    EONSIM_PETSC(MatMult(a.get(),x.get(),residual.get()));
    EONSIM_PETSC(VecAXPY(residual.get(),-1.,b.get()));
    PetscReal rhs,norm,rtol,atol;
    PetscInt iterations;
    KSPConvergedReason reason;
    EONSIM_PETSC(VecNorm(b.get(),NORM_2,&rhs));
    EONSIM_PETSC(VecNorm(residual.get(),NORM_2,&norm));
    EONSIM_PETSC(KSPGetConvergedReason(ksp.get(),&reason));
    EONSIM_PETSC(KSPGetIterationNumber(ksp.get(),&iterations));
    EONSIM_PETSC(KSPGetTolerances(ksp.get(),&rtol,&atol,nullptr,nullptr));
    PetscOwner<PetscViewer,PetscViewerDestroy> viewer;
    EONSIM_PETSC(PetscViewerBinaryOpen(comm,output,FILE_MODE_WRITE,viewer.put()));
    EONSIM_PETSC(VecView(x.get(),viewer.get()));
    EONSIM_PETSC(PetscPrintf(comm,"snapshot_correction reason=%d iterations=%" PetscInt_FMT
        " rhs=%.17g norm=%.17g rtol=%.17g atol=%.17g\n",
        int(reason),iterations,double(rhs),double(norm),double(rtol),double(atol)));
}
}

int main(int argc,char** argv) {
    if (argc<5 || PetscInitialize(&argc,&argv,nullptr,nullptr)) return 1;
    try {
        replay(argv[1],argv[2],argv[3],argv[4]);
    } catch(const std::exception& e) {
        std::cerr<<"snapshot replay failed: "<<e.what()<<'\n';
        MPI_Abort(PETSC_COMM_WORLD,1);
    }
    return PetscFinalize();
}
