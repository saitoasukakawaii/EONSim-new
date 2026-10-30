#pragma once
/** @file
 * @brief 标签固体及单位块基准的静载和 BE 撤载响应。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/vtu.hpp"
namespace eonsim {
/** @brief 最后接受状态的标签边界观测；分量按全局笛卡尔坐标排列。
 * reference_area 为参考面积 (m²)，mean_displacement/mean_velocity 为参考面积平均 (m、m/s)。
 * reaction 为支座对固体的力 (N)：仅统计本标签位移条件指定的 constrained 分量，
 * 对 owned 节点的原始残量求和，不再乘面积。其余分量为零，不能解释为已测反力。
 * 共享同一受约束 DoF 的标签会重复包含该反力，各标签反力不可直接相加。
 */
struct SolidBoundarySummary {
    int tag=0;
    double reference_area=0;
    Point mean_displacement{},mean_velocity{},reaction{};
    Space3::Vector<bool> constrained{};
};
struct SolidResult {
    NonlinearResult nonlinear;
    std::vector<PointField> fields;
    std::vector<SolidBoundarySummary> boundaries; ///< 仅显式标签模式；所有 rank 返回相同摘要。
    Point support_reaction{}; ///< 仅标签模式；合并后的全部受约束 DoF 各计一次，单位 N。
    /// displacement_error/reaction_x/tip_displacement 仅用于未配置标签边界的单位块基准。
    double strain_energy=0,kinetic_energy=0,displacement_error=0,reaction_x=0,tip_displacement=0;
};
/// collective；显式标签模式使用区域材料和标签边界，并规约面积均值与约束反力。
/// 省略标签边界时使用单位块基准：x=0/y=0/z=0 约束法向分量，x=1 施加均布 x 牵引。
/// 撤载模式先计算静载 accepted 位移，再以速度为 BE 未知量推进；无材料阻尼。
SolidResult solve_solid(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
