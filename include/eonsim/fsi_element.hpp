#pragma once
/** @file
 * @brief 活塞 FSI 的局部流体/ALE 残量，参考网格扩展不产生物理界面力。 */
#include "eonsim/fluid_element.hpp"
namespace eonsim {
struct FsiElementData {
    std::array<Point,4> reference;
    std::array<double,16> previous_fluid{};
    std::array<Point,4> previous_mesh{};
    std::vector<std::array<int,3>> inlet_faces;
    FluidParameters fluid;
    double inlet_pressure=1;
};
/// 节点优先 [ux,uy,uz,p,dmx,dmy,dmz]，无约束投影，无通信或历史写入。
std::array<double,28> fsi_element_residual(const FsiElementData& data,const std::array<double,28>& state);
/// 小算例基线：完整局部中心差分，包括几何/网格速度/压力面积导数；不是解析切线。
std::array<double,784> fsi_element_tangent(const FsiElementData& data,const std::array<double,28>& state);
}
