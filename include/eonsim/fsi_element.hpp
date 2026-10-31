#pragma once
/** @file
 * @brief 活塞 FSI 的局部流体/ALE 残量，参考网格扩展不产生物理界面力。 */
#include "eonsim/fluid_element.hpp"
namespace eonsim {
struct FsiElementData {
    /// 固定参考坐标、几何与 Laplace 矩阵一次构造；trial ALE 坐标不修改这些缓存。
    explicit FsiElementData(const Tet4Topology::Nodal<Point>& coordinates);
    const Tet4Topology::Nodal<Point> reference;
    const Tet4Geometry reference_geometry;
    const Tet4Scalar::Matrix<double> mesh_stiffness;
    /// 时间参考（BE为accepted，BDF2为两层历史重建）；fluid.dt为有效步长。
    /// previous_mesh使用同一映射，保证界面离散网格速度与结构速度一致。
    Tet4Flow::State<double> previous_fluid{};
    Tet4Topology::Nodal<Point> previous_mesh{};
    std::vector<Tri3Topology::Nodal<int>> inlet_faces;
    FluidParameters fluid;
    double mesh_dt=0; ///< 正值指定网格位移到stage速度的链分母；0沿用fluid.dt（BE/BDF2）。
    double inlet_pressure=1;
};
/// 节点优先 [ux,uy,uz,p,dmx,dmy,dmz]，无约束投影，无通信或历史写入。
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& state);
/// 解析体积/梯度导数与固定宽度前向链式传播；包含几何、网格速度和压力面积。
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& state);
/// 中心差分参考，仅用于导数/性能对照；默认求解使用解析几何与前向链式导数。
Tet4Ale::Matrix<double> fsi_element_tangent_fd(const FsiElementData&,const Tet4Ale::State<double>&);

}
