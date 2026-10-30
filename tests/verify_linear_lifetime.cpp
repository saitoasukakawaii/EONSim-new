/** 重复线性求解及失败恢复必须释放每次调用的 KSP/PC。 */
#include "eonsim/linear_system.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace eonsim;
namespace {
int created = 0, destroyed = 0;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
PetscErrorCode apply(PC, Vec x, Vec y) { return VecCopy(x, y); }
PetscErrorCode destroy(PC) { ++destroyed; return PETSC_SUCCESS; }
PetscErrorCode create(PC pc) {
    PetscCall(PCSetType(pc, PCSHELL));
    PetscCall(PCShellSetApply(pc, apply));
    PetscCall(PCShellSetDestroy(pc, destroy));
    ++created;
    return PETSC_SUCCESS;
}
void verify() {
    int rank, ranks;
    MPI_Comm_rank(PETSC_COMM_WORLD, &rank);
    MPI_Comm_size(PETSC_COMM_WORLD, &ranks);
    require(ranks == 1 || ranks == 2, "Verification uses 1/2 ranks");
    EONSIM_PETSC(PCRegister("lifetime_test", create));
    EONSIM_PETSC(PetscOptionsSetValue(nullptr, "-pc_type", "lifetime_test"));
    AlgebraLayout layout;
    layout.global = 2; layout.owned = 2/ranks; layout.begin = rank;
    for (PetscInt i = 0; i < layout.owned; ++i) layout.local_to_global.push_back(layout.begin+i);
    if (ranks == 2) layout.local_to_global.push_back(1-rank);
    layout.diagonal.assign(layout.owned, layout.owned);
    layout.off_diagonal.assign(layout.owned, 2-layout.owned);
    {
        LinearSystem system(PETSC_COMM_WORLD, layout);
        if (rank == 0) {
            const PetscInt dofs[] = {0, 1};
            const double matrix[] = {2, -1, -1, 2}, rhs[] = {0, 3};
            system.add(2, dofs, matrix, rhs);
        }
        system.constrain({}, {});
        SolverConfig config;
        for (int attempt = 0; attempt < 4; ++attempt) {
            // A failed solve between successful calls also exercises stack unwinding.
            const bool fail = attempt == 2;
            if (fail) EONSIM_PETSC(PetscOptionsSetValue(nullptr, "-ksp_max_it", "0"));
            bool rejected = false;
            try {
                const auto result = system.solve(config, attempt % 2 == 0);
                require(!fail, "Iteration exhaustion was accepted");
                for (std::size_t i = 0; i < result.values.size(); ++i)
                    require(std::abs(result.values[i] - (layout.local_to_global[i]+1)) < 1e-10,
                            "Repeated solve changed owned/ghost solution");
            } catch (const std::runtime_error& e) {
                if (!fail || std::string(e.what()).find("Linear solve did not converge") == std::string::npos) throw;
                rejected = true;
            }
            if (fail) EONSIM_PETSC(PetscOptionsClearValue(nullptr, "-ksp_max_it"));
            require(rejected == fail, "Unexpected solve failure state");
            require(created == attempt+1, "Expected a fresh configured PC per call");
            require(destroyed == created, "Solve retained its KSP/PC after return or failure");
        }
    }
    require(destroyed == created, "Unbalanced PC lifetime after system destruction");
    EONSIM_PETSC(PetscOptionsClearValue(nullptr, "-pc_type"));
    if (rank == 0) std::cout << "linear lifetime: 4 PC creations/destructions per rank; success/failure/recovery passed on " << ranks << " ranks\n";
}
}
int main(int argc, char** argv) {
    PetscInitialize(&argc, &argv, nullptr, nullptr);
    try { verify(); }
    catch (const std::exception& e) { std::cerr << e.what() << '\n'; MPI_Abort(PETSC_COMM_WORLD, 1); }
    return PetscFinalize();
}
