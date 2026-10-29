#pragma once
/** @file @brief 速度/压力 Schur 及嵌套 FSI 块预条件；字段使用有效 owned 编号。 */
#include "eonsim/linear_system.hpp"
namespace eonsim {
/// collective；matrix 已装配。独立流体为 u/p Schur，FSI 为 flow/mesh/structure 外层分裂。
/// 采用 SELFP: D-C diag(A)^-1 B，速度/压力及椭圆块采用 GAMG；不显式形成 A^-1。
void configure_schur_solver(MPI_Comm comm,KSP solver,const AlgebraLayout& layout,Mat matrix);
}
