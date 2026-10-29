#pragma once
/** @file
 * @brief 固定几何 Tet4/P1-P1 SUPG/PSPG 流体核，无通信或历史提交。 */
#include "eonsim/tet4.hpp"
namespace eonsim {
struct FluidParameters {
    double density = 1, viscosity = 1, dt = 0, tau = 0;
    bool convection = false;
};
struct FluidElement {
    std::array<double,16> residual{};
    std::array<double,256> tangent{};
};
/** 节点优先 [ux,uy,uz,p]；previous 是已接受速度/压力，mesh_velocity 是当前几何速度。
 * dt=0 表示稳态；tau 在一次 Newton 求解中固定。返回 dR/dx，几何与历史保持不变。
 * 使用 SI 一致单位，压力正值表示压缩；残量为惯性+内力，无体力。
 */
FluidElement fluid_element(const Tet4Geometry& geometry, const FluidParameters& parameters,
    const std::array<double,16>& state, const std::array<double,16>& previous,
    const std::array<Point,4>& mesh_velocity, bool compute_tangent=true);
}
