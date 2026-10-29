#pragma once
/** @file @brief 单体活塞 FSI 的界面消元和分布式有效编号。 */
#include "eonsim/mesh.hpp"
#include "eonsim/linear_system.hpp"
namespace eonsim {
struct ReducedLayout {
    AlgebraLayout algebra;
    // 每个本地节点七分量 [u,v,w,p,dm_x,dm_y,dm_z] 的有效全局/本地编号。
    // -1 表示恒定零；刚体界面自由度共享 body，dm_x 的链式系数由时间步给出。
    std::vector<PetscInt> global,local;
    PetscInt body=-1,body_local=-1;
};
/// collective；只交换 ghost 编号和 rank 计数，稀疏图通过 PETSc 分布式预分配器装配。
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh);
}
