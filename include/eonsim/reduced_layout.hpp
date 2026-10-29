#pragma once
/** @file
 * @brief 单体活塞 FSI 的界面消元和分布式有效编号。 */
#include "eonsim/mesh.hpp"
#include "eonsim/linear_system.hpp"
namespace eonsim {
struct ReducedLayout {
    AlgebraLayout algebra;
    int components=Tet4Ale::components;
    // 每个节点前七分量 [u,v,w,p,dm_x,dm_y,dm_z]；弹性模式另加三个结构速度分量。
    // global/local 给出有效全局/本地编号，界面别名共享对应编号。
    // -1 表示恒定零；刚体界面自由度共享 body，dm_x 的链式系数由时间步给出。
    std::vector<PetscInt> global,local;
    PetscInt body=-1,body_local=-1;
};
/// collective；只交换 ghost 编号和 rank 计数，稀疏图通过 PETSc 分布式预分配器装配。
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh);
/// 共形弹性块：额外节点分量 [vs_x,vs_y,vs_z]，界面流体/网格映射到同节点结构速度。
ReducedLayout make_elastic_fsi_layout(MPI_Comm comm,const MeshPartition& mesh);
}
