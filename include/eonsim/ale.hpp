#pragma once
/** @file @brief 给定网格运动的 ALE 验证：均匀流与匀速剪切壁面。 */
#include "eonsim/fluid.hpp"
namespace eonsim {
struct AleResult { MeshPartition current_mesh; std::vector<PointField> fields; double velocity_error=0,mesh_error=0,min_volume=0; };
/// collective；所有流体未知量收敛后才提交几何/流体历史；本入口不含双向 FSI。
AleResult solve_ale(MPI_Comm comm,const MeshPartition& reference,const Config& config);
}
