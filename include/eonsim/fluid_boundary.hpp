#pragma once
/** @file @brief 固定网格的标签边界准备、载荷积分和边界通量诊断。 */
#include "eonsim/boundary_geometry.hpp"
#include "eonsim/config.hpp"
#include "eonsim/linear_system.hpp"
namespace eonsim {
struct PrescribedDof { PetscInt id; double value,ramp_time; };
using TriangleVector=NodalLayout<Tri3Topology,Space3::dimension>;
struct SurfaceLoad {
    TriangleVector::State<PetscInt> ids;
    TriangleVector::State<double> residual{}; // -integral N*t dA，独立于 trial
    double ramp_time;
};
struct FluidBoundaryPlan {
    std::vector<PrescribedDof> constraints; // 仅 owned DoF、已合并相交面的相同条件
    std::vector<SurfaceLoad> loads; // 本 rank 面积分，由 PETSc 向行 owner 累加
};
/** @brief collective 准备：检查标签覆盖、交线约束相容及压力规范；缓存固定几何的面载荷。
 * 三点静态规则精确积分仿射牵引；全部速度条件与规范点只由节点 owner 施加。
 * 同一节点非零速度要求值与时间 ramp 一致，不允许后读条件覆盖前者。
 */
FluidBoundaryPlan prepare_fluid_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const AlgebraLayout& layout,const FluidConfig& config,const std::vector<TriangleGeometry>& surfaces);
/// collective；流体/固体共用的分量约束与载荷准备。stride 为节点全场分量数。
FluidBoundaryPlan prepare_vector_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const AlgebraLayout& layout,const std::vector<FluidBoundary>& boundaries,const std::vector<TriangleGeometry>& surfaces,
    int stride,bool transient,std::optional<PressureGauge> gauge=std::nullopt);
/// t 是当前求解时间；稳态不应用时间 ramp。
double boundary_scale(double ramp_time,double t,bool transient);
/// 将所有边界物理参数纳入重启签名；64 位规范点 ID 分为两个精确可表示的整数。
std::vector<double> fluid_boundary_signature(const FluidConfig& config);
struct BoundarySummary { int tag; double area,flow,pressure; }; // flow 为外向体积流量，pressure 为面积平均
/// collective；只规约每个配置标签的面积、外向流量和压力积分，不收集全局场。
std::vector<BoundarySummary> summarize_fluid_boundaries(MPI_Comm comm,const MeshPartition& mesh,
    const FluidConfig& config,const std::vector<TriangleGeometry>& surfaces,const std::vector<double>& state);
}
