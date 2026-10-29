#pragma once
/** @file
 * @brief 弹性单位块静载及 BE 撤载响应。 */
#include "eonsim/nonlinear_system.hpp"
#include "eonsim/mesh.hpp"
#include "eonsim/vtu.hpp"
namespace eonsim {
struct SolidResult {
    NonlinearResult nonlinear;
    std::vector<PointField> fields;
    double strain_energy=0,kinetic_energy=0,displacement_error=0,reaction_x=0,tip_displacement=0;
};
/// collective；x=0/y=0/z=0 各约束法向分量，x=1 施加均布 x 牵引。
/// 撤载模式先计算静载 accepted 位移，再以速度为 BE 未知量推进；无材料阻尼。
SolidResult solve_solid(MPI_Comm comm,const MeshPartition& mesh,const Config& config);
}
