#pragma once
/** @file
 * @brief 参考构形 Tet4 线弹性/Neo-Hookean 与一致质量矩阵。 */
#include "eonsim/tet4.hpp"
namespace eonsim {
struct SolidParameters { double young=100, poisson=.3, density=1, dt=0; bool neo_hookean=false; };
template<class Element> struct SolidElementResult {
    using Layout=NodalLayout<Element,Element::dimension>;
    typename Layout::template State<double> residual{};
    typename Layout::template Matrix<double> tangent{};
    double strain_energy=0,kinetic_energy=0;
};
using SolidElement=SolidElementResult<Tet4Topology>;
/** 节点优先 xyz。静力 dt=0 时 state 为位移；动态为速度，d=d_n+dt*v。
 * old_displacement/old_velocity 是只读时间参考，BE取accepted；BDF2按两层历史重建，dt为有效步长。
 * 返回原始动量残量及对 state 的导数。
 * 参考几何、SI 一致单位；无载荷、通信或历史写入。
 * compute_tangent=false 跳过材料和单元切线，返回 tangent 为零；残量、能量及有效性检查不变。
 */
SolidElement solid_element(const Tet4Geometry& geometry,const SolidParameters& p,
    const Tet4Vector::State<double>& state,const Tet4Vector::State<double>& old_displacement,
    const Tet4Vector::State<double>& old_velocity,bool compute_tangent=true);
}
