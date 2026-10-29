#pragma once
/** @file
 * @brief 活塞 FSI 的局部流体/ALE 残量，参考网格扩展不产生物理界面力。 */
#include "eonsim/fluid_element.hpp"
namespace eonsim {
struct FsiElementData {
    Tet4Topology::Nodal<Point> reference;
    Tet4Flow::State<double> previous_fluid{};
    Tet4Topology::Nodal<Point> previous_mesh{};
    std::vector<Tri3Topology::Nodal<int>> inlet_faces;
    FluidParameters fluid;
    double inlet_pressure=1;
};
/// 节点优先 [ux,uy,uz,p,dmx,dmy,dmz]，无约束投影，无通信或历史写入。
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& state);
/// 小算例基线：完整局部中心差分，包括几何/网格速度/压力面积导数；不是解析切线。
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& state);
}
