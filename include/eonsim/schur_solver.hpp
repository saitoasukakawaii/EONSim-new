#pragma once
/** @file @brief 速度/压力 Schur 及嵌套 FSI 块预条件；字段使用有效 owned 编号。 */
#include "eonsim/linear_system.hpp"
#include <functional>
namespace eonsim {
/** Options which create distinct A00 solves in a PETSc Schur factorization.
 * Prefixes are relative to the containing KSP, without the leading '-'.
 */
struct SchurAuxiliaryOptions { bool inner=false,upper=false; };
/** Collective configuration-only check. The factorization and creation of
 * auxiliary solvers must agree across ranks. PETSc uses the separate upper
 * solver only for FULL; reject its otherwise unused options, including when
 * the initial nonlinear residual is zero. second_name is the second IS name.
 */
SchurAuxiliaryOptions validate_schur_auxiliary_options(MPI_Comm comm,
    const std::string& prefix,const std::string& second_name);
/** Configure an already set-up two-field Schur PC using public PETSc APIs.
 * Calls configure_a00 for each distinct main, interior and upper A00 KSP in
 * that order, then configure_second for the Schur KSP. Aliased KSPs are visited
 * once. All handles are borrowed; callbacks apply defaults followed by each
 * KSP's own options and may recursively configure the same semantic subtree.
 * Installs the interior KSP postsolve check, including when it aliases main:
 * iteration limits remain permitted inexact work, other failures propagate to
 * the parent PC. Child KSP callbacks/handles must not outlive that parent PC.
 */
void configure_schur_subsolvers(MPI_Comm comm,PC pc,
    const std::function<void(KSP)>& configure_a00,
    const std::function<void(KSP)>& configure_second);
/// Validate topology and option conflicts even if the initial residual is zero.
void validate_schur_solver_options(MPI_Comm comm,KSP solver,const AlgebraLayout& layout);
/// collective；matrix 已装配。独立流体为 u/p Schur，FSI 为 flow/mesh/structure 外层分裂。
/// 采用 SELFP: D-C diag(A)^-1 B，速度/压力及椭圆块采用 GAMG；不显式形成 A^-1。
void configure_schur_solver(MPI_Comm comm,KSP solver,const AlgebraLayout& layout,Mat matrix);
}
