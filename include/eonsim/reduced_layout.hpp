#pragma once
/** @file
 * @brief 单体活塞 FSI 的界面消元和分布式有效编号。 */
#include "eonsim/mesh.hpp"
#include "eonsim/linear_system.hpp"
namespace eonsim {
/** One physical slot's affine trial map and independent test-row projection.
 * x_slot = trial_weight*q[local] + lifting; test_row=-1 discards its equation.
 * The mapping is fixed during one Newton solve. Kernel-internal time derivatives
 * are not part of this map and must not be multiplied twice.
 */
struct ReducedSlot {
    PetscInt column=-1,local=-1,test_row=-1;
    double trial_weight=0,lifting=0;
    double expand(const std::vector<double>& q) const { return lifting+(local<0?0:trial_weight*q.at(local)); }
};
struct ReducedLayout {
    AlgebraLayout algebra;
    int components=Tet4Ale::components;
    // 每个节点前七分量 [u,v,w,p,dm_x,dm_y,dm_z]；弹性模式另加三个结构速度分量。
    // global/local 给出有效全局/本地编号，界面别名共享对应编号。
    // -1 表示恒定零；刚体界面自由度共享 body，dm_x 的链式系数由时间步给出。
    std::vector<PetscInt> global,local;
    std::vector<bool> interface_nodes; ///< Shared trace, owned+ghost mesh node order.
    ReducedSlot slot(std::size_t i,double displacement_from_velocity,double interface_lifting=0) const {
        const bool mesh_trace=interface_nodes.at(i/components)&&
            i%components>=Tet4Ale::mesh_offset&&i%components<Tet4Ale::structure_offset;
        return {global.at(i),local.at(i),mesh_trace?-1:global.at(i),
                local.at(i)<0?0:(mesh_trace?displacement_from_velocity:1),mesh_trace?interface_lifting:0};
    }
    PetscInt body=-1,body_local=-1;
};
/// collective；只交换 ghost 编号和 rank 计数，稀疏图通过 PETSc 分布式预分配器装配。
ReducedLayout make_rigid_fsi_layout(MPI_Comm comm,const MeshPartition& mesh);
/// 共形弹性块：额外节点分量 [vs_x,vs_y,vs_z]，界面流体/网格映射到同节点结构速度。
ReducedLayout make_elastic_fsi_layout(MPI_Comm comm,const MeshPartition& mesh);
/// 独立双域联合网格，inactive 分量消元，界面共享结构速度。
ReducedLayout make_dual_fsi_layout(MPI_Comm comm,const MeshPartition& mesh,const FsiDomains& domains);
}
