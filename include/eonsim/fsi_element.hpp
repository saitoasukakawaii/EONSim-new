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
    /// Positive time (s) selects current regular-Tet4 cell metric coefficients, differentiated in Newton.
    double regular_metric_dt=0;
    double mesh_dt=0; ///< 正值指定网格位移到stage速度的链分母；0沿用fluid.dt（BE/BDF2）。
    double inlet_pressure=1;
};
/// 节点优先 [ux,uy,uz,p,dmx,dmy,dmz]，无约束投影，无通信或历史写入。
Tet4Ale::State<double> fsi_element_residual(const FsiElementData& data,const Tet4Ale::State<double>& state);
struct FsiElementResult {
    Tet4Ale::State<double> residual{};
    Tet4Ale::Matrix<double> tangent{};
};
/// 一次当前几何求值返回完整残量/切线：速度/ALE保留24方向链式导数，四个压力列、参考网格和压力面积块解析计算。
/// 无共享可写状态，可对不同单元并行求值；调用方独占各返回结果，材料/历史输入在求值期间只读。
FsiElementResult fsi_element(const FsiElementData& data,const Tet4Ale::State<double>& state);
/// Same physical residual; P freezes current geometry/ALE transport while
/// differentiating all u/p coefficients. Cell fluid/ALE entries are absent.
FsiElementResult fsi_element_reduced_preconditioner(const FsiElementData& data,const Tet4Ale::State<double>& state);
/// 解析体积/梯度导数与固定宽度前向链式传播；包含几何、网格速度和压力面积。
Tet4Ale::Matrix<double> fsi_element_tangent(const FsiElementData& data,const Tet4Ale::State<double>& state);
/** Exact directional derivative J(state)*direction, without storing the element
 * tangent. One forward AD lane includes current geometry, ALE velocity, pressure,
 * stabilization and moving traction area. No finite-difference step or history mutation.
 */
Tet4Ale::State<double> fsi_element_action(const FsiElementData& data,
    const Tet4Ale::State<double>& state,const Tet4Ale::State<double>& direction);
/** Frozen Newton quadrature data, not a dense element Jacobian. Stores current
 * geometry, primitive gradients, transport, strong residual and metric factors.
 * Rebuild whenever state, history, material or time coefficients change, even
 * when the assembled preconditioner is reused. No history ownership or MPI.
 */
struct FsiElementLinearization {
    std::array<double,132> coefficients{};
    struct Face { Tri3Topology::Nodal<int> nodes; Point edge1,edge2; double factor; };
    std::vector<Face> faces;
};
FsiElementLinearization fsi_prepare_action(const FsiElementData& data,const Tet4Ale::State<double>& state);
Tet4Ale::State<double> fsi_element_action(const FsiElementLinearization& data,const Tet4Ale::State<double>& direction);
/** Batch 1..4 independent cells using SoA arithmetic; supports unequal material,
 * geometry and time coefficients. Output does not alias directions or caches.
 * Pressure face actions use their cached signed edges after the volume batch.
 */
void fsi_element_action_batch(const FsiElementLinearization* const* data,
    const Tet4Ale::State<double>* directions,Tet4Ale::State<double>* result,std::size_t count);
/// 中心差分参考，仅用于导数/性能对照；默认求解使用解析几何与前向链式导数。
Tet4Ale::Matrix<double> fsi_element_tangent_fd(const FsiElementData&,const Tet4Ale::State<double>&);

}
