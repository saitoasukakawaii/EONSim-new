#pragma once
/** @file
 * @brief 固定几何 Tet4/P1-P1 SUPG/PSPG 流体核，无通信或历史提交。 */
#include "eonsim/tet4.hpp"
namespace eonsim {
struct FluidParameters {
    double density = 1, viscosity = 1, dt = 0, tau = 0;
    bool convection = false;
};
template<class Element> struct FluidElementResult {
    using Layout=FluidLayout<Element>;
    typename Layout::template State<double> residual{};
    typename Layout::template Matrix<double> tangent{};
};
using FluidElement=FluidElementResult<Tet4Topology>;
/** 节点优先 [ux,uy,uz,p]；previous 是时间积分器生成的速度参考，mesh_velocity 是当前几何速度。
 * 惯性导数=(state-previous)/dt；BE时previous=accepted、dt=实际步长；BDF2由两层历史重建。
 * dt=0 表示稳态；tau 在一次 Newton 求解中固定。返回 dR/dx，几何与参考保持不变。
 * 使用 SI 一致单位，压力正值表示压缩；残量为惯性+内力，无体力。
 * compute_tangent=false 跳过切线计算并返回零 tangent；残量及有效性检查不变。
 */
FluidElement fluid_element(const Tet4Geometry& geometry, const FluidParameters& parameters,
    const Tet4Flow::State<double>& state, const Tet4Flow::State<double>& previous,
    const Tet4Topology::Nodal<Point>& mesh_velocity, bool compute_tangent=true);
}
