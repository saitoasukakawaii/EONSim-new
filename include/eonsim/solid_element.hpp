#pragma once
/** @file @brief 参考构形 Tet4 小应变线弹性与一致质量矩阵。 */
#include "eonsim/tet4.hpp"
namespace eonsim {
struct SolidParameters { double young=100, poisson=.3, density=1, dt=0; };
struct SolidElement { std::array<double,12> residual{}; std::array<double,144> tangent{}; double strain_energy=0,kinetic_energy=0; };
/** 节点优先 xyz。静力 dt=0 时 state 为位移；动态为速度，d=d_n+dt*v。
 * old_displacement/old_velocity 只读 accepted；返回原始动量残量及对 state 的导数。
 * 参考几何、SI 一致单位；无载荷、通信或历史写入。
 */
SolidElement solid_element(const Tet4Geometry& geometry,const SolidParameters& p,
    const std::array<double,12>& state,const std::array<double,12>& old_displacement,
    const std::array<double,12>& old_velocity);
}
