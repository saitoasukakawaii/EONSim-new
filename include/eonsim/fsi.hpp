#pragma once
/** @file @brief 压力驱动单轴活塞、流体、ALE 的单体 SNES 驱动。 */
#include "eonsim/ale.hpp"
namespace eonsim {
struct FsiResult { MeshPartition current_mesh,solid_mesh; std::vector<PointField> fields,solid_fields; double position=0,velocity=0,fluid_force=0,balance=0; };
/// collective；界面速度/位移被消元，网格界面测试行被丢弃；仅整体收敛后提交。
FsiResult solve_fsi(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
