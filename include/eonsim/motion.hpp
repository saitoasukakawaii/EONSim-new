#pragma once
/** @file
 * @brief 单轴刚体 BE 和给定位移的参考网格向量 Laplace 扩展。 */
#include "eonsim/mesh.hpp"
#include "eonsim/linear_system.hpp"
namespace eonsim {
struct RigidState { double position=0,velocity=0; };
struct RigidParameters { double mass=1,damping=.1,stiffness=10; };
/// 纯局部残量；trial未知量为速度。位置=reference.position+displacement_dt*velocity，
/// 加速度=(velocity-reference.velocity)/dt；BE传accepted与实际步长，BDF2传历史参考与有效步长。
/// displacement_dt=0时使用dt；alpha分别传惯性与位移链系数。不提交历史。
double rigid_residual(const RigidParameters& p,const RigidState& accepted,double dt,double velocity,double force,double displacement_dt=0);
/// 给定外力的闭式 BE 步，与未来单体刚体行使用同一离散。
RigidState rigid_step(const RigidParameters& p,const RigidState& accepted,double dt,double force);
/// collective。节点优先 xyz 约束仅 owned，单位 m；参考几何不变，返回 owned+ghost 位移。
std::vector<double> extend_mesh(MPI_Comm comm,const MeshPartition& reference,
    const std::vector<PetscInt>& dofs,const std::vector<double>& prescribed,const SolverConfig& solver);
}
