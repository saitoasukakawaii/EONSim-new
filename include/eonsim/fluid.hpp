#pragma once
/** @file
 * @brief 固定网格不可压流：标签边界或内置单位通道基准。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/fluid_boundary.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/vtu.hpp"
namespace eonsim {
struct FluidResult {
    NonlinearResult nonlinear;
    std::vector<PointField> fields;
    std::vector<BoundarySummary> boundaries;
    double inlet_flow=0,outlet_flow=0,pressure_drop=0,velocity_error=0,divergence=0;
};
/// collective；BE 每步整体 SNES 收敛后才提交历史；只返回最终已接受状态。
FluidResult solve_fluid(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
