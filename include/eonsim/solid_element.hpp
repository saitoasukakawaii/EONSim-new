#pragma once
/** @file
 * @brief 参考构形 Tet4 线弹性/Neo-Hookean 与一致质量矩阵。 */
#include "eonsim/tet4.hpp"
#include "eonsim/boundary_geometry.hpp"
namespace eonsim {
struct SolidParameters {
    double young=100, poisson=.3, density=1, dt=0; bool neo_hookean=false;
    double displacement_dt=0; ///< 正值单独指定位移对速度的链系数；0沿用dt（BE/BDF2）。
};
template<class Element> struct SolidElementResult {
    using Layout=NodalLayout<Element,Element::dimension>;
    typename Layout::template State<double> residual{};
    typename Layout::template Matrix<double> tangent{};
    double strain_energy=0,kinetic_energy=0;
};
using SolidElement=SolidElementResult<Tet4Topology>;
struct WallSupportBalance {
    double spring_energy=0, dissipation=0, power_on_wall=0;
};
struct WallSupportFace {
    Tri3Topology::Nodal<int> nodes;
    TriangleGeometry geometry; ///< Normal and area in the reference configuration.
    double stiffness, damping;
    /// d_stage = reference_displacement + displacement_dt * velocity.
    /// A supplied solid element receives the internal restoring residual and optional velocity tangent.
    WallSupportBalance evaluate(const Tet4Vector::State<double>& reference_displacement,
        const Tet4Vector::State<double>& velocity,double displacement_dt,
        SolidElement* assembly=nullptr,bool compute_tangent=false) const;
    /// Exact velocity-tangent action on the fixed reference face. No residual,
    /// energy or dense tangent is formed; callers add contributions from all faces.
    Tet4Vector::State<double> action(const Tet4Vector::State<double>& direction,
        double displacement_dt) const;
};
/** 节点优先 xyz。静力 dt=0 时 state 为位移；动态为速度，d=d_n+dt*v。
 * old_displacement/old_velocity 是只读时间参考，BE取accepted；BDF2按两层历史重建，dt为有效步长。
 * generalized-alpha的位移=old_displacement+displacement_dt*state，惯性仍=(state-old_velocity)/dt。
 * 返回原始动量残量及对 state 的导数。
 * 参考几何、SI 一致单位；无载荷、通信或历史写入。
 * compute_tangent=false 跳过材料和单元切线，返回 tangent 为零；残量、能量及有效性检查不变。
 */
SolidElement solid_element(const Tet4Geometry& geometry,const SolidParameters& p,
    const Tet4Vector::State<double>& state,const Tet4Vector::State<double>& old_displacement,
    const Tet4Vector::State<double>& old_velocity,bool compute_tangent=true);
/** Exact derivative of the same solid residual in one supplied direction.
 * Static state is displacement; dynamic state is velocity, with the same
 * displacement_dt/dt chain and consistent mass as solid_element. Accepted
 * displacement enters the Neo-Hookean deformation, while accepted velocity
 * drops out of its derivative. No residual, energy, material tangent or element
 * tangent is formed. Geometry and history are read-only. Nonfinite actions are
 * rejected; Neo-Hookean deformation-gradient and Jacobian checks retain the
 * same fatal/recoverable distinction as the assembled kernel.
 */
Tet4Vector::State<double> solid_element_action(const Tet4Geometry& geometry,const SolidParameters& p,
    const Tet4Vector::State<double>& state,const Tet4Vector::State<double>& direction,
    const Tet4Vector::State<double>& old_displacement);
/** Frozen material/geometry quadrature data: inverse deformation gradient,
 * Lamé coefficients, time chain and mass; no 9x9 or 12x12 tangent is retained.
 * Rebuild at every Newton state/time/history change. The linear material uses
 * F^-T=I and the equivalent directional expression. No material history writes.
 */
struct SolidElementLinearization { std::array<double,27> coefficients{}; };
SolidElementLinearization solid_prepare_action(const Tet4Geometry& geometry,const SolidParameters& p,
    const Tet4Vector::State<double>& state,const Tet4Vector::State<double>& old_displacement);
Tet4Vector::State<double> solid_element_action(const SolidElementLinearization& data,const Tet4Vector::State<double>& direction);
/// SoA arithmetic on 1..4 independent cells; output must not alias directions.
void solid_element_action_batch(const SolidElementLinearization* const* data,
    const Tet4Vector::State<double>* directions,Tet4Vector::State<double>* result,std::size_t count);
}
