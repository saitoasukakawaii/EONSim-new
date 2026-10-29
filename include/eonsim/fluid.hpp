#pragma once
/** @file @brief 单位立方体平面通道流：入口/出口速度、y 无滑移、z 对称边界。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/vtu.hpp"
namespace eonsim {
struct FluidResult {
    NonlinearResult nonlinear;
    std::vector<PointField> fields;
    double inlet_flow=0,outlet_flow=0,pressure_drop=0,velocity_error=0,divergence=0;
};
/// collective；BE 每步整体 SNES 收敛后才提交历史；只返回最终已接受状态。
FluidResult solve_fluid(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
