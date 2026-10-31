#pragma once
#include "eonsim/mesh.hpp"
#include "eonsim/config.hpp"
#include <mpi.h>
namespace eonsim {
/// Collective Poisson/diffusion P1/Q1 solve with accepted-only time history.
/// Writes endpoint fields and an accepted-step PVD series for transient cases.
void solve_scalar2d(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
